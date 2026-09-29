# starter-journey: from an empty account to a governed, cost-visible, CI/CD-ready platform

**Repo:** `databricks-solutions/starter-journey` @ `ac21559` (2026-09-24). A Docusaurus site: 62 doc pages in 7 stages, plus decks, written by field engineers "who have set up hundreds of customer accounts". As-is, not formally supported.
**How I studied it:** a deep-read of every page, deck, skill and script, with a static link check (284 internal links and 269 images all resolve) and runs of the freshness script. I re-ran the freshness edge cases myself (below). The raw report is in [`appendix/deep-read-reports/starter-journey.md`](../appendix/deep-read-reports/starter-journey.md).

**Why it matters for the interview:** it is the **platform-fundamentals** reference, the "first 90 days" with a customer, and it's full of well-built Assistant prompts paired with verification steps. My distillation is [`cheatsheets/platform-fundamentals.md`](../cheatsheets/platform-fundamentals.md).

## 1. What it is, for a customer

An opinionated runbook in dependency order:

| # | Stage | You end with |
|---|---|---|
| 1 | Introduction | A mental model (account console, workspace, Unity Catalog) and a single- vs multi-tenant decision, made before anything is deployed |
| 2 | Account and workspaces | dev/staging/prod workspaces; SCIM-synced account-level users and groups; SSO; a **group** owning the metastore; usage dashboards, tags and budgets from day zero |
| 3 | Data access and ETL | Storage credentials + external locations; Lakeflow Connect ingestion; a bronze/silver pipeline built with Genie Code; a serverless SQL warehouse |
| 4 | Governance | Persona groups, group ownership of UC assets, catalog/schema/grant layout sized to the org, ABAC masks and row filters |
| 5 | Genie Ontology | One governed **metric view** feeding a dashboard and a Genie Agent, plus a domain → subdomain → page tree so Genie One routes questions |
| 6 | Data science | MLflow 3 + UC model registry with aliases; batch inference; feature tables |
| 7 | Operations and CI/CD | **Terraform for anything outside a workspace, DABs for anything inside**; one repo per project; GitHub Actions deploy |

One dataset (`samples.bakehouse`) threads from the first pipeline to a Genie One question, so every artifact is created once and reused.

## 2. The ideas I'd reuse with every customer

