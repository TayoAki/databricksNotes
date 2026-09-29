"""Tests for Exercise 01. Each test pins down one deliberate defect in the landing data."""
from __future__ import annotations

from decimal import Decimal

import pytest
from pyspark.sql import functions as F

from ex01_messy_orders_medallion import pipeline as p


@pytest.fixture(scope="module")
def result(spark, tmp_path_factory):
    base = str(tmp_path_factory.mktemp("ex01"))
    return p.run_all(spark, base) | {"base": base}


def _silver(result):
    return {r["order_id"]: r for r in result["silver"].collect()}


def test_bronze_keeps_every_line_including_garbage(spark, result):
    bronze = spark.read.format("delta").load(f"{result['base']}/bronze/orders")
    assert bronze.count() == 15                                   # 11 lines day 1 + 4 lines day 2
    assert bronze.where("_corrupt_record IS NOT NULL").count() == 1


def test_ingestion_is_idempotent(result):
    first, second, replay = result["runs"]
    assert first["ingested"] == ["orders_2026-09-01.jsonl"]
    assert second["ingested"] == ["orders_2026-09-02.jsonl"]      # day 1 skipped
    assert replay["ingested"] == []                               # nothing new: no-op


def test_silver_has_one_row_per_order(result):
    silver = result["silver"]
    assert silver.count() == silver.select("order_id").distinct().count() == 6


def test_standardisation(result):
    s = _silver(result)
    assert "ORD-1002" in s                                        # " ord-1002 " trimmed + upper-cased
    assert s["ORD-1001"]["amount"] == Decimal("1234.50")          # "1,234.50"
    assert s["ORD-1002"]["amount"] == Decimal("99.99")            # "$99.99"
    assert s["ORD-1003"]["amount"] == Decimal("250.00")           # bare JSON number
    assert s["ORD-1008"]["status"] == "cancelled"                 # "canceled" -> "cancelled"
    assert str(s["ORD-1003"]["order_ts"]) == "2026-09-01 12:30:00"  # MM/dd/yyyy format
    assert str(s["ORD-1011"]["order_ts"]) == "2026-09-02 02:00:00"  # epoch millis


def test_latest_state_wins_and_out_of_order_update_loses(result):
    s = _silver(result)
    assert s["ORD-1001"]["status"] == "delivered"   # newer update applied
    assert s["ORD-1002"]["status"] == "shipped"     # late-arriving OLDER "cancelled" ignored


def test_quarantine_reasons_are_explainable(spark, result):
    q = spark.read.format("delta").load(f"{result['base']}/silver/orders_quarantine")
    reasons = {r["order_id"]: set(r["dq_failures"]) for r in q.collect()}
    assert reasons["ORD-1004"] == {"customer_id_present"}
    assert reasons["ORD-1005"] == {"amount_positive"}
    assert reasons["ORD-1006"] == {"amount_positive"}   # NULL amount caught: rule is null-safe
    assert reasons["ORD-1007"] == {"order_ts_parsed"}
    assert reasons["ORD-1009"] == {"amount_positive"}   # "abc" -> try_cast -> NULL -> fails
    assert "not_corrupt" in reasons[None]               # the malformed JSON line
    assert q.count() == 6


def test_null_unsafe_rule_would_leak_the_null_amount(spark):
    """The lakeflow quarantine pitfall, reproduced: NOT(amount > 0) is NULL for NULL amount."""
    df = spark.createDataFrame([(None,), (Decimal("5"),), (Decimal("-1"),)], "amount DECIMAL(18,2)")
    naive = df.where(F.expr("NOT (amount > 0)")).count()                      # quarantine filter
    safe = df.where(~F.coalesce(F.expr("amount > 0"), F.lit(False))).count()
    assert (naive, safe) == (1, 2)


def test_dimension_is_deduplicated(result):
    dim = {r["customer_id"]: r for r in result["dim_customer"].collect()}
    assert len(dim) == 5
    assert dim["C002"]["segment"] == "Mid-Market"       # latest record wins
    assert dim["C004"]["region"] == "Unknown"           # empty region


def test_gold_revenue_reconciles_with_silver(result):
    gold_total = result["fct_daily_revenue"].agg(F.sum("revenue_usd")).first()[0]
    assert gold_total == Decimal("2219.49")
    rows = {(str(r["order_date"]), r["region"], r["segment"]): r["revenue_usd"]
            for r in result["fct_daily_revenue"].collect()}
    assert rows == {
        ("2026-09-01", "EMEA", "Enterprise"): Decimal("1234.50"),
        ("2026-09-01", "AMER", "Mid-Market"): Decimal("99.99"),
        ("2026-09-01", "APAC", "SMB"): Decimal("275.00"),       # 250 EUR * 1.10, exact decimal
        ("2026-09-02", "Unknown", "Unknown"): Decimal("550.00"),  # orphan customer C006 kept
        ("2026-09-02", "AMER", "Mid-Market"): Decimal("60.00"),
    }


def test_naive_join_to_undeduplicated_dimension_inflates_revenue(spark, result):
    """The fan-out trap: C002 appears twice in customers.csv, so its orders get counted twice."""
    raw_customers = (spark.read.option("header", True).schema(p.CUSTOMER_SCHEMA)
                     .csv(result["files"]["customers"]))
    silver = result["silver"].where("status != 'cancelled'")
    naive = (silver.join(p.fx_rates(spark), "currency", "left")
             .join(raw_customers, "customer_id", "left")
             .agg(F.sum((F.col("amount") * F.col("usd_rate")).cast("decimal(18,2)"))).first()[0])
    assert naive == Decimal("2379.48")          # 2219.49 + 159.99 double-counted
    with pytest.raises(ValueError, match="fan-out"):
        p.assert_same_row_count(silver, silver.join(raw_customers, "customer_id", "left"), "naive")


def test_top_customers_per_region(result):
    top = {(r["region"], r["customer_id"]): r["rank"] for r in result["top_customers"].collect()}
    assert top == {("EMEA", "C001"): 1, ("AMER", "C002"): 1, ("APAC", "C003"): 1, ("Unknown", "C006"): 1}
