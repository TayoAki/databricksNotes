"""Exercise 03: see how Spark executes your code before you have to defend it.

Every experiment answers a question an interviewer (or a customer's platform team) asks:
  1. "Which of your steps cause a shuffle?"                  -> narrow vs wide transformations
  2. "How will that join behave when the tables grow?"         -> broadcast vs sort-merge
  3. "What if one customer has 90% of the rows?"               -> skew, salting, AQE
  4. "Why is this notebook slow to even *start*?"              -> withColumn loops vs one select
  5. "Can we just use a Python function here?"                 -> Python UDF vs native vs pandas UDF
  6. "Does the filter actually skip data?"                     -> partition pruning / pushdown

Run: python -m ex03_execution_and_scaling.lab   (from exercises/). It prints plans and timings.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

import pandas as pd
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import StringType


def executed_plan(df: DataFrame) -> str:
    """The physical plan as a string. For AQE, run an action first to see the *final* plan."""
    return df._jdf.queryExecution().executedPlan().toString()


def count_exchanges(df: DataFrame) -> int:
    # Match shuffle exchanges only; a BroadcastExchange does not move the big side.
    plan = executed_plan(df)
    return sum(1 for line in plan.splitlines() if "Exchange hashpartitioning" in line
               or "Exchange SinglePartition" in line or "Exchange rangepartitioning" in line)


@contextmanager
def conf(spark: SparkSession, **settings):
    old = {k: spark.conf.get(k, None) for k in settings}
    for k, v in settings.items():
        spark.conf.set(k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            spark.conf.unset(k) if v is None else spark.conf.set(k, v)


def sales(spark: SparkSession, n: int = 200_000) -> DataFrame:
    return spark.range(n).select(
        F.col("id").alias("order_id"),
        (F.col("id") % 1000).alias("customer_id"),
        (F.col("id") % 97 * 1.5).alias("amount"),
        F.date_add(F.lit("2026-01-01"), (F.col("id") % 30).cast("int")).alias("order_date"),
    )


def customers(spark: SparkSession) -> DataFrame:
    return spark.range(1000).select(F.col("id").alias("customer_id"),
                                    F.concat(F.lit("seg_"), F.col("id") % 5).alias("segment"))


# 1. Narrow vs wide --------------------------------------------------------------------------
def narrow(df: DataFrame) -> DataFrame:
    return df.where("amount > 10").select("order_id", (F.col("amount") * 2).alias("amt2"))


def wide(df: DataFrame) -> DataFrame:
    return df.groupBy("customer_id").agg(F.sum("amount").alias("revenue"))


# 2. Join strategies --------------------------------------------------------------------------
def join_plan(spark: SparkSession, broadcast_threshold: str) -> str:
    with conf(spark, **{"spark.sql.autoBroadcastJoinThreshold": broadcast_threshold,
                        "spark.sql.adaptive.enabled": "false"}):  # static plan, no AQE rewrites
        return executed_plan(sales(spark).join(customers(spark), "customer_id"))


# 3. Skew -------------------------------------------------------------------------------------
def skewed_sales(spark: SparkSession, n: int = 400_000, hot_share: float = 0.9) -> DataFrame:
    """hot_share of the rows belong to customer 0: the 'one giant customer' problem."""
    return spark.range(n).select(
        F.when(F.rand(seed=7) < hot_share, F.lit(0)).otherwise((F.col("id") % 999) + 1).alias("customer_id"),
        F.col("id").alias("order_id"),
    )


def join_task_sizes(spark: SparkSession, big: DataFrame, small: DataFrame, salted: bool) -> list[int]:
    """Rows handled by each task of a *shuffle* join (broadcast and AQE off: the raw truth)."""
    with conf(spark, **{"spark.sql.autoBroadcastJoinThreshold": "-1", "spark.sql.adaptive.enabled": "false",
                        "spark.sql.shuffle.partitions": "16"}):
        joined = salted_join(big, small) if salted else big.join(small, "customer_id")
        return partition_sizes(joined)


def partition_sizes(df: DataFrame) -> list[int]:
    return sorted((r["count"] for r in df.groupBy(F.spark_partition_id().alias("p")).count().collect()),
                  reverse=True)


def hash_partitioned_by_key(df: DataFrame, n: int = 8) -> DataFrame:
    return df.repartition(n, "customer_id")          # what a shuffle join does to each side


def salted_join(big: DataFrame, small: DataFrame, salt_buckets: int = 8) -> DataFrame:
    """Spread the hot key over salt_buckets tasks: random salt on the big side, and the
    small side replicated once per salt value (explode). The cost is salt_buckets x the small side."""
    big_s = big.withColumn("salt", (F.rand(seed=11) * salt_buckets).cast("int"))
    small_s = small.withColumn("salt", F.explode(F.sequence(F.lit(0), F.lit(salt_buckets - 1))))
    return big_s.join(small_s, ["customer_id", "salt"]).drop("salt")


def aqe_skew_join(spark: SparkSession) -> tuple[DataFrame, str]:
    """Let AQE find and split the skewed partition at runtime (no code change)."""
    settings = {
        "spark.sql.adaptive.enabled": "true",
        "spark.sql.adaptive.skewJoin.enabled": "true",
        "spark.sql.autoBroadcastJoinThreshold": "-1",          # force a shuffle join
        # Lowered so laptop-sized data counts as "skewed" (defaults: 5x median AND 256MB).
        "spark.sql.adaptive.skewJoin.skewedPartitionFactor": "2",
        "spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes": "1KB",
        "spark.sql.adaptive.advisoryPartitionSizeInBytes": "16KB",
        "spark.sql.adaptive.coalescePartitions.enabled": "false",
        "spark.sql.shuffle.partitions": "8",
    }
    with conf(spark, **settings):
        joined = skewed_sales(spark).join(customers(spark), "customer_id")
        # The action must run on THIS DataFrame's QueryExecution. A write/count builds a
        # new plan, and this one would still show the initial (isFinalPlan=false) plan.
        joined.collect()
        return joined, executed_plan(joined)


# 4. withColumn in a loop vs one select --------------------------------------------------------
def many_columns_loop(df: DataFrame, n: int) -> DataFrame:
    for i in range(n):
        df = df.withColumn(f"c{i}", F.col("amount") + i)   # each call re-analyses the growing plan
    return df


def many_columns_select(df: DataFrame, n: int) -> DataFrame:
    return df.select("*", *[(F.col("amount") + i).alias(f"c{i}") for i in range(n)])


# 5. UDFs ---------------------------------------------------------------------------------------
@F.udf(returnType=StringType())
def py_upper(s):  # row-at-a-time: pickled across the JVM <-> Python boundary
    return s.upper() if s is not None else None


@F.pandas_udf(StringType())
def pandas_upper(s: pd.Series) -> pd.Series:  # vectorised: Arrow batches
    return s.str.upper()


def names(spark: SparkSession, n: int = 300_000) -> DataFrame:
    return spark.range(n).select(F.concat(F.lit("customer_"), F.col("id")).alias("name"))


# 6. Pruning ------------------------------------------------------------------------------------
def write_partitioned(spark: SparkSession, path: str) -> DataFrame:
    sales(spark, 50_000).write.format("delta").partitionBy("order_date").mode("overwrite").save(path)
    return spark.read.format("delta").load(path)


def timed(fn, *args, repeat: int = 1):
    best = float("inf")
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn(*args)
        best = min(best, time.perf_counter() - t0)
    return best


if __name__ == "__main__":  # pragma: no cover
    import sys
    import tempfile
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.spark_session import get_spark

    spark = get_spark("ex03", shuffle_partitions=8)
    s = sales(spark)

    print("\n### 1. Shuffles (Exchange operators)")
    for label, df in [("narrow: filter+select", narrow(s)), ("wide: groupBy", wide(s)),
                      ("window: row_number per customer",
                       s.withColumn("rn", F.row_number().over(Window.partitionBy("customer_id").orderBy("order_id"))))]:
        print(f"  {label:34} exchanges = {count_exchanges(df)}")

    print("\n### 2. Join strategy")
    for thr in ["10MB", "-1"]:
        plan = join_plan(spark, thr)
        kind = "BroadcastHashJoin" if "BroadcastHashJoin" in plan else "SortMergeJoin" if "SortMergeJoin" in plan else "?"
        print(f"  autoBroadcastJoinThreshold={thr:5} -> {kind}, shuffles={plan.count('Exchange hashpartitioning')}")

    print("\n### 3. Skew")
    sk = skewed_sales(spark)
    print("  rows per task after hash-partitioning by customer_id:", partition_sizes(hash_partitioned_by_key(sk)))
    print("  shuffle-join tasks, unsalted (16 partitions):", join_task_sizes(spark, sk, customers(spark), False)[:6], "...")
    print("  shuffle-join tasks, salted x8 (16 partitions):", join_task_sizes(spark, sk, customers(spark), True)[:9], "...")
    joined, plan = aqe_skew_join(spark)
    print("  AQE final plan mentions skew handling:", "skew=true" in plan)
    print("  groupBy on the skewed key (partial aggregation absorbs skew):",
          f"{timed(lambda: wide(sk.withColumn('amount', F.lit(1))).collect()):.2f}s")

    print("\n### 4. Building a 300-column DataFrame (driver-side analysis cost)")
    for n in (100, 200, 300):
        t_loop = timed(many_columns_loop, s, n)
        t_sel = timed(many_columns_select, s, n)
        print(f"  n={n:3}: withColumn loop {t_loop:6.2f}s | single select {t_sel:5.2f}s")

    print("\n### 5. UDFs (300k rows, noop sink)")
    df = names(spark)
    for label, col in [("native F.upper", F.upper("name")), ("pandas_udf (Arrow)", pandas_upper("name")),
                       ("python udf (row-at-a-time)", py_upper("name"))]:
        t = timed(lambda: df.select(col.alias("u")).write.format("noop").mode("overwrite").save(), repeat=2)
        print(f"  {label:28} {t:5.2f}s")
    print("  plan operator for python udf:",
          [op for op in ("BatchEvalPython", "ArrowEvalPython") if op in executed_plan(df.select(py_upper("name")))])

    print("\n### 6. Partition pruning")
    t = write_partitioned(spark, tempfile.mkdtemp() + "/sales_by_date")
    plan = executed_plan(t.where("order_date = '2026-01-05' AND amount > 50"))
    import re
    for key in ("PartitionFilters", "PushedFilters"):
        m = re.search(key + r": \[[^\]]*\]", plan)
        print("  ", m.group(0) if m else f"{key}: (not found)")
