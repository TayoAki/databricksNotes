"""A local SparkSession with Delta Lake, so the exercises run off-platform.

On Databricks you never write this: `spark` is pre-created, Delta is the default
table format, and Unity Catalog gives you three-level names (catalog.schema.table).
Locally we reproduce the pieces that matter for reasoning about execution:
Delta transactions, MERGE, shuffles, AQE, and Structured Streaming.
"""
from __future__ import annotations

import os
import sys

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession


def get_spark(app_name: str = "databricks-notes", shuffle_partitions: int = 4) -> SparkSession:
    # Python workers must run the SAME interpreter as the driver. Otherwise they start
    # whatever `python3` is on PATH, and UDFs fail with ModuleNotFoundError only when they
    # actually execute. The in-process SparkContext reads ONLY this env var
    # (pyspark/core/context.py: pythonExec = os.environ.get("PYSPARK_PYTHON", "python3")).
    # The `spark.pyspark.python` conf is honoured by spark-submit, not here; I learned that
    # the hard way, see case-studies/05. The Databricks version of this bug is
    # `!pip install` (driver only) instead of `%pip install` (driver + executors).
    os.environ["PYSPARK_PYTHON"] = sys.executable
    builder = (
        SparkSession.builder.master("local[2]")
        .appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # Default is 200: far too many for laptop-sized data (every shuffle would create
        # 200 tiny tasks). On Databricks, AQE coalesces these automatically.
        .config("spark.sql.shuffle.partitions", str(shuffle_partitions))
        # Pin the session time zone. Date bucketing silently depends on it (see ex05).
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .config("spark.ui.showConsoleProgress", "false")
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark
