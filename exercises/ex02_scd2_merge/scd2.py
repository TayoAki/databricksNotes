"""Exercise 02: SCD Type 2 customer dimension with a hand-written Delta MERGE.

Why hand-write it when Lakeflow SDP has `create_auto_cdc_flow(stored_as_scd_type=2)`?
Because you will meet customers on plain Jobs, dbt, or legacy code, and because you can only
judge AUTO CDC (or Assistant-generated MERGE code) if you know the four ways this goes wrong:

  1. Several changes to one key in a single batch
     -> DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE, or lost intermediate history.
  2. Out-of-order (late) events
     -> a naive MERGE closes the current row with an OLDER date: effective_to < effective_from.
  3. No-op updates (same attributes re-sent)
     -> spurious new versions, and history bloat.
  4. Re-running a batch
     -> duplicate versions unless the logic is idempotent.

AUTO CDC handles 1, 2 and 4 for you (via sequence_by). Rule 3 maps to track_history_column_list.
"""
from __future__ import annotations

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

KEY = "customer_id"
TRACKED = ["name", "city", "segment"]  # changes in these columns create a new version

DIM_SCHEMA = (
    "customer_sk BIGINT, customer_id STRING, name STRING, city STRING, segment STRING, "
    "row_hash STRING, effective_from TIMESTAMP, effective_to TIMESTAMP, is_current BOOLEAN"
)


def with_row_hash(df: DataFrame) -> DataFrame:
    # Hash of tracked attributes. NULL-safe: concat_ws skips NULLs, so encode them explicitly.
    # Without that, (NULL, 'x') and ('x', NULL) would hash the same.
    parts = [F.coalesce(F.col(c).cast("string"), F.lit("<NULL>")) for c in TRACKED]
    return df.withColumn("row_hash", F.sha2(F.concat_ws("||", *parts), 256))


def _chain(changes: DataFrame) -> DataFrame:
    """Turn a set of versions per key into contiguous intervals: [from, next_from)."""
    w = Window.partitionBy(KEY).orderBy("effective_ts")
    return (
        changes.withColumn("effective_to", F.lead("effective_ts").over(w))
        .withColumn("is_current", F.col("effective_to").isNull())
        .withColumnRenamed("effective_ts", "effective_from")
        # 64-bit hash surrogate key: fine at this scale. At ~1e9 versions the collision
        # probability is ~2.7%; see playbook/05-execution-and-scaling.md for the maths.
        .withColumn("customer_sk", F.xxhash64(KEY, "effective_from"))
        .select(*[f.split()[0] for f in DIM_SCHEMA.split(", ")])
    )


def scd2_upsert(spark: SparkSession, target_path: str, batch: DataFrame) -> DataFrame:
    """Apply a batch of change records. Returns the late events that were NOT applied.

    batch columns: customer_id, name, city, segment, effective_ts (possibly several per key).
    """
    batch = with_row_hash(batch)

    if not DeltaTable.isDeltaTable(spark, target_path):
        w = Window.partitionBy(KEY).orderBy("effective_ts")
        first_load = (batch.withColumn("_prev", F.lag("row_hash").over(w))
                      .where(F.col("_prev").isNull() | (F.col("_prev") != F.col("row_hash"))))
        _chain(first_load).write.format("delta").save(target_path)
        return spark.createDataFrame([], batch.schema)

    target = DeltaTable.forPath(spark, target_path)
    # Pin the snapshot. A DataFrame over a Delta table is a recipe, re-resolved at every
    # action. `late` is returned to the caller and evaluated AFTER the MERGE below, so
    # without versionAsOf it would be computed against the post-MERGE table and flag the
    # events we just applied. Verified in case-studies/04-lazy-evaluation-meets-mutable-tables.md.
    version = target.history(1).select("version").first()[0]
    current = (spark.read.format("delta").option("versionAsOf", version).load(target_path)
               .where("is_current")
               .select(KEY, F.col("row_hash").alias("_cur_hash"), F.col("effective_from").alias("_cur_from")))
    b = batch.join(current, KEY, "left")

    # (2) Out-of-order guard: events at or before the current version's start are NOT applied
    #     blindly. They go back to the caller for review, or a per-key history rebuild.
    late = b.where(F.col("_cur_from").isNotNull() & (F.col("effective_ts") <= F.col("_cur_from")))
    b = b.where(F.col("_cur_from").isNull() | (F.col("effective_ts") > F.col("_cur_from")))

    # (3) Collapse no-op / consecutive duplicate versions. The first event compares against
    #     the target's current hash; later events compare against the previous event.
    w = Window.partitionBy(KEY).orderBy("effective_ts")
    b = b.withColumn("_prev_hash", F.coalesce(F.lag("row_hash").over(w), F.col("_cur_hash")))
    changes = b.where(F.col("_prev_hash").isNull() | (F.col("row_hash") != F.col("_prev_hash")))

    # (1) Many changes per key: insert the whole chain, close the current row ONCE per key.
    inserts = _chain(changes.drop("_cur_hash", "_cur_from", "_prev_hash"))
    closers = (changes.where(F.col("_cur_hash").isNotNull())
               .groupBy(KEY).agg(F.min("effective_ts").alias("_close_ts")))

    staged = (
        closers.select(F.col(KEY).alias("_merge_key"), F.lit("close").alias("_action"),
                       "_close_ts", *[F.lit(None).cast(t).alias(c) for c, t in
                                     [(f.split()[0], f.split()[1]) for f in DIM_SCHEMA.split(", ")]])
        .unionByName(inserts.select(F.lit(None).cast("string").alias("_merge_key"),
                                    F.lit("insert").alias("_action"),
                                    F.lit(None).cast("timestamp").alias("_close_ts"), *inserts.columns))
    )

    (
        target.alias("t")
        .merge(staged.alias("s"), f"t.{KEY} = s._merge_key AND t.is_current")
        .whenMatchedUpdate(condition="s._action = 'close'",
                           set={"is_current": "false", "effective_to": "s._close_ts"})
        .whenNotMatchedInsert(condition="s._action = 'insert'",
                              values={c: f"s.{c}" for c in inserts.columns})
        .execute()
    )
    return late.drop("_cur_hash", "_cur_from")


def naive_scd2_merge(spark: SparkSession, target_path: str, batch: DataFrame) -> None:
    """The textbook 'staged updates' MERGE with no batch dedupe. It breaks on rule (1)."""
    batch = with_row_hash(batch)
    target = DeltaTable.forPath(spark, target_path)
    (
        target.alias("t")
        .merge(batch.alias("s"), f"t.{KEY} = s.{KEY} AND t.is_current")
        .whenMatchedUpdate(condition="t.row_hash <> s.row_hash",
                           set={"is_current": "false", "effective_to": "s.effective_ts"})
        .execute()
    )


def point_in_time_join(facts: DataFrame, dim: DataFrame, ts_col: str) -> DataFrame:
    """Attribute each fact to the dimension version that was valid at the fact's timestamp."""
    cond = (
        (facts[KEY] == dim[KEY])
        & (facts[ts_col] >= dim["effective_from"])
        & (dim["effective_to"].isNull() | (facts[ts_col] < dim["effective_to"]))
    )
    return facts.join(dim, cond, "left").select(facts["*"], dim["customer_sk"], dim["city"], dim["segment"])
