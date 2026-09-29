"""Exercise 01: messy orders -> Bronze / Silver / Gold on Delta Lake.

Design rule: every transformation is a pure function DataFrame -> DataFrame, so it can be
unit-tested locally, reused in a Databricks notebook or Job, or lifted into a Lakeflow
Spark Declarative Pipeline (@dp.table / @dp.view) almost unchanged. I/O lives only in run_*().

Run end to end:   python -m ex01_messy_orders_medallion.pipeline      (from exercises/)
"""
from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from delta.tables import DeltaTable
from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from .landing_data import FX_RATES, write_landing_zone

# --------------------------------------------------------------------------------------
# Bronze: land raw data exactly as received, plus lineage. Never "fix" data here.
# --------------------------------------------------------------------------------------

# Explicit all-STRING schema: schema inference on messy JSON is non-deterministic (the
# inferred type depends on which files you sampled) and a bad row can flip a column type.
RAW_ORDER_SCHEMA = (
    "order_id STRING, customer_id STRING, status STRING, amount STRING, currency STRING, "
    "order_ts STRING, updated_at STRING, _corrupt_record STRING"
)


def read_raw_orders(spark: SparkSession, paths: list[str]) -> DataFrame:
    return (
        spark.read.schema(RAW_ORDER_SCHEMA)
        .option("mode", "PERMISSIVE")  # keep bad rows instead of failing or dropping them
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .json(paths)
        # File-level lineage via the hidden _metadata column (same on Databricks).
        .withColumn("_source_file", F.col("_metadata.file_path"))
        .withColumn("_source_file_name", F.col("_metadata.file_name"))
        .withColumn("_ingested_at", F.current_timestamp())
    )


def ingest_new_files(spark: SparkSession, files: list[str], bronze_path: str) -> list[str]:
    """Idempotent file ingestion: a file already in bronze is never loaded twice.

    This is the job Auto Loader does for you at scale. It tracks discovered files in the
    stream checkpoint, so it doesn't collect() a ledger to the driver the way this does.
    """
    seen: set[str] = set()
    if DeltaTable.isDeltaTable(spark, bronze_path):
        seen = {
            r[0]
            for r in spark.read.format("delta").load(bronze_path)
            .select("_source_file_name").distinct().collect()
        }
    new_files = [f for f in files if Path(f).name not in seen]
    if new_files:
        read_raw_orders(spark, new_files).write.format("delta").mode("append").save(bronze_path)
    return [Path(f).name for f in new_files]


# --------------------------------------------------------------------------------------
# Silver: standardise -> validate (null-safe) -> split valid/quarantine -> latest state.
# --------------------------------------------------------------------------------------

def parse_timestamp(col: str) -> Column:
    """Accept every format we have seen upstream; unknown formats become NULL, not errors.

    try_to_timestamp returns NULL instead of raising. That matters on Spark 4 / ANSI mode,
    where a plain to_timestamp on a bad string fails the whole job.
    Naive strings (no zone) are interpreted in spark.sql.session.timeZone, so pin it.
    """
    s = F.trim(F.col(col))
    return F.coalesce(
        F.try_to_timestamp(s, F.lit("yyyy-MM-dd'T'HH:mm:ssX")),
        F.try_to_timestamp(s, F.lit("yyyy-MM-dd HH:mm:ss")),
        F.try_to_timestamp(s, F.lit("MM/dd/yyyy HH:mm")),
        # Epoch millis only when it really looks like one: 13 digits. Otherwise "2026"
        # would silently become 1970-01-01T00:00:02.026.
        F.when(s.rlike(r"^[0-9]{13}$"), F.timestamp_millis(s.cast("bigint"))),
    )


def standardise(raw: DataFrame) -> DataFrame:
    status = F.lower(F.trim("status"))
    return raw.select(
        F.upper(F.trim("order_id")).alias("order_id"),
        F.upper(F.trim("customer_id")).alias("customer_id"),
        F.when(status == "canceled", F.lit("cancelled")).otherwise(status).alias("status"),
        # Strip currency symbols and thousands separators, then *try*-cast: "abc" -> NULL.
        F.regexp_replace(F.trim("amount"), r"[$,\s]", "")
        .try_cast("decimal(18,2)").alias("amount"),
        F.upper(F.trim("currency")).alias("currency"),
        parse_timestamp("order_ts").alias("order_ts"),
        F.coalesce(parse_timestamp("updated_at"), parse_timestamp("order_ts")).alias("updated_at_ts"),
        "_corrupt_record", "_source_file", "_source_file_name", "_ingested_at",
        # Keep the raw values: quarantine rows must be explainable to the data owner.
        F.col("amount").alias("_raw_amount"),
        F.col("order_ts").alias("_raw_order_ts"),
    )


