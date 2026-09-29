"""An error zoo: trigger common Spark / Delta errors on purpose and print their exact error class,
so the table in playbook/04-resilience-and-debugging.md is backed by real messages.
    pip install -r exercises/requirements.txt && python playbook/error_signatures_demo.py
"""
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exercises"))
os.chdir(tempfile.mkdtemp())   # keep spark-warehouse/ (created by saveAsTable) out of the repo
from common.spark_session import get_spark
from delta.tables import DeltaTable

s = get_spark("error-zoo")
d = tempfile.mkdtemp()


def attempt(label, fn):
    try:
        fn()
        print(f"{label:34} -> no error")
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        m = re.search(r"\[([A-Z_]+(?:\.[A-Z_]+)?)\]", msg)
        print(f"{label:34} -> {m.group(1) if m else type(e).__name__}: {msg.splitlines()[0][:110]}")


a = s.createDataFrame([(1, "x")], "id INT, v STRING")
b = s.createDataFrame([(1, "y")], "id INT, v STRING")

attempt("cast garbage (ANSI on)", lambda: s.sql("SELECT CAST('abc' AS INT)").collect())
attempt("divide by zero (ANSI on)", lambda: s.sql("SELECT 1 / 0").collect())
attempt("ambiguous column after join", lambda: a.join(b, "id").select("v").collect())
attempt("unknown column", lambda: a.select("amount").collect())
attempt("unknown table", lambda: s.table("default.orders_missing").collect())
# A 3-part name on OSS Spark (no Unity Catalog) fails differently: REQUIRES_SINGLE_PART_NAMESPACE.
attempt("3-part name without Unity Catalog", lambda: s.table("main.shop.orders").collect())

target = f"{d}/t"
s.createDataFrame([(1, "old")], "id INT, v STRING").write.format("delta").save(target)
dup_source = s.createDataFrame([(1, "new1"), (1, "new2")], "id INT, v STRING")
attempt("MERGE with duplicate source keys", lambda: DeltaTable.forPath(s, target).alias("t")
        .merge(dup_source.alias("s"), "t.id = s.id").whenMatchedUpdateAll().execute())
attempt("write join with duplicate names", lambda: a.join(b, "id").write.format("delta").save(f"{d}/dup"))

s.createDataFrame([(1,)], "id INT").write.format("parquet").saveAsTable("pq")
attempt("overwrite a parquet table read", lambda: s.table("pq").union(s.range(2, 3).selectExpr("CAST(id AS INT) id"))
        .write.format("parquet").mode("overwrite").saveAsTable("pq"))

src = f"{d}/src"
s.createDataFrame([(1, "x")], "id INT, v STRING").write.format("delta").save(src)
stream = s.readStream.format("delta").load(src)
attempt("aggregate to Delta in update mode", lambda: stream.groupBy("v").count().writeStream.format("delta")
        .outputMode("update").option("checkpointLocation", f"{d}/cp1").start(f"{d}/o1").awaitTermination(30))
attempt("stream-stream LEFT join, no watermark", lambda: stream.alias("l").join(
        s.readStream.format("delta").load(src).alias("r"), "id", "left").writeStream.format("delta")
        .option("checkpointLocation", f"{d}/cp2").trigger(availableNow=True).start(f"{d}/o2").awaitTermination(30))
