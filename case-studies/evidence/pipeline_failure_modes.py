"""Nine pipeline failure modes, each reproduced on tiny data next to its fix
(cheatsheets/pipeline-failure-modes.md). Run from anywhere once the exercises env is installed.
Spark 4 runs with ANSI mode on, so some traps are loud errors here that are silent NULLs with ANSI off."""
import json
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "exercises"))
from common.spark_session import get_spark
from delta.tables import DeltaTable
from pyspark.sql import Window, functions as F

s = get_spark("failure-modes")
TMP = tempfile.mkdtemp()


def attempt(fn):
    """Run fn and return 'ok', or the error class Spark or Delta raised."""
    try:
        fn()
        return "ok"
    except Exception as e:  # any Spark/Delta error: report its class instead of a stack trace
        m = re.search(r"\[([A-Z_][A-Z0-9_.]*)\] ?([^.(]*)", str(e))
        if not m:
            return type(e).__name__
        return m.group(2).strip() if m.group(1).startswith("_LEGACY") else m.group(1)


@contextmanager
def ansi_off():
    """What the same code does on a cluster or session with ANSI mode off."""
    s.conf.set("spark.sql.ansi.enabled", "false")
    try:
        yield
    finally:
        s.conf.set("spark.sql.ansi.enabled", "true")


def sql(expr):
    out = []
    err = attempt(lambda: out.append(s.sql(f"SELECT {expr}").first()[0]))
    return out[0] if out else err


def rows(df):
    return [tuple(r) for r in df.collect()]


def json_dir(records):
    path = tempfile.mkdtemp(dir=TMP)
    Path(path, "part.json").write_text("\n".join(json.dumps(r) for r in records))
    return path


def append(df, path, **opts):
    return attempt(lambda: df.write.format("delta").mode("append").options(**opts).save(path))


def schema_drift():
    t = f"{TMP}/orders"
    s.createDataFrame([(1, 10.0)], "order_id INT, amount DOUBLE").write.format("delta").save(t)
    added = s.createDataFrame([(2, 20.0, 1.0)], "order_id INT, amount DOUBLE, discount DOUBLE")
    renamed = s.createDataFrame([(4, 40.0)], "order_id INT, amt DOUBLE")
    print("  added column  :", append(added, t), "| with mergeSchema:", append(added, t, mergeSchema="true"))
    print("  dropped column:", append(s.createDataFrame([(3,)], "order_id INT"), t))
    print("  renamed column:", append(renamed, t), "| with mergeSchema:", append(renamed, t, mergeSchema="true"))
    table = s.read.format("delta").load(t).orderBy("order_id")
    print("  table now     :", table.columns, rows(table))
    fixed = s.read.schema("order_id INT, amount DOUBLE").json(json_dir([{"order_id": 1, "amount": 10.5},
                                                                         {"order_id": 2, "amt": 20.5}]))
    print("  fixed-schema read of a renamed key:", rows(fixed.orderBy("order_id")))

    # The fix: diff every batch against the contract before it reaches silver.
    def contract_diff(contract, df):
        got = {f.name: f.dataType.simpleString() for f in df.schema.fields}
        added, missing = sorted(set(got) - set(contract)), sorted(set(contract) - set(got))
        return {"added": added, "missing": missing,
                "possible_renames": [(m, a) for m in missing for a in added if got[a] == contract[m]]}
    print("  contract diff :", contract_diff({"order_id": "int", "amount": "double"}, renamed))


