# Case study 04: lazy evaluation meets a mutable table

**Where:** my own Exercise 02 (`exercises/ex02_scd2_merge/scd2.py`), found while building it.
**Status:** CONFIRMED by execution ([`evidence/lazy_snapshot.py`](evidence/lazy_snapshot.py)) and guarded by a test that fails under a mutation.

## Why this is a good interview story

The bug was mine, not a customer's. It is a textbook "Code Stewardship" question: *can you explain what your code actually does under the hood?* The code read correctly line by line. It was wrong only because of *when* Spark evaluates it.

## The situation

`scd2_upsert` does two things with the dimension table:
1. It reads the **current** rows to decide which incoming changes are new, which are no-ops, and which are **late**, meaning older than the current version.
2. It applies a MERGE that closes old rows and inserts new versions.

It also *returns* the late events as a DataFrame, so the caller can route them for review. My first version built that DataFrame from `spark.read...load(target)` **before** the MERGE and returned it. The caller evaluated it **after** the MERGE.

## The experiment

A Delta table with 3 rows. Define DataFrames over it, append 7 rows, then evaluate the DataFrames:

```
spark.read.load defined before write -> 10
DeltaTable.toDF defined before write -> 10
derived df defined before write     -> 10
fresh read after write               -> 10
pinned versionAsOf=0 read            -> 3
cached df, counted before append     -> 3
same cached df, counted after append -> 10
```

**A DataFrame is a recipe, not a result.** It records *which table* to read, not *which version*. Delta resolves the snapshot when an action runs, so every unpinned DataFrame, including ones derived from it, sees the table as it is at action time.

In the SCD2 code this meant the "late events" were computed against the **post-MERGE** table, in which the events had just been applied. The result looked plausible and was wrong.

## The fix

Pin the snapshot you reasoned about:

```python
version = target.history(1).select("version").first()[0]
current = (spark.read.format("delta").option("versionAsOf", version).load(target_path)
           .where("is_current"))
```

Every downstream DataFrame derived from `current` now refers to the same version, whenever it runs.

**Other remedies, with their trade-offs:**

| Remedy | Cost | When to use it |
|---|---|---|
| `versionAsOf` / `timestampAsOf` pin | Free; relies on the version still being in the log (VACUUM/retention) | The default for "read then write the same table" |
| Materialise: write to a temp/staging table, then read it | One extra write | The result must outlive the job, or be audited |
| `df.localCheckpoint()` / `.checkpoint()` | Executor storage; `localCheckpoint` is lost if an executor dies | Short-lived, within one job |
| `.cache()` + an action | **Not a correctness tool.** Measured: a cached, already-counted DataFrame returned 3, then **10** after an append, because the write refreshed the cache. Evicted blocks are also recomputed from the current source | Performance only |
| Put both steps in one MERGE | None, if the logic fits | When the read is only used to build the MERGE source |

## Proving the test would catch it (mutation testing)

`test_late_event_is_returned_not_applied` asserts that the late event comes back *and* is not in the dimension. To prove the test guards the bug, I removed the `versionAsOf` pin and re-ran: the test **fails**. A test that passes with and without the fix protects nothing. Removing the fix is the cheapest way to check.

`test_lazy_dataframe_sees_later_writes` keeps the underlying Spark behaviour documented as an executable fact.

## Where this bites in real customer code

- **"Read, compute, overwrite the same table"** is safe *within one action* on Delta: snapshot isolation fixes the read version when the job starts, and the old files stay until VACUUM. I checked: a Delta table of 3 rows read, unioned with 2 rows and overwritten in one write ends with 5 rows. The same thing on a Parquet table is refused with `[UNSUPPORTED_OVERWRITE.TABLE] Can't overwrite the target that is also being read from`. The trap is the **multi-action** version: anything computed from the table and evaluated *after* the write.
- **Audit or late-data outputs** computed from the target and consumed after the write.
- **Reconciliation checks** (`before = spark.table(t)` … write … `after = spark.table(t)`): `before` is not "before" unless it is pinned or counted first.
- **Streaming `foreachBatch`** that reads the sink table inside the batch function while another writer appends.
- **Assistant-generated code.** An assistant writes the natural top-to-bottom version; it will not add a version pin unless you ask. This is a good review prompt: *"For every DataFrame that reads a table this job also writes, tell me which table version it will see when it is evaluated."*

## How I'd explain it

- **To an engineer:** "Spark DataFrames are lazy. Our 'before' snapshot was really 'whenever you look'. We pinned it to a Delta version, so it means what the code says."
- **To a business stakeholder:** "The report of late corrections was being compiled after the corrections were applied, so it could quietly list the wrong records. We now take the snapshot at a fixed point, and a test fails if anyone removes it."