# Each rule states the VALID condition and must be NULL-safe. Evaluating a rule to NULL
# (for example amount > 0 when amount is NULL) is treated as a FAILURE via coalesce(..., false).
# That closes the three-valued-logic hole found in lakeflow_framework's quarantine
# predicate (see case-studies/02).
DQ_RULES: dict[str, str] = {
    "not_corrupt": "_corrupt_record IS NULL",
    "order_id_present": "order_id IS NOT NULL AND order_id <> ''",
    "customer_id_present": "customer_id IS NOT NULL AND customer_id <> ''",
    "amount_positive": "amount > 0",  # NULL amount -> NULL -> coalesced to failure
    "order_ts_parsed": "order_ts IS NOT NULL",
    "status_known": "status IN ('pending', 'shipped', 'delivered', 'cancelled')",
    "currency_known": "currency IN ('USD', 'EUR', 'GBP')",
}


def with_dq_failures(df: DataFrame, rules: dict[str, str] = DQ_RULES) -> DataFrame:
    """Add dq_failures: array of the names of the rules this row violates (empty = valid)."""
    checks = [
        F.when(~F.coalesce(F.expr(expr), F.lit(False)), F.lit(name))
        for name, expr in rules.items()
    ]
    return df.withColumn("dq_failures", F.filter(F.array(*checks), lambda x: x.isNotNull()))


def split_valid_quarantine(df: DataFrame) -> tuple[DataFrame, DataFrame]:
    flagged = with_dq_failures(df)
    valid = flagged.where(F.size("dq_failures") == 0).drop("dq_failures", "_corrupt_record")
    quarantine = flagged.where(F.size("dq_failures") > 0)
    return valid, quarantine


def latest_per_order(valid: DataFrame) -> DataFrame:
    """One row per order_id: the version with the greatest business timestamp.

    Order by updated_at (event time), NOT by arrival time. An update that arrives late
    but carries an older timestamp must lose. The extra sort keys make ties deterministic.
    dropDuplicates(["order_id"]) would keep an arbitrary row, and the "arbitrary" can
    change between runs, which makes it a real bug.
    """
    w = Window.partitionBy("order_id").orderBy(
        F.col("updated_at_ts").desc(), F.col("_ingested_at").desc(), F.col("_source_file").desc()
    )
    return valid.withColumn("_rn", F.row_number().over(w)).where("_rn = 1").drop("_rn")


def merge_into_silver(spark: SparkSession, updates: DataFrame, silver_path: str) -> None:
    """Upsert with a sequencing guard. This is the hand-written equivalent of AUTO CDC's sequence_by.

    Pre-condition: `updates` has at most one row per key. Otherwise Delta raises
    DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE (see ex02).
    """
    if not DeltaTable.isDeltaTable(spark, silver_path):
        updates.write.format("delta").save(silver_path)
        return
    (
        DeltaTable.forPath(spark, silver_path).alias("t")
        .merge(updates.alias("s"), "t.order_id = s.order_id")
        .whenMatchedUpdateAll(condition="s.updated_at_ts > t.updated_at_ts")  # older events lose
        .whenNotMatchedInsertAll()
        .execute()
    )


# --------------------------------------------------------------------------------------
# Gold: conformed dimension + business aggregates, with cardinality guards.
# --------------------------------------------------------------------------------------

CUSTOMER_SCHEMA = "customer_id STRING, name STRING, region STRING, segment STRING, updated_at DATE"


def dim_customer(customers_raw: DataFrame) -> DataFrame:
    """Type-1 (current state) customer dimension: exactly one row per customer_id."""
    w = Window.partitionBy("customer_id").orderBy(F.col("updated_at").desc())
    return (
        customers_raw
        .withColumn("customer_id", F.upper(F.trim("customer_id")))
        .withColumn("region", F.coalesce(F.nullif(F.trim("region"), F.lit("")), F.lit("Unknown")))
        .withColumn("_rn", F.row_number().over(w))
        .where("_rn = 1")
        .drop("_rn")
    )


def fx_rates(spark: SparkSession) -> DataFrame:
    # DECIMAL, not DOUBLE: money is exact. 250 * 1.1 in floating point is 275.00000000000006.
    rows = [(c, Decimal(str(r))) for c, r in FX_RATES]
    return spark.createDataFrame(rows, "currency STRING, usd_rate DECIMAL(10,4)")


