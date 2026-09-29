# technical-services-solutions: the field team's accelerator monorepo

**Repo:** `databricks-solutions/technical-services-solutions` @ `41fa465` (2026-09-28). 380 files. Everything ships **as-is, without support**; the newest "track" folders (`aibi-migration/`, `dw-migration/`, `genie/`, `production-readiness/`, `unified-governance/`) are empty placeholders.
**How I studied it:** a deep-read (which ran the PBI converter's rewrite functions under sqlglot 26.33 and checked disputed behaviour against docs), with claims spot-checked at source. I reproduced the converter's fuzzy column swap myself ([`evidence/fuzzy_column_match.py`](../case-studies/evidence/fuzzy_column_match.py)). The raw report is in [`appendix/deep-read-reports/technical-services-solutions.md`](../appendix/deep-read-reports/technical-services-solutions.md).

**Why it matters for the interview:** it covers the platform decisions that are expensive to change later (network, identity, metastore, storage, governance, CI/CD), plus the most instructive AI-application bug class in the set: **"repair" code that turns a loud failure into a silent wrong answer.**

## 1. What's in it

| Area | Projects | Maturity |
|---|---|---|
| **Workspace setup** | Terraform for AWS (BYO-VPC ± UC, classic PrivateLink, serverless + NCC), Azure (VNet injection ± UC, PrivateLink), GCP (BYO-VPC, shared VPC, PSC); Pulumi Azure; PowerShell managed-VNet → VNet-injection | substantial (flat, teachable roots) |
| **Governance** | Unity Catalog **ABAC** (governed tags + Data Classification + tag-matched policies); AIM user-ownership inventory before identity cleanup | substantial (demo) |
| **Data engineering** | Lakeflow Connect SQL Server CDC bundle; a network pre-flight validator notebook (DNS → TCP → TLS → hand-written TDS login); SDP schema-drift handling (Auto Loader rescue → reconcile) | partial–substantial |
| **Warehousing / BI** | UC **metric views** semantic layer (semi-additive windows, materialisation); LLM-powered **Power BI → AI/BI** converter (Streamlit on Apps) | substantial |
| **CI/CD** | Customer-360 bundle deployed by 4 CI systems; **dabs-migrator** agent skill (UI assets → bundle repo); OrderFlow (Apps + Lakebase + SDP) | substantial |

## 2. The implied reference architecture (read the repo as one design)

1. **Account layer:** SSO + SCIM/AIM; groups for every role; automation through **OAuth M2M service principals** (no PATs); **one metastore per region, owned by an admin group**, in its own IaC state.
2. **Network per workspace:** BYO VPC/VNet with secure cluster connectivity (no public IPs); back-end PrivateLink/PSC for REST and relay; **egress denied by default** (AWS SG egress to the VPC CIDR + S3 prefix list; Azure service-endpoint policy + DBFS firewall); private DNS; **an NCC for the serverless plane**, which your VPC does not cover.
3. **Data and governance:** catalogs per domain or environment, each on its own storage via storage credentials and external locations; grants to groups; governed tags + ABAC for PII; cluster and budget policies; audit logs and system tables; CMK if regulated.
4. **Delivery:** Git → PR `bundle validate` → deploy staging as an SP → approval → deploy prod as an SP (`run_as` SP, `permissions` block, `root_path` under `/Shared`); remote, locked Terraform state.

**Order of operations for an AWS UC catalog** (the canonical trace): IAM cross-account role → 30 s IAM wait → credentials/storage/network configs → workspace → 120 s wait → metastore assignment → **storage credential first** (so its external ID exists) → trust policy generated from that external ID ("self-assuming role") → 60 s wait → external location → catalog with `storage_root`.

## 3. Patterns worth stealing

| Pattern | Where | Why |
|---|---|---|
| **Pure mask/filter functions; "who" lives in the policy** (`TO`/`EXCEPT`) | ABAC demo | Separates *what* is masked from *who* is exempt. Admins are governed unless explicitly excepted |
| **ABAC scales O(policies), not O(tables × rules)** | ABAC README | Governance attaches automatically when a column is tagged; Data Classification makes tagging automatic |
| **`databricks_grants` (authoritative) vs `databricks_grant` (additive)** | serverless NCC example | The plural revokes anything unlisted, including the deploying SP's implicit privileges if applied at the wrong time |
| **Poll-then-patch for eventually consistent APIs**, `coalesce(unknown, lookup)` for single-apply convergence | S3 private-endpoint rule | The rule appears before the VPCE exists and only goes ESTABLISHED after a bucket policy names it |
| **Wrap untrusted SQL as `SELECT * FROM (<sql>) _t LIMIT 0`** to validate it; allow-list identifiers before quoting | PBI converter | Can't execute DDL/DML; validates columns without scanning data |
| **Short-lived DB credentials per connection, pool recycled below the token TTL** (45 min < 1 h) | OrderFlow | Lakebase OAuth tokens expire hourly |
| **Rescue, then reconcile** schema drift, as a tested pure function | sdp-evolution | Survive renames and new columns without a full refresh |
| **Job-scoped `run_as` when a bundle contains Apps** | OrderFlow | Apps must run as their owner; a bundle-wide `run_as` fails |
| **Agent runbooks with PAUSE gates; skills with a "why" changelog** | Lakeflow Connect RUNBOOK, dabs-migrator | "Validation is necessary but not sufficient: a bundle isn't 'done' until it deploys" |
| **Report-only first, act later** | AIM inventory | Inventory ownership before deleting identities |

## 4. What I found (status-tagged)

| # | Finding | Status |
|---|---|---|
| 1 | **PBI converter "repair" layer changes semantics silently:** aggregate promotion drops `HAVING` and aggregate `ORDER BY` but keeps `LIMIT` (top-N becomes N arbitrary raw rows); the fuzzy column fix swaps in a *different* real column: `unit_cost→unit_count`, `order_date→order_rate`, `customer_name→customer_id` | CONFIRMED: rewrite reproduced by the deep-read; column swap reproduced by me |
| 2 | Converter validation is displayed but **doesn't gate publish**, and publish omits `embed_credentials` (API default `true`), so **viewers query as the app SP**: viewer-aware row filters and masks evaluate for the SP. PBI RLS roles are never parsed | CONFIRMED (deep-read) |
| 3 | The DAX→SQL cookbook the LLM is given has wrong translations (e.g. `DATEADD(-1, YEAR)` becomes "last 12 months from today"); correctness is checked for *executability*, never numeric equivalence | CONFIRMED (deep-read) |
| 4 | Root `.gitignore` `*conf*.json` ignores `tsconfig.json`, so OrderFlow's frontend build fails from a clean clone (`TS5083`) | CONFIRMED by me (`git check-ignore -v`) |
| 5 | Customer-360 metric view **sums snapshot measures** (`account_count`, `arr_total`) across a daily spine: any multi-day slice multiplies them. They need semi-additive windows | CONFIRMED (deep-read) |
| 6 | AIM inventory: a failed scan section prints `[skip]`, yet the user is still listed as having **no objects**, a false "safe to delete" | CONFIRMED (deep-read); [case 03](../case-studies/03-fail-open-patterns.md) pattern |
| 7 | Terraform: no remote backend anywhere (local, unlocked state); a region-wide metastore created inside a per-workspace stack with `force_destroy = true` | CONFIRMED (deep-read) |
| 8 | Serverless NCC bucket policy is an **Allow** with `Principal:*`, `s3:*`, conditioned only on `aws:SourceVpce`. The README's "only the Databricks VPC endpoint can reach the bucket" is wrong: an Allow restricts nothing | SUSPECTED impact (deep-read) |
| 9 | Lakeflow Connect gateway bundle omits `continuous: true`, and the runbook waits for the gateway to "complete"; the docs say gateways must be continuous, since a stopped gateway can lose changes once the source log truncates | CONFIRMED divergence / SUSPECTED impact |
| 10 | OrderFlow CI masks job failure with `|| true` and never runs `bundle run <app>`, so new app code isn't rolled out | CONFIRMED (deep-read) |

## 5. How it scales

- **Terraform:** one flat root is one workspace. For 50 workspaces: split account-level singletons (metastore, NCC, groups) into their own state; wrap per-workspace roots in modules with `for_each`; remote state with locking; policy-as-code (checkov/OPA). The README points to the SRA templates for that rigour.
- **ABAC:** O(policies) instead of O(tables × rules). Limits: tag hygiene (governed-tag `ASSIGN`), per-row predicate cost (drive tenant mapping from a table, not `CASE` literals).
- **PBI migration:** one report per LLM call, sequential. For an estate: a job/queue, dedup of shared semantic models (convert once into **metric views**), numeric reconciliation against PBI, and human review queues.
- **Lakeflow Connect:** one gateway per source database, continuous on classic compute; limits are source CDC log retention vs gateway uptime, tables per pipeline, gateway sizing.

## 6. How I'd explain it

- **Executive:** "A repeatable blueprint for a private, governed Databricks estate in days, not months, plus accelerators for the moves customers make next: managed CDC ingestion, one KPI layer for BI and AI, and bringing UI-built work under version control."
- **Platform engineer:** "Account provider for account objects, workspace provider for UC. Back-end PrivateLink plus restricted egress; an NCC for serverless. You add a remote backend, modules, cluster policies, CMK and grants before prod."
- **Internal stakeholder:** "Great for onboarding and security reviews. Position the PBI converter as '70% draft + review', not push-button migration, and fix its silent repairs before large pilots."

## 7. Interview angles

1. **"How do you implement row-level security in UC?"** Per table: a BOOLEAN SQL UDF + `ALTER TABLE … SET ROW FILTER`. At scale: governed tag → tag the column → `CREATE POLICY … ROW FILTER … TO … EXCEPT … FOR TABLES MATCH COLUMNS has_tag_value(…)`. Test as a non-admin; admins aren't exempt without `EXCEPT`; watch dashboards published with embedded credentials.
2. **"How do you make AI-generated SQL safe to execute?"** Wrap as `SELECT * FROM (<sql>) LIMIT 0`; least-privilege identity; allow-list identifiers; **prefer failing over auto-fixing semantics**; verify results numerically against a reference.
3. **"The deploy passed `bundle validate` but failed in prod. Why?"** Validate checks schema and variable resolution; deploy-time API checks catch empty optional blocks, ID formats and name constraints. Validate every target; Genie spaces need their tables at deploy time. Deploy to dev in CI.
4. **"How does serverless reach private storage if it isn't in my VPC?"** A Network Connectivity Configuration with private-endpoint rules; allow the endpoint in the bucket policy (and scope it by principal, unlike this repo).
5. **"Why metric views?"** Measures defined once with correct aggregation semantics (ratio of sums, semi-additive windows), governed in UC, with synonyms for Genie. Finding 5 is the counter-example.

## 8. AI-stewardship angle

- **The converter lesson:** deterministic "repair" around an LLM is the most dangerous code in the app. Fuzzy matching, HAVING removal and CTE rewriting each turned an error (which someone would have fixed) into a plausible wrong dashboard. Rules: unit-test every rewrite with adversarial SQL; fail closed; gate publish on validation; reconcile numbers against the source.
- **Contradictory knowledge docs in one prompt** produce nondeterministic behaviour. Keep one authoritative instruction per topic.
- **An agent following a wrong runbook does the wrong thing faithfully** (the gateway "wait for COMPLETED"). Cite the doc behind each behavioural claim in a runbook.
- **Check what the AI scaffolding actually committed:** one broad ignore rule silently dropped the files a Vite project needs. Build from a clean clone in CI.
