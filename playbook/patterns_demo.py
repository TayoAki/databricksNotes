"""Runs every SQL idiom quoted in playbook/01-computational-thinking.md on tiny data, so each one is verified.
    pip install -r exercises/requirements.txt && python playbook/patterns_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exercises"))
from common.spark_session import get_spark

s = get_spark("patterns")


def show(title, sql):
    print(f"--- {title}")
    for r in s.sql(sql).collect():
        print("   ", tuple(r))


s.createDataFrame([
    ("u1", "2026-09-01 10:00:00"), ("u1", "2026-09-01 10:10:00"), ("u1", "2026-09-01 11:30:00"),
    ("u1", "2026-09-01 11:45:00"), ("u2", "2026-09-01 09:00:00")],
    "user_id STRING, ts STRING").selectExpr("user_id", "to_timestamp(ts) ts").createOrReplaceTempView("clicks")
show("P9 sessionization: new session after 30 min of inactivity", """
WITH flagged AS (
  SELECT *, CASE WHEN ts - LAG(ts) OVER (PARTITION BY user_id ORDER BY ts) <= INTERVAL 30 MINUTES
                 THEN 0 ELSE 1 END AS new_session
  FROM clicks)
SELECT user_id, ts, SUM(new_session) OVER (PARTITION BY user_id ORDER BY ts) AS session_no
FROM flagged ORDER BY user_id, ts""")

s.createDataFrame([("c1", d) for d in ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-05", "2026-09-06"]],
                  "customer_id STRING, d STRING").selectExpr("customer_id", "to_date(d) d") \
 .createOrReplaceTempView("active_days")
show("P10 gaps-and-islands: consecutive-day streaks", """
WITH g AS (SELECT customer_id, d,
                  date_sub(d, CAST(ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY d) AS INT)) AS island
           FROM active_days)
SELECT customer_id, min(d) AS streak_start, max(d) AS streak_end, count(*) AS days
FROM g GROUP BY customer_id, island ORDER BY streak_start""")

s.createDataFrame([("a1", "2026-09-01", 100), ("a1", "2026-09-15", 120), ("a1", "2026-09-30", 90),
                   ("a2", "2026-09-01", 50), ("a2", "2026-09-30", 70)],
                  "account STRING, d STRING, balance INT").selectExpr("account", "to_date(d) d", "balance") \
 .createOrReplaceTempView("balances")
show("P11 semi-additive: month-end balance (right) vs SUM over days (wrong)", """
SELECT date_trunc('month', d) AS month,
       SUM(balance) AS summed_over_days_WRONG,
       SUM(month_end) AS month_end_balance
FROM (SELECT *, CASE WHEN d = max(d) OVER (PARTITION BY account, date_trunc('month', d))
                     THEN balance END AS month_end FROM balances)
GROUP BY 1""")

s.createDataFrame([("o1", "C1", "2026-03-01"), ("o2", "C1", "2026-08-01")],
                  "order_id STRING, customer_id STRING, d STRING").selectExpr("order_id", "customer_id", "to_date(d) d") \
 .createOrReplaceTempView("orders")
s.createDataFrame([("C1", "SMB", "2026-01-01", "2026-06-01"), ("C1", "Enterprise", "2026-06-01", None)],
                  "customer_id STRING, segment STRING, f STRING, t STRING") \
 .selectExpr("customer_id", "segment", "to_date(f) valid_from", "to_date(t) valid_to") \
 .createOrReplaceTempView("dim_customer_scd2")
show("P6 point-in-time join: segment as of the order date (half-open interval)", """
SELECT o.order_id, o.d, c.segment
FROM orders o LEFT JOIN dim_customer_scd2 c
  ON o.customer_id = c.customer_id
 AND o.d >= c.valid_from AND (c.valid_to IS NULL OR o.d < c.valid_to)
ORDER BY o.order_id""")

s.createDataFrame([("r1", "EMEA", 10), ("r2", "EMEA", 30), ("r3", "EMEA", 30), ("r4", "AMER", 5)],
                  "rep STRING, region STRING, sales INT").createOrReplaceTempView("reps")
show("P8 top-N per group: row_number (exactly N) vs dense_rank (ties included)", """
SELECT region, rep, sales,
       ROW_NUMBER() OVER (PARTITION BY region ORDER BY sales DESC, rep) AS rn,
       DENSE_RANK() OVER (PARTITION BY region ORDER BY sales DESC) AS dr
FROM reps ORDER BY region, rn""")
