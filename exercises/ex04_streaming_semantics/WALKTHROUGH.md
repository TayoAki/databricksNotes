# Exercise 04: streaming semantics that decide whether the numbers are right

> **The customer ask:** "We moved our nightly job to streaming with `availableNow`. Why is yesterday's last hour always missing from the dashboard?"

The code is in `streaming_lab.py` and the tests in `test_ex04.py` (5 tests). All run Delta source → Delta sink with `trigger(availableNow=True)`, the way most incremental Databricks jobs and SDP streaming tables consume data.

## What I observed (and the tests pin down)

| Experiment | Observation | Why |
|---|---|---|
| A. Checkpoints | Run 1 reads 2 rows; a re-run reads **0**; after appending 1 row, the next run reads **1** | The checkpoint stores which Delta versions (or files, for Auto Loader) were processed. That is how "exactly-once, incremental" works. Delete the checkpoint and you reprocess everything. |
| B. Watermark + append | After run 1 the sink is **empty**, even though every event for window [10:00, 10:10) had arrived. The window was written only after an event at 10:30 moved the watermark to 10:20 | Append mode writes a window **once**, when it can no longer change: watermark = max event time − delay must pass the window end. The newest window is always held back until newer data arrives. **This is the customer's missing last hour.** |
| C. Constant event-time watermark (lakeflow `table_import.py` pattern) | 3 rows read, **0** rows written, in any number of runs | The event time is constant (2000-01-01), so the watermark is stuck 10 minutes before it and the window never closes. In OSS Spark append mode this branch emits nothing. |
| C'. Update mode to Delta | `DELTA_UNSUPPORTED_OUTPUT_MODE` | Use `foreachBatch` + MERGE for upserting aggregates, or a materialized view |
| D. Stream-static join | e1 kept `SMB`; e2 got `Enterprise` after the dimension changed | The static side is read **as of each micro-batch**. Rows already written are never re-joined, so there is no retroactive correction. |

## How to answer the customer (B)

- **Diagnosis:** windowed aggregation in append mode plus `availableNow`. Each run emits only windows the watermark has passed, so the last window(s) wait for the next run. If data stops (month-end), they never emit.
- **Fixes, with trade-offs:**
  1. Compute the aggregate as a **materialized view** (SDP or DBSQL). It's recomputed or incrementally refreshed and always complete as of the refresh. Simplest.
  2. `foreachBatch` + MERGE with **update** semantics. Partial windows are written and corrected later. Consumers must tolerate restatement.
  3. Accept the lag and document it. Choose the watermark delay from real lateness data (a percentile of `ingest_time − event_time`), not a guess.

## The `table_import.py` hypothesis (C), stated carefully

`lakeflow_framework/src/lakeflow_framework/dataflow/table_import.py:92-115` builds "closed rows" (the delete markers for end-dated SCD2 records) with exactly this constant-watermark aggregation.
- **Evidence:** in OSS Structured Streaming append mode, that construction emits nothing (test C).
- **Unknown:** how Databricks' AUTO CDC `once=True` flow evaluates the source view. If it runs as a batch, `withWatermark` is a no-op and the aggregation *would* emit.
- **Coverage:** the repo's unit test mocks `dp`, `View` and `CDCFlow` (`tests/unit/dataflow/test_table_import.py`), and no sample uses `tableMigrationDetails`, so nothing in the repo exercises it end to end.
- **Next step:** migrate a tiny SCD2 table containing one closed record on Databricks and check that `__END_AT` is set.

That is how to present an uncertain finding: hypothesis, evidence, unknowns, and the cheapest decisive test.

## Scaling notes to say out loud

- **State is the scaling axis of streaming.** Aggregations, dedups and stream-stream joins keep state in the state store (RocksDB on Databricks). Watermarks are what let state be dropped. `dropDuplicates` with no watermark grows forever (the vibe-coding Silver skill mandates exactly that; see `repos/vibe-coding-workshop-template.md`). Use `dropDuplicatesWithinWatermark`.
- **Triggers:** `availableNow` gives cheap incremental batch processing. `processingTime` or continuous means always-on compute. Choose by latency SLA, not fashion.
- **Checkpoints are identity.** In SDP a flow's checkpoint is keyed by its **flow name**, so renaming a flow means a full reprocess. This is why lakeflow_framework's nodespec lets you pin `{view, flow}` names.
- **Stream-static joins are cheap and stateless**, but only "as of now". For as-of-event-time correctness use the "streaming DWH" pattern (change-point spine plus as-of joins), as in the lakeflow TPCH `dim_customer` spec.
