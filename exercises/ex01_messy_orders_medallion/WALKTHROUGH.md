# Exercise 01: messy orders → Bronze / Silver / Gold

> **The customer ask.** "Our order feed is a mess. Finance's daily revenue number never matches the ops dashboard. Can you build us something we can trust?"

The code is in `pipeline.py`, the tests in `test_ex01.py`, and the data (every defect is deliberate and labelled) in `landing_data.py`.
To run it: `cd exercises && pytest ex01_messy_orders_medallion -q` (11 tests, about 50s locally).
To see the tables and the physical plan: `python -m ex01_messy_orders_medallion.pipeline`.

---

## 1. Clarify before coding (what I'd ask out loud)

| Question | Why it changes the code | Assumption I made |
|---|---|---|
| What *is* "revenue"? Gross? Net of cancellations? Which currency? | Filters and FX logic | Exclude cancelled orders; report in USD |
| Which timestamp defines "the day": order time or ship time? In which time zone? | `to_date()` bucketing depends on the session time zone | Order time, UTC |
| An order changes status over time. Which version counts? | Dedupe and sequencing rule | Latest version by `updated_at` (event time), **not** arrival time |
| What should happen to bad rows: drop, fail the pipeline, or park them? | Expectations: `expect` / `drop` / `fail` / quarantine | Park them in a quarantine table with reasons. Never drop silently. |
| Can a customer on an order be missing from the customer master? | Inner vs left join | Yes (late-arriving dimension), so LEFT join and "Unknown" |
| Is the customer master unique per customer? | Join fan-out | **No.** C002 appears twice, so dedupe the dimension first |
| Attribute revenue to the customer's segment *now* or *at order time*? | Type 1 vs Type 2 dimension | Now (Type 1). Say out loud that this is a business choice. |
| Volume and latency? Daily batch or minutes? | Batch vs streaming, Auto Loader, SDP | Daily batch, incremental by file |

> Saying these out loud is half the interview. Each one is a place where two reasonable engineers produce different numbers. **That is exactly why Finance and Ops disagree today.**

## 2. Decompose: a messy problem becomes a sequence of transformations

```
landing/*.jsonl ──► BRONZE  (raw, append-only, + lineage: _source_file, _ingested_at, _corrupt_record)
                      │   idempotent by file: re-delivered files are skipped
                      ▼
                 STANDARDISE (trim/upper ids, status vocabulary, amount parse, multi-format timestamps)
                      ▼
                 VALIDATE (7 null-safe rules → dq_failures array)
                      ├──► QUARANTINE (row + raw values + reasons)     ← explainable to the data owner
                      ▼
                 LATEST PER ORDER (row_number over event time, deterministic tiebreak)
                      ▼
                 MERGE INTO SILVER  WHEN MATCHED AND s.updated_at > t.updated_at   ← sequencing guard
                      ▼
 customers.csv ► DIM_CUSTOMER (dedupe → one row per key; empty region → Unknown)
 fx ────────────► ENRICH (broadcast joins, LEFT for orphans, DECIMAL money, cardinality guard)
                      ▼
                 GOLD: fct_daily_revenue, top_customers_per_region
```

Each arrow has a single responsibility. When a number is wrong you can bisect the pipeline by counting rows at each arrow: the "row-count ledger" in `playbook/04-resilience-and-debugging.md`.

## 3. Key decisions (and the alternative I rejected)

