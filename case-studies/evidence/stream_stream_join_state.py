"""What a stream-stream join does with no watermark (case-studies/07). Run from anywhere.
lakeflow_framework's delta_join source joins streams with no withWatermark() anywhere in its code path."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "exercises"))
from common.spark_session import get_spark

spark = get_spark("stream-stream")
d = tempfile.mkdtemp()


def add(path, rows, col):
    spark.createDataFrame(rows, f"id INT, {col} STRING").write.format("delta").mode("append").save(path)


a, b = f"{d}/a", f"{d}/b"
add(a, [(1, "a1")], "va"); add(b, [(1, "b1")], "vb")
sa = spark.readStream.format("delta").load(a).alias("a")
sb = spark.readStream.format("delta").load(b).alias("b")

# 1. LEFT stream-stream join without watermark: rejected when the query starts (loud, good)
try:
    (sa.join(sb, "id", "left").writeStream.format("delta")
       .option("checkpointLocation", f"{d}/cp_left").trigger(availableNow=True).start(f"{d}/out_left")
       .awaitTermination())
    print("left join: started")
except Exception as e:
    print("left join without watermark ->", type(e).__name__, str(e).split("\n")[0][:160])

# 2. INNER stream-stream join without watermark: allowed; the state store only ever grows (quiet).
#    (Non-key columns are named va / vb: joining two tables that share a column name makes Delta reject the
#    write with DELTA_DUPLICATE_COLUMNS_FOUND, which I hit on the first attempt.)
for i in range(3):
    q = (sa.join(sb, "id", "inner").writeStream.format("delta")
           .option("checkpointLocation", f"{d}/cp_inner").trigger(availableNow=True).start(f"{d}/out_inner"))
    q.awaitTermination()
    ops = q.lastProgress["stateOperators"] if q.lastProgress else []
    print(f"inner join run {i + 1}: state rows =", ops[0]["numRowsTotal"] if ops else "n/a",
          "| output rows =", spark.read.format("delta").load(f"{d}/out_inner").count())
    add(a, [(10 + i, f"a{10 + i}")], "va"); add(b, [(20 + i, f"b{20 + i}")], "vb")   # keys that never match
