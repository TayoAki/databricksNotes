"""Reproduces lakeflow_framework sources/delta_join.py:40-50 alias extraction (pure Python)."""
import re

PATTERN = r'(\b\w+)\.'   # verbatim from DeltaJoin.get_table_aliases


def aliases(cond: str) -> list[str]:
    out = []
    for m in re.findall(PATTERN, cond):
        if m not in out:
            out.append(m)
    return out


for cond in ["a.id = b.id",
             "b.id = a.id",                                  # same join, reversed text -> reversed LEFT side
             "a.id = b.id AND a.amount > 1.5",               # decimal literal -> phantom alias '1'
             "a.country = 'U.S.' AND a.id = b.id",           # dotted string literal -> phantom 'U', 'S'
             "a.id = b.id AND b.ts >= a.ts - INTERVAL 1 DAY",
             "a.payload.id = b.id"]:                         # struct field access -> phantom 'payload'
    print(f"{cond!r:50} -> {aliases(cond)}")
# Observed:
# 'a.id = b.id'                          -> ['a', 'b']
# 'b.id = a.id'                          -> ['b', 'a']
# 'a.id = b.id AND a.amount > 1.5'       -> ['a', 'b', '1']
# "a.country = 'U.S.' AND a.id = b.id"   -> ['a', 'U', 'S', 'b']
# 'a.id = b.id AND b.ts >= a.ts - ...'   -> ['a', 'b']
# 'a.payload.id = b.id'                  -> ['a', 'payload', 'b']
# Phantom aliases make _get_df raise ValueError("Missing DataFrames for aliases: [...]") - loud, but baffling.
