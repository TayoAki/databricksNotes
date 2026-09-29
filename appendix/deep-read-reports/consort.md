> **Provenance.** Deep-read of `databricks-solutions/consort` @ `61b3a48`, written by a research sub-agent during this study and kept verbatim, apart from local paths normalised to `<clone-root>/`. Its CONFIRMED / SUSPECTED labels are the agent's. The claims I re-verified myself, and how, are listed in [`README.md`](README.md); anything not listed there I have not independently checked.

# Consort: technical deep-read

Repo: `databricks-solutions/consort` (shallow clone of `main`, a single commit `61b3a48`, `package.json` version `0.3.102`, CHANGELOG top entry dated 2026-09-26). All paths below are relative to the repo root. "(inferred)" marks a claim I reasoned about but did not verify. Where the docs and the code disagree, I say so and trust the code.

Method: I read the orchestrator, pipeline, gates, smells, deploy, experiment, and runner code end to end. I read the substrate package `@databricks-solutions/lakebase-scm-utils@0.2.45` from a scratch `npm ci`. I also ran the hermetic suite on a scratch copy of the repo, never the original: 334 files, 4356 tests, 4292 passed, 59 skipped (live tiers), 2 todo, and 3 failed, all three caused by my environment (explained in §2.7). The run took about 88 s. Finally, I ran one small scratch experiment to confirm a suspected bug (§8, item 1).

---

## 1. What it is, in one paragraph for a customer

AI coding agents write code quickly, but on their own they declare work "done" with no test behind it. They also drift from the request, weaken tests to get to green, blur the application's layers, and lose the plan when their context resets. The database makes this worse: it is usually mocked, or shared on a staging box that the tests quietly drift away from. Consort is an open-source framework from Databricks for teams that build transactional application backends (an API plus an optional web UI) on Lakebase, Databricks' serverless Postgres. It runs a team of role agents (Product Owner, Spec Author, Architect Reviewer, DBA, Test Strategist, UX Designer, and a Navigator/Driver pair) inside a deterministic, code-defined state machine. The design lane is spec-first; the build lane is test-driven. Every story is built on its own copy-on-write Lakebase branch paired with a git branch. A build counts as "green" only when the orchestrator itself runs the real test suite against a live, throwaway database branch. Humans approve at gates that fail closed. The outcome is an auditable, resumable loop (`/plan → /design → /build → /deploy`) that produces reviewed, migrated, tested increments. Those increments are promoted through PR, CI, and parent-tier migration, and at every step the system checks the agents' claims rather than trusting them.

---

## 2. Architecture map

### 2.1 Size and layout

| Area | What it is | Size (approx.) |
|---|---|---|
| `consort/orchestrator/` | pure router (`workflow/`, `drive/orchestrator-drive.ts`), loop (`drive/orchestrator-run.ts`), effects (`drive/orchestrator-effects.ts`), state derivation (`state/`), step executor + manifests (`steps/`, `turns/`), Claude runner (`drive/claude-runner.ts`) | ~16k LOC |
| `consort/pipeline/` | per-story pipeline (`story-pipeline.ts`), cycle recorder (`cycle-record.ts`, `run-cycle.ts`), design fingerprint | ~2.7k |
| `consort/gates/` | gate state (`gates.ts`), hashing, lock, approve/withdraw, Human Proxy, escalations, handoff ledger, conformance guard | ~4.1k |
| `consort/smells/`, `consort/architecture/` | smell catalogue + self-heal markers; deterministic "clean" gates (layering, migrations, test smells, UX) | ~6k |
| `consort/deploy/`, `consort/experiment/` | honest-GREEN verify + local deploy; paired experiment branches | ~3k |
| `consort/evaluation/`, `consort/optimize/` | LLM-as-judge vs a recorded reference; model/effort sweep harness | ~3k code + reference corpus |
| `consort/telemetry/`, `consort/logging/` | pseudonymous telemetry; agent log, turn recorder, replay | ~4.9k |
| `bin/consort`, `bin/lakebase` | ~50 CLIs (`consort-drive`, `consort-cycle`, `consort-pipeline`, …) | ~9.1k |
| `apps/` | `dashboard` (Next.js, read-only observer), `mcp-server` (24 tools), `dev-playground` (placeholder) | ~19k |
| `skills/consort/` | `SKILL.md` + 8 role prompts (`agents/*.md`, 176 KB total) + references | prose |
| `templates/` | scaffolded project assets: `.claude/commands`, CI (`pr.yml`, `merge.yml`), hooks, `.consort` bootstrap | |
| `tests/` | 300 BDD files in `tests/bdd`, plus integration, live, and mcp tests | ~61k LOC |
| `dist/` | **committed** build output (2,223 tracked files, 83 MB) so consumers can use a git-URL pin without a build step | skipped |

The Lakebase, git, and GitHub substrate is a separate package, `@databricks-solutions/lakebase-scm-utils` (`package.json` dependencies). It owns `createPairedBranch`, `mergePaired`, `applySchemaMigrations`, the SCM ladder (`prepare-pr`, `wait-ci`, `merge`), and the Databricks CLI calls.

### 2.2 Control and data flow

```
 Human / interactive Claude Code session
   /consort:start  /plan  /design  /build  /deploy   (scaffolded .claude/commands/*.md)
   consort-approve-gate --approver <name>            (the human gate door)
        |  launches ./scripts/lk consort-drive ... --detach         ^ reads .consort/next.json
        v                                                           |  (consort-next, same engine)
 +---------------------- consort-drive  (bin/consort/drive.cli.ts:1158 main) ------------------+
 | guards: proxy-needs-CI (1241-1253), auth preflight (1255-1275), claim guards, bound (1287-96)|
 | runDriver(effects, {transition, stopWhen, pauseBefore})   orchestrator-run.ts:220           |
 |   loop:  state  = effects.readState()          -> readDriveStateFromDisk (effects.ts:2156) |
 |          ledger.reconcile(state)               -> orchestrator-expect.ts:319               |
 |          action = nextTransition(state)        -> PURE, orchestrator-drive.ts:244          |
 |          done / raise-to-hil / stopWhen / stall check (run.ts:311-348)                     |
 |          performViaExecutor ?? perform(action) -> commandsForAction (effects.ts:1545)      |
 +---------------+-------------------------------+----------------------------+----------------+
                 | DriveCommand kinds            |                            |
     "claude"    v                  "cli"        v              "set-phase"   v   "verify-artifact"
 claude -p <task> --agent <role>   consort-pipeline / -cycle / -experiment /  workflow-state.json
  --model --permission-mode        -deploy / -human-proxy / -test-list /      (phase + owner)
  acceptEdits --setting-sources    lakebase-scm-prepare-pr / -wait-ci / -merge
  project --strict-mcp-config      git
  (claude-runner.ts:637-648)
                 |                               |
                 v                               v
     .claude/agents/<role>.md          .consort/  ("artifact-as-API"; all state on disk)
     (8 role prompts)                  features/<F>/{feature-request.md, feature-spec.json,
                                         architecture.json, db-design.json, test-list.json,
                                         gates.json, pipeline.json, deploy-evidence.json,
                                         stories/<S>/{story.json, acs/AC*.json, test-list-per-story.json,
                                         reflect-verdict.json}}
                                       cycles/<F>/<S>/<AC>/{cycle-NNN.json, green-failure.json, review.json}
                                       experiments/<F>/<S>/exp1/{branch.txt, outcomes.json}
                                       escalations/*.json, smells.json, workflow-state.json,
                                       selection-log.md, agent-log.jsonl, next.json
                 |
                 v  lakebase-scm-utils -> `databricks postgres ...`, git, gh
 Lakebase project (one per app repo):
   main (default = prod) <- merge.yml migrates on push
    +- staging (tier)    <- lakebase-scm-merge (PR merge) -> merge.yml migrate
        +- <feature branch>             paired git + DB branch (claim-feature-branch)
            +- experiment-<s>-exp1      per-story paired branch, noExpiry (experiment.ts:366)
            |    +- <exp>-vrfy-<nonce>  ephemeral verify child, TTL 3600s (ephemeral-verify.ts:25)
            +- ci-pr-<N>                pr.yml CI branch (migrations + tests + schema diff)
```

### 2.3 Entry points

- **Installation:** `bootstrap.sh` (doctor plus install), `install.sh` (copies skills to Claude, Cursor, and Genie Code; `--install-to-genie` uploads them with `databricks workspace import-dir`, `install.sh:222-242`). The Claude Code plugin is `.claude-plugin/plugin.json` (`skills: ./skills/`; its `SessionStart` hook finishes `npm ci`), and `.mcp.json` registers the MCP server.
- **Project bootstrap:** `lakebase-create-project` (`bin/lakebase/create-project.cli.ts`) runs a doctor gate, then the substrate `createProject` with `kitConsortHooks`. Those hooks lay down `.consort/`, `.claude/agents|skills|commands` (`consort/setup/project-consort-setup.ts:51-82`, `:256-259`).
- **Runtime:** `consort-drive` is the only orchestrator. Tier 1 is `--sprint`; Tier 2 bounds are `--plan-only` and `--only design|build|deploy` (`orchestrator-run.ts:195-212`). `consort-next` is a read-only "what next" view from the same engine (`consort/orchestrator/status/next.ts:1-23`). `consort-watch` relays live progress, and `consort-dashboard` is a read-only observer.
- **Other agent surfaces:** `apps/mcp-server` (stdio MCP, 24 tools) and `tools/openai-foundry/consort.tools.json`.

### 2.4 The role ensemble, and how each role is spawned

The role definitions live in `skills/consort/agents/<role>.md`, as YAML frontmatter plus a prompt. At scaffold time `layDownKitClaudeAssets` copies them into the project's `.claude/agents/` without overwriting existing files (`consort/setup/project-consort-setup.ts:128-140`), and `lakebase-update-agents` refreshes them later. The driver spawns every role turn as a headless Claude Code process (`claude-runner.ts:637-648`):

```ts
export function claudeBaseArgs(cmd: Extract<DriveCommand, { kind: "claude" }>): string[] {
  return [
    "-p", cmd.task,
    "--agent", cmd.role,
    "--model", cmd.model,
    "--permission-mode", "acceptEdits",
    "--setting-sources", "project",
    "--strict-mcp-config",
    "--output-format", "stream-json",
    "--verbose",
  ];
}
```

Two flags are load-bearing. `--setting-sources project` is what makes `--agent <role>` resolve at all, and `acceptEdits` is used instead of `bypassPermissions` because enterprise managed settings silently downgrade the latter (`claude-runner.ts:604-636`). The runner adds several more controls:
- per-turn `--effort`, `--fallback-model`, and `--max-budget-usd`;
- a Playwright MCP config for the UX Designer only;
- session resume keyed per role, or per role and story for the builders (a manifest can force `session: fresh`), subject to a context-budget guard that requires 40% of the window to be free (`consort/session/context-budget.ts:17`, `:85-92`);
- up to 2 fresh-session retries when a turn fails with "prompt is too long", up to 5 transient retries with backoff, and a 10-minute inactivity kill (`claude-runner.ts:49-67`, `:805-900`).

The task prompt is assembled as handback + role body + context pack + `AGENT_TERSE_SUFFIX` + optional optimization levers (`orchestrator-effects.ts:1346-1351`, `:277-280`).

| Role (frontmatter tools / default model; the effective per-step model is in the manifest) | Consumes | Produces | Code |
|---|---|---|---|
| **Product Owner** (`Read, Write, Edit, Bash` / opus) | `intake/answers.md`, the StockFlow example; later `requested.json` + proposals | `product-overview.md`, `nfrs.md` (R-ids), `design/design-brief.md`; `features/<F>/feature-request.md` | `orchestrator-effects.ts:614-663` |
| **Spec Author** (opus) | intake docs; `feature-request.md`; the story stub | `planning/feature-proposals.md`; `feature-spec.json` + story stubs (with `independence`); `stories/<S>/acs/AC<n>-slug.json` | `:588-595`, `:665-686`, `:715-734` |
| **Architect Reviewer** (opus) | proposals / committed requests; the ACs + `nfrs.md` + project conventions | `planning/estimates.json`; per-AC `architectural_notes` + `architecture.json` (`service_backed`, `layers`/`may_import`, `persistence_invariants`) | `:596-613`, `:735-756` |
| **DBA** (opus) | `architecture.json` (invariants, models layer) | `db-design.json` (tables, constraints, `schema_changes`, `realizes_invariants`) + `db-design.md` | `:757-804` |
| **Test Strategist** (`+Task` / sonnet; a supervisor that fans out to behavior, fitness, and client analysts) | ACs, `architecture.json`, `db-design.json` | appends to `features/<F>/test-list.json` (items: `id, ac_id, kind, scenario_file, invariant_id`) | `:805-864`; `consort/test-list/test-analyst-catalogue.ts` |
| **UX Designer** (`+WebFetch, WebSearch, mcp__playwright` / sonnet) | `design-brief.md`, `product-overview.md`, reference sites | `design/design-guide.{md,json}`, `ia.md` (theme tokens) | `:691-712` |
| **Navigator** (sonnet) | test-list items, the context pack, green-failure advisories | reflect verdict; RED test files; review verdict; assess markers (`superseded-tests.json` / `regression-assessment.json`); deploy/refactor scope | `:866-1069` |
| **Driver** (`+Skill` / sonnet) | failing tests (the RED body is injected), directives | app code (GREEN); refactor; repair; scoped test refactors for superseded tests only | `:1070-1167` |

