# Platform fundamentals: setting up a customer's Databricks platform

Distilled from starter-journey (the field team's runbook) and technical-services-solutions (its Terraform, governance and CI/CD accelerators), plus general platform practice where both repos are silent (marked *general practice*; confirm against current docs). See [`repos/starter-journey.md`](../repos/starter-journey.md) and [`repos/technical-services-solutions.md`](../repos/technical-services-solutions.md).

## 1. Decisions that are expensive to change later (settle in week 1)

| Decision | Why it's expensive later | Default recommendation |
|---|---|---|
| Cloud tenant layout (single vs multi) | Moving workspaces and IAM between accounts is a migration | Single-tenant unless billing, IAM or a regulator demands a wall; write down what would trigger a change |
| Region | A workspace can't move region; data gravity and egress follow | The region where the data lives |
| Workspace type and networking | Re-platforming means new workspaces and re-pointing every job | Serverless by default; classic (BYO VPC/VNet) when you must own the network; Private Link / SRA when traffic must stay private |
| Number of workspaces | Sprawl is admin overhead; one-for-all means untested jobs can hit prod | Three: dev, staging, prod. Teams are groups, not workspaces |
| Catalog / schema / group naming | "Rewriting every reference" | Catalog per environment (and per BU if needed), `[project]_bronze/_silver/_gold` schemas, one written convention, enforced |
| Group model | Splitting a flat group is a re-grant migration | Account-level persona groups via SCIM; BU prefixes before growth |
| Metastore owner | A departed person-owner blocks governance | A group (`metastore-admins`), never a person or SP |
| Tagging standard | Tags are forward-only: past spend stays unattributable | `team`, `project`, `env` on day zero; compute policies that *require* tags |
| Managed storage location per catalog | Moving managed data means copying tables | A new bucket/container per environment for managed tables and volumes |
| Repo-per-project and CI identity | Untangling a monorepo later is costly | One repo = one bundle = one team; service principals deploy |
| CDC gateway continuity | Downtime past log retention forces a full refresh | Never stop the gateway; monitor it |

## 2. Account and identity

- Account console for account-level things (workspaces, identity, metastores, billing, SSO/SCIM); workspaces for data work.
- **SCIM** from the IdP (Azure: automatic identity management). If users were added by hand first, match on email or you get duplicates.
- **Groups at account level**, never workspace-local. **Grant to groups, not people.** One admin group per workspace.
- **SSO is authentication, not authorisation:** users still need workspace assignment.
- **Service principals with OAuth M2M** for automation; only SP-run automation writes to prod; no PATs for CI.
- Account admin is not workspace admin; grant it sparingly.

## 3. Unity Catalog

- **Everything goes through UC:** no hardcoded credentials in notebooks, no cluster-level environment-variable access. Both bypass audit and revocation.
- **One metastore per region**, shared by that region's workspaces, owned by a group, with auto-assignment for new workspaces.
- **Environment catalogs bound to their workspaces** (the prod workspace sees only prod). "Workspaces don't isolate data on their own."
- **Storage:** storage credential (the key) + external location (the door). Source locations read-only. A new bucket per environment for managed storage.
- **Privileges:** path privileges (`USE CATALOG`, `USE SCHEMA`) plus object privileges. **Grant at schema level** (Data Reader / Data Editor presets); per-table grants "break the moment someone adds a new table".
- **Ownership ≠ privilege:** transfer ownership of credentials, locations, catalogs and schemas to the admin group; grant working privileges separately.
- Terraform: `databricks_grants` (plural) is **authoritative** and revokes anything unlisted; `databricks_grant` (singular) is additive. New catalogs created by the TSS templates have **no grants**.
- **Fine-grained access:** ABAC: governed tags (+ automatic Data Classification) → masking / row-filter UDFs → one policy per schema or catalog with `TO … EXCEPT`. Needs DBR 16.4+ or serverless. Admins aren't exempt unless excepted. Mask functions stay pure; "who" lives in the policy.
- Managed tables by default (UC owns files and lifecycle; enables predictive optimization). External tables when other engines or a lifecycle you control require it.

## 4. Networking (classic and serverless)

- Classic: BYO VPC/VNet, secure cluster connectivity (no public IPs), back-end PrivateLink/PSC for REST and relay, **egress denied by default** (AWS: SG egress to VPC CIDR + S3 prefix list; Azure: service-endpoint policy + DBFS firewall).
- **Serverless is a separate network plane:** reaching private storage needs a **Network Connectivity Configuration** with private-endpoint rules (approved on Azure), and the bucket/storage policy must allow that endpoint. Scope bucket policies by principal too, not only by `aws:SourceVpce` (TSS finding).
- Terraform order for an AWS UC catalog: IAM role → workspace → metastore assignment → **storage credential first** (its external ID feeds the trust policy) → IAM propagation wait → external location → catalog.
- Remote, locked Terraform state; account-level singletons (metastore, NCC, groups) in their own state; no `force_destroy` outside sandboxes.

## 5. Compute and cost

- Serverless first (workspaces, SQL warehouses, jobs, pipelines). SQL warehouse: start 2X-Small, auto-stop ~10 min.
- Classic where you must be in the customer network (the Lakeflow Connect CDC gateway) or pin hardware.
- *General practice:* scheduled production work on job compute or serverless jobs; all-purpose clusters for interactive work, with auto-termination. WAF flags job cost landing on all-purpose clusters.
- **Cost visibility on day zero:** usage dashboard; tags + serverless usage (budget) policies + compute policies that require tags; account budgets with thresholds (they alert, **don't throttle**, lag up to 24 h, list price). Truth source: `system.billing.usage` × `list_prices` ([system-tables cheatsheet](system-tables-best-practice-checks.md)).
- Runtime gates: metric views need DBR 17.3+; ABAC needs 16.4+.

## 6. Ingestion and pipelines

- **Lakeflow Connect** managed connectors for databases and SaaS, credentials in a UC connection.
- **CDC vs query-based:** CDC captures every change with low source load via an always-on gateway (classic compute, in the customer network) and must never be down longer than log retention. Query-based polls a cursor (serverless, needs NCC for private sources): simpler, latest state only, needs a cursor that changes on every update and is never NULL (index it).
- **Auto Loader** for files, with file events (notification mode) at scale. *General practice:* `COPY INTO` for simple idempotent SQL batch loads.
- **Spark Declarative Pipelines:** bronze as landed (the replay point), silver cleaned/deduplicated/conformed with expectations, gold as MVs and metric views. Streaming tables for incremental ingest and CDC (AUTO CDC with `sequence_by`), MVs for aggregates.
- **Lakeflow Jobs** for orchestration; prototype in the UI, productionise in a bundle.
- Schema drift: fixed bronze schema + rescue (`_rescued_data`) + a tested reconcile function in silver (TSS `sdp-evolution`).

## 7. Semantic layer and BI

- **Metric views** in gold define each KPI once (measures, dimensions, joins with stated cardinality, synonyms, semi-additive windows). Reconcile against a known-good query before publishing; check joins are many-to-one.
- Dashboards bound to the metric view (no widget-local SQL). Sharing: "Only people with access can view" keeps per-viewer row/column rules; "Embed your credentials" runs as the publisher.
- **Genie:** topic-specific spaces over curated, commented data (ideally metric views); short instructions (synonyms, default time axis, ranking rules); benchmark questions with gold-standard SQL; access runs as the **viewer**, so grants still apply. Partner-powered AI features must be on.

## 8. ML and apps (thin in the repos)

- MLflow 3 with the UC registry: 3-level model names, signature + input example, promote by **alias** (champion/challenger); batch-score via Spark UDF by alias.
- Feature tables in UC with point-in-time lookups (no leakage).
- Databricks Apps: app service principal for app-owned resources; **OBO** (`x-forwarded-access-token`, least-privilege `user_api_scopes`) so queries run with the user's grants; build the user client per request. Lakebase OAuth DB tokens expire hourly: mint per connection, recycle the pool below the TTL.

## 9. CI/CD

- **Terraform for anything outside a workspace, DABs for anything inside it.**
- One repo = one bundle = one team; trunk-based development.
- PR → `bundle validate` (every target) → deploy to dev → tests → staging → prod with approval, deploying as an SP (OAuth M2M, secrets in the CI store). Prod: `mode: production`, `root_path` under `/Shared`, `run_as` an SP, explicit `permissions`.
- `bundle run` doesn't sync code: always deploy first. Removing a resource block destroys the resource. Validation is necessary but not sufficient: "a bundle isn't done until it deploys".
- Pin CLI and action versions; protect the prod environment.

## 10. The first 90 days (starter-journey, re-sequenced)

| Days | Outcomes |
|---|---|
| 0–10 | Decision record for the §1 table; dev/staging/prod workspaces; SCIM + groups + SSO; group-owned metastore; **cost guardrails before the first workload** (tags, policies, budgets) |
| 10–35 | Storage credentials/locations per environment; the governance skeleton (bound catalogs, medallion schemas, ownership to admin groups, schema-level grants); one Lakeflow Connect source; the first pipeline + warehouse answering one real, reconciled business question, scheduled as a job |
| 35–60 | ABAC on sensitive domains; the first metric view (reconciled); a dashboard + Genie space for a pilot group |
| 60–90 | Everything into a DAB with CI/CD deploying as SPs; ML registry if in scope; an operational review from system tables (budget vs actual, untagged spend, access review) |

## 11. Troubleshooting index (condensed from starter-journey's "Where people trip")

| Symptom | Likely cause |
|---|---|
| "Serverless workspaces" option missing | Not an account admin, or unsupported region |
| Azure: serverless type not offered | Pricing tier isn't Premium |
| Terraform `User is not an owner of Metastore` | The SP needs metastore admin or `CREATE CATALOG ON METASTORE` |
| Duplicate users after SCIM | Users were added by hand earlier; match on email |
| SSO works, workspace inaccessible | Authentication ≠ authorisation: assign the user/group to the workspace |
| External-location test fails | Cloud identity lacks rights on the path, or (serverless only) no approved NCC endpoint |
| Usage dashboard shows permission denied | No `SELECT` on `system.billing.*` |
| Serverless usage has no tags | Classic tags don't apply: use a serverless usage policy |
| Query-based ingestion misses updates | Cursor doesn't change on every update, or is NULL |
| Metric view totals inflated | One-to-many join fan-out |
| Shared Genie user gets empty answers | The viewer lacks `SELECT` (Genie runs as the viewer) |
| ABAC query fails | Runtime older than 16.4 |
