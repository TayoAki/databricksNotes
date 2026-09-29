# Interview question bank

Short answers I can say out loud, each linked to the evidence behind it. Grouped by the four evaluation criteria, plus execution/scaling and platform.

## Computational thinking

**Q: Here's a messy order feed. How do you get to "daily revenue by region"?**
Frame first (net or gross, currency, time zone, which order version counts), inspect the grain and keys, then decompose: parse/type → validate + quarantine → latest version per order (event time, deterministic tie-break) → sequenced MERGE → dedupe customers → LEFT join + "Unknown" → FX in DECIMAL → aggregate → reconcile. → [Exercise 01](../exercises/ex01_messy_orders_medallion/WALKTHROUGH.md), [playbook/00](../playbook/00-operating-loop.md)

**Q: What's the first thing you check about a table?**
Its grain: what one row means. Then key uniqueness, NULLs in keys, enum values (`SELECT DISTINCT`), and the time range. → [playbook/01](../playbook/01-computational-thinking.md)

**Q: How do you report customers by the segment they were in at the time of the sale?**
SCD2 dimension (validity intervals) and a point-in-time join with a half-open interval `ts >= valid_from AND (valid_to IS NULL OR ts < valid_to)`. → [Exercise 02](../exercises/ex02_scd2_merge/WALKTHROUGH.md)

**Q: A balance table has one row per account per day. Monthly total balance?**
Semi-additive: take each account's value at the month's last date, then sum across accounts. Summing days gave 430 instead of 160 in my demo. → [patterns_demo](../playbook/patterns_demo.py)

**Q: How would you price Databricks usage from system tables?**
Point-in-time LEFT join on `usage_end_time` within `[price_start, price_end)`, per `usage_unit`, reporting unpriced records and duplicate matches, labelled "list price". → [case 08](../case-studies/08-price-join-containment-vs-point-in-time.md)

## Code stewardship

**Q: Walk me through what happens when this PySpark runs.**
Transformations build a plan; the action triggers a job; Catalyst optimises (pushdown, pruning, join strategy); the plan is cut into stages at Exchanges; one task per partition; AQE re-plans at stage boundaries. Then read the actual `explain("formatted")`. → [playbook/05](../playbook/05-execution-and-scaling.md)

**Q: What does a Delta MERGE do under the hood, and why does it fail with multiple source rows?**
It joins source to target to find affected files, rewrites them (or writes deletion vectors) and commits a new version atomically. Two source rows matching one target row is ambiguous, so it refuses: dedupe on the merge key first. → [error zoo](../playbook/error_signatures_demo.py)

**Q: Why is `orderBy(ts desc).dropDuplicates([key])` wrong?**
The sort isn't preserved through the aggregation's shuffle, so the survivor is arbitrary (the plan shows `first()` in an Aggregate). Use `row_number()` with a full tie-break. It's recommended as "SIMPLE and RELIABLE" in a real skill pack. → [kata B2](../exercises/ex05_debug_kata/DEBUGGING_LOG.md)

**Q: You inherit a pipeline that "runs green but the numbers are off". What do you do?**
Draw the data flow with grains; ask the four questions per step (cardinality, NULLs, determinism, semantics); mark positional and default-driven code; then bisect with a row-count ledger. → [debug kata](../exercises/ex05_debug_kata/DEBUGGING_LOG.md), [playbook/02](../playbook/02-code-stewardship.md)

**Q: Tell me about a bug you found in code you didn't write.**
lakeflow_framework decides which side of a LEFT join to keep from the *text order* of the join condition: `a = b` keeps all customers, `b = a` drops two-thirds. I proved it with the framework's real classes on OSS Spark. → [case 07](../case-studies/07-lakeflow-delta-join-alias-parsing.md). Or the packaging chain: [case 01](../case-studies/01-lakeflow-packaging-three-stacked-faults.md).

**Q: Why is `status != 'cancelled'` a bug?**
For NULL status the predicate is UNKNOWN, and WHERE keeps only TRUE, so orders without a status vanish. Use `NOT (status <=> 'cancelled')` if NULL means "not cancelled". → [playbook/07](../playbook/07-null-semantics.md)

**Q: A DataFrame defined before a write: what does it see?**
The table at action time, not definition time. A DataFrame is a recipe. Pin with `versionAsOf`; `.cache()` doesn't pin (measured 3 → 10). → [case 04](../case-studies/04-lazy-evaluation-meets-mutable-tables.md)

## AI stewardship

**Q: How do you use the Databricks Assistant effectively?**
One bounded step at a time; give fully qualified names, grain, the output contract and the business rules; make it list its assumptions; then verify statically, by execution (plan, row counts), and semantically (invariants, reconciliation). → [playbook/03](../playbook/03-ai-stewardship.md)

**Q: How do you know when the Assistant is wrong?**
Names that don't trace to `DESCRIBE`; `IN (…)` literals without a `SELECT DISTINCT`; NULL-unsafe filters; arbitrary dedupes; INNER joins to dimensions; "fixes" that change meaning; claims of success without evidence. Then check row counts across every join.

