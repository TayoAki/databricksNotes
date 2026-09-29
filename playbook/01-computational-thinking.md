# 01. Computational thinking: turning a messy problem into a sequence of transformations

> **What's being assessed:** "Can you break a messy problem into a logical sequence of transformations?"

The skill isn't knowing many functions. It's being able to say, at every step, **what one row means** and **what this step does to the rows**. When I can say that, the code is mostly typing, and when a number is wrong I know where to look.

## 1. Grain first

**Grain** = what one row represents ("one row per order", "one row per customer per day"). Before writing a transform I write down the grain of the input, the grain of the output, and the grain of every intermediate. Then each step can be checked against it:

| Step type | Effect on grain | What must be true |
|---|---|---|
| filter | same grain, fewer rows | the predicate's NULL behaviour is intended |
| select / withColumn | same grain, same rows | nothing |
| dedupe (latest per key) | coarser: one row per key | the ordering is deterministic (full tie-break) |
| join to a dimension | **same grain** as the fact | the dimension is unique on the join key; otherwise the join fans out |
| join fact to fact | new grain (often wrong) | almost never what you want: drill across through dimensions |
| aggregate | coarser: one row per group | measures are additive over the grouped dimensions |
| explode | finer | intended |
| window | same grain | partitioned by the right key (kata B8) |

**Say:** "The fact is one row per order. After joining customers it must still be one row per order. I'll assert that the row count doesn't change, because if the customer file has duplicates, revenue silently doubles."

## 2. The step ledger: four questions per step

