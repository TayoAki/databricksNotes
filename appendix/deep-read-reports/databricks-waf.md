> **Provenance.** Deep-read of `databricks-solutions/databricks-waf` @ `e765461`, written by a research sub-agent during this study and kept verbatim, apart from local paths normalised to `<clone-root>/`. Its CONFIRMED / SUSPECTED labels are the agent's. The claims I re-verified myself, and how, are listed in [`README.md`](README.md); anything not listed there I have not independently checked.

# databricks-waf — deep-read technical report

Repo: `github.com/databricks-solutions/databricks-waf`, shallow clone of `main` at `e765461`
("Fix unfinished assessment continuation and custom scan questions (#26)"), app version 0.1.0 Alpha
(`app/package.json:3`, `CHANGELOG.md:6`). Read-only clone at `<clone-root>/databricks-waf`.

Path abbreviations used throughout:

| Prefix | Means |
| --- | --- |
| `srv/` | `app/server/` |
| `R/` | `app/server/resolve/resolvers/` |
| `S/` | `app/config/statements/` (the 40 assessment SQL files) |
| `T/` | `app/config/topology/` (8 topology SQL files) |
| `C/` | `app/config/controls/` (the catalogue YAML, one file per pillar) |
| `cli/` | `app/client/src/` |

Unit tests were run (in a scratchpad copy, so the clone was not touched): `npm ci` took 24 s, and
`vitest run` finished in 105.8 s. **403 of 404 test files passed and 1 was skipped. 6,937 tests passed and 54 were skipped.** The skips are
the live-Lakebase suites guarded by `describe.skipIf(!bound)` (`srv/store/postgres.live.test.ts:314`).

---

## 1. What it is (customer framing)

Architecture reviews usually end as a slide deck with a score. After that, nobody can say which workspace resource
caused a gap, what to change, or whether the fix worked. `databricks-waf` is a Databricks App that the customer installs
in their own workspace. It assesses the estate against the seven pillars of the Databricks Well-Architected
Framework and keeps an unbroken chain from **requirement → evidence → affected resource → action → later
verification** (`README.md:14`).

It has two sources of evidence. The first is **Unity Catalog system tables**: billing, audit, compute, Lakeflow jobs and
pipelines, query history, lineage and `information_schema`, read through the customer's SQL warehouse. The second is a
few **read-only REST APIs**. Every read runs as the signed-in user, never as the app's service principal. Anything the
platform cannot answer becomes an explicit human question. The question has an owner, rests on an evidence link and
expires on a review cadence. When every pillar has been reviewed, the result is sealed into an immutable report. Every
record lives in the customer's own Lakebase (Postgres).

The outcome for a CIO or platform owner is a defensible posture score that carries its own error bars. Low coverage is
never hidden behind a good score. The biggest gaps are each tied to named clusters, jobs, warehouses or tables. An
improvement plan with owners is verified automatically by the next scan. The design principle the authors defend
hardest is that **not measured never becomes pass** (`README.md:29`).

---

## 2. Architecture map

```
 Browser (React 19, react-router, AppKit UI)                     Lakeflow Job (optional, PAUSED)
 cli/pages/*  ── fetch /api/* ──┐                                 app/schedule/trigger.py (notebook)
                                │ Databricks Apps proxy           readiness task ─┐  assess task (3 retries)
                                │ (OAuth; mints OBO token;        client-credentials OAuth for a
                                │  x-forwarded-access-token,      dedicated SP → POST /api/scan/scheduled
                                │  x-forwarded-email)             with idempotency-key job-{id}/run-{run}/repair-{n}
                                ▼                                              │
 ┌──────────────────── Node 22 / Express 5 / @databricks/appkit ──────────────▼───────────────────┐
 │ srv/server.ts  createApp({plugins:[analytics(), server()]}) + registerApi(...)                 │
 │ srv/api/*routes.ts  ── authorize/group.ts (SCIM /Me direct groups)  ── audit/record.ts         │
 │        │                                                                                       │
 │        ▼                                                                                       │
 │ run/runs.ts (durable run: open→claim lease→resume checkpoints→collect→finish)                  │
 │ scan/runner.ts (single-flight lock) → scan/scan.ts runScan()                                   │
 │   plan: registry.signalsFor(controls)+preconditions  → collect/collection.ts                   │
 │   scheduler (scan/scheduler.ts): per-surface budget, AIMD limiter, retry/backoff, wall clock   │
 │   ├─ SqlCollector  (collect/sql/collector.ts) ─ StatementExecutor ─► POST /api/2.0/sql/statements
 │   ├─ DescribeCollector (DESCRIBE DETAIL per sampled table)        ─► same warehouse           │
 │   ├─ PredictiveOptimizationCollector (DESCRIBE CATALOG EXTENDED)  ─► same warehouse           │
 │   ├─ RestCollector (SDK WorkspaceClient, user token) ─► workspace-conf, token-mgmt,           │
 │   │                                                     serving-endpoints, vector-search      │
 │   └─ CloudCollector (off unless a UC service credential is named)                             │
 │   + import/signals.ts merged(): admin-collected evidence fills only unmeasurable gaps          │
 │   resolve/resolver.ts resolveControl() × 184  (applicability → resolver → attestation)        │
 │   apply/apply.ts (applicability decisions) → score/score.ts (severity-weighted, ranges)       │
 │        │                                                                                       │
 │        ▼                                                                                       │
 │ store/postgres.ts  ─► Lakebase (schema `waf`, created & owned by the app SP on boot)           │
 │   scans, attestations, decisions, runs, run_checkpoints, assessment_reviews, pillar_reviews,   │
 │   assessment_results, month_publications, audit_events, … (28 tables)                          │
 └────────────────────────────────────────────────────────────────────────────────────────────────┘
 Deploy: app/databricks.yml + resources/scheduled-scan.yml (DAB) ← scripts/lifecycle.mjs
```

| Area | Path | Role |
| --- | --- | --- |
| Entry point | `srv/server.ts:86-399` | Loads the catalogue, guidance and resolver registry. Opens the stores. Builds per-scan collectors in `collectorsFor` (`:365-390`). Serves a fallback page on a startup failure (`:454-460`). |
| HTTP API | `srv/api/routes.ts` (3,419 lines) + 17 `*-routes.ts` | 114 route registrations (`/api/scan`, `/api/scan/scheduled`, `/api/scan/readiness`, `/api/reviews/*`, `/api/months/*/publish`, `/api/evidence/imports`, …). |
| AuthZ | `srv/authorize/group.ts:90-113` | Mutations require direct membership of `WAF_ASSESSOR_GROUP`. Denied by default. |
| Collection | `srv/collect/**` | SQL, describe, PO, REST, cloud and topology collectors. Credentials and estate scope. |
| Resolution | `srv/resolve/**`, `R/*.ts` (20 resolver modules) | Pure functions from signals to `Finding`s. |
| Scoring | `srv/score/score.ts` | Severity-weighted pillar scores, low/high ranges, alias groups. |
| Durable runs | `srv/run/*` | Leases, heartbeats, checkpoints, idempotency keys. |
| Human review | `srv/attest/*`, `srv/review/*`, `C/questions.mjs`, `app/config/guidance/*.yaml` | Questions, attestations with expiry, per-pillar confirm/skip, final result. |
| Publication | `srv/monthly/*`, `srv/export/*`, `srv/records/*` | Frozen monthly bytes, RFC 8785 canonical JSON, SHA-256 digests. |
| Advisor | `srv/advise/*`, `app/config/analyze/*.yaml` | Workload, warehouse, job and serverless advice. Scores nothing. |
| Shared contract | `app/shared/api/contract.ts`, `comparability.ts` | Wire types and the run-comparability rule. |
| Client | `cli/pages/*` (34 page components), `cli/components/*` | Dashboard, Investigate, Findings, Review, Report, Operate, Diagnostics… |
| Config | `C/*.yaml` (184 controls), `S/*.sql`, `app/config/analyze/*.yaml` (advisor thresholds), `app/config/evidence/collect-evidence.py` (admin evidence script) | |
| Deploy | `app/databricks.yml`, `app/app.yaml`, `app/resources/scheduled-scan.yml`, `app/schedule/trigger.py`, `app/scripts/lifecycle.mjs`, `recovery.mjs`, `schedule-principal.mjs` | |
| Checks | `app/scripts/*.mjs|mts|ts` (~160 non-test scripts), `app/scripts/verify.mjs` | Static gates on SQL shape, bounds, docs, licences and bundle drift. |

**`appkit.plugins.json`** is AppKit's generated template manifest, refreshed by `appkit plugin sync --write` (`package.json:30`).
It lists nine plugins: agents, aiSearch, analytics, files, genie, jobs, lakebase, server and serving. Only `analytics` and
`server` are marked `requiredByTemplate`, and those two are the only plugins the app registers (`srv/server.ts:292`).
Lakebase is reached directly through `@databricks/lakebase` (`srv/store/postgres.ts:17`), not through the plugin. The
`analytics` plugin stays registered only for its warehouse-resource handshake. Queries bypass it (see §4, D2).

**Docs map.** `docs/` is a Jekyll site: install, configuration, user-guide, pages, operations, deployment-lifecycle,
scheduled-scans, troubleshooting, contributing, `coverage-ledger.md` (generated) and two design standards. About 65 ADRs
and several `docs/plan/*` and `docs/design/*` files are cited from source comments but are **not in the public repo**.
The README says private history was deliberately withheld (`README.md:257-259`). `scripts/verify.mjs:437-452` switches
off 11 "private evidence" checks when `../docs/plan-status.md` is absent.

---

## 3. How the code executes: one assessment run, end to end

1. **Click "Run assessment".** `cli/components/RunScanDialog.tsx:191` calls `runScan`, which sends `POST /api/scan` (`cli/api/hooks.ts:1949`) to `runScanFor('interactive')`
   (`srv/api/routes.ts:1242`, registered at `:1363`). A scheduled run comes through the other door,
   `POST /api/scan/scheduled` (`:1378`). Same code, different `trigger`.
2. **Resolve what is being asked.** The handler parses pillars and workspaces from the body. It resolves the saved assessment
   definition, whose version fixes the pillars, the workspace scope and the lookback (`routes.ts:1246-1283`). An ad-hoc
   lookback is clamped to 1–365 days, default 30 (`routes.ts:2765-2772`).
3. **Authorize.** `permitted()` (`routes.ts:3118`) calls SCIM `GET /api/2.0/preview/scim/v2/Me` with the forwarded user
   token (`srv/collect/estate-scope.ts:199-227`). It reads direct group memberships and the `x-databricks-org-id`
   header, then calls `requirePermission` (`srv/authorize/group.ts:90-113`). The check denies when memberships are unknown
   and denies non-members. An audit "act" is opened before the change and closed as performed or failed
   (`routes.ts:1317`, `:1350`).
4. **Take the caller's identity, never the app's.** `fromRequest()` builds credentials from the
   `x-forwarded-access-token` header and throws `MissingUserTokenError` instead of falling back to the app's service
   principal (`srv/collect/credentials.ts:87`, `:256-291`). `modeFor` stamps a UUID actor as `service-principal` and an
   email actor as `on-behalf-of-user` (`:157-159`).
5. **Build per-scan collectors.** `collectorsFor` builds a `StatementExecutor` bound to this user's token and the bound
   warehouse. Order matters: SQL, then DESCRIBE, then PO, then REST, then Cloud (`srv/server.ts:365-390`). The warehouse id
   is read per scan (`:409-418`).
6. **Open a durable run.** `startRun` (`routes.ts:1315`, `:2857`) goes through `Runs`: open the row, claim a lease with a
   heartbeat, resume from checkpoints, collect, finish (`srv/run/runs.ts:1-25`, resume at `:178`/`:237`). An
   idempotency key that names a finished run is refused with the prior answer (409 `run-not-joinable`).
7. **Single-flight.** `ScanRunner.start` throws `ScanInProgressError` if another scan is running (`srv/scan/runner.ts:240-242`).
   It loads effective attestations, imported evidence and applicability decisions, then calls `runScan`.
8. **Plan.** `runScan` (`srv/scan/scan.ts:319`) filters controls to the requested pillars. It asks the registry which
   signals their resolvers need, adds precondition signals and closes over collector inputs (`scan.ts:462-468`,
   `srv/resolve/resolver.ts:152-160`, `srv/collect/collection.ts` `withInputs`).