**Q: What's a good prompt?**
Goal with the business definition; inputs with grain; exact output contract; rules; scope (and what *not* to do); the checks to show; the definition of done. Starter-journey's pattern: prompt + acceptance checklist + deterministic fallback.

**Q: Can you trust curated AI skills and prompt packs?**
Only after testing them. The vibe-coding skills recommend an arbitrary dedupe and ship an "SCD2" template that isn't SCD2; the lakeflow skill generates a stale format; the PBI converter's repair code swaps `unit_cost` for `unit_count`. Grounding moves the trust problem into the instructions. → [AI-error catalogue](../playbook/03-ai-stewardship.md#6-the-ai-error-catalogue-found-in-these-repos-own-ai-guidance-or-ai-built-code)

**Q: Why would you keep an LLM out of the control loop?**
consort's lesson: routing, gating and "is it done" belong in deterministic code; the model does bounded judgment tasks whose output is checked. → [repos/consort](../repos/consort.md)

## Resilience

**Q: You hit an error you've never seen. Walk me through it.**
Read the exact error class and which process raised it; classify (logic vs harness vs environment); write a hypothesis and a prediction; run the cheapest decisive test; fix the cause; prove the fix with a test that fails without it; grep for the same pattern. → [playbook/04](../playbook/04-resilience-and-debugging.md)

**Q: Tell me about a time you were wrong.**
I nearly reported a missing `return` in a framework; it was my `wc -l` hiding the last line of a file with no trailing newline. Now I verify the instrument before the finding. 15 such entries, each with the check that caught it. → [case 06](../case-studies/06-near-misses-and-false-positives.md)

**Q: Your pandas UDF says "No module named pyarrow" but pyarrow is installed. Why?**
The Python workers run a different interpreter than the driver. I asked the workers directly (a UDF returning `sys.executable`) and pinned `PYSPARK_PYTHON`. On Databricks: `%pip`, not `!pip`. → [case 05](../case-studies/05-the-worker-python-interpreter.md)

**Q: A test suite has 32 collection errors in a repo you just cloned. First move?**
Reproduce in the project's pinned environment (its lockfile) before blaming the code: 32 errors became 396 passes. → [case 01](../case-studies/01-lakeflow-packaging-three-stacked-faults.md)

## Execution and scaling

**Q: How does your pipeline scale to 100× data?**
Work per task after each shuffle; number and size of shuffles; skew (hot keys, NULL keys); broadcastable dimensions; driver-side operations; Python UDFs; file layout (liquid clustering, file stats); incrementality; streaming state. → [playbook/05 checklist](../playbook/05-execution-and-scaling.md)

**Q: One task takes 10× longer than the others.**
Skew. I measured 91% of rows in one task on a hot key. AQE skew join first (`SortMergeJoin(skew=true)` with no code change), then salting (hottest task 362k → 93k rows), then handle the hot key separately. → [Exercise 03](../exercises/ex03_execution_and_scaling/WALKTHROUGH.md)

**Q: Broadcast or sort-merge?**
Broadcast when one side is small (the fact never moves: 0 shuffles); sort-merge otherwise (both sides shuffle: 2 Exchanges). AQE can switch at runtime.

**Q: Why is the last hour always missing from the streaming dashboard?**
Append-mode windowed aggregation emits a window only after the watermark passes it; with `availableNow` the newest window waits for the next run. Use an MV, or `foreachBatch` + MERGE with restatement. → [Exercise 04](../exercises/ex04_streaming_semantics/WALKTHROUGH.md)

**Q: Is a 64-bit hash surrogate key safe?**
Collision probability is 0.03% at 10⁸ keys, 2.7% at 10⁹, 39% at 2³². Assert uniqueness in a test; use 128-bit or identity columns for large keyspaces.

## Platform

**Q: How would you set up a new customer's platform?**
Settle the expensive decisions first (tenant, region, workspace type, naming, group model, group-owned metastore, tags); three workspaces; SCIM groups; environment catalogs bound to workspaces; schema-level grants; cost guardrails before the first workload; Terraform outside workspaces, DABs inside. → [platform fundamentals](platform-fundamentals.md)

**Q: How do you mask PII at scale?**
ABAC: governed tags (plus automatic classification) → pure masking/row-filter UDFs → one policy per schema or catalog with `TO … EXCEPT`. New tables are covered once tagged. Watch dashboards published with embedded credentials.

**Q: How do you make KPIs consistent across BI and AI?**
One metric view per analytical grain, reconciled against a known-good query, with many-to-one joins and semi-additive windows where needed; dashboards and Genie bound to it.

**Q: How do you promote from dev to prod?**
DABs: PR validates every target; deploy to dev and test; staging; prod with approval as a service principal. `bundle run` doesn't sync code.

**Q: How would you check a workspace follows best practices?**
System tables with honest denominators: tagged cost share, serverless share where it's a choice, job cost on all-purpose, cluster auto-termination/policies/runtimes (rank-then-filter), job timeouts and health rules, audit freshness, run-as service principals. Report unmeasured as unmeasured. → [system-tables cheatsheet](system-tables-best-practice-checks.md)
