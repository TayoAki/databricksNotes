# Nine pipeline failure modes: the fix, a prompt, and what to check

These nine cause most "the job is green but the numbers are wrong" incidents. For each one: what goes wrong, how I'd solve it, a prompt that gets the Databricks Assistant (or any AI) to write the solution, and what to check in its answer.

Every trap below was reproduced on Spark 4.0.1 + Delta 4.0.0, with ANSI mode on (the Spark 4 default), by [`pipeline_failure_modes.py`](../case-studies/evidence/pipeline_failure_modes.py). The results are quoted under **Evidence**. Databricks-only features (Auto Loader, SDP expectations) are described from the documentation and weren't run here.

## The nine at a glance

| # | Failure | What the business sees | The fix in one line |
|---|---|---|---|
| 1 | [Schema drift](#1-schema-drift) | A field that "stopped being filled in" on some date, or a load that suddenly fails | Land raw, diff every batch against a contract, apply renames only through a map |
| 2 | [Type changes and silent casts](#2-type-changes-and-silent-casts) | Totals slightly off, dates a month out, rows that vanish | Keep raw strings, parse with `try_*`, quarantine what failed to parse |
| 3 | [Nullability changes and missing fields](#3-nullability-changes-and-missing-fields) | Counts that drop although nobody deleted anything | Declare required fields, enforce them with constraints, watch null rates |
| 4 | [Incremental watermark bugs](#4-incremental-watermark-bugs) | A few records missing from each load, never the same ones | Re-read an overlap, make the write idempotent, advance the watermark only after success |
| 5 | [Late-arriving data](#5-late-arriving-data) | Last week's number changes, or should have and didn't | Report on event time, recompute every date the new rows touch |
| 6 | [Time zones and DST](#6-time-zones-and-dst) | Daily totals that disagree with the store's own report around midnight | Store UTC, convert with region IDs, test the DST days |
| 7 | [Duplicates and idempotency](#7-duplicates-and-idempotency) | Revenue up after an outage or a re-run | A stable event key, deterministic dedupe, MERGE instead of append |
| 8 | [Join fan-out](#8-join-fan-out) | One segment's revenue suddenly too high | Check key uniqueness before the join and row counts after |
| 9 | [Bad keys and inconsistent normalization](#9-bad-keys-and-inconsistent-normalization) | Customers who "have no orders", orders with no customer | One canonical form, one function, both sides of the join; measure orphans |

## How the prompts are built

Each prompt is the skeleton from [playbook/03](../playbook/03-ai-stewardship.md#2-the-prompt-skeleton), cut down to four parts:

1. **Context:** the tables, their grain and key, and that it runs on Databricks with Delta.
2. **The rule that prevents the failure,** stated as behaviour ("re-reading the overlap must change nothing"), not as code.
3. **Tests with the exact inputs that break naive code.** Ask for them in the same prompt; they are how you judge the answer.
4. **"List your assumptions."** That is where the AI's guesses become visible.

Swap in your own table and column names. If the Assistant can't see the table, paste the `DESCRIBE` output. Then run the tests before you read the code, and go through the **Check the answer for** list (more in [playbook/03 §4](../playbook/03-ai-stewardship.md#4-evaluate-the-output-at-three-levels)).

## 1. Schema drift

**What goes wrong**
- An append with an extra or a renamed column fails: "A schema mismatch detected when writing to the Delta table". That is loud, which is good, until someone adds `mergeSchema` to make the error go away.
- With `mergeSchema`, a rename becomes a second column. The table ends up with both `amount` and `amt`, and each row fills only one of them.
- A dropped column is silent. Delta accepts an append without `amount` and writes NULL.
- A read with a fixed schema turns a renamed JSON key into NULL, with no error.

**How to solve it**
- Land raw data in bronze without losing anything: every column as STRING, plus the source file and load time. On Databricks, Auto Loader with `cloudFiles.schemaLocation` does this incrementally. `cloudFiles.schemaEvolutionMode` decides whether a new column is added (the default stops the stream once and restarts with it) or kept out, and fields that don't fit the schema go to `_rescued_data`.
- Write the silver contract down: each column's name and type, and whether it is required.
- Diff each batch against it before silver. Report added columns, missing columns and possible renames (a missing and an added column of the same type in one batch).
- Agree the policy with the data owner. A sensible default: added columns stay in bronze with a warning; a missing required column fails the load; a rename fails until it is added to an explicit rename map.
- Silver selects columns by name through that map. No `select("*")`, no `mergeSchema` on silver, and `unionByName` rather than `union`, which matches columns by position ([kata B1](../exercises/ex05_debug_kata/DEBUGGING_LOG.md#2-the-bugs-the-symptom-each-produces-and-how-to-find-it)).

**Prompt**
```prompt
On Databricks, a daily JSON feed lands in bronze table raw.orders (every column
STRING) and loads into silver.orders (order_id BIGINT, amount DECIMAL(12,2), order_ts
TIMESTAMP). Upstream adds, drops and renames fields without telling us.

Write PySpark that compares each batch's columns with an expected-columns contract and
reports added, missing and possibly renamed columns (a missing and an added column in
the same batch). Added columns stay in bronze with a warning. A missing column or an
unmapped rename fails the silver load with a clear message. Renames are applied only
from an explicit rename map. Select silver columns by name: no select("*"), no
mergeSchema.

Include pytest cases for an added, a dropped and a renamed column. List your
assumptions.
```

**Check the answer for**
- `mergeSchema` or `spark.databricks.delta.schema.autoMerge.enabled` switched on for silver "to fix the error". That is exactly what turns a rename into a silent second column.
- A rename handled as "drop the old column, add the new one" with no alert and no mapping.
- `select("*")`, or `union` instead of `unionByName`.

**Evidence** (`schema_drift()`): after a `mergeSchema` append of the renamed column, the table's columns are `order_id, amount, discount, amt` and the new row is `(4, None, None, 40.0)`. The contract diff reports `possible_renames: [('amount', 'amt')]`.

## 2. Type changes and silent casts

**What goes wrong**
- With ANSI mode on (the default in Spark 4, Databricks SQL and serverless), a bad cast fails the job: `cast('12.5' AS INT)` raises `CAST_INVALID_INPUT`. With ANSI off, the same cast silently returns 12, and `cast('N/A' AS INT)` returns NULL. The same code is loud on one cluster and silent on another.
- Some casts are silent even with ANSI on:
  - `cast('12.345' AS DECIMAL(5,2))` rounds to 12.35.
  - `'03/04/2026'` parses as 4 March or 3 April, depending on which format you guess.
  - Epoch milliseconds read as seconds give the year 57971.
- Schema inference changes a column's type: one `"N/A"` makes `amount` a STRING for the whole batch.
- DOUBLE is the wrong type for money: `0.1 + 0.2 = 0.30000000000000004`.

**How to solve it**
- Bronze keeps every field as its raw STRING, and types are decided once, in silver.
- Parse with `try_cast`, `try_to_timestamp` and `try_to_number`, so bad input becomes NULL instead of an error.
- Then count what broke: a value that was present before parsing and NULL after is a parse failure. Quarantine the row with the field name and raw value, and fail the batch above a threshold.
- Use one explicit format per source for dates and timestamps, and reject what doesn't match rather than guessing. For epochs, know the unit (`timestamp_millis` or `timestamp_seconds`) and range-check the result.
- Keep money in `DECIMAL(p, s)`. Flag inputs with more decimals than the target scale, because DECIMAL casts round without telling you.

**Prompt**
```prompt
Bronze table raw.orders stores every field as STRING. Write PySpark that builds
silver.orders with order_id BIGINT, amount DECIMAL(12,2) and order_ts TIMESTAMP
(format 'yyyy-MM-dd HH:mm:ss', UTC).

Parse with try_cast and try_to_timestamp, never a plain cast. A field that was present
before parsing and NULL after is a parse failure: send the row to a quarantine table
with the field name and raw value. Treat an amount with more than 2 decimal places as
a failure too, because DECIMAL casts round silently. Fail the job if more than 1% of
rows are quarantined.

Include tests for '12', ' 12 ', '12.5', 'N/A', '', '12.345', '03/04/2026' and
'2026-02-30 10:00:00'. List your assumptions.
```

**Check the answer for**
- A plain `cast()`, or schema inference. Either works on the demo data, then fails or goes silent on the first bad file.
- DOUBLE or FLOAT for money.
- `try_cast` with no count of what it turned into NULL. That just moves the silence somewhere else.
- A list of fallback date formats that can both match the same string (`dd/MM` and `MM/dd`): the order of the list then decides the date.

**Evidence** (`silent_casts()`): the quarantine rule catches exactly `['12.5', 'N/A', '']`; `' 12 '` parses as 12; `'12.345'` is flagged as "would round"; `timestamp_seconds(1767225600000)` is in the year 57971 while `timestamp_millis` gives 2026-01-01. More error classes are in [playbook/04 §3](../playbook/04-resilience-and-debugging.md#3-error-signatures-what-they-usually-mean), and the bronze-as-STRING decision is in [Exercise 01](../exercises/ex01_messy_orders_medallion/WALKTHROUGH.md#3-key-decisions-and-the-alternative-i-rejected).

## 3. Nullability changes and missing fields

**What goes wrong**
- With an explicit schema, a missing JSON key and an explicit `null` both become NULL. That is what you want, but nothing tells you a required field has stopped arriving.
- NULLs then disappear quietly downstream: `status != 'cancelled'` drops NULL statuses, inner joins drop NULL keys, `count(col)` skips them and `sum` ignores them. See [playbook/07](../playbook/07-null-semantics.md).
- Without constraints, Delta stores NULLs in a column everyone assumes is populated.

**How to solve it**
- Declare which columns are required and which are optional (the contract from #1).
- Enforce it in the table: `NOT NULL` and `CHECK` constraints make a bad write fail instead of land. On Databricks, SDP expectations (`expect_or_drop`, `expect_or_fail`) do the same inside a pipeline.
- Before writing, split the batch. Rows missing a required field go to quarantine with the list of missing fields; the rest are written.
- Track each column's null rate per batch and alert on jumps. An optional column going from 2% to 60% NULL usually means an upstream change.
- Write NULL-safe logic: `coalesce`, `<=>` or `eqNullSafe`, and `count(*)`.

**Prompt**
```prompt
Write PySpark that loads silver.customers from a bronze JSON feed. customer_id and
country are required; email is optional. A missing JSON key and an explicit null mean
the same thing.

Rows missing a required field go to a quarantine table with the list of missing
fields; the rest are written. Give silver.customers NOT NULL and CHECK constraints so
a bad row can never be written. Record each column's null rate per batch in a metrics
table, and fail if an optional column's null rate rises by more than 20 points from
the previous run. Use null-safe comparisons: no != or NOT IN on nullable columns.

Include tests for a missing key, an explicit null and an empty string. List your
assumptions.
```

**Check the answer for**
- `dropna()` on whole rows. It deletes data without a trace.
- `fillna(0)` or `fillna('')` on a required field, which turns "missing" into a plausible wrong value.
- `!=` or `NOT IN` on a nullable column.
- Constraints with no quarantine, so the first bad row stops the whole load.

**Evidence** (`nullability()`): writing the raw batch fails with `DELTA_VIOLATE_CONSTRAINT_WITH_VALUES`; a NULL key fails with `DELTA_NOT_NULL_CONSTRAINT_VIOLATED`; a batch without the `customer_id` column fails with `DELTA_MISSING_NOT_NULL_COLUMN_VALUE`. After `C2` and `C3` are quarantined for a missing `country`, the write succeeds. The same NULL hole in a real framework is [case 02](../case-studies/02-null-semantics-in-quarantine-predicates.md).

## 4. Incremental watermark bugs

**What goes wrong**
- `updated_at > last_watermark` skips rows that have the watermark's exact timestamp but committed after the last read.
- It also skips rows from a transaction that started before the last read and committed after it, carrying an older `updated_at`: long transactions, lagging replicas and clocks that disagree all do this.
- Setting the new watermark to `now()` instead of the largest value actually read, or saving it before the write succeeds, loses rows the next time something fails.

**How to solve it**
- Re-read an overlap: `updated_at >= watermark - lookback`, with the lookback longer than your longest transaction plus any clock skew.
- Make the write idempotent so the overlap is harmless. Dedupe to one row per key, then `MERGE ... WHEN MATCHED AND s.updated_at > t.updated_at`, the sequencing guard from [Exercise 01](../exercises/ex01_messy_orders_medallion/WALKTHROUGH.md#3-key-decisions-and-the-alternative-i-rejected).
- Save the new watermark as the largest `updated_at` actually read, and only after the MERGE has committed.
- Better still, use a column ordered by commit rather than by a wall clock: a CDC log sequence number, or Delta's Change Data Feed (`_commit_version`) when the source is a Delta table. A streaming read with a checkpoint does this bookkeeping for you.

**Prompt**
```prompt
I load source table src.orders into Delta table silver.orders incrementally by
updated_at.

Write PySpark that reads rows with updated_at >= (last watermark - 10 minutes), keeps
one row per order_id (latest updated_at, with a deterministic tie-break), and MERGEs
on order_id, updating only when the incoming updated_at is newer. Only after the MERGE
succeeds, save the new watermark to a control table: the max updated_at of the rows
read, never now(). Explain why '>' loses rows.

Include tests for a row with the same updated_at as the previous watermark, a row
committed late with an older updated_at, and a re-run that must leave the table
unchanged. List your assumptions.
```

**Check the answer for**
- `>` with no overlap, or an overlap written with `append`, which duplicates rows on every run.
- A watermark taken from `current_timestamp()`, or saved before the write.
- A watermark on `created_at` for a table whose rows get updated.

**Evidence** (`incremental_watermark()`): after a run whose watermark is 10:05, the next `>` read picks only `[5]`. It misses id 3 (same timestamp) and id 4 (committed late at 10:03). `>= watermark − 10 min` picks `[1, 2, 3, 4, 5]`, and running that overlapping MERGE twice leaves 5 rows, one per id. The MERGE idiom is in [the patterns cheatsheet](pyspark-sql-patterns.md#sequenced-upsert-merge).

## 5. Late-arriving data

**What goes wrong**
- Reports grouped by ingest time put a late order on the day it arrived, not the day it happened.
- A daily job that recomputes only "yesterday" by event time never picks up late rows for earlier days, so those totals stay wrong for good.
- In streaming, a row behind the watermark is dropped silently. The only trace is the `numRowsDroppedByWatermark` metric.
- In append mode, the newest window also waits for later data before it's written ([Exercise 04](../exercises/ex04_streaming_semantics/WALKTHROUGH.md#what-i-observed-and-the-tests-pin-down)).

**How to solve it**
- Keep both timestamps: `event_time` for business logic and `ingest_time` for operations. Report on event time.
- Measure lateness (`ingest_time − event_time`, for example its 99.9th percentile) and choose the correction window from data, not a guess.
- Batch: each run finds the event dates the new rows touch and recomputes exactly those, with Delta `replaceWhere` or MERGE, instead of a fixed "yesterday".
- Streaming: set the watermark from the measured lateness and alert on `numRowsDroppedByWatermark`. If every late row must count, land events first and aggregate them with a materialized view or `foreachBatch` + MERGE ([Exercise 04's options](../exercises/ex04_streaming_semantics/WALKTHROUGH.md#how-to-answer-the-customer-b)).
- Agree what happens once a period is closed (month-end): route the late row to review rather than rewrite a closed total.

**Prompt**
```prompt
Orders have event_time (when the customer ordered) and ingest_time (when we received
it). Some arrive up to 3 days late.

Write PySpark that maintains gold.daily_revenue by event date. Each run finds the
event dates touched by newly ingested orders and recomputes only those dates (Delta
replaceWhere or MERGE) instead of just "yesterday". Dates more than 3 days old are
closed: late orders for them go to a late_orders table for review, and the run reports
how many.

Include tests where an order from two days ago arrives today and changes that day's
total, and an order from five days ago lands in late_orders. List your assumptions.
```

**Check the answer for**
- Grouping by `to_date(ingest_time)`, or `current_date() - 1` as the only date to process.
- A watermark delay picked without measuring lateness, with nothing watching the dropped-rows metric.
- `mode("overwrite")` on the whole table instead of the touched dates. It's expensive, and it can overwrite another writer's changes.

**Evidence** (`late_data()`): recomputing the touched dates `['2026-09-01', '2026-09-03']` gives 15.0 for 1 September (10.0 plus the late 5.0), leaves 2 September at 20.0, and adds 3 September. In the streaming run, an order 25 minutes behind the newest event was dropped (`numRowsDroppedByWatermark` per run: `[0, 1]`), and its 99.0 never reached the sink.

## 6. Time zones and DST

**What goes wrong**
- `to_date(ts)` uses the session time zone. An event at 03:30 UTC on 10 March 2026 is still 9 March in New York.
- A fixed offset is wrong for half the year. On 1 July at 04:30 UTC, `from_utc_timestamp(ts, '-05:00')` gives 23:30 on 30 June; `'EST'` gives the same, because EST is a fixed offset. `'America/New_York'` gives 00:30 on 1 July.
- DST days aren't 24 hours long. New York's local day lasts 23 hours on 2026-03-08 and 25 hours on 2026-11-01, so local midnight plus 24 hours on 8 March lands at 01:00 on 9 March.
- Local times that don't exist, or that happen twice, are resolved without warning: 02:30 on 8 March becomes 07:30 UTC, and 01:30 on 1 November becomes 05:30 UTC (the first of its two occurrences).

**How to solve it**
- Store instants in UTC and pin `spark.sql.session.timeZone` to UTC in the job config, so `to_date`, `hour` and `current_date()` mean the same thing on every cluster.
- Convert to local time once, at the edge, with a region ID such as `America/New_York`, never a fixed offset. Store the business time zone with the entity (a store's `tz` column), because "local" differs by row.
- Derive the local date after converting. Build day boundaries by converting each local midnight to UTC, not by adding 24 hours.
- Test on DST days: 2026-03-08 and 2026-11-01 in the US, 2026-03-29 and 2026-10-25 in the UK and EU, plus events just before and after local midnight.
- For sources that send local wall-clock strings with no offset, get the zone from the source, and decide what a missing or repeated hour means.

**Prompt**
```prompt
Sales events have event_ts, a TIMESTAMP in UTC. Each store's time zone is in
dim_store.tz as a region ID such as 'America/New_York'.

Write PySpark for daily sales by each store's local calendar date. Pin
spark.sql.session.timeZone to UTC. Convert with the store's region time zone, never a
fixed offset like '-05:00' or 'EST', and derive the local date after converting.

Include tests for an event at 03:30 UTC that belongs to the previous local day, a July
event where '-05:00' would give the wrong date, and New York's DST days 2026-03-08 and
2026-11-01, which are 23 and 25 hours long. List your assumptions.
```

**Check the answer for**
- `from_utc_timestamp` with an offset such as `'-05:00'`, or an abbreviation such as `'EST'`.
- `to_date(ts)` or `date_trunc('day', ts)` with no pinned session time zone.
- `+ INTERVAL 24 HOURS` or `+ 86400` to get "the next day".
- Tests that use only ordinary days.

**Evidence** (`time_zones()`): all of the values above come from Spark, and the 2026 DST dates come from the tz database. The same bug planted in the debug kata is [B6](../exercises/ex05_debug_kata/DEBUGGING_LOG.md#2-the-bugs-the-symptom-each-produces-and-how-to-find-it), and the idioms are in [the patterns cheatsheet](pyspark-sql-patterns.md#dates-and-time-zones).

## 7. Duplicates and idempotency

**What goes wrong**
- A retried append writes the batch twice: 6 rows and a total of 50.0, where the truth is 2 events and 15.0.
- `distinct()` doesn't help when copies differ only in metadata: the same events from a resent file still leave 4 rows, because `_source_file` differs.
- MERGE alone isn't enough. An insert-only MERGE inserts both copies of a key that is duplicated inside the batch, with no error. A MERGE that updates fails with `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`.
- `orderBy(...).dropDuplicates(["event_id"])` keeps an arbitrary row ([kata B2](../exercises/ex05_debug_kata/DEBUGGING_LOG.md#2-the-bugs-the-symptom-each-produces-and-how-to-find-it)).
- A streaming `dropDuplicates` with no watermark keeps every key in state forever.
- Checkpoints and Auto Loader make ingestion exactly-once per file, not per event: a resent file with a new name is new data to them.

**How to solve it**
- Find the key that identifies an event across retries. Use the source's `event_id`, or a hash of the business fields if there is truly no ID (and agree with the owner that two identical events are one event).
- Dedupe inside the batch deterministically: `row_number()` over the key, with a full tie-break.
- Write with MERGE on the key: insert-only for immutable events, or with the sequencing guard (`WHEN MATCHED AND s.updated_at > t.updated_at`) for records that change. Re-running then changes nothing.
- In `foreachBatch`, either MERGE, or pass `txnAppId` and `txnVersion` (the batch id) so Delta skips a batch it has already committed. That protects retries of the same write, not duplicates inside it.
- For streaming dedupe, use `withWatermark` + `dropDuplicatesWithinWatermark` so the state is bounded.

**Prompt**
```prompt
Our payments feed sometimes sends an event twice (producer retries), and upstream
sometimes resends a whole day's file. Each event has event_id and updated_at.

Write PySpark that loads a batch into Delta table silver.payments idempotently: keep
one row per event_id within the batch (latest updated_at, deterministic tie-break),
then MERGE on event_id and insert only events the table doesn't have. No append.

Include tests that load the same batch twice, and a resent file with the same events,
and assert the row count and total amount don't change. List your assumptions.
```

**Check the answer for**
- `append` anywhere a retry or replay can happen.
- `distinct()` over all columns, or `dropDuplicates()` with no ordering rule.
- A MERGE whose source can still contain the same key twice.

**Evidence** (`duplicates()`): dedupe plus an insert-only MERGE, run twice and then fed the resent file, ends at `(2, 15.0)`. Writing with the same `txnAppId`/`txnVersion` twice ends at `(3, 25.0)`: Delta skipped the second write, but the in-batch duplicate stayed. The idioms are in [the patterns cheatsheet](pyspark-sql-patterns.md#latest-version-per-key-deterministic).

## 8. Join fan-out

**What goes wrong**
- One duplicate row in a dimension multiplies every fact row that matches it: 3 orders become 4 rows and revenue goes from 600 to 800, with no error.
- Many-to-many joins multiply: 3 rows × 4 rows on one key gives 12 rows, and one key's task becomes huge (skew).
- Joining an SCD2 table on the business key alone matches every version of the customer.

**How to solve it**
- State the grain of both sides before joining: which columns make a row unique.
- Check that the dimension is unique on the join key. If it isn't, stop and show the duplicates, or dedupe it to one row per key on purpose (the kata's B5 fix).
- Assert that the fact row count is unchanged after a LEFT join to a dimension.
- For SCD2, join point-in-time on the key plus `valid_from <= ts < valid_to`: half-open, with a NULL `valid_to` for the current version ([Exercise 02](../exercises/ex02_scd2_merge/WALKTHROUGH.md)).
- If many-to-many is the real shape (a bridge table), aggregate to the target grain first, or allocate with weights that sum to 1 per fact row.

**Prompt**
```prompt
Write a PySpark helper safe_left_join(fact, dim, keys) for joining a fact table to a
dimension. It raises if dim has more than one row per keys (showing the top
duplicates), and raises if the join changes the fact row count. Never use distinct()
to hide duplicates.

Then join orders to dim_customer, an SCD2 table (valid_from, valid_to; NULL valid_to
means current), point-in-time: same customer_id and valid_from <= order_ts < valid_to.
Check that no customer has overlapping versions, and that each order matches at most
one version.

Include tests where a duplicated customer row raises instead of doubling revenue, and
a customer with two versions matches the right one. List your assumptions.
```

**Check the answer for**
- `.distinct()` or `dropDuplicates()` after the join to "fix" the counts. It hides the problem and can merge rows that are legitimately identical.
- An SCD2 join on `customer_id` alone, or with `BETWEEN`, which is closed at both ends, so an event on a boundary matches two versions.
- Row-count checks that run on a sample, or not at all.

**Evidence** (`join_fanout()`): `safe_left_join raises: dimension not unique on ['customer_id']: [('C2', 2)]`. The same bug, planted, is [kata B5](../exercises/ex05_debug_kata/DEBUGGING_LOG.md#2-the-bugs-the-symptom-each-produces-and-how-to-find-it); the guard idiom is in [the patterns cheatsheet](pyspark-sql-patterns.md#joins).

## 9. Bad keys and inconsistent normalization

**What goes wrong**
- The same customer shows up as `' c001'`, `'C001 '`, `'c-001'`, `'C0001'`, `1` and `'00001'`. String equality sees six different keys, so joins silently miss.
- Comparing a STRING key with a BIGINT key makes Spark cast the string. `'007'` matches 7, and with ANSI on a single `'N/A'` fails the whole join with `CAST_INVALID_INPUT`. With ANSI off, `'N/A'` silently matches nothing.
- UUIDs in upper case, in braces or without hyphens don't match their canonical form.

**How to solve it**
- Define one canonical form per key and write it down with the data owner: case, padding, separators and prefix.
- Implement it once, as a column function built from `trim`, `upper`, `regexp_replace` and `lpad`, with no Python UDF, and apply it to both sides of every join. Keep the raw key next to it for audit.
- Return NULL for values that don't fit, and quarantine them, rather than guessing.
- Join on the same type: cast explicitly, and never rely on implicit STRING/BIGINT coercion.
- Measure the unmatched-key rate after each join and list the top unmatched raw values. A rising orphan rate usually means a new key format.

**Prompt**
```prompt
Customer IDs differ across systems: ' c001', 'C001 ', 'c-001' and 'C0001' in the web
app; integers (1) and zero-padded strings ('00001') in billing.

Write one PySpark column function, normalize_customer_id, that trims, upper-cases,
removes separators and returns 'C' plus 5 digits, or NULL when the value doesn't fit
(so it can be quarantined). Use only built-in functions, no UDF. Apply it to both
sides of every join, cast explicitly (never compare STRING with BIGINT), and report
the share of orders with no matching customer plus the top 10 unmatched raw IDs.

Include a test for each variant above. List your assumptions, and ask before treating
two formats as the same customer.
```

**Check the answer for**
- Normalization applied to only one side of the join.
- A Python UDF for what the built-in string functions already do. It's slower, and the optimizer can't see inside it.
- `cast(... AS INT)` to "normalize" zero-padded IDs. It strips leading zeros that may matter, and fails on the first non-numeric value.
- Rules that merge IDs the business considers different. Is `C0001` really `C001`? The assumptions list is where this shows up.

**Evidence** (`bad_keys()`): all six variants normalize to `C00001` and `'X9'` to NULL; three spellings of one UUID collapse to one; the STRING = BIGINT join fails with `CAST_INVALID_INPUT` while `'N/A'` is present.

## One prompt to review someone else's pipeline

When the code already exists, ask for a targeted review instead of a rewrite:

```prompt
Review this pipeline for nine failure modes: schema drift, silent casts, nullability
changes, incremental watermark bugs, late-arriving data, time zones and DST,
duplicates and idempotency, join fan-out, and inconsistent keys.

For each one that applies: quote the lines at risk, give an input that would break
them, and propose the smallest fix with a test that fails before the fix and passes
after. Say "not applicable" when one doesn't apply. Don't invent problems.
```

Then run each proposed test before accepting the finding. The Assistant over-reports as readily as it under-reports, and a finding without a failing test is only a guess ([case 06](../case-studies/06-near-misses-and-false-positives.md) lists fifteen of mine).