9. **Collect.** `collectSignals` loops over the collectors (`collection.ts:75`) and checkpoints every signal as it
   settles (`:142`, `:221`).
   - `SqlCollector.collect` reads the **workspace directory first**, always (`srv/collect/sql/collector.ts:699`). That
     yields the live, same-region workspace ids that every other statement filters on (`:754-767`). It then runs the
     statements **sequentially** (`:706-731`), each through `scheduler.run` (`srv/scan/scheduler.ts`). Parameters are
     bound as typed markers (`collector.ts:1028-1052`). A statement with a `-- Slice:` header runs once per workspace
     group, and is re-bucketed by hash if the warehouse truncates the result (`:880-958`).
   - `StatementExecutor.query` submits `POST /api/2.0/sql/statements` with `INLINE`/`JSON_ARRAY`, `byte_limit` 20 MiB,
     `wait_timeout` 30 s, `on_wait_timeout: CONTINUE`, typed parameters and `query_tags` (`statements.ts:298-352`).
     It polls every 1 s. After 10 minutes it **cancels on the warehouse** (`:241-244`, `:415-422`). It follows
     `next_chunk_internal_link` for more pages (`:274-296`).
   - Rows are parsed by `S`-specific parsers (`srv/collect/sql/shapes.ts`). An empty snapshot or a zero-row slice
     becomes `unmeasurable`, not a row of zeroes (`collector.ts:835-851`).
   - DESCRIBE collector: `DESCRIBE DETAIL \`c\`.\`s\`.\`t\`` for up to 50 sampled tables. Identifiers are quoted with
     `quoteIdent` (`srv/collect/sql/describe.ts`, `app/scripts/sql-identifiers.mjs:22-27`).
   - REST collector: probes run through an SDK `WorkspaceClient` built with the user's token and `authType:'pat'`, so
     the SDK cannot silently fall back to the app SP (`srv/collect/rest/client.ts:39-54`,
     `srv/collect/rest/probes.ts`).
10. **Merge admin imports.** An imported reading replaces only a signal the app read as `unmeasurable`
    (`srv/import/signals.ts:458-477`, called at `scan.ts:337`).
11. **Resolve 184 controls.** `resolveControl` (`resolver.ts:171-248`) runs applicability preconditions, then the resolver.
    An attestation is consulted **only** if the resolver returned `unmeasurable` (`:222`). The kind of gap and a
    remedy are derived from the platform's refusal (`:231-244`).
12. **Apply decisions and score.** `applyDecisions` (`scan.ts:360`, `srv/apply/apply.ts`) then `scoreFindings`
    (`scan.ts:397`, `srv/score/score.ts:219-267`).
13. **Persist and settle.** `store.save(scan)` writes the `scans` row, with a digest (`runner.ts:312`). `onFinished`
    runs `resolveValidations`, which marks improvement actions verified or failing from this scan, and opens a review of
    the scan (`srv/server.ts:194-227`).
14. **Respond.** An interactive run returns the full presentation (`routes.ts:1320-1330`). A scheduled run returns a small
    summary. A run that read less than it failed to read gets **422 `mostly-unreadable`** (`routes.ts:1336-1343`,
    `underGranted` at `:2961-2963`), so the job fails loudly.
15. **Human review.** The Review page posts answers (`srv/api/review-routes.ts:500`), confirms (`:405`) or skips
    (`:455`) each selected pillar. **There is no finalise endpoint.** The last pillar record produces the
    `AssessmentResult` in one commit (`review-routes.ts:8-9`, `srv/review/review.ts:370-383`,
    `srv/review/postgres-store.ts:118`).
16. **Publish.** `POST /api/months/:month/publish` (`srv/api/publication-routes.ts:937`) freezes JSON and CSV bytes
    with an identity and a SHA-256 digest inside them (`srv/monthly/publication.ts:1-14`). Corrections go through
    `/supersede` (`:1031`). They never edit.

---

## 4. Key design decisions and why (with trade-offs)

**D1. On-behalf-of for every estate read; the app's SP only runs the server and reads its own job.**
Rationale: reading as the app SP would be a privilege escalation, showing any user the estate "through admin eyes"
(`srv/collect/rest/client.ts:3-12`). The only non-user client is `machineClient()`, which is limited to the scheduled
job (`srv/schedule/client.ts:1-7`). *Trade-off:* two people see different estates, so scans by different actors are
**not comparable**. `comparable()` refuses a mismatched actor or execution mode (`app/shared/api/comparability.ts`).
Trends therefore only work for one person or for the scheduled SP.

**D2. Bypass AppKit's `analytics.asUser(req).query` and call the Statement Execution API directly.**
AppKit 0.50's user-scoped proxy was unbound and threw. On top of that, AppKit caches results for an hour and retries
under the scheduler, and both are wrong for a measurement (`srv/collect/sql/statements.ts:3-28`). *Trade-off:* the app
owns polling, cancellation and chunking itself.

**D3. SQL lives in `.sql` files with machine-checked headers** (`-- Signal:`, `-- Rows:`, `-- Slice:`, `-- Benchmark:`,
`-- Feeds:`), loaded by `FileQuerySource` (`srv/collect/sql/queries.ts:114-141`). The files are reviewable as SQL, and
static gates parse them: `check-statement-bounds`, `history.ts` (SCD2 ordering), `grain.ts` and `slices.ts`.

**D4. Five outcomes, and `unmeasurable` is excluded rather than scored** (`srv/resolve/finding.ts:19-44`,
`srv/score/score.ts:73-81`). The score carries a `[low, high]` range: all unknowns fail versus all unknowns pass
(`score.ts:32-48`, `:390-397`). This avoids both a perverse incentive (hiding access to raise the score) and an
arbitrary coverage cut-off, although the UI still suppresses thin pillars (§9 item 21).

**D5. Applicability before evidence, and three kinds of "doesn't count"**: `not-applicable` leaves the denominator,
`satisfied-by-architecture` counts as a pass, `unmeasurable` widens the range (`srv/resolve/applicability.ts:1-12`,
`R/helpers.ts:426-459`). This is the "don't fail a serverless estate for missing cluster policies" rule
(`R/cost.ts:504-538`).

**D6. Account reach by default, narrowed by region.** Some system tables are regional and some are global. The workspace
directory is intersected with a region inferred from serverless SKU suffixes, weighted by DBUs, so every statement
describes the same set of workspaces (`S/workspace_directory.sql:27-94`, `srv/collect/sql/region.ts`). Each signal
declares its `reach` (`collector.ts:219-576`).

**D7. Budgets instead of trust** (`srv/scan/surfaces.ts:98-188`). The SQL surface gets 250 statements at concurrency 2
(shared warehouse) or 4 (dedicated). `sql` and `describe` share one limiter. REST gets 3,000 calls at concurrency 8.
The wall clock is 45 minutes and each statement has a 10-minute deadline. When the budget runs out the scan is *partial*,
not an error (`srv/scan/budget.ts:1-8`).

**D8. Durable, idempotent runs over an unreliable host.** Apps restart, so runs have leases, heartbeats and checkpoints.
The scheduled job reuses the same idempotency key on retries and a new key on repairs (`app/schedule/trigger.py:123-141`).

**D9. A job, not an in-app timer, for scheduling** (`app/resources/scheduled-scan.yml:13-17`). It deploys paused,
`max_concurrent_runs: 1`, with a readiness task that has 0 retries and an assess task with 3 retries
(`scheduled-scan.yml:57-200`).

**D10. Human questions are authored, not templated, and they expire.** Each question states why it is a question
(`asked_because`) and carries a cadence of 365, 180 or 90 days (`C/questions.mjs:1-84`). An attestation can only fill a
gap. It can never overturn a measurement (`resolver.ts:213-224`).

**D11. Lakebase schema created by the app on boot, with no migration framework.** The role with `CAN_CONNECT_AND_CREATE`
must own what it creates. Migrations are idempotent `create … if not exists` plus
`alter table … add column if not exists` on every boot (`srv/store/postgres.ts:7-15`, `:209`, `:870-899`). Late
invariants are added `NOT VALID` (`srv/store/invariants.ts:1-6`). *Trade-off:* this is expand-only. A destructive change
would need real migration tooling.

**D12. Read-only by construction for the REST surface**, with a CI gate (`check:read-only`). The broad `model-serving` and
`vector-search` scopes are accepted only because the narrow scope names were measured to grant nothing
(`app/app.yaml:94-113`).

### Test strategy and the invariants it protects (`app/tests`, co-located `*.test.ts`)

There are 404 test files: 353 `.test.ts` and 51 `.test.tsx`, about 48 of which test `app/scripts/`. The top-level `app/tests/`
holds three: `applicability.test.ts` ("a good architectural decision must never read as a failure",
`app/tests/applicability.test.ts:1-3`), `scheduler.test.ts` and `harvest-waf-docs.test.ts`. The patterns worth naming:

- **Counter-example-first static rules.** `history.test.ts` rebuilds the shipped SCD2 bug and requires the rule to catch
  it. It also pins the legitimate shapes that must *not* fire (`srv/collect/sql/history.test.ts:1-14`). `grain.test.ts`
  does the same for grain.
- **Empty-estate tests.** Every resolver is fed its collector's real parse of zero rows, which must not be a fabricated
  pass or fail (`srv/resolve/resolvers/empty.test.ts:1-16`, using `emptySqlSignal`, `collector.ts:637-646`).
- **Vocabulary agreement.** The serverless product list must be identical in three statements
  (`srv/collect/sql/billing-semantics.test.ts`).
- **Scale fixtures.** Statements run at declared target cardinality against the 25 MiB inline cap. For example,
  `serverless_job_readiness` hits 110% of the cap at 100k jobs (`srv/collect/sql/scale.test.ts:1-14`).
- **No-leak tests** plant secrets in API bodies and assert that the admin script's projection drops them
  (`srv/evidence/no-leak.test.ts`).
- **Isolation.** No read from one assessment returns another's data (`srv/api/assessment-isolation.test.ts`).
- **Durability.** A killed run resumes from checkpoints and a duplicate trigger is refused (`srv/run/runs.test.ts`).

The invariants the authors clearly care about most: no silent pass, correct denominators and populations, run
comparability, identity honesty, bounded load on the customer's warehouse, and records that cannot be rewritten.

---

## 5. Databricks platform features used, and how

| Feature | How it is used | Where |
| --- | --- | --- |
| **System tables** | `billing.usage`, `billing.list_prices`, `access.audit`, `access.table_lineage`, `access.workspaces_latest`, `access.assistant_events`, `compute.clusters`, `compute.warehouses`, `compute.warehouse_events`, `compute.node_timeline`, `lakeflow.jobs`, `lakeflow.job_run_timeline`, `lakeflow.job_task_run_timeline`, `lakeflow.pipelines`, `lakeflow.pipeline_update_timeline`, `query.history`, `storage.predictive_optimization_operations_history`, `storage.table_metrics_history`, `serving.served_entities`, `serving.endpoint_usage`, `mlflow.runs_latest`, `mlflow.experiments_latest`, `data_quality_monitoring.table_results`, `data_classification.results`, and 20+ `information_schema` views (tables, columns, catalogs, shares, recipients, providers, connections, volumes, routines, column_masks, row_filters, table_tags, column_tags, metastores, metastore_privileges, external_locations, storage_credentials, …) | `S/*.sql`, `T/*.sql` |
| **Databricks Apps** | OBO: the proxy injects `x-forwarded-access-token` and `x-forwarded-email` (`srv/collect/credentials.ts:87-101`). `user_api_scopes` = `sql.statement-execution`, `sql.warehouses:read`, `catalog.{catalogs,schemas,tables}:read`, `model-serving`, `vector-search`, `sql.query-history:read` (`app/databricks.yml:115-124`, `app/app.yaml:84-126`). Resource bindings `sql-warehouse` (CAN_USE) and `postgres` (CAN_CONNECT_AND_CREATE) via `valueFrom` (`databricks.yml:162-177`). | |
| **AppKit** | `createApp({plugins:[analytics(), server()]})`, `appkit.server.extend(registerApi)` (`srv/server.ts:291-295`). `appkit-ui` React components. `sql.string`/`sql.int` typed parameter markers (`collector.ts:14`, `:49-52`). | |
| **Lakebase (Postgres)** | `createLakebasePool` with a workspace client, so the Postgres role is the app SP (`srv/store/postgres.ts:159-203`). Schema `waf` (overridable by `WAF_PG_SCHEMA`, validated by `/^[a-z_][a-z0-9_]{0,61}$/`, `:74-83`). 28 tables. Transactions via a dedicated pooled client (`:175-200`). | |
| **SQL warehouse / Statement Execution API** | `POST /api/2.0/sql/statements` with INLINE + JSON_ARRAY + `byte_limit` + `wait_timeout` + typed `parameters` + `query_tags`. Poll `GET /statements/{id}`, cancel `POST …/cancel`, chunks via `next_chunk_internal_link` (`statements.ts:227-422`). | |
| **Query History API** | `GET /api/2.0/sql/history/queries/{id}?include_plans=true` for operator plans, used by the advisor (`srv/collect/sql/plans/fetch.ts:112`). | |
| **DABs** | `bundle: waf-assessment`. Variables: warehouse, Lakebase branch and db, assessor group, schedule SP. `include: resources/*.yml`. Target `customer` with no ids (overrides go in the git-ignored `.databricks/bundle/customer/variable-overrides.json`) (`databricks.yml:16-185`). `config.env` **replaces** app.yaml's env, so both lists must match (`databricks.yml:126-158`). | |
| **Lakeflow Jobs** | Serverless notebook tasks, `performance_target` STANDARD by default. Quartz `0 0 6 ? * MON` UTC, `pause_status: PAUSED`. `permissions: CAN_MANAGE_RUN` granted to the app SP from the job file to dodge a CLI drift bug (`resources/scheduled-scan.yml:33-63`). `{{job.run_id}}`/`{{job.repair_count}}` substitution for idempotency (`:169-171`). | |
| **Service principals / OAuth** | The scheduled SP gets a client-credentials token from `/oidc/v1/token` (`scope=all-apis`). The Apps proxy then **re-mints** an OBO token limited to the app's declared scopes (`app/schedule/trigger.py:185-212`). PATs, runtime tokens and dbutils tokens were refused by the proxy (`trigger.py:22-26`). | |
| **Unity Catalog grants** | Preflight probes `SELECT 1 FROM <t> WHERE false` per table (`srv/define/preflight.ts:165-167`). The scheduled-SP tool derives `USE CATALOG system`, `USE SCHEMA`+`SELECT` per system schema, and optional `BROWSE` on customer catalogs (`app/scripts/schedule-principal.mjs:51-80`, `:330-334`). | |
| **UC service credentials** | Optional: `POST /api/2.1/unity-catalog/temporary-service-credentials` to vend cloud keys for storage-bill reads (`credentials.ts:192-210`). | |
| **REST (control plane)** | `GET /api/2.0/workspace-conf?keys=…` (15 flags + `maxTokenLifetimeDays`), `token-management/tokens`, `serving-endpoints`, `vector-search/endpoints` (`srv/collect/rest/probes.ts:71-202`). Only the last two scopes are grantable to Apps. The first two are always refused live and are filled by admin import. | |

