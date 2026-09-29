> **Provenance.** Deep-read of `databricks-solutions/starter-journey` @ `ac21559`, written by a research sub-agent during this study and kept verbatim, apart from local paths normalised to `<clone-root>/`. Its CONFIRMED / SUSPECTED labels are the agent's. The claims I re-verified myself, and how, are listed in [`README.md`](README.md); anything not listed there I have not independently checked.

# starter-journey: deep-read report

**Repo:** `databricks-solutions/starter-journey`, read-only clone at `<clone-root>/starter-journey`, commit `ac21559` (2026-09-24, "docs: tighten Genie Ontology continuity, rename Operations, and switch classic prompts to AI Platform Kit (#97)"). The clone is shallow (one commit), so I could not diff PR #97 locally, and the GitHub MCP tool is not authorised for this repo in this session.
**Read in full:** `sidebars.ts`, `docusaurus.config.ts`, all 62 doc pages, 4 blog posts, `AGENTS.md`, `docs/STYLE.md`, both skills, the freshness script, 2 shell scripts, 3 workflows, and the custom React components (`StepGuide`, `PromptBlock`, `StarterJourneyProgress`, `Button`). I extracted text from all 5 PDF decks using a stdlib-only extractor in the scratchpad. I viewed 6 diagrams whose captions matter.
**Checks run (read-only; the repo was not modified):** the freshness script at several dates and on edge-case CSV copies in the scratchpad; a static resolver for all 284 internal `/docs/...` links and all 269 image references (all resolve); a walk of the "Do next" chain; a grep for style-rule violations.

**Citation conventions.** A plain path such as `02-account-workspaces/activate-sso.mdx` is under `docs/starter-journey/docs/`. The prefix `repo:` means the repo root (`repo:AGENTS.md`), and `site:` means `docs/starter-journey/` (`site:sidebars.ts`, `site:static/pdfs/...`). `L<n>` is the line number at `ac21559`, and `§` marks a heading. **CONFIRMED** means I verified it in the files, **SUSPECTED** means it is likely but not verified, and **(inferred)** means it is my reasoning or general Databricks knowledge that this repo does not state.

---

## 1. What it is (customer framing)

Starter Journey is a free, opinionated runbook written by Databricks field engineers ("Bricksters… who have set up hundreds of customer accounts", `site:src/components/HomepageFeatures/index.tsx`). It takes an organisation from an **empty Databricks account to a governed, cost-visible, CI/CD-ready platform**, one dependency at a time (`site:docusaurus.config.ts` tagline). It runs in 7 stages, in the order things depend on each other (`01-introduction/index.mdx` L14-24): Introduction (concepts plus the cloud-tenant decision), Account and workspaces (workspaces, identity, SSO, metastore ownership, day-zero cost controls), Data access and ETL (storage, managed connectors, first pipeline, SQL, jobs), Governance (groups, ownership, catalog layout, ABAC), Genie Ontology (metric views, dashboards, Genie Agents, a routing tree for natural-language BI), Data science (MLflow and UC model registry, batch inference, feature tables), and Operations and CI/CD (Terraform for infrastructure, Declarative Automation Bundles for workspace projects). Most technical pages are click-by-click screenshot guides that end in something working. They are cross-linked to short "Field Notes" pages that explain the decision behind each step (`repo:docs/STYLE.md` L8-11). One sample dataset, Databricks' `samples.bakehouse`, runs from the first pipeline through to a Genie One question. The guide also leans on AI help: Genie Code prompts build the pipeline, SQL, metric view and dashboard, and "AI Platform Kit" prompts have a coding agent generate the Terraform for classic workspaces, with human approval gates. It is provided **as-is and is not formally supported** by Databricks (`repo:README.md` §Project Support).

---

## 2. Curriculum map

The sidebar is managed by hand (`site:sidebars.ts`) and has 7 top-level categories. The page types are my labels (inferred): **BL** = Build Log (uses `StepGuide`), **FN** = Field Notes (concept page), **Stub** = placeholder or link-only.

| # | Stage (sidebar label) | Pages in sidebar order (type) | Learning objective: what you have at the end | Source |
|---|---|---|---|---|
| 1 | **1. Introduction** | `index` (FN) · Foundations: `index`, `account-console`, `workspace`, `unity-catalog`, `recap-and-learning` (all FN) · Cloud tenant ready: `index`, `single-tenant-setup`, `multi-tenant-setup` (FN) | A mental model of the three building blocks (account console, workspace, Unity Catalog), plus a decision on single-tenant or multi-tenant layout, made before anything is deployed | `01-introduction/index.mdx` L32; `foundations/index.mdx` L18 |
| 2 | **2. Account and workspaces** | `index` · Create workspaces: `index` (FN) → AWS/Azure/GCP × {`serverless` (BL), `classic` (BL plus AI Platform Kit prompt), `private-link` (Stub: SRA links)} · Add users: `manual`, `scim` (BL) · Add groups: `manual`, `scim` (BL) · `metastore-admins/set-admin-group` (BL) · `activate-sso` (BL) · Workspace settings › Cost monitoring: `index` (FN), `import-usage-dashboard`, `additional-dashboards`, `tag-compute-and-jobs`, `budget-alerts` (BL) | dev/staging/prod workspaces; account-level users and groups synced by SCIM; SSO; a **group** that owns the metastore; usage dashboards, tags and budgets from day zero | `01-introduction/index.mdx` L33; `02-account-workspaces/index.mdx` L16 |
| 3 | **3. Data access and ETL** | `index` (FN) · Cloud object storage: `index` (FN), `aws`, `azure`, `gcp` (BL) · Databases and SaaS ingestion: `index` (FN), `cdc`, `query-based`, `dabs-definition` (BL) · `build-first-pipeline/index` (BL, Genie Code) · `query-and-explore` (BL, Genie Code) · `orchestration/index` (FN plus video) | Governed paths to cloud storage (storage credential plus external location), Lakeflow Connect ingestion, a bronze/silver pipeline built with Genie Code, a serverless SQL warehouse, a saved query, and the concept of scheduled jobs | `01-introduction/index.mdx` L34 |
| 4 | **4. Governance** | `index` (FN) · `groups` (FN) · `uc-assets-ownership` (BL) · `small-organizations`, `medium-large-organizations` (FN) · `unity-catalog-setup` (**Stub: "work in progress"**) · ABAC: `index` (FN), `lab` (hands-on SQL lab, ~55 min) | Persona groups, group ownership of UC assets, a catalog/schema/grant pattern sized to the organisation, and tag-driven column masks and row filters | `01-introduction/index.mdx` L35 |
| 5 | **5. Genie Ontology** | `index` (FN) · `metadata-generation` (**Stub**) · `metric-views` (BL) · `dashboards` (BL) · `genie-agents` (BL) · `domains-subdomains-pages` (BL) | One governed metric view, `franchise_sales_metrics`, feeding an AI/BI dashboard and a Genie Agent, plus a Discover domain → subdomain → page tree that lets Genie One route a question to the right surface | `01-introduction/index.mdx` L36; `05-genie-ontology/index.mdx` L14-47 |
| 6 | **6. Data science** | `index` (FN plus MLOps video) · `save-model-to-unity-catalog.md` · `batch-inference.md` (link table only) · `prepare-datasets` (BL: dbdemos `feature-store`) | Models registered in UC with MLflow 3 (train, Volume, or Hugging Face), inference patterns, feature tables; the three Ops layers (DataOps, ModelOps, DevOps) | `01-introduction/index.mdx` L37; `06-data-science/index.mdx` L16-22 |
| 7 | **7. Operations and CI/CD** | `index` only (FN plus 4 videos) | The dividing line: Terraform for anything outside a workspace, DABs for anything inside it; one repo per project; trunk-based development; a GitHub Actions deploy | `07-operations/index.mdx` L16, L29-32, L157 |
| – | Blog and decks | 4 blog posts, all LinkedIn or Medium embeds; 5 PDFs in `site:static/pdfs/`, only **2 linked** (Cheatsheet 2026 from Foundations, UC Best Practices from Governance) | Reference material | `site:blog/*.mdx`; see §8 G18 |

**The Bakehouse thread.** This is the continuity that PR #97 "tightened". Each artifact is created once and reused downstream:

| Artifact | Created in | Consumed in |
|---|---|---|
| `starterjourney_catalog.bakehouse_bronze` / `bakehouse_silver` (pipeline `bakehouse_e2e_pipeline`) | `03-data-access-etl/build-first-pipeline/index.mdx` L32-54 | query-and-explore, metric-views |
| Silver column contract: `transaction_timestamp`, `total_price` (transactions); `franchise_id`, `franchise_name` (franchises) | build-first-pipeline tip, L78-80 | query-and-explore L107; metric-views L66 |
| Serverless SQL warehouse `starter_journey_wh` (2X-Small, auto-stop 10 min, 1/1 clusters) | `03-data-access-etl/query-and-explore.mdx` L39 | metric-views L35; genie-agents L51 |
| Saved "daily franchise revenue" query | query-and-explore L166-170 (it is never given a name) | metric-views L148 (calls it `daily_franchise_revenue`) |
| Metric view `starterjourney_catalog.bakehouse_gold.franchise_sales_metrics` | `05-genie-ontology/metric-views.mdx` | dashboards, genie-agents, domains |
| Dashboard "Bakehouse Franchise Performance" | `05-genie-ontology/dashboards.mdx` | domain page "Franchise Performance at a Glance" |
| Genie Agent "Bakehouse Sales Assistant" | `05-genie-ontology/genie-agents.mdx` | subdomain page "Sales Q&A Assistant" |
| Domain "Bakehouse Sales Operations" › subdomain "Sales Analytics" | `05-genie-ontology/domains-subdomains-pages.mdx` | Genie One tests |

**How the site shows progress (a code-stewardship detail).** Every section index renders `<StarterJourneyProgress currentLevel={N}/>`. `site:src/components/StarterJourneyProgress/journey-blocks.ts` defines 7 blocks at levels 0-6 (`MAX_LEVEL = 6`). `getBlockState()` marks a block completed, current or pending by comparing levels. It still carries "fork column" logic (`"da" | "ml" | "genai"`) for parallel tracks at one level, but no block uses it any more. That is vestigial code from an older layout, which `repo:AGENTS.md` L346 still describes ("like section 6").

---

## 3. Page-by-page digest (grouped by stage)

Each page uses the same labels: **C** = key concepts, **Do** = recommendation (with the reason the page gives), **Code** = snippets, **Trip** = gotchas and warnings, **AI** = prompts. Every page ends with a `## Next` block (Do next / Learn why / Reference), which the style guide requires (`repo:docs/STYLE.md` §Shared chrome).

### Stage 1: Introduction

**`01-introduction/index.mdx`** (FN, ~10 min)
- **C:** Build in dependency order. "Every dashboard, model, and agent reads data from the same platform and catalog. If the tables are wrong, reports mislead, models train on noise, and agents return unreliable answers" (L15-16). BI, ML and AI have different serving needs but share the account, governance and trusted data, so "Fix those layers once, then build each workload on top" (L18-20). The "What you'll build" table (L28-38) is the canonical outcome list; `repo:AGENTS.md` §Journey overview table sync wants it kept in sync with the sidebar.

**`01-introduction/foundations/index.mdx`** (FN, ~15 min)
- **C:** Three building blocks: account console, workspace, Unity Catalog. "Get one wrong and you'll be paying to unwind it after resources are already running" (L18).
- **Do:** Everyone on the project reads the **Databricks Cheatsheet 2026** deck before any infrastructure work (L22-24). From my partial text extraction of `site:static/pdfs/Databricks-Cheatsheet-2026-Ready.pdf` (a Canva LinkedIn carousel dated "Jan 06"), it defines the whole product surface in one line each. Governance: UC, metric views, RBAC and ABAC access control, lineage, anomaly detection, governed tags, data classification. SQL: DBSQL, SQL Editor, Lakehouse Federation (query federation vs catalog federation). Compute: serverless, classic, SQL warehouse, serverless GPU, Lakebase (managed Postgres OLTP). Lakeflow: Connect, Spark Declarative Pipelines, Jobs, Auto Loader, Designer, Real-Time Mode, Zerobus. Sharing: Delta Sharing, Clean Rooms, Marketplace, Partner Connect, Private Exchanges. BI: AI/BI Genie, AI/BI Dashboards, Databricks Apps, Databricks One. ML: MLflow, AutoML, Feature Store, ML Runtime. AI: Mosaic AI, Model Serving, Foundation Model Serving, Vector Search, Agent Framework, Agent Evaluation, Agent Bricks (Beta). Other: Lakebridge, Solution Accelerators, external MCP servers. Exact wording is (inferred) because the extraction dropped glyphs.

**`01-introduction/foundations/account-console.mdx`** (FN, ~5 min)
- **C:** The account console is the control plane above all workspaces, "to Databricks what the AWS console, Azure portal, or GCP cloud console is to your cloud provider" (L16). It owns workspaces, UC metastores, users/groups/service principals, billing and budgets, and SCIM and SSO (L24-30). "One account can own many workspaces. Each workspace in a region attaches to one metastore" (L38).
- **Do:** Keep account-level changes in the account console and do data work (notebooks, jobs, queries) in a workspace (L14, L42-44).
- **Trip:** Account admin and workspace admin are different roles. Granting account admin to someone who only needs a workspace over-privileges them (L48-50).

**`01-introduction/foundations/workspace.mdx`** (FN, ~5 min)
- **C:** A workspace is a region-scoped environment that bundles compute, storage references, code and permissions (L16). It contains notebooks and repos, jobs, pipelines, clusters and SQL warehouses, dashboards, and MLflow experiments and models (L24-31).
- **Do:** "Start with three workspaces (dev, staging, prod) and resist the urge to spin up one per team" (L14). Add teams as groups (L46), or give a BU its own workspaces and catalogs only if required (tip, L48-50).
- **Trip:** "Workspaces don't isolate data on their own… A workspace can reach any data its attached metastore governs, subject to grants" (L54). One workspace for everything means "an untested job can take down production pipelines" (L60). One workspace per team means admin overhead and harder collaboration (L64).

**`01-introduction/foundations/unity-catalog.mdx`** (FN, ~5 min)
- **C:** UC sits between the workspaces and the data lake. Every create, read, update, delete or run on a table, view, volume, function or model is checked against grants (L48). Data stays in the customer's cloud account: "UC never moves data out. It only governs access to it" (L23). Key terms (L66-72): **one metastore per region per account**, catalogs map to an environment or domain, and so on.
- **Do:** "Route everything through Unity Catalog… Default to it even when a quick experiment doesn't strictly need it" (L17). The payoff is fine-grained access, full lineage and an audit trail "without extra work" (L52).
- **Code (L33-44, verbatim):**
```sql
-- catalog.schema.table
SELECT * FROM my_catalog.my_schema.my_table;

-- Example: select the gold table "sales" from the galaxy project in the dev catalog
SELECT * FROM dev.galaxy_gold.sales;

-- Set defaults to shorten queries
USE CATALOG dev;
USE SCHEMA galaxy_gold;
SELECT * FROM sales;
```
- **Trip:** Hardcoded credentials in notebooks cannot be audited or revoked by UC (L58). Cluster-level data access through external libraries and environment variables creates dependencies that lineage cannot see (L62).

**`01-introduction/foundations/recap-and-learning.mdx`** (FN, ~3 min): a self-quiz. Its `:::danger` repeats the two anti-patterns: hardcoded credentials, and cluster-level access through environment variables, because both "bypass UC governance" (L48-53). It also answers "how do I isolate data between workspaces? You don't, at least not at the workspace level" (L32-33).

**`01-introduction/cloud-tenant-ready/index.mdx`** (FN, ~5 min)
- **C:** A tenant is one AWS account, one Azure subscription or one GCP project, "the building your workspaces live in" (L19-20).
- **Do:** "If you have one cloud account and no compliance rule forcing you to split, go single-tenant" (L15). Go multi-tenant only for "a real boundary: separate billing, separate network and IAM, or a regulator who put it in writing" (L16). The reason: "Most teams overestimate how much separation they need, and the layout is painful to unwind once workspaces are live" (L17).
- **Trip:** Splitting too early buys overhead because UC already isolates data (L47-49). Not splitting when you should means one bad IAM policy or "a runaway Spark job can take prod down" (L53).

**`01-introduction/cloud-tenant-ready/single-tenant-setup.mdx`** (FN): all three workspaces and their IAM roles, buckets and networking sit in one account. Isolation comes from workspace boundaries plus UC grants (L30). **Do:** "Write down the decision and the conditions that would trigger a move to multi-tenant" (L46).

**`01-introduction/cloud-tenant-ready/multi-tenant-setup.mdx`** (FN): one workspace per cloud account (dev/staging/prod table, L32-36). "Unity Catalog metastores can span accounts within the same Databricks account, so governance stays centralized" (L38). **Trip:** Connect every workspace to the same Databricks account or you get governance silos (L50). "Use Terraform or another IaC tool from day one" because hand-built accounts drift (L54). Split by environment or compliance boundary, **not by team** (L58).

### Stage 2: Account and workspaces

**`02-account-workspaces/index.mdx`**: "Do this part in order, and do it before anyone starts loading data" (L16). The order is Create workspaces → Add users → Add groups → Set admin group → SSO (L24-28). The cost-monitoring subsection is not listed (see §8 G6).

**`02-account-workspaces/create-workspaces/index.mdx`** (FN)
- **C:** "A workspace… cannot move regions or merge with another once it exists. The choices you make in the creation wizard are the choices you live with" (L17). There are three deployment modes per cloud (L37-41):
  - **Serverless** is the recommended default: no VPC or VNet to size.
  - **Classic** is Terraform plus a customer-managed VPC or VNet, for when you need control, repeatability and a change record.
  - **Private Link** is classic plus the Security Reference Architecture (SRA) defaults, for when "traffic must stay off the public internet".
  - Serverless can be locked down with Network Connectivity Configurations (NCC) and Private Link (L43).
- **Do:** Three workspaces, each "isolated at the network level, not just by folder or permission" (L29).
- **Image:** `site:static/img/workspace-target.jpg` actually shows "Unity Catalog Isolation Options (SDLC)". It has DEV, STG and PRD catalogs, each with its own admin, and workspace-to-catalog binding: the PRD workspace is fully isolated, while the DEV workspace can see the DEV and STG catalogs. Storage is isolated at catalog level ("typically sufficient"). Its alt text says "Account console user management screen" (L33), a copy-paste error.

**`create-workspaces/{aws,gcp}/serverless.mdx`** (BL, ~10 min)
- **Steps:** Account console → **Previews** → turn on "Serverless Workspaces" → Workspaces → Create workspace → name and **Region** ("You cannot change this later") → "Use serverless compute with default storage" → optional metastore → status **Running** → Open workspace.
- **GCP only:** a "Sign in with Google" → **Allow** step, which must use the same Google account as the Databricks account (gcp L92-97, L126-131). The account comes from a GCP Marketplace subscription (L23).
- **Trip:** The preview toggle is visible only to account admins. An empty metastore dropdown is fine; attach one later. A wrong region means delete and recreate. "Deploy in the region that hosts your data sources to avoid cross-region egress fees" (aws L119-121).

**`create-workspaces/azure/serverless.mdx`** (BL): Azure portal → Azure Databricks → Create. On the Basics tab pick subscription, resource group, name (immutable), region, **Pricing Tier Premium** ("Serverless requires Premium") and **Workspace type Serverless** (L50-56). Prereq: **Contributor at subscription scope**, because Databricks creates a managed resource group (L23, L125-127). **Trip:** Serverless only appears once Premium is selected. If Launch fails, check that the account console (`accounts.azuredatabricks.net`) shows Running.

