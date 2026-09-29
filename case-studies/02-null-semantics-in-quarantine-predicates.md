# Case study 02: NULL slips past the quarantine

**Repo:** `lakeflow_framework` @ `0e8d0ca`, `src/lakeflow_framework/dataflow/quarantine.py:54-56`, `sources/base.py:124-130`
**Status:** Predicate behaviour CONFIRMED by execution ([`evidence/verify_lakeflow_semantics.py`](evidence/verify_lakeflow_semantics.py)). The end-to-end effect inside a Databricks SDP pipeline is SUSPECTED; it depends on how SDP expectations treat a NULL rule result, which I could not run.
**Same bug class found independently in:** databricks-waf (found and fixed by its authors), and my Exercise 05 kata (B4).

## The code

The framework combines every data-quality rule into one "is this row bad?" predicate:
```python
# Each rule is parenthesised so a rule containing OR cannot change the
# meaning of the combined predicate.
self.quarantine_rules = f"NOT({ ' AND '.join(f'({rule})' for rule in data_quality_rules.values()) })"
```
- **Table mode** keeps `.where(F.col("is_quarantined"))` rows for the quarantine table.
- **Flag mode** stores the predicate's value in an `is_quarantined` column.

## What happens with NULLs (executed on Spark 4.0.1)

Rules: `amount > 0` and `id IS NOT NULL`. The predicate becomes `NOT((amount > 0) AND (id IS NOT NULL))`.

| id | amount | `is_quarantined` | routed to quarantine table? |
|---|---|---|---|
| 1 | 10.0 | false | no |
| 2 | -5.0 | true | yes |
| 3 | **NULL** | **NULL** | **no** ← the gap |
| NULL | 7.0 | true | yes |

Row 3's rule evaluates to NULL (`NULL > 0`). `NOT(NULL AND TRUE)` = `NOT(NULL)` = NULL, and `.where(NULL)` drops the row. In flag mode the flag is NULL, which is neither true nor false, so any downstream `WHERE is_quarantined = false` also loses it.

## The parentheses fix is real, and worth appreciating

With rules `status = 'A' OR status = 'B'` and `qty > 0`:
- **Unparenthesised:** `NOT(status = 'A' OR status = 'B' AND qty > 0)`. `AND` binds tighter, so row `(A, qty=0)` is **not** flagged, even though it fails `qty > 0`.
- **Parenthesised:** it is flagged.

The comment records a real bug fix (commit `deece3d`, #141 in the public history, per the deep-read). The general lesson: **when you compose user-supplied predicates, always parenthesise each one, and decide what NULL means.**

## The fix I'd propose

Decide the policy explicitly. For a *quarantine* ("anything not proven valid is suspect"), make NULL a failure:
```python
self.quarantine_rules = "NOT(" + " AND ".join(f"coalesce(({r}), false)" for r in rules.values()) + ")"
```
Alternatively, require each rule to be null-safe, such as `amount IS NOT NULL AND amount > 0`, and validate that at spec-build time by evaluating each rule against a one-row all-NULL DataFrame. Rules that return NULL there are ambiguous and should be rejected or rewritten. Exercise 01 implements the coalesce version (`with_dq_failures`), and `test_null_unsafe_rule_would_leak_the_null_amount` proves the difference: the naive predicate catches 1 of 2 bad rows, and the null-safe one catches 2 of 2.

## The same bug, elsewhere

- **databricks-waf** `app/config/statements/workload_sql_paths.sql:112-121`. The authors' own comment: written as one `AND NOT (…)`, the filter "returned zero statements of 6,969 on labs while the identical expression counted 3,773 of them as ours". `try_element_at` returned NULL for untagged statements, so the whole chain was NULL and `NOT NULL` kept no rows. Their fix computes a `CASE WHEN … THEN 1 ELSE 0 END` flag and filters `= 0`, because a `CASE` sends NULL to `ELSE`.
- **Exercise 05, B4:** `status != 'cancelled'` silently drops NULL-status orders. The Exercise 01 plan shows Spark inserting `IsNotNull(status)` into the pushed filters, which is the optimizer telling you the same thing.

Full rules table: [`playbook/07-null-semantics.md`](../playbook/07-null-semantics.md).

## How I'd explain it to a customer

> "Your data-quality rules answer 'is this row valid?' with yes, no, or *unknown*, whenever a value is missing. The quarantine only catches the 'no's. Rows with missing values are neither caught nor clearly passed. We'll make every rule say explicitly what a missing value means, and add a test with a blank row so it can't regress."
