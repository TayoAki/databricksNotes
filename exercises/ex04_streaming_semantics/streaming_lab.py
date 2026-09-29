"""Exercise 04: Structured Streaming semantics that decide whether numbers are right.

Experiments (all use Delta source -> Delta sink with trigger(availableNow=True), the way
most Databricks "incremental batch" jobs and SDP streaming tables consume data):

  A. Checkpoints = exactly-once bookkeeping. Re-running reprocesses nothing; new data only.
  B. Watermarks + append mode: a window's result is written only after the watermark
     passes the window end, so results can lag by a run.
  C. The constant-event-time watermark trick used by lakeflow_framework's table_import.py:
     does a windowed aggregation over a *constant* timestamp ever emit in append mode?
  D. Stream-static joins read the static side's CURRENT state each micro-batch. Facts that
     are already written are NOT re-joined when the dimension changes later.
"""
from __future__ import annotations

from datetime import datetime

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

EVENT_SCHEMA = "event_id STRING, customer_id STRING, event_ts TIMESTAMP, amount INT"


def append_events(spark: SparkSession, path: str, rows: list[tuple]) -> None:
    spark.createDataFrame(rows, EVENT_SCHEMA).write.format("delta").mode("append").save(path)


def run_available_now(df: DataFrame, sink: str, checkpoint: str, mode: str = "append") -> dict:
    """Process everything available now, then stop. Returns simple progress numbers."""
    q = (df.writeStream.format("delta").outputMode(mode)
         .option("checkpointLocation", checkpoint).trigger(availableNow=True).start(sink))
    q.awaitTermination()
    progress = q.recentProgress
    return {"batches": len(progress),
            "input_rows": sum(p["numInputRows"] for p in progress)}


# A ---------------------------------------------------------------------------------------------
def passthrough(spark: SparkSession, source: str) -> DataFrame:
    return spark.readStream.format("delta").load(source)


# B ---------------------------------------------------------------------------------------------
def windowed_revenue(spark: SparkSession, source: str, watermark: str = "10 minutes") -> DataFrame:
    return (spark.readStream.format("delta").load(source)
            .withWatermark("event_ts", watermark)
            .groupBy(F.window("event_ts", "10 minutes"))
            .agg(F.sum("amount").alias("revenue"), F.count("*").alias("events"))
            .select(F.col("window.start").alias("window_start"), "revenue", "events"))


# C ---------------------------------------------------------------------------------------------
def latest_per_key_constant_watermark(spark: SparkSession, source: str) -> DataFrame:
    """Mirror of lakeflow_framework table_import.py (the closed-rows branch):
    a constant event-time column only exists to satisfy 'streaming aggregation needs a watermark'."""
    return (spark.readStream.format("delta").load(source)
            .withColumn("WATERMARK_COLUMN", F.lit("2000-01-01").cast("timestamp"))
            .withWatermark("WATERMARK_COLUMN", "10 minutes")
            .groupBy("customer_id", F.window("WATERMARK_COLUMN", "10 minutes"))
            .agg(F.max_by(F.struct("*"), "event_ts").alias("max_row"))
            .select("max_row.customer_id", "max_row.event_ts", "max_row.amount"))


# D ---------------------------------------------------------------------------------------------
def enrich_stream_with_static(spark: SparkSession, source: str, dim_path: str) -> DataFrame:
    dim = spark.read.format("delta").load(dim_path)       # "static" = re-read per micro-batch
    return (spark.readStream.format("delta").load(source)
            .join(dim, "customer_id", "left")
            .select("event_id", "customer_id", "segment"))


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s)
