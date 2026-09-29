"""The same job with the 8 bugs fixed. Each fix is labelled [B#] to match DEBUGGING_LOG.md."""
from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

FX_TO_USD = {"USD": 1.00, "EUR": 1.10, "GBP": 1.25}


def load_orders(web: DataFrame, store: DataFrame) -> DataFrame:
    # [B1] union() matches columns by POSITION. The store extract lists quantity before amount,
    #      so union() silently put quantities in the amount column. unionByName matches by name.
    return web.unionByName(store)


def latest_orders(orders: DataFrame) -> DataFrame:
    # [B2] orderBy().dropDuplicates() does not promise which row survives: the dedupe is
    #      hash aggregation and ignores the prior sort. Rank explicitly, with a deterministic tiebreak.
    w = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc(), F.col("source").desc())
    return orders.withColumn("_rn", F.row_number().over(w)).where("_rn = 1").drop("_rn")


def to_usd(orders: DataFrame) -> DataFrame:
    # [B3] when() without otherwise() yields NULL for unlisted values (GBP), and SUM skips NULLs,
    #      so revenue silently shrank. Use a mapping for every currency and fail loudly on unknowns.
    rate = F.create_map(*[x for k, v in FX_TO_USD.items() for x in (F.lit(k), F.lit(v))])[F.col("currency")]
    out = orders.withColumn("amount_usd", (F.col("amount") * rate).cast("decimal(18,2)"))
    unknown = out.where(F.col("amount_usd").isNull() & F.col("amount").isNotNull()).limit(1).collect()
    if unknown:
        raise ValueError(f"No FX rate for currency {unknown[0]['currency']!r}")
    return out


def revenue_orders(orders: DataFrame) -> DataFrame:
    # [B4] status != 'cancelled' is NULL when status is NULL, so those orders were filtered out.
    #      Business rule: NULL status means "not yet updated", which still counts as revenue.
    return orders.where(~F.col("status").eqNullSafe("cancelled"))


def attach_region(orders: DataFrame, regions: DataFrame) -> DataFrame:
    # [B5] The region mapping has duplicate customer_ids, so the join fanned out and double-counted.
    #      Enforce one row per key BEFORE joining.
    w = Window.partitionBy("customer_id").orderBy(F.col("valid_from").desc())
    one_per_key = regions.withColumn("_rn", F.row_number().over(w)).where("_rn = 1").select("customer_id", "region")
    return orders.join(one_per_key, "customer_id", "left").fillna({"region": "Unknown"})


def daily_revenue(orders: DataFrame) -> DataFrame:
    # [B6] Finance reports in UTC days. Converting to Los Angeles time first moved late-UTC orders
    #      to the previous day. (The session time zone is pinned to UTC in the job config.)
    # [B7] count("customer_id") skips NULLs, so orders without a customer vanished from order_count.
    return (orders.withColumn("order_date", F.to_date("order_ts"))
            .groupBy("order_date", "region")
            .agg(F.sum("amount_usd").alias("revenue_usd"), F.count(F.lit(1)).alias("order_count")))


def region_rank(daily: DataFrame) -> DataFrame:
    # [B8] No partitionBy gave a GLOBAL rank (wrong answer) computed in ONE task (Spark logs
    #      "No Partition Defined for Window operation!"): a correctness bug AND a scaling bug.
    w = Window.partitionBy("region").orderBy(F.col("revenue_usd").desc())
    return daily.withColumn("rank_in_region", F.rank().over(w))


def run(web: DataFrame, store: DataFrame, regions: DataFrame) -> DataFrame:
    orders = to_usd(latest_orders(load_orders(web, store)))
    return region_rank(daily_revenue(attach_region(revenue_orders(orders), regions)))