---

## 6. The best-practice checklist

### 6.1 How outcomes are decided (applies to every row)

- **Helper semantics.** `bandOutcome(share, {pass, partial})` returns `unmeasurable` if share is undefined, `pass` if
  share ≥ pass, `partial` if share ≥ partial, else `fail` (`R/helpers.ts:317-322`). Bands come from the catalogue's
  `thresholds.pass_share` / `partial_share` and override code defaults (`R/helpers.ts:325-335`).
- A required signal that is missing or unmeasurable short-circuits to `unmeasurable` with the collector's reason
  (`R/helpers.ts:33-67`, `:114-130`).
- An empty catalogue read (`information_schema` is **privilege-filtered**) becomes `unmeasurable` with a `BROWSE` remedy,
  not `not-applicable`, whenever un-filtered lineage shows activity (`R/visibility.ts:79-110`).
- Monetary shares are refused, returning `unmeasurable` (attestation kind), when a usage row matched more than one list
  price, when there is more than one currency, or when more than 1% of the worst-covered usage unit is unpriced
  (`R/helpers.ts:353-390`).
- Pillar score = Σ(weight × credit) / Σ weight over scored outcomes. Weights: critical 10, high 6, medium 3, low 1,
  info 0.5. Credit: pass/SbA 1, partial 0.5, fail 0 (`srv/score/score.ts:54-81`). Overall = mean of pillar scores
  (`:245-258`).

Legend: **Measured** = read live by an install. **Import** = the resolver exists but the scope cannot be granted to Apps,
so it runs only on admin-collected evidence (`app/config/evidence/collect-evidence.py`). **Q-practice** = attestation
only. `C:n` = line of the control in that pillar's catalogue YAML. "SbA" = satisfied-by-architecture. "N/A" =
not-applicable. "UM" = unmeasurable.

### 6.2 Cost optimization (`C/cost-optimization.yaml`, 22 entries: 17 measured, 5 practice)

| Pillar | Check / requirement | Evidence source | Pass/fail logic or threshold | `path:line` |
| --- | --- | --- | --- | --- |
| CO | CO-01-01 Performance-optimized formats (alias `open-table-formats` with REL-01-01, DG-03-03, IU-02-01; high) | `information_schema.tables` (`S/uc_asset_census.sql`) | Delta+Iceberg ÷ (tables − views − metric views − foreign). Pass ≥ 0.95, partial ≥ 0.70. 0 tables → visibility cross-check → UM or N/A | `R/cost.ts:135-178`, C:15 |
| CO | CO-01-02 Use job compute | `billing.usage` ⋈ `list_prices` (`S/cost_compute_mix.sql`) | 1 − (job-attributed all-purpose cost ÷ "choice" cost over JOBS/ALL_PURPOSE/INTERACTIVE/SQL/DLT). Pass ≥ 0.98, partial ≥ 0.85. Price barrier → UM | `R/cost.ts:188-226`, C:38 |
| CO | CO-01-03 SQL warehouse for SQL | `query.history` ⋈ `compute.clusters` (`S/workload_sql_paths.sql`) | Interactive statements (no job or pipeline source) on WAREHOUSE ÷ interactive. Pass ≥ 0.9, partial ≥ 0.6. App's own statements excluded. 0 statements → UM | `R/cost.ts:626-666`, C:63 |
| CO | CO-01-04 Up-to-date runtimes | `compute.clusters` latest live row (`S/compute_cluster_inventory.sql`) | All-purpose (UI/API) with DBR major ≥ 14. Pass ≥ 0.9, partial ≥ 0.6. Unparseable runtime = stale. None → SbA. Precondition "0 classic clusters billed" → N/A | `R/cost.ts:235-261`, C:93 |
| CO | CO-01-05 GPUs only where needed | `compute.clusters` worker node-type regex | No GPU nodes → pass. Any → **partial** (never fail) | `R/cost.ts:271-304`, C:131 |
| CO | CO-01-06 Serverless (alias `serverless-adoption` with PE-02-01, REL-01-06, IU-03-02; high) | `cost_compute_mix` | Serverless cost ÷ choice cost. Pass ≥ 0.8, partial ≥ 0.3. Choice cost 0 → N/A | `R/cost.ts:316-359`, C:165 |
| CO | CO-01-08 Efficient compute size | `compute.node_timeline` (`S/node_utilization.sql`) | Any cluster with ≥ 60 samples and avg (user+system) CPU < 5% → **fail**. Otherwise UM (**never passes**) | `R/cluster-sizing.ts:112`, C:223 |
| CO | CO-01-10 Photon (alias `photon` with PE-03-08) | `cost_compute_mix` | Serverless ≥ 95% of Photon-eligible spend → SbA. Else Photon-SKU cost ÷ eligible. Pass ≥ 0.7, partial ≥ 0.3 | `R/cost.ts:368-411`, C:274 |
| CO | CO-02-01 Autoscaling (alias `compute-autoscaling` with REL-03-01) | `compute.clusters` + `compute.warehouses` | (autoscaling all-purpose + serverless/scale-out warehouses) ÷ total. Pass ≥ 0.8, partial ≥ 0.4. None → SbA | `R/cost.ts:420-453`, C:310 |
| CO | CO-02-02 Auto termination (high) | clusters + warehouses | `auto_termination_minutes>0` / `auto_stop_minutes>0`. Pass = 1.0, partial ≥ 0.7 | `R/cost.ts:456-502`, C:350 |
| CO | CO-02-03 Compute policies (high) | `compute.clusters.policy_id` | All-purpose with policy. Pass ≥ 0.9, partial ≥ 0.5. None → SbA | `R/cost.ts:513-538`, C:387 |
| CO | CO-03-01 Tagging for attribution (high) | `billing.usage.custom_tags` ⋈ `list_prices` (`S/cost_attribution_coverage.sql`) | Custom-tagged cost ÷ list cost. Pass ≥ 0.8, partial ≥ 0.3. Identifier-attributable share reported alongside | `R/cost.ts:576-611`, C:430 |
| CO | CO-03-05 Storage volume & growth | `storage.table_metrics_history` (empty everywhere measured) or DESCRIBE DETAIL sample; optional cloud bill | Bytes and files reported. Compacted-file share pass ≥ 0.9, partial ≥ 0.6. Unreadable → UM | `R/storage.ts:70`, C:526 |
| CO | CO-03-06 VACUUM | PO history + `query.history` manual VACUUM + `DESCRIBE CATALOG EXTENDED` | PO enabled → SbA. Else manual VACUUM within 30 days → pass, else partial/fail | `R/storage.ts:171`, C:559 |
| CO | CO-03-07 Delta retention (alias `delta-history-retention` with REL-04-05) | DESCRIBE DETAIL `delta.logRetentionDuration`/`deletedFileRetentionDuration` | Reachable days < 7 → fail. Log retention > file retention → partial. Else pass | `R/retention.ts:131`, C:592 |
| CO | CO-04-01 Always-on vs triggered streaming | `lakeflow.jobs.trigger.continuous` | No continuous jobs → pass. Continuous share ≤ 0.25 → partial. Else fail | `R/cost.ts:719-754`, C:630 |
| CO | CO-04-02 Spot / capacity-excess | `compute.clusters.*_attributes.availability` | SPOT/PREEMPTIBLE/LOWEST_PRICE share. Pass ≥ 0.5, partial ≥ 0.2 | `R/cost.ts:541-567`, C:653 |
| CO | Q-practice: CO-01-07 instance type, CO-01-09 right-size at deployment, CO-03-02 budgets & alerts, CO-03-03 monitor costs, CO-03-04 manage costs | attestation; `C/questions.mjs:87-150` | Authored question + evidence prompt + cadence 365/180 days | C:200,251,456,479,502 |

### 6.3 Data & AI governance (`C/data-and-ai-governance.yaml`, 13: 10 measured, 3 practice)

| Pillar | Check / requirement | Evidence source | Pass/fail logic or threshold | `path:line` |
| --- | --- | --- | --- | --- |
| DG | DG-01-02 Design UC / DG-01-03 One metadata plane (critical, alias `unity-catalog-governed`) | `information_schema.tables` | **Pass whenever ≥ 1 table is visible** (a count, not a share). Legacy HMS is out of scope | `R/governance.ts:65-99`, C:37,60 |
| DG | DG-01-04 Lineage | `access.table_lineage` ⋈ `information_schema.tables` (`S/uc_lineage_coverage.sql`) | Tables in lineage ÷ tables. Pass ≥ 0.5, partial ≥ 0.15. 0 lineage events → fail | `R/governance.ts:254-300`, C:73 |
| DG | DG-01-05 Descriptions (low) | `information_schema.tables.comment` | Described share. Pass ≥ 0.8, partial ≥ 0.4 | `R/governance.ts:105-131`, C:103 |
| DG | DG-01-06 Easy discovery | lineage reads ⋈ tables, tags, owners (+ `information_schema.columns` enrichment) | Described share of *read* tables. 0.8/0.4. Nothing read → UM (attestation) | `R/governance.ts:160-236`, C:131 |
| DG | DG-01-07 AI assets with data | census | **Partial cap** when tables exist | `R/governance.ts:363-406`, C:163 |
| DG | DG-02-02 Audit logging / DG-02-03 Audit events (high, alias `audit-logging` with SCP-04-18) | `access.audit` (`S/governance_audit_coverage.sql`) | Events > 0 and days since last ≤ 2 → pass. > 2 → partial. 0 events → UM | `R/governance.ts:315-359`, C:210,238 |
| DG | DG-03-02 Data quality tools | `data_quality_monitoring.table_results` (`S/uc_quality_monitoring.sql`) | Latest verdict per table counted. **Always UM (attestation)**, reported not banded | `R/quality-monitoring.ts:35`, C:284 |
| DG | DG-03-03 Standard formats | = CO-01-01 alias | | C:313 |
| DG | Q-practice: DG-01-01 governance process, DG-02-01 centralize access control, DG-03-01 quality standards | attestation | | C:15,188,256 |

### 6.4 Interoperability & usability (15: 10 measured, 5 practice)

| Pillar | Check / requirement | Evidence source | Pass/fail logic or threshold | `path:line` |
| --- | --- | --- | --- | --- |
| IU | IU-01-02 Optimized connectors | `information_schema.connections` (+ `metastore_privileges` visibility gate) | ≥ 1 connection → pass. 0 → UM (Auto Loader and managed connectors register none) | `R/interoperability.ts:158`, C:36 |
| IU | IU-01-05 IaC (alias `infrastructure-as-code`) | `lakeflow.jobs.deployment.kind` | See OE-02-01 | `R/operational-excellence.ts:283`, C:111 |
| IU | IU-02-01 Open formats | alias CO-01-01 | | C:125 |
| IU | IU-02-02 Secure sharing | `information_schema.shares/recipients/providers` | Nothing shared → N/A. Shares = 0 (inbound only) → pass (see §9 item 5). Shares without recipients → partial. Shares + recipients → pass | `R/interoperability.ts:63-156`, C:141 |
| IU | IU-03-02 Serverless | alias CO-01-06 | | C:213 |
| IU | IU-03-03 Compute templates (alias `compute-templates` with OE-02-02) | `compute.clusters.policy_id` | Pass ≥ 0.9, partial ≥ 0.5 | `R/operational-excellence.ts:337`, C:228 |
| IU | IU-03-04 AI for productivity | REST `serving-endpoints` + `vector-search/endpoints` | Any endpoint → pass. None → UM | `R/interoperability.ts:372`, C:253 |
| IU | IU-04-01 / IU-04-02 Data products (alias `data-products`) | `information_schema.table_tags` + census | No tags → partial if ≥ 80% described, else fail. Tags present → **partial cap** | `R/interoperability.ts:296`, C:283,306 |
| IU | IU-04-03 Central catalog | census + lineage | min(described share, lineage share). Pass ≥ 0.7, partial ≥ 0.3 | `R/interoperability.ts:218`, C:316 |
| IU | Q-practice: IU-01-01, IU-01-03 certified partner tools, IU-01-04, IU-02-03, IU-03-01 | attestation | | C:15,62,89,165,191 |

