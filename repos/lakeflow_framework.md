# lakeflow_framework: metadata-driven Spark Declarative Pipelines

**Repo:** `databricks-solutions/lakeflow_framework` @ `0e8d0ca` (v0.24.1, 2026-09-07). Open source from Databricks field engineering; "Databricks support does not cover this repository" (README.md:68).
**How I studied it:** traced the engine end to end, ran the unit suite (396 passed, in the repo's pinned lockfile environment), built the wheel, ran the framework's real classes on open-source Spark, and cross-checked a deep-read of docs, samples and ADRs. The raw report is in [`appendix/deep-read-reports/lakeflow_docs_samples.md`](../appendix/deep-read-reports/lakeflow_docs_samples.md).

## 1. What it is, for a customer

Teams describe pipelines as JSON/YAML **Data Flow Specs** instead of hand-writing SDP code. At pipeline start, one generic notebook (`src/dlt_pipeline.ipynb`) calls `DLTPipelineBuilder(spark, dbutils).initialize_pipeline()`, which:
1. reads every spec in the pipeline bundle and validates it against JSON Schema;
2. expands templates and substitutes per-environment `{tokens}` and `${secret.*}` values;
3. declares SDP views, streaming tables, materialized views, append / AUTO CDC flows, expectations, quarantine and sinks.

**The problem it solves:** platform teams running dozens to hundreds of medallion pipelines end up with copy-pasted, inconsistent CDC, DQ and table-property code, and no standard way to promote it. The framework turns "a new SCD2 table" into a reviewed spec plus a schema file, with DQ, audit columns and mandatory table properties applied uniformly. Config lives in Git: "No control tables".

**When not to use it:** a small estate or a single SDP-fluent team (plain SDP + DABs has fewer layers); logic outside the pattern envelope (streaming aggregations and windows are explicitly excluded); SDP features the spec doesn't expose (`cdc_settings` is a closed object, so no `apply_as_truncates` or `column_list`; no metric-view spec type); or when the customer needs vendor support or can't run a framework release process.

## 2. How it executes

```
dlt_pipeline.ipynb ─► DLTPipelineBuilder.initialize_pipeline()
   ├─ pipeline_config singletons: spark, dbutils, logger, substitutions, mandatory table props, op-metadata schema
   ├─ DataflowSpecBuilder.build()  (parallel across driver cores − 1)
   │     load *_main.json/yaml ─► template expansion ─► spec mapping (dataFlowVersion) ─► token substitution
   │     ─► JSON-Schema validation ─► spec transformers (nodespec is lowered to the legacy engine model)
   └─ for each DataFlow: create views (dp.view) ─► targets (streaming table / MV) ─► flows
         append_view / append_sql / merge (AUTO CDC) / cdc_snapshot / table_import / quarantine
```

**nodespec lowering** (the current default format): the terminal target becomes `targetDetails`; other targets become staging tables; each `sources` entry becomes a flow (`merge` if the target has CDC, else `append_view`); each `mv` target becomes its own MV spec.

**Checkpoints are identity.** SDP keys a streaming flow's checkpoint by its name, so renaming a flow means a full reprocess. nodespec derives `f_<node>` or lets you pin `{"view": ..., "flow": ...}`. The migration script pins legacy names so checkpoints survive.

**Placeholders and when they resolve:**

| Syntax | Resolved by | When |
|---|---|---|
| `${var.x}` | DAB CLI | deploy time |
| `${param.x}` | template processor | pipeline init, before validation |
| `{token}` | SubstitutionManager (`\{(\w+)\}`) | pipeline init |
| `${secret.alias}` | SecretsManager | pipeline init, redacted in logs |

**Precedence rules** (read at source, because a merge helper's argument order decides them): `merge_dicts_recursively(d1, d2)` lets **d1 win**. So pipeline substitutions beat framework ones (`substitution_manager.py:76`), and mandatory table properties beat per-table ones (`targets/base.py:85`). I initially assumed the opposite for table properties; see [case 06 #2](../case-studies/06-near-misses-and-false-positives.md).

## 3. Patterns worth stealing

| Pattern | Why it's good |
|---|---|
| **Framework bundle / pipeline bundle split** | Platform team owns the engine; domain teams own specs. Deploy framework first, then pipelines |
| **`src/local` sparse overlay (ADR-0006)** | Customer customisations deep-merge over defaults and are never touched by upstream upgrades. Dicts merge; lists and scalars replace |
| **Deploy the framework twice: `current` + `<version>`** | Pipelines point at `current`; canaries pin a version; rollback is a repoint, not a redeploy. (Caveat: `current` is a *mutable, fleet-wide* pointer. Treat a promotion as a fleet change.) |
| **Pinned flow names** | Protects streaming state across refactors and format migrations |
| **Streaming-DWH pattern** (TPCH `dim_customer`) | A change in *any* joined table re-drives its key: keys-only fan-in → SCD2 on `(key, version_ts)` → CDF → as-of joins. Stream-static joins alone only reflect the dimension "as of now" |
| **Unknown member `-1` + `COALESCE(sk, -1)`** | Facts never drop on a late dimension; a later full refresh re-resolves |
| **SCD1 AUTO CDC keyed on the fact grain** (`fct_order_lines`) | Makes re-delivery idempotent, unlike a pure append |
| **Parenthesised predicate composition** | `NOT((r1) AND (r2))`. A rule containing `OR` can't change the combined meaning (fix #141). But see NULLs below |
| **Fail-safe pluggable logger (ADR-0003)** | Customer logging integrations are config-only, and a broken custom logger falls back instead of crashing the pipeline |

## 4. What I found (status-tagged)

**Confirmed by execution:**

| Finding | Impact | Evidence |
|---|---|---|
| Wheel can't be built (`setuptools.backends.legacy` doesn't exist), can't be imported once built (bare `import pipeline_config`), and tests can't see it (`pythonpath = src`) | Documented `pip install` path is broken; not on PyPI | [case 01](../case-studies/01-lakeflow-packaging-three-stacked-faults.md), 3-line patch verified |
| Quarantine predicate is NULL when a rule is NULL; `.where()` routes the row nowhere | Rows with missing values neither quarantined nor clearly passed | [case 02](../case-studies/02-null-semantics-in-quarantine-predicates.md) |
| A spec-transformer exception is logged as WARNING and the untransformed spec continues | Fails later with an unrelated `TypeError` | [case 03 #1](../case-studies/03-fail-open-patterns.md) |
| `delta_join`: `a = b` vs `b = a` decides which side a LEFT join keeps; literals and struct fields create phantom aliases; flag-mode quarantine rules evaluated per table before the join; caller's `ReadConfig` mutated; no watermark setting | Silent row loss (batch), confusing errors (stream), unbounded state for stream-stream INNER joins | [case 07](../case-studies/07-lakeflow-delta-join-alias-parsing.md), with the real classes |
| Legacy specs validated with `Draft7Validator`, which ignores `dependentSchemas` (9 uses in 6 schema files) | Typos in legacy `sourceDetails`/`targetDetails`/`flowDetails` pass validation and fail at run time | [`evidence/lakeflow_validation_gaps.py`](../case-studies/evidence/lakeflow_validation_gaps.py) |
| `MAIN_SPEC_FILE_SUFFIX: tuple = ("_main.json")` is a `str`; the file-filter check iterates characters | `orders_dqe.json` passes the "is this a main spec" check | same script |
| `append_view` column-prefix exceptions extended with `StructField` objects, not names | With `column_prefix` + op metadata, `meta_load_details` gets prefixed. No sample uses `column_prefix`, so latent | [`evidence/verify_lakeflow_semantics.py`](../case-studies/evidence/verify_lakeflow_semantics.py) #1 |

**Confirmed by reading (deep-read, spot-checked by me):**
- Docs say `pipeline.targetTableFiler`; the engine reads `pipeline.targetTableFilter` (`constants.py:28`). Copy the docs and the filter is ignored, so **all flows run**.
- Unknown `{tokens}` are left verbatim with no warning (`substitution_manager.py:149-155`). The Kafka sink sample uses tokens its substitutions file doesn't define.
- nodespec specs were never schema-validated at runtime until commit `fca1b4e` (#142): a wrong path fell through to `errors = []`. "No errors" is not "validated".
- `CHANGELOG.md` is 0 bytes; the Operations and Monitoring pages say "Under Construction"; nothing queries the SDP event log.
- The shipped AI skill (`skills/dataflowspec_builder`) generates only legacy formats, pins "v0.4.0", teaches `versionType: "datetime"` and `yyyyMMdd` (the engine uses `strptime`), and its own validator reports 64 errors on 16 valid nodespec samples.

**Suspected (needs a workspace):**
- `table_import.py:92-115` builds SCD2 "closed rows" with a constant-event-time watermark aggregation. In OSS append mode it emits nothing ([Exercise 04, test C](../exercises/ex04_streaming_semantics/WALKTHROUGH.md)). Unknown: whether the AUTO CDC `once=True` flow evaluates it as batch (where it would work). Cheapest test: migrate a tiny SCD2 table with one closed record and check `__END_AT`.
- TPCH `fct_order_lines.sql` inner stream-static join to orders: a line arriving before its order header is dropped permanently.
- Table-mode quarantine with `expect` (not `expect_or_drop`) rules puts bad rows in **both** the clean and the quarantine table.

## 5. How it scales

- **Control plane:** initialisation reads and validates **every** spec in the bundle on every update (parallelised across driver cores − 1). Big bundles mean slow starts, so filter pipelines by group and decompose along staging/final pipelines.
- **Data plane:** that's SDP's job: incremental flows, per-flow checkpoints, incremental MV refresh (needs row tracking, which the default mandatory properties turn on). TPCH demonstrates ~30M line items.
- **State:** stream-stream joins have no watermark setting (case 07 E). Multi-source SCD2 fan-in creates extra versions with late arrivals.
- **Cost of determinism:** operational metadata uses `current_timestamp()`, so it must be disabled on snapshot CDC and `incremental_strict` MVs (18 sample files do).

## 6. How I'd explain it

- **Executive (30s):** "Every pipeline is hand-built today, so quality depends on who wrote it. This turns pipelines into reviewed configuration on Databricks' managed pipeline engine: new sources become a short spec, quality rules and history tracking are applied the same way everywhere, and the same definitions promote dev→prod. The trade-off is that it's open-source code your platform team owns."
- **Data engineer:** "You write a node graph: sources, transforms, targets. CDC is `cdc_settings` (keys, `sequence_by`, SCD1/2, deletes). At start-up it validates everything and declares the same SDP objects you'd write by hand. Keep flow names stable, use `live.` for in-pipeline reads, and validate with `scripts/validate_dataflows.py`."
- **Internal stakeholder:** "Good fit for platform-led customers with many similar flows. Watch-outs: packaging is broken for pip installs, legacy validation is shallow, the AI skill is stale, ops docs are stubs, and nodespec is weeks out of beta."

## 7. Interview angles

1. **"How would you debug 'the filter in my pipeline YAML is ignored and everything runs'?"** Exact-string config keys plus a misspelled doc (`targetTableFiler`), and unknown keys are ignored. Then check `{token}` typos, which pass through verbatim.
2. **"Why does renaming a flow trigger a full refresh?"** Checkpoints are keyed by flow name. Pin names.
3. **"A stream-static join shows stale addresses."** The static side is read as of each micro-batch; rows already written are never re-joined. Use the streaming-DWH pattern or as-of joins.
4. **"How do you upgrade the framework safely?"** Fork, keep customisations in `src/local`, deploy `current` + version, canary with pinned paths, roll back by repointing.
5. **"What does 'validated' mean here?"** Name the Draft 7 `dependentSchemas` gap and the pre-#142 silent `errors = []`. Validation needs a negative test: an invalid spec must be rejected.

## 8. AI-stewardship angle

- The repo ships an AI skill that is **wrong for today's code**: stale format, wrong enum values, and a validator that rejects valid specs. Anyone prompting with it gets confident, outdated output. So: validate against the framework's **real** JSON Schema (`scripts/validate_dataflows.py`), not the skill's script; diff against the nearest sample; deploy to a dev logical environment before promotion.
- A good prompt for this framework states the constraints the skill gets wrong: *"nodespec, snake_case, `scd_type` as a string, strftime datetime formats, pinned flow names, catalog/schema via `{tokens}`."*