**`create-workspaces/aws/classic.mdx`** (BL, ~20 min)
- **C:** Terraform BYOVPC plus UC resources. There are three templates (L65-69):
  - **Workspace + Catalog** (`technical-services-solutions/.../aws-byovpc-uc`) creates a VPC, cross-account IAM, root S3, workspace, storage credential, external location and catalog.
  - **Workspace** (`aws-byovpc`) takes a new or existing VPC and an optional metastore.
  - **Catalog** (`databrickslabs/sandbox/uc-quickstart/aws`) targets an existing workspace.
- **Do:** Beginners start with Workspace + Catalog (L63). Repeat per environment with a `prefix` such as `dev` or `finance_dev` (L61). "For production, put catalog storage on separate AWS accounts" (tip, L76).
- **Trip:** `:::danger`: the Catalog template needs a **workspace-level** Terraform provider and a service principal with workspace admin (L71-73). `PERMISSION_DENIED: User is not an owner of Metastore` → add the SP to the metastore admins group, or run `GRANT CREATE CATALOG ON METASTORE TO \`service_principal_name\`;` (L106-116).
- **AI:** the AI Platform Kit coding-agent prompt (L26-55), quoted and critiqued in §6.

**`create-workspaces/azure/classic.mdx`** (BL): VNet injection with No Public IP. There are three templates (L69-71):
- `azure-vnet-injection-uc`: resource groups, VNet, subnets, NSG, NAT, workspace, new or existing metastore, storage credential, external location, catalog, and a single-node UC cluster under the Personal Compute policy.
- `azure-vnet-injection`.
- `azure-privatelink-classic`: private endpoints for the control plane and DBFS, private DNS zones, and an NCC for serverless Private Link.

**Trip:**
- With an existing metastore, `admin_user` needs `CREATE EXTERNAL LOCATION` (L73-75).
- Pin `export DATABRICKS_AUTH_TYPE=azure-cli` (L77-79).
- Subnets must be delegated to `Microsoft.Databricks/workspaces`, and the CIDRs must sit inside the VNet `cidr`.
- `vnet_resource_group_name` must differ from `resource_group_name` (L129).

**`create-workspaces/gcp/classic.mdx`** (BL): there are two templates:
- **Standalone** creates a new VPC with `private_ip_google_access`, plus Cloud Router and NAT.
- **Shared VPC** uses existing networking. The host project grants `roles/compute.networkUser` and `roles/compute.networkViewer` (L78-80).

Prereqs: a Google service account (GSA) with `roles/Owner` or the tighter README roles, GSA impersonation with `GOOGLE_OAUTH_ACCESS_TOKEN`, and the GSA added as an account admin (L28-32). Run Terraform from the repo root, not `tf/` (L67). **Trip:** Enable `compute.googleapis.com`. Refresh the token with `export GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token)`. `terraform destroy` fails on leftover firewall rules; destroy workspace → NAT/router → rest (L151-154).

**`create-workspaces/{aws,azure,gcp}/private-link.mdx`** (Stub): each is only a link table to the SRA docs (`databricks.github.io/terraform-databricks-sra`) and the `databricks/terraform-databricks-sra` repo.

**`add-users/manual.mdx`** (BL, ~2 min/user): User management → Users → Add user (email plus full name). Users are created at account level and assigned to workspaces later. **Trip:** "User already exists" usually means SCIM or an earlier admin already added them (L77-80).

**`add-users/scim.mdx`** (BL, ~15 min)
- **Do:** Connect the IdP (Entra ID, Okta, OneLogin) so "this is the last time you add anyone by hand" (L16). **On Azure, use automatic identity management (Entra ID sync) instead of manual SCIM** (tip, L41-43). Optionally, enable all IdP users (L61).
- **Trip:** an expired SCIM token, the wrong account-console URL, or a user not assigned to the SCIM app (L96); duplicates if users were added by hand first, fixed by matching on email (L100-103).

**`add-groups/manual.mdx`** (BL): create account groups such as `data-engineers` and `dev-ws-admins`, then add members (L43-55). **Trip:** "An account-level group has to be assigned to a workspace before it shows up there" (L84). A user must exist at account level before they can join a group (L90).

**`add-groups/scim.mdx`** (BL): groups travel on the same SCIM connector. "Only assigned groups sync" (L47). **Trip:** A member is missing from a group → the user must also be assigned to the SCIM app individually, not only through the group (L94).

**`metastore-admins/set-admin-group.mdx`** (BL, the canonical single-flow screenshot guide)
- **Do:** `:::danger` "The metastore owner must be a group. Assign an individual or a service principal, and the day that person leaves or that principal is deleted, governance operations stop" (L25-28).
- **Steps:** Account console → Catalog → metastore → Configuration → Metastore Admin → Edit → pick `metastore-admins`. Then **turn on automatic workspace assignment** so new workspaces in the region attach automatically (L83).
- **Verify:** In a workspace, Catalog gear → External locations; the "Create external location" button is active (L93-102).
- **Trip:** Only the current owner or an account admin can transfer ownership. If the owner has left, contact Databricks support (L111-113). An empty External locations tab means you are not in the admin group (L119).

**`activate-sso.mdx`** (BL): Azure needs nothing (Entra ID SSO is on by default). AWS: configure a SAML or OIDC app in the IdP, then register it under Settings › Single sign-on. GCP: Google SSO is often on already (L35-39). Test from an incognito window. **Trip:** A redirect loop usually means a reply-URL mismatch ("Trailing slashes and protocol mismatches", L62). "SSO handles authentication, not authorization": the user must still be assigned to the workspace (L68). Azure guest or B2B users must be invited and accepted (L74).

**`workspace-settings/cost-monitoring/index.mdx`** (FN)
- **Do:** "Turn on cost visibility now, while the account is small" (L14). Tags "only apply to usage created after you set them, so every week you wait is a week of spend you can never attribute. Retrofitting attribution is not a thing" (L16).
- **C:** The system tables `system.billing.usage` and `system.billing.list_prices` are "the source of truth for consumption and list-price dollars" (L20). The ordered path is import dashboard → dbdemos dashboards → tags → budgets (L32-37).

**`.../import-usage-dashboard.mdx`** (BL, ~10 min, **account admins only**)
- **Steps:** Account console → Usage → Setup dashboard → choose a version. "Usage Dashboard version 2.0" is Public Preview and adds cost forecasting and object-level drill-down, with a `TODO: verify` comment at L47. Choose scope (account or workspace), pick the target workspace, and Import. Optionally publish with "Viewer credentials" or "Editor credentials" (L63).
- **Also on the Usage page:** a graph (USD or DBU, UTC), usage details, **Pricing settings** (adjust list rates toward contract rates), budgets, and CSV download. "Large exports can hit row caps, so query `system.billing.usage` directly" (L71-75).
- **Trip:** numbers differ from invoices because invoices include discounts and credits (L81); permission-denied tiles → grant SELECT on `system.billing.usage` and `list_prices`, or republish with editor credentials (L112); no rows → run something and wait a few hours (L126).

**`.../additional-dashboards.mdx`** (BL, ~15 min): installs the dbdemos system-tables package, which adds a DBU forecast, model-endpoint and warehouse attribution, UC and volume analysis, and a Genie Space.
- **Code (L39-66):**
```python
%pip install dbdemos
dbutils.library.restartPython()
import dbdemos
catalog = "mycatalog"
schema = "myschema"
dbdemos.install("uc-04-system-tables", catalog=catalog, schema=schema)
```
- **Trip:** `ModuleNotFoundError` → pip install then restart Python. The reader needs SELECT on `system.billing` (and `system.access` for the audit tiles) (L109). Forecasts stay thin on new accounts. The cluster needs egress to PyPI (L123).

**`.../tag-compute-and-jobs.mdx`** (BL, ~25 min)
- **C:** There are two attribution mechanisms:
  - **Custom tags** on classic clusters, SQL warehouses, pools and job compute (GA).
  - **Serverless usage policies**, which "the docs also call… budget policies". They surface in billing as `usage_metadata.budget_policy_id` and cover serverless notebooks, jobs, Lakeflow pipelines and model serving (L17, L34).
  - **Compute policies can *require* tags** at cluster creation (L93). Workspace tags are set through the Account API (`PATCH` with `custom_tags`, L87).
- **Do:** Start early: "Tags apply from creation forward… Start early if you need chargeback" (L24-28). If a user has one policy it auto-attaches; with several, they pick at creation time (L68).
- **Limits:** letters, digits and `+ - = . , _ : @` only; at most 20 custom tags per compute resource; never the key `Name`; tag edits need a restart and workspace tags can lag an hour; a key that collides with a default gets an `x_` prefix or fails under a policy (L97-102); GCP labels are stricter (L104-108).
- **Code (verbatim, L114-127):** cost by team.
```sql
SELECT
  custom_tags['team'] AS team,
  SUM(u.usage_quantity * lp.pricing.effective_list.default) AS estimated_cost_usd
FROM system.billing.usage u
JOIN system.billing.list_prices lp
  ON u.sku_name = lp.sku_name
  AND u.cloud = lp.cloud
  AND u.usage_start_time >= lp.price_start_time
  AND (u.usage_end_time <= lp.price_end_time OR lp.price_end_time IS NULL)
WHERE u.usage_date >= CURRENT_DATE - INTERVAL 30 DAY
GROUP BY 1
ORDER BY estimated_cost_usd DESC;
```
  Two more queries hunt untagged clusters (`custom_tags['team'] IS NULL AND usage_metadata.cluster_id IS NOT NULL`) and group serverless spend by `budget_policy_id` (L131-162). The key idea is the time-bounded join to `list_prices` (price validity window), which turns DBUs into list dollars.
- **Trip:** "Classic tags never apply to fully serverless runs" (L195). Pooled workloads only propagate pool and workspace tags to the cloud bill (L101, L209). Policies are not retroactive for old notebooks (L216). Verification takes 2-4 hours for tagged rows to land (L172).

**`.../budget-alerts.mdx`** (BL, ~10 min, account admins)
- **C:** Monthly USD budgets at **list price**. "It never throttles a workload… A budget only watches" (L17, L26). The page says budgets are Public Preview (L30).
- **Example:** "Development Workspace budget", scoped to the non-prod workspace, with thresholds at $500 and $1000 and an email to a distribution list (L58-67).
- **Trip:** Alerts can trail usage by up to 24 hours, and a new budget may read $0 (L75-76). "Budgets ignore credits and discounts on purpose" (L105). Tag filters are empty if nothing emitted the tag.

### Stage 3: Data access and ETL

**`03-data-access-etl/index.mdx`** (FN): "Every path runs through Unity Catalog… each connection is a UC object with its own permissions and audit trail" (L22). There are two ways in: cloud object storage, or database and SaaS ingestion (L26-29).

**`cloud-object-storage/index.mdx`** (FN, ~5 min)
- **C:** "Key and door" analogy (L20-37). The **storage credential** is the key, wrapping a cloud identity. The **external location** is the door, a path bound to a credential (`s3://…`, `abfss://…@….dfs.core.windows.net/…`, `gs://…`). Flow: a metastore admin creates the credential → creates external locations → UC grants on each location → every notebook, job or query on that path is permission-checked (L41-44).
- **Trip:** The alternative, credentials pasted into notebooks or set at cluster level, "sidesteps Unity Catalog completely. Then nobody can tell you who touched what" (L17-18).

**`cloud-object-storage/aws.mdx`** (BL, ~10 min)
- **C:** There are two reasons to create an external location:
  - Access an existing bucket in place, "usually to ingest it".
  - Use a **new bucket for UC managed tables and volumes** (L18-19).
- **Do:**
  - Use **Set up Automatically**. Databricks provisions the IAM role and storage credential through an AWS delegation page (**Allow access**, or **Request approval** if you cannot create roles) (L25, L73, L97).
  - The privileges needed are `CREATE STORAGE CREDENTIAL` and `CREATE EXTERNAL LOCATION` on the metastore. "Workspace admin is not enough on its own" (L37-48).
  - Mark source locations **read-only** "so a stray job cannot overwrite it" (L81, L105-107).
- **Code:** `GRANT CREATE STORAGE CREDENTIAL, CREATE EXTERNAL LOCATION ON METASTORE TO \`your-group\`;` (L47).
- **Optional NCC** (account admin): account console → Security → Networking → NCC in the workspace's region → Private endpoint rule → resource type "S3 bucket" with endpoint service `com.amazonaws.<region>.s3` and the bucket names → attach to the workspace's Networking config (L109-220).
- **Verify:** "Test connection" checks read, list, write, delete, path, file events, assume role, self assume role and external ID condition (L259).
- **Trip:** "A bucket that blocks public access is not reachable from serverless by default" → NCC (L290). The bonus section creates a bucket with Block all public access, ACLs disabled and SSE-S3 (L293-368).

**`cloud-object-storage/azure.mdx`** (BL, ~20 min; "Azure has the most moving parts", L26)
- **Prereqs:**
  - The storage account must have **hierarchical namespace** (ADLS Gen2), and it can **only be set at creation** (L32, L598-600).
  - Azure RBAC: Storage Account Contributor or Contributor for creation and networking. **User Access Administrator or Owner** to assign roles ("Contributor cannot grant Azure roles"). Network Contributor for private endpoints (L36-44).
  - UC: `CREATE STORAGE CREDENTIAL`, `CREATE EXTERNAL LOCATION`, and `CREATE` on the credential (L50-54).
- **Steps:**
  1. Create the **Access Connector for Azure Databricks** (a managed identity) in the workspace's region and copy its Resource ID.
  2. Grant it **Storage Blob Data Contributor**, plus **Storage Queue Data Contributor** and **EventGrid EventSubscription Contributor** for file events (L123, L174-177).
  3. Create a storage credential (Azure Managed Identity, Access connector ID).
  4. Create an external location `abfss://<container>@<storage_account>.dfs.core.windows.net/<directory>`.
  5. **Assign it to workspaces** (Permissions tab) and mark it read-only if it is source-only (L255-293).
- **Private storage:**
  - Serverless compute needs an NCC with private-endpoint rules for **both `dfs` and `blob`** subresources, **approved** on the storage account (L373-389).
  - Classic compute needs its own `dfs` and `blob` private endpoints into the workspace VNet, integrated with private DNS zones `privatelink.dfs/blob.core.windows.net` (L409-505).
- **Trip:** a missing Blob Data Contributor role is "the most common one to skip" (L523); a truncated Resource ID paste, or a connector in a different region (L535); a private endpoint "stays in Pending" until approved (L547).
- **AI:** two "Genie" (Databricks Assistant) prompts that generate the credential and three external-location DDL statements (L185-189, L242-244); see §6.

**`cloud-object-storage/gcp.mdx`** (BL, ~10 min)
- **C:** "Unlike AWS", creating a **GCP Service Account** storage credential makes Databricks generate a service account (`db-uc-credential-…`). You then grant it **Storage Legacy Bucket Reader** and **Storage Object Admin** on the bucket (L25, L72-90).
- **File events (optional):** they let Auto Loader file-notification mode and managed ingestion use notifications instead of listing (L160). They need a **custom role** on the credential service account and **Pub/Sub Publisher** on the project's **Cloud Storage service agent** (L163). The custom role's 14 permissions are the `pubsub.subscriptions.*` and `pubsub.topics.*` sets plus `storage.buckets.update` (L200-215).
- **Trip:** "the service agent grant is the most common one to miss" (L372). The URL must be `gs://<bucket>/<directory>` (L366).

**`managed-connectors/index.mdx`** (FN, ~5 min)
- **C:** "Lakeflow Connect copies data from an external database or SaaS application into Unity Catalog streaming tables. The source credentials live in a Unity Catalog connection" (L15). The decision table (L19-26) boils down to three differences:
  - **CDC** uses a gateway plus a staging **volume**, captures intermediate changes from the change log, and reads the log rather than re-querying tables. It needs a supported source with CDC configured.
  - **Query-based** has no gateway, runs on a schedule, sees only the latest row state, and works with more sources, but "adds source load".
  - Sources: CDC covers MySQL, PostgreSQL, SQL Server and Oracle. Query-based covers Oracle, Teradata, SQL Server, MySQL, MariaDB and PostgreSQL, plus Lakehouse Federation sources through a foreign catalog (L30). SQL Server also has single-pipeline "integrated CDC", which is out of scope (L32).
- **Do:** Use a bundle "when the pipeline should be version-controlled and repeatable across environments" (L59). Videos cover SQL Server CDC, Salesforce, SharePoint and ServiceNow.

**`managed-connectors/cdc.mdx`** (BL, ~15 min)
- **C:** "A gateway runs continuously on classic compute and writes source changes to a Unity Catalog staging volume. A scheduled serverless ingestion pipeline applies those changes to destination streaming tables" (L16).
- **Steps:** Data Ingestion → source (SQL Server shown) → Create connection → **Change data capture** → name the pipeline, event-log catalog and schema, gateway, and staging catalog and schema → select tables → destination → **Validate** (support objects, CDC config, permissions) → schedule plus notifications (L42-114).
- **Trip:** `:::warning` "Do not stop the gateway. It must run continuously so it captures changes before the source removes them" (L108-110). A stopped gateway past the source retention window needs a **full refresh** (L150-154). If the gateway cannot reach the source, check routing, private connectivity, firewall rules and the port; the gateway runs on classic compute in the workspace network (L145-148).

**`managed-connectors/query-based.mdx`** (BL, ~10 min)
- **C:** A **cursor column** is used as a high-water mark. With a timestamp cursor, SCD type 1 and type 2 "re-read a short window below the mark to catch late-arriving rows" (L16). "The cursor has to be trustworthy" (L18).
- **Prereqs:** The source must be reachable from **serverless**. You need `USE CATALOG`, `USE SCHEMA` and `CREATE TABLE`, and a monotonically increasing timestamp or integer cursor. SCD1 and SCD2 need a primary key (L26-29).
- **Trip:** a creation timestamp or auto-increment ID only tracks inserts (L129); rows with a `NULL` cursor are never ingested (L135); for source load, add a **B-tree index on the cursor** or move to CDC (L147).

**`managed-connectors/dabs-definition.mdx`** (BL, ~15 min)
- **C:** Defining the pipeline as a bundle lets you set an explicit **classic compute block on the gateway**, "the whole reason to go the DABs route" (L35).
- **Code (excerpt of L52-73; the full YAML also defines a `pipeline_postgresql` ingestion pipeline with `ingestion_gateway_id: ${resources.pipelines.gateway.id}`, `source_type: POSTGRESQL`, table and schema objects, and `slot_config` publication settings):**
```yaml
resources:
  pipelines:
    gateway:
      name: ${var.gateway_name}
      gateway_definition:
        connection_name: <my-connection>
        gateway_storage_catalog: development
        gateway_storage_schema: ${var.dest_schema}
        gateway_storage_name: ${var.gateway_name}
      target: ${var.dest_schema}
      catalog: ${var.dest_catalog}

      clusters:
        - label: default
          # AWS instance types. For Azure use Standard_DS3_v2 / Standard_DS4_v2
          driver_node_type_id: r5.xlarge
          # AWS instance types. For Azure use Standard_E8ds_v4 / Standard_E16ds_v4
          node_type_id: m5.xlarge
          autoscale:
            min_workers: 2
            max_workers: 4
            mode: ENHANCED
```
  Deploy and run with `databricks bundle deploy`, then `databricks bundle run pipeline_postgresql` (L126, L136).