### 6.5 Operational excellence (21: 15 measured, 6 practice)

| Pillar | Check / requirement | Evidence source | Pass/fail logic or threshold | `path:line` |
| --- | --- | --- | --- | --- |
| OE | OE-01-02 SCM / OE-02-01 IaC (alias with IU-01-05) | `lakeflow.jobs.deployment.kind = BUNDLE` | Bundle marker present → **partial cap** (Terraform leaves no marker). None → UM | `R/operational-excellence.ts:283`, C:34,153 |
| OE | OE-01-04 MLOps | `serving.served_entities` + `mlflow.runs_latest` | **Partial cap**. Both empty → UM | `R/operational-excellence.ts:566`, C:69 |
| OE | OE-01-06 Catalog strategy | census | 1 catalog → fail. > 1 → **partial cap** | `R/operational-excellence.ts:378`, C:120 |
| OE | OE-02-02 Standardize compute | `compute.clusters.policy_id` | Pass ≥ 0.9, partial ≥ 0.5. None → SbA | `R/operational-excellence.ts:337`, C:178 |
| OE | OE-02-03 UC managed tables | census: managed ÷ (managed + external) | Pass ≥ 0.8, partial ≥ 0.4 | `R/operational-excellence.ts:63-100`, C:216 |
| OE | OE-02-04 Automated jobs | `lakeflow.jobs` trigger / paused / change_time | Automated ÷ decidable. Pass ≥ 0.9, partial ≥ 0.6. **UM if the band flips when unknowns are counted as manual** | `R/operational-excellence.ts:108-172`, C:242 |
| OE | OE-02-05 Event-driven ingestion | `lakeflow.jobs.trigger_type` | Any FILE_ARRIVAL → pass. Else UM or N/A (never fail) | `R/job-triggers.ts:39`, C:266 |
| OE | OE-02-06 ETL frameworks / OE-02-11 Declarative (alias) | `lakeflow.pipelines` (+ update timeline) vs jobs | Pipelines ÷ (pipelines + jobs). Pass ≥ 0.5, partial ≥ 0.15. No pipelines but jobs exist → fail | `R/operational-excellence.ts:203`, C:288,417 |
| OE | OE-02-08 Model registry | `serving.served_entities.entity_version` | All custom models versioned → pass. Else fail. None → UM | `R/model-lifecycle.ts:116`, C:337 |
| OE | OE-02-09 Automated experiment tracking | `mlflow.runs_latest.tags['mlflow.source.type']` (≤ 30 days) | Any JOB/PROJECT/RECIPE run → pass. 0 automated → fail. No runs → UM | `R/model-lifecycle.ts:178`, C:365 |
| OE | OE-03-01 Service limits & quotas | `query.history.waiting_at_capacity_duration_ms` (lookback capped at 30 d) | **Always partial** when any statements exist. None → N/A | `R/operational-excellence.ts:498-545`, C:434 |
| OE | OE-04-01 Monitoring / OE-04-02 Native tools / PE-05-04 Job perf (alias `job-monitoring`) | `lakeflow.jobs.health_rules` | ≥ 1 health rule among jobs where the column is written. Pass ≥ 0.8, partial ≥ 0.3 | `R/operational-excellence.ts:437`, C:488,513 |
| OE | Q-practice: OE-01-01 ops team, OE-01-03 CI/CD, OE-01-05 environment isolation, OE-02-07, OE-02-10, OE-03-02 capacity planning | attestation | | C:15,47,98,314,396,465 |

### 6.6 Performance efficiency (25: 13 measured, 12 practice)

| Pillar | Check / requirement | Evidence source | Pass/fail logic or threshold | `path:line` |
| --- | --- | --- | --- | --- |
| PE | PE-02-01 Serverless | alias CO-01-06 | | C:19 |
| PE | PE-02-02 Enterprise model serving | `serving.served_entities` + `endpoint_usage` (`S/serving_model_entities.sql`) | Live entities > 0 → pass. Else UM | `R/model-lifecycle.ts:61`, C:34 |
| PE | PE-03-05 Predictive optimization | `DESCRIBE CATALOG EXTENDED` per catalog (`srv/collect/sql/predictive-optimization.ts:137`) | Enabled managed tables ÷ managed. Pass = 1.0, partial ≥ 0.5. Unknown → UM | `R/platform.ts:127`, C:154 |
| PE | PE-03-06 UC managed tables | census: managed ÷ (tables − views) | Pass ≥ 0.8, partial ≥ 0.4 | `R/platform.ts:85-117`, C:173 |
| PE | PE-03-08 Native engines | alias CO-01-10 | | C:222 |
| PE | PE-03-10 Caching | `query.history.read_io_cache_percent` weighted by `read_bytes` | Cached bytes ÷ file bytes. Pass ≥ 0.5, partial ≥ 0.2. No file reads → N/A | `R/cost.ts:678-716`, C:261 |
| PE | PE-03-11 Compaction | DESCRIBE DETAIL sample + maintenance recency + PO | Average file ≥ 16 MiB share: pass ≥ 0.9, partial ≥ 0.6. A fail becomes partial if OPTIMIZE ran or PO is not disabled | `R/platform.ts:198`, C:296 |
| PE | PE-03-12 Data skipping | DESCRIBE DETAIL (stats, clustering, partitions) | Any table disabling stats → fail. Large tables (≥ 1 GiB, ≥ 10 files) organised: 0.8/0.4 | `R/layout.ts:223`, C:318 |
| PE | PE-03-13 Avoid over-partitioning | DESCRIBE DETAIL | Any partitioned table < 1 TiB → fail. Else pass | `R/layout.ts:60`, C:348 |
| PE | PE-03-15 ANALYZE statistics (low) | PO history + `query.history` ANALYZE | PO enabled → SbA. Manual ANALYZE runs → pass. Else UM | `R/platform.ts:327`, C:399 |
| PE | PE-03-16 Deletion vectors | DESCRIBE DETAIL on read tables | Share with DV. Pass ≥ 0.8, partial ≥ 0.4 | `R/layout.ts:160`, C:414 |
| PE | PE-05-03 Streaming backlog alerts | `lakeflow.jobs.health_rules` metric `STREAMING_BACKLOG_*` | Continuous jobs with a backlog rule: 0.8/0.3. No continuous jobs → N/A | `R/job-triggers.ts:134`, C:554 |
| PE | PE-05-04 Job performance | alias OE-04-01 | | C:581 |
| PE | Q-practice: PE-03-01/02/03/04/07/09/14, PE-04-01/02/03, PE-05-01/02 | attestation | | C:67-534 |

### 6.7 Reliability (18: 8 measured, 10 practice)

| Pillar | Check / requirement | Evidence source | Pass/fail logic or threshold | `path:line` |
| --- | --- | --- | --- | --- |
| REL | REL-01-01 ACID format | alias CO-01-01 | | C:15 |
| REL | REL-01-02 Resilient distributed engine (high) | `compute.clusters` (source JOB/PIPELINE) | Share not single-node. Pass = 1.0, partial ≥ 0.9 | `R/cluster-sizing.ts:55`, C:30 |
| REL | REL-01-04 Retries & termination (high) | `lakeflow.jobs.timeout_seconds` | Timeout > 0 among jobs where it is recorded. Pass ≥ 0.8, partial ≥ 0.4. None recorded → UM | `R/platform.ts:416`, C:95 |
| REL | REL-01-06 Managed services | alias CO-01-06 | | C:144 |
| REL | REL-02-04 Constraints | DESCRIBE DETAIL `delta.constraints.*` | ≥ 80% of sampled tables with CHECK → pass. **Otherwise UM** (never partial or fail) | `R/constraints.ts:53`, C:233 |
| REL | REL-03-01 ETL autoscaling | alias CO-02-01 | | C:286 |
| REL | REL-03-02 Warehouse autoscaling | `compute.warehouses` max > min clusters | Pass ≥ 0.8, partial ≥ 0.4 | `R/platform.ts:56`, C:313 |
| REL | REL-04-05 Delta retention | alias CO-03-07 | | C:426 |
| REL | Q-practice: REL-01-03, REL-01-05, REL-02-01/02/03/05, REL-04-01/02/03/04 (HA/DR) | attestation | | C:72-407 |

### 6.8 Security, compliance & privacy (70: 12 measured, 53 setting questions, 5 practice)

| Pillar | Check / requirement | Evidence source | Pass/fail logic or threshold | `path:line` |
| --- | --- | --- | --- | --- |
| SCP | SCP-01-01 Identity configuration | `access.audit` login `action_name`s (+ account plane `workspace_id=0`) | `login` (password) events > 0 → fail. Otherwise UM (**never passes**) | `R/auth-login.ts:35`, C:15 |
| SCP | SCP-04-04 Deprecated runtimes (high) | `compute.clusters.dbr_version` | All-purpose ≥ DBR 14. Pass = 1.0, partial ≥ 0.9 | `R/compute-hardening.ts:58`, C:871 |
| SCP | SCP-04-05 Managed tables on DBFS root (low) | `information_schema.tables.storage_path` (`S/security_dbfs_tables.sql`) | 0 managed → N/A. 0 on `dbfs:/` → pass. Any → fail | `R/security-jobs.ts:117-160`, C:919 |
| SCP | SCP-04-07 UC access modes (high) | `compute.clusters.data_security_mode` | UC mode share among known. Pass = 1.0, partial ≥ 0.8 | `R/compute-hardening.ts:110`, C:983 |
| SCP | SCP-04-10 Metastore assignment / SCP-04-14 Metastore exists (derived) | census readable | **Always pass** when the census is read | `R/metastore.ts:35,66`, C:1075,1158 |
| SCP | SCP-04-16 Init scripts on DBFS (high) | `compute.clusters.init_scripts` regex `^(dbfs:/|/dbfs/)` | Clean share. Pass = 1.0, partial ≥ 0.95 | `R/compute-hardening.ts:177`, C:1205 |
| SCP | SCP-04-18 Audit via system tables | alias DG-02-02 | | C:1275 |
| SCP | SCP-04-22 Jobs run as SP | `lakeflow.jobs.run_as` (email = user) | SP share among recorded. Pass = 1.0, partial ≥ 0.8 | `R/security-jobs.ts:43`, C:1385 |
| SCP | SCP-02-09 Embeddings stored securely (low) | REST `vector-search/endpoints` (grantable) | Endpoints > 0 → pass. None → N/A | `R/endpoints.ts:39`, C:361 |
| SCP | SCP-03-07 Serving endpoints secured (high) | REST `serving-endpoints` (grantable) | Endpoints exist → UM (unreachable: networking scope). None → N/A | `R/endpoints.ts:77`, C:591 |
| SCP | SCP-05-10 LLM provider routing (info) | REST `serving-endpoints` | Any external-model endpoint → pass. Else partial. None → N/A | `R/security-settings.ts:273`, C:1630 |
| SCP | **Import:** 14 `workspace-conf` flags: SCP-02-04/05/06/07/08/12, SCP-03-10, SCP-04-08/09, SCP-05-04/05/06/07/15 | `GET /api/2.0/workspace-conf` (scope `settings`, not grantable) | Explicit secure value → pass. Explicit insecure → fail. Unset: `enforcement`/`permissive` → fail, `unknown` → UM | `R/security-settings.ts:33-97`, `srv/collect/rest/settings-keys.ts:47-172` |
| SCP | **Import:** SCP-01-04 Max token lifetime | `workspace-conf maxTokenLifetimeDays` | Unset or negative → fail. ≤ 90 days → pass. > 90 → partial | `R/security-settings.ts:99`, C:95 |
| SCP | **Import:** SCP-01-03 PATs without expiry / SCP-01-05 beyond max / SCP-04-01 expiring ≤ 30 d | `token-management/tokens` (scope `authentication`) | Any perpetual → fail. Any over max → fail. Any expiring soon → partial | `R/security-settings.ts:146,222,179` |
| SCP | **Import:** SCP-04-02 Audit log delivery | account `log-delivery` | Enabled AUDIT_LOGS → pass. Disabled only → partial. None → fail | `R/security-admin.ts:63` |
| SCP | **Import:** SCP-03-08 / SCP-03-12 Account IP lists, SCP-03-05 workspace IP lists | `ip-access-lists` | Enabled ALLOW list → pass. Lists but none enabled → partial or fail. None → fail | `R/security-admin.ts:142,195,238` |
| SCP | **Import:** SCP-04-21 legacy features, SCP-02-01 secret scopes, SCP-02-02 disk encryption, SCP-04-03 clusters up > 30 days, SCP-01-06 PAT creation ACL | account setting / `secrets/scopes/list` / `clusters/list` / `permissions/authorization/tokens` | Boolean or presence rules. `users` group holds token permissions → fail | `R/security-admin.ts:291,328,379,446,514` |
| SCP | **Import:** typed settings SCP-02-10 legacy DBFS, SCP-02-11 SQL download, SCP-04-19 restrict admins, SCP-04-20 auto cluster update, SCP-05-13/14 CSP/ESM ws, SCP-05-11 CSP account | `settings/types/*/names/default` | Boolean equals secure value → pass, else fail. Missing field → UM | `R/security-admin.ts:565-650` |
| SCP | **Planned, unreachable (19):** SCP-01-07, 02-03, 03-03/04/06/09/11, 04-11/12/13/15/17/23, 05-01/02/03/08/09/12 | account/UC/permissions APIs not grantable | UM "unreachable" + attestation remedy | `srv/resolve/resolver.ts:401-424` |
| SCP | Q-practice: SCP-01-02, SCP-03-01, SCP-03-02; planned attestations SCP-03-13 egress test, SCP-04-06 DBFS mounts | attestation | | C:44,464,483,747,950 |

