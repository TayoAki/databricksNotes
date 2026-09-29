> **Provenance.** Deep-read of `databricks-solutions/vibe-coding-workshop-template` @ `a26c6d0`, written by a research sub-agent during this study and kept verbatim, apart from local paths normalised to `<clone-root>/`. Its CONFIRMED / SUSPECTED labels are the agent's. The claims I re-verified myself, and how, are listed in [`README.md`](README.md); anything not listed there I have not independently checked.

# Deep-read report: `databricks-solutions/vibe-coding-workshop-template`

**Clone:** `<clone-root>/vibe-coding-workshop-template` · **HEAD:** `a26c6d0` ("Add AI/BI custom-viz (Vega-Lite) and custom-page (React) skills; reconcile dashboards skill to 12-column grid") · **Read on:** 2026-09-29.
**Method:** I read every orchestrator and most workers in full or by section, grepped all 421 markdown files for NEVER / CRITICAL / MANDATORY / ❌ / "Common Mistakes" / anti-pattern, and read the Python in `scripts/` in full. I also ran `audit_genie_compat.py`, `genie_gate.py` and `verify_agent_track_flow.py` read-only (bytecode off, CSV output sent to the scratchpad). `git status` stayed clean.
**Labels:** **CONFIRMED** means I verified it in the files or by execution. **SUSPECTED** means it is a strong signal I did not execute or check against live docs. "(inferred)" marks my reasoning or general platform knowledge that this repo does not verify.
**Citations:** a citation is `path:line`, with paths relative to the repo root. `DPA/` = `data_product_accelerator/skills/`, `GA/` = `genai-agents/`.

---

## 0. Orientation facts (read this before the rest)

- **Skill count.** The tree holds **93 `SKILL.md`** files: root `skills/` 5 (including a stray one), `apps_lakebase/` 10, `data_product_accelerator/` 48, `genai-agents/` 29, `agentic-framework/` 1. The docs quote four different counts: 44 (`AGENTS.md:187`), 45 (`AGENTS.md:5`, `data_product_accelerator/AGENTS.md:18`), 55 (`data_product_accelerator/README.md:3`) and 77 (`README.md:5`, `QUICKSTART.md:64`). CONFIRMED stale.
- **Files the docs reference that are absent from the public clone.**
  - `apps_lakebase/prompts/`, cited by `AGENTS.md:23`, `README.md:94` and `QUICKSTART.md:32`. `scripts/genie_gate.py:14` and `:138` call it the *"git-ignored, separate-repo prompts tree"*.
  - The root `Instructions.md` and `example/`, which `skills/vibecoding-state/SKILL.md:40,659` point to.
  - `data_product_accelerator/context/`. The sample CSV actually lives at `data_product_accelerator/docs/reference/Wanderbricks_Schema.csv`.
  - `data_product_accelerator/docs/agent-walkthrough.md`, cited at `DPA/skill-navigator/SKILL.md:36`.
- **The input contract.** The schema CSV is a raw `information_schema.columns` export: 33 columns, 16 tables and 114 rows for Wanderbricks (`amenities`, `bookings`, `booking_updates`, `clickstream`, `payments`, `properties`, `reviews`, `users`, …). The skills only need `table_catalog, table_schema, table_name, column_name, ordinal_position, full_data_type, (data_type), is_nullable, comment` (`data_product_accelerator/QUICKSTART.md:45`, `DPA/skill-navigator/SKILL.md:105`). In business terms, the customer shares metadata, not data.
- **The real 9 stages.** They differ from the brief's list: **1 Gold Design → 2 Bronze → 3 Silver → 4 Gold Impl → 5 Planning → 6 Semantic (Metric Views, TVFs, *Genie*) → 7 Observability → 8 ML → 9 GenAI** (`data_product_accelerator/AGENTS.md:43`). Genie is part of stage 6; Planning and Observability are stages of their own.

---

## 1. What it is (customer framing)

This is a template for **AI-assisted ("vibe coding") delivery of governed data products on Databricks**. It does not ask the coding assistant to recall how to build a lakehouse. It hands the assistant a library of about 90 versioned, hand-curated instruction packs (`SKILL.md` "agent skills"). The packs encode Databricks best practices and the failure modes seen in the field.

The approach is design-first. You start from a metadata-only export of the source schema. The AI designs the target star schema (Gold) first, then builds Bronze, Silver and Gold as governed, bundle-deployed jobs, then plans and builds the consumption layer: Metric Views, TVFs, Genie spaces, dashboards, monitors, ML models and GenAI agents. Each stage is one prompt in one fresh conversation, and every stage passes through explicit validation gates. Everything ships as a Databricks Asset Bundle, so it is reproducible, reviewable and promotable to prod.

A second path builds a full-stack **Databricks App (AppKit + Lakebase Postgres)**, optionally fronting a separately deployed Python agent with on-behalf-of-user auth, chat history and MLflow-linked feedback. The pitch is faster time to a working, governed data product (the accelerator claims 4-6x, `data_product_accelerator/README.md:161-168`, unverified). The less-advertised value is that it turns tacit expertise into checklists an AI can follow and a human can audit.

---

## 2. Architecture of the skill system

### 2.1 Routing and loading diagram

```
                ┌──────────────────────────────── repo root ────────────────────────────────┐
  user prompt → │ AGENTS.md  (universal entry; keyword → component routing; RULE_0 preamble)│
                └───────┬──────────────────────┬──────────────────────┬─────────────────────┘
                        │                      │                      │
   data_product_accelerator/AGENTS.md   apps_lakebase/skills/   genai-agents/00-course-orchestrator
   (stage routing table + worker table) 00-appkit-navigator     (navigator: Foundation→Track A→SDLC)
                        │
         DPA/skill-navigator/SKILL.md (tiered loading, routing algorithm, budget zones)
                        │
   ┌────────────────────┼──────────────────────────────────────────────────────────┐
   │ ORCHESTRATOR 00-*  (one per stage; phases; "MANDATORY: Read X at Phase N")    │
   │   Phase k:  read WORKER SKILL.md just-in-time → do work → write files to disk │
   │             → persist "Notes to Carry Forward" → discard worker from context   │
   └───────┬──────────────────────────┬───────────────────────────┬────────────────┘
      WORKERS 01-*, 02-*…        COMMON skills                 ROOT skills/
      (references/ on demand,    (naming, table-props,         databricks-expert-agent (principles)
       scripts/ as black boxes,   UC constraints, imports,     databricks-asset-bundles (deploy spine)
       assets/templates/ copied)  autonomous-ops …)            genie-code-environment (client manual)
                                                               vibecoding-state (state/gates/retro)
   Cross-conversation memory lives ON DISK, never in chat:
   <slug>_dab/gold_layer_design/{yaml,DESIGN_DECISIONS.md,COLUMN_LINEAGE.csv}
   <slug>_dab/plans/manifests/*.yaml  (plan-as-contract)   <slug>_dab/plans/deploy-checkpoint.md
   <dp_bundle_root|app_root|agent_app_root>/.vibecoding-state.md  (gates, captured IDs, per-step log)
```

### 2.2 Anatomy of a `SKILL.md`

- **Layout** (`data_product_accelerator/AGENTS.md:130-138`, `DPA/admin/create-agent-skill/SKILL.md:112-135`):
  - `SKILL.md` holds the overview, critical rules and links. The target is "<500 lines / ~1-2K tokens".
  - `references/` holds detailed patterns, loaded on demand.
  - `scripts/` holds validators and generators, executed "as black boxes".
  - `assets/templates/` holds YAML, SQL and notebook starters to copy.
- **Required frontmatter** is `name` (≤64 characters, kebab-case, "must match directory name") and `description` (≤1024 characters, third person, what + when + trigger phrases) (`create-agent-skill/SKILL.md:70-97`).
- **Extended frontmatter the repo actually uses:**

| Field | Purpose | Example |
|---|---|---|
| `clients: [ide_cli, genie_code]` | Which coding client the skill supports | most skills |
| `bundle_resource`, `deploy_verb`, `deploy_note`, `coverage` | How the output is deployed (bundle vs apps vs none) and client caveats | `DPA/bronze/00-bronze-layer-setup/SKILL.md:5-8` |
| `metadata.role` (orchestrator/worker/shared/navigator/runtime-contract), `pipeline_stage`, `next_stages`, `workers`, `dependencies`, `common_dependencies`, `called_by`, `standalone` | The routing and dependency graph | `DPA/gold/00-gold-layer-design/SKILL.md:9-50` |
| `metadata.reads` / `emits` / `consumes` / `consumes_fallback` | Plan-as-contract I/O | `DPA/skill-navigator/SKILL.md:87` |
| `metadata.last_verified`, `volatility`, `upstream_sources{repo,paths,relationship,last_synced,sync_commit}` | Freshness auditing against `databricks/databricks-agent-skills` | `skills/databricks-asset-bundles/SKILL.md:10-24` |
| `fields_read:` | Machine-parseable list of state-file fields a skill consumes (drift audit) | `GA/sdlc/03-scorers-and-judges/SKILL.md:37-45`; contract at `skills/vibecoding-state/SKILL.md:555-581` |
| `inputs`, `compatibility`, `allowed-tools`, `license` | Optional agentskills.io fields | `apps_lakebase/skills/05-appkit-lakebase-wiring/SKILL.md:13-14` |

- **Numbering:** `00-` is an orchestrator; `01-`, `02-` are workers; Gold splits into `design-workers/` (stage 1) and `pipeline-workers/` (stage 4) (`DPA/skill-navigator/SKILL.md:146-149`).
- **Required closing sections.** Orchestrators with three or more phases must have `## Working Memory Management`. Workers must end with `## … Notes to Carry Forward` and `## Next Step` (`create-agent-skill/SKILL.md:171-175`). Every orchestrator ends with a **mandatory "Skill Usage Summary"** of what it actually read, including skipped and unplanned files (`DPA/skill-navigator/SKILL.md:407-430`).

### 2.3 Routing layers and navigators

1. **`AGENTS.md`** (root) is auto-loaded by Cursor, Claude Code, Codex and others.
   - It is a keyword table that routes to a component.
   - Rule 1: "Route first, act second". Rule 3: "Generated artifacts go at the repo root", never inside the read-only framework directories (`AGENTS.md:181-187`).
   - It fixes the output locations: `<use_case_slug>_dab/` for the data product and `<app_name>/` for the app (`AGENTS.md:69-78`).
2. **`data_product_accelerator/AGENTS.md`** maps keywords to the stage orchestrator. It also routes workers (autonomous ops, naming, DABs, imports, table properties, schema, constraints, freshness audit) and lists "at minimum, always read" `databricks-expert-agent` + `naming-tagging-standards` (`:48-74`, `:110-112`).
3. **`DPA/skill-navigator/SKILL.md`** is the full router.
   - The algorithm: an orchestrator match routes to the orchestrator, which reads its workers. A worker match with no active orchestrator routes to the worker, since workers are `standalone: true` (`:159-169`).
   - Tier budgets (`:173-186`) and green, yellow and red context zones (`:305-319`).
4. **Domain navigators:** `GA/00-course-orchestrator` (Foundation F0-F5 → Track A A1-A8 → SDLC S1-S8b) and `apps_lakebase/skills/00-appkit-navigator`.

### 2.4 "One prompt per stage, one new conversation per stage", and why

- **The stated rule:** "New conversation per stage. Start a fresh agent conversation for each stage to keep context clean" (`data_product_accelerator/QUICKSTART.md:448`, `README.md:223-224`).
- **The mechanism behind it, context hygiene:**
  - A budget of 40-60K working tokens against a 200K window (`DPA/skill-navigator/SKILL.md:173-177`).
  - Just-in-time worker loading: "do NOT batch-read all design-worker skills upfront … pushes the common-skill rules and the active phase's rules out of the attention window, producing format divergence" (`DPA/gold/00-gold-layer-design/SKILL.md:163-175`).
  - After each phase, keep only the current worker, the inventory dict and the previous phase's summary. "Discard intermediate outputs … they are on disk" (`:146-161`).
  - Semantic stage: "Context is a finite resource with diminishing marginal returns … Loading all 4 workers (~2000 lines) would consume your attention budget" (`DPA/semantic-layer/00-semantic-layer-setup/SKILL.md:194-198`).
- **The parallelism bonus:** a separate conversation per stage lets independent stages run concurrently. Stages 1 and 2 can run in parallel, and 6, 7 and 8 after Planning (`data_product_accelerator/docs/framework-design/09-parallel-execution-guide.md:112-169, 206-208`).

### 2.5 How state crosses conversations

**(a) Files on disk are the contract between stages.** The Gold YAML is the "single source of truth". `DESIGN_DECISIONS.md` is written before any ERD or YAML, and "include the full text … in every subagent prompt (not by reference)" (`DPA/gold/00-gold-layer-design/SKILL.md:299-323`). Planning emits four **YAML manifests** that downstream orchestrators read in a "Phase 0: Read Plan" (`DPA/skill-navigator/SKILL.md:67-89`). DAB `plans/deploy-checkpoint.md` captures resolved job, warehouse and asset names from `bundle validate --output json` (`skills/databricks-asset-bundles/SKILL.md:666-772`).

**(b) The `skills/vibecoding-state` runtime contract** (`skills/vibecoding-state/SKILL.md`).

*Setup operations*
- `bootstrap` creates the state file (`:64-102`). It:
  - detects the client and writes the `## Environment Capabilities` block with `client_context`, `cli_channel`, `artifact_root`, `dp_bundle_root`, `app_root`, `skill_ref_root` and others (`:82`);
  - normalises the workspace URL and refuses placeholders;
  - matches the auth profile to the host;
  - enforces a CLI minimum of 0.295.0 (skipped on Genie Code);
  - checks the Apps quota;
  - detects DAB dev-mode schema prefixing;
  - runs `resolve_spec`.
- `resolve_spec` has an LLM turn the PRD into YAML. It then runs **deterministic guards**: parse check, schema rules, a placeholder guard, and a variant-id echo. It retries once, with the errors appended to the prompt, then halts (`:121-151`).

*Per-prompt operations*
- **`enter`** runs at the top of every prompt (`:201-259`). It:
  - locates the live state file;
  - hard-fails on a schema version other than 2.0;
  - reads the file end to end ("never ask the operator for a value that already exists in state");
  - applies `canonical_names` aliasing;
  - enforces the prior gate, pathway applicability, `deferred_actions`, known quality issues and the preflight registry;
  - lets a failed gate through only with an **unexpired `state_override`**.
- **`exit`** runs at the bottom of every prompt (`:286-316`). It:
  - logs a `## Prompt <id>` section, **idempotent by `prompt_id`** (replace in place, never duplicate);
  - updates the captured IDs;
  - requires the gate "Local testing passed" for build prompts;
  - **re-reads the file to verify the write**. "The chat summary is NOT the state store" (`:309`).

*Recovery and handoff*
- **Recovery reconcile** (`:245`): in a resumed thread, the state file wins over the chat summary. A step logged PASSED is DONE even if a summary says otherwise. Use `os.listdir`, not `listFiles`, before recreating files.
- **Handoff invariant** (`:312`): every summary or compaction carries `state_file_path`, `last_completed_prompt`, `last_gate`, `environment_capabilities` and `state file updated: yes/no`, and it must be generated **from** the state file.

*Audits and resolution*
- Size discipline: a `<!-- HISTORY -->` marker, with a warning above 800 header lines (`:631-648`).
- Retrospectives and audits: `state_contract_audit` (producer versus consumer `fields_read` drift), `audit_debts`, and `endpoint_guardrail_audit` / `llm_role_endpoint_probe` (probe LLM endpoints and bind roles by capability) (`:318-464`).
- **`skill_helper_resolution`** (`:466-521`). When a skill prescribes a helper that the installed SDK or CLI does not have, it probes the candidates in order (import path, signature, bundle schema, API field, CLI jq path) and records the winner in state.

### 2.6 Why this design works well with LLMs

1. **Smaller, fresher context.** JIT loading keeps the governing rules near the end of the context, where recent tokens get the most attention. Phase notes replace full skill bodies, which prevents the "lost in the middle" format drift the authors observed (`DPA/gold/00-gold-layer-design/SKILL.md:175`).
2. **Externalised memory.** Contracts on disk (YAML, manifests, the state file) survive context resets. The model re-derives facts from files instead of trusting its own summary (`skills/vibecoding-state/SKILL.md:245,312`).
3. **Grounding over generation.** "Extract, Don't Generate": every name comes from YAML, `DESCRIBE` or `SELECT DISTINCT`. This removes the largest class of hallucination (`skills/databricks-expert-agent/SKILL.md:75-165`).
4. **Deterministic guards around stochastic steps.** Examples: `_assert_sql_arrays`, `validate_upstream_contracts.py`, `bundle validate`, and design Validations 1-5.
5. **Explicit STOP points and human checkpoints.** "🛑 STOP — Artifact Creation Complete … Do NOT proceed … unless the user explicitly requests deployment" (`DPA/gold/01-gold-layer-setup/SKILL.md:391-395`). There are also phase completion gates that ask the user before continuing (`DPA/semantic-layer/00-semantic-layer-setup/SKILL.md` §Phase 1-3 Completion Gate).
6. **Named failure modes and pre-mortems.** "Rationalization Red Flags" (`skills/databricks-expert-agent/SKILL.md:36-47`), the anti-pattern library, and `❌/✅` pairs (613 `❌` in 100 files).
7. **Proof of work.** Examples: the Skill Usage Summary of what was actually read; "list the key pattern from each skill or you have not read it" (`DPA/semantic-layer/00-semantic-layer-setup/SKILL.md:132-145`); and the Phase 0 "Extract-Don't-Generate: confirmed" block.
8. **Portability.** AGENTS.md plus SKILL.md is an open format that works across Cursor, Claude Code, Copilot, Windsurf, Codex and Genie Code (`AGENTS.md:191-211`).

---

## 3. The 9-stage pipeline: inputs, outputs, encoded rules, gates

Source for the per-stage prompts and what each stage produces: `data_product_accelerator/QUICKSTART.md`. Dependency graph: `docs/framework-design/09-parallel-execution-guide.md`. There are three deployment checkpoints: after stage 4 (Bronze + Silver + Gold together), after stage 6 and after stage 7 (`QUICKSTART.md:452`).

### Stage 1: Gold Layer Design (`DPA/gold/00-gold-layer-design` + 8 design workers)

**Inputs:** the schema CSV; an optional `context/industry_reference.yaml`; an optional PRD. The CSV is the only source of names: "The schema CSV is the **single source of truth** … never generate table/column names from memory" (`:235`).

**Outputs** (`:112-134`, `:505-526`), all under `gold_layer_design/`:
- `erd_master.md`, plus `erd/erd_{domain}.md` at 9+ tables and `erd_summary.md` at 20+ tables (`:136-142`).
- `yaml/{domain}/{dim_,fact_}*.yaml`.
- `DESIGN_DECISIONS.md`, `COLUMN_LINEAGE.csv` and `.md`, `SOURCE_TABLE_MAPPING.csv`.
- `docs/BUSINESS_ONBOARDING_GUIDE.md` (10 sections, including 3-4 real-world stories, `:424-444`).
- `DESIGN_SUMMARY.md`, `DESIGN_GAP_ANALYSIS.md`, `README.md`.
- Advisory: `INDUSTRY_CROSSWALK.csv` and `INDUSTRY_ALIGNMENT.md`.

**Engineering rules encoded**
- **Non-negotiable YAML defaults** (`:83-106`):
  - `clustering: auto` (becomes `CLUSTER BY AUTO`);
  - `delta.enableChangeDataFeed`, `delta.enableRowTracking`, `autoOptimize.optimizeWrite`, `autoCompact`;
  - `layer: gold`;
  - every PK column `nullable: false`.