- **Build in dependency order.** "If the tables are wrong, reports mislead, models train on noise, and agents return unreliable answers." Fix the shared layers once, then build workloads on top.
- **Decisions that are expensive to change later** (the table I'd walk a customer through in week 1): tenant layout, **region** (a workspace can't move), workspace type and networking, ADLS hierarchical namespace (set at creation only), **catalog/schema naming** ("rewriting every reference"), group model, **metastore owner = a group**, **tagging standard** ("Retrofitting attribution is not a thing"), managed storage location per catalog, repo-per-project and CI identity, CDC gateway continuity.
- **Three workspaces, not one per team.** Teams are groups. "Workspaces don't isolate data on their own": data isolation comes from UC (environment catalogs bound to workspaces, catalog-level managed storage).
- **Grant to groups, at schema level,** with Data Reader/Editor presets. Per-table grants "break the moment someone adds a new table".
- **Ownership ≠ privilege.** Transfer ownership of credentials, locations, catalogs and schemas to the admin group; grant working privileges separately.
- **Cost from day zero:** usage dashboard, tags + serverless usage policies + compute policies that *require* tags, budgets (which **don't throttle**, lag up to 24 h, and use list price).
- **One KPI definition:** a metric view in gold, **reconciled against a known-good query**, with joins checked to be many-to-one ("Metric view totals inflated → one-to-many join fan-out").
- **Dashboard sharing is a governance decision:** "Only people with access can view" keeps row/column rules per viewer; "Embed your credentials" runs as the publisher.

## 3. Its Assistant prompts: the model pattern

The daily-revenue prompt is effectively a spec: tables, join key, output columns, aggregation, grain and sort. The page pairs it with a **4-point acceptance checklist, a deterministic fallback SQL, and a sanity check** on the result. That is the pattern I want to demonstrate live: **generate → verify against a checklist → keep a known-good fallback.**

The metric-view prompt states fully qualified names, **join cardinality** ("many-to-one", which prevents the #1 metric bug), exact measure formulas and synonyms, and is backed by a reconciliation query.

The AI Platform Kit prompt (for a coding agent writing Terraform) is the best "agent that acts" prompt in the six repos:
- "Ask me for any missing value. **Do not guess regions, CIDRs, prefixes, or account IDs.**"
- "Explain the plan … before any apply. Run terraform apply **only after I explicitly approve** the plan. Never apply or destroy without approval."
- Done = "three-path verification: classic cluster, serverless SQL warehouse, and serverless notebook job."
- "If something fails, diagnose … and **re-plan before retrying**."

Its weaknesses are also worth saying out loud: `curl … | bash` of an unpinned `main`; account-admin credentials for the agent; and a contradiction on the same page (the prompt says don't clone the TSS templates; the table below recommends them).

Weak spots in the Genie Code prompts, and how I'd fix them: "cleaned column names" leaves the output contract open (downstream pages depend on exact names, so the page needs a "rename them now" patch tip); "date" has no time-zone rule (a later page has to warn about time-zone mismatches). **Specify the output contract whenever something downstream depends on it.**

## 4. What I found (status-tagged)

| # | Finding | Status |
|---|---|---|
| 1 | **Freshness check trusts a typo:** a section dated `2062-09-24` is never flagged (age is negative, and the check is `age > 60 days`), so a typo silences a section for decades. Fix: reject `last_update > today` | CONFIRMED by my run: the 2062 row was not listed; only the genuinely stale section was |
| 2 | Same script crashes with a `ValueError` traceback (`args.csv.relative_to(REPO_ROOT)`, L165) when `--csv` points outside the repo and something is stale. Exit code is still 1, so CI is unaffected | CONFIRMED by my run |
| 3 | Freshness is **self-attested**: all 7 rows carry the same date as the latest commit, and the check doesn't cover `AGENTS.md`, `STYLE.md` or the skills, which are the stalest files (they describe a site structure that no longer exists) | CONFIRMED (deep-read) |
| 4 | Following "Do next" from the Introduction **skips 25 of 62 pages**, including all 5 cost-monitoring pages, although those pages say tagging must start before usage | CONFIRMED (deep-read crawl) |
| 5 | Order contradiction: governance says decide catalogs and grants "before anyone builds a pipeline", but Stage 3 builds a pipeline into a catalog no page tells you to create | CONFIRMED (deep-read) |
| 6 | Cost query uses a **containment** price join with an INNER JOIN, which drops usage that spans a price change or has no price | Mechanics CONFIRMED by me ([case 08](../case-studies/08-price-join-containment-vs-point-in-time.md)) |
| 7 | Naming drift in the multi-BU prefix model (`finance_dev` vs `dev_finance` vs `finance-development` …), on the page whose own pitfall is "the whole scheme falls apart if one team writes `fin_` and another writes `finance_`" | CONFIRMED (deep-read) |
| 8 | No mention anywhere of liquid clustering, predictive optimization, deletion vectors, OPTIMIZE/VACUUM, Photon, COPY INTO, Delta Sharing, job vs all-purpose compute, DR | CONFIRMED gap; I cover them in the platform-fundamentals cheatsheet (labelled as general practice) |

## 5. How it scales (the business framing per stage)

- **Identity** scales by group membership; **spend attribution** by tags and policies, not spreadsheets.
- **Grants** scale with groups × schemas, not users × tables; tag-based ABAC policies cover new tables automatically.
- **Serverless** pipelines and warehouses scale with load and stop when idle; CDC keeps load on source systems low.
- **One metric view serves many consumers;** the ontology absorbs new dashboards and agents without retraining users.
- **One repo per team** keeps release cadences independent as the number of teams grows.

## 6. How I'd explain it

- **Executive:** "We build the foundation once (one account, one governance layer, one copy of trusted data) so every report, model and assistant draws from the same source instead of each team rebuilding it. Spend tracking is on before the first job runs."
- **Platform engineer:** "Account console for account-level things, workspaces for data work; SCIM to account-level groups; group-owned metastore; environment catalogs bound to workspaces; schema-level grants; Terraform outside the workspace, DABs inside."
- **Stakeholder:** "It's the field team's default path. Two fixes I'd make: put the governance *design* in week 1 (it's taught in stage 4), and make the freshness check measure rather than attest."

## 7. Interview angles

1. **"How many workspaces, and how do you isolate environments?"** Three; teams are groups; isolation from UC (bound catalogs, catalog-level managed storage); separate cloud accounts only for real billing/IAM/regulatory walls.
2. **"CDC vs query-based ingestion?"** CDC: every change, low source load, an always-on gateway that must never stop longer than log retention. Query-based: simpler, latest state only, needs a cursor that changes on every update and is never NULL, adds source load (index the cursor).
3. **"Genie says X, the dashboard says Y."** Same metric view? Then compare filters and time windows (time zones), inspect Genie's SQL and "Thought process", fix with an instruction or sample SQL, or fix the metric view once for every consumer.
4. **"Why must the metastore owner be a group?"** A person or SP owner blocks governance the day they leave.
5. **"Improve this repo's freshness mechanism"** (computational thinking): separate *what* is stale, *how* to measure it, and *who acts*; fix the two defects; derive the section list from `sidebars.ts`; per-page `last_reviewed`; include the agent instructions.
