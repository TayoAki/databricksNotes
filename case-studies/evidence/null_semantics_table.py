"""Every NULL rule quoted in playbook/07-null-semantics.md, verified on Spark 4.0.1 (ANSI on)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "exercises"))
from common.spark_session import get_spark

s = get_spark("nulls")
s.createDataFrame([(1, "A", 10), (2, None, 20), (3, "B", None), (None, "C", 5)],
                  "id INT, status STRING, amount INT").createOrReplaceTempView("t")
checks = {
    "NULL = NULL":                              "SELECT NULL = NULL",
    "NULL <=> NULL (null-safe equal)":          "SELECT NULL <=> NULL",
    "NOT (NULL)":                               "SELECT NOT CAST(NULL AS BOOLEAN)",
    "NULL AND false":                           "SELECT CAST(NULL AS BOOLEAN) AND false",
    "NULL OR true":                             "SELECT CAST(NULL AS BOOLEAN) OR true",
    "rows kept by WHERE status != 'A'":         "SELECT count(*) FROM t WHERE status != 'A'",
    "rows kept by WHERE NOT (status <=> 'A')":  "SELECT count(*) FROM t WHERE NOT (status <=> 'A')",
    "count(*) vs count(amount)":                "SELECT concat(count(*), ' vs ', count(amount)) FROM t",
    "avg(amount) (ignores NULLs)":              "SELECT avg(amount) FROM t",
    "sum over zero rows":                       "SELECT sum(amount) FROM t WHERE 1 = 0",
    "count over zero rows":                     "SELECT count(amount) FROM t WHERE 1 = 0",
    "1 NOT IN (2, NULL)":                       "SELECT 1 NOT IN (2, NULL)",
    "rows from NOT IN subquery with a NULL":    "SELECT count(*) FROM t WHERE amount NOT IN (SELECT id FROM t)",
    "concat('a', NULL)":                        "SELECT concat('a', NULL)",
    "concat_ws('|', 'a', NULL, 'b')":           "SELECT concat_ws('|', 'a', NULL, 'b')",
    "greatest(1, NULL, 3)":                     "SELECT greatest(1, NULL, 3)",
    "NULL keys in GROUP BY (groups)":           "SELECT count(*) FROM (SELECT status FROM t GROUP BY status)",
    "count(DISTINCT status)":                   "SELECT count(DISTINCT status) FROM t",
    "join on NULL key matches?":                "SELECT count(*) FROM t a JOIN t b ON a.status = b.status WHERE a.status IS NULL",
    "join on NULL key with <=>":                "SELECT count(*) FROM t a JOIN t b ON a.status <=> b.status WHERE a.status IS NULL",
    "CASE WHEN NULL THEN 1 ELSE 0 END":         "SELECT CASE WHEN CAST(NULL AS BOOLEAN) THEN 1 ELSE 0 END",
    "try_cast('abc' AS INT)":                   "SELECT try_cast('abc' AS INT)",
}
for label, q in checks.items():
    print(f"{label:42} -> {s.sql(q).first()[0]}")
try:
    s.sql("SELECT CAST('abc' AS INT)").first()
except Exception as e:
    print(f"{'CAST(abc AS INT) under ANSI':42} -> ERROR {str(e).split(']')[0]}]")