Coverage totals from the generated ledger: **85 of 184 entries measured in an install, 53 setting questions (34 revived
from admin import, 16 collected and held, 3 not collected), 46 practice questions (10 beyond telemetry, 36 partial
telemetry, 0 "owed a measure")** (`docs/coverage-ledger.md:19-68`). Security has 12 of 70 measured
(`coverage-ledger.md:237-247`).

### 6.9 SQL inventory (all `.sql` files)

"Window" describes how the lookback N is applied (default 30, clamped 1–365). Nearly every statement over a
workspace-carrying table also filters on the `live_workspace_ids` parameter. "SCD" = latest-row window, then lifecycle
filter applied outside it.

| File | Signal → consumers | System tables | Rows | Window / key logic |
| --- | --- | --- | --- | --- |
| `S/workspace_directory.sql` | estate.workspaces → filter for all | `access.workspaces_latest`, `billing.usage` | 1/workspace | Region = DBU-weighted `regexp_extract` of the SKU suffix. `live = status='RUNNING'` |
| `S/estate_compute_profile.sql` | estate.compute_profile → preconditions | `billing.usage` | ≤ 100 | `usage_date` window, DBU only. Pre-group to make distinct counts one scan |
| `S/compute_cluster_inventory.sql` | compute.clusters → 12 controls | `compute.clusters` | 1/cluster (sliced ws, cluster_id) | No window. SCD latest row, then `delete_time IS NULL`. GPU regex, DBFS init regex |
| `S/compute_warehouse_inventory.sql` | compute.warehouses | `compute.warehouses` | 1/warehouse | No window. SCD latest row |
| `S/node_utilization.sql` | compute.node_utilization → CO-01-08 | `compute.node_timeline` | 1 | `start_time` window. ≥ 60 samples, < 5% CPU |
| `S/cost_attribution_coverage.sql` | cost.attribution → CO-03-01 | `billing.usage`, `billing.list_prices` | 1 | Point-in-time price join on `usage_end_time`. Per-unit coverage. `duplicate_price_matches` |
| `S/cost_compute_mix.sql` | cost.compute_mix → CO-01-02/06/10, PE-02-01/03-08, REL-01-06, IU-03-02 | usage + list_prices | 1 | Serverless = flag OR closed product list. Choice set = JOBS/ALL_PURPOSE/INTERACTIVE/SQL/DLT |
| `S/jobs_inventory.sql` | jobs.inventory | `lakeflow.jobs` | 1/job (sliced) | No window (deliberate). SCD. `_known` flags for columns empty before December 2025 |
| `S/lakeflow_pipeline_inventory.sql` | pipelines.inventory → OE-02-06/11 | `lakeflow.pipelines`, `pipeline_update_timeline` | 1/pipeline | SCD. Update counts over the window |
| `S/serverless_job_readiness.sql` | serverless.job_readiness → advisor | `job_task_run_timeline`, `compute.clusters` | 1/job (sliced ws, job_id) | Last period row per task run (no duration double-count). Cluster config = current, not as-of |
| `S/serverless_job_spend.sql` | serverless.job_spend → advisor | usage + list_prices | 1/job (sliced) | Serverless rate by tier and region derived from the workspace's own serverless SKUs |
| `S/job_run_health.sql` | workload.job_run_health → advisor | job run and task timelines, `billing.usage` | ≤ `:job_limit` | Durations from period endpoints (stated durations are 0). Retractions summed |
| `S/job_compute_utilisation.sql` | workload.job_compute_utilisation → advisor | timelines, `node_timeline`, `clusters` | ≤ `:job_limit` | Overlap join, `driver = FALSE`, as-of config join `change_time <= run_start` |
| `S/workload_query_shapes.sql` | workload.query_shapes → advisor | `query.history` | ≤ 40 | `least(N,15)`×2 (≤ 30 d). Fingerprint = sha2 of normalised text. `kinds = 1` guard. Self-exclusion |
| `S/workload_write_patterns.sql` | workload.write_patterns → advisor | `query.history` | ≤ 40 | `least(N,30)`. Writes ranked by bytes written |
| `S/workload_table_statistics.sql` | workload.table_statistics → advisor | PO history, `table_lineage`, `billing.usage` | ≤ 200 | ANALYZE vs later writes |
| `S/workload_sql_paths.sql` | workload.sql_paths → CO-01-03, PE-03-10 | `query.history`, `compute.clusters` | 1 | `current_timestamp` window. Interactive = no job/pipeline. Cache weighted by bytes |
| `S/workload_warehouse_pressure.sql` | workload.warehouse_pressure → advisor | `query.history`, `compute.warehouse_events` | ≤ 200 | 7 calendar days. Uptime from event stream with carried-in state and `lead()` |
| `S/query_capacity.sql` | query.capacity → OE-03-01 | `query.history` | 1 | `least(N,30)` |
| `S/governance_audit_coverage.sql` | governance.audit_coverage → DG-02-02/03, SCP-04-18 | `access.audit` | 1 | `event_date` window. Days since last event |
| `S/auth_login_paths.sql` | security.auth_login_paths → SCP-01-01 | `access.audit` | 1 | Admits `workspace_id = 0` (account plane). Names other auth actions |
| `S/security_dbfs_tables.sql` | security.dbfs_tables → SCP-04-05 | `information_schema.tables`, `.catalogs` | 1 | No window |
| `S/uc_asset_census.sql` | uc.census → ≈ 14 controls | `information_schema.tables` | 1 | Customer-catalog predicate. Counts views, metric views and foreign tables separately |
| `S/uc_catalog_inventory.sql` | uc.catalogs → PO collector | `information_schema.tables` | 1/catalog | Catalogs holding tables |
| `S/uc_schema_census.sql` | uc.schema_census (enrichment) | `information_schema.tables` | ≤ 500 | `count(*) OVER ()` population before LIMIT |
| `S/uc_platform_census.sql` | uc.platform_census → IU/OE/SCP | 15 `information_schema` views | 1 | Plus `owns_metastore`, `sharing_privileges` visibility columns |
| `S/uc_discovery_metadata.sql` / `uc_discovery_columns.sql` | uc.discovery (+columns) → DG-01-06 | tables, table_tags, columns, table_lineage | 1 | Columns split out because `information_schema.columns` compiled for about an hour on a large estate |
| `S/uc_lineage_coverage.sql` | uc.lineage_coverage → DG-01-04, cross-check | `table_lineage`, tables | 1 | One pass. Struct identity (no dot collisions) |
| `S/uc_quality_monitoring.sql` | uc.quality_monitoring → DG-03-02 | `data_quality_monitoring.table_results` | 1 | `max_by` latest verdict per table |
| `S/storage_sample_selection.sql` | storage.sample_selection → DESCRIBE | `information_schema.tables`, `table_lineage` | ≤ 200 | Most-read Delta tables first, deterministic tiebreak |
| `S/storage_table_metrics.sql` | storage.table_metrics | `storage.table_metrics_history` | ≤ 200 | Latest snapshot. Empty → `noAnswer` returns UM |
| `S/maintenance_recency.sql` | maintenance.recency → CO-03-06, PE-03-11/15 | PO history, `query.history`, tables | ≤ 40 | Comment-stripping regex, 3-part name extraction |
| `S/serving_population.sql`, `serving_asset_{tags,facts,quality,classifications}.sql` | serving.* → foundation readiness (not scored) | `information_schema.*`, `table_lineage`, `assistant_events`, DQM, `data_classification.results` | ≤ 2000 | On-demand, two-pass |
| `S/serving_model_entities.sql` | serving.model_entities → PE-02-02, OE-02-08, OE-01-04 | `serving.served_entities`, `endpoint_usage` | ≤ 200 | Traffic `least(N,30)` |
| `S/mlflow_run_tracking.sql` | mlflow.run_tracking → OE-02-09, OE-01-04 | `mlflow.runs_latest`, `experiments_latest` | 1 | `least(N,30)`. Untagged runs counted apart |
| `T/*.sql` (8) | topology edges (job→cluster/job/table/warehouse, pipeline→table, table→table, warehouse→table, names) | timelines, lineage, `query.history`, inventories | ≤ `:topology_limit` | Drawing only, scores nothing |
| `srv/collect/sql/runtime-baseline/probes/*.sql` (8) | calibration probes for measurement scripts | billing, jobs, lineage, `query.history`, warehouse_events | — | Not run by the app |

### 6.10 Notable SQL excerpts

**Point-in-time list-price join plus a double-count detector** (`S/cost_attribution_coverage.sql:44-49`, `:86`):
```sql
  FROM system.billing.usage u
  LEFT JOIN system.billing.list_prices p
    ON u.sku_name = p.sku_name
    AND u.usage_end_time >= p.price_start_time
    AND (p.price_end_time IS NULL OR u.usage_end_time < p.price_end_time)
  WHERE u.usage_date >= current_date() - make_dt_interval(:lookback_days)
...
    count(*) - count(DISTINCT record_id)                          AS duplicate_price_matches,
```

**SCD2 "latest row, then lifecycle filter"** (`S/compute_cluster_inventory.sql:36-50`). The earlier version filtered
`delete_time IS NULL` inside the ranked query and returned 6.1 M "live" clusters where 135 k existed
(`:14-18`):
```sql
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY workspace_id, cluster_id ORDER BY change_time DESC) AS recency
  FROM system.compute.clusters
  WHERE (:workspace_id = '' OR workspace_id = :workspace_id)
    AND (:live_workspace_ids = '' OR array_contains(split(:live_workspace_ids, ','), workspace_id))
),
-- The lifecycle filter, on the row the window chose.
latest AS (
  SELECT *
  FROM ranked
  WHERE recency = 1
    AND delete_time IS NULL
)
```

**Region from SKU names, weighted by DBUs** (`S/workspace_directory.sql:56-83`):
```sql
WITH regional_sku AS (
  SELECT
    workspace_id,
    regexp_extract(
      sku_name,
      '_(US_[A-Z_]+|EUROPE_[A-Z_]+|AP_[A-Z_]+|CANADA[A-Z_]*|SA_[A-Z_]+|AF_[A-Z_]+|ME_[A-Z_]+)$',
      1
    )                                                          AS region,
    usage_quantity
  FROM system.billing.usage
  WHERE usage_date >= current_date() - make_dt_interval(:lookback_days)
    AND usage_unit = 'DBU'
),
by_volume AS (
  SELECT workspace_id, region,
    ROW_NUMBER() OVER (PARTITION BY workspace_id ORDER BY sum(usage_quantity) DESC) AS rank
  FROM regional_sku
  WHERE region <> ''
  GROUP BY workspace_id, region
)
```
(Comment lines inside the CTE are omitted, and `by_volume` is condensed onto fewer lines.)

**The NULL trap in self-exclusion, and the fix** (`S/workload_sql_paths.sql:94-101`, `:122`). Written as
`AND NOT (a OR b …)`, the filter dropped every row, because `try_element_at` returns NULL and `NOT NULL` is not true
(`:112-121`):
```sql
    CASE
      WHEN try_element_at(h.query_tags, 'databricks_waf') = 'assessment'
        OR startswith(trim(h.statement_text), '-- databricks-waf: assessment')
        OR contains(h.statement_text, '-- Signal: sql:')
        OR contains(h.statement_text, '-- Rows: ')
      THEN 1
      ELSE 0
    END                                                       AS is_self
...
  SELECT * FROM history WHERE is_self = 0
```

