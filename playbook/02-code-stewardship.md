# 02. Code stewardship: generating code, explaining it under the hood, and reading code you didn't write

> **What's being assessed:** "Can you generate working code and, more importantly, explain exactly what it's doing under the hood? Can you read and reason about code you didn't write?"

## 1. The method I used to read six unfamiliar repos

The same method works on a customer's codebase on day one.

| Step | What I do | Example from this work |
|---|---|---|
| 1. Orient | README claims, entry points, build and test commands, **pinned environment** (lockfile, runtime version) | lakeflow: one generic notebook calls `DLTPipelineBuilder.initialize_pipeline()` |
| 2. Run their tests **in their environment** | Reproduce green before judging red | 32 collection errors with plain pyspark → the repo's hash-pinned lockfile → **396 passed** |
| 3. Trace one execution end to end | Entry → state → effects, following one real input | consort: `runDriver` loop → pure `nextTransition` → effects. WAF: `POST /api/scan` → collectors → resolvers → score |
| 4. Find the **decisions** | Where does the code choose? Routing, precedence, merge order, NULL handling, error handling, parsing | lakeflow: join order comes from a regex over the condition text ([case 07](../case-studies/07-lakeflow-delta-join-alias-parsing.md)) |
| 5. Hypothesis → cheapest decisive test | Verbatim function in isolation; real classes with stubs for platform-only modules; a scratch test using the repo's fixtures | [`lakeflow_delta_join_real.py`](../case-studies/evidence/lakeflow_delta_join_real.py) runs the framework's real `SourceDeltaJoin` on OSS Spark |
| 6. Status-tag every claim | CONFIRMED / SUSPECTED / REFUTED, with evidence links | [case-studies/README](../case-studies/README.md) |
| 7. Explain at three levels | Executive, engineer, internal stakeholder | every `repos/*.md` |

**Rules I hold myself to:**
- **Trust the executable path over comments and docs.** consort's comments say telemetry defaults to a no-op; the code arms a real endpoint. lakeflow's docs say `targetTableFiler`; the code reads `targetTableFilter`.
- **Read helpers' bodies, not their names.** `merge_dicts_recursively(d1, d2)` lets the *first* argument win; I assumed the opposite once ([case 06](../case-studies/06-near-misses-and-false-positives.md) #2).
- **Verify tool output before believing a finding.** My `wc -l` hid the last line of a file with no trailing newline, and I nearly reported a missing `return`.

## 2. Smells to look for in data code (and why)

| Smell | Why it bites | Seen in |
|---|---|---|
| **Positional semantics:** `union`, CSV without a header, `select` by index | Columns are matched by position, not name | kata B1 (store quantity summed as money) |
| **Silent defaults:** `when` without `otherwise`, `count(col)`, `Window` without `partitionBy`, implicit session time zone, default inner join | The default is rarely the business rule | kata B3, B6, B7, B8 |
| **NULL in predicates:** `!=`, `NOT (…)`, `NOT IN` with a NULL | Three-valued logic drops or misroutes rows | lakeflow quarantine, WAF filter, kata B4 |
| **Non-deterministic dedupe:** `orderBy().dropDuplicates()`, `first()` after a shuffle | The survivor can change between runs | vibe-coding dedup skill, kata B2 |
| **Swallowed errors:** `except Exception: print`, `notebook.exit("FAILED")`, `return {}`, `|| true`, SKIP counted as PASS | Loud local failure becomes a quiet distant one | [case 03](../case-studies/03-fail-open-patterns.md) (7 instances) |
| **"Repair" of generated output** | Fuzzy fixes change meaning | PBI converter: `unit_cost → unit_count` |
| **Parsing code or SQL with a regex** | Literals and nested names look like identifiers | lakeflow join aliases (`1.5` → alias `'1'`) |
| **Stringly-typed config keys** | A typo is silently ignored, so defaults apply | `targetTableFiler`; unknown `{tokens}` left verbatim |
| **`("x")` meant as a tuple** | It's a string; `for s in ("x")` iterates characters | lakeflow `MAIN_SPEC_FILE_SUFFIX` |
| **Validator that doesn't validate** | Draft 7 ignores `dependentSchemas`; a missing schema path meant `errors = []` | lakeflow (R1, R2) |
| **Shared mutable config** | A callee changes the caller's object | lakeflow `read_config.mode` |
| **Reads with side effects** | Deriving state changes state | consort `readGreenFailure` deletes files |
| **Filter before a window over a lifecycle column** | Resurrects deleted objects | WAF: 45× live clusters |
| **Lazy reference to a table that the job then writes** | "Before" is evaluated after | [case 04](../case-studies/04-lazy-evaluation-meets-mutable-tables.md) |