def assert_same_row_count(before: DataFrame, after: DataFrame, what: str) -> None:
    """Cheap-to-write, not free to run: two extra Spark jobs.

    In production, enforce key uniqueness on the dimension itself, for example with an
    expectation or a primary-key check in the dim pipeline, and keep this for tests.
    """
    b, a = before.count(), after.count()
    if a != b:
        raise ValueError(f"{what}: row count changed {b} -> {a}. Duplicate join keys (fan-out)?")


def enrich_orders(silver: DataFrame, dim: DataFrame, fx: DataFrame) -> DataFrame:
    revenue_orders = silver.where(F.col("status") != "cancelled")  # status is DQ-guaranteed non-NULL
    with_fx = revenue_orders.join(F.broadcast(fx), "currency", "left")
    enriched = (
        with_fx.join(F.broadcast(dim.select("customer_id", "region", "segment")), "customer_id", "left")
        .fillna({"region": "Unknown", "segment": "Unknown"})  # orphan keys (late-arriving dimension)
        .withColumn("amount_usd", (F.col("amount") * F.col("usd_rate")).cast("decimal(18,2)"))
        .withColumn("order_date", F.to_date("order_ts"))  # date in session TZ (UTC)
    )
    assert_same_row_count(revenue_orders, enriched, "enrich_orders")
    return enriched


def fct_daily_revenue(enriched: DataFrame) -> DataFrame:
    return enriched.groupBy("order_date", "region", "segment").agg(
        F.sum("amount_usd").alias("revenue_usd"),
        F.count("*").alias("order_count"),
    )


def top_customers_per_region(enriched: DataFrame, n: int = 3) -> DataFrame:
    per_customer = enriched.groupBy("region", "customer_id").agg(F.sum("amount_usd").alias("revenue_usd"))
    w = Window.partitionBy("region").orderBy(F.col("revenue_usd").desc(), F.col("customer_id"))
    return per_customer.withColumn("rank", F.dense_rank().over(w)).where(F.col("rank") <= n)


# --------------------------------------------------------------------------------------
# Orchestration (the only place with I/O). On Databricks: a Job or an SDP pipeline.
# --------------------------------------------------------------------------------------

def run_batch(spark: SparkSession, base: str, new_files: list[str]) -> dict:
    bronze_path, silver_path, quarantine_path = (f"{base}/bronze/orders", f"{base}/silver/orders",
                                                 f"{base}/silver/orders_quarantine")
    ingested = ingest_new_files(spark, new_files, bronze_path)
    if not ingested:
        return {"ingested": []}
    batch = (spark.read.format("delta").load(bronze_path)
             .where(F.col("_source_file_name").isin(ingested)))
    valid, quarantine = split_valid_quarantine(standardise(batch))
    quarantine.write.format("delta").mode("append").save(quarantine_path)
    merge_into_silver(spark, latest_per_order(valid), silver_path)
    return {"ingested": ingested}


def run_gold(spark: SparkSession, base: str, customers_csv: str) -> dict[str, DataFrame]:
    silver = spark.read.format("delta").load(f"{base}/silver/orders")
    dim = dim_customer(spark.read.option("header", True).schema(CUSTOMER_SCHEMA).csv(customers_csv))
    enriched = enrich_orders(silver, dim, fx_rates(spark))
    return {
        "silver": silver,
        "dim_customer": dim,
        "enriched": enriched,
        "fct_daily_revenue": fct_daily_revenue(enriched),
        "top_customers": top_customers_per_region(enriched),
    }


def run_all(spark: SparkSession, base: str) -> dict:
    files = write_landing_zone(base)
    first = run_batch(spark, base, [files["day1"]])
    second = run_batch(spark, base, [files["day1"], files["day2"]])  # day1 is skipped: idempotent
    replay = run_batch(spark, base, [files["day1"], files["day2"]])  # nothing new: no-op
    out = run_gold(spark, base, files["customers"])
    out.update({"runs": [first, second, replay], "files": files})
    return out


if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.spark_session import get_spark

    spark = get_spark("ex01")
    base = tempfile.mkdtemp(prefix="ex01_")
    result = run_all(spark, base)
    print("runs:", result["runs"])
    for name in ("silver", "fct_daily_revenue", "top_customers"):
        print(f"\n=== {name}")
        result[name].orderBy(*result[name].columns[:2]).show(truncate=False)
    print("\n=== quarantine")
    (spark.read.format("delta").load(f"{base}/silver/orders_quarantine")
     .select("order_id", "_raw_amount", "_raw_order_ts", "dq_failures").show(truncate=False))
    print("\n=== physical plan: fct_daily_revenue")
    result["fct_daily_revenue"].explain("formatted")
