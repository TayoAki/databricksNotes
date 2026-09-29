# Case study 05: "pyarrow is installed", but not where the code runs

**Where:** my own Exercise 03 (`exercises/ex03_execution_and_scaling/lab.py`, the pandas UDF experiment), found while building it.
**Status:** CONFIRMED by execution ([`evidence/which_python_workers.py`](evidence/which_python_workers.py)). The fix lives in `exercises/common/spark_session.py`.

## Why this is a good interview story

It is the smallest possible example of the most important idea in distributed Python: **the driver and the workers are different processes, and they may not even be the same Python.** Every "works in my notebook cell, fails in the job" story has this shape.

## Symptom

The pandas UDF test failed with:
```
ModuleNotFoundError: No module named 'pyarrow'
```
But `import pyarrow` worked in the same script, and `pip show pyarrow` found it in the venv.

Note *where* the failure appeared. Defining the UDF worked. `explain()` worked. The error only came when an action ran the UDF, and the traceback came from a **worker** process. That is lazy evaluation again: the plan is built on the driver, and the Python code runs later, elsewhere.

## Diagnosis: ask the workers who they are

Don't guess which interpreter the workers use; make them tell you. A UDF can return `sys.executable`:

```
== default (venv python run by path, venv not activated)
driver : <scratch>/sparkenv/bin/python
workers: /usr/local/bin/python3 | pyarrow importable: False
== PYSPARK_PYTHON pinned to sys.executable
driver : <scratch>/sparkenv/bin/python
workers: <scratch>/sparkenv/bin/python | pyarrow importable: True
```

The cause is one line in PySpark 4.0.1, `pyspark/core/context.py:324`:
```python
self.pythonExec = os.environ.get("PYSPARK_PYTHON", "python3")
```
With no environment variable, workers launch whatever `python3` is first on `PATH`. I ran the venv's interpreter by absolute path without activating it, so the workers got the system Python, which had no pyarrow. (Plain Python UDFs still worked, because Spark puts its own `pyspark.zip` on the workers' `PYTHONPATH`. That is why the failure appeared only in the pandas UDF.)

## A fix that didn't work, and why that's worth saying

My first attempt was the Spark conf `spark.pyspark.python`. It changed nothing. That conf is consumed by the launcher (`spark-submit`/`pyspark` shell), while a SparkContext created *in-process* from a plain `python` script reads only the environment variable. The working fix, in `get_spark()`, runs before the session exists:
```python
os.environ["PYSPARK_PYTHON"] = sys.executable
```
**Lesson:** when a config "has no effect", check *who reads it and when*, instead of trying more configs.

## The Databricks versions of the same bug

| Situation | Why it fails | Do this instead |
|---|---|---|
| `!pip install pkg` in a notebook | Runs a shell command **on the driver only**. The driver can import it; UDFs on executors can't | `%pip install pkg` (notebook-scoped, installed for driver and executors; it restarts Python, so put it at the top) |
| Library installed in one notebook session, job run on a new cluster | Notebook-scoped libraries don't carry over | Declare dependencies on the job task / cluster library / serverless environment, ideally in the bundle (DAB) |
| Databricks Connect: UDF works locally, fails remotely | The UDF body runs on the **cluster's** Python, not your laptop's. Local-only packages or a different Python minor version break it | Match the Python minor version to the cluster runtime; install UDF dependencies on the cluster side |
| Serverless notebook or job | The environment is defined by its environment version and dependency list, not by what you installed interactively | Pin dependencies in the environment spec, so every run gets the same set |

## General rules

1. **Ask the process that fails.** Driver-side checks (`import x`, `pip show x`) prove nothing about executors. A one-row UDF returning `sys.executable`, `sys.version` and `find_spec("x")` is the decisive test.
2. **Pin interpreters and dependencies declaratively.** An environment that depends on shell state (`PATH`, which venv is active) will differ between your laptop, CI and the job.
3. **Read the traceback's process of origin.** A worker traceback wrapped in a `PythonException` is a *remote* failure. Look for the Python environment first, not the logic.

## How I'd explain it

- **To an engineer:** "Spark runs your Python UDFs in separate worker processes. They were starting a different Python than the one you tested with, so a package you had installed wasn't there. We pinned the worker interpreter and made the dependency part of the job definition."
- **To a stakeholder:** "The code was fine. The production machines were missing a component that the development machine had. We now declare the components with the job, so every run gets the same set."