1. **Bronze stores everything as STRING with an explicit schema.** Inference on messy JSON is sample-dependent, and one bad file can flip a column's type. Rejected: `inferSchema`. On Databricks, Auto Loader's `cloudFiles.schemaEvolutionMode` plus `_rescued_data` does this more robustly.
2. **`PERMISSIVE` + `_corrupt_record`.** A truncated line is data about the upstream system's health, so keep it. Rejected: `DROPMALFORMED`, which hides problems, and `FAILFAST`, which lets one bad line stop the business.
3. **`try_cast` / `try_to_timestamp`.** On Spark 4 (ANSI mode on by default) a plain `cast('abc' as decimal)` *throws*. The `try_` variants turn garbage into NULL, and the null-safe DQ rules turn the NULL into a quarantine reason.
4. **Null-safe DQ rules.** `coalesce(<rule>, false)`: a rule that evaluates to NULL counts as a failure. `test_null_unsafe_rule_would_leak_the_null_amount` proves the naive `NOT(amount > 0)` misses the NULL row. This is the same hole I found in lakeflow_framework's quarantine predicate (`case-studies/02`).
5. **Event time beats arrival time.** A `cancelled` event for ORD-1002 arrives on day 2 but carries an *older* `updated_at`, so it must lose. This is the reason AUTO CDC has `sequence_by`. The hand-written equivalent is the MERGE condition `s.updated_at_ts > t.updated_at_ts`.
6. **Deterministic dedupe.** `row_number()` with a full tiebreak order. Rejected: `dropDuplicates(["order_id"])`, which keeps an arbitrary row that can differ between runs.
7. **Dedupe the dimension before joining.** Without it, C002's two master rows double its revenue: 2,379.48 instead of 2,219.49 (`test_naive_join_to_undeduplicated_dimension_inflates_revenue`).
8. **DECIMAL for money.** In DOUBLE, 250 × 1.1 = 275.00000000000006, and those errors accumulate in SUMs.
9. **LEFT join plus "Unknown".** Dropping ORD-1010 because its customer hasn't reached the master yet would understate revenue by 550.

## 4. How it executes (read the physical plan like a story)

From `python -m ex01_messy_orders_medallion.pipeline` → `fct_daily_revenue.explain("formatted")`:

```
AdaptiveSparkPlan
+- HashAggregate (final)            ← 3. merge partial sums per (date, region, segment)
   +- Exchange hashpartitioning     ← the ONLY shuffle in the query
      +- HashAggregate (partial)    ← 2. map-side pre-aggregation (like a combiner)
         +- BroadcastHashJoin LeftOuter BuildRight   ← dim_customer broadcast, no shuffle
            :- BroadcastHashJoin LeftOuter BuildRight ← fx broadcast, no shuffle
            :  :- Filter / Scan parquet (Delta)
            :  :     PushedFilters: [IsNotNull(status), Not(EqualTo(status,cancelled))]
            :  :     ReadSchema: 5 of 12 columns        ← column pruning (Parquet is columnar)
            +- BroadcastExchange
               +- Window / WindowGroupLimit / Sort / Exchange / WindowGroupLimit ← dedupe of dim
                     └ Spark saw "row_number() = 1" and pushed a per-group limit BEFORE the shuffle
```

Things to say out loud:
- **Lazy evaluation.** Nothing ran until an action: `count`, `collect`, `write`, or `show`. The functions only build a logical plan, and Catalyst optimises the *whole* plan (pushdown, pruning, join strategy).
- **Look at `IsNotNull(status)`.** Spark inserted it because `status != 'cancelled'` is NULL for NULL status, and NULL means "drop". If DQ didn't already guarantee a non-NULL status, rows would vanish right here. Exercise 05 plants exactly this bug.
- **Broadcast vs shuffle.** Small dimensions (fx, customers) are shipped whole to every executor, so the big fact side never moves. Spark picks this automatically under `spark.sql.autoBroadcastJoinThreshold` (default 10 MB). I also hinted it with `F.broadcast`.
- **The window dedupe needs a shuffle** (`Exchange` by `customer_id`), because every version of a key must land on the same task.
- **AQE** (`AdaptiveSparkPlan`) can re-plan at shuffle boundaries using real sizes: coalescing tiny partitions, switching sort-merge to broadcast, and splitting skewed partitions.

## 5. How it scales (the same code at 1B orders a day)

