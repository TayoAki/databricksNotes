"""System-table SCD2 trap from databricks-waf (compute_cluster_inventory.sql, server/collect/sql/history.ts):
filtering `delete_time IS NULL` in the same query as the ROW_NUMBER() that picks the latest row resurrects
deleted objects. WAF measured 6,136,941 "live" clusters where 135,177 existed (45x). Runs on OSS Spark."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "exercises"))
from common.spark_session import get_spark

s = get_spark("scd-filter-before-rank")
# system.compute.clusters shape: one row per configuration change, and a final row when the cluster is deleted
s.createDataFrame([
    ("ws1", "c1", "2026-09-01 09:00:00", None, 60),                    # created
    ("ws1", "c1", "2026-09-02 09:00:00", None, 30),                    # edited
    ("ws1", "c1", "2026-09-03 09:00:00", "2026-09-03 09:00:00", 30),   # deleted: the only row with delete_time
    ("ws1", "c2", "2026-09-01 10:00:00", None, 0),                     # created, never deleted, no auto-termination
], "workspace_id STRING, cluster_id STRING, change_time STRING, delete_time STRING, auto_termination_minutes INT") \
 .selectExpr("workspace_id", "cluster_id", "to_timestamp(change_time) change_time",
            "to_timestamp(delete_time) delete_time", "auto_termination_minutes") \
 .createOrReplaceTempView("clusters")

filter_then_rank = """
SELECT cluster_id, auto_termination_minutes FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY workspace_id, cluster_id ORDER BY change_time DESC) AS recency
  FROM clusters WHERE delete_time IS NULL                -- filters rows BEFORE the window picks one
) WHERE recency = 1 ORDER BY cluster_id"""
rank_then_filter = """
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY workspace_id, cluster_id ORDER BY change_time DESC) AS recency
  FROM clusters
)
SELECT cluster_id, auto_termination_minutes FROM ranked
WHERE recency = 1 AND delete_time IS NULL ORDER BY cluster_id"""
for label, q in [("filter-then-rank (bug)", filter_then_rank), ("rank-then-filter (fix)", rank_then_filter)]:
    rows = [tuple(r) for r in s.sql(q).collect()]
    share = sum(1 for _, m in rows if m and m > 0) / len(rows)
    print(f"{label:24} live clusters = {rows}  -> auto-termination share = {share:.0%}")
# Observed:
# filter-then-rank (bug)   live clusters = [('c1', 30), ('c2', 0)]  -> auto-termination share = 50%
# rank-then-filter (fix)   live clusters = [('c2', 0)]              -> auto-termination share = 0%
