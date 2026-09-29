"""Verify suspected behaviours found while reading lakeflow_framework source."""
from pyspark.sql import SparkSession, functions as F, types as T

spark = (SparkSession.builder.master("local[2]").appName("verify")
         .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "2")
         .getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

# ---- 1. append_view.py: column_prefix_exceptions extended with StructField objects -----------
op_meta = T.StructType([T.StructField("meta_load_ts", T.TimestampType()),
                        T.StructField("meta_pipeline_id", T.StringType())])
exceptions = ["__START_AT", "__END_AT"]          # additional_column_prefix_exceptions
exceptions.extend(op_meta.fields)                 # what the framework does (StructField objects)
df = spark.createDataFrame([(1, "x")], "id INT, meta_pipeline_id STRING")
prefix = "src_"
cols = [df[c].alias(prefix + c) if c not in exceptions else df[c] for c in df.columns]
print("1) prefixed columns ->", df.select(cols).columns,
      "| 'meta_pipeline_id' in exceptions?", "meta_pipeline_id" in exceptions)

# ---- 2. quarantine.py: NOT((r1) AND (r2)) with NULL inputs -------------------------------------
rules = {"valid_amount": "amount > 0", "valid_id": "id IS NOT NULL"}
quarantine_rules = f"NOT({ ' AND '.join(f'({r})' for r in rules.values()) })"   # verbatim construction
data = spark.createDataFrame([(1, 10.0), (2, -5.0), (3, None), (None, 7.0)], "id INT, amount DOUBLE")
flagged = data.withColumn("is_quarantined", F.expr(quarantine_rules))
print("2) quarantine predicate:", quarantine_rules)
flagged.show()
print("   rows routed to quarantine table (.where(flag)):",
      [r.id for r in flagged.where(F.col("is_quarantined")).collect()])

# ---- 3. Why the parentheses matter (the bug the comment says was fixed) ------------------------
rules_or = {"r1": "status = 'A' OR status = 'B'", "r2": "qty > 0"}
unsafe = "NOT(" + " AND ".join(rules_or.values()) + ")"
safe = f"NOT({ ' AND '.join(f'({r})' for r in rules_or.values()) })"
d3 = spark.createDataFrame([("A", 0), ("B", 5), ("C", 5)], "status STRING, qty INT")
d3.select("*", F.expr(unsafe).alias("unsafe_flag"), F.expr(safe).alias("safe_flag")).show()
spark.stop()
