# Case study 01: three stacked faults in lakeflow_framework's packaging

**Repo:** `databricks-solutions/lakeflow_framework` @ `0e8d0ca` (v0.24.1)
**Status:** CONFIRMED by execution. Fix verified: the wheel imports and all 396 unit tests still pass.
**Evidence:** [`evidence/lakeflow_packaging_fix.patch`](evidence/lakeflow_packaging_fix.patch)

## Why this is a good interview story

It has the whole resilience arc. A hypothesis came from reading code. The first attempt to test it was blocked by a *different* fault. I worked around that fault, confirmed the original one, fixed both, and then explained why the project's own test suite could never have caught it. It also teaches the most transferable rule in platform work: **test the artifact you ship, in the environment it will run in.**

## Timeline

**1. Reading the code: a bare import that shouldn't be there.**
`src/lakeflow_framework/dataflow/cdc_snapshot.py:12` does `import pipeline_config`, where every other module does `import lakeflow_framework.pipeline_config as pipeline_config`. The bare name resolves only because a *compat shim* exists at `src/pipeline_config.py`:
```python
# Compat shim — kept until v1.0.0.
from lakeflow_framework import pipeline_config  # noqa: F401
from lakeflow_framework.pipeline_config import *  # noqa: F401, F403
```
`pyproject.toml` uses `[tool.setuptools.packages.find] where = ["src"]`, which collects *packages*, not loose top-level modules.
**Hypothesis:** an installed wheel won't contain the shim, so `import lakeflow_framework` fails.

**2. Running the tests first: 32 collection errors (not the bug I was looking for).**
With plain `pyspark==4.1.1` every test module failed: `ModuleNotFoundError: No module named 'pyspark.dbutils'`. `pyspark.dbutils` exists only in `databricks-connect` or on the Databricks runtime. I installed the repo's **own hash-pinned lockfile** (`pip install --require-hashes --no-deps -r requirements-dev.lock`) and got **396 passed**.
- Side finding: in that environment `pyspark.__version__` reports **3.5.2** (databricks-connect's client), yet `pyspark.pipelines` from 4.1.1 is present. Two distributions wrote into one `pyspark/` directory. It works, but it's fragile and install-order dependent.
- Lesson: *reproduce with the project's pinned environment before blaming the code.*

**3. Fault #1: the package can't be built at all.**
```
$ pip wheel --no-deps .
BackendUnavailable: Cannot import 'setuptools.backends.legacy'
```
`pyproject.toml` declares `build-backend = "setuptools.backends.legacy:build"`. That module exists neither in the lock's setuptools 82.0.1 nor in the newest setuptools (84.0.0, fetched by an isolated build). The standard backend is `setuptools.build_meta`. The README's documented `pip install -e ".[contrib]"` fails the same way. (Consistently, `pip download lakeflow-framework` finds no distribution on PyPI, although the docs mention pip installation.)

**4. Work around fault #1 in a scratch copy to reach the original hypothesis.**
With the backend patched to `setuptools.build_meta`, the wheel builds. Its top-level entries are `['lakeflow_framework', 'lakeflow_framework-0.24.1.dist-info']`, so **no shim**.

**5. Fault #2 confirmed: the installed wheel can't be imported.**
In a clean venv, from `/` (no `src/` on `sys.path`):
```
import lakeflow_framework            FAILED -> ModuleNotFoundError: No module named 'pipeline_config'
import lakeflow_framework.constants  FAILED -> ModuleNotFoundError: No module named 'pipeline_config'
```
Even `.constants` fails, because the package `__init__` eagerly imports `dataflow`, which imports `cdc_snapshot`. A second, lazier bare import exists at `utility.py:531` (`from logger import create_default_logger`).

**6. Fault #3: why the tests are green anyway.**
`pytest.ini` sets `pythonpath = src tests`, so every test run has the shim on the path. `tests/unit/test_package.py::test_core_api_importable` imports `DataFlow` and passes, but only from the source tree, never from the built artifact. The tests README even says "the compat shim layer at `src/*.py` is not exercised". In fact it is exercised implicitly by every import.

**7. The fix: three one-line changes.**
```diff
-build-backend = "setuptools.backends.legacy:build"
+build-backend = "setuptools.build_meta"
-import pipeline_config
+import lakeflow_framework.pipeline_config as pipeline_config
-    from logger import create_default_logger
+    from lakeflow_framework.logger import create_default_logger
```
Result: `wheel import OK, version 0.24.1`, and `396 passed, 8 deselected`.

## What should prevent this class of bug

1. A CI job that **builds the wheel, installs it into a clean venv, and imports it from outside the repo**.
2. A lint rule banning bare intra-package imports (`ruff`'s `TID` rules, or a grep for `^import (pipeline_config|utility|logger|…)` inside `src/lakeflow_framework/`).
3. Removing `src` from `pytest` `pythonpath` for a smoke-test job, or using `pip install .` in the test job instead of path injection.

This is not the first packaging escape. The public history shows `pyyaml` missing from wheel dependencies, which made YAML fail in clean installs (commit `d910588`, #143, per the lakeflow deep-read report). **Two escapes of the same class mean the fix is a check, not another patch.**

## How I'd explain it

- **To the maintainers:** "The wheel can't be built because the declared backend doesn't exist. Once you fix that, it builds but can't be imported, because `cdc_snapshot` uses the pre-1.0 shim import, and the tests can't see it because pytest injects `src/`. Here's a three-line patch and a CI step that imports the built wheel in a clean venv."
- **To a customer platform lead:** "Deploy the framework the documented way (bundle to workspace files), not via pip, until upstream fixes packaging. If you vendor it, pin a commit and run our smoke import in your CI."
