# Case study 06: near-misses. What I almost got wrong, and what caught it

**Status:** every row below happened during this work, and each correction is backed by an executed check.

## Why keep this list

Interviewers asking about **resilience** want to see *how you navigate the unknown*, not a clean record. The honest version of any investigation contains wrong turns. What matters is that each one was **caught by a check, not by luck**, and that the check becomes a habit. The same list is the best argument for how I use AI: an assistant makes these mistakes too, at speed, and the checks are what keep either of us honest.

## The ledger

| # | What I believed | What was actually true | What caught it | Habit it created |
|---|---|---|---|---|
| 1 | `lakeflow_framework` `cdc_snapshot.py` has a function that "falls off the end" (missing `return df`), so it returns `None` | The file has **no trailing newline**. `wc -l` reports 714 lines, but there are 715, and I printed lines up to `wc -l`, which dropped the last line: `        return df` | Before reporting, I looked at the raw bytes (`tail -c 80 \| od -c`) | Never report "missing code" from a line-range dump. Verify with a whole-file view. Tool artifacts look exactly like findings |
| 2 | A pipeline spec's `tableProperties` can override the framework's mandatory properties | `merge_dicts_recursively(d1, d2)` says "Keys in d1 take precedence", and it's called as `(mandatory, spec)`, so **mandatory wins** (`targets/base.py:85`) | Read the helper's *body*, not its name or call site | Precedence and merge order must be read, never inferred. (Corollary: `add_table_properties` can't override an existing key either. It has no callers today) |
| 3 | lakeflow_framework's test suite is broken: 32 collection errors | `No module named 'pyspark.dbutils'`: I was using plain pyspark. That module ships only with databricks-connect or the runtime | Installed the repo's own hash-pinned `requirements-dev.lock`: **396 passed** | Reproduce in the project's pinned environment before blaming the code |
| 4 | The Delta-enabled Spark session is broken (`JAVA_GATEWAY_EXITED`) | The first run downloads the Delta jars through Ivy, and that outlasted the gateway's start-up wait | Re-ran once the jars were cached in `~/.ivy2*/jars`: fine | Separate "first-run" from "every-run" failures. Retry *once*, deliberately, and say why |
| 5 | Salting reduced the hottest partition (first measurement) | I was re-hashing the joined *output*, measuring my own repartition. Worse, with broadcast on, the join never shuffled at all | Asked "which operator produced the partitions I'm counting?" Forced a sort-merge join (broadcast off, AQE off, 16 partitions) and measured the join's own tasks: **362,113 → 92,888** | Be sure you're measuring the thing you claim. Print the plan next to the number |
| 6 | AQE did not handle the skewed join | I read the QueryExecution of a **different** action (a `noop` write builds a new plan) | Collected through the *same* DataFrame, then read `executedPlan`: `isFinalPlan=true … SortMergeJoin(skew=true)` | AQE decisions exist only in the plan that actually ran |
| 7 | My test for kata bug B2 (`orderBy().dropDuplicates()`) proves the bug | It **XPASSed**: the buggy code returned the right row in every layout I tried. Non-determinism can't be proven absent by a laptop test | Strict xfail turned the XPASS into a failure | Split it: a behavioural test (honestly passes for both) plus a **structural** test on the optimized plan (no `first(`/`last(`/`any_value(`) |
| 8 | 9 kata "expected failures" meant 9 bugs detected | My fixture crashed (a string where a DATE was needed). A bare `xfail` accepts **any** exception, so every buggy test "passed" | The run said `2 passed, 9 xfailed, 8 errors`. The *fixed* tests errored in the fixture (`PySparkTypeError`), so the 9 "expected failures" were the same crash | `xfail(strict=True, raises=AssertionError)`: only a wrong *answer* counts |
| 9 | The SCD2 "late events" output was right | It was computed *after* the MERGE: a lazy DataFrame over a table the job then changed ([case 04](04-lazy-evaluation-meets-mutable-tables.md)) | Wrote a test for the late-event path, then **mutation-tested** it (remove the fix, and the test must fail) | Any test you write for a fix should fail without the fix. Check it |
| 10 | `.cache()` + an action freezes a snapshot | Measured: a cached, counted DataFrame returned 3, then **10** after an append | Ran it instead of writing it down from memory | Cache is performance, never correctness |
| 11 | "Spark refuses to overwrite a table you're reading from" (general statement) | True for **Parquet** (`UNSUPPORTED_OVERWRITE.TABLE`). **Delta allows it** in one action and gets it right (snapshot isolation: 3 + 2 → 5 rows) | Ran both formats | Format-specific behaviour needs a format-specific test |
| 12 | `spark.pyspark.python` would pin the worker interpreter | In-process SparkContext reads only the `PYSPARK_PYTHON` env var (`context.py:324`). The conf is for the `spark-submit` launcher ([case 05](05-the-worker-python-interpreter.md)) | Asked the workers directly: a UDF returning `sys.executable` | When a config "has no effect", find who reads it and when |
| 13 | My stream-stream join evidence script failed, so maybe the hypothesis was wrong | `DELTA_DUPLICATE_COLUMNS_FOUND`: my *test harness* gave both inputs a column named `v`, so the join output couldn't be written | Read the error's subject (the sink write), not just "it failed" | Classify every failure: the system under test, the harness, or the environment. Only the first is evidence |
| 14 | The pbi-aibi-converter's fuzzy column matcher would return nothing for `customer_name` against a table with `customer_id` | It returns `customer_id`: 9 of 13 characters match position by position (0.69 > 0.6), so a name silently becomes an ID. Worse than I predicted | I wrote down my prediction, then ran the verbatim function ([`evidence/fuzzy_column_match.py`](evidence/fuzzy_column_match.py)) | Write the prediction before running the experiment. A wrong prediction is the most useful kind |

## Patterns across the ledger

1. **Tool artifacts pose as findings** (#1, #13). The terminal, `wc`, `sed`, and your own harness all have semantics. When a finding is surprising, first check the instrument.
2. **Environment faults pose as code faults** (#3, #4, #12). The fix is to reproduce in the declared environment: lockfile, runtime version, same interpreter on driver and workers.
3. **Measuring the wrong thing** (#5, #6). Put the physical plan beside every performance number.
4. **Tests that pass for the wrong reason** (#7, #8, #9). Strict xfail, specific `raises=`, and mutation checks are cheap and decisive.
5. **Plausible semantics from memory** (#2, #10, #11). Precedence, caching and format behaviour are exactly where memory, and AI assistants, are confidently wrong. A 10-line experiment settles it.

## The claims discipline I use

Every finding in these notes carries one of three statuses:
- **CONFIRMED:** reproduced by execution, with the evidence script linked.
- **SUSPECTED:** consistent with the code as read, but the decisive run needs an environment I don't have. It is always stated together with the cheapest test that would settle it.
- **REFUTED:** it looked like a bug and wasn't. These stay in the notes (rows 1, 2, 10, 11), because a refuted hypothesis is information, and hiding it makes the confirmed ones less credible.

## How I'd say this in an interview

> "I'd rather show you where I was wrong. Early on I nearly reported a missing return statement in a framework. It was my `wc -l` hiding the last line of a file with no trailing newline. Since then, before I call something a bug, I ask three questions: is the instrument right, is the environment the declared one, and would my test fail without my fix? Each question is cheap and each has caught me at least once."
