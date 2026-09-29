# Case study 08: two ways to price usage, and the rows one of them loses

**Repos:** `starter-journey` @ `ac21559` (`docs/.../cost-monitoring/tag-compute-and-jobs.mdx`, "Cost by team tag") vs `databricks-waf` @ `e765461` (`app/config/statements/cost_attribution_coverage.sql`, plus the probe `app/server/collect/sql/runtime-baseline/probes/billing-price-coverage.sql`)
**Status:** the mechanics are CONFIRMED by execution on a constructed example ([`evidence/price_join_demo.py`](evidence/price_join_demo.py)). The size of the effect on real accounts is **data-dependent**: WAF measured zero boundary-spanning records on its lab workspace (see below).

## Why this is a good interview story

"What does this cost?" is the first question every customer asks, and the answer usually comes from joining `system.billing.usage` to `system.billing.list_prices`. The two repos write that join differently. The difference is a **business rule hiding in a join condition**: *which price applies to usage that spans a price change?* It is also a clean example of reading two teams' code and explaining why they disagree.

## The two joins

**starter-journey (containment, INNER JOIN):** the usage interval must sit entirely inside one price interval.
```sql
FROM system.billing.usage u
JOIN system.billing.list_prices lp
  ON u.sku_name = lp.sku_name
  AND u.cloud = lp.cloud
  AND u.usage_start_time >= lp.price_start_time
  AND (u.usage_end_time <= lp.price_end_time OR lp.price_end_time IS NULL)
```

**databricks-waf (point-in-time on `usage_end_time`, LEFT JOIN, coverage reported):**
```sql
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name
  AND u.usage_end_time >= p.price_start_time
  AND (p.price_end_time IS NULL OR u.usage_end_time < p.price_end_time)
...
count(*) - count(DISTINCT record_id)                       AS duplicate_price_matches,
count(DISTINCT CASE WHEN rate IS NULL THEN record_id END)  AS unpriced_records,
```

## The experiment

Three one-hour usage records of 10 DBUs. The price changes from 0.50 to 0.55 at 12:00, and record `r2` runs from 11:30 to 12:30:

```
containment  : {'matched_rows': 2, 'cost': 10.5}
point-in-time: {'matched_rows': 3, 'priced_rows': 3, 'duplicate_matches': 0, 'cost': 16.0}
```

Under containment, `r2` fits inside **neither** price interval, so the INNER JOIN drops it. The total is short by a third, and nothing on the result says so. Under the point-in-time rule, every record gets exactly one price, the one in force when it *ended*, and the query also reports how many rows were unpriced or double-matched.

## Honest scope: how big is this in practice?

The WAF authors measured it. Their statement's header says: "Q1a measured zero records on labs where start and end disagreed; this statement still documents and tests the end-time rule rather than treating that sample as proof the two are equivalent." Usage records are short, and price changes are rare, so straddling rows may be rare or absent in a given account. I would present it that way:
- **The straddle** is a correctness hole with a probably small effect. Check it rather than assume it, using WAF's probe pattern: join twice (start-time boundary and end-time boundary) and count the rows where the prices differ.
- **The INNER JOIN** is the bigger practical risk. A SKU that is missing from `list_prices`, or a usage row outside every price interval, disappears from the total with no trace. The LEFT JOIN plus an `unpriced_records` column makes that gap visible.
- **Duplicate matches:** a price-join condition does not by itself guarantee one match per usage row. WAF's own probe comment retracts its earlier assumption that it did: "Nothing in the join makes that true: two list-price rows for one SKU and interval — the same rate quoted in two currencies would do it — match one usage row twice". WAF now returns `duplicate_price_matches` rather than trusting the price list.

## The general lessons

1. **A join condition can encode a business rule.** When you see a range join, ask what happens at the boundaries and to rows that span one. Write the answer down.
2. **Report coverage beside every sum:** priced vs unpriced records, and duplicate matches. A total without its coverage can't be checked.
3. **Prefer LEFT JOIN + explicit accounting over INNER JOIN for money.** An INNER JOIN is a silent filter.
4. **Half-open intervals** (`>= start AND < end`) make every instant belong to exactly one interval. Mixing `<=` on one end with `>=` on the other creates overlaps or gaps.
5. **Units don't add.** WAF computes coverage per `usage_unit`, because DBUs, DSUs and GB appear in the same table ("one pooled priced-share is a DBU share wearing a general name").
6. **List price ≠ what the customer pays.** Both queries use `pricing.effective_list.default`. Discounts and commitments are elsewhere, so label the output "estimated list cost".

## How I'd explain it

- **To a FinOps lead:** "Our cost query only priced usage that fitted entirely inside one price period, and it silently skipped anything it couldn't price. We now price each record at the rate in force when it ended, and the report shows how much usage had no price, so you can see whether the total is complete."
- **To an engineer:** "Range joins need a boundary rule and a coverage check. Use a half-open interval on one timestamp, a LEFT JOIN, and return `unpriced_records` and `duplicate_price_matches` with the sum."