- **Phase 0 intake** (`:196-235`): `parse_schema_csv` → `classify_tables` → `infer_relationships`.
  - The classifier rules: bridge = 3 or fewer columns and 2+ FK-like columns; fact = 2+ FKs plus numeric measures (or 2+ timestamps plus 2+ FKs); dimension = everything else.
  - FKs come from comments ("Foreign Key to 'X'") or `other_table_id` naming.
  - The classifier is **"a HEURISTIC, not ground truth"**. Print it, and document every override and why in `DESIGN_DECISIONS.md`: "Never silently correct a classification" (`:212`).
- **Dimensional modelling** (Phase 2, `:262-297`): 2-5 dimensions with SCD1/SCD2 decisions; 1-3 facts with explicit grain; measures with additivity; a bus matrix; an Unknown-member strategy.
- **Grain** (`DPA/gold/design-workers/01-grain-definition/SKILL.md:58-157`):
  - PK-driven decision tree: a single `_id` key means transaction grain; `date_key` plus dimension keys means aggregated; entity plus date means snapshot.
  - Required YAML: `grain`, `grain_type`, composite `primary_key`, `measures[].aggregation`.
- **Dimensions** (`design-workers/02-dimension-patterns/SKILL.md:55-206`):
  - **Never snowflake** (flatten hierarchies).
  - Point NULL FKs to an **Unknown row (-1)**.
  - Flags become **text** ("Active"/"Inactive"), except in generated `dim_date`/`dim_time`.
  - No generic "entity" dimensions.
  - Role-playing dimensions are **views** over one physical table.
  - Degenerate keys live on the fact.
  - Use a junk dimension for 3+ low-cardinality flags (<~50 combinations).
- **Facts** (`design-workers/03-fact-table-patterns/SKILL.md:44-200`):
  - Store additive components, not averages; compute ratios in the semantic layer.
  - Semi-additive measures use LAST_VALUE across time.
  - Factless facts for coverage and events; accumulating snapshots are **updated** by MERGE.
  - **NULL vs 0 matters**: a missing measure is stored as NULL.
- **Conformed dimensions** (`design-workers/04-conformed-dimensions/SKILL.md:63-200`): build the bus matrix before the ERDs; conformed dimensions are identical everywhere; **never join fact to fact**, drill across through conformed dimensions.
- **Documentation** (`design-workers/06-table-documentation/SKILL.md:38-121`):
  - Dual-purpose comments: `Definition. Business: … Technical: …`.
  - **Surrogate keys are PKs**; business keys are carried for readability.
  - Required TBLPROPERTIES: CDF, row tracking, deletion vectors, auto-optimize, layer, domain, entity_type, PII, classification, owners, scd_type, grain.
- **`DESIGN_DECISIONS.md` contract before Phase 3** (`:299-323`), with six sections:
  1. table inventory;
  2. **FK format** `{columns, references: table(col), nullable}`;
  3. description format with no literal brackets;
  4. the **15-value transformation enum**;
  5. top-level YAML keys;
  6. the boolean-to-text list.
- **Transformation enum** (`:377-395`): `DIRECT_COPY | RENAME | CAST | AGGREGATE_SUM | AGGREGATE_SUM_CONDITIONAL | AGGREGATE_COUNT | AGGREGATE_AVG | DERIVED_CALCULATION | DERIVED_CONDITIONAL | HASH_MD5 | HASH_SHA256 | COALESCE | DATE_TRUNC | GENERATED | LOOKUP`. It includes an edge-case map: "do NOT invent new types" such as `BOOLEAN_TO_LABEL` or `SCD2_CLOSE`.
- **Industry alignment** (`design-workers/08-industry-alignment/SKILL.md:40-53`) is a lens only. It never invents tables; uncovered entities are marked `Waived` or `Planned`.

**Validation gates**
- **Phase 8** (`design-workers/07-design-validation/SKILL.md:43-650`):
  - V1 YAML↔ERD; V2 YAML↔Lineage; V3 PK/FK references; V4 mandatory fields; V5 cross-worker semantic rules (no BOOLEAN in business dimensions, `unknown_member` required for nullable FKs, enum compliance, FK shape, no `[]<>` in descriptions, mandatory keys, `additivity` on measures).
  - V1-V5 must pass. V6 (industry) is advisory.
- **Upstream cross-reference** (`00-gold-layer-design/SKILL.md:481`): check the YAML lineage against the real Silver schemas and **report the mismatch count**, because V1-V4 are *self-referential* (see pattern P2 in §10).
- **Phase 9** is stakeholder sign-off. Then the Skill Usage Summary.

**Common mistakes** (`:540-548`): skipping the mandatory docs, the wrong ERD strategy, incomplete lineage ("33% of implementation bugs", unverified), no grain documentation, generic business docs.

### Stage 2: Bronze (`DPA/bronze/00-bronze-layer-setup` + `01-faker-data-generation`)

**Inputs** (`:174-221`): Approach A is schema CSV + Faker (recommended for demos). Approach B is existing tables. Approach C is a copy or DEEP CLONE from `samples.wanderbricks` (recommended for workshops). The QUICKSTART prompts for all three are at `QUICKSTART.md:91-139`.

**Outputs:** `src/{project}_bronze/{setup_tables.py, generate_dimensions.py, generate_facts.py, copy_from_source.py}` and the jobs `bronze_setup_job.yml` / `bronze_data_generator_job.yml` (`:106-125`, `:227-256`).

**Engineering rules**
- **Scope.** "Optimized for testing, demos, and rapid prototyping … **NOT for production ingestion**" (`:51-59`). **No Auto Loader, `cloudFiles` or `read_files` pattern exists anywhere in the accelerator.** CONFIRMED by grep: Auto Loader appears only in passing, in `silver-table-patterns.md:430,454` and an error matrix.
- **Non-negotiables** (`:61-102`): serverless `environments` with `environment_version: "4"` and `environment_key` on every task; `CLUSTER BY AUTO` (never `CLUSTER BY (cols)` or `PARTITIONED BY`); CDF; auto-optimize and auto-compact; `notebook_task` plus `base_parameters`.
- **DDL** (`:237-241`, `:276-296`): `CREATE TABLE IF NOT EXISTS`; audit columns `ingestion_timestamp` and `source_file`; `data_purpose='testing_demo'`, `is_production='false'`; governance TBLPROPERTIES (`source_system`, `domain`, `entity_type`, `contains_pii`, `data_classification`, owners); "never the reserved `table_type`" (`:7`).
- **Extract the DDL from the CSV**; hard-coding table definitions is the `❌` example (`:186-221`).
- **Naming and order:** `bronze_{entity}_dim` / `bronze_{entity}`. Load dimensions, then `bronze_date_dim` via a SQL SEQUENCE, then facts, so FKs stay consistent (`:298-308`).
- **Faker** (`01-faker-data-generation/SKILL.md:69-321`):
  - Seed numpy and Faker (the script also seeds `random`).
  - Use non-uniform distributions: lognormal for money, exponential for durations, weighted categories.
  - Keep the last 180 days, **row coherence** (tier drives amount and priority), and **raw events only** (no pre-aggregates).
  - Weighted fact sampling by dimension attributes.
  - Default **5% corruption**, mapped to DQ categories: missing, format, range, business-logic, temporal, referential.
  - "Generate valid data first, then corrupt".

**Gates:** Step 1 requirements template, which is "MANDATORY — DO NOT SKIP even if the user's request seems complete", with inference allowed for B and C (`:150-172`). Then a STOP after artifact creation (`:260-264`) and validation queries in `references/validation-queries.md`. The "NEVER without first reading" list is at `:325-330`.

### Stage 3: Silver (`DPA/silver/00-silver-layer-setup` + `01-dlt-expectations-patterns` + `02-dqx-patterns`)

**Inputs:** live Bronze tables, verified at run time. "Reading a clone script or inferring from the schema CSV is NOT runtime verification" (`:260-271`).

**Outputs** (`:51-57`, `:208-222`):
- a `dq_rules` Delta table (PK `(table_name, rule_name)`) and `setup_dq_rules_table.py`;
- `dq_rules_loader.py`, which must be **pure Python with no notebook header**;
- `silver_*.py` SDP/DLT notebooks, quarantine tables and `data_quality_monitoring.py`;
- `resources/silver_dlt_pipeline.yml` and `silver_dq_setup_job.yml`.

**Engineering rules**
- **Non-negotiables** (`:116-147`): `serverless: true`, `photon: true`, `edition: ADVANCED` ("expectations require ADVANCED"), `cluster_by_auto=True` on every table including monitoring views, CDF plus row tracking.
- **"Schema cloning" philosophy** (`:158-176`): Silver keeps Bronze's names, types and grain, and adds DQ rules, simple derived flags, SHA256 business keys and `processed_timestamp`. No aggregations and **no cross-table joins**; those belong in Gold.
- **API:** standardise on `import dlt` for framework consistency. The skill states that `from pyspark import pipelines as dp` is the recommended forward path and supports expectations (`:47`, `:178-204`).
- **DQ as data** (`01-dlt-expectations-patterns/SKILL.md:56-400`):
  - Rules live in a UC Delta table; a module-level cache loads them with `toPandas()` (to avoid `.collect()` warnings).
  - Critical rules use `@dlt.expect_all_or_drop`; warnings use `@dlt.expect_all`.
  - **Never `expect_or_fail`** (Mistake 4, `:464`).
  - Runtime rule changes are an `UPDATE dq_rules …`, picked up on the next update.
  - Quarantine tables carry `quarantine_reason` and `quarantine_timestamp`.
- **Grounding:** `DESCRIBE TABLE` to pin column names, then `SELECT DISTINCT` for enum values. "CSV column comments describe *intent*" (`:241-257`).
- **Direct publishing mode:** set `catalog` and `schema`; no `target:`, no `LIVE.` prefix (`:71-122`).
- **Streaming dedup** on the natural key is "🔴 MANDATORY: … ALWAYS deduplicate" (`00-silver-layer-setup/references/silver-table-patterns.md:396-450`). Preserve `_ingested_at` and `_metadata`, and separate event time from processing time (`:452-510`).
- **DQX** (optional; for richer diagnostics and pre-merge Gold checks): use exact function and parameter names (`is_not_less_than(limit)`, `is_in_range(min_limit,max_limit)`, `is_in_list(allowed)`, and **no** `is_greater_than`); Spark Connect-safe code; set `save_checks(mode=…)` explicitly (`02-dqx-patterns/SKILL.md:145-207`).

**Gates**
- Phase 1 pinned column inventory: "a reference to a column absent from the live `DESCRIBE` is a hard error" (`:271`).
- A **contract test before any deploy**: dry-import the loader and run each `constraint_sql` read-only with `LIMIT 1` (`:364`).
- Deploy order: the DQ job, then the pipeline (`:370-388`).
- **Verify expectations with the `event_log()` TVF, not `list-pipeline-events`** (`:392-405`; `01-dlt…/SKILL.md:385-405`).
- The QUICKSTART prompt adds: "Validate … DQ rules show up in centralized delta table … Expectations being checked" (`QUICKSTART.md:159-161`).

### Stage 4: Gold implementation (`DPA/gold/01-gold-layer-setup` + 5 pipeline workers)

**Inputs:** Gold YAML, `COLUMN_LINEAGE.csv`, live Silver. **Outputs:** `setup_tables.py`, `add_fk_constraints.py`, `merge_gold_tables.py`, `gold_setup_job.yml` (two tasks: tables, then FKs) and `gold_merge_job.yml` (`:121-147`).

**Engineering rules**
- **Non-negotiables** (`:99-112`): serverless, Environments v4, `CLUSTER BY AUTO`, CDF, row tracking and `notebook_task`. Also **"FK graceful failure: warn + continue"**.
- **Everything comes from YAML except aggregation and derivation formulas** (`:115-119`).
- **DDL** (`:237-243`):
  - PKs `NOT NULL`.
  - **FKs via `ALTER TABLE` after all PKs exist, never inline.**
  - `CREATE OR REPLACE TABLE` "for idempotent setup". This is a risk; see §11.
  - PyYAML in the job environment, and `find_yaml_base()`.
  - The YAML is synced into the bundle (`:369-381`).
- **UC constraints** (`DPA/common/unity-catalog-constraints/SKILL.md:44-131`):
  - The number-one failure is an FK that references a business key instead of the surrogate PK.
  - FKs must reference PK columns; no inline FKs.
  - **No `DEFAULT` column clauses**; set defaults at INSERT time.
- **Phase 1b ordering** (`:254-270`): create tables → PKs → role-playing views → **Unknown (-1) rows** → FKs → merges.
- **MERGE rules** (`:292-353`):
  - Load the metadata inventory from YAML first.
  - **Deduplicate the Silver source before every MERGE, and the dedup key must equal the merge key.**
  - Surrogate key: `md5(concat_ws("||", …))`.
  - SCD2 columns `effective_from`, `effective_to` and `is_current`; the SCD2 merge condition adds `is_current = true`.
  - Merge dimensions before facts.
  - `.select()` the YAML column list and validate it against the DDL (`validate_merge_schema`).
  - Validate grain for facts.
  - Use `spark_sum`, never variables named `sum`, `count`, `min` or `max`.
  - Cast `DATE_TRUNC` results to DATE.
- **Pattern selection** by YAML `dimension_pattern` / `grain_type`: junk, accumulating snapshot (updates), factless (insert-only), periodic snapshot (period replace) (`:323-345`).
- **Predictive optimisation at schema level**: `ALTER SCHEMA … ENABLE PREDICTIVE OPTIMIZATION` (`DPA/common/schema-management-patterns/SKILL.md:134-186`). The Gold templates contradict this; see §11.

**Gates**
- **Phase 0 upstream contracts**: `validate_upstream_contracts.py` must print PASSED for every table before any code. The minimum fallback is `DESCRIBE` plus one PASS line per table (`:186-211`). The merge template re-checks fail-fast.
- STOP before deploy (`:391-395`).
- Phase 4 checks tables, PKs and FKs; Phase 5 checks ERD cross-reference, schema, **grain duplicates, orphan FKs, exactly one `is_current` per business key**, audit timestamps and conformance (`:399-447`).
- **The first QUICKSTART checkpoint** (`QUICKSTART.md:202-223`): validate, deploy, then run Bronze → DQ job → Silver → gold_setup → gold_merge.
  - Diagnose with the **task-level `run_id`**.
  - Known signatures: `TABLE_OR_VIEW_NOT_FOUND` (upstream not ready), `DELTA_MULTIPLE_SOURCE_ROW_MATCHING` (dedup needed), `PARSE_SYNTAX_ERROR`.
  - **Maximum 3 iterations** before escalating.

### Stage 5: Project planning (`DPA/planning/00-project-planning`)

**Inputs:** Gold (live or YAML), `docs/design_prd.md`, and the onboarding guide. **Outputs:**
- the `plans/phase1-addendum-1.{1..7}` files: 1.1 ML, 1.2 TVFs, 1.3 MVs, 1.4 monitors, 1.5 dashboards, 1.6 Genie, 1.7 alerts;
- `plans/use-case-catalog.md`;
- **4 manifests** (`plans/manifests/{semantic-layer,observability,ml,genai-agents}-manifest.yaml`) (`:621-662`).

**Engineering rules**
- **Mode detection** (`:60-81`): acceleration is the default. Workshop mode (artifact caps of 3-5 TVFs, 1-2 MVs and 1 Genie space) **only on the exact phrase** `planning_mode: workshop`. "Do NOT infer workshop mode from words like 'small', 'simple', 'demo'"; when in doubt, ask. State the mode in the first output line and stamp it into every manifest.
- **Idempotency guard** (`:102-131`): if `plans/` exists, offer regenerate / incremental / **skip (default)**, and confirm any destructive action.
- **Phase 0 source discovery** (`:187-229`): fidelity order deployed Gold > Gold YAML > Silver > Bronze > CSV. Acceleration mode forces Gold.
- **Traceability:** every artifact maps to a Gold table and a business question (`:661`).
- **Rationalisation** (`:766-777`): "do not create artifacts to fill quotas".
  - Genie: at most 25 assets per space, 10-25 optimal, merge spaces below 10.
  - TVFs **only** when a metric view cannot answer; one MV per analytical grain.
  - Domains need at least 3 questions; merge when overlap exceeds 70%.
- **SQL standards** (`:779-785`): Gold only, never `system.*`; date parameters as STRING, CAST at query time.
- **Agent layer:** agents query **through Genie spaces**, so deploy Genie before agents (`:727-764`).
- **Build order:** TVFs → MVs → Genie → Dashboards → Monitors → Alerts → Agents (`QUICKSTART.md:244`).

**Gates:** summary counts must match; `validate_use_case_coverage.py`; the checklist at `:837-891`.

### Stage 6: Semantic layer (`DPA/semantic-layer/00-semantic-layer-setup` + 01 MV, 02 TVF, 03 Genie patterns, 04 Genie API, 06 Discover ontology)

**Inputs:** `plans/manifests/semantic-layer-manifest.yaml`, which is **required**: "STOP if manifest is missing" (`:151`, `:202-210`). Also a `gold_inventory` dict built from YAML and `information_schema.columns`; it is "the ONLY source of table/column names" (§Planning-Source Inventory Extraction).

**Outputs:** metric view YAML and `create_metric_views.py`; TVF SQL; Genie space JSON (`serialized_space`); `semantic_layer_job.yml`; optional API deployment.

**Engineering rules: Metric Views** (`01-metric-views-patterns/SKILL.md:125-594`)
- Syntax: `CREATE … VIEW … WITH METRICS LANGUAGE YAML … AS $$ … $$` with `version: "1.1"`.
- **No `name`, `time_dimension`, top-level `window_measures` or `join_type` keys**; use `source`, not `table`, in joins.
- Prefix columns with `source.` or `<join_name>.`.
- **Revenue comes from the fact table, not a dimension** ("under-reports by 4x").
- **No transitive joins**: use nested joins (DBR 17.1+) or denormalised columns.
- Joins are many-to-one with LEFT OUTER semantics; check **cardinality before `rely.at_most_one_match`**.
- SCD2 joins include `is_current = true`.
- `format.type` ∈ {byte, currency, date, date_time, number, percentage}.
- **Percent-of-total via a fixed LOD plus `ANY_VALUE`, never `MEASURE()/MEASURE()`**, which always gives 1.0.
- Prefer `ALTER VIEW` to keep grants.
- Structured comments: PURPOSE / BEST FOR / NOT FOR / DIMENSIONS / MEASURES / SOURCE / JOINS / NOTE.