def silent_casts():
    for e in ["cast('12.5' AS INT)", "try_cast('12.5' AS INT)", "cast(' 12 ' AS INT)",
              "cast('12.345' AS DECIMAL(5,2))", "try_cast(123456.789 AS DECIMAL(5,2))", "0.1D + 0.2D",
              "to_timestamp('03/04/2026', 'MM/dd/yyyy')", "to_timestamp('03/04/2026', 'dd/MM/yyyy')",
              "try_to_timestamp('2026-02-30 10:00:00', 'yyyy-MM-dd HH:mm:ss')",
              "year(timestamp_seconds(1767225600000))", "timestamp_millis(1767225600000)"]:
        print(f"  {e:62} -> {sql(e)}")
    with ansi_off():
        print("  ANSI off: cast('12.5' AS INT) ->", sql("cast('12.5' AS INT)"),
              "| cast('N/A' AS INT) ->", sql("cast('N/A' AS INT)"))
    inferred = s.read.json(json_dir([{"amount": 10.5}, {"amount": "N/A"}]))
    print("  inferred schema after one bad record:", inferred.schema.simpleString())

    # The fix: parse with try_*, and quarantine what was present before parsing and NULL after.
    raw = s.createDataFrame([("12",), (" 12 ",), ("12.5",), ("N/A",), ("",), (None,)], "v STRING")
    parsed = raw.withColumn("v_int", F.expr("try_cast(v AS INT)"))
    print("  to quarantine:", [r.v for r in parsed.where("v IS NOT NULL AND v_int IS NULL").collect()])
    money = s.createDataFrame([("12.34",), ("12.345",)], "v STRING").withColumn(
        "would_round", F.expr("try_cast(v AS DECIMAL(12,2)) <> try_cast(v AS DECIMAL(38,10))"))
    print("  amounts that would round:", [r.v for r in money.where("would_round").collect()])


def nullability():
    batch = s.read.schema("customer_id STRING, country STRING, email STRING").json(json_dir(
        [{"customer_id": "C1", "country": "US"}, {"customer_id": "C2"}, {"customer_id": "C3", "country": None}]))
    print("  missing key vs explicit null:", rows(batch.orderBy("customer_id")))
    c = f"{TMP}/customers"
    s.sql(f"CREATE TABLE delta.`{c}` (customer_id STRING NOT NULL, country STRING, email STRING) USING delta")
    s.sql(f"ALTER TABLE delta.`{c}` ADD CONSTRAINT country_present CHECK (country IS NOT NULL)")
    print("  write the batch as is      :", append(batch, c))
    print("  write a NULL customer_id   :", append(s.createDataFrame([(None, "US", None)], batch.schema), c))
    print("  write without customer_id  :", append(batch.drop("customer_id"), c))

    # The fix: quarantine rows that miss a required field (with the reason), write the rest,
    # and record null rates per batch so a jump in an optional column is visible.
    missing = F.filter(F.array(*[F.when(F.col(k).isNull(), F.lit(k)) for k in ["customer_id", "country"]]),
                       lambda x: x.isNotNull())
    flagged = batch.withColumn("missing", missing)
    print("  write valid rows           :", append(flagged.where(F.size("missing") == 0).drop("missing"), c),
          "| quarantined:", [(r.customer_id, r.missing) for r in flagged.where(F.size("missing") > 0).collect()])
    rates = batch.select([F.round(F.avg(F.col(k).isNull().cast("int")), 2).alias(k) for k in batch.columns])
    print("  null rates                 :", rates.first().asDict())


def incremental_watermark():
    def at(rows_):
        return s.createDataFrame([(i, datetime.fromisoformat(f"2026-09-01 {t}")) for i, t in rows_],
                                 "id INT, updated_at TIMESTAMP")
    run1 = at([(1, "10:00"), (2, "10:05")])
    watermark = run1.agg(F.max("updated_at")).first()[0]
    # after run 1: id 3 commits with the same timestamp as the watermark, id 4 is a long
    # transaction that commits late with an older timestamp, id 5 is simply new
    source = run1.unionByName(at([(3, "10:05"), (4, "10:03"), (5, "10:10")]))
    print("  watermark after run 1:", watermark)
    print("  next run with '>'    :", sorted(r.id for r in source.where(F.col("updated_at") > watermark).collect()))
    overlap = source.where(F.col("updated_at") >= F.lit(watermark) - F.expr("INTERVAL 10 MINUTES"))
    print("  next run with '>= watermark - 10 min':", sorted(r.id for r in overlap.collect()))

    # The fix: re-read an overlap and make the write idempotent, so reading a row twice is harmless.
    t = f"{TMP}/incremental"
    run1.write.format("delta").save(t)
    for _ in range(2):
        (DeltaTable.forPath(s, t).alias("t").merge(overlap.alias("s"), "t.id = s.id")
         .whenMatchedUpdateAll(condition="s.updated_at > t.updated_at").whenNotMatchedInsertAll().execute())
    print("  after the overlapping run, twice:", s.read.format("delta").load(t).count(), "rows, one per id")


