# Case study 07: a join whose direction is decided by how you type the condition

**Repo:** `databricks-solutions/lakeflow_framework` @ `0e8d0ca`, `src/lakeflow_framework/dataflow/sources/delta_join.py`
**Status:** A, C and D are CONFIRMED by running the framework's **real** `SourceDeltaJoin.read_source` on open-source Spark 4.0.1 + Delta ([`evidence/lakeflow_delta_join_real.py`](evidence/lakeflow_delta_join_real.py)). Only the Databricks-only modules are stubbed. B is CONFIRMED by running the verbatim regex; the `raise` it triggers is read from code. E is CONFIRMED for Spark's behaviour ([`evidence/stream_stream_join_state.py`](evidence/stream_stream_join_state.py)), and the framework's lack of a watermark setting is confirmed by code read.
Supporting scripts that need no lakeflow checkout: [`evidence/alias_regex_check.py`](evidence/alias_regex_check.py) and [`evidence/delta_join_direction.py`](evidence/delta_join_direction.py).

## Why this is a good interview story

It is "read code you didn't write" at its most useful. The feature works in every sample and the unit tests pass. The bug only appears when you ask *what information does this code use to make its decision?* The answer here is "the order of the words in a string", which is not something a spec author knows they are choosing.

## The code

A `deltaJoin` view declares sources (each with an `alias`) and joins (each a `joinType` plus a SQL `condition`). Which tables to join, and in which order, is recovered from the condition text with a regex:

```python
def get_table_aliases(self) -> List[str]:
    pattern = r'(\b\w+)\.'  # Matches word characters before a dot
    matches = re.findall(pattern, self.condition)
    ...  # de-duplicate, keeping first-seen order

# SourceDeltaJoin._get_df
for source in self.get_sources():
    read_config.mode = "batch" if source.joinMode == "static" else source.joinMode
    df = source.read_source(read_config)          # full read pipeline, per source
    dfs_to_join[source.alias] = df.alias(source.alias)
...
if final_df is None:
    df1, df2 = (dfs_to_join[aliases[0]], dfs_to_join[aliases[1]])
    final_df = df1.join(df2, on=F.expr(join.condition), how=join.joinType)
```

## A. The first alias in the text becomes the preserved side of a LEFT join (silent)

The same spec, with the equality written both ways (customers C1–C3, one address):

```
left join 'c.CUSTOMER_ID = ca.CUSTOMER_ID'  -> 3 rows: ['Ann', 'Bo', 'Cy']
left join 'ca.CUSTOMER_ID = c.CUSTOMER_ID'  -> 1 rows: ['Ann']
```

`a = b` and `b = a` mean the same thing in SQL, but here they produce **different joins**. With static (batch) sources, two-thirds of the customers silently disappear. With customers read as a stream, the reversed text builds `static LEFT JOIN stream`:

```
left join 'c.CUSTOMER_ID = ca.CUSTOMER_ID'  -> ran, 3 rows
left join 'ca.CUSTOMER_ID = c.CUSTOMER_ID'  -> AnalysisException: LeftOuter join with a streaming DataFrame/Dataset
                                               on the right and a static DataFrame/Dataset on the left is not supported
```

That one is loud, but it fails only when the query *starts* (`read_source` itself succeeds), and the error talks about stream/static sides that the author never knowingly chose.

The `sources` list, whose order *is* a deliberate choice, is ignored for ordering.

## B. Phantom aliases from anything that looks like `word.` (loud, but misleading)

```
'a.id = b.id AND a.amount > 1.5'       -> ['a', 'b', '1']            decimal literal
"a.country = 'U.S.' AND a.id = b.id"   -> ['a', 'U', 'S', 'b']       dotted string literal
'a.payload.id = b.id'                  -> ['a', 'payload', 'b']      struct field access
```

