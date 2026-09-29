# vibe-coding-workshop-template: AI-assisted delivery of governed data products

**Repo:** `databricks-solutions/vibe-coding-workshop-template` @ `a26c6d0`. 93 `SKILL.md` files (the docs quote four different counts: 44, 45, 55 and 77).
**How I studied it:** deep-read of the skill system, prompts and scripts. I spot-checked the headline bugs at source and built one of them (the `orderBy().dropDuplicates()` recommendation) into my debug kata. The raw report is in [`appendix/deep-read-reports/vibe-coding-workshop-template.md`](../appendix/deep-read-reports/vibe-coding-workshop-template.md).

**Why this repo matters most for the interview:** it is the best available example of *AI stewardship as engineering*: how to make an assistant reliable with context, gates and evidence. It also shows, in its own bugs, what happens when the instructions themselves are wrong.

## 1. What it is, for a customer

A template for building governed data products with a coding assistant (Cursor, Claude Code, or Genie Code, the Databricks Assistant's agent mode). Instead of trusting the model to remember how to build a lakehouse, it hands the model ~90 versioned instruction packs ("skills") encoding Databricks practice and field failure modes.

The flow is **design-first**, from a metadata-only export (`information_schema.columns`), so **the customer shares metadata, not data**:

1. Gold design → 2. Bronze → 3. Silver → 4. Gold implementation → 5. Planning → 6. Semantic layer (metric views, TVFs, Genie) → 7. Observability → 8. ML → 9. GenAI agents.

Each stage is **one prompt in one fresh conversation**, and everything ships as a Databricks Asset Bundle. A second path builds a full-stack Databricks App (AppKit + Lakebase Postgres), optionally fronting an agent with on-behalf-of-user auth.

The less-advertised value: it turns tacit expertise into checklists an AI can follow and a human can audit.

## 2. How the skill system works

```
user prompt → AGENTS.md (keyword routing) → stage orchestrator 00-* → workers 01-*, loaded just-in-time
             Phase k: read worker → do work → write files → keep "Notes to Carry Forward" → discard worker
             State crosses conversations ON DISK: Gold YAML, DESIGN_DECISIONS.md, plans/manifests/*.yaml,
             .vibecoding-state.md (gates, captured IDs, per-step log)
```

**SKILL.md anatomy:** frontmatter (`name`, `description` with trigger phrases), then critical rules and links; `references/` loaded on demand; `scripts/` run as black boxes; `assets/templates/` copied. Workers end with **Notes to Carry Forward** and **Next Step**. Orchestrators end with a **Skill Usage Summary** of what was actually read.

**Why one conversation per stage:**
- Context is finite and attention decays. Just-in-time loading keeps the governing rules near the end of the context. The authors observed "format divergence" when all workers were batch-loaded up front.
- **Files, not chat, carry state.** "The chat summary is NOT the state store." After a reset or compaction, the model re-derives facts from files instead of trusting its own summary.
- Independent stages can run in parallel.

## 3. Patterns worth stealing (the AI-stewardship core)

| Pattern | What it does | Where |
|---|---|---|
| **Extract, Don't Generate** | Every table, column and enum value comes from YAML, `DESCRIBE`, `SELECT DISTINCT` or `information_schema`, never from model memory. The model must print a Phase-0 block listing the files it will extract from and the values it will not guess | `skills/databricks-expert-agent/SKILL.md:120-143` |
| **Rationalization red flags** | A pre-mortem table: "The prompt already has everything I need" → "Prompt completeness does not equal project truth" | same file `:36-47` |
| **Proof-of-reading gate** | "List the key pattern from each skill. If you cannot, you have not read it" | semantic-layer orchestrator `:132-145` |
| **Self-consistency ≠ correctness** | YAML, ERD and lineage generated in one session agree with *each other*. Only a cross-check against real Silver schemas tests them against *reality* | gold design `:481` |
| **Bounded autonomy** | Validate → deploy → run → read the **task-level** `run_id` → match known error signatures → fix the *source* → at most 3 loops → escalate with run IDs, fixes tried and a hypothesis. "Same-class fix rule": grep sibling files for the same bug | autonomous-operations skill |
| **Announce expected failures** | "The first deploy WILL show the app in CRASHED state. This is expected", so the model doesn't debug-spiral | apps Instructions Step 3 |
| **Negative scope with reasons** | "Do NOT deploy in this step: deployment happens in Step 5" | same |
| **Explicit opt-in, never inferred** | Workshop mode only on the exact phrase `planning_mode: workshop`, not "small" or "demo". The mode is echoed on the first line | planning skill `:68-77` |
| **Blocked ≠ impossible; don't fabricate state** | Try the next execution path; report unverified facts as `unknown`; "exists" is not "works" | `skills/genie-code-environment/SKILL.md:42-53` |
| **Cardinality gate before trusting a join** | `SELECT key, count(*) … HAVING count > 1` must return 0 on the dimension | metric-views skill `:519-530` |
| **Fail-loud validator before a fragile API** | `_assert_sql_arrays` raises on the first invariant violation (sorted arrays, a concrete warehouse id) before a Genie PATCH | Genie API skill `:156-200` |
| **Hybrid authoring invariant** | "persisted file + live matches file + bundle validates + job ran once in dev". An orphan or drift is the regression | genie-code-environment `:265-270` |
| **`bundle run` does not sync** | Every edit → `bundle deploy` → `bundle run`. Never hotfix under `/Workspace/.bundle/...` | DAB skill `:565-580` |
| **Failure-shape router for evals** | Classify each failed eval gate (instruction / tool / retrieval / scorer calibration / safety) before fixing. "Never route an L1 failure to prompt iteration" | GenAI SDLC eval-runs skill |

## 4. What I found (status-tagged)

The irony worth telling: **a repo about catching AI errors contains the same errors in its own instructions.** An assistant that follows these skills faithfully reproduces them.

| # | Finding | Status | Impact |
|---|---|---|---|
| 1 | The "SCD Type 2" merge template only updates `record_updated_timestamp` on match. It never expires the current row or inserts a new version | CONFIRMED (read at `02-merge-patterns/assets/templates/scd-type2-merge.py:57-64`) | History silently lost. [Exercise 02](../exercises/ex02_scd2_merge/WALKTHROUGH.md) implements it correctly |
| 2 | `orderBy(ts.desc()).dropDuplicates(keys)` recommended as "✅ SIMPLE and RELIABLE", with "Avoid: Window functions with `row_number()`" | CONFIRMED (read `03-deduplication/SKILL.md:159-172`); the semantics are standard Spark | Arbitrary survivor after the shuffle. Bug B2 in [my kata](../exercises/ex05_debug_kata/DEBUGGING_LOG.md) |
| 3 | The merge template reads `scd_type`/`entity_type` from `table_properties`, but the canonical YAML puts `scd_type: 2` at top level and compares to `"scd2"` | CONFIRMED (read) | Empty dimension/fact dicts, **no merges, green job** |
| 4 | DQ-rules loader catches every exception and returns `{}` | CONFIRMED (read) | `expect_all_or_drop({})` enforces nothing ([case 03](../case-studies/03-fail-open-patterns.md)) |
| 5 | ML templates call `dbutils.notebook.exit("FAILED: …")` inside `except` | CONFIRMED (pattern) | The task reports SUCCEEDED; downstream tasks run |
| 6 | Eval gate example: thresholds on a 0–1 scale compared against metrics converted to 0–100 | CONFIRMED (read `03-scorers-and-judges/SKILL.md:322-347`) | 70 ≥ 0.95, so **every gate passes** |
| 7 | `from pyspark.sql.functions import F, isnan` in a "✅ CORRECT" block | CONFIRMED (read `ml/00-ml-pipeline-setup/SKILL.md:304`) | ImportError |
| 8 | Gold setup uses `CREATE OR REPLACE TABLE` | CONFIRMED (per deep-read) | Re-running setup drops Gold data, SCD2 history and constraints |
| 9 | Streaming `dropDuplicates` without a watermark is "MANDATORY"; zero `watermark` mentions in the repo | SUSPECTED at scale (standard streaming semantics) | State grows forever. Use `dropDuplicatesWithinWatermark` |
| 10 | CDF is claimed ("Silver ingests using Change Data Feed"), but nothing reads it (`readChangeFeed`, AUTO CDC) | CONFIRMED gap (per deep-read) | Updates in Bronze break append-only Silver streams |
| 11 | `genie_gate.py`: six prompt-tree checks print SKIP and return True without the private tree; at HEAD the gate FAILS on its own ratchet | CONFIRMED by execution (deep-read) | A fail-open regression gate |
| 12 | Contradictions between skills: manifest-missing behaviour, TVF parameter types, semantic build order, metric-view YAML shape, `sys.path` rules, surrogate key type, NULL FK policy | CONFIRMED (per deep-read, 20 listed) | An AI following one skill violates another |

## 5. How it scales (and where it doesn't)

- It is **demo- and workshop-oriented**: Bronze is "NOT for production ingestion" (no Auto Loader or Lakeflow Connect), streaming dedup has no watermark, feedback dedup is an in-memory `Map`.
- For production, add incremental ingestion (Auto Loader / Lakeflow Connect), CDF or AUTO CDC between layers, watermarks, incremental Gold MERGEs over change windows, Genie spaces split by domain (~25 assets), and AI Gateway in front of LLMs.
- **Context is the scaling limit of the method itself.** The navigator claims all skills are "< 2K tokens"; 32+ skills exceed 500 lines and the dashboards skill is ~20K tokens.

## 6. How I'd explain it

- **Executive:** "It turns weeks of expert data engineering into a guided, auditable process that produces a governed data product: star schema, quality-checked pipelines, trusted KPIs, a natural-language analytics space. Guardrails catch the classic AI mistakes before production, and everything is versioned for promotion."
- **Engineer:** "Each stage is one prompt in a fresh thread, loading only that stage's instructions. Names come from the catalog, never from memory. State lives in files. Every generated artefact passes a validator, a dev deploy and a semantic check before the next stage."
- **Internal stakeholder:** "The method is excellent, and the content needs QA: the SCD2 and dedup templates are wrong, several skills contradict each other, and the regression gate is fail-open on public clones. I'd fix those before using it with customers."

## 7. Interview angles

1. **"How do you use the Databricks Assistant effectively?"** Treat it like a capable junior who hasn't seen the codebase: one unit of work per thread, governing instructions and input files by path, hard constraints, a verifiable definition of done, inspect-before-write, and deploy through the bundle. See [playbook/03](../playbook/03-ai-stewardship.md).
2. **"How do you know when it's wrong?"** Provenance (every name traces to a source), execution evidence (run URL, task output, `event_log` expectation counts, not "done"), reality over self-consistency, semantic checks (PK duplicates, orphan FKs, one current row per SCD2 key, row counts across joins).
3. **"What's wrong with `orderBy().dropDuplicates()`?"** The sort isn't preserved through the aggregation shuffle; the survivor is arbitrary. Use `row_number()` over the merge key with a deterministic tiebreak.
4. **"Why one conversation per stage?"** Finite attention, externalised state, parallel stages.
5. **"Metric views vs TVFs vs tables for Genie?"** Metric views first (governed measures, correct re-aggregation), TVFs for parameterised multi-step logic, tables last; 10–25 assets; ≥10 benchmarks with pinned-date SQL.

## 8. AI-stewardship lesson

**The skills themselves can be wrong.** Grounding the model in instructions only moves the trust problem into the instructions. The defence is the same as for generated code: tests that check *behaviour* (my kata's B2 structural test, an SCD2 invariant test), not the presence of wording (`genie_gate.py`'s substring checks prove the guardrail text exists, not that it works).
