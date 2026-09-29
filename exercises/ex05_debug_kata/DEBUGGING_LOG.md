# Exercise 05: debug kata. A green job that's wrong.

> **The situation:** "This is the daily revenue job the last contractor wrote. It runs green every night. Finance says the numbers are off by 'a few percent, sometimes'. Can you take a look?"

Files:
- `customer_pipeline_buggy.py`: read it cold first.
- `test_kata.py`: the spec, as tests.
- `customer_pipeline_fixed.py`: fixes tagged `[B1]`–`[B8]`.

Run `pytest ex05_debug_kata -q -rx`. The fixed module passes. Each buggy function fails its own test (`xfail(strict=True, raises=AssertionError)`), and the xfail reasons are the answer key.

## 1. How I read someone else's pipeline (before running anything)

1. **Draw the data flow.** `load_orders → latest_orders → to_usd → revenue_orders → attach_region → daily_revenue → region_rank`. One line per step: *input grain → output grain*.
2. **For every step, ask the four data questions:**
   - **Cardinality:** can this step add rows (joins, explode) or drop rows (filters, inner joins)?
   - **NULLs:** what happens to a NULL in every column this step touches?
   - **Determinism:** would two runs over the same input give the same output?
   - **Semantics:** does it match the business definition, including time zone, currency and what counts as revenue?
3. **Mark every place where Spark resolves by position or by default:** `union`, `when` without `otherwise`, `count(col)`, `Window` without `partitionBy`, implicit time zones.

That checklist finds 7 of the 8 bugs before running a single line. The eighth (B2) needs knowledge of Spark semantics.

## 2. The bugs, the symptom each produces, and how to find it

| # | Code smell | Symptom in the numbers | How to detect it | Fix |
|---|---|---|---|---|
| B1 | `web.union(store)` | Store revenue ~10× too small: quantities summed as money | `printSchema()` of both inputs; `union` matches **by position** | `unionByName` (and `allowMissingColumns` if needed) |
| B2 | `orderBy(ts.desc()).dropDuplicates(["order_id"])` | *Sometimes* an old order version wins | **Can't reliably reproduce locally.** The plan is `Aggregate[first(...)]` over a Sort; `first()` "is non-deterministic … after a shuffle" (PySpark docstring) | `row_number() over (partition by key order by ts desc, tiebreak)` |
| B3 | `when(USD).when(EUR)` with no `otherwise` | GBP orders vanish from revenue | `groupBy(currency).agg(count, count(amount_usd))`: the NULL counts give it away | Mapping for every currency; **fail loudly** on unknowns |
| B4 | `status != 'cancelled'` | Orders with NULL status disappear | Compare `count()` before and after the filter, and count NULL statuses | `~col("status").eqNullSafe("cancelled")` |
| B5 | Join to a region map with duplicate keys | Some customers' revenue doubled | Row count before vs after the join; `groupBy(key).count().where("count > 1")` on the dimension | Dedupe the dimension (latest `valid_from`) before joining |
| B6 | `from_utc_timestamp(ts, 'America/Los_Angeles')` then `to_date` | Late-UTC orders land on the previous day | Pick one order at 02:00 UTC and trace it | Bucket in the reporting time zone the business actually uses (UTC); pin the session TZ |
| B7 | `count("customer_id")` as order count | Orders without a customer are uncounted | `count(*)` vs `count(col)` side by side | `count(lit(1))` / `count("*")` |
| B8 | `Window.orderBy(...)` with no `partitionBy` | Ranks are global, not per region; Spark logs "No Partition Defined for Window operation!" | Read the WARN log; check that each region has a rank 1 | `Window.partitionBy("region").orderBy(...)` |

## 3. The row-count ledger: bisecting a wrong number

When the total is wrong and you don't know where, count rows at every step. Also track the NULLs in key columns and the sum of the money column:

```python
def ledger(df, step):
    r = df.agg(F.count("*").alias("rows"),
               F.count("amount").alias("non_null_amount"),
               F.sum("amount").alias("amount")).first()
    print(f"{step:18} rows={r.rows:6} non_null_amount={r.non_null_amount:6} amount={r.amount}")
    return df
```

Wrap each step (`ledger(to_usd(...), "to_usd")`). The first step where rows or amounts move unexpectedly is the bug's home. Each `ledger` call is an action, so it runs a job. It's fine for diagnosis; remove it afterwards, or use expectations/metrics in production.

## 4. Lessons from building the kata itself (the honest part)

- **My first B2 test gave XPASS.** The buggy dedup returned the *correct* row in all 5 layouts I tried. That is the nature of non-determinism: laptop tests can't prove its absence. I replaced it with (a) a behavioural test that honestly passes for **both** versions locally, documented as such, and (b) a **structural** test asserting the optimized plan contains no `first(`/`last(`/`any_value(` aggregate. You catch B2 by knowing semantics, not by testing.
- **A broken fixture hid behind 9 green "expected failures".** My test data had a string where a DATE was needed. The fixture crashed, and every buggy-module test reported **XFAIL**, because a bare `xfail` accepts *any* exception. The fix was `xfail(raises=AssertionError)`, so only a wrong *answer* counts. *General lesson: make negative tests specific about why they fail.*
- **This is not a toy bug list.** B2 is recommended as "✅ SIMPLE and RELIABLE" in a real skill pack (`vibe-coding-workshop-template/.../03-deduplication/SKILL.md:159-172`, which also says to *avoid* `row_number()`). B4 is the same three-valued-logic hole found in lakeflow_framework's quarantine predicate and fixed in databricks-waf's SQL. B5 (dimension fan-out) is the metric-view warning in starter-journey ("Inflated totals mean the join is fanning out").

## 5. How I'd explain the fix to Finance

> "Three things were quietly dropping revenue: orders in pounds, orders whose status hadn't been set yet, and orders without a customer on the count. Two things were inflating it: customers listed twice in the region map, and store quantities read as amounts. Late-evening UTC orders were landing on the wrong day. Each fix now has a test, so it can't come back, and the total reconciles to the order level."