Each phantom makes `_get_df` raise `ValueError("Missing DataFrames for aliases: ['1']")`. That is fail-closed (good), but the message sends the author looking for a table named `1`. The repo's unit tests for `get_table_aliases` cover only simple conditions, so none of these cases is exercised.

## C. Flag-mode quarantine rules are evaluated per table, before the join (loud, and blocks a real use case)

Each source goes through the **full** `BaseSource.read_source`: transforms, operational metadata *and the quarantine flag*. In `flag` quarantine mode, the flow's source view gets the combined rule predicate (`dataflow.py:484-490`). For a join view, that predicate is first evaluated against each table **alone**:

```
rule on 2nd table's column -> AnalysisException: [UNRESOLVED_COLUMN.WITH_SUGGESTION] ... `CITY` cannot be resolved.
                              Did you mean one of the following? [`NAME`, `CUSTOMER_ID`]
rule on a column both have -> OK
```

So a data-quality rule on a joined column, such as "every customer must have a city", cannot be used in flag mode on a join view. Operational metadata is also added twice (per table, then again after the join). The explicit `selectExp` in the samples drops the duplicates, so there it is just wasted work.

## D. The caller's config object is mutated

```
view's ReadConfig.mode was 'stream'; after read_source it is: 'batch'
```

`ReadConfig` is owned by the `View` (`self.read_config`) and handed to the source by reference. The loop overwrites `mode` with each source's mode. Every read assigns before it reads, so **nothing observes the stale value today**. It's a trap for the next change: anything that reads `read_config.mode` after the join, or reuses the view's config, gets the last source's mode. The fix costs nothing: `dataclasses.replace(read_config, mode=...)` per source.

## E. No watermark setting for stream-stream joins

`withWatermark` appears nowhere in the sources package (only in `table_import.py`), and `joinType` allows only `left` and `inner`. What Spark does with a stream-stream join and no watermark (measured):

```
left join without watermark -> AnalysisException: Stream-stream LeftOuter join ... is not supported without a watermark ...
inner join run 1: state rows = 2 | output rows = 1
inner join run 2: state rows = 4 | output rows = 1
inner join run 3: state rows = 6 | output rows = 1
```

A LEFT stream-stream join fails at start. An INNER one runs, and its state grows with **every row ever seen on either side**. Nothing is ever evicted, so state size, checkpoint time and restart time grow for the life of the pipeline. The only hook is a per-source `pythonTransform` (the schema allows one on each join source), which runs before the join and could add `withWatermark`. The join condition must then also carry an event-time range for Spark to evict state.

## The fix I'd propose upstream

1. **Declare, don't infer:** join order follows the `sources` list (or explicit `left`/`right` keys on each join). Validate that each join's aliases are declared, and stop discovering them.
2. **If aliases must be discovered,** use a parser instead of a regex: sqlglot, or walk the column references of Spark's parsed expression, so literals and struct fields can't create aliases.
3. **Apply quarantine and operational metadata once,** after the join: pass sub-sources a copy of `ReadConfig` without `quarantine_rules`.
4. **First-class watermarks** per stream source (`{"column": ..., "delay": ...}`). Validation should require an event-time bound in the condition for stream-stream joins.
5. **Tests:** reversed-condition equivalence (both texts must give the same row count), literal and struct-field conditions, and a quarantine rule on the second table.

## How I'd explain it

- **To the maintainers:** "The join direction comes from the text order of the condition, so `a = b` and `b = a` give different LEFT joins. We lose rows silently in batch mode. Here's a failing test using your real `SourceDeltaJoin`, and a proposal to take the order from `sources`."
- **To a customer using the framework:** "Until that's fixed, write every join condition with the preserved table's alias first, avoid decimal or dotted literals in join conditions (move them to a `whereClause`), and don't put quarantine rules on joined columns in flag mode."
- **To a stakeholder:** "One configuration detail decided whether customers without an address were kept or dropped, and nobody chose it on purpose. We're making it explicit and adding a test."
