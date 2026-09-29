"""Ask the Python workers which interpreter they are (case-studies/05). Run it with a venv's python
WITHOUT activating the venv, first as-is, then with PYSPARK_PYTHON pinned:
    /path/to/venv/bin/python which_python_workers.py
    PIN=1 /path/to/venv/bin/python which_python_workers.py
"""
import os
import sys

from pyspark.sql import SparkSession, functions as F

if os.environ.get("PIN"):
    os.environ["PYSPARK_PYTHON"] = sys.executable      # what exercises/common/spark_session.py does
else:
    os.environ.pop("PYSPARK_PYTHON", None)             # PySpark's default: whatever `python3` is on PATH

spark = (SparkSession.builder.master("local[1]").appName("which-python")
         .config("spark.ui.enabled", "false").config("spark.ui.showConsoleProgress", "false").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")


@F.udf("string")
def worker_report(_):
    import importlib.util
    import sys as worker_sys
    return f"{worker_sys.executable} | pyarrow importable: {importlib.util.find_spec('pyarrow') is not None}"


print("driver :", sys.executable)
print("workers:", spark.range(1).select(worker_report("id")).first()[0])
spark.stop()
