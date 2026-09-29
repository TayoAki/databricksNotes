# System tables: best-practice checks for a customer's workspace

"How do I know my workspace follows best practices on cost, security and reliability?" This cheatsheet answers it with Unity Catalog system tables, following databricks-waf's discipline: **every share states its denominator, every sum states its coverage, and anything unreadable is reported as unmeasured, never as a pass.**

**Provenance and status.** The queries below are adapted from databricks-waf's statements (`app/config/statements/*.sql`), whose authors ran them against real estates and left their measurements in the comments. The column names are copied from those statements. I haven't run them against a live workspace (none is available here), so `DESCRIBE` each table first; columns evolve, and WAF notes some `lakeflow.jobs` columns are NULL before December 2025. The two SQL *mechanisms* they rely on (point-in-time pricing, rank-then-filter) I reproduced on Spark: [case 08](../case-studies/08-price-join-containment-vs-point-in-time.md), [`scd_filter_before_rank.py`](../case-studies/evidence/scd_filter_before_rank.py).

## The five traps (read these first)

1. **History tables are SCD2** (`compute.clusters`, `compute.warehouses`, `lakeflow.jobs`, …): one row per change plus a final row at deletion. **Rank first, then filter `delete_time IS NULL` on the chosen row.** Filtering first resurrected deleted clusters: 6,136,941 "live" where 135,177 existed (45×).
2. **Price joins need a boundary rule:** point-in-time on `usage_end_time` within `[price_start_time, price_end_time)`, LEFT JOIN, and report unpriced and duplicate matches. Money is **list price** (`pricing.effective_list.default`), not the negotiated bill.
3. **Units don't add:** DBU, DSU and GB appear in the same table. Group by `usage_unit`.
4. **`product_features.is_serverless` alone is wrong:** it's false on serverless-only products such as MODEL_SERVING and LAKEBASE (WAF: $12,770 understated on a $16,190 bill). Classify by the flag **or** the product.
5. **`information_schema` is privilege-filtered:** zero rows means "can't see", not "empty estate". Cross-check with an unfiltered source (e.g. lineage) before concluding anything.

Also: `current_date() - make_dt_interval(N)` spans N+1 calendar dates; windows over `usage_date` prune better than `usage_start_time`; usage has negative correction rows, so always `SUM`.

## Cost

**Cost by team tag, with coverage** (point-in-time price; per unit):
```sql
WITH priced AS (
  SELECT u.record_id, u.usage_unit, u.usage_quantity, u.custom_tags['team'] AS team,
         p.pricing.effective_list.default AS rate, p.currency_code
  FROM system.billing.usage u
  LEFT JOIN system.billing.list_prices p
    ON u.sku_name = p.sku_name
   AND u.usage_end_time >= p.price_start_time
   AND (p.price_end_time IS NULL OR u.usage_end_time < p.price_end_time)
  WHERE u.usage_date >= current_date() - INTERVAL 30 DAYS
)
SELECT usage_unit, coalesce(team, '(untagged)') AS team,
       round(sum(usage_quantity * rate), 2)            AS est_list_cost,
       count(DISTINCT CASE WHEN rate IS NULL THEN record_id END) AS unpriced_records,
       count(*) - count(DISTINCT record_id)            AS duplicate_price_matches,
       count(DISTINCT currency_code)                   AS currencies
FROM priced GROUP BY ALL ORDER BY est_list_cost DESC
```
Good: most cost tagged (WAF passes at ≥ 80% of cost tagged, measured in money, not records). Serverless attribution comes from budget (usage) policies; classic from custom tags.