The "Release Engineer" and "orchestrator" roles exist only as log labels. Deploy and promote are deterministic code (`consort/config/agent-models.ts:20-28`).

**The Human Proxy** (`consort/gates/human-proxy.ts`, `bin/consort/human-proxy.cli.ts`) is the headless stand-in for the human at every HIL touchpoint:
- It approves only gates whose real artifacts exist and conform, and skips the rest (`human-proxy.ts:21-37`, `:100-149`).
- It supplies recorded intake and feature-request seeds from `$LAKEBASE_CONSORT_SPRINT_REQUESTS`, after checking them for conformance (`:185-235`, `:289-328`).
- It can deterministically project `feature-proposals.md` instead of running a live propose (`:361-384`).
- It makes the PO's `revise` decision on routable spec-level escalations (`decide-escalation`, `human-proxy.cli.ts:130-196`).
- Its identity is `human-proxy`, so an audit can find it by grep (`human-proxy.ts:80`). It is labelled "NOT for production use" (`:9-12`).
- The drive refuses `--gates proxy` without CI or `AUTO_CONTINUE=1` (`drive.cli.ts:1241-1253`). The human door, `consort-approve-gate`, requires `--approver <name>` and has no default (`bin/consort/approve-gate.cli.ts:97-103`).

### 2.5 Supporting subsystems

- **`consort/smells`.** This holds the catalogue of 24 smell names, each with a level: `spec` smells route back to the owning author, `build` smells halt (`smells.ts:8-44`, `:62+`). It also holds the self-heal marker machinery:
  - `green-failure.json`, which drives assess, repair, supersede, spec-defect, and unfixable routes (`supersession.ts`);
  - deploy- and refactor-verify assess markers;
  - the reflect verdict (`reflection.ts`);
  - deterministic test-list conformance (`testlist-conformance.ts`);
  - the ephemeral verify branch (`ephemeral-verify.ts`).

  Blocking smells reach the router as escalations (`consort/gates/escalation.ts:48-85`, `:207-230`). Spec-level smells become a bounded `revise-route` (`orchestrator-probe.ts:573-610`), and build-refactor-routable smells are suppressed while a refactor is pending (`:565-572`). **Detection is split.** Deterministic sources are the reflect and test-list gates, `ux-adherence` (`cycle-record.ts:1040`), `architect-canon-gap` (`bin/consort/project-canon-notes.cli.ts:60`), and gate failures that flip GREEN to failed. Agent-reported sources arrive through `consort-log --event smell.flagged` → `recordBlockingSmellFlag` (`bin/consort/agent-log.cli.ts:328`). The cycle-history detectors (`detectAll`: cycle-stall, test-cost-spiral, test-deletion-attempt, …) have **no production caller** (§8).
- **`consort/session`.** Supporting pieces for the drive and the interactive session:
  - `context-budget.ts`: the resume-or-fresh decision and overflow and transient error signatures (`:17-127`);
  - `claude-usage.ts`: parses the `stream-json` result event for tokens and cost;
  - `relaunch-detached.ts`: `--detach` uses `spawn(detached)` with `setsid` so a run survives the harness killing the turn's process group (`:1-8`);
  - `preflight.ts`: gives `/start` its deterministic state up front, "instead of DISCOVERING them through a dozen ad-hoc find/ls/CLI probes" (`:1-8`);
  - `response-formatter.ts`: the agent-side self-check CLI that a role runs on its own artifact before returning (`:1-8`);
  - `run-config.ts`: snapshots the model and option matrix, so runs can be compared A/B.
- **`consort/architecture`.** These are static "clean" gates, each returning `{clean, violations, remediation}`:
  - `layering-clean`: session-op regex in the boundary, `may_import` import-direction scan, ORM containment, module placement, rendering, DRY/complexity, duplicate classes; `SESSION_OP` at `layering-clean.ts:153`.
  - `contract-clean`: a dropped column still referenced in code.
  - `migration-app-clean`: a migration importing app code.
  - `migration-history-clean`: `git diff` of the migration directories against the fork point, flagging M/D/R/T (`migration-history-clean.ts:1-18`).
  - `test-smell-clean`: 12 kinds (`test-smell-clean.ts:44-56`).
  - `design-adherence` / `ux-clean`, `imports-clean`, `e2e-regex-clean`.
  - `architecture-conventions` / `architecture-canon`: the first feature pins the role → module layout plus standing rules, and later stories are projected deterministically unless they are new to the canon (`architecture-canon.ts:1-19`).
- **`consort/evaluation`.** `semantic-gate.ts` is a shared LLM-as-judge on a **fixed** model (opus) that scores coverage from 0 to 1 against the reference recorded for the same turn. Thresholds: 0.85 for design, 0.75 for build (`semantic-gate.ts:12-17`, `:79-82`). It also has a navigator-verdict "discriminator" that classifies driver output as `equivalent`, `regression`, `superseded-shift`, or `insufficient` (`:509-549`). The reference assets are "the camp" extracted verbatim from recorded corpora ("the mine"), with the rule "Nothing manufactured, ever" (`consort/evaluation/reference-assets/README.md:1-40`).
- **`consort/experiment`.** Per-story paired experiments: `cutExperiment`, merge/discard lifecycle with injected operations, spikes (throwaway exploration branches), and the N≥2 race primitives (`promoteExperiment`, `synthesizeExperiments`, `checkPerExperimentCap`, `runExperimentsInParallel`). The N≥2 primitives have zero live callers (`docs/design/parallel-per-story-experiments.md:9-14`).
- **`consort/optimize`.** Two harnesses. The deprecated champion walk picked the fastest gate-passing candidate per handoff (`optimize-harness.ts:1-20`, deprecation banner `OPTIMIZE-INDEX.md:3-13`). Its replacement is the "one judged sweep engine" (`tests/optimization/role-sweep.ts`, launched by `scripts/optimize-role.sh`). That engine crosses model × effort × tool scope × prompt diet per chain, runs each candidate in its own temp workspace (or worktree plus Lakebase branch for the driver), requires both conformance and a reference judge, and preserves every output (`OPTIMIZE-INDEX.md:19-43`).
- **`consort/telemetry`.** A hand-rolled NDJSON POST with a closed allowlist, fire-and-forget delivery, a bounded queue, and a detached sender process (`emitter.ts`). Level 1 records one trace per drive with a gate span per action; Level 2 is opt-in and adds turn timings. Consent means persisted-enabled, not CI, and `CONSORT_TELEMETRY != 0` (`TELEMETRY.md` "Consent"). It is **armed by default** to an Azure-hosted ingest endpoint (`emitter.ts:132-154`). The comments disagree about this (§8).
- **`consort/test-list`.** Test-list I/O and scoping: `readMasterTestList` normalizes `items` because a model once wrote `tests` (`test-list.ts:39-60`), a per-story view, the status flip on green, the analyst catalogue and roster, and `mutateTestList`, a post-approval write surface guarded by the gate (dead in production, §8).
- **`consort/intake`.** An intake precondition check for `product-overview.md` and `nfrs.md` (plus `design-brief.md` on the UI track) (`intake.ts:1-9`), `orchestrator-sprint.ts`, and `spec-sync.ts` with adapters. The markdown adapter is implemented; the Jira adapter stub throws "not implemented" (`intake/adapters/jira.ts:4-30`).
- **`apps/dashboard`.** A Next.js 15 "Agent Mission Control". In live mode it is a read-only observer of `.consort/`: an agent-persona board, gates, and handback routing. In replay mode it scrubs a recorded corpus with a topology graph and per-turn transcripts (`apps/dashboard/README.md:1-13`). Its API routes use a symlink-safe path resolver (`lib/safepath.ts`).
- **`apps/mcp-server`.** A stdio MCP server with 24 tools wrapping substrate functions: connection, schema diff, GitHub token, create project, migrations (list, apply, rollback, status), feature status, PR open/merge/status/files/reviews/comments, doctor, workflow drift, and branch list/show/create-paired/delete-paired/checkout/sync-env (`apps/mcp-server/tools.ts:74-678`). Plugin `.mcp.json` registers it automatically.
- **`apps/dev-playground`.** A placeholder, `export {}` (`apps/dev-playground/index.ts:1-8`).

### 2.6 Process docs and the methodology they encode

- **`MASTER-CANONICAL-PROCESS.md`** is the "rebuild from scratch" contract. It lists six load-bearing invariants (`:26-37`): routing is pure; every turn goes through one executor; steps are dumb and contained; routes are bound to input contracts; the HIL is one interface with two implementations; every turn is recorded and replayable. It includes mermaid graphs of each lane and an open-work list (§9). **Its citations have drifted from the code.** It says `nextTransition` is at `orchestrator-drive.ts:195` (actually `:244`) and `runDriver` at `orchestrator-run.ts:189` (actually `:220`). §0.4 says the routing state bag is not captured, but `onRoutingDecision` now captures it (`orchestrator-run.ts:66-71`, `:304-309`). §0.5 says `author-requests` runs on the legacy path, but it is executor-dispatched (`executor-dispatch.ts:108`). The planning diagram omits the intake and backlog gates (`orchestrator-drive.ts:258-277`).
- **`CLAUDE.md`** (repo) splits the work into two lanes: SDD (`/design`: spec → architectural review → test list → gate) and TDD (`/build`: RED → GREEN → REFACTOR). It states that the orchestrator "is a deterministic driver, not an LLM agent… Every gate is HITL" and gives the maintainer rules: run typecheck, regenerate `manifest.json` after skill edits, and add live tests for Lakebase changes.
- **`docs/positioning.md`** says what Consort is: deterministic, eight roles, spec-first then TDD, real-data verified, human-gated. It says what Consort is not: data engineering, ETL, BI, Lakehouse, or a drop-in prompt pack. It compares Consort with Spec Kit and superpowers on the question of *where discipline is enforced* (code versus prompt) (`:46-93`).
- **`CONTRIBUTING.md`**:
  - two credential "seams", each guarded by a CI grep: Lakebase credential minting in `get-connection.ts`, GitHub tokens in `auth.ts` (`:82-89`);
  - test tiers: hermetic, live (5-15 min, a real workspace), and a smoke run;
  - a rule table of which tier each change needs (`:203-213`);
  - the release checklist, including the KA refresh.

  It has aged. "Tier 1 ~10s" is actually about 90 s today, and the release line `0.3.0-beta.<N>` does not match version `0.3.102`.