**Engineering rules: TVFs** (`02-databricks-table-valued-functions/SKILL.md:129-338`)
- **STRING date parameters, CAST inside** ("Genie doesn't support DATE"; the skill's claim).
- Required parameters before DEFAULT ones.
- **No `LIMIT <param>`**: use `ROW_NUMBER` and `WHERE rank <= param`.
- **Never re-join a table after aggregating it in a CTE** (cartesian inflation).
- `NULLIF` on every division.
- v3.0 bullet comments: PURPOSE / BEST FOR / NOT FOR / RETURNS / PARAMS / SYNTAX / NOTE.

**Engineering rules: Genie** (`03-genie-space-patterns/SKILL.md:87-404`)
- General instructions **≤20 lines**.
- **Benchmarks carry working SQL with pinned dates** (no `CURRENT_DATE` in regression suites).
- `MEASURE()` takes the column **name**, not the display name; metric-view dimensions are **bare names**.
- Full three-part names everywhere.
- **Asset priority: Metric Views → TVFs → tables.**
- No contradictory routing; define ambiguous terms ("underperforming").
- TVF calls: no `TABLE()` wrapper, all parameters, no extra GROUP BY.
- **Serverless warehouse only.**
- Table and column COMMENTs are "Genie fuel"; inspect tables before creating the space.
- **Ask the user for benchmarks before generating synthetic ones.**
- Validate through the **Conversation API**, with a new conversation per unrelated question.
- A 13-section extended-instruction structure.
- `column_configs` flags (`enable_format_assistance`, `enable_entity_matching`).
- **Synonyms go in `column_configs` or MV YAML, not UC comments.**
- **Append, never replace**, when changing instructions.
- `sql_snippets` for measures, filters and expressions.
- Benchmark SQL must be Databricks dialect.

**Engineering rules: Genie API** (`04-genie-space-export-import-api/SKILL.md:85-848`)
- `serialized_space` version 2.
- Every text field is `List[str]`; data sources have **no `id`**; everything else takes `uuid4().hex` ids.
- **Every array sorted** (tables and MVs by `identifier`, others by `id`).
- At most 50 `sql_functions` and 50 benchmarks.
- `semantic_warehouse_id` is **baked at deploy time** (a placeholder gives a space that fails every query).
- Update-or-create: PATCH **without `title`**, otherwise the API appends " (updated)".
- **Never `PATCH /api/2.0/data-rooms/{id}`**; it silently wipes `serialized_space`.
- Export with `GET …?include_serialized_space=true`.

**Gates**
- The **common-skill read-confirmation gate** (`:132-145`).
- **Phase 0.5 local pre-flight** (`:411-467`): enumerate variables, DDL smoke test via `EXPLAIN`, `_assert_sql_arrays`, live-catalog intersection. "Every Phase 0.5 check failure must halt … Do not 'run bundle deploy anyway to see what the cluster says'".
- Per-phase completion gates that ask the user and run per-task verification on a scratch dev target ("every TVF must return at least one row on a smoke input").
- Anti-hallucination validation: parse each MV, TVF and benchmark SQL and check every reference against `gold_inventory` (§Phase 1-3 steps).
- The post-creation checklist (`:679-722`) and the second QUICKSTART checkpoint (`QUICKSTART.md:306-326`).

### Stage 7: Observability (`DPA/monitoring/00-observability-setup` + 6 workers)

**Inputs:** `observability-manifest.yaml` (required, `:109`) and populated Gold tables. **Outputs:**
- Lakehouse monitors with custom AGGREGATE, DERIVED and DRIFT metrics;
- schema-level anomaly detection (freshness and completeness);
- AI/BI dashboards `.lvdash.json` (plus Vega-Lite custom viz and React custom pages, added at HEAD);
- SQL Alerts v2.

**Engineering rules**
- **Monitors** (`01-lakehouse-monitoring-comprehensive/SKILL.md:100-200`):
  - use the `w.data_quality.create_monitor(monitor=Monitor(object_type, object_id=table_id, …))` API, not legacy `w.quality_monitors`;
  - use SDK objects, not dicts;
  - `output_data_type` is StructField JSON; a bare `"double"` silently fails;
  - DERIVED metrics use direct names, **no `{{}}`**;
  - DRIFT metrics **must** use `{{current_df}}`/`{{base_df}}`;
  - granularity enums; `output_schema_id` (UUID);
  - initialisation is asynchronous (15-20 minutes);
  - deleting a monitor also drops its output tables.
- **Table-level KPIs** use `input_columns=[":table"]`; anomaly detection uses the schema UUID and a `Monitor` wrapper (`00-observability-setup/SKILL.md:105-117`).
- **Dashboards** (`02-databricks-aibi-dashboards/SKILL.md:345-381`): **a 12-column grid** (`layoutVersion: "GRID_V1"`) with each row summing to 12. "6-column is a subdivision choice, not the grid". Use `dataset_catalog`/`dataset_schema`, never a hard-coded catalog.
- **Alerts** (`03-sql-alerting-patterns/SKILL.md:53-373`):
  - **no parameters in alert queries**;
  - `EXPLAIN` every query before deploy;
  - severities CRITICAL, WARNING and INFO;
  - atomic plus composite jobs;
  - seed configurations with **a DataFrame, not SQL INSERT** (escaping breaks LIKE);
  - validate severity in code (no CHECK in DDL);
  - **accept partial success at ≥90%**;
  - the v2 schema uses `evaluation` (not `condition`) and `quartz_cron_schedule` (`skills/databricks-asset-bundles/SKILL.md:651-653`).

**Gates:** the third QUICKSTART checkpoint (`QUICKSTART.md:360-380`) handles `ResourceAlreadyExists` by deleting and recreating, missing tables, and monitor `update_mask`.

### Stage 8: ML (`DPA/ml/00-ml-pipeline-setup`)

**Inputs:** `ml-manifest.yaml`, optional with a fallback to self-discovery (`:55-88`), and Gold tables. **Outputs:** UC feature tables, per-model training notebooks, batch inference with `fe.score_batch`, UC-registered models, and three jobs (feature, training, inference) (`:159-236`).

**Engineering rules** (19 rules, `:237-261`)
- Pin the **same** mlflow, sklearn and xgboost versions in training and inference.
- Experiments at `/Shared/{project}_ml_{model}`; log datasets **inside** `start_run`.
- Log models with `fe.log_model(... infer_input_example=True)` and the `databricks-uc` registry.
- `FeatureLookup` + `create_training_set` (lookup keys == feature-table PKs; `exclude_columns=[label]`).
- **Clean NaN/Inf at feature-table creation**; cast numerics to DOUBLE (signatures reject Decimal).
- Label binarisation, a single-class check, and label type casting.
- `fe.score_batch` with lookup keys only (training-serving consistency).
- Inline helpers or the bundle-root `sys.path` pattern; copy the templates rather than writing your own.
- **Don't define experiments in the bundle** (`:360`).

**Gates:** the checklists at `:485-545`. The exit-signal convention is a risk; see §11.

### Stage 9: GenAI agents (routes to `genai-agents/00-course-orchestrator`)

**Inputs:** `genai-agents-manifest.yaml`, the PRD, `docs/agent_spec.yaml` and `docs/agent_tool_plan.yaml`, and the state file. **Outputs:**
- a Track A Python agent on Databricks Apps, using the OpenAI Agents SDK behind `@invoke`/`@stream`;
- tools through managed MCP (Genie, UC functions, AI Search) or function tools;
- OBO auth and Lakebase memory;
- the SDLC chain: prompt registry, eval datasets, scorers, eval runs, sign-off, UC model, deployment, monitoring and feedback.

Rules and gates are in §8. The QUICKSTART stage 9 prompt is **stale**: it mentions "Track A/B/C", "Model Serving … A/B testing" and "ResponsesAgent" (`QUICKSTART.md:427-437`), but the B, C and capstone skills were removed on 2026-04-27 (`genai-agents/README.md`, diagram note).

---

## 4. Engineering-rules master list (deduplicated, by layer)

**Cross-cutting and governance**
- Every name comes from YAML, `DESCRIBE`, `SELECT DISTINCT` or `information_schema` ("Extract, Don't Generate") (`skills/databricks-expert-agent/SKILL.md:30,75-154`).
- `snake_case`; prefixes `bronze_`/`silver_`/`dim_`/`fact_`/`bridge_`/`agg_`/`stg_`; suffixes `_quarantine`/`_history` (`DPA/common/naming-tagging-standards/SKILL.md:193-226`).
- Approved abbreviations only (`id ts dt amt qty pct num cnt avg min max pk fk dim fact agg stg`) (`:227-231`).
- Dual-purpose COMMENT on every schema, table, column, function and MV (CM-02/03/04). Tags: `layer`, `domain`, PII through `class.*` governed tags. Workflow tags `team`, `cost_center`, `environment`. Budget policies for serverless (`:33-72`).
- `CLUSTER BY AUTO` everywhere, never manual keys or `PARTITIONED BY` (`DPA/common/databricks-table-properties/SKILL.md:98-128`).
- CDF and row tracking on Silver and Gold; auto-optimise and auto-compact everywhere; deletion vectors on Silver and Gold (`:31-97`).
- Predictive optimisation at schema or catalog level with `ALTER SCHEMA … ENABLE PREDICTIVE OPTIMIZATION` (`DPA/common/schema-management-patterns/SKILL.md:134-164`).
- Per-user prefix on every job, pipeline, schema and Genie title in shared workspaces: `[${bundle.target} ${var.user_prefix}]`, with `presets.name_prefix: ""` to avoid a doubled prefix (`skills/databricks-asset-bundles/SKILL.md:71-75,514-553`).

**Bronze**
- Test and demo scope; use CSV-driven DDL, `CREATE TABLE IF NOT EXISTS`, audit columns and `is_production=false`.
- Load dimensions, then date, then facts.
- Seeded, non-uniform, coherent Faker data with about 5% mapped corruption.

**Silver**
- Serverless ADVANCED Photon pipelines with direct publishing (`catalog`+`schema`).
- The rules table plus a pure-Python loader; drop critical failures and warn on warnings; quarantine tables.
- Mirror Bronze names, grain and types; no joins or aggregates.
- Streaming dedup (see the scale caveat in §11); keep `_ingested_at`.
- Verify through `event_log()`.

**Gold**
- Design first in YAML: grain, `grain_type`, surrogate PKs, business keys, FKs in the table-level shape, the lineage enum, and `unknown_member`.
- No snowflaking; text flags; role-playing views; no fact-to-fact joins; store additive components; NULL ≠ 0.
- PK `NOT NULL`, FKs by ALTER after PKs, no DEFAULT clauses.
- Dedup before MERGE with dedup key = merge key; dimensions then facts; explicit `.select` of the YAML columns; schema and grain validation; `spark_sum`.
- Upstream contract check before coding.

**Semantic**
- Manifest-driven with `gold_inventory` as the only namespace.
- MVs: YAML 1.1, only the supported keys, fact-sourced measures, no transitive joins, cardinality checks, LOD for ratios, `ALTER VIEW`.
- TVFs: STRING dates, parameter order, no `LIMIT` parameter, no re-join after aggregating, `NULLIF`, v3.0 comments.

**Genie**
- Serverless warehouse; MV → TVF → table priority; ≤20-line general instructions; defined terms; synonyms in `column_configs`.
- ≥10 benchmarks with pinned-date Databricks SQL, validated through the Conversation API.
- `serialized_space` v2: `List[str]` everywhere, sorted arrays, uuid hex ids, no ids on data sources, warehouse id baked at deploy.
- Never PATCH `/data-rooms`; append-only instruction edits; persist the JSON in the bundle.

**Observability**
- Manifest-driven; `data_quality` SDK objects; typed custom metrics; asynchronous initialisation.
- 12-column dashboards with `dataset_catalog`/`dataset_schema`.
- Alerts: no parameters, `EXPLAIN` first, v2 schema, DataFrame seeding, severity routing.

**ML**
- Version pins; feature tables with PK lookup keys; `fe.log_model` / `fe.score_batch`; NaN handling at source (see §11); DOUBLE casts; label checks; no experiments in the DAB.

**GenAI**
- ResponsesAgent: never pass `signature=`; examples use `input`, not `messages` (`GA/foundation/01-mlflow-genai-foundation/SKILL.md:38-75`).
- Tracing to UC OTEL with the warehouse id set **before** the experiment exists (`GA/foundation/02-experiment-tracing-and-uc-storage/SKILL.md:371-502`).
- Managed MCP URL patterns and OAuth scopes (`GA/foundation/03-tools-and-data-access/SKILL.md:151-176`); `_meta` for deterministic configuration only (`:199-265`).
- AI Gateway once there are two or more consumers. **No hand-picked or unaudited endpoints; halt instead of falling back** (`GA/foundation/04-ai-gateway/SKILL.md:46-121`).
- The evaluation SDLC is in §8.

**Apps / Lakebase**
- **SQL:** `:paramName` placeholders, never string-built SQL; generate types before UI code (`apps_lakebase/skills/02-appkit-build/SKILL.md:141,152`).
- **Scaffold:** keep the scaffold's `package.json` and lockfile; no `preinstall`/`postinstall` hooks (`03-appkit-deploy/SKILL.md:124,138`).
- **Lakebase resources:** declare only `postgres_projects` (not `postgres_branches` or `postgres_endpoints`) (`apps_lakebase/Instructions.md` Step 3). Never remove `postgres_projects` once deployed (`03-appkit-deploy/SKILL.md:256`).
- **DDL ownership, Deploy-First:** DDL runs server-side under the app's service principal, which becomes the owner (`05-appkit-lakebase-wiring/SKILL.md:192`).
- **Seeding and dev:** use a count-check seed, not `ON CONFLICT DO NOTHING` on identity PKs (`:196`); do not `npm run dev` before the first deploy (`:476`).
- **OBO auth:**
  - Build the user client **inside** the request handler (`GA/tracks/A-custom-agent-apps/04-authentication/SKILL.md:198`).
  - Least-privilege `user_api_scopes`.
  - Forward `x-forwarded-access-token` verbatim **and** keep the app-to-app service-principal bearer.
  - `x-forwarded-user-info` does not exist (`apps_lakebase/skills/06d-appkit-agent-app-proxy/SKILL.md:119,252,671`).
- **Feedback:** experiments pinned to the user/use-case identity (`08-appkit-feedback/SKILL.md:161`).

**DABs**
- YAML only; `bundle deploy --target dev`; prod deploys only in CI.
- Serverless `environments` v4 plus `environment_key`.
- `notebook_task` plus `base_parameters` read through `dbutils.widgets.get` (never argparse or `python_task`).
- Notebook source headers and `# COMMAND ----------` separators.
- Atomic → composite → orchestrator job hierarchy (each notebook in exactly one atomic job, `run_job_task` above).
- Relative path depth rules; schedules PAUSED in dev.
- Volumes use `grants`; app environment variables go in `app.yaml`.
- **Every edit → `bundle deploy` → `bundle run`**, because run does not sync files.
- `--var` at run time does not override deploy-time-baked values.
- **Removing a resource block destroys the resource.**
- Emit a deploy checkpoint after `validate`.
- Verify with an explicit allowlist, not a `SHOW TABLES` count.
- Sources: `skills/databricks-asset-bundles/SKILL.md:45-664`.

---

## 5. The AI-error catalogue (what to catch, how to detect it, where it is documented)

Scale: 155 "NEVER", 199 "CRITICAL", 159 "MANDATORY", 48 "Common Mistake(s)", 74 "anti-pattern" and 613 `❌` across the markdown. The **"Detect by"** column is the check a human reviewer (or a script) runs.

### 5.1 Grounding and hallucination

| AI mistake | Detect by | Source |
|---|---|---|
| **Prompt Sufficiency Illusion**: generating from a detailed prompt without opening source files (invented columns like `cleaning_fee`) | Ask the AI to list the files it read; diff referenced names against the CSV or YAML | `skills/databricks-expert-agent/references/anti-patterns.md:5-25` |
| Hard-coded list literals of tables, columns or keys | Grep generated code for list literals that match YAML names | `anti-patterns.md:29-61` |
| **Manifest-as-Truth**: building MVs or TVFs for tables that were never created | `SHOW TABLES` / `information_schema` intersection before generating | `anti-patterns.md:65-92`; `DPA/semantic-layer/00-semantic-layer-setup/SKILL.md` §Phase 0.5 check 4 |
| **Domain knowledge injection**: `status IN ('pending','confirmed',…)` when the data holds `'PEND','CONF'` | Every `IN(...)` literal must trace to a `SELECT DISTINCT` | `anti-patterns.md:96-119`; `DPA/silver/01-dlt-expectations-patterns/SKILL.md:241-257` |
| PRD names used instead of live names (`price` vs `base_price`) | Pin a `DESCRIBE` inventory; any name absent from it is a hard error | `skills/databricks-expert-agent/SKILL.md:161`; `DPA/silver/00-silver-layer-setup/SKILL.md:271` |
| Silently "correcting" the fact/dimension classification | Require printed classification plus overrides in `DESIGN_DECISIONS.md` | `DPA/gold/00-gold-layer-design/SKILL.md:212` |
| Inventing transformation types (`BOOLEAN_TO_LABEL`, `SCD2_CLOSE`) | Enum check (Validation 5) | `:385-395`; `design-workers/07-design-validation/SKILL.md:332-343` |
| Literal `[`/`<` placeholders copied into descriptions | Regex `[\[\]<>]` on `description:` | `07-design-validation/SKILL.md:340` |
| Regenerating scaffold files from memory, reintroducing bad imports (`@databricks/appkit-ui` without `/react`; `…/styles` without `.css`) | Regex pre-flight on `client/src/**`; edit incrementally | `skills/genie-code-environment/SKILL.md:185-193, 463-464` |
| Hallucinated library APIs: DQX `is_greater_than`, `is_between`, `is_in`; parameters `value`/`min_value` | Compare against the "correct function / wrong names" table | `DPA/silver/02-dqx-patterns/SKILL.md:147-177, 342-355` |
| Hallucinated metric-view keys (`name`, `time_dimension`, `window_measures`, `join_type`, `table`) | `Unrecognized field` errors; YAML key allowlist | `DPA/semantic-layer/01-metric-views-patterns/SKILL.md:165-175` |
| Wrong format enums (`percent`, `decimal`) | Allowlist {byte, currency, date, date_time, number, percentage} | `:494-503` |
| Oracle, Postgres or T-SQL dialect in benchmark SQL (`SYSDATE`, …) | Dialect scan (see the caveat in §11) | `DPA/semantic-layer/03-genie-space-patterns/SKILL.md:388-404` |
| Guessed metric names for eval gates | Key thresholds only on names seen in a pilot run | `GA/sdlc/03-scorers-and-judges/SKILL.md:317-347` |
| Invented headers (`x-forwarded-user-info`) | `canonical_names` null-map, audited | `apps_lakebase/skills/06d-appkit-agent-app-proxy/SKILL.md:119`; `skills/vibecoding-state/SKILL.md:541` |
| Using a skill's "canonical" helper that is not in the installed library (`databricks_openai.LongTermMemory`) | Probe the candidates (`skill_helper_resolution`) | `skills/vibecoding-state/SKILL.md:466-521` |

### 5.2 Process and workflow shortcuts

| AI mistake | Detect by | Source |
|---|---|---|
| "I know these patterns already", so the skill is never read | Proof-of-reading gate (state each skill's key pattern) and the Skill Usage Summary | `skills/databricks-expert-agent/SKILL.md:36-47`; `DPA/semantic-layer/00-semantic-layer-setup/SKILL.md:132-145` |
| Batch-loading every worker up front, causing format divergence | Check the read order in the Skill Usage Summary | `DPA/gold/00-gold-layer-design/SKILL.md:175` |
| Skipping the requirements template because "the request seems complete" | The gate must be filled before Step 2 | `DPA/bronze/00-bronze-layer-setup/SKILL.md:150-172`; `DPA/silver/00-silver-layer-setup/SKILL.md:254-258` |
| Auto-deploying when asked only to author | 🛑 STOP sections; deployment only on request | `DPA/gold/01-gold-layer-setup/SKILL.md:391-401` |
| Bulk-creating every semantic asset without checkpoints | Phase completion gates ("Shall I proceed…?") | `DPA/semantic-layer/00-semantic-layer-setup/SKILL.md` §Phase 1-3 Completion Gate |
| "Deploy anyway to see what the cluster says" | STOP rule on pre-flight failure | same file, §Phase 0.5 |
| Inferring workshop mode from "small" or "demo" | Exact-phrase opt-in; the mode is echoed on the first line | `DPA/planning/00-project-planning/SKILL.md:68-81` |
| Overwriting an existing `plans/` tree | Idempotency guard defaults to skip | `:102-131` |
| Creating artifacts beyond the manifest ("self-discovery") | Check the 1:1 manifest mapping and counts | `DPA/semantic-layer/00-semantic-layer-setup/SKILL.md:679-693` |
| Paraphrasing format contracts across subagents | Paste the full `DESIGN_DECISIONS.md` into each subagent prompt | `DPA/gold/00-gold-layer-design/SKILL.md:323,395` |
| Replacing a validated Genie instruction block | Append-only rule; diff old vs new | `DPA/semantic-layer/03-genie-space-patterns/SKILL.md:340-344` |
| Silently dropping user benchmark questions | Report each invalid question with its reason | `:273-287` |
| Improvising workarounds (npm hooks, platform-detect conditionals) | Match the error to the Common Errors table first | `apps_lakebase/skills/03-appkit-deploy/SKILL.md:89,138` |
| Retrying the same class of fix | Change approach after two same-class failures | `DPA/genai-agents/09-simple-agent-scaffold/SKILL.md:641-653` |
| Fixing one file when sibling files share the bug | "Same-class fix rule": grep the whole generation batch | `DPA/common/databricks-autonomous-operations/SKILL.md` §Step 5 (`:382-388`) |

### 5.3 Platform and DAB configuration errors

| AI mistake | Detect by | Source |
|---|---|---|
| `python_task`, CLI-style `parameters`, `argparse` in notebooks | `validate_bundle.py` checks 2-3; grep for `argparse` | `skills/databricks-asset-bundles/SKILL.md:159-202`; `references/common-errors.md:241-294` |
| Missing `environments`/`environment_key`; `job_clusters`/`new_cluster` | Checklist; validator check 6 (see its false positives in §11) | `SKILL.md:120-147` |
| `${catalog}` instead of `${var.catalog}`; `job_task` instead of `run_job_task` | Validator checks 4 and 5 | `scripts/validate_bundle.py:71-110` |
| The same notebook in several jobs | Duplicate-path scan; atomic-job rule | `common-errors.md:9-30` |
| Missing `# COMMAND ----------`, or Python inside a `# MAGIC %md` cell (`NameError`) | Notebook-format lint | `SKILL.md:204-228` |
| Target-less `bundle deploy`, or a prod deploy in session | Require `--target dev`; prod only in CI | `SKILL.md:64-69` |
| `bundle run` after a local edit without redeploying | Always chain `deploy && run` | `SKILL.md:565-580` |
| Expecting `--var` at run time to change `warehouse_id` | Know which values are deploy-time baked | `SKILL.md:582-601` |
| Removing a resource block (destroys Lakebase or the app) | Diff `databricks.yml` for removed blocks | `SKILL.md:603-613`; `common-errors.md:833-889` |
| Declaring `postgres_endpoints.primary` next to `postgres_projects` (400 "already exists") | Validate the bundle; resource checklist | `common-errors.md:936-992` |
| Believing `--force` fixes name conflicts | It only fixes state drift; use prefixed names | `common-errors.md:910-935` |
| Reading the parent `run_id` output (`{}`) | Use `tasks[i].run_id` | `SKILL.md:113-114`; autonomous ops Step 4b |
| Counting `SHOW TABLES` rows as success | Explicit allowlist of the expected fully-qualified names | `SKILL.md:108-112` |
| Alert v2 `condition`/`quartz_cron_expression`; volume `permissions` | Validator checks 7-8 | `validate_bundle.py:142-186` |
| Hard-coded catalog in dashboard JSON | `dataset_catalog` check (warning) | `validate_bundle.py:189-203` |
| `DEFAULT` column clauses (`allowColumnDefaults` error) | Grep the DDL for `DEFAULT` | `DPA/common/unity-catalog-constraints/SKILL.md:117-131` |
| FK to a business key; inline FK; nullable PK | Pre-apply checklist; `information_schema` constraint queries | `unity-catalog-constraints/SKILL.md:44-131, 210-218` |
| `ALTER SCHEMA … SET TBLPROPERTIES(predictiveOptimizations)` (PARSE_SYNTAX_ERROR) | Use `ENABLE PREDICTIVE OPTIMIZATION` | `schema-management-patterns/SKILL.md:154-164` |

### 5.4 Data-correctness errors (the expensive, silent class)

| AI mistake | Detect by | Source |
|---|---|---|
| No dedup before MERGE → `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE` | Count check before and after dedup; `GROUP BY key HAVING count>1` | `DPA/gold/pipeline-workers/03-deduplication/SKILL.md:42-109` |
| Dedup key ≠ merge key | Compare `dropDuplicates` columns with the ON clause | `:126-157` |
| Wrong grain: aggregated fact without `groupBy` on the PK, or duplicates at the PK | Grain validation query (duplicates at PK = 0) | `design-workers/01-grain-definition/SKILL.md:58-112`; `01-gold-layer-setup/SKILL.md:441` |
| Averages stored in facts | Additivity tag per measure (V5 rule 7) | `design-workers/03-fact-table-patterns/SKILL.md:44-86` |
| NULL FKs, or NULL vs 0 confusion | `unknown_member` rows; NULL-rate checks | `design-workers/02-dimension-patterns/SKILL.md:81-91`; `03-fact…/SKILL.md:191-200` |
| Fact-to-fact joins (cartesian) | Plan review; row-count before and after the join | `design-workers/04-conformed-dimensions/SKILL.md:189-200` |
| Re-joining a source after aggregating it in a CTE (inflated sums) | Reconcile TVF totals against a single-pass aggregate | `DPA/semantic-layer/02-…-table-valued-functions/SKILL.md:220-248` |
| Revenue sourced from a dimension (under-reports 4x) | Source must be the fact table for flow measures | `01-metric-views-patterns/SKILL.md:194-206` |
| Many-to-many MV join or wrong `rely.at_most_one_match` → inflated SUM or COUNT | `SELECT key, COUNT(*) … HAVING c>1` must return 0 | `01-metric-views-patterns/SKILL.md:511-530` |
| `MEASURE(a)/MEASURE(b)` for percent-of-total → always 1.0 | Sanity-check that ratios differ across groups | `:571-594` |
| Display names inside `MEASURE()`; prefixed dimensions in MV queries | Run the benchmark SQL | `03-genie-space-patterns/SKILL.md:119-151` |
| `CURRENT_DATE` in benchmark SQL (flaky regressions) | Grep benchmarks for `CURRENT_` | `:97-117` |
| Shadowing `sum`, `count`, `min`, `max` (`'int' object is not callable`) | Lint variable names | `pipeline-workers/02-merge-patterns/SKILL.md:67-102` |
| `expected_signal` mirrored into `expected_response` (Correctness scores the wrong target) | Dataset contract check | `GA/sdlc/02-evaluation-datasets/SKILL.md:144-150` |
| 0-1 metrics compared with 0-100 thresholds | Keep one scale per gate (the repo's own example gets this wrong; §11) | `GA/sdlc/04-evaluation-runs/SKILL.md` §Score normalization |
| Judge without explicit aggregation → no `<scorer>/mean` metric → the gate silently misses it | `judges_with_silent_aggregation_dropouts` must be empty | `GA/sdlc/03-scorers-and-judges/SKILL.md:182-196`; `04-evaluation-runs/SKILL.md:287-300` |

### 5.5 Agent behaviour and environment (Genie Code / Databricks Assistant)

| AI mistake | Detect by | Source |
|---|---|---|
| **Fabricating state**, e.g. "I'm on the Apps page" or "deploy succeeded" without reading `deployment.state` | Demand the evidence (API field, run URL); report unverified items as `unknown` | `skills/genie-code-environment/SKILL.md:48-53, 471` |
| Declaring "impossible" after one blocked path | Three execution paths; a blocked call signals the wrong page | `:42-46, 68-96` |
| Pivoting to SDK or REST `jobs/create` or direct SQL when `bundle deploy` is blocked | Only a bundle-editor retry is allowed; escape hatch only with explicit authorisation | `:136-145, 364-380`; autonomous ops `:573-587` |
| Direct `CREATE TABLE`/`DEEP CLONE` through `executeCode` ("tables appear, gate passes") | Mechanism gate: tables existing is "not sufficient"; the job must have run | `:371-380`; `scripts/genie_gate.py:280-306` |
| Trusting `listFiles` right after a FUSE write | Verify with `os.path.exists`/`os.listdir` in the same block | `:423-428` |
| Phantom success: a SNAPSHOT deploy captured stale source | Pre-deploy flush-verify hash; post-deploy re-export diff; baseline-first bisect | `:479` (P40) |
| "Green deploy = working app" | Human render check; `ErrorBoundary`; `/logz` | `:208-210` |
| "Space/endpoint exists = works"; "greeting works = tools work" | Ask a domain data question and assert a `function_call` occurs | `DPA/genai-agents/09-simple-agent-scaffold/SKILL.md:641-653` |
| Trusting a streaming 200 | Inspect the stream body | `GA/tracks/A-custom-agent-apps/08-debugging/SKILL.md:521-524` |
| Treating a misleading `PERMISSION_DENIED` as a grants problem when the Genie space was wiped | GET the space and check `serialized_space` is non-empty | `DPA/semantic-layer/04-genie-space-export-import-api/SKILL.md:821-848` |
| Letting a built-in skill's domain authority override the governed path (`databricks-lakebase` CLI-first create) | The project's governance skill wins; use built-ins only for read-only verification | `skills/genie-code-environment/SKILL.md:477` (P38) |
| Mis-attributing cause during a deploy spiral | Hold findings as Suspected; re-run toggling one variable at a time | `:482-490` |
| Cold-start timeouts from small `timeoutMinutes` | ≥15 minutes (≥20 for heavy work) or a warm-up call | `:429-436` |

### 5.6 Silent-failure and fail-open patterns (review these hardest)

| Pattern | Why it hides bugs | Source |
|---|---|---|
| The DQ rules loader catches every exception and returns `{}` | `expect_all_or_drop({})` enforces nothing and the run is green | `DPA/silver/01-dlt-expectations-patterns/SKILL.md:147-161` |
| FK and PK constraint failures are "warn + continue" | The model may end up with no constraints and the job still succeeds | `DPA/gold/01-gold-layer-setup/SKILL.md:111`; `scripts/add_fk_constraints_template.py` |
| Mock fallback when Lakebase is unavailable | The UI looks fine with fake data. The countermeasure is a `source: "mock"` flag plus `ConnectionStatus` | `apps_lakebase/skills/05-appkit-lakebase-wiring/SKILL.md:108-114,224,282` |
| Alert deployment passes at ≥90% | A missing CRITICAL alert can pass | `DPA/monitoring/03-sql-alerting-patterns/SKILL.md:154-162` |
| ML notebooks call `dbutils.notebook.exit("FAILED: …")` in `except` | The task finishes SUCCEEDED (inferred platform behaviour) and downstream tasks run | `DPA/ml/00-ml-pipeline-setup/scripts/create_feature_tables_template.py:275-281`, `train_model_template.py:594-600` |
| `genie_gate.py` SKIP counts as PASS | On a clone without the prompt tree, six of seven checks are silently green | `scripts/genie_gate.py:137-139, 180-182 …` |

---

## 6. The prompt catalogue (verbatim, annotated)

`apps_lakebase/prompts/` is not in the public clone (§0). The richest prompts live in `data_product_accelerator/QUICKSTART.md`, `apps_lakebase/Instructions.md`, `genai-agents/PROMPT-GUIDE.md` and `AGENTS.md`.

**PR-1. The minimal "route to a skill with a context file" prompt** (`AGENTS.md:246-249`)
```
I have a customer schema at @data_product_accelerator/context/booking_app_schema.csv.
Please design the Gold layer using @data_product_accelerator/skills/gold/00-gold-layer-design/SKILL.md
```
*Why it works:* it names the **input artefact** and the **governing skill**, so the model grounds on files, not memory. It is the smallest effective prompt. *Caveat:* the path points at a directory that does not exist in the clone (§0).

**PR-2. Stage 1 with a "pre-announced workflow"** (`data_product_accelerator/QUICKSTART.md:57-74`, abridged to 8 of 8 bullets' heads)
```
I have a customer schema at @data_product_accelerator/context/user_name_schema.csv.

Please design the Gold layer using @data_product_accelerator/skills/gold/00-gold-layer-design/SKILL.md

This skill will orchestrate the following end-to-end design workflow:

- **Parse the schema CSV** — read the source schema file, classify each table as a dimension, fact, or bridge, and infer foreign key relationships from column names and comments
- **Design the dimensional model** — identify dimensions (with SCD Type 1/2 decisions), fact tables (with explicit grain definitions), and measures, ...
- **Create ERD diagrams** — ... **Generate YAML schema files** — ... **Document column-level lineage** — ...
- **Create business documentation** — ... **Map source tables** — ... **Validate design consistency** — cross-check YAML schemas, ERD diagrams, and lineage CSV ...
```
*Why it works:* it states **the steps and their order** up front. "The bullet points help you and the LLM … priming the LLM with the correct workflow sequence" (`QUICKSTART.md:450`). It also sets expectations for the human reviewer: each bullet names a checkable artefact.

**PR-3. Stage 2 Approach C, with an explicit parameter** (`QUICKSTART.md:122-134`)
```
Set up the Bronze layer using @data_product_accelerator/skills/bronze/00-bronze-layer-setup/SKILL.md with Approach C — copy data from the existing source tables in the samples.wanderbricks schema.
...
- **Deploy and run** — validate, deploy the bundle, and execute the clone job to populate Bronze tables

Use default catalog as: <YOUR_CATALOG>
```
*Why it works:* it **picks the branch** (Approach C) so the model does not guess, names the **source of truth** (`samples.wanderbricks`) and pins the **one variable** the model must not invent (the catalog).

**PR-4. Stage 3 with an explicit order and a definition of done** (`QUICKSTART.md:149-161`)
```
Set up the Silver layer using @data_product_accelerator/skills/silver/00-silver-layer-setup/SKILL.md
...
- **Deploy and run in order** — deploy the bundle, run the DQ rules setup job FIRST (creates the rules table), then run the SDP pipeline (reads rules from the table)

Ensure bundle is validated and deployed successfully, and silver layer jobs run with no errors.

Validate the results in the UI to ensure the DQ rules show up in centralized delta table, and that the silver layer pipeline runs successfully with Expectations being checked.
```
*Why it works:* it encodes the **dependency order** (a known failure mode) and a **verifiable definition of done** covering the mechanism (rules table populated) and the effect (expectations evaluated), not just "no errors".

**PR-5. Stage 4 with source and target stated** (`QUICKSTART.md:180-192`)
```
Implement the Gold layer using @data_product_accelerator/skills/gold/01-gold-layer-setup/SKILL.md
...
- **Merge data from Silver** — deduplicate Silver records before MERGE, map columns using YAML lineage metadata, merge dimensions first (SCD1/SCD2) then facts (FK dependency order)
- **Deploy 2-job architecture** — gold_setup_job (2 tasks: create tables + add FK constraints) and gold_merge_job (populate data from Silver)
...
Use the gold layer design YAML files as the target destination, and the silver layer tables as source.
```
*Why it works:* the last line **binds both ends** of the transformation to files and tables, and the bullets carry the known correctness rules (dedup, ordering).

**PR-6. The "validate, deploy, troubleshoot until success" loop** (`QUICKSTART.md:210-223`)
```
Using @data_product_accelerator/skills/common/databricks-autonomous-operations/SKILL.md, validate, deploy, run, and troubleshoot until success for all data pipeline jobs — Bronze, Silver, and Gold.
...
- **Diagnose failures at each layer** — on failure, retrieve task-level output (use task run_id, not parent job run_id), check for TABLE_OR_VIEW_NOT_FOUND (upstream not ready), DELTA_MULTIPLE_SOURCE_ROW_MATCHING (dedup needed), or PARSE_SYNTAX_ERROR
- **Apply fixes and redeploy** — fix source files, redeploy, and re-run (max 3 iterations per job before escalation)
```
*Why it works:* it **bounds autonomy** (at most 3 iterations, then escalate), names **where to look** (the task-level `run_id`), gives **known error signatures with root causes**, and says to fix **source files**, not the workspace copy.

**PR-7. Planning with an explicit mode switch** (`QUICKSTART.md:250-260`)
```
Perform project planning using @data_product_accelerator/skills/planning/00-project-planning/SKILL.md with planning_mode: workshop
...
- **Apply workshop mode caps** — enforce hard limits (3-5 TVFs, 1-2 Metric Views, 1 Genie Space) to keep the workshop focused on pattern variety over depth
- **Define deployment order** — establish build sequence: TVFs → Metric Views → Genie Spaces → Dashboards → Monitors → Alerts → Agents
```
*Why it works:* scope is set by an **exact token** the skill detects (`planning_mode: workshop`), not by fuzzy words; the caps are explicit.

**PR-8. Stage 6, plan-driven** (`QUICKSTART.md:277-296`, abridged)
```
Set up the semantic layer using @data_product_accelerator/skills/semantic-layer/00-semantic-layer-setup/SKILL.md
...
- **Create Table-Valued Functions (TVFs)** — write parameterized SQL functions with STRING date params (non-negotiable for Genie), v3.0 bullet-point COMMENTs, and ROW_NUMBER for Top-N patterns
- **Configure Genie Space** — ... General Instructions (≤20 lines), and ≥10 benchmark questions with exact expected SQL
Implement in this order:
1. **Table-Valued Functions (TVFs)** — using plan at plans/phase1-addendum-1.2-tvfs.md
2. **Metric Views** — using plan at plans/phase1-addendum-1.3-metric-views.md
3. **Genie Space** — using plan at plans/phase1-addendum-1.6-genie-spaces.md
```
*Why it works:* each step points at its **plan file** (context), repeats the **non-negotiables** (constraints) and sets an order. *Catch:* the orchestrator runs MVs before TVFs (Phase 1 MV, Phase 2 TVF), so prompt and skill disagree (§11).

**PR-9. Path A, Step 1 system prompt, the best-structured prompt in the repo** (`apps_lakebase/Instructions.md:111-129`)
```
You are a full-stack developer building a web application on Databricks AppKit. Your goal is to scaffold a blank AppKit project, implement a UI with mock data from a PRD, and test locally.

Key requirements:

- Scaffold a **blank** AppKit project (no plugins) using the `01-appkit-scaffold` skill
- Read the PRD to understand user personas, journeys, and data requirements
- Build the app using the `02-appkit-build` skill (frontend components, design quality, routing)
- Use static mock data arrays in all components — no live backend, no SQL warehouse, no database
- Create a UI design document describing screens, components, and navigation
- Test locally at `http://localhost:8000` before proceeding
```
It pairs with an Input Template (`:131-316`) that adds four things:
- **Hard Constraints**, e.g. "If you get a 403, STOP and ask the user for a different workspace", pre-declared noise ("`TABLE_OR_VIEW_NOT_FOUND` errors are expected … do not block") and "do not use a shell variable named `USERNAME`".
- A **file-location table**.
- **Numbered steps** that each name a skill.
- A **Summary Checklist** as the definition of done, closing with "Only proceed to deployment after local testing passes" and a state-file update.

*Why it works:* role, goal, skill references, scope limits (mock data only), **anticipated false alarms**, a stop condition, a checklist and persistence. This is the canonical shape.

**PR-10. Path A, Step 3: config-only scope with explicit DO NOTs** (`apps_lakebase/Instructions.md` §Step 3 System Prompt)
```
- Install `@databricks/lakebase` npm package (do NOT register the plugin in `server.ts` yet)
- Declare `postgres_projects` resource in `databricks.yml` (do NOT declare `postgres_branches` or `postgres_endpoints` — Lakebase auto-creates these)
- Configure `app.yaml` with `valueFrom: postgres` for `LAKEBASE_ENDPOINT` and a static `DB_SCHEMA`
- Derive `DB_SCHEMA` from `$APP_NAME` (hyphens to underscores) for user-scoped database isolation
- Do NOT deploy in this step — deployment happens in the **Deploy and E2E Test** step
- Do NOT create a Lakebase project via CLI — the bundle creates it automatically on first deploy
```
It also says: "**The first deploy WILL show the app in CRASHED state.** This is expected".
*Why it works:* **negative scope** stops the model from "helpfully" doing the next step, each prohibition comes **with its reason**, and **expected failures are announced** so the model does not go into a debug spiral.

**PR-11. Artefact-only design prompts** (`genai-agents/PROMPT-GUIDE.md:190-205`)
```
> Generate `docs/agent_spec.yaml` from `docs/design_prd.md`. Use
> `foundation/00b-agent-spec-and-tool-plan/SKILL.md`. If I ask for MCP web
> research, use web search and record recommendations with source URLs. Do not
> create code or resources.
```
```
> Generate `docs/agent_tool_plan.yaml` from `docs/agent_spec.yaml`. If I provide
> `{agent_sql_catalog}` and `{agent_sql_schema}`, include SQL MCP as a read-only
> tool over those Unity Catalog tables using warehouse `{warehouse_id}`. Do not
> create code or resources.
```
*Why it works:* an input file, an output file, a skill, **"Do not create code or resources"** (design is separated from build), provenance for research ("source URLs") and a **conditional** tool ("If I provide…") with a safety property (read-only). Each has an **Expected** line: "every selected tool has a smoke test; SQL MCP carries read-only guardrails".

**PR-12. A precise implementation prompt with verifiable telemetry** (`PROMPT-GUIDE.md:322-356`)
```
> Configure auth for `{agent_name}`. App-level auth = service principal,
> user-level auth = OBO via `databricks_app.utils.get_user_workspace_client(http_request)`
> called inside `@invoke`/`@stream` handlers. Declare `user_api_scopes` in
> `app.yaml` for least privilege (serving-endpoints, dashboards.genie,
> sql.statement-execution, catalog.connections). Load
> `tracks/A-custom-agent-apps/04-authentication/SKILL.md`.
```
*Why it works:* it names the **exact API and where it is called** (inside the handler, which heads off the "init at startup" bug) and the **least-privilege list**, then points to the skill. P13 ("Verify MLflow `AGENT` spans appear at `{experiment_path}`") and P19 ("Run the 3-probe e2e test") show the pattern of asking for **observable proof**.

**PR-13. A counter-example: a stale prompt that primes the wrong facts**
- `QUICKSTART.md:345` tells the model to use a "6-column grid layout", while the dashboard skill says the grid is 12 columns and calls the 6-unit assumption the #1 bug cause.
- `QUICKSTART.md:427-437` promises "Track A/B/C", Model Serving A/B testing and ResponsesAgent for a course that is now Track A on Apps.

*Lesson:* prompts are code. They drift and need the same review and lint as skills (the repo has prompt linters, but only for the private prompt tree; §9).

---

## 7. Databricks Assistant / Genie Code environment specifics

**Sources:** `skills/genie-code-environment/SKILL.md` (every claim there is tagged `[DOC]`/`[TESTED Pnn]`/`[INFERENCE]`, with probe ledger P1-P41), `skills/vibecoding-state/SKILL.md` and `AGENTS.md:213-238`.

| Dimension | Local IDE agent (Cursor, Claude Code…) | Genie Code (in-workspace agent) |
|---|---|---|
| Auth | CLI profile, `databricks auth login`, `--profile` | **Pre-authenticated**; omit `--profile` (`:57-59`) |
| Compute | Local shell plus remote jobs | **Serverless**; the first `executeCode` pays a **3-5 minute cold start**; `timeoutMinutes` ≥15 (`:429-436`) |
| Tools | Files, shell, CLI | **Surface-scoped** to the current page (notebook, SQL, dashboard, bundle folder…). "Navigate to the right surface first" (`:55-66`) |
| Execution paths | Shell | 1 `runDatabricksCli` (allow-list, **non-deterministic**) → 2 SDK via `executeCode` (most capable; bypasses the allow-list; **no bundle-deploy equivalent**) → 3 native tools (`createAsset`, `readTable`, `openAsset`, …). A raw shell `databricks` call is trampolined. There is also an **action-safety checker** on mutating SDK/REST calls (`:68-96`) |
| Bundle deploy | From the bundle directory | `--target dev` **required** (a target-less deploy is refused by a content guardrail). **CWD is pinned to the current page's bundle root**: open the bundle editor. Bundles are recognised **only inside a git working tree**. A file created in-session is not visible to the CLI's FUSE mount, so edit the existing on-page `databricks.yml` (`:101-149`) |
| Skill discovery | `AGENTS.md` auto-load, `@path` | Skills are copied into `/Workspace/Users/<you>/.assistant/skills/<repo>` and loaded with `readSkillFile("skills/<clone>/…")`. `AGENTS.md` is **read once and does not propagate across threads**, so every prompt must name full skill paths (`:347-360`). Batch independent reads into one turn (they run in parallel) (`:407-411`) |
| Artifact paths | Relative to the repo | The CWD depends on the page type, so **anchor every write to `artifact_root`**; never `/tmp` (`:317-346`) |
| Files | Normal FS | Two write paths: `executeCode open().write()` (needs warm compute), or `createAsset → readFile → workspaceUpdateFile` (compute-free, but the file must exist and must have been read first). Verify with `os.path.exists`, **not `listFiles`** (lags FUSE) (`:412-428`) |
| Node / AppKit | Local `npm`, `tsc` gates, `npm run dev` | **No npm/npx**. The Apps SNAPSHOT deploy builds server-side. Use `apps init --output-dir`; the SDK `w.apps.deploy(..., SNAPSHOT)` is the reliable deploy path. **Build logs only at `<app-url>/logz` in a browser.** Keep `package-lock.json` (`:151-210`) |
| Python | venv | `uv`, pip and Python 3.12 are present but ephemeral; uv/FastAPI agent apps build server-side (`:169-184`) |
| Verifying an app | curl with a PAT | The Apps OAuth gate rejects a bearer token. Use a browser, or replay the **3-hop OAuth** in one `requests.Session()`; on serverless `w.config.token` is `None`, so use `w.config.authenticate()` (`:293-311`) |
| Blocked verbs | n/a | `aitools install` (use a git clone of the skills repo), `apps validate` (page-dependent), and the `postgres`/`lakebase` CLI tool (use `subprocess` inside `executeCode` or REST) (`:212-217, 475, 480`) |
| Genie spaces | Bundle resource / provisioning job | Tier 3 hybrid: `createAsset` shell → PATCH the full `serialized_space` → **persist the JSON in the bundle** (`:219-239`) |
| Semantic assets | Bundle job | **Hybrid:** author the file → apply natively → **extract it back and diff** → the bundle is the source of truth. Invariant: "persisted file + live matches file + bundle validates + job ran once in dev" (`:263-291`) |
| Built-in skills | n/a | Native `using-metric-views`/`writing-sql` skills are "more accurate than the workshop 01/02". The built-in `databricks-lakebase` skill is **authoritative but wrong for the governed path** (P38) |
| BI import | n/a | The `/importBI` slash command turns Tableau or Power BI into an AI/BI dashboard plus local MVs; promote those to UC MVs before Genie can reuse them (`:285-291`) |

**Behavioural rules unique to the in-workspace assistant:**
1. "Match the surface to the task … **Never conclude 'impossible' from one path or one page**" (`:44-46`).
2. "**Don't fabricate state — report unverified facts as `unknown`**" (`:48-53`).
3. Blocked `bundle deploy` → navigate to the bundle editor → still blocked → **STOP**. **Never** substitute the SDK, REST or direct SQL without explicit operator authorisation (`:136-145`).
4. In-session DDL through `executeCode` is the "frictionless-but-wrong" trap: "it 'works' and the tables appear, so the gate passes", but it bypasses version control (`:371-380`).
5. **Manifest-load gate G3.** On Genie Code, the first deploy prompt's `enter` halts until this manual has been read in the thread (`:35-40`; `skills/vibecoding-state/SKILL.md:82,242`).

**Client detection** comes from `vibecoding-state`. It sets `client_context` to `genie_code` when `runDatabricksCli` is present. That detection is itself labelled "[inference — pending the live Genie Code probe]" (`skills/vibecoding-state/SKILL.md:82`). Every routed prompt starts with a client-specific **RULE_0 preamble** (`AGENTS.md:7`).

---

## 8. Apps + Lakebase, and the GenAI agents course

### 8.1 AppKit phases (Path A)

| Phase | Skill | Key rules / gate |
|---|---|---|
| 1 Scaffold and build (mock data) | `01-appkit-scaffold`, `02-appkit-build` | Blank scaffold; replace `server.ts` with `await createApp({plugins:[server()]})`; mock arrays in components; `data-testid` smoke tests; `databricks apps validate`; **"Local testing passed"** gate (`apps_lakebase/Instructions.md:101-432`) |
| 2 Deploy (mock) | `03-appkit-deploy` | Never `rm package-lock.json && npm install`; no lifecycle hooks; match errors to the table, "do NOT improvise" (`03-appkit-deploy/SKILL.md:89-138`) |
| 3 Lakebase setup (config only) | `04-appkit-plugin-add` | Only `postgres_projects` (capped with `default_endpoint_settings`: min 0.5 CU, max 2 CU, suspend 1800 s); `valueFrom: postgres`; per-user `DB_SCHEMA`; **two-phase deploy** (the first deploy CRASHES until `app.resources.postgres` is bound) (`Instructions.md` §Step 3; `skills/databricks-asset-bundles/SKILL.md:479-498`) |
| 4 Wire Lakebase | `05-appkit-lakebase-wiring` | Schema from the PRD; **DDL in `server.ts` runs as the service principal on first deploy** (Deploy-First, so the SP owns the tables); idempotent DDL; `server.extend()` routes with a **mock fallback** tagged `source:"mock"`; `useLakebaseData` hook; `ConnectionStatus`; coerce DECIMAL with `Number()`; index signatures for chart data (`05-appkit-lakebase-wiring/SKILL.md:60-476`) |
| 4b Serving | `06-appkit-serving-wiring` | Model Serving / agent endpoint streaming |
| 4c Agent App proxy | `06d-appkit-agent-app-proxy` | Two Apps: the AppKit service-principal bearer **plus** a verbatim `x-forwarded-access-token`; stamp `x-app-user-email` from `x-forwarded-email`; accept both request shapes, 400 otherwise; dual-format streaming; a synthesized-SSE fallback, tagged as a productized debt, where a gateway guardrail breaks streaming; the Agent App declared as an `app` resource with `CAN_USE`; **3-probe e2e** (direct, SP-only, OBO); do not register `serving()` (`06d…/SKILL.md:119-671`) |
| 4d Chat history + feedback | `07-appkit-chat-history`, `08-appkit-feedback` | Chat tables created at server start by the service principal; per-user scoping; thumbs feedback → Lakebase `Vote` → **MLflow Assessments REST** (`/api/3.0/mlflow/traces/{traceId}/assessments`, `source={HUMAN,userId}`); PATCH on re-click; `enable_trace=True` so `trace_id` is returned; experiment pinned per user (`08-appkit-feedback/SKILL.md:108-333`) |
| 5 Deploy + E2E | `03-appkit-deploy` | Bind the Postgres resource (the `database` value is the RFC-1123 resource FQN, **not** `databricks_postgres`); verify live data end to end |

**Lakebase technical rules**
- Autoscaling projects auto-create the `production` branch and `primary` endpoint, so never declare them.
- Removing a `postgres_projects` block destroys the project.
- Verify caps read-only; never PATCH endpoints on the governed path.
- Always-on endpoints are a cost trap (`skills/databricks-asset-bundles/SKILL.md:479-498`).
- Lakebase tokens expire after 1 hour, so refresh them (`GA/tracks/A-custom-agent-apps/05-lakebase-memory/SKILL.md:44`).
- Cold starts need a retry on `AdminShutdown`/`PoolClosed`: 3 attempts with 5 s/10 s/20 s backoff, and lazy initialisation, never at import (`GA/tracks/A-custom-agent-apps/02-agent-framework/SKILL.md` §Lakebase cold-start retry policy).
- The stray `skills/SKILL.md` documents **Lakebase CDF** (WAL → `lb_<table>_history` Delta tables in about 15 s batches, `REPLICA IDENTITY FULL` required, no partitioned tables).

**OAuth / OBO rules**
- Call `get_user_workspace_client()` inside the request handler; there is no user context at startup (`04-authentication/SKILL.md:198`).
- Declare least-privilege `user_api_scopes`; the user consents on first open.
- Feedback attribution uses `x-forwarded-email`, not the service principal (`source_id=user_email`).
- Apps need OAuth tokens, not PATs (`08-debugging/SKILL.md` DO/DON'T).
- The OBO grant model: under OBO, **your** UC grants apply; a failing data question is often your missing grant (`DPA/genai-agents/09-simple-agent-scaffold/SKILL.md` §Gotchas).

### 8.2 GenAI course structure (`genai-agents/`)

- **Foundation**
  - F0 UC resources (schemas and volumes).
  - F0b agent spec and tool plan (PRD → `agent_spec.yaml` → `agent_tool_plan.yaml`).
  - F1 MLflow GenAI (ResponsesAgent mandatory, autolog, connection pooling).
  - F2 experiments and UC OTEL tracing (experiment path from state; warehouse id before the experiment).
  - F2b TypeScript tracing; F2c trace context (user, session, environment).
  - F3 tools and data access: managed MCP URLs for Genie, UC functions and AI Search; external MCP through UC connections; `system.ai.python_exec`.
  - F4 AI Gateway (optional hardening once there are two or more consumers): inference tables, rate limits per endpoint and user, PII and safety guardrails, fallbacks, `databricks_request_id` correlation, **halt rather than bind an unaudited endpoint**.
  - F5 Knowledge Assistant lifecycle.
- **Track A** (canonical)
  - A1 clone `agent-openai-advanced`; A2 OpenAI Agents SDK behind module-level `@invoke`/`@stream`.
  - A3 tools and MCP, with grants `CAN_QUERY`/`CAN_RUN`/`CAN_USE`; A4 auth; A5 Lakebase memory (short-term session plus long-term).
  - A6 `agent-evaluate` smoke test (≥80% relevance, zero safety failures).
  - A7 deploy and query; A8 debugging, including **agent-as-judge trace diagnosis**.
- **SDLC**
  - S1 prompt registry: `prompts:/<fqn>@alias`, a single slash; UC schema linkage.
  - S2 eval datasets; S3 scorers; S4 eval runs; S4b stakeholder sign-off; S4c end-user feedback.
  - S5 logged model and UC registration (champion alias, rollback).
  - S6 evaluate → gate → promote → deploy with DAB and CI.
  - S7 production monitoring (registered scorers with sampling, trace archival, backfill).
  - S8 GEPA `optimize_prompts`; S8b hand-authored prompt iteration.

### 8.3 Evaluation methodology (distilled)

1. **Dataset contract** (`GA/sdlc/02-evaluation-datasets/SKILL.md` §canonical fields, `:144-160`).
   - Every row carries `row_id, request, expected_response, expected_signal, bucket, journey_id, split (train|held_out|regression|gold), provenance`.
   - **Coverage gates:** `min_rows: 40`, at least one row per bucket and per journey, and a complete expectations schema.
   - `Correctness` reads **only** `expected_response`.
   - Version the datasets and never trust synthetic rows unchecked.
2. **A five-tier scorer suite**, cheap to expensive (`GA/sdlc/03-scorers-and-judges/SKILL.md:198-260`).
   - L1 universal: `Safety`, `pii_protection`, output contract.
   - L2-instruction: `Guidelines`, from the system prompt, about 4-6 rules.
   - L2-behavior: **derived automatically from tools' `writes_to`**.
   - L3-deterministic: regex, parse, SQL compile, `sql_execution_readonly` with a refusal short-circuit.
   - L3-judge: `make_judge(..., feedback_value_type=Literal["yes","no"], model="databricks:/<endpoint>")`.
   - Conversation scorers: `ConversationCompleteness` and `UserFrustration` with session-tagged traces.
3. **MLflow 3.11 contracts** (`:182-196`): import `make_judge` from `mlflow.genai.judges`; the `provider:/model` URI; explicit aggregation so `<scorer>/mean` exists; the `{{ trace }}` placeholder is required for trace judges; the judge endpoint comes from state and is never hard-coded.
4. **Run** (`GA/sdlc/04-evaluation-runs/SKILL.md:69-258`).
   - `mlflow.genai.evaluate(data, predict_fn, scorers)`, where `predict_fn(inputs: dict) -> str|dict`.
   - Answer-sheet mode re-scores existing outputs.
   - Retry with backoff on transient errors; handle `None` traces.
   - Gate on the **logged** metric names, on one scale.
5. **Failure-shape router** (`:260-285`): classify each failed gate as `instruction | tool_call_empty | retrieval | scorer_calibration | safety_classifier` and route the fix. **Never "fix" an L1 or architecture failure with prompt edits.**
6. **Telemetry** (`:287-350`) is persisted on the run:
   - `failing_trace_ids` and `safety_buffer` (headroom to the threshold);
   - `predict_fn_exception_count` (a **smaller denominator inflates means**);
   - sentinel counts, `judges_with_silent_aggregation_dropouts` (must be empty to promote) and the signature seen.
7. **Human calibration.** Label schemas, a labeling session, then `sync()` followed by `merge_records_from_session`. Judge-human disagreement routes to `scorer_calibration` (`:352-495`).
8. **Iteration.**
   - S8b: at most 3 hand-authored revisions, each re-evaluated on the **full** dataset, promoted `@staging→@production` only if **every** target scorer meets or beats baseline (`GA/sdlc/08b-prompt-handauthoring/SKILL.md:120-132`).
   - S8 (GEPA): only when explicitly invoked, with safeguards and at least 2 scorers with rationales.
9. **Sign-off gate** (`GA/sdlc/04b-stakeholder-signoff/SKILL.md:37,117`): "Engineering-only gates fail in the field". Record the decision in **machine-readable YAML front matter** (engineering plus stakeholder). CI parses the YAML; **substring grep is forbidden** (`GA/sdlc/06-deployment-and-automation/SKILL.md:70-78`).
10. **Production.** Registered scorers with sampling; the end-user feedback round-trip gate (`log_feedback → override → delete → re-log`, read back from the SQL warehouse) (`GA/sdlc/04c-end-user-feedback/SKILL.md:164`); negative feedback flows back into the eval dataset.

---

## 9. `scripts/`: what the code actually checks

### 9.1 `scripts/audit_genie_compat.py` (157 lines): an environment-coupling linter
- It walks the repo (`ROOTS=["."]`) and reads **only** `.md .sql .yml .yaml .txt .mdx .json`, **not `.py`** (`:42`). It skips `.git`, `node_modules`, `.cursor`, `plans/`, `retrospectives/`, `presentations/` and its own outputs (`:45-57`).
- It applies **12 line-level regexes** (`:59-107`), each tagged with a RULE id:
  - `LOCAL_AUTH` (`databricks auth login`, `DATABRICKS_TOKEN=`); `LOCAL_PATH` (`/Users/`, `/home/`, `~/`, `../..`);
  - `BARE_ARTIFACT_PATH` (save or write instructions with a relative `*.md/csv/yaml/json/sql` path not anchored to `<ARTIFACT_ROOT>`);
  - `LOCAL_SPARK`, `SCRIPT_DEPLOY`, `SETUP_SCRIPT`, `PY_BUNDLE_CONFIG`, `GENIE_RESOURCE`;
  - `INSESSION_CREATE` (`jobs create`, `createAsset(`, `CREATE SCHEMA|VOLUME|TABLE`); `APP_DEPLOY`;
  - `SHELL_DATABRICKS` (a bare `databricks bundle|jobs|…` not preceded by `run`); `CLIENT_NAV` ("open in your IDE").
- It writes one CSV row per matching line and pattern, then prints counts by class.
- **Nature.** A lexical heuristic: it cannot tell a prohibition from a prescription. For example, `genie-code-environment/SKILL.md:372`, a *"do NOT CREATE TABLE"* sentence, is counted as `INSESSION_CREATE`, and so are the Lakebase CDF permission-table cells in `skills/SKILL.md:34`. **CONFIRMED by running it.**

### 9.2 `scripts/genie_gate.py` (654 lines): a ratcheting regression gate
1. `check_audit` (`:94-130`) runs `scan()` and buckets the results as `area::class`, where area is the top-level directory.
   - **FAIL** if any `area::class` count rises in an area not passed with `--touched`. A rise inside touched areas only warns.
   - The baseline (`genie_gate_baseline.json`) moves forward only with `--update-baseline` after review; that is the "ratchet".
2. `check_roundtrip` (`:133-155`) requires `apps_lakebase/prompts/sync_markdown_to_seed.py --dry-run` to print "No differences detected"; the markdown prompts must match the SQL seed.
3. `check_fork_parity` (`:171-236`). Every `*.genie-code.md` prompt fork must:
   - keep all `{template_tokens}` from its default (the per-user-prefix invariant);
   - keep the same `**Gate:**`;
   - use no bare `@…/SKILL.md` mentions (the full `skill_ref_root` path is required).
4. `check_deploy_fork_discipline` (`:239-315`). Forks that contain "bundle deploy" must include:
   - a no-direct-creation prohibition;
   - the phrase `databricks.yml not found` (the page-recovery recipe);
   - "not sufficient" (a mechanism gate);
   - "bundle editor";
   - "escape hatch".
   Semantic "hybrid" forks may substitute the orphan/drift terms.
5. `check_hybrid_fork_discipline` (`:318-397`) requires "persisted", "reproducible", "drift", "orphan", "live matches file", "extract-back" and "non-dev". Genie forks additionally need `data-rooms`, `serialized_space`, `metric_views` and "benchmark"; dashboard forks need `openAsset`/`readAssetById`.
6. `check_lakehouse_fork_discipline` (`:400-513`) requires:
   - the `readSkillFile("skills/vibe-coding-workshop/` path form, a "preflight acknowledgement" and `source_linked_deployment`;
   - "create catalog" named as forbidden (Bronze);
   - `saveAsTable` forbidden and `validate_gold` present (Gold);
   - `os.path.exists` plus `listFiles`, and the no-`DEFAULT` rule;
   - "column inventory" + "describe table" (Silver and Gold), "contract test" (Silver);
   - Gold design: "just-in-time", no "in one batched", `DESIGN_GAP_ANALYSIS.md`/`README.md`, "upstream cross-reference", `population_strategy`.
7. `check_state_persistence_discipline` (`:516-584`). Forks with `State-lock:` need `prompt_id:`/`gate:`, a canonical state path, "mandatory ritual, not advisory" and "NOT complete until". It also asserts that the vibecoding-state skill contains "idempotent by `prompt_id`", "supersede" and "recovery reconcile".
8. `check_bundle` (`:587-599`) is optional: `databricks bundle validate --target dev`.

**What this means:** these are **prompt contract tests**. They regression-test that prompts and skills still contain the guardrail language that prevented observed field failures. They are substring checks, so they prove presence of wording, not correct behaviour.

**Executed result at HEAD (CONFIRMED).**
- `GATE RESULT: FAIL`. The total fell from 3557 to 2163, but untouched areas rose: `data_product_accelerator::BARE_ARTIFACT_PATH 8→10`, `skills::APP_DEPLOY 108→114`, `skills::INSESSION_CREATE 14→17`. Part of the rise comes from the stray `skills/SKILL.md` and the new industry-alignment worker.
- **All six prompt-tree gates print SKIP and return True** (`:137-139, 180-182, 255-257, 335-337, 414-416, 528-530`), so a checkout without the private tree passes them silently. That is fail-open.
- `check_bundle` looks only at a **root** `databricks.yml` (`:589`); generated bundles live in `<slug>_dab/`.

### 9.3 `scripts/verify_agent_track_flow.py` (718 lines): the agent-track prompt chain contract
- **Ordering.** It asserts that the SQL seed rows for 11 section tags (`agent_spec_design`=38 … `appkit_chat_feedback_mlflow`=48) carry those exact `order_number`s (`:14-26, :71-74`).
- **Per-prompt must-contain and must-not-contain**, for example:
  - 38 must say "Do NOT create code", "DO NOT predict tool selections", the unified eval paths (`agent.benchmark_seeds.coverage_buckets`, `governance.scorer_suite.*`), and must **not** contain `tool_shaped_scorers`.
  - 39 must contain "ASK ME", "COPY the SCALAR value" and the tool-shaped scorer derivation, and must **not** set `endpoint: "docs/agent_spec.yaml.agent.model"`. That line guards a real observed LLM error: copying a YAML path string instead of its value.
  - 43 must contain "No model endpoint may be hardcoded in Python".
  - The core prompts must not make AI Gateway mandatory (`assert_core_prompt_gateway_optional`, `:49-58`).
- **Skill-side checks.** It asserts content in skills, including the vibecoding-state `hydrate_from_files` op, `resolver_version: "3.0"`, `hydrated_from_files: true` and the spec-schema/state-template fixtures (`:304-490`).
- **Legacy and lint.** Legacy section files must keep `section_tag:`. It then runs `lint_section_prompts.py` as **informational** only (`:700-714`).
- **Executed result (CONFIRMED).** It crashes immediately: `AssertionError: Missing required file: apps_lakebase/prompts/02_seed_section_input_prompts.sql`. So it **fails closed**, the opposite of `genie_gate.py`'s fail-open SKIP.

### 9.4 Other scripts worth knowing
- **`skills/databricks-asset-bundles/scripts/validate_bundle.py`** runs 9 lexical checks (duplicate YAML names, `python_task`, CLI parameters, `${var}` prefixes, `job_task`, `environment_key`, the Alert v2 schema, volume grants, the dashboard catalog). Bugs are in §11.
- `DPA/gold/01-gold-layer-setup/scripts/validate_upstream_contracts.py` is the Phase 0 gate.
- `skills/vibecoding-state/scripts/probe_endpoints.py` probes endpoints for short chat, long context (80K characters), SQL quoting and `stream=True`.
- `scripts/_ws8_state_ritual.py`, `_ws7_prefix_dab.py` and `_invert_clone_step0.py` are one-off, idempotent mechanical edits over the private prompt forks.

---

## 10. Patterns worth stealing (verbatim, ≤25 lines each)

**P1. Rationalization red flags: a pre-mortem against skipping steps** (`skills/databricks-expert-agent/SKILL.md:36-47`)
```
## Rationalization Red Flags

If you catch yourself thinking any of these, STOP — you are about to skip a critical principle:

| Rationalization | Reality |
|---|---|
| "The prompt already has everything I need" | Prompt completeness does not equal project truth. Read skills by task type. |
| "I know these patterns already" | You don't have the current version in context. Read it. |
| "This is just a quick task" | Quick tasks create the most schema drift. Extract, don't generate. |
| "Other skills cover this" | No other skill enforces extraction-over-generation. This one does. |
| "I'll read it after I explore the codebase" | Skills tell you HOW to explore. Read first. |
| "The user gave me code blocks to follow" | User code may contain hardcoded names. Validate against source files. |
```

**P2. Self-consistency is not correctness** (`DPA/gold/00-gold-layer-design/SKILL.md:481`, excerpt)
> "…record the resulting mismatch count (target: 0) as an explicit line in the validation report — running it silently does not satisfy this check. This is the only validation that confirms the artifacts agree with *reality* rather than just with each other (the YAML/ERD/lineage consistency checks are self-referential — all three are generated from the same session data, so a systematic column error would pass them while failing here)."

**P3. The Phase 0 "Extract-Don't-Generate" checkpoint block** (`skills/databricks-expert-agent/SKILL.md:120-143`)
```
Before generating ANY artifacts (SQL, Python, YAML), produce this structured block:

Extract-Don't-Generate: confirmed
Source files I will extract from:
  - [list actual file paths discovered via Glob / SHOW TABLES / DESCRIBE]
Source files I will NOT generate from memory:
  - [list what would be tempting to hardcode]
Rules in working memory:
  1. Extract, Don't Generate
  2. CLUSTER BY AUTO
  3. CDF + Row Tracking
  4. Serverless + notebook_task
  5. Comments + Tags on everything

If you cannot list concrete source file paths, you MUST run discovery first:
- `Glob("gold_layer_design/yaml/**/*.yaml")` for table/column names
- `SHOW TABLES IN catalog.schema` for live catalog verification
- `DESCRIBE TABLE catalog.schema.table` for column-level validation

Do NOT proceed to artifact generation until source files are identified.
```

**P4. Proof-of-reading gate** (`DPA/semantic-layer/00-semantic-layer-setup/SKILL.md:132-145`)
```
**STOP. Before proceeding past Phase 0, confirm you have read the common skills by listing the key pattern from each:**

| Skill | Key Pattern to Confirm |
|-------|-----------------------|
| `databricks-python-imports` | Bundle root: `rsplit('/src/', 1)[0]` |
| `databricks-asset-bundles` | Job `base_parameters` must include all widget params |
| `databricks-expert-agent` | "Extract names from source, never hardcode" |
| `naming-tagging-standards` | CM-02 dual-purpose COMMENT with PURPOSE/BEST FOR/NOT FOR |

**If you cannot produce these patterns from memory, you have not read the skills. Read them now.**
```

**P5. The state file supersedes chat memory: verify-write plus handoff invariant** (`skills/vibecoding-state/SKILL.md:309,312`)
> "**Verify the write (load-bearing — not advisory):** after appending, **re-read the live state file** and confirm the new `## Prompt <prompt_id>` section … **The prompt is NOT complete until this re-read confirms the write.** The chat summary is NOT the state store."
> "**Handoff invariant** … carry `state_file_path`, `last_completed_prompt`, `last_gate`, `environment_capabilities`, and `state file updated: yes/no` verbatim … **Generate the summary FROM the live state file's Per-Step Log — never from in-memory recollection — and the state file always supersedes the summary**"

**P6. Blocked ≠ impossible; don't fabricate state** (`skills/genie-code-environment/SKILL.md:42-53`)
```
## The one operating rule (read this first)

> **Match the surface to the task. If a path is blocked, try the next of the three execution paths. Never
> conclude "impossible" from one path or one page.** Every operation that was hard-blocked on one path in
> the probes had a working alternative on another. [TESTED, recurring P1–P18]

> **Don't fabricate state — report unverified facts as `unknown`.** Never claim a page, surface, deploy
> state, or capability you did not actually observe (e.g. "I'm on the Apps page" when you never navigated
> there, or "the deploy succeeded" without reading `deployment.state`). If you haven't verified it this
> turn, say so and probe it. The `runDatabricksCli` allow-list is **non-deterministic** (a verb blocked on
> one attempt can be allowed on the next), so "blocked once" is not "impossible" — and "worked once" is not
> "always works." [TESTED P32]
```

**P7. Failure-shape router for eval regressions** (`GA/sdlc/04-evaluation-runs/SKILL.md:275-285`)
```
| `primary_shape` | Route to | Pre-condition |
|-----------------|----------|---------------|
| `instruction` | **Skill 08b (prompt hand-authoring)** | Only if `l1_failures` is empty. If L1 failures exist, route to architecture / system-prompt redesign instead — do **not** paper over an L1 failure with prompt iteration. |
| `tool_call_empty` | **Skill 06 direct trace debug** | Symptoms: `UNRESOLVED_COLUMN.WITH_SUGGESTION`, `TABLE_OR_VIEW_NOT_FOUND`, permission-denied, or empty tool output. Fix the data/grant/SQL-grounding issue before re-running eval. |
| `retrieval` | **Retrieval tuning** (chunking, reranker, top-k, embeddings) | Failing scorers are retrieval-shaped (`groundedness`, `retrieval_relevance`, `context_precision`). Do not iterate the system prompt. |
| `scorer_calibration` | **Skill 03 (Scorers and Judges)** | Judge disagrees with human labels at >X%. Fix the scorer prompt, aggregation, or `feedback_value_type` before treating the eval signal as ground truth. |
| `safety_classifier` | **Endpoint audit and role re-binding** | Safety scorer regressed because the scoring endpoint is the wrong model or hit a guardrail. Audit `llm_role_endpoints.llm_judge_safety` binding before iterating the agent. |

**Hard rule:** never route an L1 failure to Skill 08b. L1 means architecture/role-binding/refusal — instruction iteration cannot fix it. Mis-routing here is the single most expensive failure mode in the SDLC.
```

**P8. Explicit opt-in, never inferred scope** (`DPA/planning/00-project-planning/SKILL.md:68-77`)
```
### Mode Detection Rules

1. **Default is ALWAYS `acceleration`.** If the user does not explicitly declare workshop mode, use acceleration.
2. **Workshop mode requires EXPLICIT opt-in.** The user must include one of these EXACT phrases:
   - `planning_mode: workshop`
   - `"workshop mode"`
   - `"use workshop mode"`
3. **Do NOT infer workshop mode** from words like "small", "simple", "demo", "limited", "quick", "basic", "training", or "few". These are NOT triggers. ...
4. **When in doubt, ask.** ...
5. **Confirm mode at the start.** The first line of any plan output should state the active mode:
```

**P9. Cardinality gate before trusting a join** (`DPA/semantic-layer/01-metric-views-patterns/SKILL.md:519-530`)
```
-- The join key MUST be unique in the dimension table (0 rows = safe many-to-one).
SELECT <join_key>, COUNT(*) AS c
FROM ${catalog}.${gold_schema}.<dim_table>
WHERE is_current = true            -- include for SCD2 dimensions
GROUP BY <join_key>
HAVING c > 1;                       -- must return 0 rows
```
> "A quick `COUNT(*)` before/after adding a join is the fastest fan-out smoke test — if the row count changes, you have a fan-out."

**P10. Fail-loud validator before a fragile API call** (`DPA/semantic-layer/04-genie-space-export-import-api/SKILL.md:156-200`, excerpt)
```python
def _assert_sql_arrays(space: dict) -> None:
    """
    Validate serialized_space invariants before POST / PATCH.
    Raises RuntimeError on the FIRST violation — never returns False / warns.
    """
    errors: List[str] = []
    if space.get("version") not in (1, 2):
        errors.append("serialized_space.version must be 1 or 2 (prefer 2); got %r" % space.get("version"))
    ...
    wh = cfg.get("semantic_warehouse_id")
    if not isinstance(wh, str) or not _WAREHOUSE_ID_RE.match(wh or ""):
        errors.append(
            "config.semantic_warehouse_id must be a concrete warehouse id baked at deploy time; "
            f"got {wh!r}. Template placeholders like '${{warehouse_id}}' are never acceptable."
        )
    ds = space.get("data_sources") or {}
    for key in ("tables", "metric_views"):
        items = ds.get(key) or []
        idents = [it.get("identifier", "") for it in items]
        if idents != sorted(idents):
            errors.append(f"data_sources.{key} must be sorted by identifier (got {idents})")
```

**P11. Reasoning-trap list: "exists ≠ works"** (`DPA/genai-agents/09-simple-agent-scaffold/SKILL.md:641-653`, abridged)
```
- **"Genie Space exists" ≠ "Genie Space works."** Listing a space proves it was created, not that its tables are queryable. Always ask a real question from Step 0 before wiring it into an agent.
- **`READY` endpoint ≠ working agent.** An endpoint that only answers greetings has never exercised the tool-calling path. Verify with a domain-specific data question.
- **Same error class after retry ≠ try another variant — change approach.** If two path-style fixes produce the same framework-loader error, the category of fix is wrong. Step back and understand the framework's lifecycle.
- **`PATCH /permissions/warehouses/{id}` with `service_principal_name = <uuid>` ≠ granting a system SP.** Returns `200 OK` but silently drops the entry. ...
```

**P12. Hybrid authoring invariant (native speed with a governed source of truth)** (`skills/genie-code-environment/SKILL.md:265-270`)
> "author the definition file FIRST, apply it natively for a fast dev loop, extract the live asset back and diff it against the file, then keep the Asset Bundle as the version-controlled source of truth and the non-dev deploy mechanism. The invariant: **persisted file + live matches file + bundle validates + job ran once in dev.** An orphan asset (no file) or drift (live ≠ file) is the regression."

**P13. `bundle run` does not sync: the 30-minute debugging trap** (`skills/databricks-asset-bundles/SKILL.md:565-580`, abridged)
```
**Root cause:** `bundle run` does NOT sync files. It only triggers the workspace-deployed copy from the **last** `bundle deploy`. Local edits are invisible until you re-run `bundle deploy`.
| `bundle deploy` → `bundle run` | ✅ Yes |
| `bundle run` (after local edit, no deploy) | ❌ No — runs stale workspace copy |
**Rule:** Every code edit → re-run `bundle deploy` → then `bundle run`.
**Corollary — never hotfix in the Databricks workspace:** Any edit made directly to a file under `/Workspace/.bundle/<target>/files/` is destroyed on the next `bundle deploy`.
```

**P14. Autonomy with bounded retries and an evidence-rich escalation** (`DPA/common/databricks-autonomous-operations/SKILL.md:382-406`, abridged)
```
5. **Same-class fix rule:** Before redeploying, grep ALL files from the same generation batch for the same error pattern. ...
**Maximum 3 iterations.** Track each iteration's error and fix.
### Step 7: Escalation (After 3 Failed Attempts)
1. **All errors encountered** — with run IDs, task keys, error messages
2. **All fixes attempted** — what was changed and why
3. **Root cause hypothesis** — best guess based on evidence
4. **Run page URLs** — direct links to the Databricks UI
```

---

## 11. Risks, bugs, contradictions, outdated guidance

### 11.1 Code or template bugs (would produce wrong results or failures)

1. **CONFIRMED: the "SCD Type 2" templates are not SCD2.**
   - On a match they only update `record_updated_timestamp`. They never expire the current row (`is_current=false`, `effective_to`) or insert a new version when attributes change, so history is lost.
   - Locations: `DPA/gold/pipeline-workers/02-merge-patterns/assets/templates/scd-type2-merge.py:57-64`; the same code in `02-merge-patterns/SKILL.md` §SCD Type 2; `DPA/gold/01-gold-layer-setup/scripts/merge_gold_tables_template.py:292-300`; `03-deduplication/SKILL.md:86-92`.
   - The 02 template also skips dedup, which contradicts "ALWAYS deduplicate".
2. **CONFIRMED in the repo; the semantic claim is general Spark behaviour, not executed here: `orderBy(ts.desc()).dropDuplicates(keys)` is presented as "SIMPLE and RELIABLE", with the advice "Avoid: Window functions with row_number()"** (`03-deduplication/SKILL.md:159-172`, used in every merge template).
   - Spark does not guarantee which duplicate survives `dropDuplicates`, because the preceding sort is not preserved through the aggregation shuffle.
   - The deterministic pattern is `row_number() over (partition by key order by ts desc) = 1`, which `04-grain-validation/references/grain-validation-patterns.md:113-181` itself uses.
3. **CONFIRMED: the merge template silently merges nothing when given the canonical YAML.**
   - `load_table_metadata` reads `table_properties.entity_type` and `table_properties.scd_type` (`merge_gold_tables_template.py:84-86`), and `main()` branches on `scd_type == "scd2"` (`:486`).
   - The canonical YAML puts `scd_type: 2` at **top level** and has no `entity_type` in `table_properties` (`00-gold-layer-design/references/yaml-schema-patterns.md:59-62, 204-210`). Result: empty dimension and fact dicts, no merges, and a green job.
   - The vocabulary also drifts: `2` / `'2'` / `SCD_TYPE_2` / `scd2` (`design-decisions-template.md:100`; `06-table-documentation` references). SCD1 is a `# TODO`.
   - The lineage key mismatch: the parser collects `lineage.source_table`, but the YAML uses `silver_table`, so `meta["source_tables"][0]` would raise IndexError. Multi-column lineage strings (`silver_column: store_id, processed_timestamp`) would become `col("store_id, processed_timestamp")`. (Static reading; not executed.)
4. **CONFIRMED: FK YAML shape drift can silently produce zero FK constraints.**
   - Design-worker examples use a column-level `foreign_key: references: dim_date.date_key` (`02-dimension-patterns/SKILL.md:141-152`, `03-fact-table-patterns/SKILL.md:134-179`).
   - The implementation and validation read only table-level `foreign_keys` (`scripts/add_fk_constraints_template.py:62`, `07-design-validation/SKILL.md:215`).
   - The "warn + continue" FK policy then hides the result.
5. **CONFIRMED: the predictive-optimisation syntax contradiction.**
   - `schema-management-patterns/SKILL.md:154-163` labels `ALTER SCHEMA … SET TBLPROPERTIES('databricks.pipelines.predictiveOptimizations.enabled')` as a PARSE_SYNTAX_ERROR.
   - The Gold setup template runs exactly that form inside its main `try` (`setup_tables_template.py:205-210`; `references/setup-script-patterns.md:223-227`), and the expert-agent skill teaches it as a "Core Pattern" (`skills/databricks-expert-agent/SKILL.md:244-248`).
   - (Inferred) Automatic liquid clustering depends on predictive optimisation, so this compounds `CLUSTER BY AUTO`.
6. **CONFIRMED: `CREATE OR REPLACE TABLE` in Gold setup** (`01-gold-layer-setup/SKILL.md:240`; `setup_tables_template.py:115`). Re-running `gold_setup_job` drops all Gold data, including SCD2 history, and its constraints. Bronze correctly uses `IF NOT EXISTS`.
7. **CONFIRMED: `UNIQUE` constraint on every `business_key`, including SCD2 dimensions** (`setup_tables_template.py:165-178`). This contradicts "SCD2 business key does NOT have UNIQUE" (`unity-catalog-constraints/references/constraint-patterns.md:59`) and "skip UNIQUE on serverless" (`validation-guide.md:221-233`). The error is swallowed as a warning.
8. **CONFIRMED (pattern); the effect is inferred Databricks behaviour: ML templates call `dbutils.notebook.exit("FAILED: …")` inside `except`.** This ends the notebook normally, so the task reports SUCCEEDED, masking failure from `bundle run`, dependent tasks and the autonomous-ops loop, which keys on `result_state` (`create_feature_tables_template.py:275-281`; `train_model_template.py:594-600`; `batch_inference_template.py:356-360`). The rationale in rule 3 ("may show SUCCESS on failure", `ml/00-ml-pipeline-setup/SKILL.md:244`) inverts the real risk. Re-raise after logging.
9. **CONFIRMED: `from pyspark.sql.functions import F, isnan`** (`ml/00-ml-pipeline-setup/SKILL.md:304`) raises an ImportError. The idiom is `import pyspark.sql.functions as F`.
10. **CONFIRMED (by reading): threshold-scale bug in the canonical gate example.** `THRESHOLDS` are on a 0-1 scale (`"safety/mean": 0.95`), while `all_thresholds_met(metrics_0_100, thresholds)` takes metrics converted to 0-100 (`GA/sdlc/03-scorers-and-judges/SKILL.md:322-347`). Composed as the names suggest, **every gate passes** (e.g. 70 ≥ 0.95). The skill's own Common Mistakes table warns about exactly this.
11. **CONFIRMED: fail-open DQ loader.** It catches every exception and returns `{}`, so zero expectations are enforced. The snippet also references undefined `catalog`/`schema` inside the module (`DPA/silver/01-dlt-expectations-patterns/SKILL.md:147-161`).
12. **CONFIRMED: the emit-checkpoint script sorts jobs alphabetically but labels them "deploy order"** (`skills/databricks-asset-bundles/SKILL.md:751, 760`). It would emit `dashboards → genie → metric_views → tvfs`, running Genie before its dependencies.
13. **CONFIRMED: `validate_bundle.py` bugs.**
    - It flags `run_job_task`, `sql_task` and `pipeline_task` tasks lacking `environment_key` (`:131`), yet those task types do not use environments. The skill's own composite-job example (`SKILL.md:312-328`) would fail.
    - It hard-codes `repo_root/resources` (`:212-214`), but bundles live under `<slug>_dab/resources`.
    - It flags any `permissions:` in a file that also has `volumes:`.
14. **CONFIRMED: planning's `detect_planning_sources` globs `gold_layer_design/yaml/*.yaml` non-recursively** (`DPA/planning/00-project-planning/SKILL.md` §Step 0.1), while YAMLs live in `{domain}/`, so the Gold design is never detected. It also uses repo-relative rather than `dp_bundle_root` paths.
15. **CONFIRMED: `${bundle.target}` in a bash command.** `databricks pipelines start-update --pipeline-name "[${bundle.target} …]"` (`DPA/silver/00-silver-layer-setup/SKILL.md:387`) fails with "bad substitution" (tested in bash). The `--pipeline-name` flag is SUSPECTED not to exist. Use `databricks bundle run -t dev <pipeline_key>`.
16. **SUSPECTED: `CREATE CATALOG IF NOT EXISTS`** in `bronze/…/scripts/setup_tables.py:38`, `gold/…/setup_tables_template.py:201`, `schema-management-patterns/SKILL.md:56` and `databricks-asset-bundles/references/configuration-guide.md:594`. PRE-REQUISITES grants only `USE CATALOG`/`CREATE SCHEMA` (`PRE-REQUISITES.md:43-63`), and the private-fork gate demands "catalog no-create hard-stop" language (`scripts/genie_gate.py:457-462`), which is evidence the authors hit this.
17. **SUSPECTED (scale): streaming `dropDuplicates` without a watermark is "MANDATORY"** (`silver-table-patterns.md:396-450`). There are **zero** `watermark` mentions in the repo, so state grows without bound (inferred from Structured Streaming semantics). Use `withWatermark` + `dropDuplicatesWithinWatermark`, or dedupe in a materialised view or Gold MERGE.
18. **CONFIRMED gap: CDF is claimed but not used.** Bronze calls CDF "required for Silver streaming" (`bronze/00-bronze-layer-setup/SKILL.md:70`) and QUICKSTART says Silver ingests "using Change Data Feed" (`QUICKSTART.md:154`). There is no `readChangeFeed`, `apply_changes` or `create_auto_cdc` anywhere in the accelerator; Silver uses an append-only `read_stream`. (Inferred) Updates or overwrites in Bronze break the stream unless there is a full refresh.
19. **SUSPECTED: ML `clean_numeric` maps NULL/NaN/Inf to 0.0** (`ml/00-ml-pipeline-setup/SKILL.md:300-320`). This contradicts "NULL vs 0 matters" (`03-fact-table-patterns/SKILL.md:191-200`) and biases models. Prefer explicit imputation plus missing-indicators.
20. **SUSPECTED: the Genie dialect table overstates the problem.** `NVL`, `TO_DATE`, `TRUNC(date,'quarter')`, `DATEADD(unit,n,d)` and `DATEDIFF(unit,a,b)` are, to my knowledge, valid Databricks SQL (`03-genie-space-patterns/SKILL.md:388-404`). It is still reasonable as a style rule.
21. **SUSPECTED:** "UC limitation: CHECK constraints … not supported in DDL" (`03-sql-alerting-patterns/SKILL.md:364`). Delta supports `ALTER TABLE … ADD CONSTRAINT … CHECK`; the statement over-generalises. The `SHOW CONSTRAINTS IN <schema>` command in `unity-catalog-constraints/SKILL.md:214` is SUSPECTED not to exist; use `information_schema.table_constraints`.
22. **SUSPECTED (scale): in-memory `assessmentStore = new Map()` for feedback dedup** (`apps_lakebase/skills/08-appkit-feedback/SKILL.md:220`) is lost on restart or with several replicas, which creates duplicate assessments.
23. **CONFIRMED: `skills/SKILL.md` is a stray Lakebase CDF skill with no frontmatter.** It is invisible to routing and trips the audit gate. **24 accelerator skills violate "name must match directory name"** (`DPA/admin/create-agent-skill/SKILL.md:78`, e.g. `name: gold-layer-design` in `00-gold-layer-design/`).

### 11.2 Contradictions between skills (an AI following one will violate another)

24. **CONFIRMED: manifest-missing behaviour.** Semantic and observability say "NEVER create artifacts via self-discovery; STOP" (`00-semantic-layer-setup/SKILL.md:151`; `00-observability-setup/SKILL.md:109`). The navigator and ML say "falls back to self-discovery" (`skill-navigator/SKILL.md:85`; `ml/00-ml-pipeline-setup/SKILL.md:79`).
25. **CONFIRMED: TVF parameter types.** The orchestrator says "NEVER use DATE, INT, or other non-STRING params" (`00-semantic-layer-setup/SKILL.md:153`). The TVF worker's canonical pattern uses `top_n INT DEFAULT 10` (`02-…-table-valued-functions/SKILL.md:92,191`).
26. **CONFIRMED: semantic build order.** QUICKSTART and planning say TVFs → MVs → Genie (`QUICKSTART.md:244, 288-293`). The orchestrator phases run MVs first (`00-semantic-layer-setup/SKILL.md:469-534`), and the deploy checkpoint lists `metric_views_job` first (`skills/databricks-asset-bundles/SKILL.md:692-693`).
27. **CONFIRMED: the metric-view YAML in the expert agent is invalid according to the MV skill.** `version: 1`, `metric_views: - name:`, `table:`, `dimensions: [..]`, `windows:` (`skills/databricks-expert-agent/SKILL.md:284-301`) against "NEVER include `name`", `source` not `table`, no top-level windows (`01-metric-views-patterns/SKILL.md:165-175`).
28. **CONFIRMED: the expert agent contradicts itself.** Essential Rule 4 says "every job uses `notebook_task`" (`:33`), but the sample workflow uses `python_wheel_task` (`:313`). Rule 3 "CDF + Row Tracking on every table" conflicts with Bronze and table-properties, which omit row tracking for Bronze (`DPA/common/databricks-table-properties/SKILL.md:35-50`).
29. **CONFIRMED: comment style.** Planning prescribes `COMMENT 'LLM: Returns top N …'` (`planning/00-project-planning/SKILL.md:788`). Table-documentation lists the "LLM:" prefix as Mistake 1 (`06-table-documentation/SKILL.md:48,204-207`).
30. **CONFIRMED (logic): SCD2 join semantics.**
    - Facts FK to **surrogate** keys (`06-table-documentation/SKILL.md:57-61`), yet the same file says "Always filter with `WHERE is_current = true` when joining to facts" (`:163`). Facts pointing at historical versions then drop out or return NULL attributes.
    - Planning instead joins on the business `_id` plus `is_current` (`planning/…/SKILL.md:784`), which is as-is reporting.
    - Nothing explains the as-was versus as-is choice.
31. **CONFIRMED: surrogate key type.** STRING MD5 (`yaml-schema-patterns.md:79-92`; merge templates) against BIGINT keys with a `-1` Unknown member (`02-dimension-patterns/SKILL.md:83-88`; `03-fact…/SKILL.md:195`).
32. **CONFIRMED: NULL FKs.** "Dimension foreign keys should never be NULL" (`02-dimension-patterns/SKILL.md:83`) against accumulating-snapshot date FKs that are "NULL until …" (`03-fact-table-patterns/SKILL.md:166-180`) and `nullable: true` FKs in the DESIGN_DECISIONS contract.
33. **CONFIRMED: `sys.path`.** `databricks-python-imports/SKILL.md:103-125` requires a `sys.path` bundle-root block; the same file (`:269-270`) says "❌ DON'T: Manipulate sys.path". ML rule 16 says "ALWAYS inline helper functions (don't import modules)" and rule 17 says use `sys.path.insert` (`ml/…/SKILL.md:237-261`).
34. **CONFIRMED: serverless-only versus classic workaround.** The DAB skill says "NO `job_clusters` … NO EXCEPTIONS" (`skills/databricks-asset-bundles/SKILL.md:122-147`). UC constraints suggests "Use classic (non-serverless) compute for the constraint application job" (`unity-catalog-constraints/SKILL.md:198-208`).
35. **CONFIRMED: Genie asset limits.** Planning says "25-asset **hard** limit" (`planning/…/SKILL.md:773,902`). The Genie API skill says tables have "No hard limit — keep ~25-30" (`04-genie-space-export-import-api/SKILL.md:103-104`).
36. **CONFIRMED: Genie config paths.** `src/{project}_semantic/genie_configs/` (`00-semantic-layer-setup` Phase 3 step 7), `src/semantic/genie_configs/**` (Phase 4 sync), `src/genie_spaces/*.json` (Phase 0.5 pre-flight; DAB Tier 1). Mismatched sync patterns mean "config not found" at run time.
37. **CONFIRMED: instruction field names.** The validator checks `instructions.general_instructions` (`04-genie…/SKILL.md:128,332-335`), while the ID and sort sections use `instructions.text_instructions` (`:430,610,643`).
38. **CONFIRMED: Genie deploy tiers disagree on status.** DAB says Tier 1 native `genie_spaces` has "LANDED" (2026-08-23) (`SKILL.md:360-369`). The same file's Tier 2 says "Until Tier 1 lands … The IDE client always uses Tier 2" (`:387-409`), and `genie-code-environment/SKILL.md:222` says Tier 1 is "landing ~this month".
39. **CONFIRMED: naming drift.**
    - Metric views: `mv_{domain}_{entity}` (`naming-tagging-standards/SKILL.md:208`) vs `{domain}_analytics_metrics` (`planning/…/SKILL.md:777`).
    - Genie space names: `{Domain} {Description} Space` vs `{Project} {Domain} Analytics Space`.
    - `dp_bundle_root`: `<use_case_slug>_dab` (`AGENTS.md:76`) vs `{user_schema_prefix}_<use_case_slug>_dab` (`skills/vibecoding-state/SKILL.md:82`).
    - `selected_layer`: `gold|silver|…` (`planning/…/SKILL.md:66`) vs `deployed_gold|…` (templates; `00-semantic-layer-setup`, which **raises** on anything else in acceleration mode).
40. **CONFIRMED: app location.** `AGENTS.md:78` says the app root is `<repo-root>/<app_name>/`, "NOT nested under `apps_lakebase/`". `apps_lakebase/Instructions.md:84,202` and all its steps use `apps_lakebase/$APP_NAME/`. `skills/vibecoding-state/SKILL.md:169` (hydrate) uses `apps_lakebase/$APP_NAME/`, while `:216` says "NOT `apps_lakebase/<app_name>/`".
41. **CONFIRMED: Lakebase models and ownership.**
    - AppKit uses Autoscaling `postgres_projects` with `valueFrom: postgres`; `05-appkit-lakebase-wiring/SKILL.md:73` still lists `postgres_branch`/`postgres_endpoint` as prerequisites, which Instructions and Error 18 forbid.
    - Track A uses provisioned `database.instance_name` and "DON'T use valueFrom" (`GA/tracks/A-custom-agent-apps/08-debugging/SKILL.md:330-373, 532`).
    - Track A says "Run `await store.setup()` **locally** before deploying" (`:336, 526`), while AppKit's Deploy-First says never run DDL locally, because the service principal must own the tables (`05-appkit-lakebase-wiring/SKILL.md:192`).
42. **CONFIRMED: MLflow experiment paths.**
    - ML uses `/Shared/{project}_ml_{model}` (`ml/…/SKILL.md:242`) with no user prefix, which collides in shared workspaces and contradicts the per-user invariant (`skills/databricks-asset-bundles/SKILL.md:71-75`).
    - PROMPT-GUIDE P0 suggests `/Shared/loyalty-agent/traces` (`genai-agents/PROMPT-GUIDE.md` §P0), which `vibecoding-state` explicitly forbids ("generic leaves like `Tracing`, `traces` … are forbidden", `SKILL.md:276-279`).
    - P0 also runs `databricks schemas create --catalog main …`, in-session creation that violates RULE_10.
43. **CONFIRMED: validation versus iteration split.** Datasets define `split: train|held_out|regression|gold` (`GA/sdlc/02-evaluation-datasets/SKILL.md` §canonical fields). 08b iterates prompts against the **full** dataset with "Holdout splits are explicitly out of scope" (`08b-prompt-handauthoring/SKILL.md:123`). This is a SUSPECTED overfitting risk, mitigated only by the 3-iteration cap.

### 11.3 Outdated or stale documentation

44. **CONFIRMED:** QUICKSTART stage 7 still says "6-column grid" (`QUICKSTART.md:345`), against 12-column in the dashboard skill (`02-databricks-aibi-dashboards/SKILL.md:345-381`). Stage 9 still says "Track A/B/C", "A/B testing" and "ResponsesAgent" (`QUICKSTART.md:427-437`).
45. **CONFIRMED:** the navigator routes to eight nonexistent GenAI workers (`DPA/skill-navigator/SKILL.md:246-253`, e.g. `genai-agents/01-responses-agent-patterns`), to `common/databricks-expert-agent` and `common/databricks-asset-bundles` (moved to root `skills/`), and to a `capstone/` that does not exist (`:340-341, 393-399`). Monitoring 05 and 06 and `semantic-layer/06` are missing from its map.
46. **CONFIRMED:** the Gold-design phase table cites nonexistent workers `design-workers/00-schema-intake`, `01-business-onboarding`, `03-fact-patterns`, `04-erd-patterns` and `05-yaml-schema-patterns` (`00-gold-layer-design/SKILL.md:167-172`). Other missing references: `semantic-layer/00-…/references/pre-flight-ddl-smoke.md` (`:448`) and `common/databricks-autonomous-operations/references/job-design-patterns.md` (`:464,597`).
47. **CONFIRMED: CLI minimums disagree:** v0.200+ (`data_product_accelerator/QUICKSTART.md:16`, `README.md:27`), ≥0.295.0 (`README.md:24`, `QUICKSTART.md:119`), ≥1.3.0 for `genie_spaces` and 1.15.0 for the `postgres_projects` schema (`skills/databricks-asset-bundles/SKILL.md:15,496`). Vibecoding-state compares CLI versions "lexicographically" (`skills/vibecoding-state/SKILL.md:478`), which mis-orders `0.30` vs `0.295`.
48. **CONFIRMED:** the GenAI orchestrator's Genie Code first-run ("Clone the whole repo into `/Users/<you>/.assistant/skills/…`", `GA/00-course-orchestrator/SKILL.md:97-98`) predates the two-place git-clone plus copy kickstart (`AGENTS.md:215-228`), which is required for bundle recognition.
49. **CONFIRMED: size discipline is not met.** The navigator claims "ALL SKILL.md files are lightweight (< 2K tokens)" and budgets Tier 1 (4 core files) at about 4K tokens (`skill-navigator/SKILL.md:23,181`). Measured with chars/4, `databricks-expert-agent` + `naming-tagging-standards` alone are about 11K tokens. 32+ SKILL.md files exceed 500 lines, and the dashboards skill is 2,423 lines (about 20K tokens). "Claude Opus 200K" is hard-coded (`:23,175`).
50. **SUSPECTED:** many numeric claims are unverified anecdotes, e.g. "100% of SQL compilation errors … not consulting YAML" (`06-table-documentation/SKILL.md:44`), "First-Time Success Rate: 0% → 95%+" (`02-…-table-valued-functions/SKILL.md:145`), "catches ~80%" (Phase 0.5), "4-6x faster" (`README.md:168`). Treat them as motivation, not evidence.
51. **SUSPECTED heuristic presented as platform fact:** "Genie processes General Instructions effectively only when ≤20 lines" (`03-genie-space-patterns/SKILL.md:89-95`). It is also in tension with the 13-section extended-instruction mandate (`:307-317`). Rules 13 and 18 are duplicates (`:289, 346`).
52. **CONFIRMED:** the repo's own regression gate fails at HEAD, and its prompt checks are fail-open without the private tree (§9.2). `verify_agent_track_flow.py` cannot run on the public clone (§9.3).

---

## 12. Interview-prep angles (questions with crisp answers)

1. **"How do you use the Databricks Assistant effectively?"**
   - Treat it like a capable junior who has not seen the codebase.
   - Scope one unit of work per thread and give it the **governing instructions and the context files by path**. In Genie Code, that means skills from `.assistant/skills` and full paths, because AGENTS.md does not carry across threads.
   - State hard constraints and an explicit definition of done.
   - Make it **inspect before it writes**: `DESCRIBE`, `SELECT DISTINCT`, `information_schema`.
   - Generate one artefact type at a time behind a gate, and deploy through the bundle, not ad-hoc DDL.
   - Use the surface-appropriate path (bundle editor for deploys), and put all durable state in files, never in chat.
2. **"How do you know when the Assistant is wrong?"**
   - **Provenance:** every name must trace to a source (YAML, `DESCRIBE`, `DISTINCT`).
   - **Execution evidence:** a run URL, a task-level result, or `event_log` expectation counts, not the word "done".
   - **Reality over self-consistency:** YAML, ERD and lineage agreeing proves nothing if all three were generated from the same wrong assumption.
   - **Semantic checks:** duplicates at the PK, orphan FKs, one current row per SCD2 key, the row count before and after a join, ratios that are not 1.0.
   - **Red flags:** list literals of table names, invented enum values, API names not in the docs, non-Databricks SQL dialect, "exists" offered as proof of "works", and claims about state it did not observe.
3. **"Walk me through building a medallion pipeline from a raw schema."**
   - Start from an `information_schema.columns` export.
   - (1) **Design Gold first**: classify tables, pick the grain, dimensions and SCD types, facts and additivity, the bus matrix, the YAML contracts and the lineage enum. Validate it against itself **and** against real Silver.
   - (2) **Bronze** as bundle jobs, with CSV-driven DDL, CDF and `CLUSTER BY AUTO`, seeded Faker or a clone (Auto Loader for production).
   - (3) **Silver** SDP: mirror the columns, drop critical DQ failures to quarantine from a rules table, dedupe, verify via `event_log`.
   - (4) **Gold** from the YAML: tables → PKs → Unknown rows → FKs, then dedupe (key = merge key), MERGE dimensions then facts, and validate grain and FKs.
   - Deploy all of it with DABs (validate → deploy → run → poll the task `run_id`, at most 3 fix loops, then escalate). Then plan the consumption layer through manifests.
4. **"How do you design a Gold layer?"**
   - Start from business processes and **grain** ("one row per …"). The PK must match the grain.
   - Choose SCD1 or SCD2 per dimension; use surrogate keys, **flattened** dimensions, text flags, Unknown members, role-playing views and conformed dimensions across a bus matrix.
   - Store additive components in facts (compute ratios in the semantic layer), mark semi-additive measures, and keep NULL distinct from 0.
   - Document everything with dual-purpose comments, since Genie reads them, and PK/FK constraints.
   - Physically: `CLUSTER BY AUTO`, CDF, row tracking and predictive optimisation.
5. **"What makes a good Genie space?"**
   - Curated assets in priority order: **metric views, then TVFs, then a few Gold tables**, 10-25 assets, all commented and descriptively named.
   - Concise general instructions with no contradictory routing and ambiguous terms defined.
   - Synonyms and entity matching in `column_configs`, and SQL expressions for KPIs.
   - **≥10 benchmarks with pinned-date, tested SQL**, gathered from real users first and validated through the Conversation API.
   - A serverless warehouse; config versioned as JSON in the bundle; append-only instruction changes; drift audits.
6. **"How do you evaluate a GenAI agent?"**
   - A versioned dataset (≥40 rows, bucket and journey coverage, `expected_response`).
   - A tiered scorer suite: safety and PII, guideline adherence, behaviour derived from tool write permissions, deterministic checks, then LLM judges with typed outputs and explicit aggregation.
   - Run `mlflow.genai.evaluate` with a matching `predict_fn`, gate on the logged metric names on one scale, and persist the failing trace IDs and exception counts.
   - Calibrate judges with human labels. **Route failures by shape**; prompt tweaks never fix architecture failures.
   - Require structured stakeholder sign-off, then monitor in production with registered scorers and user feedback linked to traces.
7. **"Liquid clustering vs partitioning, and how does it scale?"**
   - The repo mandates `CLUSTER BY AUTO`: no manual keys, no `PARTITIONED BY`. Predictive optimisation chooses and evolves the keys and compacts incrementally, which avoids the small-file and skew problems of over-partitioning.
   - (Inferred) Partitioning still makes sense only for very large tables with a low-cardinality filter column, or for lifecycle management. Automatic LC needs predictive optimisation enabled, which the Gold template's broken PO statement undermines (§11.5).
8. **"How do you deduplicate before a MERGE, and what is wrong with `orderBy().dropDuplicates()`?"**
   - Deduplicate on exactly the merge key.
   - `dropDuplicates` keeps an arbitrary row because a sort is not preserved through the shuffle. Use `row_number() OVER (PARTITION BY key ORDER BY ts DESC) = 1`.
   - In streaming, bound the state with a watermark (`dropDuplicatesWithinWatermark`).
9. **"Implement SCD Type 2 correctly."**
   - Stage the changed rows by comparing a hash of the tracked attributes against the current version.
   - MERGE on business key AND `is_current`: when matched and the hash differs, set `is_current=false` and `effective_to=ts`; insert the new version with `is_current=true`. The usual trick unions a "null merge key" copy of the changed rows so they insert.
   - Validate with one `is_current` row per key and no overlapping validity windows.
   - The repo's template only touches a timestamp, so it is not SCD2 (§11.1). A good interview story about catching an AI or template error.
10. **"How do you deploy reproducibly, and why DABs?"**
    - A single artefact (`databricks.yml` plus `resources/`) that is reviewable, diffable and promotable dev→prod in CI.
    - Per-user prefixes in shared workspaces; `bundle deploy` bakes variables; `bundle run` does not sync code; removing a resource destroys it.
    - Avoid in-session ad-hoc creation, because it makes drift invisible to version control and `bundle destroy`.
11. **"A multi-task job failed. How do you debug it?"**
    - `get-run`, then find the failed task's **task-level `run_id`**, then `get-run-output`, then match the error signature: `TABLE_OR_VIEW_NOT_FOUND` means upstream order; `DELTA_MULTIPLE_SOURCE_ROW_MATCHING` means dedup; `PARSE_SYNTAX_ERROR` means the SQL.
    - Fix the **source** (not the workspace copy), grep siblings for the same bug, redeploy and re-run.
    - After three attempts, escalate with run IDs, the fixes tried and a hypothesis. Capture the lesson.
12. **"Metric views vs TVFs vs tables for Genie?"**
    - Metric views give governed, reusable measures and dimensions: consistent KPIs and correct re-aggregation, including LOD. TVFs are for parameterised multi-step logic (top-N by period, cohorts). Tables are a last resort.
    - One MV per analytical grain; a TVF only when an MV cannot answer. Keep additive components alongside ratios for dashboard pivots.
13. **"Silver data quality: drop, quarantine, or fail?"**
    - Critical rule failures are dropped and quarantined with a reason, so the pipeline keeps flowing and the business sees clean data plus a remediation queue. Warnings are tracked but kept. `expect_or_fail` is reserved for truly fatal conditions.
    - Rules live in a governed Delta table so data stewards can tune them without redeploying. Use DQX when you need row-level diagnostics or dataset-level checks.
14. **"OBO vs service principal in Databricks Apps?"**
    - The app service principal handles app-to-app and app-owned resources, such as Lakebase tables created on first deploy.
    - OBO (`x-forwarded-access-token`, a least-privilege `user_api_scopes` list) makes queries run with the **user's** UC grants, so governance is enforced per user. Build the client per request.
    - Attribution for feedback uses `x-forwarded-email`.
15. **"How does this scale beyond the workshop?"**
    - The repo is demo-oriented: Bronze is not production ingestion, streaming dedup has no watermark, and the feedback dedup map is in memory.
    - For production: add Auto Loader or Lakeflow Connect ingestion, CDF or AUTO CDC between layers, watermarking, incremental Gold MERGEs keyed on change windows, serverless autoscaling, and Genie spaces split by domain (about 25 assets). Put the AI Gateway in front of the LLMs (rate limits, inference tables).
16. **"Explain the business value in one breath."**
    - It turns weeks of expert data engineering into a guided, auditable process that produces a governed data product: a documented star schema, quality-checked pipelines, trusted KPIs, a natural-language analytics space and evaluated agents.
    - Guardrails catch the classic AI mistakes before they reach production, and everything is versioned for promotion.
17. **"Why one conversation per stage?"**
    - Context is finite and attention decays. Loading only the current phase's instructions keeps the rules salient.
    - Files, not chat, carry state across the boundary, so a reset or compaction cannot corrupt facts, and stages can run in parallel.

---

## 13. AI stewardship playbook (for a live coding task with the Databricks Assistant)

**0. Frame the unit of work.**
- One stage or one artefact type per thread. Start fresh when switching stages.
- Before starting, confirm the durable context exists on disk: the design contract, manifests, the state file and the bundle root.

**1. Write the prompt with this skeleton** (distilled from PR-9, PR-10 and PR-6):
```
ROLE + GOAL (one sentence)
READ FIRST: <skill/guide paths>, <input files: YAML/CSV/PRD/plan>    (full paths; ask it to confirm what it read)
SCOPE: do X only. Do NOT: <next steps>, <in-session creation>, <prod targets>   (+ why)
CONSTRAINTS: naming/prefix, serverless, CLUSTER BY AUTO, STRING date params, … (the non-negotiables)
ORDER: 1 … 2 … 3 …   (dependency order)
EXPECTED NOISE: "<error X> is expected at this step"
DONE WHEN: <checklist of verifiable outputs + evidence to show me>
STOP: after artefacts are written; ask before deploy.  PERSIST: update <state file> and re-read it.
```

**2. Load context deliberately.**
- Reference files by path rather than pasting large blobs. In Genie Code, use full `skills/<clone>/…` paths and batch independent reads into one turn.
- Keep the phase narrow: only the current phase's instructions, plus notes from the last one.
- When delegating to sub-agents or new threads, **paste the full contract text** (e.g. the design decisions), not a paraphrase.

**3. Force grounding before generation.**
- Have it produce the "Extract-Don't-Generate" block (P3): the sources it will extract from and the values it will not guess.
- If it cannot name sources, have it run discovery first: `SHOW TABLES`, `DESCRIBE TABLE`, `SELECT DISTINCT` for enums, `information_schema`.
- Pin the column inventory in the thread and treat any other name as an error.

**4. Generate incrementally behind gates.**
- One artefact type at a time: DDL → load → validate, or MV → TVF → Genie.
- After each, review a summary of names, paths and decisions and approve the next phase.
- For fragile targets (apps, Genie JSON), run the local validators (`bundle validate`, `_assert_sql_arrays`, `EXPLAIN`, regex pre-flights) before any deploy.

**5. Verify with evidence, at three levels.**
- **Static:** validators, lint, `bundle validate`, and a diff of the generated YAML against its source.
- **Execution:** deploy to dev, then **`deploy && run`** (never `run` alone). Poll to a terminal state and read the task-level output and run URL. For DLT, query `event_log()` expectation counts. For apps, do a human render check and read `/logz`. For Genie and agents, ask a real domain question and assert tool calls and non-empty rows.
- **Semantic:** duplicates at the PK = 0, orphan FKs = 0, one current SCD2 row per key, the count before and after each join, reconciliation totals against the source, ratios not stuck at 1.0, eval gates on the right scale and metric names, no silent aggregation drop-outs.

**6. Watch for red flags. Stop and challenge when you see:**
- literal lists of table or column names, or `IN (...)` values with no `SELECT DISTINCT` behind them;
- API names or YAML keys you do not recognise (check the docs or skill tables), or Oracle/T-SQL dialect;
- "done", "deployed" or "I'm on page X" with no observed evidence; "exists" offered as proof of "works";
- `job_clusters`, `python_task`, `argparse`, target-less deploys, `CREATE OR REPLACE` on stateful tables, `orderBy().dropDuplicates()`, `except: … exit("FAILED")`, `except: return {}`;
- silent fallbacks (mock data, warnings instead of failures, SKIP=PASS);
- a pivot to REST, SDK or direct SQL "to get past" a blocked bundle deploy;
- regenerating scaffold or config files from memory instead of editing them;
- the same fix retried with small variations.

**7. Recover when it is wrong.**
- **Stop generating.** Name the source gap. Run discovery. Resume with extracted values and comment where each came from.
- Fix the **source** file, then grep every file from the same batch for the same bug (the same-class fix rule).
- At most three fix-and-redeploy loops. After two failures of the same class, **change approach**: read the framework's lifecycle or docs instead of guessing variants.
- In a spiral, go baseline-first: redeploy the last known-good state, then change **one variable at a time** and label hypotheses Suspected until they are isolated.
- Escalate to a human with run IDs, errors, fixes tried and a hypothesis.

**8. Close out.**
- Update the state file (captured IDs, gate, resolved issues) and **re-read it** to confirm the write.
- Have the AI list what it actually read and used (the Skill Usage Summary).
- Capture the lesson as a rule or checklist item: a skill update, a prompt constraint, or a validator. The next run then starts smarter.

---

## 14. Glossary

- **AGENTS.md:** the auto-loaded routing file for AI coding agents (root and component level).
- **SKILL.md / agent skill:** a markdown instruction pack with YAML frontmatter plus `references/`, `scripts/` and `assets/templates/` (agentskills.io format).
- **Orchestrator / worker:** a `00-` skill that sequences a stage's phases; `01+` skills hold patterns for one concern and can run standalone.
- **Progressive disclosure / JIT loading:** load SKILL.md, then a reference only when a phase needs it; discard afterwards and keep notes.
- **Notes to Carry Forward:** the worker-defined summary passed to the next phase instead of the full skill.
- **Extract, Don't Generate:** take every name and value from source files or the catalog, never from model memory.
- **Plan-as-contract / manifest:** YAML emitted by Planning (`plans/manifests/*`) that downstream stages implement one-to-one.
- **`DESIGN_DECISIONS.md`:** the Gold design contract (inventory, FK format, description format, transformation enum, keys, boolean-to-text list).
- **`gold_inventory`:** the verified dict of tables and columns from YAML plus `information_schema`; the only allowed namespace in stage 6.
- **vibecoding-state / state file:** the runtime contract and `.vibecoding-state.md` (capabilities, captured IDs, gates, overrides, per-step log).
- **`client_context` / RULE_0:** the detected client (`ide_cli` or `genie_code`) and the client-specific preamble on each routed prompt.
- **`artifact_root` / `dp_bundle_root` / `app_root` / `agent_app_root`:** the output anchors: project root, the `<slug>_dab` bundle folder, the app folder and the agent-app folder.
- **RULE_10:** no in-session artifact creation; everything is a bundle resource brought to life by `bundle deploy`.
- **Genie Code:** the Databricks in-workspace AI agent (the Assistant's agent mode). It is pre-authenticated, runs on serverless and has surface-scoped tools.
- **`runDatabricksCli` / `executeCode` / `createAsset`:** Genie Code's CLI tool (allow-listed), code-execution tool (SDK) and native asset tools.
- **FUSE gap:** files created through the workspace API are not immediately visible to the CLI's filesystem mount.
- **SNAPSHOT deploy:** the Apps deploy mode that copies source and builds server-side.
- **DAB (Databricks Asset Bundle):** infrastructure-as-code for jobs, pipelines, dashboards, apps, schemas, Genie and more. `bundle validate/deploy/run/destroy`.
- **Atomic / composite / orchestrator jobs:** a three-level job hierarchy; notebooks appear only in atomic jobs, and higher levels use `run_job_task`.
- **Environments V4:** the serverless job environment spec (`environment_version: "4"`) referenced from every task.
- **`CLUSTER BY AUTO`:** automatic liquid clustering; keys chosen by predictive optimisation.
- **CDF / row tracking / deletion vectors:** Delta features for change propagation, incremental refresh and cheap deletes.
- **Predictive optimisation:** managed OPTIMIZE, VACUUM and clustering at catalog or schema level.
- **SDP / DLT / LDP:** Spark (Lakeflow) Declarative Pipelines, formerly Delta Live Tables. `import dlt` or `from pyspark import pipelines as dp`.
- **Expectations / quarantine:** declarative DQ rules (`expect_all_or_drop`, `expect_all`) plus a side table of failed rows with reasons.
- **DQX:** the Databricks Labs data-quality framework (row and dataset checks, diagnostics, profiler).
- **Grain:** what one fact row represents. It defines the PK.
- **SCD1 / SCD2:** overwrite in place vs keep history with `effective_from/to` and `is_current`.
- **Surrogate key / business key:** the warehouse-generated PK vs the natural source identifier.
- **Unknown member:** a `-1` dimension row that absorbs missing FKs.
- **Conformed dimension / bus matrix:** a dimension shared identically across facts / the fact × dimension matrix.
- **Role-playing / degenerate / junk dimension:** one dimension used in several roles through views / a key kept on the fact / a combination of low-cardinality flags.
- **Factless / accumulating / periodic snapshot fact:** event or coverage rows / a row updated through milestones / a state per entity per period.
- **Additive / semi-additive / non-additive:** summable across all / not across time / not at all.
- **Metric View:** a UC view defined in YAML (`WITH METRICS LANGUAGE YAML`), queried with `MEASURE()`. **LOD** = level-of-detail windows for percent-of-total.
- **TVF:** a SQL table-valued function exposed to Genie as a trusted asset.
- **Genie space / `serialized_space`:** the natural-language analytics room / its JSON config (v2).
- **Benchmarks / `sql_snippets`:** a question-plus-expected-SQL test suite / structured measure, filter and dimension definitions.
- **Lakehouse Monitoring / anomaly detection:** table profiling with custom metrics / schema-level freshness and completeness baselines.
- **AI/BI dashboard (`.lvdash.json`):** the Lakeview dashboard definition on a 12-column grid.
- **AppKit:** Databricks' TypeScript full-stack app SDK with plugins (analytics, Lakebase, Genie, files, serving).
- **Lakebase:** managed Postgres (Autoscaling `postgres_projects`, or provisioned instances). **Lakebase CDF** mirrors WAL changes to UC Delta.
- **OBO (on-behalf-of):** a user-scoped token (`x-forwarded-access-token`) that enforces the user's UC grants.
- **ResponsesAgent:** the MLflow agent interface (OpenAI Responses-compatible); the signature is auto-inferred.
- **MCP (managed):** Model Context Protocol servers for Genie, UC functions, AI Search and SQL.
- **AI Gateway:** a governed LLM and MCP proxy (usage tracking, inference tables, rate limits, guardrails, fallbacks).
- **MLflow tracing / UC OTEL:** spans per agent step; traces stored in Unity Catalog tables.
- **Scorer / judge / `make_judge`:** an evaluation function / an LLM-as-judge scorer / the factory for custom judges.
- **Failure shape:** the class of eval failure that decides the fix route (instruction, tool, retrieval, calibration, safety).
- **Prompt registry / alias:** versioned prompts in UC loaded as `prompts:/<fqn>@production`.
- **GEPA / `optimize_prompts`:** MLflow automated prompt optimisation.
- **Productized debt / `state_override`:** a deliberately shipped workaround with a removal predicate / an audited, expiring gate bypass.