**Warehouse uptime from an event stream with carried-in state** (`S/workload_warehouse_pressure.sql:302-318`, `:339-349`):
```sql
carried AS (
  SELECT workspace_id, warehouse_id, cluster_count
  FROM (
    SELECT workspace_id, warehouse_id, cluster_count,
      ROW_NUMBER() OVER (
        PARTITION BY workspace_id, warehouse_id ORDER BY event_time DESC, cluster_count ASC
      ) AS recency
    FROM system.compute.warehouse_events
    WHERE event_time < date_sub(current_date(), least(:lookback_days, 7) - 1)
      AND (:live_workspace_ids = '' OR array_contains(split(:live_workspace_ids, ','), workspace_id))
  )
  WHERE recency = 1 AND cluster_count > 0
),
...
    lead(at) OVER (
      PARTITION BY workspace_id, warehouse_id ORDER BY at, seeded DESC
    ) AS next_at
```
(One filter line is omitted, and the inner SELECT is condensed onto one line.)

**Timeline durations from period endpoints, never sums** (`S/job_run_health.sql:75-91`):
```sql
WITH task_runs AS (
  SELECT
    workspace_id, job_id, job_run_id, run_id, task_key,
    min(period_start_time) AS task_start,
    max(period_end_time)   AS task_end,
    unix_timestamp(max(period_end_time)) - unix_timestamp(min(period_start_time)) AS task_seconds
  FROM system.lakeflow.job_task_run_timeline
  WHERE period_start_time >= current_date() - make_dt_interval(:lookback_days)
    AND (:live_workspace_ids = '' OR array_contains(split(:live_workspace_ids, ','), workspace_id))
  GROUP BY workspace_id, job_id, job_run_id, run_id, task_key
),
```
(The select list is condensed onto one line, and the `workspace_id` filter and a comment are omitted.)

**Population before LIMIT** (`S/uc_schema_census.sql:44`): `count(*) OVER () AS schema_population`. The window is
evaluated before `LIMIT :segment_limit`, so a truncated result is distinguishable from a complete one.

---

## 7. Patterns worth stealing

**P1. The "no answer" contract at the collector boundary** (`srv/collect/sql/collector.ts:847-851`, `:984-989`):
```ts
      const noAnswer = definition.noAnswer?.(value);
      if (noAnswer != null) return unread(noAnswer);
...
    if (whole && truncated) {
      throw new Error(
        'The warehouse returned more data than an inline result can carry, and this statement cannot ' +
          'be divided, so the rows it did return are part of the answer rather than the answer.'
      );
    }
```

**P2. Attestation can fill but never override** (`srv/resolve/resolver.ts:222-224`):
```ts
  if (resolution.outcome === 'unmeasurable' && attested != null) {
    return { ...findingFromAttestation(spec, attested), evidence: resolution.evidence };
  }
```

**P3. Score with honest bounds** (`srv/score/score.ts:73-81`, `:392-397`):
```ts
export const CREDIT: Readonly<Record<Outcome, number | null>> = {
  pass: 1, 'satisfied-by-architecture': 1, partial: 0.5, fail: 0,
  unmeasurable: null, 'not-applicable': null,
};
...
          score: round((earned / available) * 100),
          range: { low: round((earned / total) * 100), high: round(((earned + unmeasured) / total) * 100) },
```
(`CREDIT` is condensed onto three lines, and its comments are omitted.)

**P4. Sensitivity test against unknowns: abstain when the unknowns could flip the verdict**
(`R/operational-excellence.ts:145-148`):
```ts
  const bands = bandsOf(context.spec, { pass: 0.9, partial: 0.6 });
  const ifAllManual = bandOutcome(share(automated.length, jobs.length), bands);
  const outcome = bandOutcome(adopted, bands);
  if (outcome !== ifAllManual) {
    return unmeasured( /* … */ 'attestation');
```

**P5. Tri-state semantics for an unset setting** (`srv/collect/rest/settings-keys.ts:26`, `:48-57`). Each key declares
whether "unset" means `enforcement` (fail), `permissive` (fail) or `unknown` (unmeasured). This avoids the classic SAT
false-fail on untouched defaults.

**P6. AIMD concurrency control per surface** (`srv/scan/limiter.ts:100-123`). The limit halves on throttle and grows by 1
after 5 consecutive successes. A `Retry-After` pauses admissions. Retries use full-jitter backoff, but only where the
client below does not already retry (`surfaces.ts:43-58`), which prevents 3×3 = 9× amplification:
```ts
  onThrottled(retryAfterMs?: number): void {
    this.limit = Math.max(1, Math.floor(this.limit / 2));
    this.consecutiveSuccesses = 0;
    this.reductions += 1;
    if (retryAfterMs != null && retryAfterMs > 0) {
      this.pausedUntil = Math.max(this.pausedUntil, this.now() + retryAfterMs);
    }
```

**P7. Deadline plus cancel on the warehouse**, not just "stop waiting" (`statements.ts:241-244`):
```ts
      const waited = Date.now() - started;
      if (waited >= this.deadlineMs) {
        throw new StatementDeadlineError(statementId, waited, await this.cancel(statementId));
      }
```

**P8. Tag your own queries so the analysis can exclude them** (`srv/collect/sql/self.ts:99-106`). It uses
`query_tags` (as an array, because a map is silently recorded as `tags_invalid`) plus a comment marker. Two retroactive
text marks cover history written before the tags existed.

**P9. Lossless re-bucketing of a truncated slice** (`srv/collect/sql/buckets.ts:97-101`). A bucket on a GROUP BY key
never splits an output group, and `pmod(hash, 4k)` refines `pmod(hash, k)`:
```ts
    `${first} (bucket ${String(bucket.index + 1)} of ${String(bucket.of)} on ${column})\n` +
    `SELECT * FROM (\n${statement}\n) AS sliced\nWHERE pmod(hash(sliced.${quoted}), ${String(bucket.of)}) = ` +
    `${String(bucket.index)}`
```

**P10. One identifier-quoting rule for all generated SQL** (`app/scripts/sql-identifiers.mjs:22-27`). A test walks the
tree for hand-built identifiers:
```js
export function quoteIdent(value) {
  if (value == null) return undefined;
  const text = String(value);
  if (text.trim() === '' || /[\r\n]/.test(text)) return undefined;
  return `\`${text.replaceAll('`', '``')}\``;
}
```

**P11. Idempotent retries versus fresh repairs** (`app/schedule/trigger.py:141`):
```python
key = f"job-{job_id}/run-{job_run_id}/repair-{repair_count}" if job_id and job_run_id else None
```

**P12. Deployment verification by a second plan that must be all `skip`** (`app/scripts/lifecycle.mjs:130-132`, `:476-477`),
plus a read-back of effective OBO scopes and bindings (`:180-212`):
```js
export function isIdempotent(answer) {
  return planFacts(answer).every((one) => one.action === 'skip');
}
...
  if (!isIdempotent(afterPlan)) throw new Error('Post-deploy DAB plan is not idempotent.');
