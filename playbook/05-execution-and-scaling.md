# 05. How code executes, and how it scales

> **What's being assessed:** "We will discuss how your code executes. Be prepared to talk about how your code scales."

The measurements behind this page are in [Exercise 03](../exercises/ex03_execution_and_scaling/WALKTHROUGH.md) (plan-shape tests, local Spark 4.0.1). Timings on a laptop are only indicative; the **plan shapes** are what carry over to a cluster.

## 1. The mental model, in the order I'd narrate it

1. **Code builds a plan; an action runs it.** `select`, `join`, `withColumn` add to a logical plan. `count`, `collect`, `write`, `display` trigger a job.
2. **Catalyst optimises the whole plan:** pushes filters into the scan, prunes columns, folds constants, picks join strategies, and recognises patterns (top-1 per group becomes a `WindowGroupLimit` below the shuffle).
3. **The physical plan is cut into stages at `Exchange` (shuffle) boundaries.** Each stage runs one task per partition, in parallel up to the available cores. Stage time = slowest task.
4. **AQE re-optimises at stage boundaries with real statistics:** coalescing small partitions, switching to broadcast joins, splitting skewed partitions.
5. **Photon** (Databricks) runs supported operators in vectorised native code. Python UDFs and some expressions fall back.
6. **Where Python runs:** the driver runs your notebook; UDF bodies run in Python worker processes next to each executor; `collect()`/`toPandas()` bring data to the driver.

## 2. What I measured (Exercise 03)

| Question | Measurement | The sentence to say |
|---|---|---|
| Which steps shuffle? | filter + select: **0** exchanges; groupBy: **1**; window by key: **1** | Narrow transformations pipeline inside one task; wide ones need a shuffle (disk + network) |
| Broadcast vs sort-merge | 10 MB threshold: **BroadcastHashJoin, 0 shuffles**; threshold −1: **SortMergeJoin, 2 shuffles** | A small dimension is copied to every executor, so the fact table never moves |
| Skew | one task held **364,467 of 400,000 rows (91%)** after hashing on the hot key | One hot key turns a 200-task stage into a 1-task stage |
| Salting | hottest join task **362,113 → 92,888 rows** with 8 salt buckets | Replicate the small side × buckets to spread the big side; costs a bigger small side |
| AQE skew join | final plan: `SortMergeJoin(skew=true)` with no code change | Try `spark.sql.adaptive.skewJoin.enabled` before salting |
| Skewed `groupBy` | 0.41–0.48 s; partial aggregation absorbs it | Aggregations are skew-tolerant (map-side combine); joins and windows aren't |
| `withColumn` loop vs one `select` | 300 columns: **5.5 s vs 1.3 s** (driver-side analysis) | Each `withColumn` re-analyses the plan; build the column list and `select` once |
| UDFs (300k rows) | built-in **0.25 s**, pandas UDF **0.36 s**, Python UDF **0.53 s**; plan shows `BatchEvalPython` vs `ArrowEvalPython` | Built-in > pandas UDF > Python UDF; UDFs are opaque to the optimizer and to Photon |
| Partition pruning | `PartitionFilters: [… (order_date = 2026-01-05)]`; `PushedFilters: [… GreaterThan(amount,50.0)]` | Partition predicates skip directories; other predicates use file/row-group statistics |

## 3. "How does this scale to 10× / 100×?": my checklist

| Axis | Question | Levers |
|---|---|---|
| **Work per task** | How much data per partition after each shuffle? (aim ~100–200 MB) | AQE coalescing; `spark.sql.shuffle.partitions`; fewer, larger files |
| **Shuffles** | How many Exchanges, and how big? | Broadcast small dimensions; aggregate before joining; avoid unnecessary `repartition`/`distinct` |
| **Skew** | Any hot keys (NULLs, "unknown", one big customer)? | AQE skew join → salting → handle the hot key separately; filter NULL keys before joining |
| **Joins** | Is the small side broadcastable? Is any join accidentally many-to-many? | Dimension uniqueness checks; broadcast hints only when you know the size |
| **Driver** | Any `collect`, `toPandas`, Python loops over rows, `withColumn` loops? | Keep work distributed; one `select` |
| **Python** | Any UDFs that could be built-ins? | Built-ins; pandas UDFs (Arrow) when you must |
| **I/O and layout** | Small files? Over-partitioned tables? Pruning working? | Liquid clustering, OPTIMIZE / predictive optimization, file statistics |
| **Incrementality** | Does each run reprocess everything? | Checkpoints, `availableNow`, CDF, incremental MV refresh (needs row tracking) |
| **State (streaming)** | Is state bounded? | Watermarks; `dropDuplicatesWithinWatermark`; time-bounded stream-stream joins |
| **Cost** | Is compute idle, or oversized? | Serverless / auto-stop; job compute for scheduled work; right-size warehouses |

