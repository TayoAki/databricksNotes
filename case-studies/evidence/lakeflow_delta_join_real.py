"""Run lakeflow_framework's REAL SourceDeltaJoin.read_source on open-source Spark + Delta (case-studies/07).

Only the Databricks-only modules (pyspark.pipelines, pyspark.dbutils) are stubbed, so the package imports.
Everything under test is the framework's own code at commit 0e8d0ca.

    pip install -r exercises/requirements.txt jsonschema pyyaml
    LAKEFLOW_FRAMEWORK_SRC=/path/to/lakeflow_framework/src python lakeflow_delta_join_real.py

Observed (Spark 4.0.1, delta-spark 4.0.0):
  A. left join 'c.CUSTOMER_ID = ca.CUSTOMER_ID' -> 3 rows: ['Ann', 'Bo', 'Cy']
     left join 'ca.CUSTOMER_ID = c.CUSTOMER_ID' -> 1 rows: ['Ann']
  A2. stream-static: first text -> ran, 3 rows; reversed text -> AnalysisException: LeftOuter join with a
      streaming DataFrame/Dataset on the right and a static DataFrame/Dataset on the left is not supported
  B. rule on 2nd table's column -> AnalysisException: [UNRESOLVED_COLUMN.WITH_SUGGESTION] ... `CITY` ...
     rule on a column both have -> OK
  C. view's ReadConfig.mode was 'stream'; after read_source it is: 'batch'
"""
import logging
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "exercises"))
src = os.environ.get("LAKEFLOW_FRAMEWORK_SRC")
if not src or not Path(src, "lakeflow_framework").is_dir():
    sys.exit("Set LAKEFLOW_FRAMEWORK_SRC to the src/ directory of a lakeflow_framework checkout.")
sys.path.insert(0, src)
sys.dont_write_bytecode = True                                    # leave the checkout untouched (no __pycache__)

for name in ["pyspark.pipelines", "pyspark.dbutils"]:            # Databricks-only modules
    sys.modules[name] = types.ModuleType(name)
sys.modules["pyspark.dbutils"].DBUtils = object
import pyspark  # noqa: E402

pyspark.pipelines = sys.modules["pyspark.pipelines"]

os.chdir(tempfile.mkdtemp())                                       # keep spark-warehouse out of the repo
from common.spark_session import get_spark  # noqa: E402

spark = get_spark("lakeflow-delta-join")

import lakeflow_framework.pipeline_config as pc  # noqa: E402
from lakeflow_framework.dataflow.features import Features  # noqa: E402
from lakeflow_framework.dataflow.sources.base import ReadConfig  # noqa: E402
from lakeflow_framework.dataflow.sources.delta_join import SourceDeltaJoin  # noqa: E402

pc._spark = spark
pc._logger = logging.getLogger("lff")
pc._substitution_manager = MagicMock()
pc._pipeline_details = MagicMock()
pc._operational_metadata_schema = None
pc._mandatory_table_properties = {}

spark.createDataFrame([(1, "Ann"), (2, "Bo"), (3, "Cy")], "CUSTOMER_ID INT, NAME STRING") \
     .write.format("delta").mode("overwrite").saveAsTable("default.customers")
spark.createDataFrame([(1, "Leeds")], "CUSTOMER_ID INT, CITY STRING") \
     .write.format("delta").mode("overwrite").saveAsTable("default.addresses")


def join_source(cond, c_mode="static"):
    return SourceDeltaJoin(
        sources=[{"database": "default", "table": "customers", "alias": "c", "joinMode": c_mode, "cdfEnabled": False},
                 {"database": "default", "table": "addresses", "alias": "ca", "joinMode": "static", "cdfEnabled": False}],
        joins=[{"joinType": "left", "condition": cond}],
        selectExp=["c.CUSTOMER_ID", "c.NAME", "ca.CITY"])


features = Features(operationalMetadataEnabled=False)

print("=== A. The text order of a symmetric equality decides which side a LEFT join keeps")
for cond in ["c.CUSTOMER_ID = ca.CUSTOMER_ID", "ca.CUSTOMER_ID = c.CUSTOMER_ID"]:
    df = join_source(cond).read_source(ReadConfig(features=features, mode="batch"))
    print(f"  left join {cond!r:36} -> {df.count()} rows: {sorted(r.NAME for r in df.collect() if r.NAME)}")

print("=== A2. Same spec, customers read as a stream (stream-static join)")
out = tempfile.mkdtemp()
for i, cond in enumerate(["c.CUSTOMER_ID = ca.CUSTOMER_ID", "ca.CUSTOMER_ID = c.CUSTOMER_ID"]):
    df = join_source(cond, c_mode="stream").read_source(ReadConfig(features=features, mode="stream"))
    try:
        (df.writeStream.format("delta").option("checkpointLocation", f"{out}/cp{i}")
           .trigger(availableNow=True).start(f"{out}/sink{i}").awaitTermination())
        print(f"  left join {cond!r:36} -> ran, {spark.read.format('delta').load(f'{out}/sink{i}').count()} rows")
    except Exception as e:  # noqa: BLE001
        print(f"  left join {cond!r:36} -> {type(e).__name__}: {str(e).splitlines()[0][:130]}")

print("=== B. Flag-mode quarantine rules are evaluated on each joined table alone, before the join")
for label, rules in [("rule on 2nd table's column", "NOT((CITY IS NOT NULL))"),
                     ("rule on a column both have", "NOT((CUSTOMER_ID IS NOT NULL))")]:
    rc = ReadConfig(features=features, mode="batch", quarantine_rules=rules)
    try:
        df = join_source("c.CUSTOMER_ID = ca.CUSTOMER_ID").read_source(rc)
        print(f"  {label} -> OK, columns {df.columns}, rows {df.count()}")
    except Exception as e:  # noqa: BLE001
        print(f"  {label} -> {type(e).__name__}: {str(e).splitlines()[0][:200]}")

print("=== C. The caller's ReadConfig is mutated by the join source")
rc = ReadConfig(features=features, mode="stream")
join_source("c.CUSTOMER_ID = ca.CUSTOMER_ID", c_mode="stream").read_source(rc)
print("  view's ReadConfig.mode was 'stream'; after read_source it is:", repr(rc.mode))
