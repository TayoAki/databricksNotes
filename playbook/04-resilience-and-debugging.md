# 04. Resilience: how I navigate bugs and the unknown

> **What's being assessed:** "When you hit a bug or a logic error, how do you handle it? We don't mind if you need to work through it; we care about how you navigate the unknown."

The honest record of this work is in [case 06](../case-studies/06-near-misses-and-false-positives.md): 15 wrong turns, each caught by a check. This page is the method behind those catches.

## 1. The debug loop

```
 observe precisely ──► classify ──► hypothesis (+ prediction) ──► cheapest decisive test
        ▲                                                               │
        └──── generalise ◄── prove the fix (fails without it) ◄── fix at the cause
```

1. **Observe precisely.** The exact error class and message, the process it came from (driver, Python worker, streaming query), the input. For wrong numbers: which number, by how much, since when.
2. **Classify before fixing.** Is the failure in:
   - the **system under test** (the logic),
   - the **harness** (my test, my data, my measurement), or
   - the **environment** (packages, interpreter, permissions, runtime version, network)?
   Only the first is evidence about the code. My stream-stream join "failure" was a duplicate column in my own test data; lakeflow's 32 "broken" tests were a missing Databricks-only module.
3. **Write the hypothesis and a prediction** before running anything. A wrong prediction is the most useful result (the fuzzy matcher mapped `customer_name` to `customer_id`, not to nothing as I predicted).
4. **Cheapest decisive test:** the smallest input that distinguishes the hypotheses. Toggle one variable at a time; bisect with the row-count ledger.
5. **Fix at the cause, not the symptom.** A `dropDuplicates` after a fan-out join hides the bug; deduplicating the dimension fixes it.
6. **Prove the fix:** the test must **fail without the fix** (mutation check). I removed the `versionAsOf` pin in Exercise 02 to watch the test fail.
7. **Generalise:** grep for the same pattern elsewhere; turn the lesson into a test, an assertion or a checklist item.

## 2. The row-count ledger: bisecting a wrong number

```python
def ledger(df, step, money="amount", key="order_id"):
    r = df.agg(F.count("*").alias("rows"), F.countDistinct(key).alias("keys"),
               F.count(money).alias("non_null_money"), F.sum(money).alias("money")).first()
    print(f"{step:22} rows={r.rows:>8} distinct_{key}={r.keys:>8} non_null={r.non_null_money:>8} sum={r.money}")
    return df
```

Wrap each step. The first step where rows, keys or money move unexpectedly is where the bug lives:

| Symptom in the ledger | Usual cause |
|---|---|
| rows go **up** after a join | the dimension isn't unique on the key (fan-out) |
| rows go **down** after a join | an INNER join dropped orphans |
| rows go down after a filter more than expected | NULLs in the predicate column |
| `non_null_money` drops | a cast or a `when` without `otherwise` produced NULLs |
| `rows > distinct keys` where the grain should be one per key | dedupe missing or on the wrong key |

Each ledger call is an action (a Spark job). Use it to diagnose, then remove it or turn it into expectations and metrics.

## 3. Error signatures: what they usually mean

Rows marked ✔ were reproduced in this work ([`error_signatures_demo.py`](error_signatures_demo.py), the exercises, or the case studies); the others are platform field knowledge to confirm in the docs.