- **`OPTIMIZE-RUN-LOG.md`** is an experiment journal. Its standing rule is: **every evaluation must run a judge against the recorded reference and preserve outputs** (`:11-37`). It records self-corrections: winners applied *without* a judge (`:390-411`), "manufactured slice" references reversed (#705, `:64-86`, `:153-166`), and real harness bugs such as a directory read as a file (EISDIR) and ranking by the wrong clock. The results are the "effort=low is the dominant win" headline and "haiku under-delivers on reasoning-heavy turns" (`:353`). The "APPLIED WINNERS" list (`:123-151`) no longer matches the shipped manifests: `navigator-red` is now sonnet/low, and `navigator-reflect` is sonnet/default rather than haiku/low. Trust the manifests.
- **`DEPRECATIONS.md`** records the rename from `lakebase-sftdd-*`/`lakebase-tdd-*` bins and `LAKEBASE_SFTDD_*`/`LAKEBASE_TDD_*` environment variables to `consort-*`/`LAKEBASE_CONSORT_*`. The old names are removed in v0.4.0, and `consortEnv()` warns once per legacy name.
- **`TELEMETRY.md`** is the privacy contract: pseudonymous `install_id`, a closed allowlist, opt-out, and an install beacon sent regardless of opt-out unless `CONSORT_TELEMETRY=0`.
- **`CHANGELOG.md`** has 104 releases and is the best "what went wrong" source; §11 mines it.

### 2.7 The repo's own testing and CI

- **Layout.** `tests/bdd/` holds 300 Vitest files, almost all hermetic, including the pure state machine (`orchestrator-drive.test.ts`, 480 lines), the loop against a fake world (`orchestrator-drive-loop-e2e.test.ts`), the ledger, the legacy-path guard, stale green-failure handling, gates, the lock, the Human Proxy, and the clean gates. Other folders: `tests/integration/` (manifest chains, hermetic role chains, `live/` seeds), `tests/live/` (live orchestration and spec-author step), `tests/mcp-server/`, `tests/agent-capability/`, and `tests/optimization/` (the sweep engine, not tests). Live tiers skip unless `LAKEBASE_TEST_E2E=1` and `DATABRICKS_HOST` are set (`CLAUDE.md`). The suite uses a 30 s default timeout for git-heavy tests and excludes scaffold fixtures (`vitest.config.ts:8-24`).
- **My run** (scratch copy, `npm ci --ignore-scripts`, 16 s install): 334 files and 4356 tests in about 88.5 s. 4292 passed, 59 skipped, 2 todo, and 3 failed. All 3 failures came from my environment. `dist-bins-shipped` failed because I excluded `dist/` from the copy. Two `deploy-claude-agents` tests failed because the vendored `databricks-core` and `databricks-lakebase` skills are gitignored (`.gitignore:30-31`) and fetched by the network `prepare` step I skipped. So the "hermetic" tier has a dependency on the network.
- **Husky hooks.** `pre-commit` refuses commits on `main`, `master`, or `production`, with a `HUSKY=0` escape hatch (`.husky/pre-commit`). `pre-push` runs `typecheck`, then `npm test`, then the dashboard's `tsc` and `vitest` (`.husky/pre-push`). The hook notes that "GitHub Actions is disabled at the databricks-solutions org level… this hook is the only automated gate today".
- **Workflows in `.github/workflows`:** `ci.yml` (Node 20: typecheck, test, dashboard job), `grep-guard.yml` and `github-auth-grep-guard.yml` (enforce the single-seam rules), `release.yml` (tag verify: build, typecheck, test), and `traffic-stats.yml` (daily). The only commit in the clone is a traffic-log commit authored by `gh-traffic-log`, not `github-actions[bot]`, which fits the claim that Actions are disabled.

---

## 3. How the code executes: one increment traced through the code

### 3.1 The state machine

**Coarse phases.** `DrivePhase = "planning" | "feature" | "deploy" | "promote" | "done"` (`consort/orchestrator/workflow/workflow-vocabulary.ts:206`). The persisted TDD phase in `workflow-state.json` maps to these phases through `driverPhaseForTdd` (`consort/orchestrator/state/orchestrator-derive.ts:293-308`). A persisted phase is honored only when it is sprint-scoped `planning` or was stamped for this feature (`orchestrator-probe.ts:118-127`, FEIP-8022). This prevents F2 from inheriting F1's `deploy` phase.

**Per-story pipeline status.** `designing → awaiting-gate → ready → building → awaiting-acceptance → done | discarded` (`consort/pipeline/story-pipeline.ts:19-27`). There is a FIFO `build_queue` and at most one `build_active` (`:120-128`, `dispatchNext` at `:268-275`).

**Actions.** The `WorkflowAction` union (`workflow-vocabulary.ts:347-404`) has 28 distinct `kind`s, and `invoke-role` alone has more than 20 role, mode, and build-mode variants. Legal transitions follow from `nextTransition` (`consort/orchestrator/drive/orchestrator-drive.ts:244-376`). Escalation is checked before every phase, so a pending escalation pre-empts everything (`escalationPreempt`, `workflow-vocabulary.ts:428-442`). The sequences:

| Phase | Legal sequence (each step fires only when its predecessor's state flag is set) | Code |
|---|---|---|
| planning | `invoke PO intake` → `approve-intake-gate` → `spec-author propose` → `architect estimate` (unless `--no-sizing`) → `approve-backlog-gate` → `PO author-requests` → `architect estimate-committed` → `approve-plan-gate` → `planning-complete` | `orchestrator-drive.ts:250-296` |
| feature | UX Designer (UI track, once) → **if a story is building:** `nextBuildAction` → **else if a story is gate-approved and unaccepted:** `dispatch` → **else** the design lane → `feature-complete` | `:353-376` |
| design lane (first un-gated story, in breakdown order) | `spec-author breakdown` → `ux-designer` → `spec-author (ACs)` → `project-architect-notes` or `architect-reviewer` → `dba` → `test-strategist` → `flag-testlist-nonconformance` (deterministic) → `navigator reflect` → `surface-gate` → `approve-gate` | `:53-114` |
| build lane | `cut-experiment` → (self-heal routes) → `navigator` RED → `driver` GREEN → `review` / `refactor` → `await-acceptance` (per-story deploy + verify) → `accept` → `complete` | `:117-241` |
| deploy | `deploy` → [feature self-heal] → `deploy-verify-reverify` (once) / `raise-to-hil` → `approve-deploy-gate` → `deploy-complete` | `:298-334` |
| promote | `prepare-pr` → `wait-ci` → `approve-promote-gate` → `merge` → `done` | `:336-349` |

The build lane's precedence order is itself a design artifact (`orchestrator-drive.ts:149-240`):
1. Refactor-verify assess and refactor.
2. Story review, then refactor.
3. `assessGreenAc` (Navigator assesses a failed verify).
4. `repairRegressionAc` (one Driver repair).
5. `greenSupersededAc`.
6. `specDefectAc` → `raise-to-hil` (recommending `consort-reopen-story --from <role>`).
7. `greenUnfixableAc` → `raise-to-hil`.
8. RED, then GREEN.
9. `await-acceptance`.
10. Deploy-verify self-heal.
11. `accept` only when `deployVerified`.

**Why routing is code, not a model's choice.** `nextTransition` is a pure function with no I/O and no model (`orchestrator-drive.ts:1-16`). `runDriver` computes each action from the state it has just re-derived (`orchestrator-run.ts:298`). An agent can only change state by writing files, and those files are re-read and validated. Where an optional "route proposal" seam exists, `validateAndBound` accepts a step's proposed next action only if it equals the pure transition, and otherwise falls back to that transition (`consort/orchestrator/steps/step-contract.ts:479-489`). Agents cannot emit gate lifecycle events: `consort-log` rejects `gate.*` events from agents (`bin/consort/agent-log.cli.ts:29-49`). The design doc explains the move away from the earlier LLM "scrum-master" orchestrator: routing was already deterministic, and running it through an LLM cost latency (a first turn of about 99 s), dropped logs (haiku skipped `phase.*` events), and forced a "false model trade-off" (`docs/design/refactor/orchestrator-deterministic-driver.md:1-48`).

### 3.2 The loop body (`runDriver`, `orchestrator-run.ts:220-393`)

1. `readState()` rebuilds the `DriveState` from disk: `readPipeline` + `diskArtifactProbe` + `readDriveContext` → `deriveDriveState` (`orchestrator-effects.ts:2156-2179`). Nothing is cached between iterations.
2. `ExpectationLedger.reconcile(state)` checks that the previous role handoff delivered its artifact. On a miss it grants one informed retry, then throws `ProtocolViolationError` (`orchestrator-run.ts:272-278`; `consort/gates/orchestrator-expect.ts:239-324`, `maxRetries = 1` at `:244`).
3. `action = transitionFn(state)` (`:298`). The `onRoutingDecision` hook records both the action and the state that produced it (`:304-309`).
4. `done` and `raise-to-hil` are terminal (`:311-325`). A Tier-2 `stopWhen` exits cleanly before an out-of-scope action (`:329-331`). In interactive mode, `gatedStopWhen` also stops before every HITL gate action (`bin/consort/drive.cli.ts:453-462`).
5. **Stall guard:** if the same action appears twice in a row without a sanctioned retry, the loop throws `DriverStalledError` (`:342-348`). There is also a hard backstop of `MAX_ITERATIONS = 10_000` (`:180`).
6. The loop pushes the new handoff expectation (`:355-358`), asserts that the route is satisfiable (`:364`), and then runs `performViaExecutor` (manifest-driven Template Method), falling back to `perform` (`:373-391`). `perform` throws on any agent turn that escaped the executor (`assertNotStrandedAgentTurn`, `consort/orchestrator/drive/executor-dispatch.ts:217-228`).

### 3.3 Trace of one increment (feature F with story S1, Python, UI track off)

**Planning (`/plan` → `consort-drive --sprint s1 --plan-only`, `drive.cli.ts:614`, bound at `orchestrator-run.ts:201`).**

1. `invoke-role product-owner intake`: the PO drafts `.consort/product-overview.md`, `nfrs.md`, and `design/design-brief.md` from `intake/answers.md` (`orchestrator-effects.ts:614-646`).
2. `approve-intake-gate`: the interactive drive stops here. The human's `consort-approve-gate --gate intake` writes the marker `intake/approved` (`consort/gates/intake-gate.ts:22-28`).
3. `spec-author propose` writes `planning/feature-proposals.md` (`orchestrator-effects.ts:588-595`). The prompt adds `deliveredFeaturesDirective` so shipped features are not proposed again (`:529-539`).
4. `architect-reviewer estimate` writes `planning/estimates.json`. At `approve-backlog-gate`, the human's selection becomes `sprints/<s>/requested.json`, and `sync-backlog` projects it to `backlog.json` (`:1851-1865`).
5. `PO author-requests` writes `features/F/feature-request.md` (`:648-663`). `estimate-committed` re-sizes the committed features, then re-syncs the backlog (`:1635-1644`).
6. `approve-plan-gate` → `approveSprintPlanGate` hashes `feature-proposals.md` after checking that it exists and conforms (`consort/gates/sprint-gates.ts:115-156`). `planning-complete` is where the run stops: the `plan` bound halts *before* performing it (`orchestrator-run.ts:201`). Sprint planning state is derived in memory with phase `planning` (`consort/intake/orchestrator-sprint.ts:49`, `:97`), so the `set-phase discovery` effect mapped to that action (`orchestrator-effects.ts:1879-1880`) does not fire on the `/plan` path. `/sprint` then commits and pushes the feature requests and claims each backlog feature in turn (`drive.cli.ts:793-845`).

**Design (`/design F`: the command first claims the paired feature branch; the drive refuses to run with a foreign claim (`drive.cli.ts:1317-1336`) or with no claim (`:1360-1370`); bound `--only design` uses `nextDesignOnlyTransition`, `orchestrator-drive.ts:401-409`).**

7. `spec-author breakdown` runs as `[pipeline reset-breakdown, claude, verify-artifact feature-spec.json, pipeline sync-breakdown, consort-log --reconcile]` (`orchestrator-effects.ts:1585-1605`). It writes `features/F/feature-spec.json` (with a non-empty `stories[]`) and `stories/S1/story.{md,json}`. `syncBreakdownToPipeline` seeds `pipeline.json` with S1 as `designing` (`story-pipeline.ts:189-213`).
8. `spec-author` (S1) writes `stories/S1/acs/AC1-*.json`. The prompt scopes the turn to "S1 and NOTHING else" (`orchestrator-effects.ts:715-734`).
9. The architect step runs only if the story is new to the canon. Otherwise `project-architect-notes` projects the notes deterministically (`orchestrator-probe.ts:289-316`). The architect writes `architectural_notes` into each AC and creates `architecture.json` with `service_backed`, `layers` (including `may_import`), and `persistence_invariants` (`orchestrator-effects.ts:735-756`).
10. `dba` writes `db-design.json` (tables, constraints, `schema_changes`, `realizes_invariants`) (`:757-804`). It is "done" when `checkDbDesign` passes (`orchestrator-probe.ts:261-287`).
11. `test-strategist`, a supervisor that fans out to behavior, fitness, and client analysts (`consort/test-list/test-analyst-catalogue.ts:1-18`), appends S1's items to `features/F/test-list.json`. A post-turn `consort-test-list` then writes `stories/S1/test-list-per-story.json` (`orchestrator-effects.ts:1612-1614`).
12. `flag-testlist-nonconformance` fires only if the deterministic structural checks fail (`orchestrator-drive.ts:102`, `orchestrator-effects.ts:1716-1720`).
13. `navigator reflect` writes `stories/S1/reflect-verdict.json`. `consort-cycle reflect-gate` turns a failed verdict into a spec-level smell, which then drives a bounded `revise-route` (`orchestrator-effects.ts:875-910`, `:1397-1398`).
14. `surface-gate` (`pipeline surface` sets `awaiting-gate`), then `approve-gate`, the HITL gate (`:1722-1729`). `approveStoryGateFromDisk` refuses on any of these:
    - batched drafts in other stories;
    - a registered-breakdown mismatch;
    - malformed or non-conformant ACs;
    - a missing story-independence determination;
    - `requires_e2e` without an E2E AC.

    Only then does it set `ready` and enqueue the story (`story-pipeline.ts:422-474`).

**Build (`/build F` → `--only build`, whose `stopWhen` is `actionLane(a) !== "build"`, `orchestrator-run.ts:204-205`).**

15. `dispatch` sets `build_active = S1` and status `building` (`story-pipeline.ts:268-275`).
16. `cut-experiment` runs `consort-experiment cut --branch experiment-s1-...-exp1 --parent <featureBranch> --instance <lakebase project>` (`orchestrator-effects.ts:1734-1766`). `cutExperiment` (`consort/experiment/experiment.ts:272-424`) then:
    - commits the design corpus before forking (`:285-313`);
    - refuses if tracked source is dirty (`:322-341`);
    - calls `createPairedBranch`, which creates a Lakebase branch from the feature branch, a git branch, and a `.env` DSN (`:359-367`);
    - fails if `.env` was not synced (`:377-383`);
    - checks that the git and DB fork parents agree (`:392-395`);
    - writes `experiments/F/S1/exp1/{branch.txt, notes.md, outcomes.json, timeline.json}` (`:398-414`).

    The CLI also stamps `design_fingerprint` on the pipeline record (`bin/consort/story-experiment.cli.ts:84-97`).
17. **RED:** `navigator` (no build mode) receives the exact pending test IDs for the whole story (`orchestrator-effects.ts:351-366`) plus the context pack. It writes the test files. Then `consort-cycle begin --loop story` runs `beginNextPendingBatch`, which writes `cycles/F/S1/AC1/cycle-001.json` with `red_at` and `test_ids` (`consort/pipeline/cycle-record.ts:429-457`; `consort/pipeline/run-cycle.ts:184-221`).
18. **GREEN:** `driver` writes app code. Then `consort-cycle green` runs `greenOpenCycle` (`cycle-record.ts:545-816`):
    - `ensureDeployedAndVerify` (`consort/deploy/deploy.ts:929-1107`) stops any old app, picks a free port, starts the app, and polls the health endpoint.
    - It runs the verify command on ephemeral child Lakebase branches: `not migration`, then `migration`, then client (`deploy.ts:990-1076`; `consort/smells/ephemeral-verify.ts:69-100`).
    - A provisioning-fault retry (`cycle-record.ts:590-614`), an auth-expired short circuit (`:691-702`), and deterministic post-pass gates (migration-app-clean, shipped-migration-immutable, test-smells; `:622-663`) can each turn a pass into a fail.
    - **On pass:** `markGreen` (`run-cycle.ts:281-321`), then `markTestItemGreen`, then a commit `green: ...` on the experiment branch (`cycle-record.ts:789-815`).
    - **On first fail:** it writes `cycles/.../green-failure.json` and routes to Navigator assess (`:703-743`).
19. **REVIEW/REFACTOR:** `navigator review` writes `cycles/F/S1/review-verdict.json`, which `consort-cycle review` turns into `review.json` (`cycle-record.ts:1250-1290`). If a refactor is requested, `driver refactor` runs, and `refactorStory` re-verifies, resolves routable smells, and commits (`:1297-1375`).
20. `await-acceptance` runs `consort-deploy --stop`, then `consort-deploy --gate --story S1 --lakebase-branch experiment-...`, which writes `stories/S1/deploy-evidence.json`, then `pipeline await-acceptance` (`orchestrator-effects.ts:1768-1799`). Acceptance requires `deployVerified` (`orchestrator-drive.ts:235-239`).
21. `accept` (HITL). When the drive performs it (headless), it runs `consort-ux-clean` and then `consort-pipeline accept` (`orchestrator-effects.ts:1810-1833`). In interactive mode the drive stops first, and `consort-next` offers the human `consort-pipeline accept … --approver <you>` (`consort/logging/orchestrator-logging.ts:371-372`). That calls `mergeAndAcceptStory` (`consort/experiment/experiment-merge.ts:73-108`), which does commit code → commit drive-state audit → `mergePaired` git merge into the feature branch → `applySchemaMigrations` on the feature branch's Lakebase DB → `deletePairedBranch` for the experiment (`experiment-lifecycle.ts:89-104`). `acceptStory` then marks the story `done` and frees the lane (`story-pipeline.ts:611-626`).
22. `complete` returns the loop to the design lane for S2, and so on. When every story is accepted, `feature-complete` runs `consort-gate-conformance` over all the feature's artifacts, then `set-phase deploy` (`orchestrator-effects.ts:1882-1894`).

**Deploy and promote (`/deploy F` → `--only deploy`, lanes deploy + promote, `orchestrator-run.ts:206-210`).**

23. `deploy` runs `consort-deploy --gate --feature F --lakebase-branch <feature>`, which writes `features/F/deploy-evidence.json` (`orchestrator-effects.ts:1896-1908`, `:1530-1543`). A failed verdict gets one `deploy-verify-reverify` (marker `deploy-reverify.json`), then a terminal HIL (`orchestrator-drive.ts:315-329`).
24. `approve-deploy-gate` (HITL). Headless, this is `consort-human-proxy --gate deploy`; interactive, it is the human's `consort-approve-gate --feature F --gate deploy` (`orchestrator-logging.ts:358-359`). Both go through the same resolver. This refuses unless the evidence shows `reachable === true && verify.passed === true`; if so it calls `approveGate` with hashes (`consort/gates/gate-conformance-guard.ts:973-1002`, `consort/gates/approve-gate.ts:78-151`).
25. `deploy-complete` → `set-phase promote`. `prepare-pr` runs `consort-migration-history-clean` and then `lakebase-scm-prepare-pr --force`. That pushes and opens a PR, which triggers `pr.yml`: a `ci-pr-<N>` Lakebase branch, migrations, tests, and a schema-diff comment (`templates/project/common/.github/workflows/pr.yml:1-5`).
26. `wait-ci`, then `approve-promote-gate` (HITL; the promote ref is the feature branch, `orchestrator-effects.ts:1964-1982`), then `merge` → `lakebase-scm-merge --wait-migrate --migrate-timeout-nonfatal --migrate-timeout-sec 600` (`:1984-2008`). That merges the PR, deletes the feature's Lakebase branch, and lets `merge.yml` migrate the parent tier.
27. `done` runs `git checkout -f <parent>`, `git branch -D <feature>`, and `set-phase shipped` (`:2010-2058`).

**What `.consort/` holds at the end.** `features/F/{feature-request.md, feature-spec.json, architecture.json, db-design.json, test-list.json, gates.json (deploy+promote approved with sha256), pipeline.json (S1 done, gate approved, experiment merged + design_fingerprint), deploy-evidence.json, stories/S1/...}`, plus `cycles/F/S1/...`, `experiments/F/S1/exp1/...`, `selection-log.md` (narrative gate log), `agent-log.jsonl`, `smells.json`, `escalations/` (if any), `workflow-state.json` (`phase: shipped`, owner F), and `next.json`.

---

## 4. Key design decisions, and why

1. **The router is a pure function; LLMs only do bounded judgment turns.** Everything else is decided in code. *Why:* the routing was already deterministic, and running it through an LLM cost latency and fidelity (`docs/design/refactor/orchestrator-deterministic-driver.md:21-48`). It also makes "subagents can't spawn subagents" irrelevant, because the driver process is the spawner (`:78-80`). *Trade-off:* every new failure shape needs a new state flag and a new route. `StoryBuild` now has 24 fields (`workflow-vocabulary.ts:108-195`), and the CHANGELOG is largely a history of new routes (issues #196-#202).
2. **Artifact-as-API: state is re-derived from disk every iteration.** *Why:* crash- and context-reset safety, `--detach` resumption, and a single source for `consort-next`. Warm Claude sessions are only an optimization ("correctness never depends on the retained session", `claude-runner.ts:650-656`). *Trade-off:* state is split across `pipeline.json`, cycle files, marker files, `gates.json`, and SCM state, which invites "split-brain" bugs. For example, "Finding 27": a revised story was re-deployed because its old cycle files still read as all-green (`CHANGELOG.md:1238`).
3. **One serial build lane per feature (FIFO, `build_active` ≤ 1).** *Why:* simplicity, one experiment branch and database at a time, and no merge races. *Trade-off:* throughput. N≥2 parallel experiments are designed but not wired (§8).
4. **Honest GREEN means the orchestrator runs the real suite on an ephemeral Lakebase branch.** *Why:* an earlier version "hardcoded passed:true – which faked the runner contract and shipped a false-green" (`cycle-record.ts:568-573`). Branching makes an isolated fork cheap enough to run on every verify (`ephemeral-verify.ts:10-16`). *Trade-off:* every verify starts the app and creates up to three branches (Python) (`deploy.ts:990-1076`).
5. **Default "story" granularity.** One RED turn writes the whole story's tests, one GREEN makes them pass, then one review and one refactor (`orchestrator-effects.ts:178-183`). *Why:* wall-clock and cost. *Trade-off:* this is less strict TDD. "Contract" stories (drop, rename, cleanup) automatically drop to per-AC granularity, chosen by a regex on the story id (`orchestrator-derive.ts:160-174`).
6. **Bounded self-heal loops before a human.** Assess→repair runs at most 3 rounds (`consort/smells/supersession.ts:232`). Reflect→revise runs at most 4 laps, with a check that the test-list fingerprint changed between laps (`consort/smells/smells.ts:871`, `orchestrator-probe.ts:590-609`). Other spec smells get 1 revise (`:605`). The handoff retry is 1 (`orchestrator-expect.ts:244`). The deploy re-verify and the refactor/deploy assess steps are one-shot. *Trade-off:* cost when a loop repeats, and a correctness risk if a counter can reset (§8, item 1).
7. **Fail-closed HITL gates, with one interface and two implementations (human, Human Proxy).** Headless proxy mode is refused unless an explicit CI or `AUTO_CONTINUE` signal is present (`drive.cli.ts:1241-1253`). The default mode is `interactive` (`consort/config/consort-config-file.ts:125`). *Trade-off:* human latency at every gate. The Human Proxy exists to make capture, replay, and CI identical to interactive runs (`MASTER-CANONICAL-PROCESS.md:29-37`, invariant 5).
8. **Deterministic gates run before LLM gates.** Examples: the structural test-list gate before the reflect critic (`orchestrator-drive.ts:97-102`), layering, test smells, and migration history. *Why:* an LLM lap is slow and expensive (CHANGELOG 0.3.101-0.3.102). *Trade-off:* a growing catalogue of regex heuristics (for example, 12 test-smell kinds in `consort/architecture/test-smell-clean.ts:44-56`) that need tuning for false positives (CHANGELOG 0.3.101 "Fixed").
9. **Record/replay plus a manifest-driven step executor.** A seven-phase Template Method (`consort/orchestrator/turns/step-executor.ts:1-34`) with JSON manifests declaring inputs, outputs, channels, validators, and `agentOptions` (`consort/orchestrator/steps/manifests/README.md`). *Why:* reproducibility, per-turn optimization experiments, and a single routing authority. *Trade-off:* a large meta-framework (evaluation, optimize, corpus, turn recorder) relative to the product path.
10. **Role prompts as a store of lessons learned.** The eight role prompts total about 176 KB. The Navigator prompt alone encodes dozens of failure modes, such as whole-table aggregates, `vi.mock` temporal dead zones (TDZ), and port-swapped seeds (`skills/consort/agents/navigator.md:45-48`). *Trade-off:* prompt weight becomes latency and cost. The optimize log finds `effort=low` is "the dominant win" (`OPTIMIZE-RUN-LOG.md:353`).
11. **Per-step model tiering in manifests.** For example, `driver-green` uses opus with medium effort, `navigator-red` sonnet with low, `spec-author-breakdown` sonnet with low (`consort/orchestrator/steps/manifests/*.json`, `agentOptions`). This is resolved per turn by `modelFor` (`consort/orchestrator/settings/project-settings.ts:131-141`).
12. **Committed `dist/` with a git-URL or version pin (`kit-ref`), and a substrate extracted into `lakebase-scm-utils`.** *Why:* zero-build consumption and an immutable version pin (`bin/lakebase/create-project.cli.ts:327-336`). *Trade-off:* an 83 MB repo and the risk of `dist/` drifting from source. A test, `tests/bdd/dist-bins-shipped.test.ts`, guards that every bin in `dist/` is git-tracked.

---

## 5. Databricks platform features used

| Feature | How Consort uses it | Evidence |
|---|---|---|
| **Lakebase projects and branches** (serverless Postgres, copy-on-write) | One Lakebase project per app. Tiers are `main` (the default/production branch) and `staging`. The claimed feature branch, each per-story experiment branch, each ephemeral verify child, and `ci-pr-N` are all branches. Created with `databricks postgres create-branch <project> <name> --json {spec:{source_branch, ttl \| no_expiry}}`, with automatic recovery when a TTL exceeds the workspace cap (probes `history_retention_duration`) | substrate `scripts/lakebase/branch-create.ts:280-350`; `experiment.ts:359-367`; `ephemeral-verify.ts:69-100` |
| **Lakebase endpoints and OAuth DB credentials** | `ensureEndpoint` (poll until a host exists), then `generate-database-credential` to mint a token as the Postgres password. `.env` stores only metadata; the app mints its own tokens | substrate `paired-branch.ts:370-405` (`ensureEndpoint` at `:381`); `get-connection.ts:156-181` |
| **Branch lifecycle hygiene** | Ephemeral verify branches carry TTL `3600s` and are deleted in `finally`. `deletePairedBranch` removes both the Lakebase and git branches. `cleanup-orphans.yml` runs weekly to remove orphaned `ci-pr-*` branches. `orphan-project-sweep` handles leaked test projects | `ephemeral-verify.ts:25,92-98`; `templates/.../cleanup-orphans.yml:1-13`; `consort/setup/orphan-project-sweep.ts:1-15` |
| **Pre-migration snapshot** | `merge.yml` cuts a `pre-migrate-pr-<N>` backup branch (via `lakebase-cut-backup`) before migrating a tier | `templates/project/common/.github/workflows/merge.yml:251-298` |
| **Connection attribution** | `PGAPPNAME=consort/<version>` labels every Lakebase connection a Consort drive opens | `templates/project/common/scripts/post-checkout.sh:25-32`; `drive.cli.ts:1159-1161` |
| **Databricks CLI v1+ and auth** | Every Lakebase operation shells out to the CLI. Before any agent spawns, the drive runs a `databricks auth token --force-refresh` preflight so an expired OAuth refresh token fails fast instead of hanging a test hours later. CI uses `DATABRICKS_AUTH_TYPE=pat` | `drive.cli.ts:1255-1275`; `merge.yml:252-265` |
| **Databricks Apps** | The substrate generates `app.yaml` + `databricks.yml` with a `postgres` resource (`valueFrom: postgres`). Only the live test tier exercises it; `consort-deploy` supports only `type: local` | substrate `deploy-app-yaml.ts:1-21`; `consort/deploy/deploy.ts:215-222` |
| **Genie Code** | `install.sh --install-to-genie` uploads the skills to `/Users/<me>/consort-skills/<skill>` with `databricks workspace import-dir` | `install.sh:222-242` |
| **Agent Bricks Knowledge Assistant + UC Volumes** | The release process copies docs to a UC Volume and runs `databricks knowledge-assistants sync-knowledge-sources` for the `#consort-for-app-dev` Slack bot | `scripts/refresh-kb.sh:1-44`; `CONTRIBUTING.md:233` |
| **devhub skills** | `databricks-core` and `databricks-lakebase` are vendored at a pinned devhub SHA, fetched during `prepare` | `devhub.lock`; `.gitignore:30-31` |
| **SDKs** | `@databricks/appkit`, `@databricks/lakebase`, `pg` | `package.json` dependencies |

**Failure and cleanup semantics (Lakebase).**
- **Paired branch creation is not transactional.** Once the Lakebase branch exists, later failures (READY wait, git branch, `.env` sync) become `warnings` rather than a rollback, and a retry reuses the branch idempotently (substrate `paired-branch.ts:290-301`). Consort turns a skipped `.env` sync into a hard cut failure, because it would otherwise surface about 10 turns later as an opaque Alembic connect error (`experiment.ts:368-383`).
- **Accept is ordered and fail-closed:** git merge, then migrate the feature's DB, then tear down. A failed merge preserves the experiment for retry; a failed migration skips teardown so the state is kept for diagnosis (`consort/experiment/experiment-lifecycle.ts:80-104`).
- **Teardown is best-effort.** `deletePairedBranch` never throws and returns per-side warnings (substrate `paired-branch.ts:415-460`). Ephemeral verify children are deleted in `finally`, with TTL as the backstop.
- **Re-cuts are clean.** A re-cut after a discard or redesign passes `--reset-stale-branch`, which drops the polluted paired branch before re-forking (`experiment.ts:342-353`; `orchestrator-drive.ts:118-127`).
- **Tier protection.** Build and experiment commits cannot land on a protected tier (`assertCommitTargetNotProtected`, `cycle-record.ts:118-121`), and a migration aimed at a tier is refused unless it is the promote path (`TierMigrationRefusedError`, substrate `schema-migrate.ts:299-322`).
- **Promote merges tolerate slow migrations.** They wait for the downstream migrate with `--migrate-timeout-nonfatal`: a slow run is a warning, but a migrate that completes with a failure is fatal (`orchestrator-effects.ts:1984-1994`).
- **Tier snapshots.** `merge.yml` deletes the pre-migrate snapshot on success and preserves it on failure (`merge.yml:242-250`).

Explicitly **not** used: Delta, Spark, Lakeflow, Jobs, notebooks, and warehouse compute. A Unity Catalog foreign catalog is described as peripheral (`docs/positioning.md:65-73`, FAQ).

---

## 6. Patterns worth stealing

**6.1 A pure brain plus an effects seam.** Decide in a pure function, act through an injected interface, and test both hermetically (`orchestrator-drive.ts:244-249`, `:362-376`):
```ts
export function nextTransition(state: DriveState): WorkflowAction {
  // Escalation pre-empts everything: it never false-greens past the problem or
  // silently stalls (the await-acceptance spin). Shared with the design-only bound.
  const preempt = escalationPreempt(state);
  if (preempt) return preempt;
  ...
  // 1. Finish/advance the story the build lane is already on.
  if (state.buildActive) {
    return nextBuildAction(state.buildActive, state.stories[state.buildActive].build);
  }
  // 2. Lane idle: dispatch the first gate-approved, not-yet-accepted story.
  for (const story of state.storyOrder) {
    const v = state.stories[story];
    if (v?.gateApproved && !v.build.accepted) return { kind: "dispatch", story };
  }
  // 3. Otherwise advance the design lane (reusing the design sub-machine).
  const design = nextDesignAction(toDesignView(state));
  // 4. Design lane exhausted + nothing left to build => every story is accepted.
  if (design.kind === "design-complete") return { kind: "feature-complete" };
  return design;
}
```
The loop test drives a whole feature with in-memory "replay" effects and the real derivation (`tests/bdd/orchestrator-drive-loop-e2e.test.ts:1-9`).

**6.2 A stall detector: if an effect didn't change the state, fail loudly** (`orchestrator-run.ts:342-348`):
```ts
    const signature = JSON.stringify(action);
    // A sanctioned retry re-issues the SAME action by design (the responder's
    // contract is still outstanding), so skip the generic stall check this pass.
    if (!retrying && signature === previousSignature) {
      throw new DriverStalledError(action, i);
    }
    previousSignature = signature;
```
This is also what makes a refused gate "fail closed" in practice. A proxy that skips a gate exits 0, the next iteration derives the same `approve-*-gate` action, and the loop throws.

**6.3 A handoff contract with exactly one informed retry** (`orchestrator-expect.ts:291-306`):
```ts
    const h = this.outstanding[idx];
    if (h.satisfiedBy(state)) {
      this.outstanding.splice(idx, 1);
      this.attempts.delete(h.signature);
      return { kind: "met", handoff: h };
    }
    const attempt = (this.attempts.get(h.signature) ?? 0) + 1;
    this.attempts.set(h.signature, attempt);
    if (attempt > this.maxRetries) {
      throw new ProtocolViolationError(
        h,
        `the expected artifact did not satisfy its contract across ${attempt} attempts ` +
          `(it is absent, empty, OR present-but-nonconformant on disk – the orchestrator re-checked it and it still fails)` +
          (h.remediation ? `. To satisfy it: ${h.remediation}` : ""),
      );
    }
    return { kind: "retry", handoff: h, detail: handbackMessage(h, attempt), attempt };
```
The retry prompt tells the model "prose describing the artifact is NOT the artifact" (`:215-225`), and the prompt is consumed only once (`orchestrator-effects.ts:472-488`).

**6.4 Verify on a disposable database branch: fork, run, and always delete, with a TTL as backstop** (`ephemeral-verify.ts:69-100`):
```ts
  await create({ instance: args.instance, branch: args.childName, parentBranch: args.parentBranch, ttl });
  try {
    await waitReady({ instance: args.instance, branch: args.childName });
    const dsn = await resolveDsn({ instance: args.instance, branch: args.childName, database: args.database });
    return await run(dsn);
  } finally {
    // Never fail the verify on teardown – the TTL reaps a leaked child.
    try {
      await remove({ instance: args.instance, branch: args.childName });
    } catch {
      /* best-effort; Lakebase TTL is the backstop */
    }
  }
```
Every Lakebase operation is an injectable seam (`:45-49`), so this is unit-testable without the cloud. On a Databricks engagement, the same shape applies to "clone a table, run the test, drop the clone".

**6.5 Hash artifacts so that formatting changes are ignored but real edits are caught** (`consort/gates/gate-hash.ts:35-64`, trimmed):
```ts
export function normalizeForHash(content: string): string {
  let normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  normalized = normalized
    .split("\n")
    .map((line) => line.replace(/[ \t]+$/, ""))
    .join("\n");
  normalized = normalized.replace(/\n{3,}/g, "\n\n");
  return normalized;
}
export function hashArtifact(content: string): string {
  return createHash("sha256").update(normalizeForHash(content), "utf8").digest("hex");
}
```
The header argues the trade-off explicitly. Too strict, and a prettier run trips the gate so users disable it. Too loose, and real edits slip through (`:9-15`). A related pattern is to fingerprint only the design-identity fields, projecting out fields the build mutates, such as `status` (`consort/pipeline/design-fingerprint.ts:37-84`).

**6.6 A file-lock mutex with `O_EXCL` (`"wx"`) and exponential backoff** (`consort/gates/gates-lock.ts:88-103`):
```ts
  while (!acquired && attempts <= maxRetries) {
    try {
      const fd = openSync(lockPath, "wx");
      writeFileSync(fd, String(process.pid));
      closeSync(fd);
      acquired = true;
    } catch (err) {
      if (!isEexist(err)) throw err;
      attempts += 1;
      if (attempts > maxRetries) {
        const heldByPid = readHeldByPid(lockPath);
        throw new GatesLockBusyError(featureId, heldByPid, maxRetries);
      }
      sleep(initialBackoffMs * 2 ** (attempts - 1));
    }
  }
```
The code pairs this with an atomic temp-file-plus-rename write (`gates.ts:113-132`). The PID written into the lock file makes a crashed holder easy to diagnose.

**6.7 A fail-closed gate that checks the evidence, not just that the file exists** (`gate-conformance-guard.ts:988-1001`):
```ts
      if (parsed.reachable !== true) {
        return { reason: "deploy-evidence records reachable=false (app not reachable on the target)" };
      }
      if (parsed.verify?.passed !== true) {
        return {
          reason:
            `deploy-evidence records verify.passed=false (feature-verify did not pass against the running app). ` +
            `An approve cannot clear stale failed evidence (issue #198): fix the cause, then re-run the deploy ` +
            `\`./scripts/lk consort-deploy --target local --feature <F>\` (kill any stale deploy server first: ` +
            `\`lsof -tiTCP:8000 | xargs kill\`) to rewrite the evidence, and approve then.`,
        };
      }
      return withConformance({ "deploy-evidence.json": evidence });
    }
```
The Human Proxy follows the same rule: "a gate is only approved when its REAL artifact exists on disk… SKIPS… instead of fabricating one" (`consort/gates/human-proxy.ts:21-37`).

**6.8 Idempotent escalations keyed by a deterministic ID** (`consort/gates/escalation.ts:89-105`):
```ts
export function escalationId(parts: { source: string; feature_id?: string; story_id?: string; ac_id?: string }): string {
  return [parts.source, parts.feature_id, parts.story_id, parts.ac_id]
    .filter(Boolean)
    .join("__")
    .replace(/[^A-Za-z0-9_.-]/g, "-");
}
...
  const id = esc.id ?? escalationId(esc);
  const file = escalationFile(consortDir, id);
  const existing = readEscalationFile(file);
  if (existing && !existing.resolved_at) return existing;
```
Each escalation also records its own `how_to_resolve` instructions and never deletes records (`:114-118`, `:182-201`).

**6.9 Pin the agent to exact IDs instead of "do the next thing"** (`orchestrator-effects.ts:361-366`):
```ts
    const list = batch.map((b) => `${b.id} [ac ${b.ac_id}]: "${b.description}"`).join("; ");
    return (
      `Write the failing tests (RED) for the WHOLE story ${story} in this one turn, EXACTLY these ${batch.length} item(s)` +
      ` across all its ACs, in order: ${list}. Write ALL of them now and ONLY these; do NOT add or drop items, the` +
      ` orchestration stamps ONE whole-story batch RED cycle for exactly these ids, and any mismatch is a defect.`
    );
```
The prompt and the recorder read the same `nextPendingBatch`, so they cannot drift apart (`cycle-record.ts:411-427`).

**6.10 Classify failure signatures before routing a "fix".** `isAuthExpiredSummary` and `isProvisioningFaultSummary` (`cycle-record.ts:481-497`), plus the transient-API and prompt-too-long regexes (`consort/session/context-budget.ts:102-127`), stop the system from sending an infrastructure fault to a code-repair agent. That repair could never converge.

**6.11 Assert runtime invariants loudly.** `assertNotStrandedAgentTurn` refuses to run any agent turn that bypassed the recording and validation path (`executor-dispatch.ts:217-228`). The dashboard's `resolveContained` realpath-checks request paths after a review found `/etc/passwd` served through a symlink (`apps/dashboard/lib/safepath.ts:1-30`).

---

## 7. Scaling characteristics

**What grows, and with what.**
- **Turns per story.** The design lane takes about 5-8 turns per story: ACs, architect (or deterministic projection), DBA, test strategist, reflect, plus up to 4 revise laps. The build lane takes at least RED, GREEN, REVIEW, and REFACTOR, plus self-heal turns (assess, repair, supersede, deploy scope). The one full measured run had **119 agent turns, 709.7 min of compute, $139.18, and 2.45M output tokens for 2 features and 6 stories** (`consort/optimize/OPTIMIZE-INDEX.md:51-56`). That is about $23 and 2 compute-hours per story. The build lane was about 90% of wall-clock time, and `driver/green` alone was 46.4% (`:58-75`).
- **Verification cost per GREEN.** Each GREEN (and each REFACTOR) starts the app, forks up to three ephemeral Lakebase branches for a Python project (the `not migration` pass, the `migration` pass, and the client pass), and runs the **full** accumulated suite (`deploy.ts:990-1076`; the Driver prompt calls the orchestrator's run "the single authoritative FULL run", `skills/consort/agents/driver.md:65-66`). So verify time per cycle grows linearly with delivered stories, and total verify cost over a project's life grows roughly quadratically (inferred).
- **The worst case is schema contract changes.** Two expand/contract migration stories took 73% of the measured run: 11 GREEN turns on one story and 8 on another, in repeated green → assess → repair churn (`OPTIMIZE-INDEX.md:77-79`). Contract stories are automatically switched to per-AC granularity for this reason (`orchestrator-derive.ts:149-174`).
- **State-derivation work per iteration.** `readState` re-reads `pipeline.json`, the test lists, every cycle file, and every marker, with no caching (`orchestrator-effects.ts:2156-2179`). When a green-failure marker exists, the probe calls `readGreenFailure` up to six times per story (`orchestrator-probe.ts:405-496`), and each call spawns `git rev-parse` and `git status` (`supersession.ts:260-274`). This is fine for a handful of stories but is not built for hundreds (inferred).

**Bottlenecks.**
1. **One serial build lane.** `dispatchNext` refuses to dispatch while `build_active` is set (`story-pipeline.ts:268-275`). N≥2 parallel experiments are designed, and partly built in the optimize harness (worktree plus Lakebase branch per candidate), but not wired into the drive (`docs/design/parallel-per-story-experiments.md:5-18`).
2. **LLM output tokens.** "Output volume is the wall (avg driver/green turn = 45k output over 14 min)" (`OPTIMIZE-INDEX.md:56`).
3. **A single machine.** `consort-deploy` supports only local targets (`deploy.ts:215-222`); there is one drive per project (a pid file, `drive.cli.ts:1186-1188`); the gate lock is safe only on a local filesystem (`gates-lock.ts:19-22`); and E2E tests need free-port juggling (CHANGELOG 0.3.95-0.3.96).
4. **CI runs on self-hosted runners** (`templates/.../pr.yml:18`).
5. **Human latency at every HITL gate.** `interactive` is the default (`consort-config-file.ts:125`).

**Cost controls that exist.**
- Per-step model and effort tiering in the manifests. The logged effort=low sweeps cut test-strategist time from 585.5 s to 173.6 s and navigator RED time by 88% (`OPTIMIZE-RUN-LOG.md:334-352`).
- An optional per-role `--max-budget-usd` (`claude-runner.ts:786-788`).
- Story-scoped warm sessions with a context-budget guard (`context-budget.ts:85-92`).
- The deterministic pre-LLM gates, which exist largely to avoid spending LLM laps (CHANGELOG 0.3.101).

**Cost controls that are missing.**
- There is no live wall-clock or cycle budget. `checkPerExperimentCap` is dead, and `snapshotBudget` depends on a `plan.json` that is never written in live runs (`consort/session/budget.ts:21-24`; `analyzeForGate`/`writePlan` have zero callers, `docs/design/parallel-per-story-experiments.md:10`).
- Lakebase cost leaks are possible. Experiment branches are `noExpiry` (`experiment.ts:366`) and are reaped only on accept or discard; stale ones are detected, not deleted (`consort/setup/stale-branches.ts:1-12`). Ephemeral verify children have a 1 h TTL, and `ci-pr-*` branches are cleaned weekly.

**How I would scale it (inferred).**
- Promote the optimize harness's worktree-plus-paired-branch executor into the build lane for independent stories.
- Run test-impact-based verification per cycle, and the full suite only at acceptance and deploy.
- Cache the derived state per iteration and invalidate it by file modification time.
- Add a Databricks Apps deploy target, since the substrate already generates `app.yaml`/`databricks.yml`.
- Add a hard per-story dollar and time budget enforced in `runDriver`.

---

## 8. Risks, bugs, smells, and questionable logic

Each item is labeled **CONFIRMED** (I traced it in code, or reproduced it) or **SUSPECTED**.

1. **The bound on the repair loop can silently reset. CONFIRMED at unit level; end-to-end SUSPECTED.**
   - `greenOpenCycle(repair)` calls `markRegressionFixAttempted` first (`cycle-record.ts:557-559`). That calls `readGreenFailure` (`supersession.ts:423-437`).
   - `readGreenFailure` **deletes** the record whenever the working tree's `git status --porcelain` fingerprint has changed since the record was written (the issue #202 staleness rule, `supersession.ts:286-296`).
   - A Driver repair that creates a new file, or touches a previously clean tracked file, therefore makes the record vanish, so the attempt is never counted. The still-failing verify then takes the "first failure" branch and writes a fresh record with no `fixAttempts` (`cycle-record.ts:703-743`). `MAX_REGRESSION_FIX_ATTEMPTS = 3` (`supersession.ts:232`) never trips.
   - I reproduced this with the real functions in a scratch test. Five rounds in which the repair added a file left `fixAttempts` at `[null,null,null,null,null]`. Rounds that edited only already-dirty files counted correctly.
   - The stall guard compares only consecutive actions (`orchestrator-run.ts:342-348`), so the alternating assess → repair pattern is not caught before `MAX_ITERATIONS = 10_000` (`:180`).
   - The fingerprint is wrong in both directions. Porcelain lines carry status and path but not content, so a second edit to an already-dirty file is invisible (a false negative), while a new file counts as a change (a false positive).
   - Fix: carry `fixAttempts` in a counter that is not subject to staleness (for example, keyed by AC in `smells.json`), or stamp `treeState` after the repair rather than before.
2. **"Tests are immutable within a unit of work" is not enforced at the file level. CONFIRMED.**
   - The Driver has `Write, Edit, Bash` (`skills/consort/agents/driver.md:8`).
   - Nothing hashes the RED test files and compares them at GREEN. The Driver's executor validators check only that code exists and that it logged (`consort/orchestrator/validators/conformance/validator-registry.ts:167-190`, `:337`).
   - The purpose-built primitives are dead in production: `mutateTestList` (`consort/test-list/mutate-test-list.ts:83`) and `verifyGateIntegrity` (`consort/gates/verify-gate-integrity.ts:42`) have zero production callers.
   - `run-tests.sh` maps pytest exit code 5 ("no tests collected") to success under the marker passes (`templates/project/common/scripts/run-tests.sh:120-127`).
   - A weakened or deleted test is therefore caught only by the prompt rules, the Navigator's LLM REVIEW, the Navigator's `test-deletion-attempt` flag, and a few deterministic test-smell detectors. The test *list* (the plan) is effectively frozen (see item 3). The test *code* is not.
3. **"Frozen at a hashed gate" is only partly implemented. CONFIRMED.**
   - The per-story spec gate, the one the design lane actually blocks on, stores `spec_hash` only when one is passed. The drive's `approve-gate` never passes one (`orchestrator-effects.ts:1725-1729`), and neither does the human CLI (`approve-gate.cli.ts:113`; `story-pipeline.ts:373`).
   - Hashing does happen for the sprint plan gate (`sprint-gates.ts:135`) and for the feature deploy and promote gates (`approve-gate.ts:107-110`), but those hashes are never re-verified (item 2).
   - The freeze that works in practice is structural: approved stories are skipped by the design lane (`orchestrator-drive.ts:70`), and the `design_fingerprint` stamped at cut forces a re-cut if the test list changes (`orchestrator-derive.ts:193-201`).
4. **An LLM turn is labelled "deterministic-agentless" and runs outside the executor. CONFIRMED.**
   - `deterministicAgentless` says `estimate-committed` runs "no LLM" (`executor-dispatch.ts:162-182`; also `orchestrator-effects.ts:2199-2203`, `MASTER-CANONICAL-PROCESS.md` §0.5).
   - But `commandsForAction` builds a `claude` command for it, with its own prompt (`orchestrator-effects.ts:598-613`, `:1585`), and the repo's own test asserts that (`tests/bdd/orchestrator-effects.test.ts:324-338`).
   - So the "no agent turn on the legacy path" guard lets exactly one real agent turn bypass the executor's recording and validation. The `verify-artifact` check still runs.
5. **The cycle-history smell detectors are never run. CONFIRMED.** `detectAll` and `runDetectorsForScope` (`smells.ts:502-515`, `:960-973`) have no production caller, although `SKILL.md:289-301` tells agents to run them "after every cycle". Cycle-stall, test-cost-spiral, fragility, and test-deletion-attempt surface only if an agent chooses to emit `smell.flagged`.
6. **Documented N≥2 features are dead or unimplemented. CONFIRMED.** The scaffolded `/build` advertises `--parallel-experiments N` (`templates/project/common/.claude/commands/build.md:12`), but no TypeScript parses it. `analyzeForGate`, `writePlan`, `recordPlan`, `promoteExperiment`, `synthesizeExperiments`, `checkPerExperimentCap`, `runExperimentsInParallel`, and `withdrawGate` have zero live callers (grep; confirmed by the repo's own `docs/design/parallel-per-story-experiments.md:9-14`).
7. **Telemetry comments contradict the code. CONFIRMED.** The emitter header says "the DEFAULT sink is a local no-op: nothing phones home until a human flips the real endpoint" (`consort/telemetry/emitter.ts:8-10`). The drive says telemetry needs an "interactive TTY" and that "the sink defaults to a local no-op" (`drive.cli.ts:1378-1382`). In fact `endpointMode` defaults to an armed Azure endpoint with sign-off on (`emitter.ts:138-154`), and `TELEMETRY.md` says the TTY condition "is GONE". Only allowlisted, content-free fields are sent, so the privacy impact is low, but comment drift inside a privacy feature is a governance smell.
8. **The MCP server bypasses the gates. CONFIRMED (impact SUSPECTED).** The plugin automatically registers an MCP server (`.mcp.json`) whose tools include `lakebase_github_token`, which returns the raw token into the model's context (`apps/mcp-server/tools.ts:134-157`), plus ungated `lakebase_pr_merge` and `lakebase_pr_merge_paired` (`:379-432`). The drive's promote gate can be sidestepped by any agent session holding these tools. `applySchemaMigrations` does refuse protected tiers (substrate `schema-migrate.ts:364-367`).
9. **Some state writes are not atomic. CONFIRMED (impact SUSPECTED).** `writePipeline` is a plain `writeFileSync`, and `readPipeline` calls `JSON.parse` with no guard (`story-pipeline.ts:152-162`). `writeGates` uses temp-file plus rename (`gates.ts:113-132`). The smells log, the escalations, and `green-failure.json` are plain writes too. A crash mid-write would corrupt the central state file and leave the drive unable to derive state.
10. **A read with destructive side effects. CONFIRMED.** `readGreenFailure` deletes files (`supersession.ts:291-295`) and is called from `readState` probes (`orchestrator-probe.ts:405-496`), so deriving state can change state. It also spawns two git subprocesses per call.
11. **The `done` step force-checks-out the parent branch. CONFIRMED (impact SUSPECTED).** It runs `git checkout -f <parent>` (`orchestrator-effects.ts:2032`), which discards uncommitted edits to tracked files, a human's included. `prepare-pr --force` skips the dirty-tree refusal (`:1956`). Both are justified as ".consort churn only", but neither checks that claim.
12. **Experiment branches can leak. CONFIRMED.** Experiment paired branches are created `noExpiry` (`experiment.ts:366`), and the drive never passes `--ttl` (`orchestrator-effects.ts:1739-1765`). A crashed run leaves a billed Lakebase branch that is detected (`stale-branches.ts`) but never reaped automatically.
13. **The pre-migration snapshot covers the wrong branch. SUSPECTED; the behavior is CONFIRMED in the template.** `merge.yml` snapshots the **default (production)** branch "not the merge-target git branch" (`templates/project/common/.github/workflows/merge.yml:273-281`). A promotion into `staging` therefore migrates staging with no staging rollback snapshot. That may be intended, since staging is disposable, but it is undocumented.
14. **Bounded autonomy is recorded as a PO decision. CONFIRMED.** `revise-route` is not a HITL action (`workflow-vocabulary.ts:534-544`), so even an interactive run applies the "PO's revise decision" automatically through the Human Proxy with approver `human-proxy` (`orchestrator-effects.ts:1548`, `:2060-2097`), up to the revise budget. This is a sound design, but the audit trail says the PO decided.
15. **The spec-gate approve path lacks the HITL assertion. CONFIRMED (impact SUSPECTED).** `approveStoryGate` has no `hitlApproved` check, unlike `approveGate` (`story-pipeline.ts:362-384` versus `approve-gate.ts:79-81`). Human versus proxy is distinguished only by the approver string. Nothing in code stops the interactive LLM session, which has Bash, from running `consort-approve-gate --approver <name>` itself. Only the prompt contract governs it (`skills/consort/references/orchestrator-contract.md`).
16. **A naming heuristic controls build granularity. CONFIRMED.** `isContractStory` is a story-id regex, `/(drop|remove|delete|rename|…)|dropp|remov|delet|renam|deprecat/i` (`orchestrator-derive.ts:160-164`). A story named "S2-deletion-audit-log" would be forced into slower per-AC mode.
17. **Dead code. CONFIRMED.** `DESIGN_DONE_STATUSES` is never read (`orchestrator-derive.ts:142-147`). `apps/dev-playground` is empty.
18. **Documentation has drifted from code. CONFIRMED.** Stale line citations in `MASTER-CANONICAL-PROCESS.md`, plus the §0.4 and §0.5 claims (§2.6 above); CONTRIBUTING's "~10s" and beta-version scheme; `OPTIMIZE-RUN-LOG.md` "APPLIED WINNERS" versus the manifests; README's "hashed gate" versus item 3.
19. **The "hermetic" tier depends on the network. CONFIRMED.** Two tests fail without the `prepare` step that syncs vendored skills from GitHub (`tests/bdd/deploy-claude-agents.test.ts:138`, `:184`; `.gitignore:30-31`).
20. **"Deploy" is local only. CONFIRMED.** `consort-deploy` rejects any target type except `local` as `unsupported` (`deploy.ts:215-222`). The deploy gate proves working software on the developer machine against the feature's Lakebase branch. Delivery to a real environment happens only through the promote step's PR → CI → merge-migrate.
21. **The two HIL doors are not identical at acceptance. CONFIRMED (impact SUSPECTED).** The drive-performed `accept` runs the fail-closed `consort-ux-clean` brand-icon/reachability gate before merging (`orchestrator-effects.ts:1811-1816`). The interactive door that `consort-next` offers is a bare `consort-pipeline accept` (`orchestrator-logging.ts:371-372`), and that CLI does not run the UX gate (`bin/consort/story-pipeline.cli.ts:331-357`). This breaks the stated invariant that the automated and interactive paths are identical (`MASTER-CANONICAL-PROCESS.md:36-37`). It is partly mitigated, because REVIEW flags a still-dirty UX as a blocking `ux-adherence` smell (`cycle-record.ts:1288`, `:1002-1045`), which pre-empts to HIL.

---

## 9. How to explain Consort to three audiences

**(a) A customer executive.** Consort lets AI agents build your transactional applications while an engineering process, enforced in code, stands between them and production. The agents do the typing, but a deterministic workflow decides what happens next, every "done" is proven by real tests against a disposable copy of a real database, and nothing merges or migrates without your team's sign-off. You get AI speed with an auditable trail of who approved what and why, instead of trusting a chatbot's claim that it worked.

**(b) A customer engineer.** `consort-drive` is a TypeScript state machine. A pure `nextTransition(state)` over on-disk artifacts decides each step, and it spawns `claude -p --agent <role>` only for bounded judgment turns such as writing ACs, tests, and code. Each story is built on its own paired git and Lakebase branch. GREEN means the orchestrator started your app, forked a throwaway Lakebase branch, ran your full pytest, Vitest, or Playwright suite, and passed its migration, layering, and test-smell gates. Failures route to bounded assess and repair loops, then to you. Accepted stories merge with their Alembic, Flyway, or Knex migrations, and promotion goes through your PR CI (a `ci-pr-N` branch) and `merge.yml` migration of the tier.

**(c) An internal Databricks stakeholder.** Consort is a reference agentic-SDLC workload that turns Lakebase's copy-on-write branching into the differentiator. It uses branches per feature, per story, per verify run, and per PR, so the database becomes as easy to branch and test against as code. That capability is expensive to replicate on conventional managed Postgres (inferred). It exercises Lakebase branching, endpoints, OAuth DB credentials, the Databricks CLI, Genie Code skill install, and Agent Bricks (the docs bot). Its telemetry and optimization data (for example, about $23 of LLM spend per story) are useful product signals for Lakebase and for Assistant or Genie Code agent design. It is still pre-1.0 (v0.3.x), and several advertised capabilities, such as parallel experiments, remote deploy, and hash verification, are not yet wired.

---

## 10. Interview-prep angles

**Q1. Why a deterministic state machine instead of letting the LLM orchestrate?**
Routing was already a pure function of recorded state. As an LLM it cost about 99 s per decision, dropped observability events (haiku skipped `phase.*` logs), and invited batching and drift. Code makes routing instant, testable (`tests/bdd/orchestrator-drive.test.ts`), resumable, and impossible for the agent to argue with. LLMs keep only the judgment tasks (`docs/design/refactor/orchestrator-deterministic-driver.md:21-48`).

**Q2. Walk me through a failed GREEN.**
`greenOpenCycle` runs the full verify. If it fails, it first checks for an auth-expired or DB-provisioning signature and escalates or retries once (`cycle-record.ts:590-614`, `:691-702`). Otherwise it writes `green-failure.json` with contract-clean, superseded-test, and test-smell advisories, and the router sends the Navigator to ASSESS. The Navigator can:
- flag superseded prior tests, leading to a labelled Driver `green-superseded` turn;
- record a regression plus a fix, leading to one Driver REPAIR per round, for up to 3 rounds;
- record a regression without a fix, which goes straight to HIL;
- declare a spec defect, which goes to HIL with a `reopen-story --from <role>` recommendation.

(`orchestrator-drive.ts:158-214`; `supersession.ts:232`.)

**Q3. How does Consort stop an agent from weakening tests?**
Honestly, it uses layers, and only some of them are deterministic:
- role separation: the Navigator writes tests, the Driver writes code;
- prompt rules ("fix the code, never the test");
- a superseded-tests allowlist that only the Navigator can create;
- an honest full-suite verify;
- deterministic test-smell and shipped-migration-immutability gates;
- the Navigator's LLM review and its `test-deletion-attempt` blocking smell;
- a frozen test list (gate plus design fingerprint).

There is no RED → GREEN hash of test files, and the purpose-built `mutateTestList` and `verifyGateIntegrity` are unused (§8, item 2). I would add a deterministic guard: record the hash of each test file at RED and refuse GREEN if a file not on the allowlist changed.

**Q4. Why does Lakebase matter here, and what does it cost?**
Copy-on-write branches let every story build against a real, isolated Postgres, and let every verify run on a fresh fork that is deleted afterwards (`ephemeral-verify.ts`). That removes mock drift and shared-staging contamination. The costs are branch lifecycle management (TTLs, orphan sweeps, `noExpiry` leaks), endpoint provisioning and credential minting latency, and quota or TTL caps (`branch-create.ts` TTL recovery).

**Q5. How does it survive a crash or a context reset?**
Everything is on disk and re-derived every iteration; sessions are only a cache. The drive runs `--detach`ed in its own session. It writes `next.json` on every stop, and `consort-next` gives any fresh session the same answer the engine would (`next.ts:1-23`; `drive.cli.ts:1627-1640`). Phase stamps carry an owner so they cannot leak across features (`orchestrator-probe.ts:118-127`).

**Q6. What does "gates fail closed" mean concretely?**
- `approveGate` throws without `hitlApproved` (`approve-gate.ts:79-81`).
- The artifact resolver returns a *reason* instead of fabricating a hash, including the deploy "teeth" check: `reachable && verify.passed` (`gate-conformance-guard.ts:973-1002`).
- A skipped gate re-derives the same action, and the stall detector aborts (`orchestrator-run.ts:345-347`).
- Interactive mode stops before every HITL action (`drive.cli.ts:453-462`), and proxy mode needs CI (`:1241-1253`).

**Q7. How are loops bounded?**
- The expectation ledger allows 1 retry.
- Reflect revise is capped at 4 laps, with a "did the test list change?" check.
- Other spec smells get 1 revise.
- Repair gets 3 rounds.
- Deploy re-verify, deploy assess, and refactor assess are one-shot markers.
- Consecutive-duplicate stall detection, plus `MAX_ITERATIONS` of 10k.
- In the Claude runner: 2 fresh-session retries for context overflow, 5 transient retries, and a 10-minute inactivity kill.

Then mention the #202 interaction bug (§8, item 1). It shows that bounds need counters that cannot be invalidated.

**Q8. How does promotion work, and where do migrations run?**
Accepting a story merges it into the feature branch and applies migrations to the feature's Lakebase branch. The feature then goes `prepare-pr` → `pr.yml` (a `ci-pr-N` Lakebase branch forked from the base: migrate, test, schema diff) → `wait-ci` → promote gate → `lakebase-scm-merge` (merge the PR, delete the feature's Lakebase branch) → `merge.yml` on the push to the tier (snapshot, then migrate the tier's branch). Build and experiment code can never migrate a protected tier (`TierMigrationRefusedError`, substrate `schema-migrate.ts:299-322`).

**Q9. How do they evaluate prompt and model changes?**
A single judged sweep engine runs each candidate (model × effort × tool scope × prompt diet) in isolation, replays every other turn from a recorded corpus, requires conformance *and* a fixed-opus judge against the recorded reference for the same turn, and preserves outputs (`OPTIMIZE-INDEX.md:19-43`). Lessons: effort=low usually wins; haiku under-delivers on reasoning-heavy turns; never apply judge-less winners (the team did once and had to correct it, `OPTIMIZE-RUN-LOG.md:390-411`).

**Q10. What would you fix first?**
(1) The repair-counter reset (§8, item 1). (2) A deterministic test-tamper guard (item 2). (3) Atomic `pipeline.json` writes (item 9). (4) Gate the MCP merge and token tools, or drop them from the plugin's default manifest (item 8). (5) Actually verify the stored gate hashes at build start (item 3).

**Q11. How is the code organized for testability?**
Every effect sits behind a seam: `DriveEffects`, `CommandRunner`, `ExperimentBranchOps`, `EphemeralVerifyOps`, and the `GreenVerifier` injection. The router is pure. The loop has a fake-world end-to-end test. Manifests carry "golden equivalence" tests that pin the command list the legacy path produced (`orchestrator-effects.ts:1434-1453`).

**Q12. What is the Human Proxy, and why is it not a security hole?**
It is the headless implementation of the HIL interface, used for CI, capture, and replay. It approves only real, conformant artifacts, identifies itself as `human-proxy`, and cannot be used without an explicit CI or auto-continue signal. The residual risk is that an interactive LLM session could itself call the human approval CLI (§8, item 15).

**"If asked to extend X, I would…"**
- **Parallel stories or experiments:** follow the repo's own M0-M8 plan. Lock N=1 behavior with tests first, parameterize `EXPERIMENT_SLUG`, model a set of experiments per story, and run lanes in git worktrees plus paired branches with a concurrency cap, reusing the per-worktree isolation in `claude-runner.ts`. Keep `nextTransition` pure by emitting N `cut-experiment` actions.
- **A Databricks Apps deploy target:** add `type: databricks-app` to `resolveDeployTarget`. Reuse the substrate's `app.yaml`/`databricks.yml` generation and the endpoint probe. Write the same `deploy-evidence.json` shape so the gate's "reachable && verify.passed" check is unchanged.
- **A deterministic test-tamper guard:** at `beginCycle`, record `sha256` of each test file that covers the cycle's test IDs. At `greenOpenCycle`, fail with a `test-deletion-attempt` escalation if any hashed file changed and is not in `superseded-tests.json`. Also refuse pytest exit code 5 for the main pass.
- **A new role (for example, a Security Reviewer):** add a role `.md`, a manifest (inputs, outputs, validator), a `DriveAction` variant, and a design-lane predicate plus a probe field. Extend `expectationFor` and `executorDispatched`, and add pure transition tests first.
- **Gate integrity:** call `verifyGateIntegrity` in `cut-experiment` and `prepare-pr` against the stored hashes, and pass `--spec-hash` on per-story approval.

---

## 11. AI-stewardship lessons

### 11.1 Failure modes this repo designs against, and the mechanism for each

| Failure mode (README's list plus others seen in the CHANGELOG) | Mechanism | Deterministic? | Evidence |
|---|---|---|---|
| **Marks "done" with no test** | Progress is driven by the test list: a story is `codeWritten` only when *every* test-list item has a GREEN cycle. Agents never write cycle files; the orchestrator stamps RED and GREEN. `markGreen` refuses without a recorded runner outcome. Acceptance requires `deployVerified`; the deploy gate requires `verify.passed` | Yes | `orchestrator-probe.ts:371-387`; `run-cycle.ts:294-306`; `orchestrator-drive.ts:235-239`; `gate-conformance-guard.ts:973-1002` |
| **Fakes green** (the orchestrator itself once hardcoded `passed:true`) | Honest verify: the orchestrator starts the app and runs the full suite on an ephemeral Lakebase fork, with post-pass deterministic gates | Yes | `cycle-record.ts:568-575`, `:622-663`; `deploy.ts:929-1107` |
| **Drifts off the request, batches ahead, wanders** | One story at a time in design (`nextDesignAction` advances only the first un-gated story). The gate hard-fails if other un-gated stories already have ACs. RED is pinned to exact test IDs. Breakdown is checked against `registration.json`; story independence is checked. Prompts include `deliveredFeaturesDirective`. The reflect critic checks cross-story conflicts | Mostly | `orchestrator-drive.ts:67-111`; `story-pipeline.ts:318-336`, `:429-458`; `orchestrator-effects.ts:351-366`, `:529-539` |
| **Weakens a test to reach green** | Role split, prompt rules, a Navigator-owned supersede allowlist, a frozen test list (gate plus fingerprint re-cut), test-smell gates, shipped-migration immutability, a spec-defect route back to design (so the Driver never "fixes" a wrong test), and a Navigator review flag | **Partly** (no test-file hash; §8, item 2) | `driver.md:66-68`; `orchestrator-effects.ts:414-432`; `migration-history-clean.ts:1-18`; `orchestrator-drive.ts:177-194` |
| **Tangles layers** | The architect declares `layers`/`may_import`/`persistence_invariants` (the gate blocks if they are missing). A deterministic `consort-layering-clean` flags `layering-violation`, which triggers a REFACTOR turn, then HIL. Project conventions are pinned by the first feature, and a later divergent layout blocks the gate | Yes (regex and static analysis) | `gate-conformance-guard.ts:235-297`; `layering-clean.ts:1-17`, `:153`; `escalation.ts:68-73` |
| **Loses the plan across a context reset** | All state on disk, re-derived each iteration; sessions are an optional cache with a context-budget guard; `next.json` and `consort-next` from the same engine; `--detach`ed drive; owner-stamped phase | Yes | `orchestrator-effects.ts:2156-2179`; `context-budget.ts:85-92`; `next.ts:1-23`; `orchestrator-probe.ts:118-127` |
| **Narrates an artifact instead of writing it, then claims it "already exists"** | An expectation ledger with one informed handback ("prose describing the artifact is NOT the artifact"), `verify-artifact` after each turn, and deterministic reset of an incomplete breakdown | Yes | `orchestrator-expect.ts:215-225`; `orchestrator-effects.ts:1592-1605`; `story-pipeline.ts:229-250`; CHANGELOG FEIP-8024 |
| **Writes to a hallucinated or malformed path** (relative paths, `~/dev/...`) | Absolute artifact roots in every prompt, an out-of-root guard, and relocation of stray trees | Yes | `orchestrator-effects.ts:245-265`, `:561-567`; `claude-runner.ts:943-985`; CHANGELOG FEIP-8006/8038 |
| **Invents file shapes** (for example `tests` instead of `items`, or `status:"red"` instead of `red_at`) | Agents never write orchestration state. Schemas and conformance validators run, and readers normalize at a single read point | Yes | `cycle-record.ts:16-19`; `test-list.ts:39-60` |
| **Rewrites history to satisfy a test** (edits shipped migrations) | A `git diff` of migration directories against the fork point fails the cycle and blocks `prepare-pr` | Yes | `cycle-record.ts:629-642`; `orchestrator-effects.ts:1949-1957` |
| **Fabricates missing infrastructure** (its own conftest) | A `scaffold-defect` blocking smell and a prompt rule | No (prompt plus agent flag) | `escalation.ts:53-56`; `driver.md:100` |
| **Spins forever** | Budgets, one-shot markers, the stall detector, and failure-signature classification (auth, provisioning, transient, overflow) | Yes (with the §8, item 1 caveat) | §10 Q7 |

### 11.2 What this teaches about prompting and evaluating any AI assistant, including the Databricks Assistant

1. **Don't let the model decide what happens next when code can.** Put sequencing, gating, and "is it done?" in deterministic code, and give the model narrow, checkable tasks. With the Databricks Assistant, ask for one bounded change (one function, one query, one test) rather than "build the feature".
2. **Verify, don't trust.** Consort's biggest win is that the orchestrator itself runs the tests. When Assistant says "fixed", re-run the cell or job, check the row counts, and run the test on a dev branch or a cloned table. Treat any claim without an artifact as unverified, whether it is "it already exists" or "tests pass".
3. **Name exact targets.** Absolute paths, exact IDs, and "EXACTLY these N items, ONLY these" removed wandering and batching (`orchestrator-effects.ts:361-366`). In Assistant prompts, give fully qualified `catalog.schema.table` names, exact column names, and the exact file or cell. Vague targets produce plausible but invented names.
4. **Check the output contract, then give one informed retry.** When output is wrong, say precisely what was missing ("the file does not exist at X"), retry once, then escalate to a human. Blind re-prompting loops.
5. **Separate author from judge.** Consort has the Navigator review the Driver, and a critic on a different model review the design. When you review AI code, read the diff yourself or with a second pass. Specifically look for loosened assertions, broadened `except` blocks, deleted tests, relaxed filters in data-quality checks, and hardcoded values. These are the "make it green" moves Consort's test-smell gate catches.
6. **Classify failures before asking for a fix.** An expired token or unmigrated database is not a code bug (`cycle-record.ts:481-497`). Tell Assistant the error class, and don't let it "fix" code for an infrastructure fault.
7. **Bound loops, and check for progress rather than just counting.** The reflect budget stops when a revise does not change the test list (`orchestrator-probe.ts:590-609`). In practice, if two iterations with an assistant produce the same diff or the same error, stop and re-scope.
8. **Run cheap deterministic checks before expensive LLM judgment.** Linters, schema checks, and unit tests catch structural defects that a second LLM pass would burn time finding (CHANGELOG 0.3.101).
9. **Evaluate prompt and model changes against recorded references with a fixed judge, and keep the outputs.** The repo applied two judge-less "winners", then logged this as an invariant violation to re-run; the shipped manifests no longer carry those settings. When you tune a prompt, compare against known-good outputs, not "it seemed faster".
10. **Read comments and docs in AI-assisted codebases skeptically.** This repo was built largely with Claude Code, judging by its run logs' references to Claude plans and memories (inferred). It has several places where comments contradict code: telemetry arming, "no LLM" labels, stale doc citations, and unimplemented flags (§8, items 4, 6, 7, 18). When stewarding AI-written code, trust the executable path and verify claims with grep, tests, or a run.
11. **Prompts become a lessons-learned store, and that has a cost.** 176 KB of role prompts encode real incidents. That works, but it is weight on latency and cost; the repo's own sweeps found that lower effort, not smaller models, is the lever that helps.
12. **Keep humans at the irreversible steps.** Merges, schema migrations on shared tiers, and production deploys go through fail-closed gates. With Assistant or Genie Code, keep PR review and approvals for migrations and jobs on shared data human-owned, and never let the agent hold a token that bypasses them (§8, item 8).

---

## 12. Glossary

- **Artifact-as-API:** roles communicate only through files under `.consort/`; the orchestrator re-derives all state from them.
- **`.consort/`:** the per-project workflow state directory (legacy names `.sftdd`/`.tdd` are auto-migrated).
- **`consort-drive`:** the deterministic orchestrator CLI. **`nextTransition`** is its pure router, and **`runDriver`** its loop.
- **`DriveState` / `WorkflowAction`:** the router's input snapshot and output action.
- **Lane:** design lane (spec, architecture, DBA, test list, reflect, gate, per story) and build lane (cut, RED, GREEN, REVIEW, REFACTOR, accept). **`actionLane`** maps each action to a lane for Tier-2 bounds.
- **Tier-1 / Tier-2 bound:** `--sprint` (the whole sprint) versus `--plan-only` / `--only design|build|deploy`.
- **HITL / HIL gate:** a human approval point, one of intake, backlog, plan, per-story spec, acceptance, deploy, and promote. **Fail closed:** refuses without real, conformant evidence.
- **Human Proxy:** the headless HIL implementation for CI, capture, and replay (approver `human-proxy`).
- **`gates.json` / `pipeline.json`:** feature-level gate state (hashes, history) and per-story status, gate, experiment, and acceptance.
- **Experiment:** a per-story paired git and Lakebase branch the story is built on (`exp1`). **Spike:** a throwaway exploration branch.
- **Paired branch:** a git branch plus a Lakebase branch with the same sanitized name, with `.env` synced by `createPairedBranch` and the post-checkout hook.
- **Tier:** a long-lived parent branch (`main` = default/production, `staging`, …). **Promote:** PR → CI → merge into the parent tier and migrate it.
- **Honest GREEN:** a verify run by the orchestrator on an ephemeral Lakebase child branch, gated by migration and test-smell checks.
- **Ephemeral verify branch:** `<exp>-vrfy-<nonce>`, TTL 3600 s, deleted after each verify.
- **Cycle:** a RED → GREEN (→ REFACTOR) record, `cycles/<F>/<S>/<AC>/cycle-NNN.json` (`red_at`, `green_at`, `test_ids`).
- **Loop granularity:** `story` (default), `ac` (strict per-test), `hybrid-a` (layer batches). **Contract story:** drop, rename, or cleanup, auto-switched to `ac`.
- **Green-failure marker:** `green-failure.json`, which drives ASSESS → REPAIR / supersede / spec-defect / unfixable routes.
- **Superseded tests:** prior tests a new AC legitimately changes, listed by the Navigator. This is the only case where the Driver may edit tests.
- **Spec-defect:** the test itself is wrong. It routes to HIL with a recommendation to `consort-reopen-story --from <role>`.
- **Reflect:** the Navigator's pre-build critique of the spec and test list. It writes `reflect-verdict.json` and drives a bounded **revise-route** back to the owning author.
- **Smell:** a catalogued defect signal. `spec`-level smells route to an author; `build`-level smells halt. **Blocking smells** become escalations.
- **Escalation / raise-to-hil:** a durable record under `escalations/` that halts the drive until a human resolves it with `consort-resolve-escalation`.
- **Expectation ledger / handback:** the per-handoff output contract, with one informed retry and then a `ProtocolViolationError`.
- **Design fingerprint:** a hash of the test list's design-only fields, stamped at experiment cut, so a redesign forces a re-cut.
- **Architecture canon / conventions:** project-level layout and rules pinned by the first feature. **Projection** writes architect notes deterministically for stories that are not new to the canon.
- **Persistence invariant:** a DB-level guarantee (unique, foreign key, not null, check, reversible migration, …) declared by the architect, realized by the DBA, and covered by a fitness test.
- **Fitness test:** an architectural or constraint test (layering, ORM-only, invariants) that may already pass when written. **Behavior test:** pytest-bdd or equivalent AC scenarios. **Client test:** Vitest or Playwright tests under `client/tests/`.
- **Step manifest / StepExecutor:** a JSON declaration of a turn's inputs, outputs (channels `product`/`artifact`/`meta`), validators, and routing, executed by a seven-phase Template Method.
- **Corpus / camp / mine:** recorded runs ("mine") and the curated, verbatim reference assets extracted from them ("camp") for tests and judged optimization sweeps.
- **`kit-ref` / `lk` shim:** the pinned kit version a scaffolded project runs, and the `./scripts/lk` launcher that resolves kit bins.
- **UI track:** the project has a user-facing UI. It enables the UX Designer, the design guide, E2E stories, and client tests.