For each step, answer (this is also how I read someone else's pipeline, see [02](02-code-stewardship.md)):

1. **Cardinality:** can it add rows (join, explode) or drop them (filter, inner join)?
2. **NULLs:** what happens to a NULL in each column it touches? ([07](07-null-semantics.md))
3. **Determinism:** would two runs over the same input give the same output?
4. **Semantics:** does it match the business definition (time zone, currency, what counts as revenue)?

## 3. Pattern catalogue

These are the transformations that real customer problems decompose into. Each idiom marked ✔ is executed in [`patterns_demo.py`](patterns_demo.py) or in an exercise.

| # | Problem shape | Transformation | Idiom | Pitfall | Proof |
|---|---|---|---|---|---|
| P1 | Raw, messy input | **Parse and type** at a boundary, keep the raw | explicit STRING schema; `PERMISSIVE` + `_corrupt_record`; `try_cast` / `try_to_timestamp` | `inferSchema` is sample-dependent; plain `CAST` throws under ANSI | ✔ Ex01 |
| P2 | Some rows are bad | **Validate and quarantine**, with a reason per row | `coalesce(rule, false)` per rule; array of failed rule names | a NULL rule result routes the row nowhere | ✔ Ex01, [case 02](../case-studies/02-null-semantics-in-quarantine-predicates.md) |
| P3 | Several versions per key | **Latest per key** | `row_number() OVER (PARTITION BY key ORDER BY event_ts DESC, tiebreak…) = 1` | `orderBy().dropDuplicates()` keeps an arbitrary row | ✔ Ex01, kata B2 |
| P4 | Updates arrive out of order | **Sequenced upsert** | `MERGE … WHEN MATCHED AND s.seq > t.seq`; SDP: `create_auto_cdc_flow(sequence_by=…)` | an older event overwrites a newer one | ✔ Ex01 |
| P5 | Need history of attributes | **SCD2**: close the old version, open a new one | hash tracked attributes; stage closers + inserts; MERGE | no-op updates create versions; multiple changes per key in one batch break a naive MERGE | ✔ Ex02 |
| P6 | Attribute as of event time | **Point-in-time join** on a validity interval | `ON k AND ts >= valid_from AND (valid_to IS NULL OR ts < valid_to)` | closed intervals double-match at boundaries | ✔ below, Ex02 |
| P7 | Enrich facts | **Dedupe the dimension, then join, then assert grain** | `assert_same_row_count(before, after)` | fan-out: C002 twice → 2379.48 instead of 2219.49 | ✔ Ex01 |
| P8 | "Top N per group" | **Rank within partition** | `row_number()` for exactly N, `dense_rank()` to include ties | a Window without `partitionBy` ranks globally | ✔ below, kata B8 |
| P9 | Events → visits | **Sessionization** | `LAG` gap > threshold → flag; running `SUM` of flags = session id | time zone and clock skew in the gap | ✔ below |
| P10 | Streaks / runs | **Gaps and islands** | `date − row_number()` is constant within a run of consecutive days | duplicates per day break the arithmetic, so dedupe first | ✔ below |
| P11 | Balances, headcount, inventory | **Semi-additive** measure: last value per period | the value at the period's max date per entity, then SUM across entities | SUM over days: 430 instead of 160 | ✔ below |
| P12 | History tables (`system.*`) | **Latest row, then lifecycle filter** | rank in a CTE; `recency = 1 AND delete_time IS NULL` outside | filtering first resurrects deleted objects (WAF: 45×) | ✔ [evidence](../case-studies/evidence/scd_filter_before_rank.py) |
| P13 | Usage × price | **Range join with a boundary rule + coverage** | half-open interval on one timestamp; LEFT JOIN; count unpriced and duplicate matches | containment drops rows that span a change | ✔ [case 08](../case-studies/08-price-join-containment-vs-point-in-time.md) |
| P14 | Only new data each run | **Incremental processing** | checkpoints (`availableNow`), an ingestion ledger, CDF with `_change_type` filters | reprocessing, missed files, unbounded state | ✔ Ex01, Ex04 |
| P15 | Any KPI | **Reconcile** against an independent calculation | gold total = silver sum; rows in = rows out + quarantined | eyeballing | ✔ Ex01 |

### The idioms, as executed

```sql
-- P9 sessionization: a new session after 30 minutes of inactivity
WITH flagged AS (
  SELECT *, CASE WHEN ts - LAG(ts) OVER (PARTITION BY user_id ORDER BY ts) <= INTERVAL 30 MINUTES
                 THEN 0 ELSE 1 END AS new_session
  FROM clicks)
SELECT user_id, ts, SUM(new_session) OVER (PARTITION BY user_id ORDER BY ts) AS session_no FROM flagged
-- u1: 10:00→1, 10:10→1, 11:30→2, 11:45→2 ; u2: 09:00→1

-- P10 gaps and islands: consecutive-day streaks
WITH g AS (SELECT customer_id, d,
                  date_sub(d, CAST(ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY d) AS INT)) AS island
           FROM active_days)
SELECT customer_id, min(d), max(d), count(*) FROM g GROUP BY customer_id, island
-- c1: 09-01..09-03 (3 days), 09-05..09-06 (2 days)

-- P11 semi-additive: month-end balance, not a sum over days
SELECT date_trunc('month', d), SUM(balance) AS wrong, SUM(month_end) AS right
FROM (SELECT *, CASE WHEN d = max(d) OVER (PARTITION BY account, date_trunc('month', d))
                     THEN balance END AS month_end FROM balances) GROUP BY 1
-- wrong = 430, right = 160 (a1 ends at 90, a2 ends at 70)

-- P6 point-in-time: the segment as of the order date
... ON o.customer_id = c.customer_id AND o.d >= c.valid_from AND (c.valid_to IS NULL OR o.d < c.valid_to)
-- o1 (March) → SMB ; o2 (August) → Enterprise

-- P8 ties: row_number gives EMEA r2=1, r3=2 ; dense_rank gives both 1
```

On Databricks, UC **metric views** encode P11 declaratively (window measures with `semiadditive: last`), which is why they matter for KPIs such as ARR and account counts. The Customer-360 metric view in technical-services-solutions gets this wrong: it sums snapshot measures across a daily spine.

## 4. Worked decompositions

### A. "Daily revenue by region" from a messy order feed (Exercise 01)

```
raw lines (1 per line) ─P1─► typed rows ─P2─► valid rows │ quarantine (1 per bad line + reasons)
  ─P3─► latest version (1 per order) ─P4─► silver orders (MERGE with sequence guard)
  ─P7─► + dim_customer (deduped: 1 per customer; LEFT join; "Unknown")
  ─────► + fx rate (DECIMAL) ─► aggregate: 1 per (day, region, segment) ─P15─► reconcile
```

### B. "What does each team spend on Databricks?" (system tables)

```
system.billing.usage (1 per usage record; includes negative corrections)
  ─P13─► + list price at usage_end_time (LEFT; count unpriced + duplicate matches)
  ─────► cost = quantity × price, per usage_unit (DBU, DSU and GB don't add)
  ─────► team = custom_tags['team'] (classic), budget policy (serverless), else identity → owner
  ─────► aggregate: 1 per (team, month, unit) + coverage: tagged share, unpriced share
```
Each arrow is a place an assistant (or a person) goes wrong; see [`cheatsheets/system-tables-best-practice-checks.md`](../cheatsheets/system-tables-best-practice-checks.md).

### C. A dimension that reflects changes in *any* source table (lakeflow TPCH `dim_customer`)

The "streaming DWH" pattern, in four steps:
1. **Keys-only fan-in:** each of the three silver SCD2 feeds (customer, address, phone) appends `{customer_key, __START_AT AS version_ts}` into one append-only staging table.
2. **Dedupe the change points:** an SCD2 flow keyed on `customer_key`, sequenced by `version_ts`, yields one row per distinct change point.
3. **As-of join:** its change feed drives SQL that joins every source table *as of* each `version_ts` (P6).
4. **Surrogate key:** `xxhash64('customer', key, __START_AT)`, written to the SCD2 target.

Why: a stream-static join reflects the dimension only "as of now"; this pattern re-drives a key whenever *any* joined table changes.

## 5. Heuristics I use

- **Work backwards from the output grain.** The final GROUP BY is known before any code; every step must preserve or coarsen towards it.
- **Separate "which rows" from "which version".** Filtering and deduplication are different questions; mixing them is how WAF's 45× bug happened.
- **Push filters early, except past a window over a lifecycle column.** A predicate inside a windowed query is only safe if it's decided by the partition columns.
- **Make each step a function with a test.** A pure `DataFrame → DataFrame` function per step is easy to test on 5 rows, easy to reorder, and easy to reuse in an SDP pipeline.
- **Prefer declarative platform features once the logic is clear:** SDP expectations for P2, AUTO CDC for P4/P5, metric views for P11, Auto Loader for P14. Knowing the hand-written version lets me explain what the declarative one does.