def late_data():
    def orders(rows_):
        return s.createDataFrame(rows_, "order_id STRING, event_date STRING, amount DOUBLE").withColumn(
            "event_date", F.to_date("event_date"))
    daily = f"{TMP}/daily_revenue"
    seen = orders([("o1", "2026-09-01", 10.0), ("o2", "2026-09-02", 20.0)])
    seen.groupBy("event_date").agg(F.sum("amount").alias("revenue")).write.format("delta").save(daily)
    new = orders([("o3", "2026-09-01", 5.0), ("o4", "2026-09-03", 7.0)])   # o3 arrives two days late

    # The fix: recompute every event date the new rows touch, not just "yesterday".
    touched = sorted(r.event_date for r in new.select("event_date").distinct().collect())
    cond = "event_date IN (" + ", ".join(f"DATE'{d}'" for d in touched) + ")"
    (seen.unionByName(new).where(cond).groupBy("event_date").agg(F.sum("amount").alias("revenue"))
     .write.format("delta").mode("overwrite").option("replaceWhere", cond).save(daily))
    print("  recomputed", [str(d) for d in touched], "->",
          [(str(r.event_date), r.revenue) for r in s.read.format("delta").load(daily).orderBy("event_date").collect()])

    # Streaming: an event behind the watermark is dropped; the only trace is a metric.
    src, sink, cp = f"{TMP}/events", f"{TMP}/revenue_10m", f"{TMP}/cp"

    def add(rows_):
        (s.createDataFrame([(e, datetime.fromisoformat(t), a) for e, t, a in rows_],
                           "event_id STRING, event_ts TIMESTAMP, amount DOUBLE")
         .write.format("delta").mode("append").save(src))

    def run():
        q = (s.readStream.format("delta").load(src).withWatermark("event_ts", "10 minutes")
             .groupBy(F.window("event_ts", "10 minutes")).agg(F.sum("amount").alias("amount"))
             .writeStream.format("delta").outputMode("append").option("checkpointLocation", cp)
             .trigger(availableNow=True).start(sink))
        q.awaitTermination()
        return sum(p["stateOperators"][0].get("numRowsDroppedByWatermark", 0)
                   for p in q.recentProgress if p["stateOperators"])

    add([("e1", "2026-09-01 10:00:00", 10.0), ("e2", "2026-09-01 10:30:00", 5.0)])
    first = run()
    add([("e3", "2026-09-01 10:05:00", 99.0)])   # 25 minutes behind the newest event
    second = run()
    print("  rows dropped by the watermark per run:", [first, second], "| sink:",
          [(str(r.window.start), r.amount) for r in s.read.format("delta").load(sink).collect()])


