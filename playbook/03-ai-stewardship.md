# 03. AI stewardship: using the Databricks Assistant well, and catching it when it's wrong

> **What's being assessed:** "How effectively do you use the Databricks Assistant? Can you write good prompts, evaluate the Assistant's output, and catch when it's wrong?"

Everything here comes from three sources: what the six repos build around AI (consort's deterministic harness, vibe-coding's skills and gates, starter-journey's prompt + checklist + fallback pattern, WAF's list of system-table traps), the AI mistakes I found in those repos' own instructions and generated code, and the checks I ran myself. I have not run the Databricks Assistant in this environment. Where a claim about the Assistant's environment comes from a repo's documentation, I say so.

## 1. The stance

- **The Assistant is a fast, capable junior who has never seen this codebase or this data.** My job is to supply context and constraints, and to verify.
- **Discipline lives in checks, not in the prompt.** consort's lesson: the model never decides what happens next or whether it's done; code and tests do. In a notebook that means: I decide the steps, the Assistant drafts one step, and a check decides whether it's right.
- **"Exists" is not "works", and "runs" is not "correct".** A query that executes can still fan out, drop NULLs or pick an arbitrary row.

## 2. The prompt skeleton

Distilled from the best prompts in the repos (vibe-coding PR-9/PR-10, starter-journey's metric-view prompt, the AI Platform Kit prompt):

```
GOAL      one sentence, including the business definition ("net revenue in USD, by UTC day")
INPUTS    fully qualified tables + their grain + key columns   (paste DESCRIBE output if the Assistant can't see it)
OUTPUT    exact column names, types, grain ("one row per order_date x region")
RULES     the non-negotiables: dedupe on order_id by updated_at desc with tie-break; LEFT join customers;
          exclude cancelled (NULL status counts as not cancelled); DECIMAL money
SCOPE     do X only. Do NOT: create tables, deploy, touch prod            (+ why)
CHECKS    show me: the row count before/after each join, and the query plan
DONE      the checklist I'll verify, e.g. "total reconciles to the silver sum"
```

A real example, the kind I'd type during the interview:

> Using `main.shop.orders_silver` (one row per `order_id`) and `main.shop.dim_customer` (one row per `customer_id`, SCD1), write PySpark that produces daily revenue by region: `order_date DATE, region STRING, revenue_usd DECIMAL(18,2)`. Revenue excludes status `'cancelled'`; treat NULL status as not cancelled. LEFT join customers and label missing regions `'Unknown'`. Bucket days in UTC. Don't write any tables. After the code, list every assumption you made.

Why it works: grain, contract, the NULL rule and the join type are stated; it asks for **assumptions**, which is where the Assistant's guesses become visible.

## 3. Ground it: "Extract, Don't Generate"

The single most valuable rule from vibe-coding-workshop-template: **every table, column and enum value comes from the catalog, never from model memory.**

- Before generating: `DESCRIBE TABLE`, `SELECT DISTINCT status`, `information_schema.columns`. Pin that inventory in the conversation; any name outside it is an error.
- Watch for **domain-knowledge injection:** `status IN ('pending','confirmed')` when the data holds `'PEND','CONF'`. Every literal in an `IN (...)` should trace to a `SELECT DISTINCT`.
- Watch for **PRD names instead of live names:** `price` in the spec, `base_price` in the table.

## 4. Evaluate the output at three levels

| Level | What I check | How |
|---|---|---|
| **Static** (read it) | Names exist; grain preserved per step; NULL behaviour; deterministic dedupe; join types; time zone; money types | The [review checklist](02-code-stewardship.md#4-review-checklist-for-a-teammates-or-the-assistants-pyspark--sql) and the four questions per step |
| **Execution** (run it) | It runs on a sample; the plan has the shuffles and joins I expect; row counts per step | `display()` on a `LIMIT` sample; `explain("formatted")`; the row-count ledger |
| **Semantic** (is it right?) | Invariants hold; the number reconciles | one row per key; no NULL keys; totals preserved across joins; compare to an independent calculation |

**Say:** "The Assistant's query runs, but the customer table has two rows for C002, so the join doubles C002's revenue. I'll dedupe the dimension first and add a row-count assertion around the join."

## 5. Red flags: stop and challenge when you see…

- `orderBy(...).dropDuplicates(...)` or `first()` after a shuffle to pick "the latest" (arbitrary survivor)
- `!= 'x'`, `NOT (…)`, `NOT IN (subquery)` on nullable columns
- an INNER join to a dimension, or a join whose dimension key uniqueness hasn't been checked
- `when(...)` chains without `otherwise`, `count(col)` used as a row count, a `Window` without `partitionBy`
- literal lists of table or column names, or `IN (...)` values with no `SELECT DISTINCT` behind them
- API names, config keys or YAML keys you don't recognise (check the docs)
- `except Exception: pass/print`, `notebook.exit("FAILED")`, `return {}` in error paths
- "fixes" that change meaning to make an error go away (renaming a column to the nearest match, dropping `HAVING`, loosening a filter or an assertion)
- `CREATE OR REPLACE TABLE` on a table with history; target-less deploys; ad-hoc DDL instead of the bundle
- claims of state it didn't observe ("the job succeeded", "the table exists") with no run URL or query result
- the same fix retried with small variations

## 6. The AI-error catalogue (found in these repos' own AI guidance or AI-built code)

Each of these was produced or recommended by an AI-oriented artifact (a skill, a prompt pack, an AI app) and would be copied faithfully by any assistant that trusted it.

| Error | Where found | Correct pattern | Status |
|---|---|---|---|
| `orderBy().dropDuplicates()` called "✅ SIMPLE and RELIABLE"; "avoid `row_number()`" | vibe-coding dedup skill | `row_number()` over the merge key with a deterministic tie-break | CONFIRMED (read); kata B2 |
| "SCD Type 2" merge that only updates a timestamp | vibe-coding merge template | close the current row, insert the new version ([Ex02](../exercises/ex02_scd2_merge/WALKTHROUGH.md)) | CONFIRMED (read) |
| Merge template reads `scd_type` from the wrong YAML level: no merges, green job | vibe-coding Gold template | validate config shape; fail on empty work | CONFIRMED (read) |
| Eval gate compares 0–100 scores to 0–1 thresholds, so every gate passes | vibe-coding GenAI SDLC skill | one scale; assert the gate can fail | CONFIRMED (read) |
| `from pyspark.sql.functions import F` in a "✅ CORRECT" block | vibe-coding ML skill | `import pyspark.sql.functions as F` | CONFIRMED (read) |
| Streaming `dropDuplicates` without a watermark marked "MANDATORY" | vibe-coding Silver skill | `withWatermark` + `dropDuplicatesWithinWatermark` | SUSPECTED at scale |
| Fuzzy column "repair": `unit_cost → unit_count`, `customer_name → customer_id` | PBI → AI/BI converter | fail and report; never substitute a different column | CONFIRMED by execution |
| Top-N rewrite drops `HAVING`/`ORDER BY`, keeps `LIMIT` | PBI converter | reject the rewrite; test with adversarial SQL | CONFIRMED (deep-read repro) |
| DAX `DATEADD(-1, YEAR)` → "last 12 months from today" | PBI converter's DAX cookbook | numeric reconciliation against the source | CONFIRMED (deep-read) |
| AI skill generates a legacy spec format and wrong enum values; its validator rejects valid specs | lakeflow `dataflowspec_builder` skill | validate with the framework's real schema | CONFIRMED (deep-read) |
| Containment price join with an INNER JOIN | starter-journey cost query (not AI-specific, but it's what an assistant reproduces) | point-in-time LEFT join + coverage | CONFIRMED ([case 08](../case-studies/08-price-join-containment-vs-point-in-time.md)) |
| System-table traps: filter before rank; `is_serverless` flag alone ($12,770 understated on $16,190); adding DBUs + DSUs + GB; `NOT (tag = …)` with NULL tags | WAF's "where an AI would go wrong" (from its own bugs) | [system-tables cheatsheet](../cheatsheets/system-tables-best-practice-checks.md) | CONFIRMED at source (WAF comments); filter-before-rank reproduced |

**The lesson that surprised me:** grounding an assistant in curated instructions only moves the trust problem into the instructions. The vibe-coding skills, the lakeflow skill and the PBI converter's knowledge docs all contain errors that an assistant would reproduce faithfully. **The defence is the same as for generated code: tests that check behaviour, not the presence of wording.** (`genie_gate.py`'s substring checks prove the guardrail text exists, not that it works.)

## 7. Patterns from the repos that make AI output trustworthy

| Pattern | Source | How I'd use it with the Assistant |
|---|---|---|
| **Prompt + acceptance checklist + deterministic fallback** | starter-journey | Ask for the query; check it against my 4-point list; keep a hand-written version for the key number |
| **Reconcile before anyone sees it** | starter-journey metric views | Generated metric = known-good query on the same filters |
| **One unit of work per conversation; state in files, not chat** | vibe-coding | New thread per stage; the design decisions live in a file I paste or reference |
| **Announce expected failures and negative scope** | vibe-coding apps prompts | "The first run will fail with TABLE_OR_VIEW_NOT_FOUND until the setup job runs; don't try to fix that" |
| **Ask, don't guess; plan → approve → apply → verify** | AI Platform Kit prompt | For anything with side effects (DDL, deploys, Terraform) |
| **One informed retry, then escalate** | consort expectation ledger | "The output is missing X. Try once more with that constraint", then write it myself |
| **Classify the failure before asking for a fix** | consort | An auth or permission error is not a code bug; don't let the Assistant rewrite code for it |
| **Change approach after two same-class failures** | vibe-coding autonomous-ops | Stop iterating variants; read the docs or the plan instead |
| **Author ≠ judge** | consort Navigator/Driver | Review the Assistant's diff specifically for loosened assertions, broadened `except`, relaxed filters |

## 8. The Assistant's environment (Genie Code), as documented in vibe-coding-workshop-template

These come from the repo's `genie-code-environment` skill, which tags each claim with its probe evidence. I haven't verified them myself, so treat them as field notes to confirm:
- Pre-authenticated; runs on serverless, and the first code execution can take a few minutes of cold start.
- Tools are **surface-scoped** to the current page (notebook, SQL editor, dashboard, bundle folder): "navigate to the right surface first". "Never conclude 'impossible' from one path or one page."
- Bundle deploys need `--target dev` and are run from the bundle editor; bundles are recognised only inside a git working tree.
- `AGENTS.md` is read once and does not carry across threads, so name skill files by full path in each prompt.
- "Don't fabricate state — report unverified facts as `unknown`."
- Files written through one path may not be immediately visible through another (verify with `os.path.exists`).

## 9. When the Assistant is wrong: the recovery loop

1. **Stop generating.** Name the gap precisely ("it assumed `order_id` is unique; it isn't").
2. **Run discovery** (`DESCRIBE`, `SELECT DISTINCT`, a count) and put the facts into the conversation.
3. **One informed retry** with the new constraint. If it's still wrong, write that step myself.
4. **Grep for the same mistake** in the rest of the generated code (the "same-class fix" rule).
5. **Capture the lesson** as a test or a checklist item, so the next generation is checked automatically.

## 10. How I'd narrate Assistant use in the interview

- "I'll ask the Assistant for the window syntax because I don't want to spend time on it. The part I'll check is the ordering: it needs a tie-break, or the dedupe isn't deterministic."
- "It used `!= 'cancelled'`. That drops orders with a NULL status. I'll ask the business whether NULL means 'not yet set'; if so, I'll use `NOT (status <=> 'cancelled')`."
- "It suggested broadcasting the fact table. The dimension is the small side; I'll check the plan to see what Spark actually chose."
- "It says the code is correct. I'll run the row-count ledger before I believe that."