- **Trip:** `:::danger` workspace-level provider, and the deploying SP needs workspace admin (L104-106). For gateway start failures, check instance types and autoscale settings, and whether the workspace may launch those instance types (L172). For connectivity, check VPC peering, security groups, firewalls and the connection's credentials (L178).

**`build-first-pipeline/index.mdx`** (BL, ~10 min)
- **Steps:** Jobs & Pipelines → Create → ETL pipeline → name `bakehouse_e2e_pipeline`, Python or SQL → catalog `starterjourney_catalog`, default schema `bakehouse_bronze` → open **Genie Code** in the Pipelines Editor and paste the prompt → "Review the plan and code diff… then click Accept all" → Run → check the bronze and silver schemas and the DAG (L24-86).
- **Do:** Keep the silver column contract: "`transaction_timestamp` and `total_price` on `transactions`, and `franchise_id` plus `franchise_name` on `franchises`. If Genie Code named them differently, rename them now" (tip, L78-80). Reference reading: Auto Loader for incremental file ingestion, views vs materialized views vs streaming tables, and expectations (L94-98).
- **AI:** the medallion pipeline prompt (L52-54); see §6.

**`query-and-explore.mdx`** (BL, ~15 min)
- **Do:** Create a **serverless SQL warehouse** `starter_journey_wh`, **2X-Small**, **auto-stop 10 min**, **min = max = 1 cluster**. "That is enough for one reader" (L39). `:::danger` "A running SQL warehouse consumes billable compute… The 10-minute auto-stop limits idle spend" (L43-45). Keep it, because later pages reuse it (L18).
- **Steps:** SQL Editor → attach the warehouse → set the catalog and schema → Genie Code prompt → review against a 4-point checklist (join on `franchise_id`, day truncation, `SUM(total_price)`, grouping) → Accept → Run → sanity-check the result ("Franchise names should not be null… more than one date and franchise combination", L160) → Save with **Suggest a title**.
- **Code (fallback, verbatim L131-144):**
```sql
SELECT
  DATE(t.transaction_timestamp) AS transaction_date,
  f.franchise_name,
  SUM(t.total_price) AS daily_revenue
FROM transactions AS t
INNER JOIN franchises AS f
  ON t.franchise_id = f.franchise_id
GROUP BY
  DATE(t.transaction_timestamp),
  f.franchise_name
ORDER BY
  transaction_date,
  franchise_name;
```
- **Trip:** The editor on the wrong catalog means tables are not found (L181). "Do not switch warehouse types during the walkthrough because startup and cost behavior will differ" (L193).

**`orchestration/index.mdx`** (FN, ~10 min; video only)
- **C:** Lakeflow Jobs are built visually: tasks (notebooks, pipelines, SQL), ordering, schedule, retries and notifications (L17).
- **Do:** Use the UI for a first job, ad-hoc work or a prototype. "Switch to DABs when the job has to be version-controlled and deployed across environments" (L25-27).

### Stage 4: Governance

**`04-governance/index.mdx`** (FN, ~15 min)
- **Do:** "Decide your catalog, schema, and grant structure now, before anyone builds a pipeline… Fixing that once a few hundred tables exist means rewriting every reference to them" (L19). Order: Groups → ownership → pick a pattern (L44-50). "A five-person team does not need business-unit prefixed catalogs" (L62).
- **C:** Both patterns use "catalogs per environment, medallion schemas, group-based grants" (L52).
- **The linked deck** (`site:static/pdfs/UC Best Practices and Patterns from accumulated STS experiences.pdf`, ©2024; my extraction) covers:
  - UC vs Hive metastore capabilities (slide 6).
  - Admin roles: account admin, metastore admin ("Change OWNER of any securable", "indirect access to data"), workspace admin, and data owner; "Think carefully before giving admin access" (slide 11).
  - Logical isolation patterns (`dev/staging/prod` or `bu_1_dev…` catalogs) with a service principal that has full access on PRD, users with read-only on PRD, and catalogs **bound** to workspaces (slides 14-15).
  - Managed storage at the metastore, catalog or schema level (slide 17).
  - **Managed vs external tables** (slide 18): DROP deletes the data for managed tables but not for external ones. Managed tables are Delta only; external ones can be Delta/CSV/JSON/AVRO/PARQUET/ORC/TEXT. Managed tables get automatic tuning; external tables are "manually managed". "Consider the benefits of Managed tables".
  - External-location patterns: Simple, Prod/Non-Prod, As Necessary (slide 20).
  - Auditing through `system.access.audit` (slide 25).

**`04-governance/groups.mdx`** (FN, ~10 min)
- **Do:** "Grant access to groups, not to people… the only thing you ever change is who is in the group" (L16-18). Give each workspace its own admin group (`dev-ws-admins`, `stg-ws-admins`, `prod-ws-admins`) "so no single group holds the keys to every environment" (L50-56). Prefix groups by BU or project (`[bu-or-project]-data-engineers`…) before a flat group leaks data (L60-69).
- **C:** The persona table (L39-46): metastore (Unity) admins approve catalogs, external locations and connections; workspace admins; data engineers read and write project schemas; data scientists read specific schemas; data analysts are read-only; business users are view-only and "usually they never log into a workspace directly".
- **Trip:** "A group made at the workspace level stays at that workspace. It does not reach other workspaces and it does not show up in Unity Catalog" (L80-82).
- **Image:** `ucblog-simple-grants.jpg` shows `metastore-admins` owning the metastore and the `development` catalog. `data-engineers` own `c360_bronze/silver/gold` with Data Editor. `data-scientists` read silver and gold, `bi-users` read gold only through a DBSQL warehouse to dashboards, Genie and third-party BI.

**`04-governance/uc-assets-ownership.mdx`** (BL, the canonical multi-part screenshot guide, ~15 min)
- **C:** Ownership changes happen in two places. First-level securables are storage credentials, external locations and connections. Catalog children are catalogs and schemas. Both are handled in Catalog Explorer (L18-19).
- **Do:** Transfer the owner to the admin group, then grant working privileges on the Permissions tab. Use presets such as **Data Editor**, and remember "Schemas and tables in the catalog inherit them" (L162, L171).
- **Trip:** An empty Credentials or External locations tab means you are not in the metastore admin group (L27-30). Only the owner or a metastore admin can transfer ownership (L197).

**`04-governance/small-organizations.mdx`** (FN, ~10 min)
- **Do:**
  - "Three catalogs, one per workspace", each **bound** to its workspace (L18, L30-34). Add an optional `sandbox` catalog (tip, L26-28).
  - Production: "The only thing that writes to it is automation running as a service principal. No manual writes, ever" (L34).
  - Medallion schemas per project: `[project]_bronze` holds raw data "landed exactly as it arrived" (reprocess from here), `[project]_silver` is cleaned, deduped and conformed, "the single source of truth for analysts", and `[project]_gold` holds MVs, metric views and aggregates for BI (L44-48).
  - Grants (L63-67): the building group owns the schemas. Share at **schema level** with the Data Reader or Data Editor presets, because "Per-table grants do not scale and break the moment someone adds a new table". Apply least privilege.
- **Trip:** Per-table grants (L85-87). Manual prod writes: "one fat-fingered query breaks the dashboard the CEO checks every morning" (L91).

**`04-governance/medium-large-organizations.mdx`** (FN, ~10 min)
- **Do:** Stamp a BU prefix on workspaces, catalogs and groups. The naming boundary makes wrong grants "obvious in the review" (L18-32). Cross-department access is an explicit schema grant (for example `finance_data_analysts` reading a marketing schema), "not a copy of the table", because "Copies drift out of sync, eat storage, and break lineage" (L73, L95-97). Every prefixed catalog needs a matching prefixed group, "or the prefixes are decoration" (L101).
- **Trip:** "The whole scheme falls apart if one team writes `fin_` and another writes `finance_`… Two to four characters per business unit is plenty" (L93). The page and its own diagrams break this rule; see §8 G7.

**`04-governance/unity-catalog-setup.mdx`** (Stub): "This guidance is a work in progress" (L12). It is still a prerequisite of Stage 5 (`05-genie-ontology/index.mdx` L12).

**`04-governance/abac/index.mdx`** (FN, ~30 min)
- **C:** "Define a masking policy once, attach it to a tag, and every column in every tagged table inherits the policy" (L13), like "a building's badge system… set the rule at the door, not at each desk" (L15). There are three building blocks: tag, masking UDF, and policy (L21-23).
- **Code (verbatim L25-42):**
```sql
-- 1. Tag: label the column so a policy can find it
ALTER TABLE main.hr.employees ALTER COLUMN salary SET TAGS ('sensitivity' = 'high');

-- 2. UDF: returns a substitute value; who sees the real value is decided by the policy, not the function
CREATE OR REPLACE FUNCTION main.security.mask_salary(salary DOUBLE)
RETURNS DOUBLE
RETURN NULL;

-- 3. Policy: created once, bound to the schema, masks every matching column except hr_admin and finance
CREATE OR REPLACE POLICY salary_policy
ON SCHEMA main.hr
COLUMN MASK main.security.mask_salary
TO `account users` EXCEPT hr_admin, finance
FOR TABLES
MATCH COLUMNS has_tag_value('sensitivity', 'high') AS salary
ON COLUMN salary;
```
- **Do:**
  - Use **governed tags** for anything a policy depends on. Custom tags are bypassable because "anyone with `ALTER`… can change or remove" them (L56-78).
  - Governed tags also enforce consistent values (`pii`, not `PII`) (L84).
  - **Automatic data classification** writes system tags such as `databricks:columnPiiTypes` (`EMAIL_ADDRESS`, `US_SOCIAL_SECURITY_NUMBER`, …). A policy on those tags covers new tables once they are scanned; "the most scalable setup" (L96-102).
  - **Redaction** (NULL or a placeholder) when nobody needs to correlate. **Hashing** (`SHA2(value, 256)`) when joins across datasets matter, because it is deterministic (L116-118).
  - **Row filters** use `ROW FILTER` with a BOOLEAN function and `USING COLUMNS (…)` (L137-153).
- **Trip:** `:::warning` "ABAC security policies require DBR 16.4+ or serverless compute" (L46-48). System tags are read-only (L104-106).

**`04-governance/abac/lab.mdx`** (hands-on, ~55 min)
- **Scenario:** Acme Robotics failed a SOC 2 audit because "anyone with `SELECT` on the HR table could pull raw salaries, SSNs, and full card numbers" (L14).
- **Steps:**
  1. Create `development.lab_dac.employees`.
  2. Tag six columns `pii=<type>` (L57-62).
  3. Add masks: salary → NULL; SSN → `'XXX-XX-XXXX'`, with a SHA-256 alternative; email → `SHA2`; card → last 4 digits via `REGEXP_REPLACE`; phone → last 4 digits.
  4. Add a region row filter (L220-235).
  5. Prove inheritance on a new `contractors` table with no new policy (L250-269).
  6. Clean up with `DROP POLICY … ON SCHEMA` (L276-296).
- **Checkpoints:** Each step has an expected output. A user with no group membership sees **0 rows, not an error**, because "that's the filter working as intended" (L238). Masks and filters "stack independently" (L240).
- **Takeaway:** "a data owner tags a column, they don't have to know a masking policy exists" (L269).

### Stage 5: Genie Ontology

**`05-genie-ontology/index.mdx`** (FN, ~10 min)
- **C:** The ontology is a routing tree: User question → Domain → optional Subdomain → Page → Dashboard or Genie Agent (L17-23). "Think of the domain as the front desk" (L25).
- **Do:** Use an ontology "when one broad question could belong to several dashboards or agents" (L14). Overview, snapshot or visual-comparison questions stop at a dashboard page. Rankings, computed comparisons and franchise-specific questions go through the Sales Analytics subdomain to the Genie Agent (L43-44). Both surfaces read the same metric view, so the KPIs match "after the ontology chooses a destination" (L46-47).

**`05-genie-ontology/metadata-generation.mdx`** (Stub): "work in progress… without inventing a procedure before the workflow is documented" (L12-13).

**`05-genie-ontology/metric-views.mdx`** (BL, ~20 min)
- **C:** A metric view "promotes that logic into a governed object: define Total Sales, Order Count, and Avg Order Value once, and every dashboard, Genie Agent, and SQL client reads the same definition" (L16).
- **Steps:** `CREATE SCHEMA IF NOT EXISTS starterjourney_catalog.bakehouse_gold;` → Catalog Explorer → Create → Metric view → Genie Code prompt → review against a checklist (source, many-to-one join, fields, measures) → Save → **reconcile** against the saved query.
- **Code (fallback YAML, excerpt of L87-118):**
```yaml
version: 1.1
source: starterjourney_catalog.bakehouse_silver.transactions
joins:
  - name: franchise
    source: starterjourney_catalog.bakehouse_silver.franchises
    'on': source.franchise_id = franchise.franchise_id
    rely:
      at_most_one_match: true
fields:
  - name: sales_date
    expr: DATE(source.transaction_timestamp)
measures:
  - name: total_sales
    expr: SUM(source.total_price)
    synonyms: ['revenue', 'sales']
  - name: avg_order_value
    expr: MEASURE(total_sales) / MEASURE(order_count)
    synonyms: ['AOV']
```
  The validation query is `SELECT sales_date, franchise, MEASURE(total_sales) AS total_sales FROM …franchise_sales_metrics GROUP BY ALL ORDER BY …` (L139-146).
- **Trip:** "Metric views need compute on Databricks Runtime 17.3 or above" (L161). Inflated totals mean the join is fanning out, so check many-to-one (L167). Field names feed later prompts; rename them or paste the YAML (L173). Mismatches can come from time zones (L179).
- **Orphaned deck:** `site:static/pdfs/UC-Metric-Views.pdf` motivates metric views: four people compute ARR as $2.5M, $2.8M, $3.2M and $2.6M; BI semantic layers are tool-specific. It describes YAML with source, dimensions and measures; `MEASURE()` that generates correct aggregations and joins; windowed and composable measures; certification; materialisation; and access over SQL, ODBC, JDBC and REST.

**`05-genie-ontology/dashboards.mdx`** (BL, ~15 min)
- **Do:** Bind every widget to the `franchise_sales_metrics` dataset, with "No copied SQL, no second definition of revenue" (L16). Generate the layout with the **"Create a dashboard with Genie"** prompt, then Publish.
- **Sharing choice (L93-98):** "**Only people with access can view**" means each viewer's UC permissions apply; use it when row or column rules must hold per viewer. "**Embed your credentials**" means viewers see through your permissions. `:::warning`: embedding "lets viewers see data you can see, even if they have no direct access".
- **Trip:** Genie Code needs **partner-powered AI features** enabled (L116). If a widget runs its own SQL, rebind it to the metric view (L122). Dashboard-level filters cause mismatches (L128).

**`05-genie-ontology/genie-agents.mdx`** (BL, ~15 min)
- **C:** "A dashboard answers the questions you anticipated. A Genie Agent answers the ones you didn't" (L16). Agents are workspace objects: "There is no separate publish button: sharing is how you release the agent" (L101).
- **Steps:** Genie Agents → New → connect `franchise_sales_metrics` ("The metric view already carries the join… you don't need to add the silver tables", L43) → name plus **default warehouse** → a Description covering capabilities *and limitations* → **Instructions** (the prompt) → **Common questions** → validation question checked against the dashboard → Share with at least **CAN RUN**.
- **Trip:** "Data access uses the viewer's own Unity Catalog identity", so an empty answer means the viewer lacks SELECT (L125). For disagreements, check time windows and filters, and add an instruction (L131).

**`05-genie-ontology/domains-subdomains-pages.mdx`** (BL, ~30 min)
- **Steps:**
  1. **Discover** → Create domain (title, subtitle, description, technical and business contacts). Keep it in **draft**.
  2. Create the page "Franchise Performance at a Glance" with synonyms, a description, and a Markdown body with "When to route here" and example questions. Add the dashboard under **Related Assets and Sources**, then Publish. The page's **Discussion** area is for maintainers.
  3. Create the subdomain "Sales Analytics" and **publish it before adding a page**.
  4. Create the page "Sales Q&A Assistant" backed by the Genie Agent.
  5. **Publish the domain last**.
  6. Test in **Genie One** with two prompts and inspect the **Thought process** to see which sources were chosen (L37-327).
- **Trip:** "Publishing the domain does not publish the subdomain" (L360). Misrouting means editing the page descriptions and bodies: routing depends on the words (`overview`, `snapshot`, `high-level summary`, `visual comparison` vs rankings and comparisons) (L367-375). The asset must appear in **both** Related Assets and Sources (L375). Different KPI values mean the two surfaces are not on the same metric view (L381-382).

### Stage 6: Data science

**`06-data-science/index.mdx`** (FN)
- **C:** "A Databricks MLOps solution is three Ops disciplines": DataOps on UC, ModelOps on MLflow (tracking, registry, serving), and DevOps on DABs plus Git (L16-22). "At the end of the day, everything here is code sitting in a repo" (L30).
- **Do:** Watch "From Notebook to Production: MLOps Quickstart". Deploy `databricks-solutions/mlops-quickstart` (DABs plus GitHub Actions) after reading Stage 7. Then use its "Adapt this template with Genie Code" section to swap in your own data and model "using the built-in Databricks Assistant skills" (L45-49). The essential reads are MLflow 3 (L53-58).
- **Image:** `mlops-diagram.png` shows the dev workspace reading the **Prod catalog** (bronze/silver/gold, features, models) for exploration, training and evaluating on a `dev` branch, logging to the MLflow tracking server, running compliance and pre-deployment checks, **registering to the Dev catalog**, and committing `train.py`, `deploy.py`, `inference.py`, `monitoring.py`, `featurization.py` and unit and integration tests to Git.

**`06-data-science/save-model-to-unity-catalog.md`** (~20 min)
- **C:** There are three paths: (A) train and register using the MLflow 3 example notebook, (B) load weights from a **UC Volume**, (C) import from **Hugging Face**. Everything was tested on **Serverless ML (ML v5, Python 3.12)**, which has MLflow and PyTorch preinstalled. Use **Serverless GPU** for deep learning (L26-28).
- **Code (Option B, excerpt of L51-86):**
```python
mlflow.set_registry_uri("databricks-uc")
weights_path = f"/Volumes/{catalog}/{schema}/model_weights/logistic_model.pkl"
sample_path = f"/Volumes/{catalog}/{schema}/model_weights/sample_input.csv"
with open(weights_path, "rb") as f:
    loaded_model = pickle.load(f)
sample_input = pd.read_csv(sample_path, index_col=0)
signature = infer_signature(sample_input, loaded_model.predict(sample_input).tolist())
with mlflow.start_run():
    model_info = mlflow.sklearn.log_model(
        loaded_model,
        name="model",
        signature=signature,
        input_example=sample_input,
        registered_model_name=f"{catalog}.{schema}.logistic_classifier",
    )
```
  Option C logs a `transformers` pipeline, which carries the tokenizer and config, then sets the alias `client.set_registered_model_alias(f"{catalog}.{schema}.{model_name}", "challenger", model_info.registered_model_version)` (L126-131).
- **Do:** Always log a **signature and input example**. Register under a three-level UC name. Promote with **aliases** (challenger/champion) (L126-131; index L28). UC-registered models use aliases in place of the old workspace-registry stages (inferred).