**Serverless share where serverless is a choice**, and **jobs running on all-purpose clusters** (both from WAF's `cost_compute_mix.sql`):
```sql
-- in the priced CTE, add:
  COALESCE(u.product_features.is_serverless, false)
    OR u.billing_origin_product IN ('MODEL_SERVING','LAKEBASE','APPS','VECTOR_SEARCH','AI_GATEWAY','GENIE',
       'AGENT_EVALUATION','DATA_CLASSIFICATION','LAKEHOUSE_MONITORING','PREDICTIVE_OPTIMIZATION',
       'SHARED_SERVERLESS_COMPUTE')                                         AS is_serverless,
  u.billing_origin_product IN ('JOBS','ALL_PURPOSE','INTERACTIVE','SQL','DLT') AS serverless_is_a_choice,
  u.billing_origin_product = 'ALL_PURPOSE'
    AND NOT COALESCE(u.product_features.is_serverless, false)               AS is_all_purpose,
  u.usage_metadata.job_id IS NOT NULL                                       AS attributed_to_job
-- then: serverless share = cost(serverless AND choice) / cost(choice)          (WAF: pass ≥ 0.8)
--       job cost on all-purpose = cost(is_all_purpose AND attributed_to_job)   (should be ~0: use job compute)
```

**Untagged classic clusters (gap hunt)** (starter-journey):
```sql
SELECT workspace_id, sku_name, usage_metadata.cluster_id, SUM(usage_quantity) AS total_dbus
FROM system.billing.usage
WHERE usage_date >= current_date() - INTERVAL 30 DAYS
  AND custom_tags['team'] IS NULL AND usage_metadata.cluster_id IS NOT NULL
GROUP BY ALL ORDER BY total_dbus DESC
```

## Compute configuration (latest row, then lifecycle filter)

```sql
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY workspace_id, cluster_id ORDER BY change_time DESC) AS recency
  FROM system.compute.clusters
),
latest AS (SELECT * FROM ranked WHERE recency = 1 AND delete_time IS NULL)   -- filter AFTER ranking
SELECT
  count(*)                                                          AS live_clusters,
  avg(CASE WHEN COALESCE(auto_termination_minutes, 0) > 0 THEN 1 ELSE 0 END) AS auto_terminate_share,
  avg(CASE WHEN policy_id IS NOT NULL THEN 1 ELSE 0 END)            AS policy_share,
  avg(CASE WHEN min_autoscale_workers IS NOT NULL
            AND max_autoscale_workers > min_autoscale_workers THEN 1 ELSE 0 END) AS autoscaling_share,
  count_if(size(filter(COALESCE(init_scripts, array()),
                       s -> lower(s) RLIKE '^(dbfs:/|/dbfs/)')) > 0)  AS clusters_with_dbfs_init_scripts,
  collect_set(data_security_mode)                                   AS access_modes
FROM latest
```
WAF's bands: auto-termination pass = 100% (partial ≥ 70%); policies ≥ 90%; runtime (DBR major ≥ 14) ≥ 90%; UC access modes 100%; DBFS init scripts 0.
Job clusters are deleted after each run, so "live" job clusters are rare: assess job compute from run timelines instead.

**SQL warehouses** (same pattern over `system.compute.warehouses`): `COALESCE(auto_stop_minutes, 0) > 0`, `max_clusters > min_clusters`, `warehouse_type = 'SERVERLESS'`.

## Jobs and reliability

```sql
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY workspace_id, job_id ORDER BY change_time DESC) AS recency
  FROM system.lakeflow.jobs
),
latest AS (SELECT * FROM ranked WHERE recency = 1 AND delete_time IS NULL)
SELECT
  count(*)                                                        AS jobs,
  try_divide(count_if(timeout_seconds > 0), count_if(timeout_seconds IS NOT NULL)) AS timeout_share,  -- WAF pass ≥ 0.8; try_divide: 0 known -> NULL, not an ANSI error
  count_if(size(COALESCE(health_rules, array())) > 0)             AS jobs_with_health_rules,
  count_if(trigger.continuous.enabled)                            AS continuous_jobs,          -- cost: always-on
  count_if(deployment.kind = 'BUNDLE')                            AS bundle_deployed_jobs,     -- IaC signal
  count_if(run_as LIKE '%@%')                                     AS jobs_running_as_a_person  -- should be SPs
FROM latest
```
For run durations, derive them from period endpoints in `lakeflow.job_task_run_timeline` (`max(period_end_time) - min(period_start_time)` per task run). WAF found stated durations written as 0, and summing period rows triple-counts.

## Governance and security

**Audit freshness** (`system.access.audit`):
```sql
SELECT count(*) AS events, datediff(current_date(), max(event_date)) AS days_since_last_event,
       count_if(service_name = 'unityCatalog') AS uc_events
FROM system.access.audit WHERE event_date >= current_date() - INTERVAL 30 DAYS
```
WAF: pass if events exist and the last one is ≤ 2 days old. Password `login` actions in audit are a fail (SSO/OAuth expected).

**From `information_schema`** (remember it's privilege-filtered):
- share of tables in Delta/Iceberg (open formats; WAF pass ≥ 0.95);
- share of tables with comments (discoverability; pass ≥ 0.8), which is also "Genie fuel";
- managed vs external share (pass ≥ 0.8 managed);
- managed tables stored on `dbfs:/` (should be 0);
- tags and column masks / row filters present (`column_tags`, `column_masks`, `row_filters`).

**Lineage coverage:** tables that appear in `system.access.table_lineage` ÷ tables (WAF pass ≥ 0.5).

## Things you can't check from system tables (ask, and record the answer with an owner and an expiry)

Workspace settings (token lifetime, IP access lists, legacy features), PAT inventory, audit-log delivery, DR rehearsals, budget policies' existence, CMK. WAF collects these with an admin script, and treats every answer as expiring evidence: an attestation fills a gap but never overrides a measurement.

## How to present the results

- **Every share with its denominator and coverage:** "82% of list cost is tagged (of the 97% of usage records we could price)".
- **Ranges when data is missing:** "between 61 and 78 depending on the 9 controls we couldn't measure".
- **Name the resources behind each gap:** "these 14 all-purpose clusters have no auto-termination; the top 3 cost $X last month".
- **Say "list price":** negotiated rates are in the contract, not in `list_prices`.
