# consort: a deterministic harness around AI coding agents, on Lakebase branches

**Repo:** `databricks-solutions/consort` @ `61b3a48` (package `0.3.102`). TypeScript. Not a data-engineering repo: it builds transactional app backends on **Lakebase** (Databricks serverless Postgres).
**How I studied it:** a deep-read that traced one increment through the code and ran the hermetic suite (4292 passed, 59 skipped, 3 failed for environment reasons). I spot-checked the key claims at source. The raw report is in [`appendix/deep-read-reports/consort.md`](../appendix/deep-read-reports/consort.md).

**Why it matters for the interview:** it is the clearest example of *where discipline lives*. An LLM's "done" is never trusted; code decides what happens next and checks every claim. The same principles apply to working with the Databricks Assistant on data code.

## 1. What it is, for a customer

AI coding agents write code fast, but on their own they declare work "done" with no test behind it, drift from the request, weaken tests to get to green, and lose the plan when their context resets. Mocked or shared staging databases make it worse.

Consort runs a team of role agents (Product Owner, Spec Author, Architect Reviewer, DBA, Test Strategist, UX Designer, and a Navigator/Driver pair) **inside a deterministic, code-defined state machine**:
- the design lane is spec-first; the build lane is test-driven (RED → GREEN → REFACTOR);
- every story is built on its own **copy-on-write Lakebase branch** paired with a git branch;
- "green" means **the orchestrator itself** ran the real test suite against a throwaway database branch;
- humans approve at gates that **fail closed**.

## 2. How it executes

```
consort-drive loop (orchestrator-run.ts:220)
  state  = readState()            # re-derived from .consort/ files every iteration, no cache
  ledger.reconcile(state)         # did the last role deliver its artifact? one informed retry, then ProtocolViolationError
  action = nextTransition(state)  # PURE function: no I/O, no model
  done / raise-to-hil / stall check (same action twice in a row = DriverStalledError)
  perform(action)                 # spawn `claude -p --agent <role>` for bounded judgment turns, or run a CLI step
```

- **Agents change state only by writing files**, which are re-read and validated. Agents cannot emit gate events.
- **Honest GREEN:** start the app, fork an ephemeral Lakebase branch (TTL 3600 s, deleted in `finally`), run the **full** suite, then deterministic post-pass gates (migration immutability, layering, test smells) that can each turn a pass into a fail. An earlier version "hardcoded `passed:true`", which is why this exists.
- **Bounded self-heal:** assess → repair up to 3 rounds; reflect → revise up to 4 laps *with a check that the test list actually changed*; one handoff retry; one-shot deploy re-verify.
- **Promotion:** accept merges code and applies migrations to the feature's DB branch → PR → CI on a `ci-pr-N` Lakebase branch (migrate, test, schema diff) → promote gate → merge → `merge.yml` snapshots and migrates the tier.

**Why routing is code, not an LLM:** the routing was already deterministic. Running it through an LLM cost ~99 s per decision, dropped log events and invited drift. Code makes it instant, testable, resumable, and impossible for the agent to argue with.

## 3. Patterns worth stealing

| Pattern | The general lesson |
|---|---|
| **Pure brain + effects seam** (`nextTransition` + injected `DriveEffects`) | Decide in a pure function; act through an interface; test both hermetically. A fake-world loop test drives a whole feature |
| **Stall detector** | If an effect didn't change the state, the next iteration derives the same action. Fail loudly instead of spinning |
| **Handoff contract with exactly one informed retry** | "Prose describing the artifact is NOT the artifact." Say precisely what's missing, retry once, then escalate |
| **Verify on a disposable branch; always delete; TTL as backstop** | The Databricks version: clone a table (shallow clone / a dev schema), run the test, drop the clone |
| **Fail-closed gate that checks evidence, not file existence** | Deploy approval requires `reachable === true && verify.passed === true`. "An approve cannot clear stale failed evidence" |
| **Pin the agent to exact IDs** | "EXACTLY these N items, ONLY these; do NOT add or drop items". Prompt and recorder read the same list |
| **Classify failure signatures before routing a fix** | Expired auth or a DB provisioning fault must not go to a code-repair agent; it can never converge |
| **Normalised hashing of artifacts** | Ignore whitespace churn, catch real edits. Too strict and users disable the gate; too loose and edits slip through |
| **Idempotent escalations keyed by a deterministic ID**, with their own `how_to_resolve` | Re-running doesn't duplicate; the record tells the human what to do |
| **Deterministic gates before LLM gates** | Cheap structural checks first; LLM laps are slow and expensive |
| **Evaluate prompt/model changes against recorded references with a fixed judge, and keep outputs** | The team once applied judge-less "winners" and logged it as a violation to redo |

## 4. What I found (status-tagged)

