# Exercise 03: see how Spark executes your code before you defend it

> **The interviewer's question:** "Walk me through what happens when this runs. How does it scale?"

The code is in `lab.py` (experiments) and `test_ex03.py` (10 **plan-shape** tests; timings are too noisy to assert on).
To see the numbers yourself: `python -m ex03_execution_and_scaling.lab`.

## Measured results (local[2], Spark 4.0.1, laptop-sized data)

| # | Question | What I measured | What to say |
|---|---|---|---|
| 1 | Which steps shuffle? | filter+select: **0** exchanges · groupBy: **1** · window by key: **1** | Narrow transformations are pipelined inside one task. Wide ones (group, window, join, distinct, repartition) need an `Exchange`, which means disk plus network. |
| 2 | Broadcast vs sort-merge join | threshold 10MB: **BroadcastHashJoin, 0 shuffles** · threshold -1: **SortMergeJoin, 2 shuffles** | A small dimension is copied to every executor and the fact never moves. Past the threshold (10 MB default; AQE can switch at runtime) both sides shuffle. |
| 3a | Skew | After hash-partitioning on the hot key, one task holds **364,467 of 400,000 rows (91%)** | Stage time = slowest task. One hot customer makes a 200-task stage effectively a 1-task stage. |
| 3b | Salting | Hottest join task **362,113 → 92,888** rows with 8 salt buckets (16 partitions) | The big side gets a random salt and the small side is replicated × buckets. The cost is a bigger small side, the benefit is parallelism. It's imperfect because salt buckets hash-collide into partitions. |
| 3c | AQE skew join | Final plan shows `SortMergeJoin(skew=true)` with no code change | `spark.sql.adaptive.skewJoin.enabled` splits oversized partitions at runtime. Try this before salting. |
| 3d | Skewed `groupBy` | 0.41–0.48 s. Partial aggregation absorbs skew | Aggregations are skew-tolerant thanks to map-side combine; **joins and windows are not**. |
| 4 | `withColumn` loop vs one `select` | n=100: 1.3s vs 0.5s · n=200: 2.7s vs 0.8s · n=300: **5.5s vs 1.3s** | Driver-side analysis cost grows superlinearly with a loop, because every call re-analyses the whole plan. Build a column list and `select` once (or `withColumns`). |
| 5 | UDFs | native `upper` **0.25s** · pandas UDF (Arrow) **0.36s** · Python UDF **0.53s** (300k rows). Plan: `BatchEvalPython` vs `ArrowEvalPython` | A Python UDF serialises rows to a Python worker and is opaque to Catalyst (no pushdown, and Photon can't run it). Prefer built-ins, then pandas UDFs. The gap grows with data. |
| 6 | Partition pruning | `PartitionFilters: [..., (order_date = 2026-01-05)]` · `PushedFilters: [..., GreaterThan(amount,50.0)]` | Partition predicates prune directories. Other predicates push into Parquet row-group stats. On Databricks, liquid clustering plus Delta file statistics gives data skipping without over-partitioning. |

## The mental model to narrate

1. **Your code builds a plan; an action runs it.** Nothing executes on `select`/`join`/`withColumn`; `count`, `collect`, `write` and `show` trigger a job.
2. **Catalyst optimises the whole plan:** predicate pushdown, column pruning, constant folding, join reordering, and special patterns such as `WindowGroupLimit` for top-1-per-group, which pushes a limit *below* the shuffle (asserted in `test_top1_per_group_pushes_limit_below_the_shuffle`).
3. **The physical plan has stages cut at `Exchange` boundaries.** Each stage runs as tasks, one per partition. Tasks run in parallel up to the cores available.
4. **AQE re-optimises at stage boundaries using real statistics:** coalescing small partitions, switching to broadcast, splitting skew.
5. **Photon** (on Databricks) vectorises supported operators in C++. Python UDFs and some expressions fall back to the JVM or Python.

## Two things that bit me while building this (resilience notes)

- **My first salting measurement was wrong.** I re-hashed the joined output, which measures my repartition, not the join, and with broadcast on the join never shuffled at all. The fix was to force a shuffle join and measure the join's own partitions. *Lesson: be sure you're measuring the thing you claim.*
- **The AQE check first read "no skew handling".** I was inspecting the DataFrame's own QueryExecution after running a *different* one (a `noop` write builds a new plan). Collecting through the same DataFrame, then reading `executedPlan`, showed `isFinalPlan=true … skew=true`.
- **The pandas UDF failed with `No module named 'pyarrow'`** even though pyarrow was installed: the Python *workers* launched the system `python3`. On Databricks this is the `!pip install` (driver only) vs `%pip install` (driver plus executors) trap. See `case-studies/05`.

## Scaling checklist to run through out loud

- **Data volume:** how many partitions per stage? Aim for about 100–200 MB per task. AQE coalesces; for huge inputs raise the shuffle partitions or leave it to AQE.
- **Skew:** is any join key hot (null keys, "unknown" customer, one big tenant)? Use AQE skew join, then salting, then isolating the hot key.
- **Joins:** can the small side be broadcast? Is any join many-to-many by accident (fan-out)?
- **Driver:** any `collect()`, `toPandas()`, Python loops over rows, or `withColumn` loops? The driver is a single machine.
- **Python:** any UDFs that could be built-ins?
- **I/O:** file count and size (small files); partitioning vs liquid clustering; column pruning (don't `select *` into wide tables).
- **State (streaming):** watermarks bound state. Without them, joins and dedups grow forever (Exercise 04).
