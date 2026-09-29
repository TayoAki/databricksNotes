"""Tests for Exercise 02: SCD2 correctness invariants plus the failure modes of naive MERGEs."""
from __future__ import annotations

from datetime import datetime

import pytest
from pyspark.sql import functions as F

from ex02_scd2_merge import scd2

SCHEMA = "customer_id STRING, name STRING, city STRING, segment STRING, effective_ts TIMESTAMP"
T = lambda s: datetime.fromisoformat(s)  # noqa: E731

BATCH1 = [("C1", "Ann", "Austin", "SMB", T("2026-01-01")),
          ("C2", "Bob", "Boston", "SMB", T("2026-01-01")),
          ("C3", "Cat", "Chicago", "Enterprise", T("2026-01-01"))]
BATCH2 = [("C1", "Ann", "Denver", "SMB", T("2026-02-01")),        # moved city -> new version
          ("C2", "Bob", "Boston", "SMB", T("2026-02-01")),        # re-sent, unchanged -> no-op
          ("C4", "Dan", "Dallas", "SMB", T("2026-02-01"))]        # brand-new key
BATCH3 = [("C1", "Ann", "Denver", "Enterprise", T("2026-03-01")),  # two changes to one key
          ("C1", "Ann", "Seattle", "Enterprise", T("2026-03-15")),  #   in the same batch
          ("C2", "Bobby", "Boston", "SMB", T("2025-12-01")),        # LATE: older than current
          ("C3", "Cat", "Chicago", "Enterprise", T("2026-03-01"))]  # no-op


@pytest.fixture(scope="module")
def dim(spark, tmp_path_factory):
    path = str(tmp_path_factory.mktemp("ex02") / "dim_customer")
    late = {}
    for i, batch in enumerate([BATCH1, BATCH2, BATCH3], start=1):
        late[i] = scd2.scd2_upsert(spark, path, spark.createDataFrame(batch, SCHEMA)).collect()
    return {"path": path, "late": late}


def _rows(spark, path):
    return spark.read.format("delta").load(path)


def test_one_current_row_per_key(spark, dim):
    cur = _rows(spark, dim["path"]).where("is_current")
    assert cur.count() == cur.select("customer_id").distinct().count() == 4


def test_history_is_complete_and_ordered(spark, dim):
    c1 = [(r.city, r.segment, str(r.effective_from.date()), r.effective_to and str(r.effective_to.date()))
          for r in _rows(spark, dim["path"]).where("customer_id = 'C1'").orderBy("effective_from").collect()]
    assert c1 == [("Austin", "SMB", "2026-01-01", "2026-02-01"),
                  ("Denver", "SMB", "2026-02-01", "2026-03-01"),
                  ("Denver", "Enterprise", "2026-03-01", "2026-03-15"),   # intermediate version kept
                  ("Seattle", "Enterprise", "2026-03-15", None)]


def test_intervals_are_contiguous_and_valid(spark, dim):
    from pyspark.sql import Window
    w = Window.partitionBy("customer_id").orderBy("effective_from")
    gaps = (_rows(spark, dim["path"]).withColumn("next_from", F.lead("effective_from").over(w))
            .where("(effective_to IS NULL AND next_from IS NOT NULL) OR effective_to <> next_from "
                   "OR effective_to <= effective_from"))
    assert gaps.count() == 0


def test_no_op_updates_do_not_create_versions(spark, dim):
    counts = {r.customer_id: r["count"] for r in _rows(spark, dim["path"]).groupBy("customer_id").count().collect()}
    assert counts["C2"] == 1 and counts["C3"] == 1


def test_late_event_is_returned_not_applied(spark, dim):
    assert [(r.customer_id, r.name) for r in dim["late"][3]] == [("C2", "Bobby")]
    c2 = _rows(spark, dim["path"]).where("customer_id = 'C2' AND is_current").first()
    assert c2.name == "Bob"          # current row not corrupted by the older event


def test_rerun_is_idempotent(spark, dim):
    before = sorted(map(tuple, _rows(spark, dim["path"]).drop("customer_sk").collect()))
    scd2.scd2_upsert(spark, dim["path"], spark.createDataFrame(BATCH3, SCHEMA))
    after = sorted(map(tuple, _rows(spark, dim["path"]).drop("customer_sk").collect()))
    assert before == after


def test_surrogate_keys_unique(spark, dim):
    df = _rows(spark, dim["path"])
    assert df.count() == df.select("customer_sk").distinct().count()


def test_point_in_time_join(spark, dim):
    orders = spark.createDataFrame([("O1", "C1", T("2026-01-20")), ("O2", "C1", T("2026-03-10")),
                                    ("O3", "C1", T("2026-04-01")), ("O4", "C9", T("2026-04-01"))],
                                   "order_id STRING, customer_id STRING, order_ts TIMESTAMP")
    got = {r.order_id: r.city for r in scd2.point_in_time_join(orders, _rows(spark, dim["path"]), "order_ts").collect()}
    assert got == {"O1": "Austin", "O2": "Denver", "O3": "Seattle", "O4": None}


def test_naive_merge_fails_on_multiple_changes_per_key(spark, tmp_path):
    path = str(tmp_path / "naive")
    scd2.scd2_upsert(spark, path, spark.createDataFrame(BATCH1, SCHEMA))
    two_changes = spark.createDataFrame(BATCH3[:2], SCHEMA)   # C1 twice in one batch
    with pytest.raises(Exception, match="MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW"):
        scd2.naive_scd2_merge(spark, path, two_changes)


def test_lazy_dataframe_sees_later_writes(spark, tmp_path):
    """Why scd2_upsert pins versionAsOf: a Delta DataFrame is a recipe, not a snapshot."""
    path = str(tmp_path / "lazy")
    spark.range(3).write.format("delta").save(path)
    defined_before = spark.read.format("delta").load(path)
    pinned = spark.read.format("delta").option("versionAsOf", 0).load(path)
    spark.range(3, 10).write.format("delta").mode("append").save(path)
    assert defined_before.count() == 10      # evaluated now -> sees the append
    assert pinned.count() == 3               # time travel pins the snapshot