**`06-data-science/batch-inference.md`**: "A batch job that loads a model from Unity Catalog by alias, scores rows, and writes predictions to a Delta table" (L15). The method table recommends a **Spark UDF** for production-scale tabular data, a **pandas single-node** run for quick validation, and a **pandas UDF** for images (L24-28). There is no code.

**`06-data-science/prepare-datasets.mdx`** (BL, ~15 min): `dbdemos.install('feature-store', catalog='main', schema='dbdemos_fs_travel')` (L43) installs three notebooks: Feature Tables plus `FeatureLookup`; point-in-time lookups, Online Tables and Feature Serving; and feature tables built as a declarative pipeline. **Do:** "Feature engineering is a data engineering task, not an ML task… define feature tables as a Lakeflow Declarative Pipeline so they refresh automatically and stay governed" (tip, L60-62).

### Stage 7: Operations and CI/CD

**`07-operations/index.mdx`** (FN, ~15 min)
- **Do:** "Anything outside the workspace is Terraform's job; anything inside it is DABs" (L16):
  - **Terraform** covers accounts, networks, metastores, workspaces and IAM.
  - **DABs** cover jobs, pipelines, schemas, dashboards and other project assets (L29-32).
  - Default to **trunk-based development** (L39, L157).
  - Use a **1:1 Git repo to Databricks project** mapping, "one deployment boundary, one owning team". The page's table compares merge conflicts, CI speed, ownership and release cadence for shared vs isolated repos (L157-166).
  - Worked example: "Awesome123" corp uses `databricks-marketing-c360` and `databricks-finance-revenue-prediction` (L170-177).
- **C:** DABs are "Databricks as code", shipped in the Databricks CLI. A typical pipeline validates, tests and deploys (L36-41). The page lists reference repos: `databricks/bundle-examples/knowledge_base` (Genie Agents, metric views, Apps, Lakebase, jobs, pipelines, models, serving endpoints, Vector Search indexes) and `databricks-solutions/databricks-dab-examples` (flights in three tiers; an Azure DevOps pipeline; a React + Lakebase app) (L72-76).
- **Code (the "Deploy to staging" workflow, L98-133, first 20 lines verbatim; the Deploy step repeats the same env block with `run: databricks bundle deploy`):**
```yaml
name: Deploy to staging
on:
  push:
    branches: [staging]

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4

      - name: Install Databricks CLI
        uses: databricks/setup-cli@main

      - name: Validate bundle
        env:
          DATABRICKS_HOST: ${{ secrets.DATABRICKS_HOST }}
          DATABRICKS_CLIENT_ID: ${{ secrets.DATABRICKS_CLIENT_ID }}
          DATABRICKS_CLIENT_SECRET: ${{ secrets.DATABRICKS_CLIENT_SECRET }}
```
  The remaining env lines are `DATABRICKS_BUNDLE_ENV: ${{ vars.ENVIRONMENT }}`, `BUNDLE_VAR_catalog: ${{ vars.CATALOG }}` and `BUNDLE_VAR_schema: ${{ vars.SCHEMA }}`. The tip: "The catalog and schema DABs values come from GitHub repository environments, not from inside the bundle itself" (L86-88). The diagram (`dabs-cicd-github.jpg`) shows these as GitHub **environment secrets** (host, client ID and secret: OAuth M2M for a service principal) and **environment variables** (`CATALOG=marketing_staging`, `ENVIRONMENT=staging`, `SCHEMA=galaxydb`).
- **Trip:** The "DABs migrator" (`technical-services-solutions/core-platform/cicd/dabs-migrator`) "is not an official Databricks-supported tool. Validate generated bundles in a non-production workspace" (L143-146). The "When to use" table ends with: a one-off prototype with a single owner and nothing downstream needs "Neither" (L187).

### Blog (site:blog)
Four embeds: the Cheatsheet 2026 LinkedIn post; "Modeling a Medallion Architecture on Unity Catalog…" ("Content of this blog was used on the Data Governance Strategy section", a stale section name); the launch post (2026-03-01); and "Monitoring Kubernetes Applications with Zerobus and Genie" (2026-07-08, Medium).

---

## 4. Platform fundamentals cheat-sheet

Rows marked **Repo: not covered** name a gap in the guide. The advice in those rows is general Databricks practice and is flagged **(inferred)**.

### 4a. Recommendations by area

| Area | Recommendation | Why (business / technical) | Source |
|---|---|---|---|
| **Account & workspace** | Keep account-level changes (workspaces, identity, metastores, billing, SSO/SCIM) in the account console; do data work inside workspaces | Business: one place to audit spend and access. Technical: without it "every workspace becomes its own island with its own users, permissions, and billing" | `01-introduction/foundations/account-console.mdx` L14, L42-44 |
| Account & workspace | Give out account admin sparingly; most people need workspace admin at most | Account admins control every workspace, identity and billing, so over-granting widens the blast radius | account-console L48-50; UC deck slide 11 ("Think carefully before giving admin access") |
| Account & workspace | Default to **single-tenant** (one cloud account). Go multi-tenant only for separate billing, a network/IAM boundary, or a written regulatory need | Business: less overhead and a single cloud bill. Technical: UC already isolates data, and the layout is "painful to unwind once workspaces are live" | `cloud-tenant-ready/index.mdx` L15-17, L47-53 |
| Account & workspace | If multi-tenant: one Databricks account and one UC across all cloud accounts, IaC from day one, and split by environment or compliance boundary, never by team | This avoids governance silos and config drift ("works in dev and breaks in prod") | `multi-tenant-setup.mdx` L38, L48-58 |
| Account & workspace | Write down the tenant decision and what would trigger a change | It turns a future migration into "a planned project and not a fire drill" | `single-tenant-setup.mdx` L44-46 |
| Account & workspace | Start with **3 workspaces (dev, staging, prod)**, not one per team | Separation contains incidents (an untested job cannot take down prod); fewer workspaces means less admin sprawl | `foundations/workspace.mdx` L14, L46, L58-64 |
| Account & workspace | Put the workspace in the region where the data lives; treat the region as permanent | Avoids cross-region egress fees; "A workspace cannot move regions", so fixing it means delete and recreate | `aws/serverless.mdx` L117-122; `create-workspaces/index.mdx` L17 |
| Account & workspace | Default to **Serverless** workspaces. Use **Classic** (Terraform BYOVPC / VNet injection) when you must own the network, and **Private Link/SRA** when traffic must stay private | Serverless has no VPC to size or maintain; Classic gives control and a change record; SRA gives hardened defaults. NCC and Private Link can now lock down serverless too | `create-workspaces/index.mdx` L37-43 |
| Account & workspace | Classic via Terraform: use one template per environment with a `prefix`; beginners use "Workspace + Catalog" | Repeatable environments and an audit trail of changes | `aws/classic.mdx` L59-69 |
| Account & workspace | For production, put catalog storage in **separate cloud accounts** | Limits the blast radius of storage and IAM mistakes | `aws/classic.mdx` L75-77 |
| Account & workspace | Azure: Premium tier (required for serverless) and Contributor **at subscription scope** | Databricks creates a managed resource group, so resource-group-only rights fail validation | `azure/serverless.mdx` L23, L54, L125-127 |
| Account & workspace | Turn on automatic metastore assignment for new workspaces in a region | New workspaces are governed from day one, with no manual attach step | `set-admin-group.mdx` L83 |
| **Identity** | Provision users and groups with **SCIM** from the IdP. On Azure, use **automatic identity management** (Entra ID sync) | Business: joiners and leavers flow from HR/IdP automatically. Technical: "this is the last time you add anyone by hand" | `add-users/scim.mdx` L16, L41-43 |
| Identity | If users were added by hand before SCIM, match on email | Otherwise every person ends up with duplicate accounts | `add-users/scim.mdx` L100-103 |
| Identity | Create groups at **account level** (or via SCIM), never workspace-local | Workspace-local groups do not reach other workspaces or UC | `04-governance/groups.mdx` L78-82 |
| Identity | **Grant to groups, not people.** Use persona groups: metastore admins, workspace admins, data engineers, data scientists, data analysts, business users | Onboarding and offboarding become a membership change, not a hunt for grants | `groups.mdx` L16-18, L39-46 |
| Identity | One admin group per workspace (`dev-ws-admins`, `stg-ws-admins`, `prod-ws-admins`) | "no single group holds the keys to every environment" | `groups.mdx` L50-56 |
| Identity | Prefix groups by business unit or project before a flat group starts leaking data | Splitting a flat group later is "a migration with permissions to re-grant" | `groups.mdx` L60-75; `medium-large-organizations.mdx` L99-101 |
| Identity | **The metastore owner is a group**, never a person or a service principal | When an owner leaves or is deleted, governance operations stop | `set-admin-group.mdx` L25-28 |
| Identity | Transfer ownership of credentials, external locations, connections, catalogs and schemas to the admin group, then grant working privileges separately | Ownership means control; privileges mean day-to-day use. Keeping them apart supports least privilege | `uc-assets-ownership.mdx` L16-19, L88-93 |
| Identity | Use **service principals** for automation. Only SP-run automation writes to prod. CI uses SP OAuth credentials (client ID/secret) stored as environment secrets | Accountability, and no "fat-fingered" human writes to prod data | `small-organizations.mdx` L34, L89-91; `07-operations/index.mdx` L114-121 + image |
| Identity | SSO: on by default on Azure (Entra ID); set up SAML/OIDC on AWS; often already on for GCP. Remember that SSO handles authentication, not authorization | Removes separate passwords; users still need workspace assignment | `activate-sso.mdx` L35-39, L68 |
| **Unity Catalog** | Send **every** data and AI access through UC; no hardcoded credentials, no cluster-level environment-variable access | Access, lineage and audit are enforced "without extra work"; bypasses cannot be audited or revoked | `foundations/unity-catalog.mdx` L17, L52, L56-62; `recap-and-learning.mdx` L48-53 |
| UC: metastore | One metastore per region per account, shared by all workspaces there, including workspaces in other cloud accounts | Keeps one permission model even when infrastructure is split | `unity-catalog.mdx` L69; `multi-tenant-setup.mdx` L38 |
| UC: catalogs | One catalog per environment (`development`, `staging`, `production`), each **bound** to its workspace, plus an optional `sandbox`. Multi-BU: prefixed catalogs per BU and environment | Environment isolation and discoverability. Renaming later means "rewriting every reference" | `small-organizations.mdx` L18-34; `medium-large-organizations.mdx` L36-44; `04-governance/index.mdx` L19 |
| UC: schemas | Per project: `[project]_bronze`, `_silver`, `_gold` | Predictable names; each layer has its own consumers and grants | `small-organizations.mdx` L38-48 |
| UC: grants | Grant at **schema level** using the **Data Reader / Data Editor** presets | Per-table grants "break the moment someone adds a new table" | `small-organizations.mdx` L66, L85-87 |
| UC: sharing | Share across business units with explicit grants, never copies | Copies "drift out of sync, eat storage, and break lineage" | `medium-large-organizations.mdx` L73, L95-97 |
| UC: storage access | Reach storage through a **storage credential** (the key) plus an **external location** (the door). Mark source locations read-only. On Azure, assign locations to workspaces | Least privilege on paths; "a stray job cannot overwrite it" | `cloud-object-storage/index.mdx` L20-44; `aws.mdx` L105-107; `azure.mdx` L277-293 |
| UC: privileges | Metastore-level `CREATE STORAGE CREDENTIAL`, `CREATE EXTERNAL LOCATION`, `CREATE CATALOG` (for Terraform SPs). "Workspace admin is not enough on its own" | These are the most common permission failures during setup | `aws.mdx` L37-48; `aws/classic.mdx` L106-116 |
| UC: managed vs external | Create a **new bucket for UC managed tables and volumes**. Point external locations at existing data mainly to ingest it. The deck says "Consider the benefits of Managed tables" | Managed tables: UC owns the files (DROP deletes them), automatic tuning, Delta only. External tables: you own layout and lifecycle, several formats allowed, DROP keeps the files | `aws.mdx` L18-19; UC deck slide 18 |
| UC: physical isolation | Set the managed storage location at the **catalog** level, with separate storage and credentials per environment | Separates prod data physically, and billing/storage ownership with it; "typically sufficient" | UC deck slides 17, 19; `static/img/workspace-target.jpg` |
| UC: volumes | Put non-tabular files (model weights, sample CSVs, CDC staging) in **UC volumes** | Files get the same grants and audit as tables | `save-model-to-unity-catalog.md` L47-65; `cdc.mdx` L16; UC deck slide 6 |
| UC: lineage & audit | Lineage is automatic when access goes through UC; audit with `system.access.audit` | Needed for compliance evidence and impact analysis | `unity-catalog.mdx` L52; UC deck slide 25 |
| UC: fine-grained | Use **ABAC**: governed tags → masking UDF / row-filter UDF → a schema- or catalog-level policy with `TO … EXCEPT`. Turn on automatic data classification | One policy covers future tables; custom tags can be bypassed; classification finds new PII | `abac/index.mdx` L13, L25-44, L56-102 |
| UC: fine-grained | Use redaction (NULL or placeholder) by default. Use SHA-256 hashing only where cross-dataset joins matter and pseudonymisation is allowed | Balances analytical value against compliance | `abac/index.mdx` L116-118; `abac/lab.mdx` L96 |
| UC: fine-grained | ABAC needs **DBR 16.4+ or serverless** | Older clusters fail at policy evaluation | `abac/index.mdx` L46-48 |
| **Compute** | Go serverless first: serverless workspace, serverless SQL warehouse, serverless ingestion pipelines, Serverless ML/GPU | No infrastructure to manage; fast start. Scale-to-zero cost behaviour is (inferred) | `create-workspaces/index.mdx` L39; `query-and-explore.mdx` L39; `cdc.mdx` L16; `save-model…md` L26-28 |
| Compute: SQL warehouses | Start at 2X-Small, **auto-stop 10 min**, min = max = 1 cluster; reuse one warehouse across the journey | "A running SQL warehouse consumes billable compute"; auto-stop limits idle spend | `query-and-explore.mdx` L39-45, L18 |
| Compute: classic | Use classic compute where you need network reach or explicit instance control, such as the CDC gateway, which runs continuously on classic compute (pin instance types and autoscale in DABs) | The gateway must reach private databases in your network | `cdc.mdx` L16, L25; `dabs-definition.mdx` L35, L64-73 |
| Compute: policies | Use **compute policies** to require tags at creation; the Azure template ships a Personal Compute policy cluster | Enforces cost attribution and guardrails at the source | `tag-compute-and-jobs.mdx` L93; `azure/classic.mdx` L69 |
| Compute: job vs all-purpose | **Repo: not covered.** Run scheduled production work on job compute or serverless jobs; keep all-purpose clusters for interactive development, with auto-termination (inferred) | Lower DBU rate and an isolated lifecycle for production (inferred) | n/a |
| Compute: networking | Serverless reaching private storage needs an **NCC** with private endpoint rules (AWS S3 endpoint service; Azure `dfs` + `blob`, approved on the account). Classic needs its own private endpoints | Serverless runs in Databricks' network, so private storage is unreachable by default | `aws.mdx` L109-220, L290; `azure.mdx` L336-505 |
| Compute: runtimes | Metric views need **DBR 17.3+**; ABAC needs **DBR 16.4+** | Feature gates, and a common cause of greyed-out UI | `metric-views.mdx` L161; `abac/index.mdx` L46 |
| **Ingestion** | Use **Lakeflow Connect** managed connectors for databases and SaaS, landing in UC streaming tables, with credentials in a UC connection | Governed credentials, no custom code, managed incremental loads | `managed-connectors/index.mdx` L15 |
| Ingestion | Choose **CDC** when the source supports it and you need every change with little source load. Choose **query-based** for wider source support, where latest state is enough | CDC captures intermediate changes from the log; query-based "adds source load" and misses in-between states | `managed-connectors/index.mdx` L19-26 |
| Ingestion: CDC | Never stop the gateway; if retention lapsed, do a full refresh | Changes are lost once the source purges its log | `cdc.mdx` L108-110, L150-154 |
| Ingestion: query-based | Use a cursor that changes on every update and is never NULL; index it (B-tree); move to CDC if source load hurts | Otherwise updates are silently missed, and the source database slows down | `query-based.mdx` L18, L29, L129-147 |
| Ingestion: network | CDC gateway: needs a classic-compute path to the DB. Query-based: needs a serverless path (NCC) | Each runs in a different network context | `cdc.mdx` L25, L147; `query-based.mdx` L26, L141 |
| Ingestion: files | **Auto Loader** for incremental file ingestion. Turn on **file events** (GCP Pub/Sub roles; Azure Queue/EventGrid roles) for notification mode | Avoids expensive directory listing at scale | `build-first-pipeline/index.mdx` L94; `gcp.mdx` L157-163; `azure.mdx` L123, L174-177 |
| Ingestion: COPY INTO | **Repo: not covered.** Use COPY INTO for simple, idempotent, SQL-driven batch file loads; prefer Auto Loader for continuous or high-file-count loads (inferred) | Simplicity vs scalable file discovery (inferred) | n/a |
| Ingestion: as code | Define gateway and ingestion pipelines as a bundle when they must be repeatable across environments | Version control, plus an explicit gateway compute block | `managed-connectors/index.mdx` L59; `dabs-definition.mdx` L35 |
| **Pipelines** | Build ETL as a **Spark Declarative Pipeline** (Lakeflow): bronze landing, silver typed and cleaned, with **expectations** that drop null-PK rows | Declarative dependency management plus data-quality gates | `build-first-pipeline/index.mdx` L48-54, L96 |
| Pipelines | Choose views, materialized views or streaming tables per transformation | Streaming for append/incremental; MVs for aggregates; views for light logic | `build-first-pipeline/index.mdx` L95 |
| Pipelines: Jobs | Orchestrate with **Lakeflow Jobs** (tasks, dependencies, schedule, retries, notifications). Prototype in the UI; productionise with DABs | Moves the team from click-ops to reviewed deployments | `orchestration/index.mdx` L17, L25-27 |
| Pipelines: features | Build feature tables as declarative pipelines | "Feature engineering is a data engineering task, not an ML task" | `prepare-datasets.mdx` L60-62 |
| **Medallion** | Bronze = raw "exactly as it arrived" (the reprocessing point). Silver = cleaned, deduplicated, conformed, "the single source of truth for analysts". Gold = MVs, metric views, aggregates for BI | Replayability, trust, and one consumption layer per audience | `small-organizations.mdx` L44-48 |
| Medallion | Medallion layers are **schemas inside environment catalogs**, per project, owned by the building group; grants widen toward gold (DS reads silver and gold, BI reads gold) | Least privilege by layer | `small-organizations.mdx` L38, L65; `ucblog-simple-grants.jpg` |
| Medallion: when overkill | **Repo: not covered** (the nearest point is "Over-engineering for a small team", about prefixes, `04-governance/index.mdx` L60-62). Collapse layers for small, clean, single-consumer data, but keep a raw landing for replay (inferred) | Each extra hop adds storage, latency and pipeline code (inferred) | n/a |
| **Delta features** | **Repo: not covered** in the docs. The UC deck only lists "AI Powered Predictive optimization" and managed-table "Auto Tune (In Preview)". Prefer managed tables with **predictive optimization** (automatic OPTIMIZE, VACUUM, ANALYZE); use **liquid clustering** (`CLUSTER BY`, or automatic) instead of partitioning or Z-order on new tables; **deletion vectors** make DELETE, UPDATE and MERGE cheaper by not rewriting files (inferred) | Lower maintenance toil and faster queries without tuning expertise (inferred) | UC deck slides 6, 18; otherwise n/a |
| **BI: semantic layer** | Define KPIs once as a **UC metric view** in gold (measures, dimensions, synonyms); every dashboard, Genie Agent and SQL client reads it | Ends "ARR = $2.5M vs $2.8M" arguments; one definition, many tools | `metric-views.mdx` L16; `UC-Metric-Views.pdf` |
| BI | **Reconcile** the metric view against a known-good query before publishing; check that joins are many-to-one | Catches fan-out and time-zone errors before business users see them | `metric-views.mdx` L136-148, L167, L179 |
| BI: dashboards | Bind every widget to the metric view; avoid widget-local SQL | "No copied SQL, no second definition of revenue" | `dashboards.mdx` L16, L122 |
| BI: sharing | Use "Only people with access can view" when row or column rules must apply per viewer. Use "Embed your credentials" only when the audience should not need table access | Embedding can expose data beyond a viewer's grants | `dashboards.mdx` L93-98 |
| BI: Genie Agents | Give the agent focused, governed data (the metric view), a default warehouse, a description that states its **limitations**, instructions defining jargon and ranking rules, and common questions. Validate against the dashboard, then share with CAN RUN | Accuracy and trust; the agent runs with the viewer's identity | `genie-agents.mdx` L41-101, L125 |
| BI: Genie practice | Keep each space topic-specific. Use clean, commented tables (example values and synonyms in comments), PK/FK or pre-joined MVs, sample SQL ("Save as Instruction"), benchmark questions with gold-standard SQL, and the monitor page | Genie accuracy depends on metadata; benchmarks track regressions | `site:static/pdfs/Genie Best Practices.pdf` (orphaned deck) |
| BI: Genie Ontology | Use a Discover **domain → subdomain → page** tree when one question could hit several surfaces. Put routing words in page descriptions and bodies, attach assets in both Related Assets and Sources, publish pages, subdomain and domain, and test in Genie One | Users ask once; routing picks the right governed surface while KPIs stay consistent | `05-genie-ontology/index.mdx` L14-47; `domains-subdomains-pages.mdx` L358-382 |
| BI: prerequisites | Turn on partner-powered AI features at account and workspace level | Genie and "Create a dashboard with Genie" are unavailable otherwise | `dashboards.mdx` L116; `genie-agents.mdx` L119 |
| **ML/AI: MLflow** | Use MLflow 3 with `set_registry_uri("databricks-uc")`. Register models under 3-level UC names with a **signature and input example**. Promote with **aliases** (challenger / champion) | Governed, lineage-tracked models; deploy by alias rather than version | `save-model-to-unity-catalog.md` L57, L76-83, L126-131; `06-data-science/index.mdx` L28 |
| ML/AI: inference | Batch-score with a **Spark UDF** loaded by alias, writing to Delta; pandas for quick checks; pandas UDF for images | Scale out, and repeatable scoring | `batch-inference.md` L15, L24-28 |
| ML/AI: features | Keep feature tables in UC. Use point-in-time lookups against leakage, and online tables or feature serving for real-time | Prevents training/serving skew and data leakage | `prepare-datasets.mdx` L56-58 |
| ML/AI: MLOps | DataOps (UC) + ModelOps (MLflow) + DevOps (DABs + Git); start from `mlops-quickstart`; develop in dev against read-only prod data and register to the dev catalog | "everything here is code sitting in a repo" | `06-data-science/index.mdx` L16-49; `mlops-diagram.png` |
| ML/AI: serving, vector search, agents | **Repo: not covered**; these are only mentioned (DS description; bundle examples; cheatsheet definitions). Serving endpoints with scale-to-zero for non-prod; Vector Search indexes synced from Delta tables; agents built with Agent Framework or Agent Bricks and evaluated with MLflow before exposure (inferred) | Cost control and quality gates for GenAI (inferred) | `07-operations/index.mdx` L74; Cheatsheet PDF |
| **Apps** | **Repo: not covered.** The Apps page was removed (the redirect `/docs/05-genie-ontology/databricks-apps` goes to the Genie Ontology index). Deploy Apps with DABs (the reference repo includes an Apps + Lakebase example); apps run as a service principal and read governed data through UC (inferred) | Apps without separate infrastructure (cheatsheet); governed data access (inferred) | `site:docusaurus.config.ts` redirects; `07-operations/index.mdx` L74-76 |
| **Cost: visibility** | Set up cost visibility on **day zero**: import the account usage dashboard, optionally the dbdemos system-tables dashboards | Avoids "a surprise invoice" and "an awkward silence when finance asks who spent what" | `cost-monitoring/index.mdx` L14; `import-usage-dashboard.mdx` |
| Cost: attribution | **Tag from day one**: custom tags on classic compute, **serverless usage (budget) policies** for serverless, and compute policies that *require* tags | Tags are forward-only: "Retrofitting attribution is not a thing" | `cost-monitoring/index.mdx` L16; `tag-compute-and-jobs.mdx` L17-34, L93 |
| Cost: budgets | Create account budgets per workspace or tag with staged thresholds (e.g. $500 / $1000) sent to a distribution list | Early warning. Budgets **do not throttle**, lag up to 24 h, and use list price | `budget-alerts.mdx` L17, L26, L58-76, L105 |
| Cost: truth source | Use `system.billing.usage` joined to `system.billing.list_prices` inside the price validity window; adjust pricing settings to approximate contract rates | The UI and dashboards reconcile to system tables; invoices add discounts and credits | `cost-monitoring/index.mdx` L20; `tag-compute-and-jobs.mdx` L114-127; `import-usage-dashboard.mdx` L73-82 |
| **CI/CD** | **Terraform** for anything outside a workspace (accounts, networks, metastores, workspaces, IAM); **DABs** for anything inside (jobs, pipelines, schemas, dashboards, …) | "Get that line wrong and you end up with brittle scripts, environments that drift, and a deploy only one person knows how to run" | `07-operations/index.mdx` L16-17, L29-32 |
| CI/CD | **1 repo = 1 bundle = 1 team**, with trunk-based development | Isolated CI, clear ownership, independent release cadence | `07-operations/index.mdx` L157-166 |
| CI/CD | Pipeline: `databricks bundle validate` → tests → `databricks bundle deploy` per target, with SP OAuth secrets and per-environment variables (catalog, schema, target) in GitHub environments | The same bundle promotes through dev → staging → prod | `07-operations/index.mdx` L41, L86-133 |
| CI/CD | Prototype jobs in the UI, then codify. Migrate existing assets with the unofficial DABs migrator, validated in non-prod first | Low-friction start without skipping review | `orchestration/index.mdx` L25-27; `07-operations/index.mdx` L143-146 |
| CI/CD hygiene | Pin third-party actions (the example uses `databricks/setup-cli@main`) and add protection rules to the prod environment (the screenshot shows "No restriction") (inferred) | Supply-chain safety and gated prod deploys (inferred) | `07-operations/index.mdx` L112 + `dabs-cicd-github.jpg` |
| **AI assistants** | Let Genie Code draft, then **review the diff against a checklist**, keep fallback code, and reconcile numbers. Coding agents must ask for missing values, `plan` before `apply`, get explicit approval, and verify afterwards | Speed without silent errors | `build-first-pipeline` L60; `query-and-explore.mdx` L116-146; `metric-views.mdx` L75-120; `aws/classic.mdx` L45-53 |

