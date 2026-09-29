"""technical-services-solutions pbi-aibi-converter: the "fix" for an unresolved column in LLM-written SQL
(converter.py:2971-2990, _best_column_match, copied verbatim). A misspelled or hallucinated column is silently
replaced by a DIFFERENT real column when >60% of characters match position by position (case-studies/03)."""


def _best_column_match(bad_col, available):
    lower_map = {c.lower(): c for c in available}
    if bad_col.lower() in lower_map:
        return lower_map[bad_col.lower()]
    stripped = bad_col.replace("_", "").lower()
    for col in available:
        if col.replace("_", "").lower() == stripped:
            return col
    best, best_score = None, 0
    bad_lower = bad_col.lower()
    for col in available:
        col_lower = col.lower()
        common = sum(1 for a, b in zip(bad_lower, col_lower) if a == b)
        score = common / max(len(bad_lower), len(col_lower))
        if score > best_score and score > 0.6:
            best_score = score
            best = col
    return best


table = ["order_id", "order_rate", "unit_count", "unit_price", "customer_id"]
for bad in ["unit_cost", "order_date", "OrderID", "customer_name"]:
    print(f"LLM wrote {bad!r:16} -> converter uses {_best_column_match(bad, table)!r}")
# Observed:
# LLM wrote 'unit_cost'      -> converter uses 'unit_count'   (cost silently becomes a quantity)
# LLM wrote 'order_date'     -> converter uses 'order_rate'   (a date silently becomes a rate)
# LLM wrote 'OrderID'        -> converter uses 'order_id'     (the one legitimate fix)
# LLM wrote 'customer_name'  -> converter uses 'customer_id'  (a name silently becomes an ID)
# (I predicted None for the last case before running it; 9 of 13 characters match, so 0.69 > 0.6.)