| Concern | At toy scale | At 1B rows/day | Databricks answer |
|---|---|---|---|
| File discovery | `collect()` a file ledger | Millions of files; listing is the bottleneck | **Auto Loader** (`cloudFiles`) with checkpointed file state and file-notification mode |
| Re-processing | Filter bronze by new file names | Reading all of bronze each run is O(history) | **Incremental**: stream bronze → `foreachBatch` MERGE, or **SDP AUTO CDC** (`sequence_by` = `updated_at`) |
| MERGE cost | Tiny | Scans the target to find matches | Liquid clustering on `order_id` (or date + id) for file pruning; deletion vectors; Photon |
| Dedupe window | One shuffle | Shuffle of the full batch | Dedupe only the incremental batch. Skewed keys: AQE skew-join. Hot `order_id`s are rare. |
| Dimension join | Broadcast | Broadcast only if the dim fits (tens of MB up to about 1 GB) | Otherwise sort-merge join. Pre-filter the dim to keys present in the batch. |
| Guards (`count()`) | 2 extra jobs | Expensive full scans | Replace with expectations (`expect_or_fail` on dim key uniqueness) and table constraints |
| Gold aggregate | Recomputed | Recomputing history daily is wasteful | Materialized view with incremental refresh (SDP/serverless), or aggregate the new partition only |
| Timestamps | Session TZ = UTC | Clusters with different TZ defaults give different "days" | Pin `spark.sql.session.timeZone` in the job or pipeline config |

## 6. How I'd verify (and what "done" means)

- **Unit tests per transformation** (`test_standardisation`, `test_quarantine_reasons_are_explainable`).
- **Invariant tests**: one row per key in silver, and one row per key in the dim.
- **Reconciliation**: gold total = silver total (non-cancelled) = 2,219.49.
- **Conservation of rows**: bronze = 15 lines = 6 quarantined + 9 valid versions, which collapse to 6 orders.
- **Idempotency**: replaying the same files changes nothing (`test_ingestion_is_idempotent`).

## 7. Using the Databricks Assistant on this task (and checking its output)

Prompts I would actually type, in this order. One transformation per prompt, each with context and a definition of done:
1. *"Given this bronze schema [paste `RAW_ORDER_SCHEMA`], write a PySpark function that parses `order_ts` strings in the formats `2026-09-01T10:15:00Z`, `2026-09-01 11:00:00`, `09/01/2026 12:30`, and 13-digit epoch milliseconds. Return NULL for anything else, never raise. Use `try_to_timestamp`."*
   **Check:** did it guard the epoch branch with a 13-digit regex? Assistants often write `cast(x as bigint)` unguarded, and on ANSI Spark that throws. Test "not a date" and "2026".
2. *"Write data quality rules as SQL boolean expressions where NULL must count as failure; return an array of failed rule names per row."*
   **Check:** is every rule wrapped in `coalesce(..., false)`, or written null-safe? Run it on a NULL amount.
3. *"Deduplicate to the latest version per order_id using updated_at; ties must be deterministic."*
   **Check:** it must not use `dropDuplicates`, and the ordering must be on event time.
4. *"Write a Delta MERGE that upserts this batch into silver but never lets an older updated_at overwrite a newer one."*
   **Check:** is the condition on `WHEN MATCHED`, and is the batch deduplicated first?

Red flags in Assistant output: `inferSchema` on raw data, `dropDuplicates` for "latest", `!=` filters on nullable columns, DOUBLE for money, INNER joins to dimensions, `collect()` in loops, and `.toPandas()` on anything unbounded.

## 8. Explaining it to the business (60 seconds)

> "Every order now has one trusted current state, based on when the change actually happened in your system, not when the file happened to arrive. That is why yesterday's late 'cancelled' message no longer wipes out a shipped order. Bad records aren't thrown away. They sit in a quarantine table with the exact reason, so your source-system owners can fix them at the root. Revenue is in exact decimal USD, counted once per order even though your customer master has duplicates, and it reconciles to the cent between the detailed and the summary tables. When Finance and Ops disagree now, we can point to the row and the rule."

## 9. What could still break (I'd raise these proactively)

- **Static FX**: real rates are date-effective, which needs an as-of join on `(currency, rate_date <= order_date)`.
- **Type 1 attribution** rewrites history when a customer changes segment. If Finance needs "segment at time of sale", that's SCD2 plus a point-in-time join (Exercise 02 and the lakeflow `dim_customer` sample).
- **"Latest valid version" policy**: if the newest version of an order is *invalid*, the previous valid version stays in silver. Confirm that with the business.
- **Quarantine growth**: somebody must own draining it. Put a dashboard and an alert on its daily count.
