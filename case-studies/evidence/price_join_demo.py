"""billing.usage x list_prices: containment join (starter-journey) vs point-in-time join (databricks-waf).
A usage row that straddles a price change matches NO price under containment and silently vanishes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "exercises"))
from common.spark_session import get_spark

s = get_spark("pricejoin")
s.createDataFrame([("r1", "SKU_A", "2026-09-01 10:00:00", "2026-09-01 11:00:00", 10.0),
                   ("r2", "SKU_A", "2026-09-01 11:30:00", "2026-09-01 12:30:00", 10.0),   # straddles 12:00
                   ("r3", "SKU_A", "2026-09-01 13:00:00", "2026-09-01 14:00:00", 10.0)],
                  "record_id STRING, sku_name STRING, s STRING, e STRING, usage_quantity DOUBLE") \
 .selectExpr("record_id", "sku_name", "to_timestamp(s) usage_start_time", "to_timestamp(e) usage_end_time",
             "usage_quantity").createOrReplaceTempView("usage")
s.createDataFrame([("SKU_A", "2026-01-01 00:00:00", "2026-09-01 12:00:00", 0.50),
                   ("SKU_A", "2026-09-01 12:00:00", None, 0.55)],
                  "sku_name STRING, ps STRING, pe STRING, price DOUBLE") \
 .selectExpr("sku_name", "to_timestamp(ps) price_start_time", "to_timestamp(pe) price_end_time", "price") \
 .createOrReplaceTempView("prices")
containment = """SELECT count(*) matched_rows, round(sum(usage_quantity*price),2) cost
  FROM usage u JOIN prices p ON u.sku_name = p.sku_name
   AND u.usage_start_time >= p.price_start_time
   AND (u.usage_end_time <= p.price_end_time OR p.price_end_time IS NULL)"""
point_in_time = """SELECT count(*) matched_rows, count(p.price) priced_rows,
       count(*) - count(DISTINCT record_id) duplicate_matches, round(sum(usage_quantity*price),2) cost
  FROM usage u LEFT JOIN prices p ON u.sku_name = p.sku_name
   AND u.usage_end_time >= p.price_start_time
   AND (p.price_end_time IS NULL OR u.usage_end_time < p.price_end_time)"""
print("containment  :", s.sql(containment).first().asDict())
print("point-in-time:", s.sql(point_in_time).first().asDict())
# Observed: containment -> {'matched_rows': 2, 'cost': 10.5}
#           point-in-time -> {'matched_rows': 3, 'priced_rows': 3, 'duplicate_matches': 0, 'cost': 16.0}