def time_zones():
    # DST days from the tz database: compare each day's noon offset with the next day's.
    for tz in ["America/New_York", "Europe/London", "Europe/Paris"]:
        noons = [datetime(2026, 1, 1, 12, tzinfo=ZoneInfo(tz)) + timedelta(days=i) for i in range(365)]
        print(f"  DST changes in 2026, {tz}:", [str(b.date()) for a, b in zip(noons, noons[1:])
                                                 if a.utcoffset() != b.utcoffset()])
    ny = "'America/New_York'"
    for e in [f"(unix_timestamp(to_utc_timestamp('2026-03-09', {ny})) - unix_timestamp(to_utc_timestamp('2026-03-08', {ny}))) / 3600",
              f"(unix_timestamp(to_utc_timestamp('2026-11-02', {ny})) - unix_timestamp(to_utc_timestamp('2026-11-01', {ny}))) / 3600",
              f"from_utc_timestamp(to_utc_timestamp('2026-03-08', {ny}) + INTERVAL 24 HOURS, {ny})",
              f"to_utc_timestamp('2026-03-08 02:30:00', {ny})", f"to_utc_timestamp('2026-11-01 01:30:00', {ny})",
              "to_date(timestamp'2026-03-10 03:30:00')", f"to_date(from_utc_timestamp(timestamp'2026-03-10 03:30:00', {ny}))",
              f"from_utc_timestamp(timestamp'2026-07-01 04:30:00', {ny})",
              "from_utc_timestamp(timestamp'2026-07-01 04:30:00', '-05:00')",
              "from_utc_timestamp(timestamp'2026-07-01 04:30:00', 'EST')"]:
        print(f"  {e.replace(ny, 'NY'):100} -> {sql(e)}")


def duplicates():
    batch = s.createDataFrame([("e1", 10.0, "2026-09-01 10:00:00", "day1.json"), ("e1", 10.0, "2026-09-01 10:00:00", "day1.json"),
                               ("e2", 5.0, "2026-09-01 10:01:00", "day1.json")],
                              "event_id STRING, amount DOUBLE, updated_at STRING, _source_file STRING")
    resent = batch.withColumn("_source_file", F.lit("day1_resent.json"))   # same events, new file

    def table():
        path = tempfile.mkdtemp(dir=TMP)
        batch.limit(0).write.format("delta").mode("overwrite").save(path)
        return path

    def total(path):
        return s.read.format("delta").load(path).agg(F.count("*"), F.sum("amount")).first()[:]

    t = table()
    for _ in range(2):
        append(batch, t)
    print("  plain append, run twice      (rows, total):", total(t), "| correct: (2, 15.0)")
    print("  distinct() over batch + resent file: rows", batch.unionByName(resent).distinct().count())

    # The fix: deterministic dedupe on the event key, then an insert-only MERGE.
    t = table()
    for b in (batch, batch, resent):
        w = Window.partitionBy("event_id").orderBy(F.col("updated_at").desc(), F.col("_source_file").desc())
        latest = b.withColumn("rn", F.row_number().over(w)).where("rn = 1").drop("rn")
        (DeltaTable.forPath(s, t).alias("t").merge(latest.alias("s"), "t.event_id = s.event_id")
         .whenNotMatchedInsertAll().execute())
    print("  dedupe + MERGE, run twice + resent file (rows, total):", total(t))

    # MERGE alone is not enough: the batch itself must be unique on the key.
    t = table()
    (DeltaTable.forPath(s, t).alias("t").merge(batch.alias("s"), "t.event_id = s.event_id")
     .whenNotMatchedInsertAll().execute())
    print("  insert-only MERGE of the undeduplicated batch (rows, total):", total(t))
    print("  updating MERGE of the undeduplicated batch:", attempt(
        lambda: DeltaTable.forPath(s, t).alias("t").merge(batch.alias("s"), "t.event_id = s.event_id")
        .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()))

    # foreachBatch-style retry: Delta skips a write whose (txnAppId, txnVersion) it has already committed.
    t = table()
    for _ in range(2):
        append(batch, t, txnAppId="payments-loader", txnVersion=7)
    print("  same txnAppId/txnVersion written twice (rows, total):", total(t), "(the in-batch duplicate stays)")


