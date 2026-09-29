# PySpark / SQL / Delta / SDP patterns: a quick reference

Idioms I want at my fingertips in a live session. Each is either executed in this repo (link) or copied from working code in the studied repos. The goal is correct semantics, not memorised syntax: when unsure of syntax, I'd check the docs or ask the Assistant, then verify.

## Reading messy input

```python
schema = "order_id STRING, amount STRING, ts STRING, _corrupt_record STRING"   # all STRING at the boundary
raw = (spark.read.schema(schema).option("mode", "PERMISSIVE")
       .option("columnNameOfCorruptRecord", "_corrupt_record").json(path)
       .select("*", "_metadata.file_path"))                  # lineage: which file each row came from

typed = raw.select(
    F.upper(F.trim("order_id")).alias("order_id"),
    F.expr("try_cast(regexp_replace(amount, '[$,]', '') AS DECIMAL(18,2))").alias("amount"),
    F.coalesce(F.expr("try_to_timestamp(ts, 'yyyy-MM-dd HH:mm:ss')"),
               F.expr("try_to_timestamp(ts, 'MM/dd/yyyy HH:mm')")).alias("ts"))
```
On Databricks, Auto Loader (`cloudFiles`) + `schemaEvolutionMode` + `_rescued_data` handles incremental discovery and drift. ([Ex01](../exercises/ex01_messy_orders_medallion/pipeline.py))

## Data quality: null-safe rules with reasons

```python
RULES = {"amount_positive": "amount > 0", "customer_present": "customer_id IS NOT NULL"}
checks = [F.when(~F.coalesce(F.expr(r), F.lit(False)), F.lit(name)) for name, r in RULES.items()]
flagged = df.withColumn("dq_failures", F.filter(F.array(*checks), lambda x: x.isNotNull()))
valid, quarantine = flagged.where(F.size("dq_failures") == 0), flagged.where(F.size("dq_failures") > 0)
```

## Latest version per key (deterministic)

```python
w = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc(), F.col("_ingested_at").desc(),
                                           F.col("_source_file").desc())       # full tie-break
latest = df.withColumn("rn", F.row_number().over(w)).where("rn = 1").drop("rn")
# NOT: df.orderBy(...).dropDuplicates(["order_id"])   <- arbitrary survivor after the shuffle
```

## Sequenced upsert (MERGE)

```python
(DeltaTable.forName(spark, "silver.orders").alias("t")
   .merge(latest.alias("s"), "t.order_id = s.order_id")
   .whenMatchedUpdateAll(condition="s.updated_at > t.updated_at")   # an older event never overwrites
   .whenNotMatchedInsertAll()
   .execute())
# Source must be unique on the merge key, or: DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE
```

## Spark Declarative Pipelines (as used in lakeflow_framework's engine)

```python
from pyspark import pipelines as dp

@dp.table(name="bronze_orders")                         # or @dp.materialized_view(..., refresh_policy=...)
@dp.expect_all_or_drop({"valid_id": "order_id IS NOT NULL"})
def bronze_orders():
    return spark.readStream.format("cloudFiles").option("cloudFiles.format", "json").load(path)

dp.create_streaming_table(name="silver_customers", cluster_by_auto=True)
dp.create_auto_cdc_flow(
    target="silver_customers", source="v_customers_cdc",
    keys=["customer_id"], sequence_by="updated_at",          # out-of-order events resolved per key
    apply_as_deletes=F.expr("op = 'D'"),
    except_column_list=["op", "updated_at"],
    stored_as_scd_type=2)                                    # __START_AT / __END_AT maintained for you

@dp.append_flow(name="f_backfill", target="silver_orders", once=True)   # one-time backfill flow
def backfill():
    return spark.read.table("legacy.orders")
```
Checkpoints are keyed by **flow name**: renaming a flow reprocesses. Expectation counts land in the pipeline **event log**.

## Joins

```python
fact.join(F.broadcast(dim), "customer_id", "left")        # small side broadcast; LEFT keeps orphans
assert fact.count() == fact.join(dim, "customer_id", "left").count(), "fan-out: dim not unique"
fact.join(dim, fact.k.eqNullSafe(dim.k))                  # NULL matches NULL, only if intended
fact.join(excluded, "id", "left_anti")                    # anti-join; never NOT IN on a nullable column
```

