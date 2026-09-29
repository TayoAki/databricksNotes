"""lakeflow_framework sources/delta_join.py:87-107 join construction, reproduced verbatim on static DataFrames.
Question: does the TEXT ORDER of a symmetric equality change the result of a LEFT join? (case-studies/07)"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "exercises"))
from common.spark_session import get_spark
from pyspark.sql import functions as F


def get_table_aliases(condition):                      # verbatim logic from DeltaJoin.get_table_aliases
    aliases = []
    for match in re.findall(r'(\b\w+)\.', condition):
        if match not in aliases:
            aliases.append(match)
    return aliases


def build(dfs_to_join, joins):                         # verbatim logic from SourceDeltaJoin._get_df
    final_df, used = None, set()
    for join in joins:
        aliases = get_table_aliases(join["condition"])
        if final_df is None:
            df1, df2 = dfs_to_join[aliases[0]], dfs_to_join[aliases[1]]
            final_df = df1.join(df2, on=F.expr(join["condition"]), how=join["joinType"])
            used.update(aliases)
        else:
            for alias in aliases:
                if alias not in used:
                    final_df = final_df.join(dfs_to_join[alias], on=F.expr(join["condition"]), how=join["joinType"])
                    used.add(alias)
    return final_df


spark = get_spark("delta-join-direction")
customers = spark.createDataFrame([(1, "Ann"), (2, "Bo"), (3, "Cy")], "CUSTOMER_ID INT, NAME STRING").alias("c")
addresses = spark.createDataFrame([(1, "Leeds")], "CUSTOMER_ID INT, CITY STRING").alias("ca")
dfs = {"c": customers, "ca": addresses}
for cond in ["c.CUSTOMER_ID = ca.CUSTOMER_ID", "ca.CUSTOMER_ID = c.CUSTOMER_ID"]:
    out = build(dfs, [{"joinType": "left", "condition": cond}])
    print(f"left join, condition {cond!r:36} -> {out.count()} rows, "
          f"customers kept = {sorted(r.NAME for r in out.select('c.NAME').collect() if r.NAME)}")
