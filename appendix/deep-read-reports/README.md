# Deep-read reports (raw) and what I verified in them

Six long-form reports written by research sub-agents, one per repo, kept verbatim so the detail (file:line citations, SQL excerpts, glossaries) is available. My distilled, status-tagged notes are in [`repos/`](../../repos/); the case studies are in [`case-studies/`](../../case-studies/).

**How to read them.** The CONFIRMED / SUSPECTED labels inside each report are the agent's. Below is everything I **independently re-checked**, and how. A claim not listed here is the agent's reading, which I haven't verified.

| Report | Repo @ commit | Size |
|---|---|---|
| [`lakeflow_docs_samples.md`](lakeflow_docs_samples.md) | lakeflow_framework @ `0e8d0ca` (docs, samples, ADRs, spec format; the engine trace is my own, in [`repos/lakeflow_framework.md`](../../repos/lakeflow_framework.md)) | ~103 KB |
| [`vibe-coding-workshop-template.md`](vibe-coding-workshop-template.md) | vibe-coding-workshop-template @ `a26c6d0` | ~151 KB |
| [`consort.md`](consort.md) | consort @ `61b3a48` | ~102 KB |
| [`databricks-waf.md`](databricks-waf.md) | databricks-waf @ `e765461` | ~96 KB |
| [`technical-services-solutions.md`](technical-services-solutions.md) | technical-services-solutions @ `41fa465` | ~105 KB |
| [`starter-journey.md`](starter-journey.md) | starter-journey @ `ac21559` | ~160 KB |

## Claims I re-verified

"Source" = I read the cited lines myself. "Execution" = I ran code (evidence linked).

### lakeflow_docs_samples.md
| Claim | How |
|---|---|
| R1: legacy specs validated with `Draft7Validator`, which ignores `dependentSchemas` | Source + execution ([`lakeflow_validation_gaps.py`](../../case-studies/evidence/lakeflow_validation_gaps.py)). I count 9 uses in **6** schema files (the report says 7) |
| R3: docs say `pipeline.targetTableFiler`, engine reads `pipeline.targetTableFilter` | Source |
| R4: unknown `{tokens}` are left verbatim | Source (`substitution_manager.py:140-157`) |
| R22: `MAIN_SPEC_FILE_SUFFIX: tuple = ("_main.json")` is a str | Source + execution (same script) |
| Mandatory table properties win over per-table ones; pipeline substitutions win over framework ones | Source (`merge_dicts_recursively`, first argument wins) |
| Quarantine predicate `NOT((r1) AND (r2))`; flag vs table mode | Source + execution ([`verify_lakeflow_semantics.py`](../../case-studies/evidence/verify_lakeflow_semantics.py)) |
| Stream-static join reads the static side per micro-batch | Source (`delta_join.py:83`) + execution with the real classes ([`lakeflow_delta_join_real.py`](../../case-studies/evidence/lakeflow_delta_join_real.py)) |
| **Not re-verified:** commit-history claims (e.g. `d910588` pyyaml, `fca1b4e` validation), validator runs on doc examples, R5–R25 except those above | |

### vibe-coding-workshop-template.md
| Claim | How |
|---|---|
| "SCD Type 2" template only updates `record_updated_timestamp` | Source (`scd-type2-merge.py:57-64`) |
| `orderBy().dropDuplicates()` recommended as "✅ SIMPLE and RELIABLE", "avoid `row_number()`" | Source (`03-deduplication/SKILL.md:159-172`) |
| Merge template reads `scd_type` from `table_properties` and compares to `"scd2"`; canonical YAML has top-level `scd_type: 2` | Source |
| Eval threshold scale mismatch (0–1 thresholds vs 0–100 metrics) | Source (`03-scorers-and-judges/SKILL.md:322-347`) |
| `from pyspark.sql.functions import F, isnan` in a "✅ CORRECT" block | Source (`ml/00-ml-pipeline-setup/SKILL.md:304`) |
| DQ loader catches everything and returns `{}`; ML templates `notebook.exit("FAILED")` | Source (earlier in the study; [case 03](../../case-studies/03-fail-open-patterns.md)) |
| **Not re-verified:** `genie_gate.py` / `verify_agent_track_flow.py` execution results, skill counts, contradictions list (#24–#43) | |

### consort.md
| Claim | How |
|---|---|
| `readGreenFailure` deletes the failure record when the tree fingerprint changes; the repair cap is `MAX_REGRESSION_FIX_ATTEMPTS = 3` | Source (`supersession.ts:228-296`) |
| Deploy gate refuses unless `reachable === true` and `verify.passed === true` | Source (`gate-conformance-guard.ts:988-991`) |
| **Not re-verified:** the 5-round reproduction of the counter reset, the hermetic suite run, cost/turn measurements from `OPTIMIZE-INDEX.md` | |

### databricks-waf.md
| Claim | How |
|---|---|
| SCD2 filter-before-rank returned 6,136,941 "live" clusters where 135,177 existed; `history.ts` now refuses the shape | Source (statement comment + `history.ts`); mechanism reproduced ([`scd_filter_before_rank.py`](../../case-studies/evidence/scd_filter_before_rank.py)) |
| `is_serverless` flag alone understated $12,770 of $16,190 | Source (`cost_compute_mix.sql` comment) |
| Point-in-time price join on `usage_end_time` with `duplicate_price_matches` | Source; mechanism reproduced ([`price_join_demo.py`](../../case-studies/evidence/price_join_demo.py)) |
| `AND NOT (…)` filter kept 0 of 6,969 statements; fixed with `CASE` | Source (`workload_sql_paths.sql`) |
| Column names used in my [system-tables cheatsheet](../../cheatsheets/system-tables-best-practice-checks.md) | Source (the statements themselves) |
| **Not re-verified:** §9 findings 1–16 (resolver logic), test-suite run, scale fixtures | |

### technical-services-solutions.md
| Claim | How |
|---|---|
| Root `.gitignore` `*conf*.json` ignores `tsconfig.json` | Execution (`git check-ignore -v`) |
| Fuzzy column "fix" substitutes a different real column | Execution ([`fuzzy_column_match.py`](../../case-studies/evidence/fuzzy_column_match.py)); I also found `customer_name → customer_id`, which the report doesn't list |
| Aggregate-promotion rewrite drops `HAVING`/`ORDER BY`, keeps `LIMIT` | Source (`converter.py:2703-2719`); the sqlglot reproduction is the agent's |
| **Not re-verified:** Terraform findings (R1–R28), ABAC, Lakeflow Connect, OrderFlow app findings except R63 | |

### starter-journey.md
| Claim | How |
|---|---|
| Freshness check never flags a future-dated (typo) row | Execution (a `2062-09-24` row was not listed; a genuinely stale row was) |
| The script crashes with a `ValueError` when `--csv` is outside the repo and something is stale | Execution (same run) |
| Cost query uses a containment price join with an INNER JOIN | Source (`tag-compute-and-jobs.mdx`); mechanism reproduced ([case 08](../../case-studies/08-price-join-containment-vs-point-in-time.md)) |
| **Not re-verified:** the link crawl (25 of 62 pages skipped), doc/style findings G1–G35 other than the above | |
