# databricks-waf: a Well-Architected assessment built on system tables

**Repo:** `databricks-solutions/databricks-waf` @ `e765461` (app 0.1.0 Alpha). A Databricks App (Node/Express/AppKit + React) with Lakebase storage, deployed by DAB.
**How I studied it:** a deep-read (unit suite run: 6,937 tests passed, 54 skipped), with key SQL claims checked at source. I reproduced two of its SQL lessons on Spark ([price joins](../case-studies/08-price-join-containment-vs-point-in-time.md), [SCD2 filter-before-rank](../case-studies/evidence/scd_filter_before_rank.py)) and its NULL fix is in [case 02](../case-studies/02-null-semantics-in-quarantine-predicates.md). The raw report is in [`appendix/deep-read-reports/databricks-waf.md`](../appendix/deep-read-reports/databricks-waf.md).

**Why it matters for the interview:** it is the best SQL-over-system-tables codebase in the set, written by people who measured their own mistakes and left the numbers in the comments. Its design principle is the one I'd defend hardest in any customer engagement: **"not measured never becomes pass."**

## 1. What it is, for a customer

Architecture reviews usually end as a slide deck with a score, and nobody can later say which resource caused a gap or whether the fix worked. This app runs **inside the customer's workspace**, assesses the estate against the seven Well-Architected pillars (184 controls), and keeps a chain from **requirement → evidence → affected resource → action → later verification**.

- **Evidence:** Unity Catalog **system tables** (billing, audit, compute, Lakeflow jobs and pipelines, query history, lineage, `information_schema`) through the customer's SQL warehouse, plus a few read-only REST APIs.
- **Identity:** every read runs **as the signed-in user (OBO)**, never as the app's service principal, so nobody sees the estate "through admin eyes".
- **Humans fill gaps, never overrule data:** anything the platform can't answer becomes an owned question with an evidence link and an expiry date. An attestation may fill an `unmeasurable` gap but never overturn a measurement.
- **Output:** a score **with error bars** (`[low, high]`), gaps tied to named clusters, jobs and tables, and an improvement plan verified by the next scan. Reports are frozen with SHA-256 digests.

## 2. How it executes (one assessment run)

1. `POST /api/scan` → authorise (SCIM direct group membership, deny by default) → build credentials from `x-forwarded-access-token`, **throwing** rather than falling back to the app SP.
2. Open a **durable run** (lease, heartbeat, checkpoints, idempotency key); single-flight lock.
3. Plan the signals the requested controls need → collect: **workspace directory first** (live, same-region workspace ids that every other statement filters on), then ~40 SQL statements **sequentially** through a budgeted scheduler, then DESCRIBE samples, then REST.
4. Statements go through the Statement Execution API directly (INLINE/JSON_ARRAY, 20 MiB byte limit, typed parameters, `query_tags`), polled every second, **cancelled on the warehouse** after 10 minutes, with result chunks followed.
5. Resolve 184 controls with pure functions → apply applicability decisions → score (severity-weighted; `unmeasurable` gets no credit and widens the range).
6. Persist; mark improvement actions verified or failing; open a human review; publish frozen monthly bytes.

## 3. Patterns worth stealing

