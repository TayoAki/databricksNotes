"""Lazy evaluation meets a mutable Delta table (case-studies/04). Run from anywhere."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "exercises"))
from common.spark_session import get_spark
from delta.tables import DeltaTable

spark = get_spark("lazy")
p = tempfile.mkdtemp() + "/t"
spark.range(3).write.format("delta").save(p)                      # version 0: 3 rows
df_read = spark.read.format("delta").load(p)                      # defined BEFORE the write
df_totable = DeltaTable.forPath(spark, p).toDF()                  # defined BEFORE the write
derived = df_read.where("id >= 0")                                # lazy transformation on top
spark.range(3, 10).write.format("delta").mode("append").save(p)   # version 1: 10 rows
print("spark.read.load defined before write ->", df_read.count())
print("DeltaTable.toDF defined before write ->", df_totable.count())
print("derived df defined before write     ->", derived.count())
print("fresh read after write               ->", spark.read.format("delta").load(p).count())
# Remedy: pin the version you mean. versionAsOf makes the read immune to later commits.
pinned = spark.read.format("delta").option("versionAsOf", 0).load(p)
print("pinned versionAsOf=0 read            ->", pinned.count())

# Non-remedy: cache() is not a snapshot. Cache and materialise it, append, count again.
p2 = tempfile.mkdtemp() + "/t2"
spark.range(3).write.format("delta").save(p2)
cached = spark.read.format("delta").load(p2).cache()
print("cached df, counted before append     ->", cached.count())
spark.range(3, 10).write.format("delta").mode("append").save(p2)
print("same cached df, counted after append ->", cached.count())