Point-in-time (SCD2 / price lists), half-open interval:
```sql
ON o.customer_id = d.customer_id
AND o.order_ts >= d.valid_from AND (d.valid_to IS NULL OR o.order_ts < d.valid_to)
```

## Window idioms

```sql
ROW_NUMBER() OVER (PARTITION BY region ORDER BY sales DESC, rep)        -- top-N, exactly N
DENSE_RANK() OVER (PARTITION BY region ORDER BY sales DESC)             -- top-N with ties
SUM(x) OVER (PARTITION BY k ORDER BY ts ROWS UNBOUNDED PRECEDING)       -- running total
LAG(ts) OVER (PARTITION BY user_id ORDER BY ts)                         -- sessionization gap
date_sub(d, CAST(ROW_NUMBER() OVER (PARTITION BY id ORDER BY d) AS INT)) -- gaps-and-islands key
```
All executed in [`playbook/patterns_demo.py`](../playbook/patterns_demo.py).

## NULL-safe expressions

```sql
NOT (status <=> 'cancelled')          -- keeps NULL status (status != 'cancelled' drops it)
coalesce(sum(x), 0)                   -- sum over no rows is NULL
count(*)  vs  count(col)              -- count(col) skips NULLs
CASE WHEN <complex OR chain> THEN 1 ELSE 0 END = 0   -- NULL goes to ELSE
try_cast(x AS INT), try_divide(a, b), try_to_timestamp(s, fmt)   -- NULL instead of an ANSI error
```
Full verified table: [`playbook/07-null-semantics.md`](../playbook/07-null-semantics.md).

## Dates and time zones

```python
spark.conf.set("spark.sql.session.timeZone", "UTC")    # pin it in the job, not per notebook
F.to_date(F.from_utc_timestamp("ts", "America/Los_Angeles"))   # only when the business day is LA time
```
`current_date() - make_dt_interval(7)` spans **8** calendar dates; `current_date()` depends on the session time zone.

## Delta operations

```sql
DESCRIBE HISTORY t;                                   -- versions, operations, who
SELECT * FROM t VERSION AS OF 12;                     -- time travel (pin a snapshot you reasoned about)
SELECT * FROM table_changes('t', 12) WHERE _change_type IN ('insert', 'update_postimage');   -- CDF
OPTIMIZE t;  VACUUM t;                                -- or let predictive optimization do it
ALTER TABLE t CLUSTER BY (customer_id);               -- liquid clustering (or CLUSTER BY AUTO)
ALTER TABLE t SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
```
```python
spark.read.format("delta").option("versionAsOf", v).load(path)   # a DataFrame is a recipe, not a snapshot
```

## Streaming

```python
(spark.readStream.table("bronze.events")
   .withWatermark("event_ts", "10 minutes")                 # bounds state; defines "late"
   .dropDuplicatesWithinWatermark(["event_id"])
   .groupBy(F.window("event_ts", "10 minutes")).agg(F.sum("amount"))
   .writeStream.option("checkpointLocation", cp)
   .trigger(availableNow=True)                              # incremental batch
   .toTable("silver.revenue_10m"))                          # append mode waits for the watermark
```
Upserting aggregates: `foreachBatch` + MERGE (Delta rejects `update` mode). Stream-static joins read the static side as of each micro-batch.

## Reading the plan

```python
df.explain("formatted")        # look for: Exchange, BroadcastHashJoin vs SortMergeJoin,
                               # PushedFilters / PartitionFilters, BatchEvalPython / ArrowEvalPython
```

## Testing

```python
from pyspark.testing import assertDataFrameEqual
assertDataFrameEqual(actual, expected)       # order-insensitive by default (checked on PySpark 4.0.1)
# Test the invariant (one row per key; totals preserved), and make sure the test FAILS without the fix.
```
Environment gotcha I hit: `pyspark.testing` imports pandas-on-Spark, which fails on **pandas 3** with PySpark 4.0.1 (`ImportError: cannot import name '_builtin_table'`). pandas 2.3.3 works. On Databricks the runtime pins compatible versions; locally, pin `pandas<3`.