| Error / symptom | Usual cause | First check / fix | |
|---|---|---|---|
| `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE` | Duplicate keys in the MERGE source | Dedupe the source on exactly the merge key (deterministically) | ✔ |
| `UNRESOLVED_COLUMN.WITH_SUGGESTION` | Name mismatch, wrong alias, or the column lives on the other side of a join | `DESCRIBE`; read the suggestion list; check which DataFrame it's evaluated on | ✔ |
| `AMBIGUOUS_REFERENCE` | Same column name from both join sides | Alias both sides; select `a.col`; drop or rename before joining | ✔ |
| `DELTA_DUPLICATE_COLUMNS_FOUND` | Writing a join result with duplicate names | Explicit `select` with aliases before the write | ✔ |
| `TABLE_OR_VIEW_NOT_FOUND` | Upstream not run yet; wrong catalog/schema; missing `USE SCHEMA` privilege | Fully qualified name; `SHOW TABLES IN c.s`; check grants | ✔ |
| `REQUIRES_SINGLE_PART_NAMESPACE` | A 3-part name where there's no Unity Catalog (local Spark, HMS) | Environment, not code | ✔ |
| `CAST_INVALID_INPUT` | ANSI mode (default in Spark 4 / serverless) on dirty strings | `try_cast` + quarantine the NULLs it produces | ✔ |
| `DIVIDE_BY_ZERO` | ANSI mode | `try_divide` or `NULLIF(denominator, 0)` | ✔ |
| `UNSUPPORTED_OVERWRITE.TABLE` | Reading and overwriting the same **non-Delta** table | Delta allows it (snapshot isolation); or write elsewhere and swap | ✔ |
| `DELTA_UNSUPPORTED_OUTPUT_MODE` | Streaming aggregate to Delta in `update` mode | `foreachBatch` + MERGE, or a materialized view | ✔ |
| "Stream-stream LeftOuter join … not supported without a watermark" | Outer stream-stream join needs watermarks + a time bound | `withWatermark` on both sides + an event-time range in the condition | ✔ |
| Streaming state keeps growing | Aggregation/dedupe/join without a watermark | Watermark; `dropDuplicatesWithinWatermark` | ✔ (inner join state 2→4→6) |
| `ModuleNotFoundError` inside a UDF | Package on the driver only, or a different worker interpreter | `%pip install` (not `!pip`); declare job/serverless environment deps | ✔ ([case 05](../case-studies/05-the-worker-python-interpreter.md)) |
| `PERMISSION_DENIED` / `INSUFFICIENT_PERMISSIONS` | Missing path privileges (`USE CATALOG`, `USE SCHEMA`) or wrong identity (OBO vs SP, job `run_as`) | `SHOW GRANTS`; test as the identity that runs it | field knowledge |
| Job green, numbers wrong | NULL predicates, fan-out, arbitrary dedupe, time zone, swallowed errors | Row-count ledger; the four questions per step | ✔ (kata) |
| Works interactively, fails as a job | Libraries, identity (`run_as`), parameters/widgets, session conf (time zone, ANSI), cluster vs serverless | Diff the two environments; one variable at a time | ✔ (case 05 is one instance) |
| `bundle run` runs old code | `bundle run` doesn't sync files | `bundle deploy` then `bundle run`; never hotfix under `.bundle/` | per vibe-coding DAB skill |
| One task much slower than the rest | Skew on a hot key (NULL, "unknown", a big tenant) | Spark UI task-time distribution; AQE skew join; salting | ✔ (Ex03: 91% of rows in one task) |
| Driver slow or out of memory | `collect()`, `toPandas()`, a broadcast that's too big, a huge plan from a `withColumn` loop | Keep work distributed; `select` once; check broadcast sizes | plan-analysis cost ✔ (Ex03: `withColumn` loop 5.5 s vs one `select` 1.3 s at 300 columns); OOM itself is field knowledge |
| Genie or a dashboard shows a different number | Different filters or time windows; metric fan-out; viewer vs embedded credentials | Same metric view? Compare the generated SQL | per starter-journey |

## 4. Resilience habits (each one earned in this work)

| Habit | The incident behind it |
|---|---|
| Reproduce in the project's pinned environment before blaming the code | lakeflow: 32 collection errors → lockfile → 396 passed |
| Retry once, deliberately, and say why | `JAVA_GATEWAY_EXITED` on the first run (jar download) |
| Check the instrument before the finding | `wc -l` hid a file's last line; my stream test harness duplicated a column |
| Measure the thing you claim; put the plan beside the number | the first salting measurement counted my own repartition |
| Read the evidence from the thing that ran | AQE skew handling is only in the executed plan of the same DataFrame |
| Make negative tests specific about *why* they fail | a bare `xfail` hid a fixture crash behind 9 "expected failures" |
| A laptop can't prove the absence of non-determinism | kata B2 XPASSed; a structural plan test replaced it |
| Write the prediction down first | the fuzzy column matcher surprised me |

## 5. Bounded effort and escalation

- **Time-box:** decide up front how long a hypothesis gets. In an interview: "I'll give this five minutes, then park it as a known issue and finish the end-to-end slice."
- **Change approach after two same-class failures.** Iterating variants of the same fix is the spiral. Read the docs, the plan or the source instead.
- **Escalate with evidence**, in this shape (from vibe-coding's autonomous-ops skill):
  1. every error seen, with run IDs and task keys;
  2. every fix tried, and what changed;
  3. the current root-cause hypothesis and the evidence for it;
  4. links to the runs;
  5. the next test I'd run.

## 6. What I say when I'm stuck (interview version)

- "Let me say what I know and don't know. The total is 7% high. Rows are stable through the dedupe and jump after the customer join, so I think the customer table has duplicate keys. Let me check that directly."
- "This error is about the *environment*, not the logic: the worker can't import pyarrow. I'll confirm which Python the workers run before I touch the code."
- "I predicted X and got Y, which rules out my first hypothesis. The remaining candidates are A and B; this query distinguishes them."
- "I've spent my time box on this. I'll note it as a known issue with my best hypothesis and move on, and come back if time allows."
