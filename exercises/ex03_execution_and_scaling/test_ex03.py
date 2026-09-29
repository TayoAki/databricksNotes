"""Plan-shape tests: assert WHAT Spark decided to do, not how long it took (timings are flaky)."""
from __future__ import annotations

import re

from pyspark.sql import Window
from pyspark.sql import functions as F

from ex03_execution_and_scaling import lab


def test_narrow_transformations_do_not_shuffle(spark):
    assert lab.count_exchanges(lab.narrow(lab.sales(spark))) == 0


def test_aggregation_shuffles_once(spark):
    assert lab.count_exchanges(lab.wide(lab.sales(spark))) == 1


def test_small_dimension_is_broadcast_and_big_side_never_moves(spark):
    plan = lab.join_plan(spark, "10MB")
    assert "BroadcastHashJoin" in plan and "Exchange hashpartitioning" not in plan


def test_disabling_broadcast_forces_sort_merge_with_two_shuffles(spark):
    plan = lab.join_plan(spark, "-1")
    assert "SortMergeJoin" in plan and plan.count("Exchange hashpartitioning") == 2


def test_top1_per_group_pushes_limit_below_the_shuffle(spark):
    w = Window.partitionBy("customer_id").orderBy(F.col("amount").desc())
    df = lab.sales(spark).withColumn("rn", F.row_number().over(w)).where("rn = 1")
    plan = lab.executed_plan(df)
    assert "WindowGroupLimit" in plan
    # the partial WindowGroupLimit sits BEFORE (below) the shuffle in the plan tree
    assert plan.rfind("WindowGroupLimit") > plan.find("Exchange hashpartitioning")


def test_hot_key_lands_in_one_task_and_salting_spreads_it(spark):
    sk = lab.skewed_sales(spark)
    unsalted = lab.join_task_sizes(spark, sk, lab.customers(spark), salted=False)
    salted = lab.join_task_sizes(spark, sk, lab.customers(spark), salted=True)
    assert unsalted[0] / sum(unsalted) > 0.85          # one task does ~90% of the work
    assert salted[0] / sum(salted) < 0.35              # spread over several tasks
    assert sum(unsalted) == sum(salted)                # salting must not change the result size


def test_aqe_detects_and_splits_the_skewed_join(spark):
    _, plan = lab.aqe_skew_join(spark)
    assert "isFinalPlan=true" in plan and "skew=true" in plan


def test_python_udf_crosses_into_python_workers(spark):
    df = lab.names(spark, 1000)
    assert "BatchEvalPython" in lab.executed_plan(df.select(lab.py_upper("name")))
    assert "ArrowEvalPython" in lab.executed_plan(df.select(lab.pandas_upper("name")))
    assert "EvalPython" not in lab.executed_plan(df.select(F.upper("name")))
    assert df.select(lab.pandas_upper("name").alias("u")).first().u == "CUSTOMER_0"


def test_select_and_withcolumn_loop_build_the_same_result(spark):
    s = lab.sales(spark, 100)
    a = lab.many_columns_loop(s, 20)
    b = lab.many_columns_select(s, 20)
    assert a.columns == b.columns and a.exceptAll(b).count() == 0


def test_partition_filter_prunes_directories(spark, tmp_path):
    t = lab.write_partitioned(spark, str(tmp_path / "sales_by_date"))
    plan = lab.executed_plan(t.where("order_date = '2026-01-05' AND amount > 50"))
    part = re.search(r"PartitionFilters: \[([^\]]*)\]", plan).group(1)
    assert "order_date" in part                       # date filter -> directory pruning
    assert "amount" not in part                       # non-partition predicate -> data filter