| Pattern | Code shape | Lesson |
|---|---|---|
| **Truncation throws** | "the rows it did return are part of the answer rather than the answer" | A partial result must never be scored as a complete one |
| **Five outcomes; `unmeasurable` excluded, not zero** | `CREDIT.unmeasurable = null`; range = all-unknowns-fail … all-unknowns-pass | Report the error bars. Coverage is part of the answer |
| **Abstain when unknowns could flip the verdict** | Compute the band with unknowns counted as "manual"; if the band changes, return `unmeasurable` | A sensitivity test against missing data |
| **Tri-state unset settings** | Each key declares whether "unset" means enforcement (fail), permissive (fail) or unknown | Avoids false fails on untouched defaults |
| **Cross-check a privilege-filtered read** | 0 tables in `information_schema` + lineage activity = "unreadable", not "empty estate" | `information_schema` is filtered by your grants |
| **SCD2: rank first, then filter the lifecycle column** | `ROW_NUMBER() … ORDER BY change_time DESC` in one CTE; `recency = 1 AND delete_time IS NULL` outside | Filtering first returned **6,136,941 "live" clusters where 135,177 existed (45×)**; jobs 5×. Now enforced by a static checker (`history.ts`) |
| **Point-in-time price join + coverage columns** | `usage_end_time` within `[price_start, price_end)`, LEFT JOIN, `duplicate_price_matches`, `unpriced_records`, per `usage_unit` | [Case 08](../case-studies/08-price-join-containment-vs-point-in-time.md) |
| **CASE for NULL-safe exclusion** | `CASE WHEN tag = 'x' OR … THEN 1 ELSE 0 END AS is_self … WHERE is_self = 0` | `AND NOT (…)` returned **0 of 6,969** statements when the tag was NULL ([case 02](../case-studies/02-null-semantics-in-quarantine-predicates.md)) |
| **Tag your own queries** | `query_tags` (as an array: a map is silently recorded as `tags_invalid`) + a comment marker | The app measured itself at 51.8% of one lab workspace's query time |
| **Budgets instead of trust** | 250 SQL statements, concurrency 2 on a shared warehouse, 45-min wall clock, AIMD limiter (halve on throttle, +1 after 5 successes), jittered retries only where the layer below doesn't retry | Avoids 3×3 = 9× retry amplification; a scan that runs out of budget is *partial*, not an error |
| **Lossless re-bucketing of truncated slices** | `WHERE pmod(hash(key), 4k) = i` refines `pmod(hash(key), k)` and never splits a GROUP BY group | Scale past the 25 MiB inline cap |
| **Population before LIMIT** | `count(*) OVER () AS population` | A truncated result is distinguishable from a complete one |
| **Idempotent retry vs fresh repair** | key = `job-{id}/run-{run}/repair-{n}` | Retries resume the same run; a human repair starts over |
| **Deploy verification by a second plan that must be all `skip`** | `isIdempotent(afterPlan)` | Proves the deploy converged |

## 4. What I found (status-tagged)

The repo is candid about its own bugs; the deep-read found a few more. The ones worth knowing:

| # | Finding | Status |
|---|---|---|
| 1 | SCP-04-05 (managed tables on DBFS root) skips the visibility cross-check: privilege-filtered `information_schema` with 0 visible tables returns `not-applicable`, and visible-subset results claim "every managed table" | CONFIRMED (deep-read) |
| 2 | IU-02-02 passes with the reason "This metastore consumes shared data" when there are recipients but **zero providers** | CONFIRMED (deep-read) |
| 3 | `serving_model_entities.sql` filters `endpoint_delete_time IS NULL` next to the ranking window, the very shape `history.ts` forbids. It evades the checker because the regex matches `delete_time` only as a whole word | SUSPECTED (deep-read) |
| 4 | CO-01-08 (idle clusters) averages **driver** samples too; idle drivers push clusters under the 5% CPU threshold (the job-utilisation statement excludes drivers for exactly this reason) | CONFIRMED (deep-read); false-fail risk |
| 5 | Two "use UC managed tables" controls use different denominators, so the same estate scores differently in two pillars | CONFIRMED (deep-read) |
| 6 | One-directional controls (can only pass-or-unmeasurable, or fail-or-unmeasurable) are excluded exactly when they'd go the other way: a "missing not at random" bias. The range partly discloses it | CONFIRMED (by design) |
| 7 | A resumed run never retries a transient `unmeasurable`: checkpoints store it and collectors skip it | CONFIRMED (deep-read) |
| 8 | Money is at **list price** (`pricing.effective_list.default`); negotiated prices aren't used | CONFIRMED |

## 5. How it scales