## 4. Delta table layout (what I'd recommend, and how I'd justify it)

The Delta and layout features below are well-established platform practice, but the six repos barely cover them (starter-journey mentions none; vibe-coding mandates `CLUSTER BY AUTO`; WAF *checks* several of them). I'd confirm current defaults in the docs.

| Feature | What it does | When |
|---|---|---|
| **Liquid clustering** (`CLUSTER BY (cols)` or `CLUSTER BY AUTO`) | Clusters data by keys incrementally, without fixed partition directories; keys can change | Default for new tables. Replaces most partitioning and Z-ordering |
| **Partitioning** | One directory per value | Only for very large tables with a low-cardinality filter column, or lifecycle management. WAF fails any partitioned table under 1 TiB ("avoid over-partitioning") |
| **File statistics / data skipping** | Min/max per file lets scans skip files | Keep filter columns among the indexed columns; WAF fails tables that disable stats |
| **Deletion vectors** | Mark rows deleted without rewriting files | Makes DELETE / UPDATE / MERGE cheaper; WAF checks the share of read tables using them |
| **Predictive optimization** | Managed OPTIMIZE, VACUUM, ANALYZE | Enable at catalog/schema level (`ALTER SCHEMA … ENABLE PREDICTIVE OPTIMIZATION`); required for automatic liquid clustering |
| **Row tracking + CDF** | Row-level change information | Needed for incremental materialized-view refresh and change-driven pipelines |
| **Managed tables** | UC owns the files and their lifecycle | Default; enables the automatic features above |

## 5. Streaming scales on state, not rows

- **Checkpoints are identity.** In SDP, a flow's checkpoint is keyed by its **flow name**, so renaming a flow means reprocessing. lakeflow_framework's nodespec lets you pin flow names for exactly this reason.
- **State needs a watermark to shrink.** Measured: an inner stream-stream join without a watermark held 2 → 4 → 6 state rows over three runs while emitting 1 row. Every row ever seen stays forever.
- **Append mode waits for the watermark.** A windowed aggregate in append mode emits a window only once the watermark passes its end, so "the last hour is always missing" (Exercise 04's customer question).
- **Stream-static joins are stateless and cheap,** but the dimension is read as of each micro-batch; rows already written are never re-joined.
- **Triggers are a cost decision:** `availableNow` = incremental batch on a schedule; continuous = always-on compute.

## 6. Surrogate keys: when does a 64-bit hash collide?

Birthday bound, P ≈ 1 − exp(−n² / 2·2⁶⁴), computed:

| Keys hashed (n) | P(at least one collision) | Expected colliding pairs |
|---|---|---|
| 10⁶ | 0.0000% | 2.7 × 10⁻⁸ |
| 10⁷ | 0.0003% | 2.7 × 10⁻⁶ |
| 10⁸ | 0.0271% | 0.00027 |
| 10⁹ | 2.67% | 0.027 |
| 2³² ≈ 4.29 × 10⁹ | 39.3% | 0.5 |
| 10¹⁰ | 93.3% | 2.7 |

A 128-bit hash at 10¹² keys: ~1.5 × 10⁻¹⁵. So `xxhash64(key, effective_from)` is fine for most dimensions, **as long as a test asserts uniqueness** (Exercise 02 does). For very large keyspaces, use a 128-bit hash, a `BIGINT GENERATED ALWAYS AS IDENTITY`, or the natural key.

## 7. Scaling lessons from the repos (beyond Spark)

- **databricks-waf:** statements run at concurrency 2 on a shared warehouse with a 250-statement budget, a 45-minute wall clock and a 10-minute cancel; an AIMD limiter (halve on throttle, +1 after 5 successes); results sliced by workspace group and re-bucketed by hash when they exceed the 25 MiB inline cap. `information_schema.columns` took about an hour to compile on a 600k-relation estate. **Being a good citizen on the customer's warehouse is part of scaling.**
- **consort:** each GREEN runs the full accumulated test suite on fresh Lakebase branches, so verify cost grows linearly per cycle and roughly quadratically over a project. Schema-contract stories took 73% of one measured run.
- **lakeflow_framework:** pipeline start-up reads and validates every spec in the bundle, so start-up time grows with bundle size; filter pipelines by group and split big bundles.

## 8. Saying it in business terms

- "This design reads only new data each run, so cost grows with the day's volume, not with total history."
- "The customer table is small, so we send a copy to every machine instead of reshuffling the orders; that keeps the job's cost flat as orders grow."
- "One very large customer would make a single machine do most of the work. The platform detects and splits that automatically, and we've tested that it does."
- "Streaming here costs memory for every open window. The watermark is the business decision about how late data can arrive; it's what keeps that memory bounded."