| # | Finding | Status |
|---|---|---|
| 1 | **The repair-loop bound can silently reset.** `readGreenFailure` *deletes* the failure record when the git-status fingerprint changes (`supersession.ts:286-296`), and the attempt counter lives in that record. A repair that adds a file resets the count, so `MAX_REGRESSION_FIX_ATTEMPTS = 3` (`:232`) never trips. The stall guard compares only consecutive actions, so alternating assess → repair isn't caught before 10,000 iterations | CONFIRMED at source by me; reproduced with the repo's functions by the deep-read (5 rounds, `fixAttempts` stayed null) |
| 2 | "Tests are immutable within a unit of work" is not enforced at the file level: no RED→GREEN hash of test files; the purpose-built `mutateTestList` / `verifyGateIntegrity` have no production callers; `run-tests.sh` maps pytest exit 5 ("no tests collected") to success | CONFIRMED (deep-read) |
| 3 | Per-story spec gate never stores a hash; stored hashes elsewhere are never re-verified | CONFIRMED (deep-read) |
| 4 | An LLM turn labelled "deterministic-agentless" runs outside the executor | CONFIRMED (deep-read) |
| 5 | The plugin auto-registers an MCP server exposing a raw GitHub token and ungated PR merge tools, which sidesteps the promote gate | CONFIRMED (impact SUSPECTED) |
| 6 | `pipeline.json` is written non-atomically (`writeFileSync`); `gates.json` uses temp-file + rename | CONFIRMED (impact SUSPECTED) |
| 7 | Telemetry comments say the default sink is a no-op; the code arms a real endpoint by default (content-free allowlisted fields) | CONFIRMED |
| 8 | A read with destructive side effects: deriving state (`readGreenFailure`) deletes files | CONFIRMED |

Finding 1 is my favourite lesson from the six repos: **a counter that bounds a loop must live somewhere the loop can't invalidate.** It's in [case 03](../case-studies/03-fail-open-patterns.md) row 6.

## 5. How it scales

- **Measured cost:** one full run was 119 agent turns, 709.7 compute-minutes, $139.18 and 2.45M output tokens for 2 features / 6 stories (≈ $23 and 2 compute-hours per story). The build lane was ~90% of wall-clock time; `driver/green` alone was 46%.
- **Verify cost grows with the product:** each GREEN runs the **full** accumulated suite on fresh branches, so per-cycle verify time grows linearly with delivered stories and lifetime verify cost roughly quadratically.
- **Worst case = schema contract changes:** two expand/contract migration stories took 73% of the measured run.
- **Bottlenecks:** one serial build lane per feature (parallel experiments designed but not wired), LLM output tokens ("output volume is the wall"), a single machine (local deploy only, one drive per project), and human latency at every gate.
- **Levers that worked:** per-step model/effort tiering. `effort=low` was "the dominant win"; haiku under-delivered on reasoning-heavy turns.
- **How I'd scale it:** test-impact-based verification per cycle with the full suite only at acceptance; worktree + paired-branch executors for independent stories; hard per-story dollar/time budgets.

## 6. How I'd explain it

- **Executive:** "AI agents do the typing, but a deterministic workflow decides what happens next, every 'done' is proven by real tests against a disposable copy of a real database, and nothing merges or migrates without your team's sign-off. AI speed, with an auditable trail."
- **Engineer:** "A TypeScript state machine: a pure `nextTransition(state)` over on-disk artifacts decides each step and spawns Claude only for bounded judgment turns. Each story gets a paired git + Lakebase branch; green means the orchestrator ran your suite on a throwaway fork."
- **Internal stakeholder:** "It's a reference agentic-SDLC workload that makes Lakebase copy-on-write branching the differentiator: branches per feature, story, verify run and PR. Pre-1.0; parallel experiments, remote deploy and hash verification aren't wired yet."

## 7. Interview angles

1. **"Why not let the LLM orchestrate?"** Latency, dropped observability, drift. Put sequencing and "is it done?" in code; give the model narrow, checkable tasks.
2. **"How do you stop an agent weakening tests?"** Layered: role separation, prompt rules, a Navigator-owned supersede allowlist, honest full-suite verify, test-smell gates. Then name the gap (no test-file hash) and the fix: hash test files at RED, refuse GREEN if a non-allowlisted file changed, and refuse pytest exit 5.
3. **"How are loops bounded?"** List the budgets, then tell finding 1: bounds need counters that can't be invalidated.
4. **"Why does Lakebase matter here?"** Copy-on-write branches give every story and every verify an isolated real Postgres, removing mock drift and shared-staging contamination. Costs: branch lifecycle (TTLs, orphan sweeps, `noExpiry` leaks), endpoint provisioning and credential-minting latency.

## 8. AI-stewardship lessons (transferable to the Databricks Assistant)

1. Don't let the model decide what happens next when code can. Ask the Assistant for **one bounded change**, not "build the feature".
2. **Verify, don't trust.** Re-run the cell or job, check row counts, run the test on a dev branch or cloned table. A claim without an artifact is unverified.
3. **Name exact targets:** fully qualified `catalog.schema.table`, exact columns, the exact cell.
4. **Check the output contract, then one informed retry,** then escalate. Blind re-prompting loops.
5. **Separate author from judge.** When reviewing AI code, look for loosened assertions, broadened `except`, deleted tests, relaxed DQ filters, hardcoded values: the "make it green" moves.
6. **Classify failures before asking for a fix.** An expired token or an unmigrated database is not a code bug.
7. **Bound loops and check for progress.** Two iterations with the same diff or the same error means stop and re-scope.
8. **Read comments in AI-assisted codebases skeptically.** This repo has several comment/code contradictions (telemetry arming, "no LLM" labels, stale citations). Trust the executable path.
