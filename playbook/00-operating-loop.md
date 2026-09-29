# 00. The operating loop: how I work a customer data problem

This is the loop I'd run in a live coding interview, a customer workshop, or a pairing session. The same loop scales from a 45-minute exercise to a multi-week engagement; only the depth of each step changes. Each step names what I'd **say out loud**, because the interview is scored on the reasoning as much as the result.

```
 1. Frame      what decision does this number drive? what does "done" look like?
 2. Inspect    grain, keys, NULLs, duplicates, volumes, time zones  (before writing a transform)
 3. Decompose  a sequence of transformations, each with input grain -> output grain
 4. Slice      the smallest end-to-end version that produces the number
 5. Verify     row-count ledger + reconciliation against an independent calculation
 6. Harden     NULLs, duplicates, late/out-of-order data, reruns, determinism
 7. Scale      read the plan: shuffles, skew, broadcast, state, small files
 8. Explain    the business version and the engineering version
 9. Ship       code + tests + deploy (DAB) + monitoring, owned by a team
```

## 1. Frame the problem (2–5 minutes, and never skipped)

Questions I ask first, and why:

| Question | Why it matters |
|---|---|
| "Who looks at this number, and what do they decide with it?" | Sets the precision needed and the cost of being wrong. Finance close ≠ a trend chart |
| "What's the definition? Gross or net? Cancelled orders? Refunds? Which currency, which time zone?" | Most "wrong numbers" are definition disagreements, not bugs (Exercise 01: Finance and Ops never agreed) |
| "What's the grain of the answer?" | "Revenue per day per region" fixes the final GROUP BY and every join's allowed cardinality |
| "What's the freshness requirement?" | Batch vs `availableNow` vs continuous is a cost decision, not a fashion ([Exercise 04](../exercises/ex04_streaming_semantics/WALKTHROUGH.md)) |
| "What does a known-good answer look like?" | I need an independent number to reconcile against: a finance report, a hand count, last month's total |

**Say:** "Before I write anything, let me make sure I'm computing the right thing. I'm assuming revenue is net of cancellations, in USD, bucketed by UTC day. Is that right?"

## 2. Inspect the data before transforming it

The cheapest bugs to fix are the ones found before any code exists. On Databricks, I'd run:

```sql
DESCRIBE TABLE catalog.schema.orders;                                   -- names + types, never from memory
SELECT count(*), count(DISTINCT order_id), count(order_id) FROM orders; -- grain + NULL keys
SELECT status, count(*) FROM orders GROUP BY ALL ORDER BY 2 DESC;       -- enum values, incl. NULL and 'Cancelled '
SELECT order_id, count(*) c FROM orders GROUP BY 1 HAVING c > 1 LIMIT 20;  -- duplicates, and why
SELECT min(ts), max(ts), count_if(ts IS NULL) FROM orders;              -- time range + missing times
```

For every table: **what is one row?** If the answer is fuzzy, the joins downstream will be wrong.

**Say:** "`order_id` isn't unique here: 3 orders have multiple rows because updates are appended. So I'll need a 'latest version per order' step, and I need a deterministic tie-break."

## 3. Decompose into transformations

Write the pipeline as a list of steps, each with its grain. See [01-computational-thinking](01-computational-thinking.md). For Exercise 01:

```
raw lines ──parse──► typed rows (1 per line) ──quarantine──► valid rows ──latest per order──► orders (1 per order_id)
   ──join customers (deduped: 1 per customer)──► enriched orders (still 1 per order_id)
   ──to USD (fx at order date)──► ──group by day, region──► revenue (1 per day × region)
```

The grain annotation is the design review: any step where the grain changes unexpectedly is where the bug will be.

## 4. Build the smallest end-to-end slice

Get a number out the far end first, then improve each step. A complete wrong pipeline teaches more than a perfect first step. On Databricks: one notebook, `display()` at each step, a `LIMIT` sample, then the full data.

## 5. Verify: reconcile, don't eyeball

- **Row-count ledger:** count rows (and the sum of the money column, and NULLs in key columns) after every step. The first step where a number moves unexpectedly is the bug's home ([debug kata](../exercises/ex05_debug_kata/DEBUGGING_LOG.md)).
- **Reconcile with an independent calculation:** gold total = sum over silver; row counts in = rows out + quarantined; a hand-computed day.
- **Invariants as tests:** one row per key; no NULL keys; one current row per SCD2 key; totals preserved across joins.

**Say** (numbers from Exercise 01's tests): "Bronze kept all 15 landed lines, including the 1 malformed one. Silver has 6 orders, exactly one row per `order_id`, and 6 rows went to quarantine, each with a named reason. Gold totals 2219.49. If I join the undeduplicated customer file instead, I get 2379.48: the extra 159.99 is customer C002's orders counted twice, because C002 appears twice in the file. That's the check that tells us the dedup is needed."

## 6. Harden against the real world

The questions that separate a demo from production (each has a case study or exercise):

| Concern | Question | Where I proved it |
|---|---|---|
| NULLs | What does every predicate do with a NULL? | [07-null-semantics](07-null-semantics.md), [case 02](../case-studies/02-null-semantics-in-quarantine-predicates.md) |
| Duplicates | Can this join add rows? Is the dimension unique on the join key? | Exercise 01 fan-out test, kata B5 |
| Late / out-of-order data | Does an older update overwrite a newer one? | Exercise 01 `merge_into_silver` sequencing, Exercise 02 late events |
| Reruns | Is running it twice the same as once? | Exercise 01 idempotent ingestion, Exercise 02 rerun test |
| Determinism | Would two runs over the same input give the same output? | Kata B2 (`orderBy().dropDuplicates()`) |
| Failure handling | If a step fails, does the job fail, or quietly continue? | [case 03](../case-studies/03-fail-open-patterns.md) |

## 7. Scale review: read the plan

`df.explain("formatted")` before claiming anything about performance. Count Exchanges, check join strategies, look for skew and Python UDFs. See [05-execution-and-scaling](05-execution-and-scaling.md).

**Say:** "This plan has two shuffles: one for the aggregation and one for the window. The customer dimension is small enough to broadcast, so the fact table never moves for the join. At 100× the data, the risk is skew on the 'unknown customer' key, and AQE's skew join is my first lever."

## 8. Explain it twice

- **Business version:** what changed in the numbers, why, and how they'll know it's right. See [06-business-translation](06-business-translation.md).
- **Engineering version:** what executes where, what's incremental, what the failure modes are.

## 9. Ship it the way a team can own it

- Code in a repo; a **DAB** for jobs, pipelines and dashboards; `bundle validate` → deploy to dev → run → promote by CI as a service principal.
- Tests for the invariants, including a test that **fails without the fix** (mutation check).
- Monitoring: expectations and their counts in the event log, row counts, freshness, cost tags.
- A runbook for the failure modes you already know about.

## Working with teammates (and the interviewer as a teammate)

- **State assumptions as questions**, early: "I'm assuming X; tell me if that's wrong."
- **Narrate hypotheses, not just actions:** "I think the total is off because the join fans out. I'll check the dimension's key uniqueness before changing anything."
- **Time-box rabbit holes:** "I'll give this 5 minutes; if it's not resolved I'll note it as a known issue and move on to the end-to-end slice."
- **Use the docs, the Assistant and teammates deliberately:** docs for semantics, the Assistant for boilerplate and syntax (verified), teammates for context the data can't tell you ("is `status = NULL` a real state?").
- **Leave the code better for the next person:** names that say what, comments that say why, tests that say what must stay true.