### 4b. Troubleshooting index (from every "Where people trip" section)

| Symptom | Likely cause | Fix | Source |
|---|---|---|---|
| "Serverless Workspaces" is missing from Previews | You are not an account admin, or the region is unsupported | Check the role and the supported-regions list | `aws/serverless.mdx` L101-106; `gcp/serverless.mdx` L117-123 |
| Azure: the Serverless workspace type is not offered | Pricing tier is not Premium | Pick Premium first | `azure/serverless.mdx` L115-120 |
| Azure validation permission error | Contributor granted only at resource-group scope | Grant Contributor at subscription scope | `azure/serverless.mdx` L123-128 |
| GCP workspace permission errors after "Allow" | The wrong Google account was used | Use the account linked to Databricks | `gcp/serverless.mdx` L126-131 |
| `PERMISSION_DENIED: User is not an owner of Metastore` in Terraform | The SP lacks metastore rights | Add it to metastore admins, or `GRANT CREATE CATALOG ON METASTORE` | `aws/classic.mdx` L106-116 |
| Catalog module cannot connect | Account-level provider in use | Use a workspace-level provider plus an SP with workspace admin | `aws/classic.mdx` L125-128 |
| Azure VNet injection subnet errors | Subnets not delegated, CIDRs overlap, same resource group | Delegate to `Microsoft.Databricks/workspaces`, fix the CIDRs, use a separate VNet RG | `azure/classic.mdx` L127-130 |
| GCP `terraform destroy` stuck on the network | Leftover firewall rules | Destroy in order; delete the orphaned rules | `gcp/classic.mdx` L151-154 |
| Users missing after SCIM sync | Token expired, wrong URL, user unassigned | Check the IdP provisioning logs | `add-users/scim.mdx` L93-97 |
| Duplicate users after SCIM | Users were added by hand earlier | Match on email | `add-users/scim.mdx` L99-103 |
| Group not visible in a workspace | Not assigned to that workspace | Account console → workspace → Permissions | `add-groups/manual.mdx` L81-85 |
| Group members missing after sync | The user is not assigned to the SCIM app directly | Assign the user as well as the group | `add-groups/scim.mdx` L91-95 |
| External locations/Credentials tab empty | You are not in the metastore admin group | Check membership | `set-admin-group.mdx` L117-120; `uc-assets-ownership.mdx` L27-30 |
| SSO redirect loop | Reply-URL mismatch (trailing slash, protocol) | Match the IdP and account-console URLs exactly | `activate-sso.mdx` L59-63 |
| SSO works but the workspace is inaccessible | Authentication ≠ authorisation | Assign the user or group to the workspace | `activate-sso.mdx` L65-69 |
| Usage dashboard tiles show permission denied | No SELECT on `system.billing.*` | Grant SELECT or republish with editor credentials | `import-usage-dashboard.mdx` L109-114 |
| Serverless rows have no tags | Classic tags do not apply to serverless | Use a serverless usage policy | `tag-compute-and-jobs.mdx` L192-197 |
| Cluster creation fails under a policy | Tag key collides with a default key | Rename it (e.g. `x_vendor`) | `tag-compute-and-jobs.mdx` L199-204 |
| Budget stuck at $0 or no email | Telemetry lag (up to 24 h), spam folder | Wait, check addresses and spam | `budget-alerts.mdx` L88-100 |
| External location Test connection fails (AWS) | IAM role not approved or still provisioning | Finish "Allow access", then re-test | `aws.mdx` L275-279 |
| Test connection fails (Azure) | Access connector lacks Storage Blob Data Contributor | Add the role on the storage account | `azure.mdx` L520-524 |
| Test connection fails (GCP) | Credential SA lacks bucket roles | Grant Legacy Bucket Reader and Object Admin | `gcp.mdx` L357-361 |
| Serverless cannot reach a private bucket or storage account | No NCC, or endpoint not approved | Create the NCC private endpoint rule; approve it on the storage account | `aws.mdx` L287-291; `azure.mdx` L544-548 |
| GCP file events never fire | Service-agent Pub/Sub Publisher grant missing | Grant it to the Cloud Storage service agent | `gcp.mdx` L369-373 |
| CDC validation fails | CDC/change tracking off, support objects missing, permissions | Use "Complete configuration" on the failed group | `cdc.mdx` L138-142 |
| CDC data gap after gateway downtime | Source log retention passed | Full refresh of the affected tables | `cdc.mdx` L150-154 |
| Query-based ingestion never sees updates | Cursor does not change on update | Choose a cursor that advances on every change | `query-based.mdx` L126-130 |
| Rows missing in query-based ingestion | NULL cursor values | Fix the source or choose another cursor | `query-based.mdx` L132-136 |
| SQL editor cannot find the silver tables | Wrong catalog selected | Select the catalog, then the schema | `query-and-explore.mdx` L178-182 |
| Create > Metric view disabled | Runtime older than 17.3 | Serverless warehouse or DBR 17.3+ | `metric-views.mdx` L158-162 |
| Metric view totals inflated | One-to-many join fan-out | Make the join many-to-one on the key | `metric-views.mdx` L164-168 |
| Genie or dashboard-with-Genie unavailable | Partner-powered AI features off | Account admin enables them | `dashboards.mdx` L113-117; `genie-agents.mdx` L116-120 |
| Shared Genie user gets an empty answer | Viewer lacks SELECT (the agent uses the viewer's identity) | Grant SELECT | `genie-agents.mdx` L122-126 |
| Genie One routes to the wrong surface | Routing words missing from page description or body; asset not in both Related Assets and Sources | Edit the page text and attach the asset twice | `domains-subdomains-pages.mdx` L364-376 |
| Domain not visible in Genie One | Pages, subdomain or domain unpublished | Publish each one; domain publish does not cascade | `domains-subdomains-pages.mdx` L350-362 |
| ABAC query fails with a permission error | Cluster runtime older than 16.4 | Serverless or DBR 16.4+ | `abac/index.mdx` L46-48 |
| dbdemos install hangs | No PyPI egress | Allow egress or use a suitable cluster | `additional-dashboards.mdx` L120-125 |

---

## 5. The "first 90 days" narrative

**How I would walk a customer through it.** I would follow the journey's own principle, foundations before workloads (`01-introduction/index.mdx` L14-24). I would re-sequence it in one respect: the governance **design** happens in week 1, even though the guide teaches it in Stage 4. The guide itself says to decide catalog, schema and grants "before anyone builds a pipeline" (`04-governance/index.mdx` L19), yet it places Stage 3's pipeline before Stage 4 (see §8 G5).

**Days 0-10: decide (mostly on paper) and stand up the control plane**
1. **Workshop the irreversible decisions** (table below). Cover tenant model, cloud and region, number of workspaces, workspace type (serverless vs classic vs Private Link), naming conventions for catalogs, groups and workspaces, the identity model, and who owns the metastore. Output: a one-page decision record (`single-tenant-setup.mdx` L44-46).
2. Give everyone the shared vocabulary: Foundations pages plus the Cheatsheet deck (`foundations/index.mdx` L22).
3. Create dev, staging and prod workspaces. Use serverless via the console for speed, or Terraform/SRA if the network must be customer-owned. Where Terraform is used, codify it from day one (`multi-tenant-setup.mdx` L54). With an AI coding agent, use the AI Platform Kit prompt and its plan → approve → apply → verify loop (§6).
4. Identity: SCIM, or Entra automatic identity management on Azure, into **account-level** persona groups plus per-workspace admin groups. Set up SSO. Make **`metastore-admins` the metastore owner** and turn on auto-assignment (`set-admin-group.mdx`).
5. **Cost guardrails before the first workload**: usage dashboard, tagging standard (team, project, env), serverless usage policies, compute policies that require tags, and dev budgets with thresholds (`cost-monitoring/*`). This must come now because tags cannot be backfilled. Note that the site's own "Do next" chain skips this subsection (§8 G4).

**Days 10-35: connect data and prove one pipeline end to end**
6. Storage: credentials and external locations per environment. Read-only for source buckets. A **new bucket per environment for managed storage**, with NCC if storage is private (`cloud-object-storage/*`).
7. Implement the governance skeleton: environment catalogs bound to workspaces, `[project]_bronze/_silver/_gold` schemas, ownership transferred to the admin group, schema-level Data Reader/Editor grants (`04-governance/*`).
8. Ingestion: one Lakeflow Connect source. Choose CDC or query-based with the §4 table, and confirm the network path (classic for the gateway, serverless for query-based).
9. First pipeline with Genie Code (bronze → silver with expectations) and a serverless 2X-Small warehouse with auto-stop. Answer one real business question and reconcile it (`build-first-pipeline`, `query-and-explore`). Schedule it as a Lakeflow Job.

**Days 35-60: trust and self-service**
10. ABAC: governed tags plus automatic classification plus schema-level mask and row-filter policies on sensitive domains, proven with the lab pattern (`abac/*`).
11. Semantic layer: the first **metric view** on the key KPIs in gold, reconciled against the known-good query (`metric-views.mdx`).
12. Consumption: an AI/BI dashboard bound to the metric view, a Genie Agent with instructions and benchmarks, rolled out to a pilot business group. Consider the ontology tree only once there is more than one surface to route between (`05-genie-ontology/*`).

**Days 60-90: industrialise**
13. Move the pipeline, job, dashboard and agent into a **DAB, one repo per project**, with GitHub Actions and SP OAuth deploying dev → staging → prod. Nobody writes to prod by hand from here on (`07-operations/index.mdx`; `small-organizations.mdx` L34).
14. If ML is in scope: deploy `mlops-quickstart` and register models in UC with aliases (`06-data-science/*`).
15. Operational review: budget-vs-actual from system tables, untagged-spend report (the gap-hunt query), access review from `system.access.audit`, and a freshness/ownership review of the Genie spaces.

**Decisions that are expensive to change later**

| Decision | Why it is expensive later | What the repo says | Source |
|---|---|---|---|
| Cloud tenant layout (single vs multi) | Moving workspaces and IAM between accounts is a migration project | "painful to unwind once workspaces are live" | `cloud-tenant-ready/index.mdx` L17 |
| Region | Workspaces cannot change region; data gravity and egress costs follow | "You cannot change this later" | `aws/serverless.mdx` L68, L119-121 |
| Workspace type and networking (serverless vs classic vs Private Link; VPC/VNet CIDRs) | Re-platforming means new workspaces and re-pointing all jobs | "The choices you make in the creation wizard are the choices you live with" | `create-workspaces/index.mdx` L17 |
| ADLS hierarchical namespace | Can only be set when the storage account is created | "You cannot turn it on for an existing storage account" | `azure.mdx` L32, L598-600 |
| Catalog, schema and prefix naming | Every query, dashboard and job references the names | "rewriting every reference to them, so it rarely happens" | `04-governance/index.mdx` L19, L58 |
| Group model (account-level, persona + BU prefixes) | Splitting flat groups means re-granting and re-sorting people | "splitting it is a migration" | `groups.mdx` L75 |
| Metastore owner = group | A departed person-owner blocks governance; recovery may need Databricks support | "governance operations stop" | `set-admin-group.mdx` L25-28, L113 |
| Tagging standard | Tags are forward-only; past spend stays unattributable | "Retrofitting attribution is not a thing" | `cost-monitoring/index.mdx` L16 |
| Managed storage location per catalog/env | Moving managed data means copying tables (inferred) | Deck: store managed data at metastore, catalog or schema level | UC deck slide 17 |
| Repo-per-project and CI identity (SPs) | Untangling a monorepo later is costly | "breaks down the moment a second team starts committing" | `07-operations/index.mdx` L159 |
| CDC gateway continuity | Downtime past retention forces a full refresh | "Do not stop the gateway" | `cdc.mdx` L108-110 |

---

## 6. AI-assistant prompts and guidance in the docs

The site has **12 `PromptBlock`s on 10 pages**, rendered by `site:src/components/PromptBlock/index.tsx` as a copyable block. The style guide allows a prompt "only when the prompt is a real step or a genuine alternative to a click" (`repo:docs/STYLE.md` L202-203). The docs name three assistants:
- **Genie Code**: the in-product assistant in the Pipelines Editor, SQL Editor, metric-view editor and dashboards.
- **Databricks Assistant (Genie)**: used on the Azure storage page.
- **AI Platform Kit**: `databricks-solutions/ai-platform-kit`, a skill pack for external coding agents.

The docs treat "Genie Code" and "Databricks Assistant" as the same product: "Adapt this template with Genie Code… using the built-in Databricks Assistant skills" (`06-data-science/index.mdx` L49), and "Open Databricks Assistant (Genie)" (`azure.mdx` L185). So "Genie Code" is presumably the current name of the Assistant's agent mode (inferred). Business users meet a separate Genie surface, **Genie One** (`domains-subdomains-pages.mdx` L271).

### 6.1 Inventory

| # | Assistant | Page (lines) | Purpose | Paired verification |
|---|---|---|---|---|
| 1-3 | AI Platform Kit (coding agent) | `create-workspaces/{aws,azure,gcp}/classic.mdx` (L30-55 / L32-57 / L38-63) | Generate and apply Terraform for a classic workspace plus UC | Plan review, explicit approval, "three-path verification" |
| 4 | Databricks Assistant ("Genie: storage credential") | `azure.mdx` L187-189 | Draft `CREATE STORAGE CREDENTIAL` SQL | Click-through steps follow |
| 5 | Databricks Assistant ("Genie: external locations") | `azure.mdx` L242-244 | Draft three `CREATE EXTERNAL LOCATION` statements | Test connection |
| 6 | Genie Code (Pipelines Editor) | `build-first-pipeline/index.mdx` L52-54 | Bronze/silver medallion pipeline | Review diff; column-name contract tip |
| 7 | Genie Code (SQL Editor) | `query-and-explore.mdx` L106-108 | Daily franchise revenue query | 4-point checklist plus fallback SQL |
| 8 | Genie Code (metric-view editor) | `metric-views.mdx` L65-67 | Metric view YAML | Checklist, fallback YAML, reconciliation query |
| 9 | "Create a dashboard with Genie" | `dashboards.mdx` L59-61 | One-page dashboard layout | Every widget on the metric view |
| 10 | Genie Agent **Instructions** | `genie-agents.mdx` L69-71 | Business vocabulary for the agent | Validation question vs dashboard |
| 11-12 | Genie One test questions | `domains-subdomains-pages.mdx` L285-287, L308-310 | Exercise both ontology routes | "Thought process" shows chosen sources |

Related guidance without a `PromptBlock`: the Genie Agent **Common questions** (`genie-agents.mdx` L81-83); "Use Genie's **Suggest a title**" for saved queries (`query-and-explore.mdx` L168); the mlops-quickstart "Adapt this template with Genie Code" section (`06-data-science/index.mdx` L49). The orphaned `Genie Best Practices.pdf` adds more: sample SQL with "Save as Instruction", benchmarks with gold-standard SQL, and "Genie is 'ignoring' my general Instructions → Try adding example SQL statements and removing unnecessary Instructions".

### 6.2 The AI Platform Kit prompt (the latest commit's "classic prompts")
PR #97 "switch[ed] classic prompts to AI Platform Kit". Today all three classic pages carry a "Prompt your coding agent" block pointing at the kit. What the prompts said before is (inferred), because the clone is shallow; the line "Do not clone a fixed technical-services-solutions template" suggests the older prompts pointed agents at those templates. AWS version, verbatim with blank lines removed (`aws/classic.mdx` L32-53):
```text
Install and use the Databricks AI Platform Kit (https://github.com/databricks-solutions/ai-platform-kit) if it is not already installed.
macOS/Linux: `bash <(curl -sL https://raw.githubusercontent.com/databricks-solutions/ai-platform-kit/main/install.sh)`
Windows PowerShell: `irm https://raw.githubusercontent.com/databricks-solutions/ai-platform-kit/main/install.ps1 | iex`
Then follow the kit skills (platform-provisioning, unity-catalog-setup, identity-governance, workspace-config, deployment-verification as needed) to provision a classic Databricks workspace on AWS with a customer-managed VPC (BYOVPC) and Unity Catalog.
Requirements for this deploy:
- Cloud: AWS
- Architecture: classic workspace with customer-managed VPC
- Include Unity Catalog (metastore assignment or creation as appropriate, plus catalog/storage pieces the skills recommend)
- Environments and naming: ask me for region, account ID, prefix (dev/staging/prod), networking choices, and any compliance constraints before generating Terraform
Workflow:
1. Confirm cloud and Databricks auth (aws configure / AWS CLI identity, Databricks CLI / account admin access).
2. Ask me for any missing value. Do not guess regions, CIDRs, prefixes, or account IDs.
3. Generate Terraform from the kit skills for my requirements. Do not clone a fixed technical-services-solutions template as the source of truth.
4. Run terraform init and terraform plan. Explain the plan (VPC, cross-account IAM, root storage, workspace, UC resources) before any apply.
5. Run terraform apply only after I explicitly approve the plan. Never apply or destroy without approval.
6. After workspace and UC are up, run the kit's mandatory three-path verification: classic cluster, serverless SQL warehouse, and serverless notebook job.
If something fails, diagnose with the kit gotchas guidance and re-plan before retrying.
```
The Azure and GCP versions differ in a few places:
- **Azure:** "VNet injection (No Public IP where appropriate)", "Pin DATABRICKS_AUTH_TYPE=azure-cli", `az login` with Contributor at subscription scope, and a plan explaining "resource groups, VNet/subnets/NSG/NAT".
- **GCP:** "Standalone / new VPC preferred", "Enable compute.googleapis.com", "gcloud auth, service account / impersonation", and a plan explaining "router/NAT, MWS network".

**Why it is a good prompt:**
- **It names its tools and skills.** The agent works from a curated, versioned knowledge pack, not from memory.
- **It gives the requirements as a checklist** and gathers inputs first ("ask me for…").
- **It forbids fabrication.** "Do not guess regions, CIDRs, prefixes, or account IDs" is the single most important line for infrastructure agents.
- **It has human-in-the-loop gates:** explain the plan, then apply only after "I explicitly approve"; "Never apply or destroy without approval".
- **It defines done as tests.** Three-path verification exercises the classic data plane, serverless SQL, and serverless jobs.
- **It bounds retries:** "diagnose… and re-plan before retrying", not blind re-apply.
- These mirror `repo:AGENTS.md` §4 "Goal-Driven Execution" ("Define success criteria. Loop until verified.").

**Weaknesses and risks** (what I would raise with a customer):
1. `curl … | bash` of an **unpinned `main`** script is supply-chain exposure; security teams in regulated industries will block it. Pin a tag or commit, or install from a reviewed fork (inferred advice).
2. The agent runs with **account-admin** credentials. Use a scoped service principal, a sandbox, and remote state with locking (inferred).
3. **Contradiction on the page:** the prompt says "Do not clone a fixed technical-services-solutions template as the source of truth". The table directly below recommends exactly those templates ("If you are **new to Databricks**, start with **Workspace + Catalog**", `aws/classic.mdx` L63-69). (CONFIRMED; §8 G22.)
4. Generated Terraform varies from run to run. Review and commit the **code**, not just the plan output, so the three environments stay identical (inferred).
5. It says nothing about the governance decisions that go with provisioning: naming convention, metastore-owner group, tags. Those still come from Stages 2 and 4.

### 6.3 Genie Code prompts (verbatim) and critique

**Medallion pipeline** (`build-first-pipeline/index.mdx` L53):
> Build a medallion pipeline from samples.bakehouse. Land the raw tables in bakehouse_bronze schema, then create silver tables with cleaned column names, typed timestamps, and expectations that drop rows with null primary keys and land them on bakehouse_silver schema.

- *Good:* It names the source, both target schemas and a data-quality rule (expectations). The page follows it with human review: "Review the plan and code diff… then click Accept all" (L60).
- *Weak:* "cleaned column names" leaves the output contract open. Downstream pages rely on exact names, so the page needs a patch tip, "If Genie Code named them differently, rename them now" (L79). "and land them on bakehouse_silver" could mean the *dropped rows* go to silver.
- *Better (inferred):* list the tables, primary keys and exact silver column names (`transaction_timestamp`, `total_price`, `franchise_id`, `franchise_name`), and say streaming table vs MV.

**Daily revenue SQL** (`query-and-explore.mdx` L107):
> Using the `transactions` and `franchises` tables in the current `bakehouse_silver` schema, write a query that joins them on `franchise_id`. Return the transaction date, franchise name, and total daily revenue. Calculate daily revenue as the sum of `total_price`, group by transaction date and franchise name, and sort by transaction date and franchise name.

- *Good:* It is effectively a spec: tables, join key, output columns, aggregation, grain and sort. It comes with a 4-point acceptance checklist (L118-121), a deterministic **fallback SQL** (L131-144), and a result sanity check (L160). This is the model pattern: **generate → verify against a checklist → keep a known-good fallback**.
- *Gap:* no time-zone rule for "date"; `metric-views.mdx` L179 later has to warn about time-zone mismatches.

**Metric view** (`metric-views.mdx` L66):
> Create a metric view on starterjourney_catalog.bakehouse_silver.transactions joined to starterjourney_catalog.bakehouse_silver.franchises on franchise_id, many-to-one. Add fields: franchise (the franchise_name from the join), sales_date (the transaction_timestamp truncated to a day), and product. Add measures: total_sales as SUM(total_price), order_count as COUNT(1), and avg_order_value as total_sales divided by order_count. Add the synonyms "revenue" and "sales" to total_sales, and "AOV" to avg_order_value.

- *Good:* fully qualified names, **join cardinality stated** (which prevents fan-out, the #1 metric bug), exact names and formulas, and **synonyms** that later help Genie map business words. It is backed by a checklist, fallback YAML and a reconciliation query against the saved SQL (L136-148).

**Dashboard** (`dashboards.mdx` L60):
> Build a one-page dashboard from the franchise_sales_metrics dataset. Add KPI counter cards for Total Sales, Order Count, and Avg Order Value. Add a line chart of Total Sales by Sales Date. Add a bar chart of Total Sales by Franchise and a bar chart of Total Sales by Product. Add a date range filter on Sales Date and a filter on Franchise. Lay it out cleanly on a single page.

- *Good:* it pins the governed dataset and lists each widget, measure and filter. The verification step is "confirm every widget uses the `franchise_sales_metrics` dataset" (L69).

**Genie Agent instructions** (`genie-agents.mdx` L70):
> "Sales" and "revenue" both mean Total Sales. Use Sales Date as the time dimension for any trend or over-time question. Franchise means the franchise name. When asked for the top or best franchise, rank by Total Sales.

- *Good:* four short rules that each remove a common natural-language ambiguity: a synonym, the default time axis, entity resolution, and the ranking metric. It is not an essay. This matches the Genie deck's advice to keep instructions concise and move complex logic into sample SQL.

**Genie One routing tests** (`domains-subdomains-pages.mdx` L286, L309):
> Show me a high-level snapshot of how our franchise sales are performing this month.
> Which 5 franchises had the lowest total sales, and how does their average order value compare to the network average?

- *Good:* these work like **unit tests for the router**, one per branch. The "Thought process" panel is the assertion (dashboard + metric view; agent + metric view) (L298, L323).
- *Weak:* the dashboard page's own example list includes "Which franchise has the highest revenue?" (L109), a ranking question that by the stated rules belongs to the agent. That weakens routing (§8 G14).

**Databricks Assistant prompts on Azure** (`azure.mdx` L188, L243): "Create a Unity Catalog storage credential that uses Azure Managed Identity… **Show the CREATE STORAGE CREDENTIAL SQL** and tell me which fields I need…", and a prompt for three external locations `dev_ext_loc`, `qa_ext_loc`, `prod_ext_loc`. *Good:* they ask for **reviewable DDL** rather than side effects. *Weak:* they use dev/**qa**/prod, while the rest of the journey uses dev/**staging**/prod.

### 6.4 Takeaways for using the Databricks Assistant (Genie Code) with customers
1. **Ground** prompts in fully qualified UC names and state join cardinality.
2. **Specify the output contract** (names, grain, measures, synonyms) whenever downstream objects depend on it.
3. Ask for **artifacts you can review** (a diff, SQL, a plan) before any side effects.
4. **Pair every prompt with an acceptance checklist and a deterministic fallback.**
5. **Reconcile** generated metrics against a known-good query before anyone sees them.
6. For agents that act (Terraform), require "ask, don't guess", **approval gates** and **post-verification**.
7. Treat routing and NL layers like code: **test cases per branch** and benchmarks over time (Genie deck).
8. Prerequisite: partner-powered AI features must be on (`dashboards.mdx` L116).

---

## 7. Repo mechanics: AI-maintained docs and freshness checks

### 7.1 Site plumbing
- **Stack:** Docusaurus 3.9.2 and React 19 (`site:package.json`). There is a local search plugin (no Algolia), client redirects that record the restructuring history (manual→serverless, terraform→classic, sra→private-link, business-semantics→metric-views, genie-spaces→genie-agents, databricks-apps→Genie Ontology index), and `numberPrefixParser: false`, so `01-…` prefixes survive in doc IDs and URLs (`site:docusaurus.config.ts`).
- **Broken links fail the build:** `onBrokenLinks: 'throw'`.
- **CI** (`repo:.github/workflows/`):
  - `test-deploy.yml`: PR to `main` → `npm ci` + `docusaurus build`.
  - `deploy.yml`: push to `main` → fetch npm packages from Databricks' **JFrog registry via GitHub OIDC** token exchange → build → upload the Pages artifact → deploy → **auto-release**: the next `vX.(Y+1).0` tag, a matching `release/<tag>` branch, and `gh release create --generate-notes`.
  - Actions are **SHA-pinned**. Dependabot runs yearly, minor and patch only. `CODEOWNERS` is a single owner (`@ivancalvo-dbxs`).

### 7.2 `repo:AGENTS.md`: the agent contract
- **Single source of truth:** "Do not recreate `CLAUDE.md`, `.cursorrules`, or tool-specific instruction duplicates" (L5-7).
- **Five behavioural guidelines** (L9-88):
  1. *Think before coding*: state assumptions and ask.
  2. *Simplicity first*: "If you write 200 lines and it could be 50, rewrite it".
  3. *Surgical changes*: "Every changed line should trace directly to the user's request".
  4. *Goal-driven execution*: turn tasks into verifiable goals and "Loop until verified".
  5. *Honest collaboration*: "Be a partner, not a yes-man"; never open with "You're absolutely right!"
- **Workflow** (§Git and GitHub): feature branches; commit or push only when asked; `gh` for GitHub tasks.
- **Doc change checklist** (L103-110):
  1. Read `STYLE.md`.
  2. Check `sidebars.ts`.
  3. Edit `.mdx` and register new pages.
  4. **Bump `section-freshness.csv`** in the same change.
  5. `npm run build`.
- **Authoring rules** summarise `STYLE.md`: two voices, shared chrome, three admonitions only, anti-slop rules, section-prefixed images.
- **"Adding a new section"** is a 6-step procedure: index page with `<StarterJourneyProgress currentLevel={N}/>`, subpages, sidebar entry, a **`journey-blocks.ts` update (`MAX_LEVEL`)**, prev/next links, then build plus CSV row plus `REQUIRED_SECTIONS` (L293-358).
- **Standards:** "PDF deck button" (`Button` + `useBaseUrl`, label `"Deck - [Topic]"`, placed inside `:::tip`, L392-427), and "Journey overview table sync" (L429-483).
- **"Common mistakes"** (L380-390), for example renaming a sidebar label without updating the frontmatter, H1, CSV and overview table.

### 7.3 `repo:docs/STYLE.md`: the voice and structure contract
- Two voices: **Build Log** for technical pages ("Lead with the outcome", steps "read like a log", one informative first-person aside, a "Where people trip" section) and **Field Notes** for educational pages ("Open with the call", one analogy, tradeoffs stated straight, opinions welcome) (L25-49).
- **Eleven anti-slop rules**, including **zero em or en dashes** and a banned-vocabulary list (L53-81).
- Screenshot guides must use `StepGuide`/`Step`/`StepImage`, one `idPrefix` per part, and follow the layout big picture → prerequisites → steps → verify → where people trip (L123-181).
- Prompts go in `PromptBlock` (L185-203).
- "The test: read the page out loud" (L222-225).

### 7.4 `repo:skills/humanizer/SKILL.md` (v2.8.0, MIT, "claude-code opencode")
- An editor skill based on Wikipedia's "Signs of AI writing".
- **33 patterns in 5 families:**
  - content: significance inflation, promotional tone, `-ing` padding, vague attributions, formulaic "challenges" sections;
  - language: AI vocabulary, copula avoidance, negative parallelisms, rule of three, synonym cycling, false ranges, passive fragments;
  - style: em dashes, boldface, inline-header lists, title case, emojis, curly quotes;
  - communication: chatbot artifacts, cutoff disclaimers, sycophancy;
  - filler and hedging: generic conclusions, hyphenation, authority tropes, signposting, fragmented headers, diff-anchored writing, staccato drama, aphorisms, rhetorical openers.
- **Detection guidance** warns against false positives: "look for clusters of tells, not isolated ones".
- **Process** (L522-529): draft → ask "What makes the below so obviously AI generated?" → final rewrite containing no em or en dashes. Deliverables: the draft, the still-AI bullets, the final, and a change summary.
- Note: the skill scopes its "personality" advice to opinion pieces; technical text should stay plain (L61).

### 7.5 `repo:skills/screenshot-guide/SKILL.md` (v0.1.0)
- **Inputs:** a reference `.md`, a folder of screenshots in order, optional prompts, the target doc path and slug.
- **Build:**
  - copy images to `static/img/<slug>/1.png…`;
  - write a Build Log page with one `Step` per action;
  - add `StepImage` with meaningful alt text and an `idPrefix` per part;
  - use `PromptBlock` only where it is real;
  - register the page in `sidebars.ts`.
- **Finish:** run the humanizer, scan for dashes and banned words, bump the CSV row, and `npm run build` until it passes.
- The pipeline behind a guide is: a human captures screenshots and a rough reference, then the agent produces a conformant page.

### 7.6 Components that enforce structure (code-stewardship notes)
- `StepGuide` auto-numbers its steps and gives each a stable anchor `${idPrefix}-${n}`, which is why the pages say "Every step links to itself".
- `StepGuide` **filters `children` to `Step` elements only** (`child.type === Step`). Any prose placed between `<Step>`s is **silently dropped** at render time.
- `StepImage` falls back to a "Screenshot coming soon" box when `src` is missing, and uses `placeholder` as alt text when `alt` is absent. `build-first-pipeline` relies on this fallback.
- `PromptBlock` copies `textContent`, so Markdown formatting such as backticks is not in the copied prompt. It silently does nothing when `navigator.clipboard` is unavailable (non-secure contexts).

### 7.7 How AI agents write and maintain the docs (end-to-end loop)
1. The agent loads `AGENTS.md`, the single cross-tool instruction file. Some agents only auto-load their own filename, so a tool may need to be pointed at `AGENTS.md` (SUSPECTED).
2. It reads `STYLE.md` and `sidebars.ts`, picks Build Log or Field Notes, and uses the **screenshot-guide skill** for click-through guides.
3. It drafts, then runs the **humanizer** loop and mechanical scans (dashes, banned words, admonition types).
4. It registers or relinks pages: `## Next` blocks, the overview table, and `journey-blocks.ts` if a section changed.
5. It **bumps `section-freshness.csv`** for each section it touched ("Do not finish a doc edit without updating `section-freshness.csv`", L190).
6. It runs `npm run build`; broken links fail.
7. PR → build check. Merge → deploy plus auto-release.
8. Weekly, the **freshness workflow** asks humans to revisit sections nobody has touched.

### 7.8 The freshness mechanism, and how `scripts/check_section_freshness.py` works
**Design:** a **self-attested** date per top-level section in `site:section-freshness.csv` (`section_name,last_update`). A weekly job fails if any section is more than 60 days old, then opens, updates or closes a GitHub issue. The source of truth is the CSV, not git history.

**Script logic** (stdlib only, 175 lines):
1. `REPO_ROOT = Path(__file__).resolve().parents[1]`. The default CSV path is absolute under it (L12-13). `REQUIRED_SECTIONS` is a hard-coded tuple of the 7 sidebar labels (L16-24). `STALE_DAYS = 60` (L26).
2. **CLI** (L29-47): `--csv`, `--report-file` (Markdown for the issue body), and `--today YYYY-MM-DD` (testability hook).
3. **`load_updates`** (L50-74) is strict:
   - the file must exist;
   - the header must be *exactly* `["section_name","last_update"]`;
   - blank names are skipped;
   - a **duplicate section is an error**;
   - dates are parsed with `date.fromisoformat` (a bad date is an error).
   - Every failure raises `SystemExit(message)`.
4. **`check_freshness`** (L77-100):
   - *configuration errors*: `missing` (required but not in the CSV) and `extra` (in the CSV but not required);
   - *stale list*: required sections where `today - last > timedelta(days=60)`. The comparison is **strictly greater**, so exactly 60 days is still fresh.
   - The stale list is sorted oldest first.
5. **`format_report`** (L103-132) builds Markdown: a header with the check date and threshold, then "Configuration errors", then "Sections past the freshness threshold", then instructions.
6. **`main`** (L135-171):
   - catches the loader's `SystemExit`, prints it and returns 1. **No report file is written** in this case; the notify script then falls back to "See workflow logs".
   - otherwise writes the report when `--report-file` is set;
   - config errors → exit 1;
   - stale → prints a list and a hint, exit 1;
   - else prints "All 7 sections are within 60 days." and exits 0.

**Workflow** (`repo:.github/workflows/section-freshness.yml`), triggered by cron `0 14 * * 1` (Mondays 14:00 UTC) and `workflow_dispatch`, with permissions `contents: read, issues: write`:
- The check step runs with `continue-on-error: true`, so later steps branch on `steps.freshness.outcome`, which stays `failure` even though the step's conclusion becomes success.
- On failure: `notify_stale_sections_issue.sh stale-sections-report.md`, then a final `exit 1` step so the run shows red.
- On success: `close_stale_sections_issue.sh`.

**Shell scripts:**
- `notify_…sh`:
  - reads the report, falling back to a generic message;
  - lists **human** contributors with `gh api /repos/$REPO/contributors --paginate -q '.[] | select(.type=="User") | .login' | sort -u`, which excludes bots;
  - builds an `@mention` line;
  - creates the label `section-freshness` idempotently (`|| true`);
  - finds an open issue with the exact title "Stale documentation sections" and that label. If found, it **edits the body and adds a comment** (re-pinging everyone); if not, it **creates** the issue. It uses `mktemp` plus `trap` for clean temporary files.
- `close_…sh` finds the same issue and closes it with `--reason completed`.

**What I verified by running it** (Python 3.11, scratch copies only; the repo was untouched):

| Test | Result |
|---|---|
| Today (2026-09-29), all rows dated 2026-09-24 | exit 0 ("All 7 sections are within 60 days.") |
| `--today 2026-11-23` (exactly 60 days, a Monday) | exit 0, so the **first scheduled failure is Monday 2026-11-30** |
| `--today 2026-11-24` with `--report-file` | exit 1; all 7 listed at 61 days; correct Markdown |
| Renamed section in the CSV ("7. Operations") | exit 1: "Missing sections… Unknown sections…", and the report file is written |
| CSV saved with a UTF-8 BOM (e.g. by Excel) | exit 1: `got ['<U+FEFF>section_name', 'last_update']`; the header check is strict |
| Date `20260924` (basic ISO) | Accepted on Python 3.11+ even though the message says "use YYYY-MM-DD" |
| **Stale data with `--csv` pointing outside the repo, or given as a relative path** | **Crash** with a `ValueError` traceback from `args.csv.relative_to(REPO_ROOT)` (L165). The exit code is still 1, so CI outcome is unaffected, but local users get a traceback instead of the hint. Fix: `args.csv.resolve()` or a try/except |
| Future-dated row (typo `2062-09-24`) | **Never flagged**: age −12,899 days is not greater than 60. A typo can silence a section for decades. Fix: reject `last > today` |

**Limitations** (inferred unless marked):
- **No sync check against `sidebars.ts`.** Renaming a label only in `sidebars.ts` still passes, because the script and CSV agree with each other. REQUIRED_SECTIONS could be derived by parsing `sidebars.ts` labels instead.
- **Self-attested and section-granular.** All 7 rows carry the same date, 2026-09-24, the day of the latest commit (CONFIRMED). That suggests bulk bumps, so "fresh" can mean "someone edited the CSV", not "someone reviewed every page". A per-page `last_reviewed` frontmatter field, or git-log-based ages, would be more honest.
- The check does not cover `AGENTS.md`, `STYLE.md` or the skills, and those are the stalest files in the repo (§8 G1-G2). The agent instructions go stale while the docs pass.
- The anti-slop rules have **no automated lint**, and 26 em dashes plus two `:::note` blocks have shipped (§8 G9). A grep step in `test-deploy.yml` would catch them.

### 7.9 Assessment
- **Strengths:** an explicit agent contract; style rules that can be checked mechanically; reusable skills; components that enforce shape; link-checked builds; a nudge that goes to *humans*; deterministic helpers (`--today`).
- **Weaknesses:**
  - The contract's own examples point to a site structure that no longer exists, so an agent following them literally would create wrong paths.
  - Freshness is attested, not measured.
  - Several style rules are unenforced.
  - Placeholder pages sit on the critical path.

---

## 8. Gaps, outdated content and contradictions

Items are numbered G1-G35 so other sections can reference them.

**Agent and repo instructions**
- **G1 CONFIRMED.** `repo:AGENTS.md` describes a site structure that no longer exists.
  - §Repository layout lists `01-get-started.mdx`, `02-before-you-start/` … `15-journey-progress-demo/` (L118-157).
  - The link-format example (L384) and the whole table-sync worked example (L457-483) use `09-unified-analytics/…` paths.
  - §Section freshness tracker says "Top-level sidebar sections (1–14 in `sidebars.ts`)" (L186). There are 7.
  - Path examples use `03-infra-setup/…` → "3. Infra Setup" (L109, L112, L202).
  - §Journey overview table sync points at `01-get-started.mdx` (L431-435). The table actually lives in `01-introduction/index.mdx` §What you'll build.
  - The "fork sections (multiple parallel tracks at the same level, like section 6)" instruction (L346) describes blocks that no longer exist; the code for them is vestigial (§2).
- **G2 CONFIRMED.** The canonical examples in `repo:docs/STYLE.md` §Screenshot guides (L127-128, L187) and `repo:skills/screenshot-guide/SKILL.md` (L24) have stale paths: `/docs/07-build-first-pipeline/`, `03-infra-setup/metastore-admins/set-admin-group`, `05-data-governance-strategy/uc-assets-ownership`. The pages now live at `03-data-access-etl/build-first-pipeline/`, `02-account-workspaces/metastore-admins/set-admin-group` and `04-governance/uc-assets-ownership`.
- **G19 CONFIRMED.** The inner `site:README.md` is stale. It says to deploy with `USE_SSH=true npm run deploy` (deploys actually go through GitHub Actions), describes an "Electric/neon" theme, and references `static/img/hero-sample.svg`, which does not exist.
- **G20 CONFIRMED.** The freshness script has defects, all verified in §7.8:
  - `relative_to` crash at L165 when `--csv` is outside the repo or relative and something is stale;
  - no future-date guard;
  - a BOM in the CSV breaks the header check;
  - no check that the section list matches `sidebars.ts`.

**Curriculum flow**
- **G3 CONFIRMED.** Placeholders sit on the critical path.
  - `04-governance/unity-catalog-setup.mdx` says "This guidance is a work in progress" (L12). It is the "Do next" of `medium-large-organizations.mdx` (L105) and a **prerequisite of Stage 5** (`05-genie-ontology/index.mdx` L12).
  - `05-genie-ontology/metadata-generation.mdx` is a placeholder and the first page of Stage 5.
  - The three `private-link.mdx` pages are link-only.
- **G4 CONFIRMED.** Following "Do next" from the Introduction skips **25 of 62 pages** (my crawl of the Do-next links):
  - `unity-catalog.mdx` L76 jumps to AWS serverless, skipping Cloud tenant ready (3 pages) and the Recap.
  - `add-users/scim.mdx` L107 jumps to Stage 3, skipping both add-groups pages, Set admin group, SSO, and **all 5 cost-monitoring pages**.
  - `set-admin-group.mdx` L125 also skips SSO.
  - This matters because the cost pages say tagging must start before usage.
- **G5 CONFIRMED.** Order contradiction. `04-governance/index.mdx` L19 says to decide catalog, schema and grants "before anyone builds a pipeline". Yet Stage 3 builds into `starterjourney_catalog`, which no page tells you to create (pages only create schemas inside it, e.g. `CREATE SCHEMA IF NOT EXISTS starterjourney_catalog.bakehouse_gold`). Stage 2 pages list Stage 4 pages as prerequisites (`add-groups/manual.mdx` L12; `set-admin-group.mdx` L12).
- **G6 CONFIRMED.** `02-account-workspaces/index.mdx` §In this section omits Cost monitoring. It also says "by hand or with Terraform" (L24), but the recommended serverless path is console-driven.
- **G15 CONFIRMED.** Data-science order is circular. `save-model-to-unity-catalog.md` has "Prepare Datasets" as its prerequisite (L11), but the sidebar puts `prepare-datasets` last, and `batch-inference.md` "Do next" points to it (L32). `06-data-science/index.mdx` lists Stage 7 as a prerequisite (L12).
- **G13 CONFIRMED.** `query-and-explore.mdx` never names the saved query ("Use Genie's Suggest a title", L168). `metric-views.mdx` L148 then refers to "the `daily_franchise_revenue` query you saved".
- **G35 CONFIRMED.** Option B in `save-model…md` never sets a model alias; only Option C does (L126-131). `batch-inference.md` loads "by alias" (L15).

**Internal contradictions and accuracy**
- **G7 CONFIRMED.** Naming drift in the business-unit prefix model. Compare:
  - prefix table: `finance_dev`, `finance-development`, `finance_data_engineers` (`medium-large-organizations.mdx` L28-30);
  - catalog list: `dev_finance`, `stg_finance`, `prod_finance` (L41-42), and "inside `dev_marketing`" (L69);
  - the page's own diagrams: catalogs `marketing_dev`/`finance_stg`, workspaces `mkt_dev`/`fin_prod`, groups `marketing-de/-ml/-bi` (`ucblog-multi-*.jpg`);
  - `groups.mdx`: `[bu-or-project]-data-engineers`;
  - the CI screenshot: `CATALOG=marketing_staging`.

  The page breaks its own pitfall: "The whole scheme falls apart if one team writes `fin_` and another writes `finance_`" (L93).
- **G8 CONFIRMED.** `cloud-object-storage/index.mdx` L28 says a storage credential wraps "An IAM role on AWS and GCP". `gcp.mdx` L25 and L72-80 say it is a Databricks-generated **GCP service account**.
- **G11 CONFIRMED.** The two pages disagree on dashboard sharing terms. `import-usage-dashboard.mdx` L63/L112 says "Viewer credentials / Editor credentials"; `dashboards.mdx` L93-94 says "Only people with access can view / Embed your credentials".
- **G12 CONFIRMED.** The `additional-dashboards.mdx` tip says the demo slug is `system-tables` (L21), but the code installs `"uc-04-system-tables"` (L65). Unresolved `<!-- TODO: verify before publishing -->` comments remain there (L25) and in `import-usage-dashboard.mdx` (L47).
- **G14 CONFIRMED.** Routing contradiction. The dashboard page body lists "Which franchise has the highest revenue?" (`domains-subdomains-pages.mdx` L109), a *ranking* question. The index routes rankings to the Genie Agent (`05-genie-ontology/index.mdx` L44). The question almost duplicates the agent's "Which franchise had the highest total sales?" (`genie-agents.mdx` L81).
- **G21 CONFIRMED (tension).** `create-workspaces/index.mdx` says each workspace "runs inside its own VPC" and to "Keep them isolated at the network level" (L19, L29). It then makes Serverless, which has no customer VPC, the default (L39). Serverless isolation (network policies, NCC) gets one sentence (L43).
- **G22 CONFIRMED.** The AI Platform Kit prompt says "Do not clone a fixed technical-services-solutions template as the source of truth" (`aws/classic.mdx` L48; azure L50; gcp L56). The table right below recommends those templates for beginners (L63-69).
- **G24 CONFIRMED.** The Azure external-location prompt uses dev/qa/prod (`azure.mdx` L243); every other page uses dev/staging/prod.
- **G25 CONFIRMED.** Problems in `dabs-definition.mdx`:
  - it hard-codes `gateway_storage_catalog: development` instead of `${var.dest_catalog}` (L58);
  - it says "Add this to your DABs `resources` block" (L39), but the snippet also has top-level `variables:`;
  - its Verify step says "Workflows > Delta Live Tables" (L149).
- **G34 CONFIRMED.** The small-org model relies on catalogs "bound to the development workspace" (`small-organizations.mdx` L30-34), but no page explains or shows **workspace-catalog binding**. It appears only in a diagram (`workspace-target.jpg`) and UC deck slide 15. `workspace.mdx` L54 ("Workspaces don't isolate data on their own") is true by default but incomplete.

**Style and hygiene (rules the repo sets for itself)**
- **G9 CONFIRMED.** Style rules are violated in several places:
  - **26 em or en dashes** across `gcp.mdx` (10), `save-model-to-unity-catalog.md` (8), `azure.mdx` (3), `aws.mdx` (3) and `abac/index.mdx` (2);
  - **`:::note`** at `aws.mdx` L111 and `gcp.mdx` L159 (only tip, warning and danger are allowed);
  - titled admonitions: `:::warning for better visibility` (`07-operations/index.mdx` L82, which also misuses warning for a UI hint) and `:::tip Unity Catalog: Data Access Control` (`abac/index.mdx` L159);
  - deck buttons not wrapped in `:::tip` (`foundations/index.mdx` L24; `04-governance/index.mdx` L38), and a label "Deck - UC best practices deck" that breaks the label rule;
  - promotional words: "definitive guide" (`06-data-science/index.mdx` L36), "Awesome pages" (`build-first-pipeline` L92);
  - an iframe without `title` (`orchestration/index.mdx` L21);
  - `build-first-pipeline` has no Verify or Where-people-trip section and uses `placeholder` instead of `alt`.
- **G10 CONFIRMED.** Product names drift across pages:
  - "Workflows > Delta Live Tables" (`dabs-definition.mdx` L149) vs "Jobs & Pipelines" (`cdc.mdx` L128);
  - "Spark Declarative Pipeline" (`build-first-pipeline` L10) vs "Lakeflow Declarative Pipeline" (`prepare-datasets.mdx` L4, L58, L61);
  - "Databricks Asset Bundles" (`dabs-definition.mdx` L3, L16) vs "Declarative Automation Bundles" (`managed-connectors/index.mdx` L59; `07-operations/index.mdx` L10, L36);
  - "Data Explorer" (`abac/index.mdx` L86, L98) vs "Catalog Explorer" (`uc-assets-ownership.mdx` L19);
  - "Genie spaces"/"Genie Space" (`groups.mdx` L46; `additional-dashboards.mdx` L74) vs "Genie Agents";
  - "Usage" vs "Consumption (Legacy)" (`import-usage-dashboard.mdx` L43, L77).
- **G17 CONFIRMED.** Wrong alt text: the UC isolation diagram is labelled "Account console user management screen" (`create-workspaces/index.mdx` L33), and the CI/CD diagram is labelled "Account Console high-level relation" (`07-operations/index.mdx` L90). Two iframes share one title (L58, L67). A section headed "DABs in the Workspace" embeds a video titled "Databricks VS Code Extension v2" (L43-50).
- **G26 CONFIRMED.** A blog post says its content "was used on the Data Governance Strategy section" (`site:blog/2026-02-12-medallion-architecture-medium.mdx` L8). That section is now "4. Governance".

**Missing or thin content**
- **G16 CONFIRMED.** `06-data-science/index.mdx` promises "Feature Store, MLflow, Model Serving, and batch inference" (L4), but there is no Model Serving page. `batch-inference.md` promises pandas and Spark UDF scoring (L4) and "large-scale tracked inference" (index L63) but contains **no code**.
- **G18 CONFIRMED.** Three decks are orphaned: `Genie Best Practices.pdf`, `UC-Metric-Views.pdf`, and `AWS-Automated-Configuration-Classic-Workspace-Deployment.pdf` (dated 2026-1-13). The last one documents a **no-Terraform "Automated Configuration" classic path**: AWS IAM temporary delegation, CloudTrail-logged, with "Request approval". `aws/classic.mdx` never mentions it.
- **G23 CONFIRMED.** A grep of all 62 pages finds **no** mention of:
  - Delta features: liquid clustering, predictive optimization, deletion vectors, OPTIMIZE/VACUUM, Photon;
  - ingestion and sharing: COPY INTO, Delta Sharing;
  - tables and compute: "external table", all-purpose vs job compute;
  - apps: Databricks Apps (the page was removed; a redirect remains in `site:docusaurus.config.ts`);
  - operations: Lakehouse Monitoring, disaster recovery;
  - audit: `system.access.audit` (deck only).

  Model Serving, Vector Search and agents are only mentioned in passing. Managed vs external tables appears only in the deck (slide 18).

**Suspected (not verified against current Databricks docs)**
- **G27 SUSPECTED.** The ABAC lab says "A plain tag works for this lab" (`abac/lab.mdx` L65). If ABAC match conditions require governed tags on the current platform, the lab's tags would have to be governed first (inferred).
- **G28 SUSPECTED.** In the ABAC index, the "bypass" example unsets a **schema** tag (`ALTER SCHEMA main.hr UNSET TAGS`, L75) and the governed-tag example sets one (L91). The policies shown match **column** tags (`MATCH COLUMNS has_tag_value…`). The prose also talks about "FILTER TAG bindings" (L71, L84), a term that does not appear in the SQL, which suggests older syntax.
- **G29 SUSPECTED.** `genie-agents.mdx` L125 says to grant SELECT on the metric view "and its source tables". View-style objects usually evaluate underlying access as the owner, so this may over-grant (inferred).
- **G30 SUSPECTED.** Preview labels may be stale by 2026-09: the "Serverless Workspaces" preview toggle (`aws/serverless.mdx` L45-50), Budgets "Public Preview" (`budget-alerts.mdx` L30), serverless usage policies "Public Preview" (`tag-compute-and-jobs.mdx` L32), and Usage Dashboard v2.0 (already carries a TODO).
- **G31 SUSPECTED.** The UC deck (©2024) uses DLT and Workflows naming, calls row and column security "in Preview", and says system tables "must be enabled by an account admin using the UC REST API" (slide 25). All of that is likely outdated.
- **G32 SUSPECTED.** "Bundles allow up to 25 tags per job definition" (`tag-compute-and-jobs.mdx` L85) mixes up job tags (a Jobs feature) with bundles. Serverless job attribution runs through usage policies, not job tags (inferred).
- **G33 SUSPECTED.** The CI example uses unpinned `databricks/setup-cli@main` (`07-operations/index.mdx` L112), while the repo pins its own actions to SHAs. The screenshot shows the environment's "Deployment branches and tags: No restriction", so any branch can deploy to it.

---

## 9. Explaining the platform in business terms, stage by stage

| Stage | Business framing (1-2 sentences) | How it scales |
|---|---|---|
| 1. Introduction | "We build the foundation once, one account, one governance layer, one copy of trusted data, so every report, model and AI assistant draws from the same source instead of each team rebuilding it." The cloud-tenant choice is "how many buildings you rent": usually one, more only when regulators or billing demand walls. | Adding a new workload reuses the foundation instead of starting a new silo. |
| 2. Account and workspaces | "We give you separate development, test and production rooms, plug in your corporate login so joiners and leavers are handled by HR systems, and switch on spend tracking before the first job runs, so finance can always see who spent what." | Identity scales by group membership; spend attribution scales by tags and policies, not spreadsheets. |
| 3. Data access and ETL | "We connect to data where it already lives and pull changes from your operational databases and SaaS apps with managed connectors. Scheduled pipelines turn raw feeds into clean tables the business can query." | Serverless pipelines and warehouses scale with load and stop when idle; CDC keeps the load on source systems low. |
| 4. Governance | "One rulebook decides who sees which data in every tool. Salaries or card numbers are masked automatically wherever they appear, so audits pass and teams share data without making copies." | Grants scale with groups × schemas, not users × tables; tag-based policies cover new tables automatically. |
| 5. Genie Ontology | "Each KPI is defined once, so the dashboard, the chat assistant and the analyst's SQL all show the same revenue number. Business users ask questions in plain English and get routed to the right trusted answer." | One metric view serves many consumers; the ontology absorbs new dashboards and agents without retraining users. |
| 6. Data science | "Models are versioned, approved and deployed like any other governed asset, so every prediction can be traced to the data and code that produced it." | Aliases and CI promotion let many models ship without manual hand-offs. |
| 7. Operations and CI/CD | "Everything becomes reviewed code that moves from test to production automatically, so there are fewer outages, faster releases, and no key-person risk." | One repo per team keeps release cadences independent as the number of teams grows. |

---

## 10. Interview-prep angles (Q&A)

1. **Why Unity Catalog?**
   - One governance layer across every workspace and asset type: tables, views, volumes, functions, models.
   - Permissions, lineage and audit are enforced "without extra work" because every access goes through UC grants (`unity-catalog.mdx` L48-52).
   - The data stays in the customer's cloud account; UC only governs access to it (L23).
   - The business angle: one place for audits, sharing by grant instead of by copy, and a base for features that need metadata (ABAC, metric views, Genie).
   - The anti-patterns it replaces: hardcoded credentials and cluster-level access, which can be neither audited nor revoked (L56-62).
2. **Serverless vs classic compute: when?**
   - Default to serverless: workspaces, SQL warehouses, pipelines, ML/GPU. There is no infrastructure to size, startup is fast, and small warehouses with 10-minute auto-stop cap idle spend (`create-workspaces/index.mdx` L39; `query-and-explore.mdx` L39-45).
   - Choose classic when you must own the network or pin hardware:
     - customer-managed VPC/VNet or SRA/Private Link requirements;
     - components that must sit in your network, such as the always-on CDC gateway (`cdc.mdx` L16);
     - specific instance types or autoscale pinned in DABs (`dabs-definition.mdx` L64-73).
   - Private data is reachable from serverless via an NCC (`aws.mdx` L109-220).
3. **Managed vs external tables?**
   - Managed: UC owns the files in the catalog's or schema's managed location. DROP deletes the data, only Delta is supported, and the platform tunes them automatically.
   - External: you own the path and lifecycle. DROP keeps the files, several formats are allowed, and optimisation is manual (UC deck slide 18: "Consider the benefits of Managed tables").
   - The journey's pattern: a new bucket per environment for managed tables and volumes, and external locations over existing buckets mainly to ingest from them, marked read-only (`aws.mdx` L18-19, L105-107).
   - Choose external for data shared with engines outside Databricks or with a lifecycle you must control (inferred).
4. **What is the medallion architecture, and when is it overkill?**
   - Bronze is raw, landed as it arrived (the replay point). Silver is cleaned, deduplicated and conformed, the analysts' source of truth. Gold is business aggregates: MVs and metric views for BI (`small-organizations.mdx` L44-48).
   - In UC it is implemented as project schemas, with grants that widen toward gold.
   - The repo does not discuss when it is overkill (G23). My answer: for small, clean, single-consumer data, collapse the layers into a raw landing plus one curated layer, because each hop adds storage, latency and code (inferred). The same instinct shows in "A five-person team does not need business-unit prefixed catalogs" (`04-governance/index.mdx` L62).
5. **How do you control cost?**
   - Visibility on day zero: the usage dashboard over `system.billing.usage` × `list_prices`.
   - Attribution from day one: custom tags on classic compute, serverless usage (budget) policies, compute policies that *require* tags. "Retrofitting attribution is not a thing."
   - Guardrails: budgets with thresholds (alert-only, list price, up to 24 h lag), small serverless warehouses with auto-stop, dev/prod separation.
   - A weekly untagged-spend query (`cost-monitoring/*`; `tag-compute-and-jobs.mdx` L114-162).
   - Scale point: budgets don't throttle, so enforcement comes from policies, not alerts.
6. **How do you get from a notebook to production?**
   - Prototype in the workspace: a Genie Code-assisted pipeline and a UI-built job.
   - Codify it as a **DAB** (jobs, pipelines, schemas, dashboards) in **one repo per project**, with trunk-based branches.
   - CI runs `bundle validate` → tests → `bundle deploy` per target, using **service-principal OAuth** and per-environment variables (catalog, schema).
   - Promote dev → staging → prod. Prod is written only by automation (`orchestration/index.mdx` L25-27; `07-operations/index.mdx` L16-187; `small-organizations.mdx` L34).
   - For ML, also register models in UC and promote by alias (`06-data-science/*`).
7. **How many workspaces, and how do you isolate environments?**
   - Three (dev, staging, prod), not one per team; teams are groups (`workspace.mdx` L14, L46).
   - Data isolation comes from UC: environment catalogs **bound** to their workspaces, and catalog-level managed storage per environment (`small-organizations.mdx` L30-34; UC deck slides 15-19).
   - Separate cloud accounts only for real billing, IAM or regulatory walls (`cloud-tenant-ready/index.mdx` L15-17).
8. **How do you design catalogs for a multi-BU organisation?**
   - Prefix workspaces, catalogs and groups with a short BU code (2-4 characters). Use medallion schemas per project inside each BU/environment catalog.
   - The owning group owns its schemas; cross-BU reads are explicit schema grants, never copies.
   - Write the naming convention down and enforce it; the repo's own examples show how easily it drifts (G7) (`medium-large-organizations.mdx`).
9. **CDC vs query-based ingestion?**
   - CDC reads the source's change log through an always-on gateway into a staging volume, captures every intermediate change, and puts little load on the source. The gateway must never stop longer than log retention (`cdc.mdx` L16, L108-110, L150-154).
   - Query-based polls with a cursor on a schedule. It is simpler (no gateway) and supports more sources, but sees only the latest state, needs a cursor that changes on every update, and adds source load, so index the cursor (`query-based.mdx`).
10. **How do you make KPIs consistent across BI and AI?**
    - Define a **UC metric view** in gold (source, joins with cardinality, dimensions, measures, synonyms), and **reconcile** it against a trusted query.
    - Bind dashboards and Genie Agents to it, so the ontology can route anywhere and still give the same number (`metric-views.mdx`; `05-genie-ontology/index.mdx` L46-47).
    - The business story is the "ARR = $2.5M vs $2.8M" problem (`UC-Metric-Views.pdf`).
11. **How would you roll out Genie to business users?**
    - Start from one topic-specific agent over curated, commented data (ideally a metric view).
    - Add a default warehouse, a description with limitations, short instructions (synonyms, time axis, ranking rules), common questions and sample SQL.
    - Validate against the dashboard with benchmark questions, then share with CAN RUN to a pilot group.
    - Watch the monitoring page and add instructions from real questions.
    - Only when several surfaces exist, add a Discover domain → subdomain → page ontology and test each route (`genie-agents.mdx`; Genie deck; `domains-subdomains-pages.mdx`).
    - Access runs as the **viewer's** identity, so UC grants still apply (L125).
12. **How do you mask PII at scale?**
    - ABAC:
      1. Classify columns with **governed** tags, or automatic classification system tags.
      2. Write small masking and row-filter UDFs.
      3. Attach **one policy per schema or catalog** with `TO … EXCEPT` exemptions.
    - New tables are covered as soon as they are tagged.
    - Redaction by default; SHA-256 when cross-dataset joins matter.
    - Needs DBR 16.4+ or serverless (`abac/index.mdx`; `abac/lab.mdx` L269).
13. **Terraform vs DABs?**
    - "Anything outside the workspace is Terraform's job; anything inside it is DABs": accounts, networks, metastores, workspaces and IAM vs jobs, pipelines, schemas and dashboards.
    - Mixing them up leads to drift and deploys that only one person can run (`07-operations/index.mdx` L16-32, L181-187).
14. **How do you use the Databricks Assistant (Genie Code) responsibly?**
    - Fully qualified names and explicit contracts in prompts.
    - Review the diff against a checklist and keep a deterministic fallback.
    - Reconcile the numbers.
    - For agents that act (AI Platform Kit): ask, don't guess; plan → approve → apply; verify all three compute paths (§6).
15. **Debugging: an external location's "Test connection" fails. Walk me through it.**
    1. Isolate the layer. Can you even see the location? If not, you are missing metastore-admin membership or privileges (`uc-assets-ownership.mdx` L27-30).
    2. Check the cloud identity's rights on the path:
       - AWS: role approved and provisioned (`aws.mdx` L275-279);
       - Azure: connector has Storage Blob Data Contributor, and the Resource ID is complete and in the same region (`azure.mdx` L520-536);
       - GCP: the `db-uc-credential-` SA has Legacy Bucket Reader and Object Admin (`gcp.mdx` L357-361).
    3. URL format and HNS (`abfss://…dfs…`, `gs://bucket/dir`).
    4. If only serverless fails, it is the network: NCC private endpoints, which must be approved (`aws.mdx` L287-291; `azure.mdx` L544-548).
    5. Re-test; the checks name the failing permission (`aws.mdx` L259).
16. **Debugging: Genie says X, the dashboard says Y.**
    - First confirm both use the same metric view.
    - Then compare time windows and filters: dashboard-level filters, time zones.
    - Inspect Genie's generated SQL and "Thought process".
    - Fix with an instruction or sample SQL. If the metric itself is wrong, fix the metric view once, and every consumer is corrected (`genie-agents.mdx` L128-132; `dashboards.mdx` L125-129; `domains-subdomains-pages.mdx` L378-383).
17. **Why must the metastore owner be a group, and how does identity fit together?**
    - A person or SP owner blocks governance the day they leave or are deleted (`set-admin-group.mdx` L25-28).
    - The full chain is: SCIM (or Entra auto-sync) brings users and groups to account level → groups are assigned to workspaces → SSO handles authentication, not authorisation → UC grants go to groups → ownership of UC assets is transferred to the admin group (Stage 2 and 4 pages).
18. **Computational thinking: how would you improve this repo's freshness mechanism?**
    1. Break the problem apart: *what* is stale (sections vs pages vs instructions), *how* to measure it (attested dates vs git history vs product-release signals), and *who acts* (issue owners).
    2. Fix the concrete defects: `resolve()` before `relative_to`, reject future dates, accept a BOM (`utf-8-sig`).
    3. Derive `REQUIRED_SECTIONS` from `sidebars.ts` so the two cannot disagree.
    4. Track per-page `last_reviewed` in frontmatter plus owners, and add AGENTS.md, STYLE.md and the skills to the check.
    5. Add a CI lint for the anti-slop rules and admonition types (§7.8, G1-G2, G9, G20).

---

## 11. Glossary

| Term | One-line definition (as used in the repo) |
|---|---|
| Account console | Admin portal above all workspaces: workspaces, identity, metastores, billing, SSO/SCIM (`account-console.mdx`). |
| Account admin / workspace admin | Account-wide control vs admin rights scoped to one workspace. |
| Workspace | Region-scoped environment bundling compute, code, storage references and permissions. |
| Cloud tenant | One AWS account, Azure subscription or GCP project that holds workspaces. |
| Single- / multi-tenant | All workspaces in one cloud account vs spread across several. |
| Unity Catalog (UC) | Central governance layer for permissions, lineage, discovery and audit on all data and AI assets. |
| Metastore | Top-level UC container; one per region per account, shared by that region's workspaces. |
| Three-level namespace | `catalog.schema.object` addressing. |
| Catalog / schema | First and second levels of the namespace; here, environment/BU and project-layer respectively. |
| Workspace-catalog binding | Restricting a catalog to specific workspaces ("bound to the development workspace"). |
| Grants / privileges | Permissions on UC objects given to users, groups or SPs (e.g. `CREATE EXTERNAL LOCATION`). |
| Data Reader / Data Editor | Privilege presets for read-only vs read-write at schema or catalog level. |
| Owner | Principal that manages an object and grants on it; should be a group. |
| Metastore admin | Group that owns the metastore and approves catalogs, locations and connections. |
| Service principal (SP) | Non-human identity for automation (Terraform, CI, prod jobs). |
| SCIM | Protocol for syncing users and groups from the IdP to Databricks. |
| Automatic identity management | Azure's built-in Entra ID sync that replaces manual SCIM setup. |
| SSO | Sign-in through the corporate IdP (SAML/OIDC); authentication only. |
| Storage credential | UC object wrapping a cloud identity (IAM role, Azure managed identity, GCP service account). |
| External location | UC object binding a storage path to a credential, with its own grants. |
| Access Connector for Azure Databricks | Azure managed identity behind an Azure storage credential. |
| NCC (Network Connectivity Configuration) | Account-level config that gives serverless compute private endpoints to your resources. |
| Private Link / SRA | Private network connectivity / Security Reference Architecture hardened Terraform templates. |
| BYOVPC / VNet injection | Customer-managed network for classic workspaces on AWS/GCP and Azure. |
| Serverless workspace | Workspace where Databricks manages compute and default storage; no customer VPC. |
| Managed vs external table | UC-managed files and lifecycle vs files at a path you manage. |
| Volume | UC-governed storage for non-tabular files. |
| System tables | Read-only `system.*` tables for billing, audit and lineage (e.g. `system.billing.usage`). |
| DBU | Databricks Unit, the billing unit that list prices convert to dollars. |
| Custom tags | Key/value labels on compute that flow to billing (`custom_tags`). |
| Serverless usage (budget) policy | Policy that attaches tags to serverless usage (`usage_metadata.budget_policy_id`). |
| Compute policy | Rules constraining cluster configs, e.g. required tags. |
| Budget | Account-level monthly spend monitor that emails at thresholds; does not throttle. |
| SQL warehouse | Compute for SQL/BI; here serverless, 2X-Small, auto-stop 10 min. |
| Lakeflow | Databricks' data-engineering family: Connect, Declarative Pipelines, Jobs. |
| Lakeflow Connect | Managed connectors ingesting databases and SaaS into UC streaming tables. |
| UC connection | Governed object holding source-system credentials. |
| Ingestion gateway | Always-on classic-compute process that captures CDC changes into a staging volume. |
| CDC | Change data capture from the source's change log. |
| Query-based connector | Scheduled incremental reads using a cursor column (high-water mark). |
| Cursor column | Monotonic timestamp or integer used to find new or changed rows. |
| SCD type 1/2 | Overwrite-in-place vs keep-history modes for changed rows. |
| Spark/Lakeflow Declarative Pipelines (SDP/LDP; formerly DLT) | Declarative ETL framework with streaming tables, MVs and expectations. |
| Streaming table / materialized view | Incrementally appended table / precomputed query result maintained by pipelines. |
| Expectations | Data-quality constraints in pipelines (e.g. drop rows with null keys). |
| Auto Loader | Incremental file-ingestion source for cloud storage. |
| File events | Storage notifications (Pub/Sub, EventGrid/Queue) replacing directory listing. |
| Lakeflow Jobs | Orchestrator for tasks, dependencies, schedules, retries and notifications. |
| Medallion architecture | Bronze (raw) → silver (clean) → gold (business) layering. |
| ABAC | Attribute-based access control: tag-matched policies apply masks and filters. |
| Custom / governed / system tags | Free-form / policy-controlled values / Databricks-generated (read-only) tags. |
| Data classification | Automatic PII detection writing `databricks:columnPiiTypes` system tags. |
| Column mask / row filter | UDF that substitutes a column value / BOOLEAN UDF that hides rows. |
| Metric view | Governed UC object defining measures, dimensions and joins, queried with `MEASURE()`. |
| AI/BI Dashboard | Databricks-native dashboard; can be generated with "Create a dashboard with Genie". |
| Genie Agent (formerly Genie space) | Natural-language Q&A over curated data, with instructions and common questions. |
| Genie One | Business-user Genie surface that routes questions through the ontology. |
| Genie Ontology | Discover tree of domain → subdomain → page used to route questions to dashboards or agents. |
| Discover / domain / subdomain / page | Catalogue surface and its routing nodes; pages attach Related Assets and Sources. |
| Genie Code | Assistant mode in editors that generates pipelines, SQL, metric views and dashboards (≈ Databricks Assistant). |
| AI Platform Kit | `databricks-solutions/ai-platform-kit` skill pack that coding agents use for provisioning. |
| Partner-powered AI features | Account and workspace setting that must be on for Genie features. |
| MLflow 3 | Tracking, registry and deployment toolkit; registry URI `databricks-uc`. |
| Model alias (challenger/champion) | Mutable pointer to a model version used for promotion and inference. |
| Model signature / input example | Logged schema and sample that document and validate model I/O. |
| Feature table / FeatureLookup | UC table of features / API to join them into training sets. |
| Online tables / Feature Serving | Low-latency feature access for real-time inference. |
| Spark UDF (inference) | Distributed model scoring over DataFrames. |
| Serverless ML / GPU | Managed notebook environments with ML libraries; GPU accelerator option. |
| DABs | Declarative Automation Bundles (formerly Databricks Asset Bundles): YAML "Databricks as code" deployed with `databricks bundle`. |
| Terraform provider (account vs workspace level) | IaC provider scope; UC catalog resources need a workspace-level provider. |
| Trunk-based development | Short-lived branches merged quickly into an always-deployable `main`. |
| DABs migrator | Unofficial tool that converts existing workspace assets into bundles. |
| dbdemos | Library that installs demo notebooks, dashboards and Genie spaces into a chosen catalog and schema. |
| Lakebase | Managed Postgres OLTP engine integrated with the lakehouse (cheatsheet; bundle examples). |
| StepGuide / PromptBlock (site) | React components for numbered screenshot walkthroughs and copyable prompts. |
| Section freshness | Weekly check that each journey section's CSV date is at most 60 days old. |
| Humanizer skill | Agent skill that rewrites prose to remove 33 AI-writing patterns. |
