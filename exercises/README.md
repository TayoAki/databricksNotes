# Runnable exercises (verified locally)

Five customer-shaped problems, each with working code, tests, and a walkthrough covering how it executes, how it scales, how I'd use the Assistant, and how I'd explain it to the business. They run on open-source Spark + Delta, so you can rehearse anywhere. On Databricks, the same functions drop into a notebook, a Job, or an SDP pipeline.

| # | Exercise | Customer ask | What it trains | Tests |
|---|---|---|---|---|
| 01 | [Messy orders → medallion](ex01_messy_orders_medallion/WALKTHROUGH.md) | "Finance and Ops never agree on revenue" | Decomposition, null-safe DQ + quarantine, event-time dedup, MERGE sequencing, fan-out guard, plan reading | 11 |
| 02 | [SCD2 with Delta MERGE](ex02_scd2_merge/WALKTHROUGH.md) | "Report by segment *at time of sale*" | The 4 SCD2 failure modes, point-in-time joins, lazy-evaluation trap | 10 |
| 03 | [Execution & scaling lab](ex03_execution_and_scaling/WALKTHROUGH.md) | "How does this scale?" | Shuffles, broadcast vs SMJ, skew/salting/AQE, withColumn loops, UDF cost, pruning | 10 |
| 04 | [Streaming semantics](ex04_streaming_semantics/WALKTHROUGH.md) | "Why is the last hour always missing?" | Checkpoints, watermarks/append mode, stream-static joins, testing a hypothesis about someone else's code | 5 |
| 05 | [Debug kata](ex05_debug_kata/DEBUGGING_LOG.md) | "The job is green but the numbers are off" | Reading unfamiliar code, 8 planted real-world bugs, row-count ledger | 12 + 9 xfail |

**Last full run:** `48 passed, 9 xfailed in 162.37s`, in a fresh venv built only from `requirements.txt` (the 9 xfails are the kata's buggy implementation, which *must* fail).

## Run it

```bash
cd exercises
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # pyspark 4.0.1, delta-spark 4.0.0, pytest, pandas, pyarrow
pytest -q -rx                              # all exercises
pytest ex01_messy_orders_medallion -q      # one exercise
python -m ex01_messy_orders_medallion.pipeline   # print tables + physical plan
python -m ex03_execution_and_scaling.lab         # print the measurements
```

Verified with Python 3.11.15, OpenJDK 21.0.10, PySpark 4.0.1, delta-spark 4.0.0, pandas 2.3.3, pyarrow 25.0.1, pytest 9.1.1.

**Troubleshooting (all three hit while building this):**
- `JAVA_GATEWAY_EXITED` on the very first run: Spark downloads the Delta jars through Ivy at JVM start-up, and a slow first download can outlast the gateway's start-up wait. The jars land in `~/.ivy2*/jars`; just re-run.
- `ModuleNotFoundError: pyarrow` inside a pandas UDF although pyarrow is installed: the Python workers started a different interpreter. `common/spark_session.py` pins `PYSPARK_PYTHON` to the driver's interpreter (see `case-studies/05`).
- `ImportError: cannot import name '_builtin_table'` when importing `pyspark.testing` or `pyspark.pandas`: pandas 3 with PySpark 4.0.x. `requirements.txt` pins `pandas<3` (see `case-studies/06` #15).

## Local vs Databricks: what differs

| Here | On Databricks |
|---|---|
| `get_spark()` builds a session | `spark` already exists; Delta is the default format |
| Paths like `/tmp/.../silver/orders` | Unity Catalog names `catalog.schema.table`; files in Volumes `/Volumes/c/s/v/...` |
| `ingest_new_files` ledger | Auto Loader (`cloudFiles`) with checkpointed file discovery |
| Hand-written MERGE for SCD2 / sequencing | `create_auto_cdc_flow(..., sequence_by=..., stored_as_scd_type=2)` in Lakeflow SDP |
| DQ rules + quarantine by hand | SDP expectations (`expect_all_or_drop`, …) + a quarantine flow/table |
| `explain("formatted")` | Same, plus the Spark UI / query profile, and Photon operators in the plan |
| Session TZ pinned in code | Pin `spark.sql.session.timeZone` in the job/pipeline config |
