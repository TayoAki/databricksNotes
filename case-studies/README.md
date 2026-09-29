# Case studies: real bugs, found by reading and proved by running

Each case study is a story I can tell in an interview: what I noticed, how I tested it, what was actually true, how I'd fix it, and how I'd explain it to an engineer and to the business. Every claim carries a status:

- **CONFIRMED:** reproduced by execution, with the script in [`evidence/`](evidence/).
- **SUSPECTED:** consistent with the code as read, but the decisive run needs an environment I don't have (usually a Databricks workspace). It is stated together with the cheapest test that would settle it.
- **REFUTED:** it looked like a bug and wasn't. These are kept on purpose (see 06).

| # | Case study | Where | What it shows | Status |
|---|---|---|---|---|
| 01 | [Three stacked faults in lakeflow_framework's packaging](01-lakeflow-packaging-three-stacked-faults.md) | lakeflow_framework | The wheel can't be built (non-existent build backend). Once built it can't be imported (bare `import pipeline_config`). The tests can't see either fault (`pythonpath = src`). Three-line patch | CONFIRMED, patch verified (wheel imports, 396 tests pass) |
| 02 | [NULL slips past the quarantine](02-null-semantics-in-quarantine-predicates.md) | lakeflow_framework (same class in databricks-waf and the Ex05 kata) | `NOT((r1) AND (r2))` is NULL when a rule is NULL, so `.where()` routes the row nowhere | Predicate CONFIRMED. End-to-end SDP effect SUSPECTED |
| 03 | [Fail-open patterns](03-fail-open-patterns.md) | lakeflow_framework, vibe-coding-workshop-template, technical-services-solutions, consort | Seven places where an error becomes a success signal or a silent "repair". WAF and consort as fail-closed counter-examples | #1 CONFIRMED by a test with repo fixtures; others by code read or deep-read execution (per row) |
| 04 | [Lazy evaluation meets a mutable table](04-lazy-evaluation-meets-mutable-tables.md) | my Exercise 02 | A DataFrame defined before a write sees the write. `versionAsOf` pins it, and `.cache()` does **not** | CONFIRMED, plus a mutation test |
| 05 | [pyarrow is installed, but not where the code runs](05-the-worker-python-interpreter.md) | my Exercise 03 | Driver and workers can run different Pythons. `PYSPARK_PYTHON`, and `%pip` vs `!pip` on Databricks | CONFIRMED |
| 06 | [Near-misses: what I almost got wrong](06-near-misses-and-false-positives.md) | this whole investigation | 13 wrong turns, what caught each one, and the habit it created | Every row backed by an executed check |
| 07 | [A join whose direction is decided by how you type the condition](07-lakeflow-delta-join-alias-parsing.md) | lakeflow_framework | `a = b` vs `b = a` changes which side a LEFT join keeps. Phantom aliases from literals. Quarantine rules applied per table before the join. Mutated config. No watermarks | CONFIRMED with the framework's **real** classes on OSS Spark |
| 08 | [Two ways to price usage](08-price-join-containment-vs-point-in-time.md) | starter-journey vs databricks-waf | A containment INNER JOIN drops usage that spans a price change or has no price. Point-in-time LEFT JOIN plus coverage columns | Mechanics CONFIRMED. Real-world magnitude data-dependent (WAF measured 0 spanning rows on labs) |

## Evidence scripts

All scripts locate `exercises/` relative to themselves, so they run from any directory once `pip install -r exercises/requirements.txt` is done.

| Script | Backs | Needs |
|---|---|---|
| [`lakeflow_packaging_fix.patch`](evidence/lakeflow_packaging_fix.patch) | 01 | a lakeflow_framework checkout @ `0e8d0ca` |
| [`verify_lakeflow_semantics.py`](evidence/verify_lakeflow_semantics.py) | 02 (and the `append_view` prefix-exception check) | pyspark only |
| [`test_scratch_transform_fail_open.py`](evidence/test_scratch_transform_fail_open.py) | 03 #1 | drop into lakeflow_framework `tests/unit/` (uses its fixtures) |
| [`lazy_snapshot.py`](evidence/lazy_snapshot.py) | 04 | exercises env |
| [`which_python_workers.py`](evidence/which_python_workers.py) | 05 | pyspark only; run with a venv python *without* activating it |
| [`lakeflow_delta_join_real.py`](evidence/lakeflow_delta_join_real.py) | 07 A, C, D | exercises env + `jsonschema pyyaml` + `LAKEFLOW_FRAMEWORK_SRC` |
| [`alias_regex_check.py`](evidence/alias_regex_check.py), [`delta_join_direction.py`](evidence/delta_join_direction.py) | 07 A, B (no checkout needed) | Python / exercises env |
| [`stream_stream_join_state.py`](evidence/stream_stream_join_state.py) | 07 E | exercises env |
| [`observe_streaming.py`](evidence/observe_streaming.py) | Exercise 04 observations | exercises env |
| [`price_join_demo.py`](evidence/price_join_demo.py) | 08 | exercises env |
| [`null_semantics_table.py`](evidence/null_semantics_table.py) | [`playbook/07-null-semantics.md`](../playbook/07-null-semantics.md) | exercises env |

## Themes across the case studies

- **Silent beats loud in how much damage it does.** A NULL flag that routes a row nowhere (02), a swallowed exception (03), a LEFT join that keeps the wrong side (07), an INNER join that drops unpriced usage (08). The loud failures in the same code (phantom aliases, unresolved columns) are annoying but harmless.
- **The test environment differs from production in exactly the way that hides the bug:** `pythonpath = src` (01), a laptop that can't reproduce non-determinism (06 #7), a driver whose Python differs from the workers' (05).
- **Semantics you "know" should be checked with a 10-line experiment:** three-valued logic (02), lazy snapshots and caching (04), merge precedence (06 #2), format-specific overwrite rules (06 #11).
