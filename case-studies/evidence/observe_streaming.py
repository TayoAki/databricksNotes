import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "exercises"))
import tempfile
from common.spark_session import get_spark
from ex04_streaming_semantics import streaming_lab as L
spark = get_spark("observe-streaming")
d = tempfile.mkdtemp()
read = lambda p: spark.read.format("delta").load(p)

print("=== A. checkpoint exactly-once")
src, sink, cp = f"{d}/a_src", f"{d}/a_sink", f"{d}/a_cp"
L.append_events(spark, src, [("e1","C1",L.ts("2026-09-01 10:00"),10), ("e2","C1",L.ts("2026-09-01 10:01"),20)])
print(" run1", L.run_available_now(L.passthrough(spark, src), sink, cp), "sink rows", read(sink).count())
print(" run2 (no new data)", L.run_available_now(L.passthrough(spark, src), sink, cp), "sink rows", read(sink).count())
L.append_events(spark, src, [("e3","C2",L.ts("2026-09-01 10:02"),5)])
print(" run3 (+1 row)", L.run_available_now(L.passthrough(spark, src), sink, cp), "sink rows", read(sink).count())

print("=== B. watermark + append mode")
src, sink, cp = f"{d}/b_src", f"{d}/b_sink", f"{d}/b_cp"
L.append_events(spark, src, [("e1","C1",L.ts("2026-09-01 10:00"),10), ("e2","C1",L.ts("2026-09-01 10:05"),20)])
print(" run1 (events in [10:00,10:10))", L.run_available_now(L.windowed_revenue(spark, src), sink, cp),
      "sink:", [tuple(r) for r in read(sink).collect()] if L.__name__ and __import__('delta').tables.DeltaTable.isDeltaTable(spark, sink) else "no table yet")
L.append_events(spark, src, [("e3","C1",L.ts("2026-09-01 10:30"),7)])
print(" run2 (event at 10:30 -> watermark 10:20)", L.run_available_now(L.windowed_revenue(spark, src), sink, cp),
      "sink:", [tuple(r) for r in read(sink).orderBy("window_start").collect()])
print(" run3 (no new data)", L.run_available_now(L.windowed_revenue(spark, src), sink, cp),
      "sink:", [tuple(r) for r in read(sink).orderBy("window_start").collect()])

print("=== C. constant-watermark trick (table_import.py)")
for mode in ["append", "update"]:
    src, sink, cp = f"{d}/c_src_{mode}", f"{d}/c_sink_{mode}", f"{d}/c_cp_{mode}"
    L.append_events(spark, src, [("e1","C1",L.ts("2026-01-01 00:00"),1), ("e2","C1",L.ts("2026-02-01 00:00"),2),
                                 ("e3","C2",L.ts("2026-01-15 00:00"),3)])
    try:
        prog = L.run_available_now(L.latest_per_key_constant_watermark(spark, src), sink, cp, mode=mode)
        rows = [tuple(r) for r in read(sink).orderBy("customer_id").collect()] if __import__('delta').tables.DeltaTable.isDeltaTable(spark, sink) else "no table"
        print(f" mode={mode}: {prog} sink={rows}")
    except Exception as e:
        print(f" mode={mode}: ERROR {type(e).__name__}: {str(e).splitlines()[0][:300]}")

print("=== D. stream-static join")
src, sink, cp, dim = f"{d}/d_src", f"{d}/d_sink", f"{d}/d_cp", f"{d}/d_dim"
spark.createDataFrame([("C1","SMB")], "customer_id STRING, segment STRING").write.format("delta").save(dim)
L.append_events(spark, src, [("e1","C1",L.ts("2026-09-01 10:00"),10)])
L.run_available_now(L.enrich_stream_with_static(spark, src, dim), sink, cp)
spark.createDataFrame([("C1","Enterprise")], "customer_id STRING, segment STRING").write.format("delta").mode("overwrite").save(dim)
L.append_events(spark, src, [("e2","C1",L.ts("2026-09-01 11:00"),10)])
L.run_available_now(L.enrich_stream_with_static(spark, src, dim), sink, cp)
print(" sink:", [tuple(r) for r in read(sink).orderBy("event_id").collect()])