```
Related guards: the lifecycle strips `DATABRICKS_*` env overrides so `--profile` wins (`lifecycle.mjs:32-36`). A
destructive uninstall requires a confirmation token that hashes the exact inventory it will remove (`:134-151`).

**P13. Cross-check a privilege-filtered read with an unfiltered one** before claiming emptiness (`R/visibility.ts:79-110`).
Zero tables in `information_schema` alongside lineage events means "unreadable", not "empty estate".

**P14. Imports only fill gaps** (`srv/import/signals.ts:458-477`): an observed reading always stands, and an import
replaces only `unmeasurable`.

---

## 8. Scaling characteristics

**Many workspaces.** One install reads *system tables* for every live workspace in its metastore's region
(`S/workspace_directory.sql:27-53`). REST settings are workspace-scoped (`srv/collect/rest/collector.ts:111-120`),
because a workspace token is rejected by sibling workspaces. An account with several regions needs one install per
region, and full security coverage needs per-workspace admin imports. The four widest statements are
**sliced per workspace group** (≤ 12 groups, `srv/collect/sql/sliced.ts:51`). A truncated slice is re-bucketed 4-way up to
depth 2 (`buckets.ts` FAN_OUT 4, `sliced.ts:99`).

**Large system tables.** The inline result cap is 25 MiB. `byte_limit` is set to 20 MiB so an overrun becomes a
`truncated` flag instead of a failure (`statements.ts:129-144`). Every statement declares a `-- Rows:` bound, enforced
statically by `check-statement-bounds` and at runtime by a warning (`collector.ts:996-1017`). Scale fixtures showed
`compute_cluster_inventory` at 153% of the cap at 150k clusters and `serverless_job_readiness` at 110% at 100k jobs,
which is why they are sliced (`scale.test.ts:6-11`). Expensive references are pushed into *enrichment* signals:
`information_schema.columns` compiled for about an hour on a 600k-relation estate (`S/uc_discovery_columns.sql:21-29`).
Row caps: tables 200, schemas 500, shapes 40, warehouses 200, jobs 200, served entities 200, serving 2,000
(`collector.ts:678-688`). DESCRIBE samples 50 tables (`describe.ts`). Coverage is marked `sampled` with
examined/population where that applies (`collector.ts:1082-1110`).

**Warehouse cost and customer impact.** Statements run sequentially through a limiter of 2 on a shared warehouse
(`collector.ts:701-706`, `surfaces.ts:98-119`). Budgets are 250 SQL and 250 DESCRIBE statements, with a 45-minute wall
clock (`surfaces.ts:188`) and a 10-minute per-statement deadline that cancels on the warehouse. Several query-history
reads cap their own window (15/30/7/30 days) to bound scan time, which was measured to grow linearly with the window
(`S/workload_query_shapes.sql:55-61`). The scheduled job defaults to STANDARD serverless performance, about a third of the
DBUs of performance-optimized (`resources/scheduled-scan.yml:69-94`). The app accounts for its own spend using statement
ids, bytes and rows (`collector.ts:1121-1152`). It measured itself at 51.8% of one labs workspace's query time, which is
the reason for self-tagging (`self.ts:1-10`).

**Rate limits.** 429/503 map to `rate-limited`, 408/504 to `timeout`, 5xx to `transient`, 401/403 to
`permission-denied` (no retry), and 404 to `not-found` (`srv/scan/errors.ts`). Up to 4 attempts with full-jitter backoff
from 500 ms, honouring `Retry-After`. Retries are skipped if the ask is longer than a scan waits. The AIMD limiter
adapts per limiter group. The REST surface relies on the SDK's own retries (`surfaces.ts:120-133`).

**Store scale.** Each scan is one row with `summary` and `body` JSONB (`postgres.ts:216-224`). History pages read
`summary` only. Retention sweeps and legal holds exist (`srv/admin/retention.ts`, `/api/retention/*`).

**Single process.** A process-level single-flight lock plus a durable lease (`runner.ts:1-12`, `runs.ts:12-17`) means
at most one scan's load, but also that an account cannot run two assessments in parallel.

---

## 9. Risks, bugs, smells, questionable logic

**Correctness / "not measured becomes pass" leaks**

1. **CONFIRMED: SCP-04-05 skips the privilege-visibility cross-check.** `R/security-jobs.ts:117-124` returns
   `not-applicable` when `totalManagedTables === 0`, and `pass` when the visible managed tables have no DBFS path. The
   source is privilege-filtered `information_schema`. This is exactly the defect class `R/visibility.ts:1-20` describes
   (a scheduled SP saw 0 of 21 tables). `unestablishedEmptiness` is used in 5 other resolver files but not here. A pass
   also claims "every managed table" when only the visible subset was examined.
2. **CONFIRMED (admin-import path only): SCP-04-03 treats a missing timestamp as compliant.** `R/security-admin.ts:466`
   has `if (reference == null) return false;`, so running clusters with no start or restart time are counted "not
   stale". If all of them lack timestamps, the control **passes** with "All N … restarted within 30 days".
3. **SUSPECTED: an SCD2 filter-before-rank in `S/serving_model_entities.sql:71-80`.**
   `WHERE endpoint_delete_time IS NULL` sits in the same query as
   `row_number() OVER (PARTITION BY served_entity_id ORDER BY change_time DESC)`. That is the very shape
   `srv/collect/sql/history.ts:1-27` forbids. It evades the guard because `mentions()` uses `(?<![\w.])delete_time\b`
   (`history.ts:150-152`), which does not match `endpoint_delete_time`. If `served_entities` appends a row on endpoint
   deletion (inferred from "change log", `:24-29`), deleted endpoints are resurrected as live. That would inflate
   PE-02-02 and OE-02-08.
4. **CONFIRMED (logic), SUSPECTED (impact): REL-01-02 measures a population that is almost always empty.**
   `R/cluster-sizing.ts:55-60` keeps `JOB`/`PIPELINE` clusters from the *live* inventory, which applies
   `delete_time IS NULL` (`S/compute_cluster_inventory.sql:45-50`). The repo itself says a job cluster "exists for the
   length of one run and is then deleted, so filtering on `delete_time IS NULL` … would discard almost every cluster"
   (`S/serverless_job_readiness.sql:36-39`). The high-severity control therefore scores only job clusters running at
   scan time, or goes N/A. The file also flags an unverified `worker_count` null assumption that can false-fail
   (`R/cluster-sizing.ts:24-34`).
5. **CONFIRMED: IU-02-02 passes on orphan recipients.** When `recipients > 0`, `shares = 0` and `providers = 0`,
   `sharing` is true and the `shares === 0` branch returns **pass** with the reason "This metastore consumes shared data".
   That is false, since there are zero providers (`R/interoperability.ts:73`, `:82-96`).
6. **CONFIRMED: CO-01-08 averages driver samples.** `S/node_utilization.sql:39-51` has no `driver = FALSE` filter.
   `S/job_compute_utilisation.sql:26-30` excludes drivers and notes that drivers are a material share of samples below
   10% CPU. Idle drivers push clusters under 5%, and **any** idle cluster fails the control (`R/cluster-sizing.ts:112`).
   A false-fail risk.
7. **CONFIRMED: two "Use UC managed tables" controls use different denominators.** OE-02-03 divides by
   managed + external (`R/operational-excellence.ts:66`). PE-03-06 divides by `tableCount − views`
   (`R/platform.ts:88`), so metric views, foreign tables, materialized views and streaming tables count as *not managed*.
   The two are not alias-grouped, so the same estate scores differently in two pillars.
8. **CONFIRMED (by design, questionable): constant-outcome and one-directional controls.**
   - Constant outcomes: OE-03-01 is always `partial` (`R/operational-excellence.ts:511`, `:534`). DG-01-02/03 (critical,
     weight 10) always pass when any table is visible, which the authors acknowledge (`R/governance.ts:59-63`).
     SCP-04-10/14 always pass.
   - One-directional controls: REL-02-04, OE-02-05, IU-01-02, IU-03-04 and PE-02-02 can only pass or be UM.
     CO-01-08 and SCP-01-01 can only fail or be UM.
   - Consequence: exclusion depends on the outcome ("missing not at random"). For pass-only controls the score is biased
     upward, because the control is excluded exactly when it would have failed. The low/high range partly discloses this.
9. **CONFIRMED: a resumed run never retries a transient failure.** Checkpoints store every reading, `unmeasurable`
   included (`srv/collect/collection.ts:136-148`). `resumeFrom` restores them all (`srv/run/run.ts:292-298`). Collectors
   skip anything already collected (`collector.ts:717`, `rest/collector.ts:67`). So a statement that timed out or hit
   the budget before an app restart stays unmeasured for that run, even though the job's `retry_on_timeout` exists to
   recover such runs. A person's *repair* starts over (`trigger.py:129-133`). An automatic retry does not.
10. **CONFIRMED (divergence), SUSPECTED (effect): the preflight grant text may be insufficient.** `grantFor` emits only
    `GRANT SELECT ON SCHEMA <s> TO <id>` (`srv/define/preflight.ts:187-191`). The project's own notebook says "SELECT
    alone is not enough and fails with INSUFFICIENT_PERMISSIONS"; `USE CATALOG` and `USE SCHEMA` are also needed
    (`app/schedule/trigger.py:34-36`). `schedule-principal.mjs:66`, `:330-334` emits those.
11. **SUSPECTED: the window used differs between signals.** Most signals use `current_date() - make_dt_interval(N)`,
    which yields a timestamp at local midnight and N+1 calendar dates. Others use `current_timestamp()`, which rolls
    (`S/query_capacity.sql:42`, `S/workload_sql_paths.sql:105`). Some cap at 7, 15 or 30 days. `job_run_health` filters
    billing on `usage_start_time`, not the `usage_date` partition column (`S/job_run_health.sql:190`), which may lose
    pruning (inferred). The scan stamp records one `lookbackDays` (`srv/scan/scan.ts:380`). OE-03-01's evidence says
    "in the window" without the 30-day cap (`R/operational-excellence.ts:505-515`).
12. **SUSPECTED: join-key collisions and duplicates.** `S/workload_sql_paths.sql:72-104` dedups clusters by
    (workspace, cluster) and then joins on `cluster_id` only, which duplicates rows if an id repeats across workspaces.
    The clusters CTE is also unfiltered by workspace, so it scans the whole regional table. The discovery and sample
    statements join on `concat_ws('.')` names (`S/uc_discovery_metadata.sql:49`, `:85`) despite the lineage
    statement's own warning about dotted names (`S/uc_lineage_coverage.sql:18-19`).
13. **CONFIRMED (mechanism): imported evidence can be fabricated by an insider.** The envelope digest is an unkeyed
    SHA-256 over canonical probes (`app/config/evidence/collect-evidence.py:854-856`, `srv/import/trust.ts:151`), so an
    assessor can edit a value and recompute it. SECURITY.md is candid that digests are "not signatures". Mitigations are
    audit, the `admin-collected` label and a replay/age check. This matters because 34 security controls rest on import.
14. **SUSPECTED: money figures are list price.** They use `pricing.effective_list.default`
    (`S/cost_compute_mix.sql:103-108`). `system.billing.account_prices` exists (`C/questions.mjs:119`) but is not used,
    so "spend" is not the negotiated bill. Shares are less affected than absolute figures.
15. **CONFIRMED (logic), SUSPECTED (impact): a billing-window precondition hides live-inventory checks.** Fourteen
    controls carry the precondition `sql:estate.compute_profile eq 0 → not-applicable`, with scope `estate` (for
    example `C/cost-optimization.yaml:93`). The profile's `summary` is the number of distinct *classic clusters that
    billed in the window* (`srv/collect/sql/shapes.ts:1601-1626`). The resolvers, by contrast, read the *live*
    inventory, and CO-02-01 and CO-02-02 (plus the REL-03-01 alias) also assess **SQL warehouses** (`R/cost.ts:420-502`).
    Two consequences:
    - An estate running only pro or classic warehouses (whose usage rows carry `warehouse_id`, not `cluster_id`, which
      is inferred) never has warehouse auto-stop or scale-out assessed under CO-02-01 and CO-02-02.
    - Idle but misconfigured all-purpose clusters that billed nothing in the window leave runtimes, policies and
      auto-termination as N/A.
16. **CONFIRMED: scan rows are upserted, so immutability is a convention, not a database property.**
    `srv/scan/postgres-store.ts:61-70` does `insert … on conflict (id) do update set body = excluded.body,
    digest = excluded.digest`. The digest is recomputed with the body, so `verifyRecords` cannot detect an app-level
    overwrite. The stronger guarantees live elsewhere: definition versions are insert-only under a unique key
    (`srv/store/postgres.ts:262-270`, primary key `(definition_id, version)`), results are written once, and publications are frozen bytes.

**Docs vs code (trust the code)**

17. **CONFIRMED:** the README promises "new, changed, resolved, regressed, **and excepted**" (`README.md:32`). The client
    implements 4 classes (`cli/components/change-language.ts:101-111`). `DifferentialStrip.tsx:11-18` says "Exception
    changed has no field behind it".
18. **CONFIRMED:** `docs/configuration.md` says that with `WAF_AUDIT_STRICT=0` "record mutations still fail if their audit
    event cannot be written". The code does the opposite: `0` means record-and-continue, counted on Diagnostics
    (`srv/audit/record.ts:100-101`, `app/app.yaml:48-63`, `srv/server.ts:171-173`).
19. **CONFIRMED:** "The optional AI layer can explain and prioritise findings" (`README.md:167-168`). `srv/ai/gateway.ts`
    is imported by nothing except its own test. It is scaffolding, not a feature.
20. **CONFIRMED stale comments:**
    - `S/estate_compute_profile.sql:23-24` mentions a `.obo.sql` suffix that no file has.
    - `S/compute_warehouse_inventory.sql:25-28` says the cluster and job inventories are "driven from billing"; they
      were reverted (`S/jobs_inventory.sql:17-25`).
    - `S/job_compute_utilisation.sql:152-161` calls an account-wide median "the workspace's own middle".
    - `S/serverless_job_readiness.sql:6` says "jobs that ran on classic compute", but the query returns all jobs.
    - About 65 ADR citations point to files absent from the public repo.
21. **Nuance:** troubleshooting says "Pillars with insufficient evidence are shown as not assessed"
    (`docs/troubleshooting.md:77`). The server has no coverage threshold (`score.ts:38-48`), but the client does: 2 or
    fewer scored with 8 or more applicable is "insufficient", and a range width of 50 or more is "directional"
    (`cli/components/coverage.ts:430-439`, `score-range.ts:26-32`).

**Operational smells**

22. **By design:** `dist/` is committed and deployed as built (`package.json:13`), which needs `check:bundle` to prevent
    drift. `databricks.yml` `config.env` *replaces* app.yaml's env. Forgetting one variable silently dropped the Lakebase
    binding in the past (`databricks.yml:126-143`).
23. **Trade-off:** interactive trends need the same actor (`shared/api/comparability.ts`). A rotating assessor team gets
    "not comparable" between people.
24. **Maintainability:** comment density is extreme (e.g. `srv/api/routes.ts` has 3,419 lines). The reasoning is
    excellent but makes review expensive, and the comments themselves drift (items 17–20).

**Failure modes from the troubleshooting guide** (`docs/troubleshooting.md`):
- `permission denied for schema waf|appkit`: the schema was created by someone other than the app SP, often by running
  locally against the production DB first. The fix is to drop an empty schema or restore into a new DB (`:28-63`).
- 502 or the app not starting: missing bindings. The app serves a fallback page and retries every 30 s
  (`srv/server.ts:454-460`).
- A user can read but not mutate: nested groups do not count (SCIM direct membership) (`:83-85`).
- Wrong workspace in validation: `DATABRICKS_*` env vars override `--profile` (`:87-95`).
- The scheduled job fails readiness: the SP secret, CAN_USE on the app, group membership, and USE/SELECT grants
  (`:97-107`).

---

## 10. How to explain it

**(a) Customer executive (2 minutes).** "It's a continuous architecture review of your Databricks estate, run inside your
own account. It reads the platform's own telemetry (billing, audit, jobs, compute, catalogue) and scores you against
Databricks' seven Well-Architected pillars. What makes it different: every score shows how much was actually measured,
and each gap names the exact job, cluster or table responsible. Fixes are tracked with an owner and confirmed by the next
scan, not by someone ticking a box. Anything the data can't prove, like DR rehearsal, is asked of a named owner and
expires. Nothing leaves your environment, and every published report is frozen and tamper-evident. Think of it as a
posture score with error bars, plus a remediation backlog that verifies itself."

**(b) Customer platform engineer.**
- Deployment: DAB, installed with `npm run lifecycle -- install --apply`. It binds your SQL warehouse (CAN_USE) and a
  Lakebase database (CAN_CONNECT_AND_CREATE).
- Reads: OBO as whoever clicks Run, with scopes `sql.statement-execution`, `sql.warehouses:read`, `catalog.*:read`,
  `sql.query-history:read`, `model-serving` and `vector-search`. It never uses `all-apis` and never uses a PAT.
- Load: about 40 parameterized statements against `system.*`, at concurrency 2 on a shared warehouse, 250 statements at
  most. Each statement is cancelled after 10 minutes. All are tagged `databricks_waf=assessment` in Query History.
- Grants: USE CATALOG on `system` plus USE SCHEMA and SELECT on billing/access/compute/lakeflow/query/storage.
  `information_schema` visibility follows your catalog grants, so BROWSE widens it.
- Settings the app scope can't reach (workspace-conf, tokens, IP lists): run `collect-evidence.py` with an admin CLI
  profile and import the JSON.
- Scheduling: a paused Monday 06:00 UTC job running as a dedicated SP. Readiness runs first. Retries resume the same run.

**(c) Internal Databricks stakeholder (field or product).** It is a reference implementation of "system tables as the
assessment substrate". It exposes real platform gaps:
- Apps can't be granted `settings`, `authentication`, `networking`, `secrets` or `clusters` scopes. As a result, 53 of 70
  security requirements need an admin script.
- `storage.table_metrics_history` was empty everywhere they measured.
- `lakeflow.jobs` columns are null before December 2025. Run-timeline stated durations are written as 0.
- The narrow `serving.serving-endpoints:read` scope validated but granted nothing. `query_tags` maps are silently
  recorded as `tags_invalid`.
- The inline 25 MiB result cap forces slicing, and `information_schema.columns` takes about an hour to compile at scale.

Each of these is a product-feedback item. It is also a strong example of the Apps + AppKit + Lakebase + DABs pattern
done with production discipline.

---

## 11. Interview-prep angles

**Q1. "How do I know my workspace follows best practices on cost, security and reliability?"**

*Cost.* Join `system.billing.usage` to `system.billing.list_prices` on `sku_name`, with
`usage_end_time >= price_start_time AND (price_end_time IS NULL OR usage_end_time < price_end_time)`. Compute:
- serverless share of spend where serverless is a choice (`billing_origin_product IN ('JOBS','ALL_PURPOSE','INTERACTIVE','SQL','DLT')`);
- job cost landing on all-purpose clusters (`usage_metadata.job_id` on non-serverless ALL_PURPOSE);
- the custom-tagged share of cost;
- Photon share of eligible spend.

Then read `system.compute.clusters` latest rows for auto-termination, autoscaling, policy and runtime ≥ 14. Guard
against duplicate price matches, mixed currencies and unpriced SKUs. Say that figures are at list price.

*Security.* From `system.access.audit`, check password `login` events (these should be SSO/OAuth) and audit freshness.
From clusters, check `data_security_mode` is a UC mode and there are no DBFS init scripts. From `lakeflow.jobs.run_as`,
jobs should run as service principals. `information_schema.tables.storage_path` should not be on `dbfs:/`. Token
policies, IP access lists and log delivery need admin APIs.

*Reliability.* Jobs should have `timeout_seconds > 0` and health rules. Warehouses should have max_clusters > min.
Formats should be Delta or Iceberg (ACID). Delta retention should give at least 7 reachable days. Check the job-run
outcomes on `lakeflow.job_run_timeline`.

Report every metric with its denominator, and say "unmeasured" when the source was unreadable.

**Q2. How does the app guarantee "not measured never becomes pass"?** Four layers:
1. The collector: `noAnswer`, a truncated result throws, a zero-row shortfall is unmeasurable (`collector.ts:835-851`, `:984-989`).
2. Resolver helpers: an unreadable signal is unmeasurable, and `bandOutcome(undefined)` is unmeasurable
   (`R/helpers.ts:114-130`, `:317-322`).
3. Scoring: `CREDIT.unmeasurable = null` removes it from the average and widens the range (`score.ts:73-81`).
4. Attestations only fill unmeasurable gaps (`resolver.ts:222`).

There are exceptions to know about (§9 items 1, 2, 5).

**Q3. Why OBO instead of the app's service principal?** Least privilege and honest findings: a user must not see the
estate through admin eyes. The cost is identity-dependent results, so comparability requires the same actor.

**Q4. How are SQL queries made injection-safe?** Values are bound as typed Statement Execution parameters
(`sql.string`/`sql.int`, `collector.ts:1028-1052`, `statements.ts:345-349`). Lists are passed as a comma-joined string and
split in SQL (`array_contains(split(:ids, ','), workspace_id)`). Identifiers (table, catalog, bucket column) go through
`quoteIdent`, which doubles backticks and refuses newlines. The Postgres schema name is regex-validated before DDL.

**Q5. What was the worst bug the authors found, and what's the lesson?** SCD2 tables filtered `delete_time IS NULL`
*before* ranking. That returned 45× the real clusters, 5× the jobs and 11× the pipelines. The lesson: rank first, filter
the lifecycle column on the chosen row. They enforced it with a static checker. (One statement may still escape it:
§9 item 3.)

**Q6. How does it scale to a large estate?**
- Result size: slicing by workspace groups, hash sub-buckets on GROUP BY keys, a byte limit that turns overflow into a
  flag, declared row bounds, and population counts via `count(*) OVER ()`.
- Load: budgets, AIMD limiter, a sequential statement loop, a statement deadline with cancel, and capped windows for
  query history.

**Q7. How does run-over-run change detection work?**
- It runs only if the stamps are comparable: same methodology, definition, catalogue span, execution mode, actor, scope,
  lookback and exclusions (`shared/api/comparability.ts`).
- The server lists per-control from→to transitions, including renamed controls (`srv/scan/changes.ts`).
- The client classes are: `new` (from absent), `regressed` (to fail or partial from anything else), `resolved` (the
  reverse) and `changed` (`cli/components/change-language.ts:103-111`). pass→unmeasurable is "changed", not regressed.
- "Excepted" is not implemented.

**Q8. How are coverage and confidence computed?**
- Coverage = answered (pass, SbA, partial, fail) ÷ applicable, where applicable = total − N/A (`cli/components/coverage.ts`).
- Confidence: ≥ 80% coverage is high, ≥ 50% moderate, else low. If more than 50% of scored findings are attested, it is
  capped one level lower (`coverage.ts:223-243`).
- The server supplies the score range, and a width of 50 or more is rendered "directional".

**Q9. How does the scheduled scan authenticate, and why two tasks?** An SP client-credentials token goes to the App URL.
The Apps proxy re-mints an OBO token limited to the app's scopes. The readiness task (0 retries) avoids paying three
serverless starts to learn a permanent refusal. The assess task retries with the same idempotency key, so it resumes the
run.

**Q10. What would you change first?** Fix §9 items 1, 3 and 5. Make resume retry transient unmeasurables. Add
`driver = FALSE` to node_utilization. Align the PE-03-06 and OE-02-03 denominators. Sign import envelopes. Record the
effective window per signal.

---

## 12. AI-stewardship angle

**Where an AI assistant would likely go wrong:**
- **SCD2 joins.** It would write `WHERE delete_time IS NULL` next to `ROW_NUMBER()`, or join clusters without
  deduplicating (a 5× multiplier on every statement, `S/workload_sql_paths.sql:35-37`). Worse, it might filter
  `change_time >= now()-30d` "to be efficient", which drops long-lived objects.
- **`billing.usage` × `list_prices`.**
  - Joining on `sku_name` alone, or on `usage_date` with `price_start_time`, produces duplicates on price changes.
  - It forgets `usage_unit`, adding DBU + DSU + GB.
  - It ignores `currency_code`.
  - It uses `product_features.is_serverless` alone. That flag is false on MODEL_SERVING and LAKEBASE, a measured
    $12,770 understatement on a $16,190 bill (`S/cost_compute_mix.sql:61-67`).
  - It classifies all-purpose by `sku_name LIKE '%ALL_PURPOSE%'`, which catches serverless Apps SKUs
    (`S/cost_compute_mix.sql:16-23`).
  - It takes one usage row instead of summing retractions (negative corrections).
- **Timelines.** It sums `setup_duration_seconds` across period rows (a 3× count), trusts `run_duration_seconds` (written
  as 0), or counts `job_run_timeline` rows as retries (it measured 0 retries where 16 of 44 runs repeated a task)
  (`S/job_run_health.sql:25-47`).
- **NULL logic.** `AND NOT (tag = 'x' OR contains(text, …))` drops every row when the tag is NULL. `sum()` over no rows
  is NULL, not 0. `percentile` should be taken over raw rows, not over per-day percentiles.
- **Dates and timezones.** `current_date() - make_dt_interval(7)` gives 8 calendar buckets
  (`S/workload_warehouse_pressure.sql:28-33`). `current_date()` depends on the session timezone. Mixing `usage_date`
  and `usage_start_time` changes the window and pruning.
- **`information_schema` semantics.** It is privilege-filtered, so zero rows is not an empty estate. `GRANT SELECT ON
  SCHEMA system.information_schema` changes nothing, and BROWSE on catalogs is what widens it
  (`app/scripts/schedule-principal.mjs:51-60`). Hive metastore tables never appear. System, samples and
  `__databricks_internal*` catalogs must be excluded.
- **Region and scope.** It would assume every table is account-global. `compute.*` and `lakeflow.*` are regional, and
  `billing.usage` and `workspaces_latest` are global.
- **Platform behaviour it would hallucinate.** It would claim the Apps SP can read token policies. It would propose
  `serving.serving-endpoints:read` (validates, grants nothing). It would use `query_tags` as a map. It would assume
  `LIMIT` on a sliced statement gives an estate top-N.

**Prompts that work well** (patterned on the repo's own discipline):
1. "Write a query over `system.compute.clusters` returning one row per *currently existing* cluster. The table is SCD2:
   rank by `change_time DESC` partitioned by `(workspace_id, cluster_id)` in one CTE, and apply `delete_time IS NULL`
   only to the rank-1 row in an outer query. Explain why filtering inside the ranked query is wrong."
2. "Compute job-attributed all-purpose spend: point-in-time join `billing.usage` to `list_prices` on `sku_name` and
   `usage_end_time` within `[price_start_time, price_end_time)`. Return `count(*) - count(DISTINCT record_id)` as
   duplicate matches, coverage per `usage_unit`, and the number of distinct `currency_code` values. Do not add different
   units. Classify serverless by flag OR product list; classify all-purpose by `billing_origin_product`, not SKU name."
3. "Given this resolver, enumerate every input for which it returns `pass`. For each, state whether the evidence could
   have been empty, privilege-filtered or truncated. Propose unit tests with synthetic empty and filtered estates."
4. "Before editing, list the denominators each control uses, and flag any two controls about the same requirement whose
   denominators differ."
5. "Rewrite this filter so it keeps rows where the tag column is NULL, and show the truth table."

**How to critically evaluate AI output here.** Demand that every share state its denominator and its empty-case
behaviour. Run the query on an empty window and on an identity with no grants. Compare row counts against the known
object count, the way the authors caught 45× with a live count. Check the query plan, not the SQL text, for repeated
scans (`S/uc_lineage_coverage.sql:21-37`).

---

## 13. Glossary

| Term | Meaning in this repo |
| --- | --- |
| Control / requirement | A catalogue entry (`C/*.yaml`), e.g. `CO-02-02`. 184 entries, 165 scored after alias collapse. |
| Pillar / principle | The 7 WAF pillars; 31 principles group the controls. |
| Provenance | `waf-docs` (113), `security-guide` (66), `extension` (5): where a control comes from. |
| Measurability | `system-table`, `rest-api`, `cloud-api`, `attestation`, `derived`. |
| Signal | One collected reading, `surface:name` (e.g. `sql:cost.compute_mix`) with status, coverage and provenance. |
| Surface | An outbound channel with its own budget: `sql`, `describe`, `rest`, `cloud`, `ai`, `plans`. |
| Reach | How far a signal sees: `account`, `metastore`, `workspace`. |
| Coverage mode | `complete` or `sampled` (examined/population/basis). |
| Resolver | A pure function from signals to a `Resolution` for one or more controls (`R/*.ts`). |
| Outcome | `pass`, `fail`, `partial`, `unmeasurable`, `not-applicable`, `satisfied-by-architecture`. |
| Unmeasured kind | `attestation`, `unreachable`, `unbuilt`, `unreadable`, `disabled`. Each has a different remedy. |
| Remedy | What would make an unmeasured control measurable (grant, re-authorise, attest). |
| Alias group | The same requirement in several pillars. Scored once per pillar at the group's worst outcome. |
| Satisfied by architecture (SbA) | The platform meets the intent (e.g. serverless has no cluster policy). Counts as a pass. |
| Precondition | A catalogue rule that makes a control N/A or SbA from a signal's `summary`. |
| Attestation | A person's answer with owner, statement, evidence URL and `reviewBy` expiry. |
| Admin-collected / import | Evidence gathered by `collect-evidence.py` under admin authority, imported as an envelope. |
| Envelope | The imported JSON: tiers, identities, probes, digest, script digest. |
| Applicability decision | A customer's `not-applicable` or `disabled` lever. Lapses if the reading turns fail. |
| Exposure | What decisions removed from, or lapsed in, a score. |
| Scan / run | A scan is the measured result. A run is its durable execution record (lease, checkpoints, attempts). |
| Stamp | Catalogue version and fingerprint, execution mode, actor, scope, lookback and identity. Decides comparability. |
| Carry-forward | Pillars not re-measured in a targeted rerun, copied from the previous comparable scan and labelled. |
| Review / pillar review / result | Human confirm or skip per pillar. The last one writes the immutable `AssessmentResult`. |
| Publication (month) | Frozen JSON and CSV bytes with a SHA-256 digest, superseded but never edited. |
| Directory | `sql:estate.workspaces`: live, same-region workspaces that filter every other statement. |
| Slice / bucket | Per-workspace-group execution, and hash sub-division of a truncated slice. |
| Customer-catalog predicate | `{{customer_catalog col}}`, expanded to exclude system, samples and `__databricks_internal*`. |
| Visibility cross-check | Privilege-filtered census versus unfiltered lineage before asserting emptiness. |
| Advisor | Workload, warehouse, job and serverless analysis (`srv/advise`). Advice only, never scored. |
| Assessor group | `WAF_ASSESSOR_GROUP`: the direct-membership gate for all mutations. |
| Lifecycle | `scripts/lifecycle.mjs`: validate/install/upgrade/rollback/uninstall over DABs with verification. |
| Preflight | A per-table `SELECT 1 … WHERE false` probe that names the grant fixing each denial. |