- **Many workspaces:** one install reads system tables for every live workspace in its region. `compute.*` and `lakeflow.*` are regional; `billing.usage` and `workspaces_latest` are global. A multi-region account needs one install per region.
- **Large system tables:** the inline result cap is 25 MiB, so `byte_limit` is 20 MiB (overflow becomes a `truncated` flag, then re-bucketing). Scale fixtures showed `compute_cluster_inventory` at 153% of the cap at 150k clusters. `information_schema.columns` took **about an hour to compile** on a 600k-relation estate, so it was moved to an optional enrichment signal.
- **Customer impact:** sequential statements at concurrency 2 on a shared warehouse, 10-minute cancel, capped query-history windows (scan time grew linearly with the window), STANDARD serverless performance for the scheduled job (~⅓ the DBUs of performance-optimised).

## 6. How I'd explain it

- **Executive:** "A continuous architecture review of your Databricks estate that runs in your own account. Every score shows how much was actually measured, each gap names the job, cluster or table responsible, and fixes are confirmed by the next scan, not by someone ticking a box. A posture score with error bars, plus a remediation backlog that verifies itself."
- **Platform engineer:** "DAB install; binds your SQL warehouse and a Lakebase database. Reads run as whoever clicks Run, with narrow OBO scopes and ~40 parameterised statements against `system.*`, tagged in query history, cancelled after 10 minutes. Settings the app can't reach are collected by an admin script and imported."
- **Internal stakeholder:** "A reference for 'system tables as the assessment substrate', with product feedback baked in: Apps can't be granted settings/authentication/networking scopes (53 of 70 security requirements need an admin script); `storage.table_metrics_history` was empty everywhere measured; `lakeflow.jobs` columns are null before December 2025; run-timeline stated durations are 0."

## 7. Interview angles

1. **"How would you check a customer's workspace follows best practices on cost?"** Point-in-time price join; serverless share of spend where serverless is a choice; job cost landing on all-purpose; tagged share; Photon share. Then latest-row cluster config for auto-termination, autoscaling, policies and runtimes. Guard duplicates, currencies, unpriced SKUs; say "list price". See [`cheatsheets/system-tables-best-practice-checks.md`](../cheatsheets/system-tables-best-practice-checks.md).
2. **"What's the worst bug they found?"** SCD2 filter-before-rank: 45× clusters. Lesson: rank first, filter the lifecycle column on the chosen row; a predicate is only safe inside the windowed query if it's decided by the partition columns.
3. **"How do you guarantee 'not measured never becomes pass'?"** Four layers: collector (no answer → unmeasurable; truncation throws), resolver helpers, scoring (no credit, wider range), attestations only fill gaps. Then name the exceptions (findings 1 and 2), because a principle is only as good as its leaks.
4. **"Why OBO rather than the app's SP?"** Least privilege and honest findings. The cost: identity-dependent results, so trends need the same actor.

## 8. AI-stewardship angle: where an assistant would go wrong on system tables

- Write `WHERE delete_time IS NULL` next to `ROW_NUMBER()` (the 45× bug), or bound a history table by `change_time >= now() - 30d` "to be efficient", which drops long-lived objects.
- Join `billing.usage` to `list_prices` on `sku_name` alone or by date; add DBUs + DSUs + GB; ignore `currency_code`; trust `product_features.is_serverless` alone (false on MODEL_SERVING and LAKEBASE: **a $12,770 understatement on a $16,190 bill**); classify all-purpose by `sku_name LIKE '%ALL_PURPOSE%'` (catches serverless Apps SKUs).
- Sum period rows in timelines (3× counts), trust `run_duration_seconds` (written as 0).
- `AND NOT (tag = 'x' OR …)` with a NULL tag; `sum()` over no rows is NULL, not 0.
- `current_date() - make_dt_interval(7)` gives **8** calendar buckets; `current_date()` depends on the session time zone.
- Treat zero rows from privilege-filtered `information_schema` as an empty estate.

**How to evaluate its output:** demand every share state its denominator and its empty-case behaviour; run the query on an empty window and on an identity with no grants; compare row counts with a known object count (that is how the authors caught 45×); read the plan for repeated scans.