def join_fanout():
    orders = s.createDataFrame([("o1", "C1", 100.0), ("o2", "C2", 200.0), ("o3", "C3", 300.0)],
                               "order_id STRING, customer_id STRING, amount DOUBLE")
    customers = s.createDataFrame([("C1", "West"), ("C2", "East"), ("C2", "East"), ("C3", "North")],
                                  "customer_id STRING, region STRING")
    joined = orders.join(customers, "customer_id", "left")
    print("  rows", orders.count(), "->", joined.count(), "| revenue", orders.agg(F.sum("amount")).first()[0],
          "->", joined.agg(F.sum("amount")).first()[0])
    a = s.createDataFrame([("k", i) for i in range(3)], "k STRING, a INT")
    b = s.createDataFrame([("k", i) for i in range(4)], "k STRING, b INT")
    print("  many-to-many on one key, 3 x 4 rows ->", a.join(b, "k").count())

    # The fix: refuse a dimension that isn't unique on the key; assert the row count after.
    def safe_left_join(fact, dim, keys):
        dups = dim.groupBy(*keys).count().where("count > 1")
        if dups.limit(1).count():
            raise ValueError(f"dimension not unique on {keys}: {rows(dups.limit(5))}")
        out = fact.join(dim, keys, "left")
        assert out.count() == fact.count(), "row count changed"
        return out
    try:
        safe_left_join(orders, customers, ["customer_id"])
    except ValueError as e:
        print("  safe_left_join raises:", e)


def bad_keys():
    web = s.createDataFrame([("007", 1.0), ("N/A", 2.0)], "customer_id STRING, amount DOUBLE")
    crm = s.createDataFrame([(7, "Ada")], "customer_id BIGINT, name STRING")
    print("  STRING = BIGINT join, 'N/A' present:", attempt(lambda: web.join(crm, web.customer_id == crm.customer_id).collect()))
    print("  same join without 'N/A'           :", rows(web.where("customer_id != 'N/A'").join(crm, web.customer_id == crm.customer_id)))
    with ansi_off():
        print("  LEFT join with ANSI off           :", rows(web.join(crm, web.customer_id == crm.customer_id, "left")))

    # The fix: one canonical form, produced by one function, applied to both sides of every join.
    def normalize_customer_id(c):
        k = F.regexp_replace(F.upper(F.trim(c)), "[^A-Z0-9]", "")
        return F.when(k.rlike("^C?[0-9]{1,5}$"),
                      F.concat(F.lit("C"), F.lpad(F.regexp_extract(k, "([0-9]+)$", 1), 5, "0")))
    raw = s.createDataFrame([(" c001",), ("C001 ",), ("c-001",), ("C0001",), ("1",), ("00001",), ("X9",)], "k STRING")
    print("  normalize_customer_id:", [(r.k, r.n) for r in raw.withColumn("n", normalize_customer_id("k")).collect()])
    uuids = s.createDataFrame([("3F2504E0-4F89-11D3-9A0C-0305E82C3301",), ("{3f2504e0-4f89-11d3-9a0c-0305e82c3301}",),
                               ("3f2504e04f8911d39a0c0305e82c3301",)], "u STRING")
    hexed = F.regexp_replace(F.lower("u"), "[^0-9a-f]", "")
    canonical = F.when(hexed.rlike("^[0-9a-f]{32}$"),
                       F.regexp_replace(hexed, "^(.{8})(.{4})(.{4})(.{4})(.{12})$", "$1-$2-$3-$4-$5"))
    print("  canonical UUIDs      :", sorted({r.c for r in uuids.withColumn("c", canonical).collect()}))


for n, fn in enumerate([schema_drift, silent_casts, nullability, incremental_watermark, late_data,
                        time_zones, duplicates, join_fanout, bad_keys], 1):
    print(f"{n}. {fn.__name__}")
    fn()

# Observed on Spark 4.0.1 + Delta 4.0.0 (ANSI on): quoted section by section in
# cheatsheets/pipeline-failure-modes.md.