Grep starters: `except Exception`, `except:`, `dropDuplicates`, `.first()`, `union(`, `when(` without `otherwise`, `!= '`, `NOT IN`, `Window.orderBy`, `from_utc_timestamp`, `inferSchema`, `collect()`, `toPandas()`, `udf(`, `notebook.exit`, `|| true`.

## 3. Explaining what code does *under the hood*

The explanations interviewers probe, in the words I'd use:

- **Lazy evaluation:** "Transformations build a logical plan; nothing runs until an action (`count`, `collect`, `write`, `display`). The optimizer (Catalyst) rewrites the whole plan (pushing filters into the scan, pruning columns, choosing join strategies) and cuts it into stages at shuffle boundaries. That's also why a DataFrame is a recipe, not a snapshot."
- **Driver vs executors:** "The driver plans and coordinates; executors run tasks, one per partition. `collect()` and `toPandas()` pull everything to one machine. Python UDFs run in separate Python worker processes on each executor, so the rows are serialised across (Arrow for pandas UDFs)."
- **Shuffles:** "A `groupBy`, `join` (unless one side is broadcast), `distinct`, window or `repartition` needs rows with the same key on the same executor. That's an Exchange: written to local disk, sent over the network. Most performance work is removing, shrinking or balancing shuffles."
- **Delta MERGE:** "It joins the source to the target to find which files contain matching rows, writes new versions of those files (or deletion vectors, where enabled), and commits a new table version atomically. If two source rows match the same target row, it refuses (`DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`), which is why the source must be deduplicated on the merge key first. Concurrent writers are resolved optimistically: a conflicting commit fails and retries."
- **Streaming checkpoint:** "The checkpoint records which source versions or files each micro-batch processed, plus operator state. Restarting resumes from it, which is what makes processing exactly-once into Delta. Change the query in incompatible ways and the checkpoint no longer applies."
- **SDP / AUTO CDC:** "I declare the target and its source; the platform manages the checkpoint per flow, orders events per key by `sequence_by`, applies SCD1 or SCD2, and records expectation metrics in the event log. The hand-written equivalent is a sequenced MERGE, which is what my Exercise 01 does, so I can explain both."
- **Time travel:** "Every commit is a version in the transaction log. `versionAsOf` reads an older snapshot, as long as VACUUM hasn't removed its files."

## 4. Review checklist for a teammate's (or the Assistant's) PySpark / SQL

- [ ] Every table and column name exists (checked against `DESCRIBE`, not memory)
- [ ] Grain stated for inputs and output; every join preserves the fact grain (row count asserted)
- [ ] NULL behaviour of every filter and join key is intended
- [ ] Dedupe is deterministic (full tie-break) and on the merge key
- [ ] Time zone and currency explicit; money in DECIMAL
- [ ] No `collect()`/`toPandas()` on unbounded data; no Python UDF where a built-in exists
- [ ] Idempotent on rerun (MERGE keys, ingestion ledger or checkpoint)
- [ ] Errors fail the job; quarantine carries reasons
- [ ] Tests cover the invariants, and at least one test fails without the fix
- [ ] The plan (`explain`) has the shuffles and join strategies I expect

## 5. Writing code other people can steward

- **One responsibility per function**, `DataFrame → DataFrame`, pure where possible. Easy to test on five rows, easy to move into an SDP pipeline.
- **Explicit schemas and named rules.** DQ rules as data (`DQ_RULES = {"amount_positive": "amount > 0", …}`), not buried in code.
- **Invariants as assertions:** `assert_same_row_count(before, after, "customer join")` fails loudly at the step that broke.
- **Tests that name the bug they prevent**, such as `test_naive_join_to_undeduplicated_dimension_inflates_revenue`.
- **Comments say *why*,** especially for non-obvious choices ("event time beats arrival time: this is why AUTO CDC has `sequence_by`").
- **A walkthrough next to the code:** what it does, how it executes, how it scales, how to explain it. Every exercise here has one.
