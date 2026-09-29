# 07. NULL semantics: the most common silent bug across all six repos

Three-valued logic (TRUE / FALSE / **UNKNOWN**) caused or nearly caused bugs in three independent places in this work:
- lakeflow_framework's quarantine predicate routes rows with NULL rule results **nowhere** ([case 02](../case-studies/02-null-semantics-in-quarantine-predicates.md));
- databricks-waf's self-exclusion filter kept **0 of 6,969** statements until its authors rewrote it with `CASE`;
- my debug kata's B4: `status != 'cancelled'` silently drops orders whose status is NULL.

## 1. The rules, verified on Spark 4.0.1 with ANSI on

Every row below was executed by [`case-studies/evidence/null_semantics_table.py`](../case-studies/evidence/null_semantics_table.py) on a 4-row table `t(id, status, amount)` = `(1,'A',10), (2,NULL,20), (3,'B',NULL), (NULL,'C',5)`.

| Expression | Result | Why it matters |
|---|---|---|
| `NULL = NULL` | **NULL** | Equality never matches NULLs |
| `NULL <=> NULL` (null-safe equal) | TRUE | Use `<=>` / `eqNullSafe` when NULL should match NULL |
| `NOT (NULL)` | **NULL** | Negating "unknown" is still unknown |
| `NULL AND false` | FALSE | FALSE dominates AND |
| `NULL OR true` | TRUE | TRUE dominates OR |
| rows kept by `WHERE status != 'A'` | **2** of 4 | The NULL-status row is dropped as well as the `'A'` row |
| rows kept by `WHERE NOT (status <=> 'A')` | 3 of 4 | Null-safe negation keeps the NULL row |
| `count(*)` vs `count(amount)` | 4 vs 3 | `count(col)` skips NULLs (kata B7) |
| `avg(amount)` | 11.67 (= 35 / 3) | Aggregates ignore NULLs: the average of the *known* values |
| `sum(amount)` over zero rows | **NULL** | Not 0: `coalesce(sum(x), 0)` if 0 is what the business means |
| `count(amount)` over zero rows | 0 | Counts are never NULL |
| `1 NOT IN (2, NULL)` | **NULL** | One NULL in the list makes NOT IN unknowable |
| rows from `WHERE amount NOT IN (SELECT id FROM t)` (ids contain a NULL) | **0** | The classic "anti-join returns nothing" bug. Use `NOT EXISTS` or a left anti join |
| `concat('a', NULL)` | **NULL** | One NULL poisons the whole string |
| `concat_ws('\|', 'a', NULL, 'b')` | `a\|b` | Skips NULLs, which can make different inputs hash the same (see §3) |
| `greatest(1, NULL, 3)` | 3 | Skips NULLs |
| number of groups from `GROUP BY status` | 4 | NULL forms its own group |
| `count(DISTINCT status)` | 3 | But DISTINCT counts skip NULL |
| join on a NULL key with `=` | 0 matches | NULL keys never join… |
| join on a NULL key with `<=>` | 1 match | …unless you use null-safe equality |
| `CASE WHEN NULL THEN 1 ELSE 0 END` | 0 | `CASE` sends UNKNOWN to `ELSE`: the WAF fix |
| `try_cast('abc' AS INT)` | NULL | Garbage becomes NULL… |
| `CAST('abc' AS INT)` under ANSI | **error** `CAST_INVALID_INPUT` | …while a plain cast fails the query (Spark 4 / serverless default) |

## 2. The core insight: WHERE keeps only TRUE

A filter keeps rows whose predicate is TRUE. FALSE and **UNKNOWN** are both dropped. So a filter meant to route rows into two buckets (valid / invalid) can lose rows that are neither: a row whose rule is UNKNOWN fails `WHERE valid` *and* `WHERE NOT valid`. That is exactly the lakeflow quarantine gap:

```
rule:        amount > 0          amount = NULL  →  UNKNOWN
flag:        NOT(rule)           NOT(UNKNOWN)   →  UNKNOWN
quarantine:  .where(flag)        dropped
clean table: .where(NOT flag)    dropped (or kept, depending on how the clean side is written)
```

## 3. Patterns I use

| Situation | Pattern |
|---|---|
| DQ rule that must treat "missing" as a failure | `coalesce((rule), false)`, applied per rule before combining (Exercise 01's `with_dq_failures`) |
| Exclusion filter on a nullable column | `NOT (col <=> 'x')` in SQL, `~F.col(c).eqNullSafe('x')` in PySpark |
| Complex exclusion (several OR'd conditions, possibly NULL) | Compute a flag with `CASE WHEN … THEN 1 ELSE 0 END`, then filter `flag = 0` (the WAF fix) |
| Anti-join | `NOT EXISTS (…)` or `left_anti` join, never `NOT IN (subquery)` on a nullable column |
| Aggregates where "no data" should be 0 | `coalesce(sum(x), 0)`, and decide if 0 or "unknown" is the honest answer |
| Row hashes for change detection (SCD2) | Make NULL explicit: `sha2(concat_ws('\|\|', coalesce(cast(col AS STRING), '<NULL>'), …), 256)`, so `('x', NULL)` and `(NULL, 'x')` hash differently (Exercise 02's `with_row_hash`) |
| Joining on keys that can be NULL | Decide: should NULL match NULL? If yes, `<=>`; if no, filter NULL keys out explicitly (and they also skew the join) |
| Parsing dirty input | `try_cast` / `try_to_timestamp`, then a NULL-safe rule that sends the resulting NULL to quarantine with a reason |

## 4. How to find NULL bugs in someone else's code

- Grep for `!=`, `<>`, `NOT (`, `NOT IN`, `.isin(` negated with `~`, `when(` without `otherwise`, `count(` on a column, joins on nullable keys.
- For every predicate, ask: **"What happens to a row where this column is NULL?"** Then test it with a one-row DataFrame of NULLs.
- Watch the optimizer: in Exercise 01 the physical plan shows `PushedFilters: [IsNotNull(status), Not(EqualTo(status,cancelled))]`. Spark adding `IsNotNull(status)` is the optimizer telling you NULL-status rows are going.
- Validate rule sets up front: evaluate each user-supplied rule against an all-NULL row, and reject or flag rules that return NULL.

## 5. How I'd explain it to a business user

> "Every check answers 'is this record OK?' with yes, no, or *we can't tell*, whenever a value is missing. Our filters only acted on the yes and no answers, so records with missing values slipped between the two. We've made every rule say what a missing value means, and there's now a test with a blank record so it can't come back."
