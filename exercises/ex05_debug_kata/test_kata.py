"""Spec-as-tests. The fixed module must pass; the buggy module must fail each test (strict xfail).

Run with -rx to print the answer key (xfail reasons):  pytest ex05_debug_kata -q -rx
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from pyspark.sql import functions as F

from ex05_debug_kata import customer_pipeline_buggy as buggy
from ex05_debug_kata import customer_pipeline_fixed as fixed
from ex05_debug_kata import kata_data as K


def impls(bug: str):
    # raises=AssertionError matters: a bare xfail is satisfied by ANY exception, including a
    # broken fixture, which would then hide behind a green "expected failure". Only a WRONG
    # ANSWER should count as the expected failure. (I learned this by breaking a fixture.)
    return [pytest.param(fixed, id="fixed"),
            pytest.param(buggy, id="buggy",
                         marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=bug))]


@pytest.fixture(scope="module")
def data(spark):
    return {"web": spark.createDataFrame(K.WEB, K.WEB_SCHEMA),
            "store": spark.createDataFrame(K.STORE, K.STORE_SCHEMA),
            "regions": spark.createDataFrame(K.REGIONS, K.REGION_SCHEMA)}


@pytest.mark.parametrize("m", impls("B1: union() is positional -> store quantity lands in amount"))
def test_b1_sources_are_aligned_by_name(m, data):
    s1 = m.load_orders(data["web"], data["store"]).where("order_id = 'S1'").first()
    assert (s1.amount, s1.quantity) == (D("20.00"), 2)


@pytest.mark.parametrize("m", [buggy, fixed], ids=["buggy", "fixed"])
def test_b2_latest_version_wins_locally(m, spark, data):
    """Passes for BOTH implementations on a laptop, and that is the whole lesson of B2.

    The buggy plan is Aggregate[first(...)] over a global Sort. Locally, shuffle blocks are
    read in map-partition order, and partition 0 holds the newest rows, so it is right by
    accident. On a cluster, blocks arrive in network order. PySpark's own docstring says
    first() "is non-deterministic because its results depends on the order of the rows which
    may be non-deterministic after a shuffle". I tried 11 layouts and could not make it fail
    locally. You catch this bug by knowing the semantics, not by testing on a laptop.
    """
    unioned = fixed.load_orders(data["web"], data["store"])
    results = {m.latest_orders(unioned.repartition(n, "source")).where("order_id = 'W7'").first().amount
               for n in (1, 2, 3, 4, 8)}
    assert results == {D("12.00")}


@pytest.mark.parametrize("m", impls("B2: dedupe = first() after a shuffle -> order-dependent on a cluster"))
def test_b2_dedupe_is_deterministic_by_construction(m, data):
    """Structural test: the optimized plan must not keep 'whichever row came first'."""
    unioned = fixed.load_orders(data["web"], data["store"])
    plan = m.latest_orders(unioned)._jdf.queryExecution().optimizedPlan().toString()
    assert not any(fn in plan for fn in ("first(", "last(", "any_value("))


@pytest.mark.parametrize("m", impls("B3: when() without otherwise() -> GBP becomes NULL, SUM skips it"))
def test_b3_every_currency_is_converted(m, data):
    w3 = m.to_usd(data["web"]).where("order_id = 'W3'").first()
    assert w3.amount_usd == D("100.00")


def test_b3_unknown_currency_fails_loudly(spark):
    jpy = spark.createDataFrame([(D("1.00"), "JPY")], "amount DECIMAL(18,2), currency STRING")
    with pytest.raises(ValueError, match="JPY"):
        fixed.to_usd(jpy)


@pytest.mark.parametrize("m", impls("B4: status != 'cancelled' is NULL for NULL status -> row filtered out"))
def test_b4_null_status_orders_count_as_revenue(m, data):
    kept = {r.order_id for r in m.revenue_orders(data["web"]).collect()}
    assert "W2" in kept and "W6" not in kept


@pytest.mark.parametrize("m", impls("B5: duplicate customer_id in region map -> join fan-out"))
def test_b5_region_join_preserves_row_count(m, data):
    orders = data["web"]
    assert m.attach_region(orders, data["regions"]).count() == orders.count()


@pytest.mark.parametrize("m", impls("B6: dates bucketed in Los Angeles time; Finance reports UTC days"))
def test_b6_order_dates_are_utc_days(m, data):
    w4 = fixed.attach_region(fixed.to_usd(data["web"].where("order_id = 'W4'")), data["regions"])
    assert m.daily_revenue(w4).first().order_date == date(2026, 9, 2)


@pytest.mark.parametrize("m", impls("B7: count('customer_id') skips NULLs -> orders without customer vanish"))
def test_b7_order_count_includes_orders_without_customer(m, data):
    w5 = fixed.attach_region(fixed.to_usd(data["web"].where("order_id = 'W5'")), data["regions"])
    assert m.daily_revenue(w5).first().order_count == 1


@pytest.mark.parametrize("m", impls("B8: Window without partitionBy -> global rank (and one task)"))
def test_b8_rank_is_within_region(m, spark):
    daily = spark.createDataFrame([("EMEA", D("10")), ("EMEA", D("5")), ("AMER", D("7"))],
                                  "region STRING, revenue_usd DECIMAL(18,2)")
    ranks = {(r.region, r.revenue_usd): r.rank_in_region for r in m.region_rank(daily).collect()}
    assert ranks == {("EMEA", D("10")): 1, ("EMEA", D("5")): 2, ("AMER", D("7")): 1}


@pytest.mark.parametrize("m", impls("all bugs combined"))
def test_end_to_end_total(m, data):
    out = m.run(data["web"], data["store"], data["regions"])
    assert out.agg(F.sum("revenue_usd")).first()[0] == K.EXPECTED_TOTAL
