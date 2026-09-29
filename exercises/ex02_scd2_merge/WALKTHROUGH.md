# Exercise 02: SCD Type 2 with a hand-written Delta MERGE

> **The customer ask:** "Finance wants to report revenue by the customer's segment *at the time of sale*, but our customer table overwrites itself every night."

The code is in `scd2.py` and the tests in `test_ex02.py` (10 tests). Run them with `pytest ex02_scd2_merge -q`.

## 1. Clarify

- **Which attributes create history?** City and segment: yes. A typo fix in a name: maybe not. This becomes the `TRACKED` list, the equivalent of `track_history_column_list` in AUTO CDC.
- **What is "effective time"?** The source's business timestamp, not load time. It decides both ordering and the as-of join.
- **Can a batch hold several changes for one customer?** Yes (nightly batches). Can events arrive late? Yes (corrections).
- **Are deletes possible?** They're out of scope here. In AUTO CDC they are `apply_as_deletes`, which closes the open version.

## 2. Decompose

```
batch ─► hash tracked attrs (NULL-safe) ─► join CURRENT rows (snapshot pinned via versionAsOf)
      ├─► late events (ts <= current.effective_from) ──► returned for review, NOT applied
      ▼
   collapse no-op / consecutive duplicate versions (lag over ts, seeded with current hash)
      ▼
   chain versions per key: effective_to = lead(effective_from)   ← handles N changes per key per batch
      ▼
   staged MERGE:  one "close" row per key (merge key = id)  ∪  all new versions (merge key = NULL → insert)
      ▼
   target:  MATCHED & close → is_current=false, effective_to=first change ts;  NOT MATCHED & insert → insert
```

## 3. The four ways SCD2 goes wrong, and the test that proves each is handled

| Failure | What a naive MERGE does | Guard | Test |
|---|---|---|---|
| Several changes to one key in a batch | Raises `DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE`. If you "fix" it with dropDuplicates, intermediate history is lost | Chain the versions; one close row per key | `test_naive_merge_fails_on_multiple_changes_per_key`, `test_history_is_complete_and_ordered` |
| Late/out-of-order event | Closes the current row with an *older* date, so `effective_to < effective_from` | Route events at or before the current start to review | `test_late_event_is_returned_not_applied`, `test_intervals_are_contiguous_and_valid` |
| No-op re-sends | Creates identical new versions (history bloat) | Compare a NULL-safe hash of tracked columns | `test_no_op_updates_do_not_create_versions` |
| Re-running a batch | Duplicate versions | All of the above make it idempotent | `test_rerun_is_idempotent` |

Plus two structural invariants: exactly one current row per key, and a unique surrogate key.

## 4. The subtle bug I hit while writing this, and why it matters in customer code

`scd2_upsert` returns the late events as a DataFrame defined over the target table, which the MERGE then changes. **A DataFrame is a recipe, not a result.** I measured it: a Delta DataFrame defined before an append, and evaluated after it, returns the *new* row count (10, not 3). Unpinned, the "late events" would be computed against the post-MERGE table and would flag the events that had just been applied. The fix is `option("versionAsOf", v)`, and a mutation test (removing the pin) makes `test_late_event_is_returned_not_applied` fail. Full write-up: `case-studies/04-lazy-evaluation-meets-mutable-tables.md`.

## 5. How it executes and scales

- The MERGE runs as a join between the staged source and the target, restricted to `is_current` rows. Delta rewrites only the files containing matched rows, and **deletion vectors** make even that a soft-delete rather than a file rewrite.
- **Cost driver: target scan.** Without data skipping, every MERGE scans the whole dimension. At scale, liquid-cluster the dimension on `customer_id`. For very large dimensions, pre-filter the target by the keys present in the batch (the dynamic file pruning Spark applies to the join).
- **Windows** (`lag`/`lead` by key) shuffle only the batch, not the target.
- **Surrogate key:** `xxhash64(id, effective_from)` is 64-bit. Collision risk is negligible below about 10⁸ versions (0.03%), 2.7% at 10⁹ and 39% at 4×10⁹ (computed in `playbook/05`). The test asserts uniqueness. For big dimensions use a 128-bit hash, an identity column, or an expectation on uniqueness.
- **On Databricks you would usually not hand-write this.** `create_auto_cdc_flow(..., stored_as_scd_type=2, sequence_by=...)` in Lakeflow SDP handles multiple changes per key, late events (it *re-slots* them into history instead of rejecting them) and idempotency, and it's incremental. Hand-written MERGE is for Jobs/dbt estates, and for knowing what AUTO CDC saves you from.

## 6. Using the Assistant here

A good prompt is a spec: *"Write a PySpark function that applies a batch of customer change events to an SCD2 Delta table. Tracked columns: name, city, segment. A batch may contain several events per customer; build the full version chain. Events older than the current version must NOT be applied; return them. Re-running a batch must be a no-op. Return tests for each property."*

Then check its output against the table in §3. Two real-world warnings:
- The `vibe-coding-workshop-template` skill's own "SCD Type 2" template **only updates a timestamp on match**. It never closes the old row or inserts the new version, so changed attributes are silently discarded (verified in `02-merge-patterns/assets/templates/scd-type2-merge.py:57-64`). An assistant that follows that skill faithfully writes a non-SCD2.
- The same skill set recommends `orderBy().dropDuplicates()` as "SIMPLE and RELIABLE". Exercise 05 (B2) shows why it isn't.

## 7. Business framing

> "Every report can now answer 'what did this customer look like on the day they bought?' History is kept only when something the business cares about changes, late corrections can't corrupt it, and re-running last night's load is always safe."
