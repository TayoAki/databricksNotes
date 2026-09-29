"""A customer's 'daily revenue by region' job, as inherited: it runs, it's green, and it's wrong.

There are 8 planted bugs. Don't read fixed version first. Read this file the way you would
read unfamiliar customer code, then run the tests: `pytest ex05_debug_kata -q -rx`.
The xfail reasons are the answer key, so try before you look.
"""
from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


def load_orders(web: DataFrame, store: DataFrame) -> DataFrame:
    return web.union(store)


def latest_orders(orders: DataFrame) -> DataFrame:
    return orders.orderBy(F.col("updated_at").desc()).dropDuplicates(["order_id"])


def to_usd(orders: DataFrame) -> DataFrame:
    return orders.withColumn(
        "amount_usd",
        F.when(F.col("currency") == "USD", F.col("amount"))
        .when(F.col("currency") == "EUR", F.col("amount") * F.lit(1.10)),
    )


def revenue_orders(orders: DataFrame) -> DataFrame:
    return orders.where(F.col("status") != "cancelled")


def attach_region(orders: DataFrame, regions: DataFrame) -> DataFrame:
    return orders.join(regions, "customer_id", "left").fillna({"region": "Unknown"})


def daily_revenue(orders: DataFrame) -> DataFrame:
    local = F.from_utc_timestamp("order_ts", "America/Los_Angeles")
    return (orders.withColumn("order_date", F.to_date(local))
            .groupBy("order_date", "region")
            .agg(F.round(F.sum("amount_usd"), 2).alias("revenue_usd"),
                 F.count("customer_id").alias("order_count")))


def region_rank(daily: DataFrame) -> DataFrame:
    w = Window.orderBy(F.col("revenue_usd").desc())
    return daily.withColumn("rank_in_region", F.rank().over(w))


def run(web: DataFrame, store: DataFrame, regions: DataFrame) -> DataFrame:
    orders = to_usd(latest_orders(load_orders(web, store)))
    return region_rank(daily_revenue(attach_region(revenue_orders(orders), regions)))
