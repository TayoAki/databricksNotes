> **Provenance.** Deep-read of `databricks-solutions/lakeflow_framework` @ `0e8d0ca`, written by a research sub-agent during this study and kept verbatim, apart from local paths normalised to `<clone-root>/`. Its CONFIRMED / SUSPECTED labels are the agent's. The claims I re-verified myself, and how, are listed in [`README.md`](README.md); anything not listed there I have not independently checked.

# Lakeflow Framework (LFF): docs, samples, ADRs and spec format, deep-read report

**Repository:** `<clone-root>/lakeflow_framework` (github.com/databricks-solutions/lakeflow_framework). HEAD is `0e8d0ca` (2026-09-07, "fix: keep quarantine database when table name is unqualified (#153)"), and `VERSION` is `v0.24.1`.
**Scope:** docs, ADRs, samples, JSON schemas, the pipeline-bundle template, scripts, and tests. I read engine code under `src/lakeflow_framework/` only to verify doc claims.

**Evidence conventions.** Every `path:line` is relative to the repository root. The following abbreviations are used throughout:
- `D/` = `docs/source/`
- `ADR/` = `docs/decisions/`
- `SCH/` = `src/lakeflow_framework/schemas/`
- `ENG/` = `src/lakeflow_framework/`
- `FS/` = `samples/feature_samples/src/dataflows/feature_samples/dataflowspec/`
- `PS/` = `samples/pattern_samples/src/dataflows/`
- `TP/` = `samples/tpch_sample/`
- `SK/` = `skills/dataflowspec_builder/`

Labels:
- **CONFIRMED** means I verified it in the files or by running code.
- **SUSPECTED** means a strong inference that I did not execute on Databricks.
- "(inferred)" marks my own reasoning.
- "(platform)" marks general Spark Declarative Pipelines (SDP) knowledge that the repository does not state. Verify these against current Databricks docs.

**How the evidence was gathered:**
1. The provided clone is shallow (one commit), and `CHANGELOG.md` is **0 bytes**. For history I made a blobless public clone in my scratchpad: 84 commits, tags `v0.7.0` to `v0.24.1`.
2. I ran the repository's own validator (`scripts/validate_dataflows.py`) and the AI skill's validator against a scratch copy of the repository. I did not touch the clone.
3. Nothing was run on a Databricks workspace.

---

## 1. What it is, framed for a customer

The Lakeflow Framework is an open-source, metadata-driven framework from Databricks field engineering. Databricks product support does not cover it: "Databricks support does not cover this repository" (README.md:68).

It lets teams describe pipelines as **JSON/YAML "Data Flow Specs"** instead of hand-writing Spark Declarative Pipelines (SDP, formerly DLT) code. At pipeline start, a single generic entry notebook (`src/dlt_pipeline.ipynb`) calls `DLTPipelineBuilder(spark, dbutils).initialize_pipeline()`. The builder then:
- reads every spec in the pipeline bundle;
- validates each spec against JSON Schema;
- expands templates and substitutes environment tokens;
- declares SDP views, streaming tables, materialized views, append and AUTO CDC flows, expectations and sinks (D/architecture/index.rst:231-258).

**Customer problem.** Platform teams running dozens to hundreds of medallion pipelines end up with inconsistent, copy-pasted CDC, data-quality and table-property code, and no standard way to promote it across environments.

**Audience.** Central platform teams and domain data-engineering teams, in centralized, federated or hybrid operating models (D/architecture/index.rst:11-15).

**Outcome:**
- A new ingestion or SCD2 table becomes a small reviewed spec plus a schema file.
- Data quality, quarantine, operational metadata and mandatory table properties are standardized.
- Promotion runs through Declarative Automation Bundles (DABs).
- Framework upgrades are decoupled from pipeline code: there is one Framework Bundle and many Pipeline Bundles.

**Design stance.** Configuration lives in Git and workspace files: "No control tables" (D/get-started/what-is-lakeflow-framework.rst:43).

**When NOT to use a metadata framework (or LFF specifically):**
- **Small estate or a single SDP-fluent team.** Plain SDP SQL/Python plus DABs has fewer layers to learn and debug (inferred).
- **Logic outside the pattern envelope.** The streaming patterns explicitly exclude aggregations, `Window By` and complex transforms (D/build/patterns/basic-1-1.rst:76-79, D/build/patterns/multi-source-streaming.rst:107-109). You would live in Python escape hatches.
- **SDP features the spec does not expose.**
  - `cdc_settings` is a closed object (`additionalProperties: false`, SCH/definitions_main.json:17), so there is no `apply_as_truncates` or `column_list` (inferred from the schema).
  - Metric views have no spec type; the TPCH sample creates them in a post-pipeline notebook (TP/DESIGN.md:192-209).
- **You need vendor support or an SLA** (README.md:68), or out-of-the-box operational runbooks. The Operations and Monitoring pages say "Under Construction" (D/operations.rst:6, D/monitoring_and_observability.rst:6).
- **You cannot run a framework release process.** A pipeline that references the `current` framework path picks up every promoted framework release on its next update (section 5).

---

## 2. The spec format

### 2.1 Two spec generations and routing

- **nodespec** is the current default: snake_case, a flat list of `source` → `transformation` → `target` nodes (D/build/spec-reference/nodespec.rst:10-20).
- **Legacy** formats are camelCase `standard`, `flow` and `materialized_view` specs. They "remain fully supported" (D/build/spec-reference/legacy.rst:6-8).
- `SCH/main.json` routes specs:
  - Only specs with an explicit legacy `dataFlowType` are validated as legacy (SCH/main.json:4-7).
  - Everything else, including specs with no type, goes to `spec_nodespec.json` (SCH/main.json:3,47).
- `samples/` holds nodespec specs and `legacy_samples/` holds the same file tree in the legacy formats. `samples/` was produced by the migration script: `python migrate_to_nodespec.py --bundle legacy_samples/feature_samples --output-dir samples/feature_samples` (scripts/migrate_to_nodespec.py:31).
- nodespec landed on 2026-08-07 as "[BETA] feat(nodespec)" (commit 6b15bb8). The docs present it as "the framework's default" with no beta caveat (D/build/spec-reference/nodespec.rst:8,17).
- **Discovery.** A spec file must end in `_main.json` (or `_main.yaml`/`_main.yml`). Legacy flow specs can be split into a `_main` file and one or more `_flow` files (ENG/constants.py:113-129; D/build/spec-reference/legacy.rst:16). The bundle format is JSON or YAML, set globally with `allow_override` (shipped as `true` in ENG/config/default/global.json:2-5).

### 2.2 Top-level keys

| nodespec key | Legacy key | Notes |
|---|---|---|
| `data_flow_id` (required) | `dataFlowId` | Unique id; filterable with `pipeline.dataFlowIdFilter` |
| `data_flow_group` (required) | `dataFlowGroup` | The usual unit a pipeline selects (`pipeline.dataFlowGroupFilter`) |
| `data_flow_type` (optional, const `nodespec`) | `dataFlowType` (required: `standard`/`flow`/`materialized_view`) | Omitted type means nodespec |
| `data_flow_version` | `dataFlowVersion` | Selects a spec-mapping version (rename/move/delete keys) |
| `tags`, `features` | same | e.g. `features.operationalMetadataEnabled` |
| `nodes[]` (at least 1) | source/target/cdc/`flowGroups`/`materializedViews` blocks | Closed object (`additionalProperties: false`) |

Sources: SCH/spec_nodespec.json:9-27; SCH/main.json:8-22.

### 2.3 Nodes, sources, targets and wiring

**Source nodes** (`source_type` enum at SCH/spec_nodespec.json:49):
- **`delta`**: `table` is required. Also takes `database`, `cdf_enabled`, `cdf_change_type_override`, `starting_version_from_dlt_setup` (which requires CDF), `reader_options`, `select_exp`, `where_clause`, `schema_path` and `as_view`. With `as_view: false`, the table is read directly into the consuming flow rather than through an extra view (SCH/spec_nodespec.json:170-197).
- **`cloud_files`** (Auto Loader): `path` and `reader_options` are required, including `cloudFiles.format`. Useful options: `cloudFiles.schemaEvolutionMode` (`addNewColumns`/`rescue`/`failOnNewColumns`), `schemaHints`, `maxFilesPerTrigger`, and CSV/JSON parser options (SCH/spec_nodespec.json:199-213,535-577).
- **`batch_files`**: `format` is one of csv/json/parquet/text/xml; the default mode is batch (SCH/spec_nodespec.json:215-230).
- **`kafka`**: `reader_options` must include `kafka.bootstrap.servers` (SCH/spec_nodespec.json:232-245,579-599).
- **`delta_join`**: `sources[{database, table, alias, cdf_enabled, join_mode: stream|static}]` plus `joins[{join_type: left|inner, condition}]` (SCH/spec_nodespec.json:247-290).
- **`sql` / `python` as sources**: provide exactly one of `sql_path`/`sql_statement`, or one of `function_path`/`python_module`. These are "discouraged and emit a warning", and a transformation node is preferred (D/build/spec-reference/nodespec.rst:265-269).

**Transformation nodes:**
- `sql`: the SQL names its upstream view, for example `FROM STREAM(live.v_source_customer)`.
- `python`: the file or module must expose `apply_transform(df)` or `apply_transform(df, tokens)`. The upstream view is inferred from the graph (D/build/spec-reference/nodespec.rst:283-301).

**Target nodes:**
- `target_type` is `delta` (the default), `delta_sink`, `kafka_sink`, `foreach_batch_sink` or `custom_python_sink` (SCH/spec_nodespec.json:125-130).
- `table_type` is `st` (streaming table, the default) or `mv` (SCH/spec_nodespec.json:338).
- The schema enforces which fields belong to which table type (SCH/spec_nodespec.json:362-384):
  - MV only: `sql_path`, `sql_statement`, `refresh_policy`, `private`.
  - Streaming table only: `cdc_settings`, `cdc_snapshot_settings`, `table_migration`, `once`.
- Sink targets keep a flat `name`/`sink_type`/`sink_config`/`sink_options` shape; the "sink redesign [is] deferred" (SCH/spec_nodespec.json:387-398).

**Wiring and flow names:**
- A target lists what feeds it in `sources`.
  - A plain string means the SDP flow is named `f_<node>`.
  - `{"view": ..., "flow": ...}` pins the flow name (SCH/spec_nodespec.json:400-417).
- Pinning matters because "SDP keys a streaming flow's checkpoint by its name, so renaming a flow forces a full refresh" (ADR/0010-unified-nodespec-dataflow-spec.md:113-115). The migrated samples pin the legacy names, for example `{ "view": "v_customer", "flow": "f_customer" }` (PS/multi_source_streaming_samples/dataflowspec/customer_multi_streaming_basic_main.json:12-19).

**Lowering nodespec into the engine's representation** (D/build/spec-reference/nodespec.rst:527-538):
1. The terminal target (the one no other node consumes) becomes `targetDetails`, and its CDC/DQ/quarantine settings move to spec level.
2. Every other target becomes a staging table.
3. Each `sources` entry becomes a flow: `merge` if the target has CDC, otherwise `append_view` (or `append_sql` for inline SQL).
4. Each `mv` target becomes its own materialized-view spec.
5. Everything lands in one flow group, `nodespec_main` (tests/integration/test_feature_samples_spec_builder.py:38).

### 2.4 CDC settings (AUTO CDC / `apply_changes`)

**`cdc_settings`** (SCH/definitions_main.json:4-19):

| Field | Meaning |
|---|---|
| `keys[]` (required) | Business key |
| `sequence_by` (required) | Ordering column: "SDP uses this sequencing to handle change events that arrive out of order" (D/build/spec-reference/cdc.rst:38) |
| `scd_type` (required) | Must be the string `"1"` or `"2"`. An integer `2` is rejected: CONFIRMED by my validator run (SCH/definitions_main.json:13) |
| `apply_as_deletes` | SQL predicate marking delete events |
| `where` | Row filter |
| `ignore_null_updates` | Nulls keep the existing values (D/build/spec-reference/cdc.rst:50) |
| `except_column_list` | Columns used but not stored, typically the sequence column and CDC flags |
| `track_history_column_list` / `track_history_except_column_list` | Restrict which columns open a new SCD2 version |

**Deletes:**
- With SCD1, deletes become tombstones in the underlying table, and a view filters them out (D/features/platform/soft-deletes.rst:19).
- With SCD2, `apply_as_deletes` closes the open version (TP/DESIGN.md:299-306).

**`cdc_snapshot_settings`** (AUTO CDC FROM SNAPSHOT; SCH/spec_nodespec.json:483-533). It requires `keys`, `scd_type` and `snapshot_type`.
- **`historical`**: the target reads files or a table directly, with no source node. You set `source_type` to `file` (needing `path` and `format`) or `table` (needing `table`, plus `version_column`).
  - Path patterns: `{version}`, `{fragment}` for multi-file versions, or regex groups `(?P<version_x>...)` concatenated left to right (D/build/spec-reference/cdc.rst:180-265).
  - Legacy file `versionType` is `integer` or `timestamp` (SCH/definitions_main.json:84). The table variant allows `date`/`timestamp`/`integer`/`long` (SCH/definitions_main.json:131).
  - Datetime formats are parsed with Python `strptime` (ENG/dataflow/cdc_snapshot.py:585), so write `%Y%m%d`, not `yyyyMMdd`.
- **`periodic`**: the target reads an upstream source node, and each pipeline update takes one snapshot, versioned by ingestion time (D/features/platform/cdc.rst:39).
- **`deduplicateMode`** is `off`, `full_row` or `keys_only`. `keys_only` is non-deterministic (D/build/spec-reference/cdc.rst:94-99). It belongs inside `source` (SCH/definitions_main.json:91,134), not at the settings level as the doc table implies. Placed at settings level it fails validation (CONFIRMED by my run).

### 2.5 Data-quality expectations and quarantine

**Expectations file** (SCH/expectations.json): arrays under `expect`, `expect_or_drop` and `expect_or_fail`. Each item is `{name, constraint, tag?, enabled?}`, and `enabled: false` switches a rule off (for example PS/base_samples/bronze/expectations/customer_address_dqe.json:9-12).

**Spec block** (SCH/spec_nodespec.json:419-457):
- nodespec: `data_quality: {enabled (default true), expectations_path (required), quarantine: {mode: flag|table, target: {...}}}`.
  - `"off"` is **invalid** in nodespec: you omit `quarantine` instead (CONFIRMED by my run).
- Legacy: `dataQualityExpectationsEnabled`, `dataQualityExpectationsPath`, `quarantineMode: off|flag|table` and `quarantineTargetDetails` (SCH/spec_standard.json:23-26).

**What the engine actually does** (verified in code; the docs are thin, D/features/data-quality/quarantine.rst:17-25):
- **Quarantine predicate.** It is `NOT((r1) AND (r2) ...)` over all enabled rules, whatever each rule's action. Parenthesization was added after a rule containing `OR` changed the combined meaning (ENG/dataflow/quarantine.py:54-56; commit deece3d, #141).
- **`flag` mode.** Every rule is downgraded to `expect_all` (warn only), and each row gets an `is_quarantined` boolean. Bad rows stay in the target (ENG/dataflow/dataflow.py:225-227; ENG/dataflow/sources/base.py:124-130; ENG/constants.py:195-196).
- **`table` mode.** The main target keeps its declared actions. A parallel append flow, `f_quarantine_<view>_quarantine`, re-reads the same source view, keeps the flagged rows and appends them to `<target>_quarantine`. That quarantine target is a streaming table for streaming targets and a quarantine materialized view for batch targets (ENG/dataflow/dataflow.py:427; ENG/dataflow/quarantine.py:81-114,142-247).
  - (inferred) Bad rows leave the clean table only when their rule is `expect_or_drop`. With `expect`, they land in **both** tables. With `expect_or_fail`, the update still fails.
- **Quarantine table naming.** The default is `<target>_quarantine`. An explicit `database` is kept when the table name is unqualified; that was fix #152/#153 (ENG/dataflow/quarantine.py:76-88).
- `append_sql` flows cannot use table-mode quarantine because there is no source view (D/features/platform/multi-source-streaming.rst:53).

### 2.6 Table properties, clustering, partitioning and operational metadata

- **`table_properties`** values must be strings (SCH/spec_nodespec.json:341).
- **Mandatory table properties** from global config are merged on top of per-table properties and win on conflict (ENG/dataflow/targets/base.py:85-88); "These properties cannot be overridden at the individual table level" (D/features/configuration/mandatory-table-properties.rst:116). The shipped defaults are 45-day log and deleted-file retention plus `delta.enableRowTracking=true` (ENG/config/default/global.json:11-15). Row tracking is what enables incremental MV refresh (TP/DESIGN.md:238-245).
- **Partitioning and clustering:**
  - `partition_columns` and `cluster_by_columns` are mutually exclusive (SCH/spec_nodespec.json:361).
  - `partition_columns` combined with `cluster_by_auto: true` **passes** validation (CONFIRMED by my run; a runtime error is SUSPECTED).
  - `cluster_by_auto` plus `cluster_by_columns` means the columns seed the keys and auto-clustering evolves them (D/features/platform/liquid-clustering.rst:35).
- **`schema_path`** points to a `.json` StructType, or a `.ddl` file that supports constraints, generated columns and column masks (D/features/metadata/schema-management.rst:145-156). It is best left off staging tables, to benefit from schema evolution (D/build/spec-reference/flows.rst:308).
- **Other target keys:** `comment`, `spark_conf`, `row_filter`, `path`, `once`, and `config_flags: ["disable_operational_metadata"]` (SCH/spec_nodespec.json:340-349).
- **Operational metadata** (added per layer, selected by `pipeline.layer`):
  - It is a `meta_load_details` struct with `record_insert_timestamp`, `record_update_timestamp` (both `current_timestamp()`), `pipeline_start_timestamp` and `pipeline_update_id` (ENG/config/default/operational_metadata_bronze.json:5-54).
  - The update id is captured by an `@dp.on_event_hook` (ENG/dlt_pipeline_builder.py:169).
  - Because `current_timestamp()` is non-deterministic, **every snapshot-CDC sample and the `incremental_strict` MVs disable it**. A grep for `disable_operational_metadata` finds 18 sample files, and commit 8982585 (#21) says "fix periodic snapshot samples to exclude op metadata".

### 2.7 Placeholders and resolution order

| Syntax | Resolved by | When | Example |
|---|---|---|---|
| `${var.x}` | DAB CLI | Deploy time (YAML resources) | `${var.framework_source_path}` |
| `${param.x}` | Template processor | Pipeline init, expanded then validated | `"table": "${param.table}"` |
| `{token}` | SubstitutionManager, regex `\{(\w+)\}` | Pipeline init | `"database": "{silver_schema}"` |
| `${secret.alias}` | SecretsManager | Pipeline init, redacted in logs | `"${secret.kafka_source_bootstrap_servers}"` |

Evidence: ENG/substitution_manager.py:30; D/features/metadata/templates.rst:126; D/features/configuration/secrets-management.rst:95-97; TP/DESIGN.md:263-264 ("template substitution resolves `${param.*}` first, leaving the `{...}` substitution token for ... runtime").

Gotchas:
- **Unknown tokens are silently left verbatim** (ENG/substitution_manager.py:149-155).
- **Pipeline-detail fields are injected as tokens.** `{logical_env}`, `{workspace_env}` (which is `bundle.target`), `{pipeline_catalog}` and others become tokens (ENG/dlt_pipeline_builder.py:159,346; ENG/pipeline_details.py:8-14).
- **Prefix/suffix rules concatenate with no separator** (ENG/substitution_manager.py:176-178).
- **YAML quoting.** Token values must be quoted: `database: '{staging_schema}'` (samples/yaml_sample/src/dataflows/yaml_samples/dataflowspec/customer_address_main.yaml:10). Unquoted, YAML reads a mapping (inferred). Likewise the docs quote `quarantineMode: 'off'` (D/build/spec-reference/flows.rst:143), because unquoted `off`/`on` are YAML 1.1 booleans (inferred).

### 2.8 Annotated examples (verbatim)

**Bronze: stream from staging with change data feed (CDF), DQ and table-mode quarantine.** Source: `PS/base_samples/bronze/dataflowspec/customer_address_main.json`, lines 1-16.
```json
{
    "data_flow_id": "base_customer_address",
    "data_flow_group": "base_bronze",
    "data_flow_type": "nodespec",
    "nodes": [
        {
            "name": "v_customer_address",
            "node_type": "source",
            "source_type": "delta",
            "config": {
                "mode": "stream",
                "database": "{staging_schema}",
                "table": "customer_address",
                "cdf_enabled": true
            }
        },
```
Lines 17-43:
```json
        {
            "name": "target_base_customer_address_append",
            "node_type": "target",
            "config": {
                "database": "{bronze_schema}",
                "table": "base_customer_address_append",
                "table_properties": {
                    "delta.enableChangeDataFeed": "true"
                },
                "schema_path": "customer_address_schema.json",
                "data_quality": {
                    "enabled": true,
                    "expectations_path": "./customer_address_dqe.json",
                    "quarantine": {
                        "mode": "table",
                        "target": {
                            "target_format": "delta"
                        }
                    }
                },
                "sources": [
                    "v_customer_address"
                ]
            }
        }
    ]
}
```
Annotations:
- `data_flow_group` is how the pipeline selects this spec: `pipeline.dataFlowGroupFilter: base_bronze` (samples/pattern_samples/resources/serverless/pipelines/pattern_base_bronze_pipeline.yml:19).
- `{staging_schema}` and `{bronze_schema}` resolve from `src/pipeline_configs/dev_substitutions.json`. Values such as `main.lakeflow_samples_bronze{logical_env}` nest a second token (samples/pattern_samples/src/pipeline_configs/dev_substitutions.json:3-4).
- With no `cdc_settings` on the target, the flow is an **append** flow into a streaming table named `f_v_customer_address` (inferred from the `f_<node>` rule). CDF is read from staging and CDF is enabled on the target for the silver layer to consume.
- The expectation file uses `expect_or_drop` (`CUSTOMER_ID IS NOT NULL`), so failing rows are dropped from the target and copied to `base_customer_address_append_quarantine` (PS/base_samples/bronze/expectations/customer_address_dqe.json:2-7).

**Silver: SCD2 with deletes.** Source: `PS/base_samples/silver/dataflowspec/customer_main.json`, lines 1-16 (the source node reads bronze CDF).
```json
{
    "data_flow_id": "base_customer",
    "data_flow_group": "base_silver",
    "data_flow_type": "nodespec",
    "nodes": [
        {
            "name": "v_customer",
            "node_type": "source",
            "source_type": "delta",
            "config": {
                "mode": "stream",
                "database": "{bronze_schema}",
                "table": "base_customer_append",
                "cdf_enabled": true
            }
        },
```
Lines 17-45:
```json
        {
            "name": "target_base_customer_scd2",
            "node_type": "target",
            "config": {
                "database": "{silver_schema}",
                "table": "base_customer_scd2",
                "table_properties": {
                    "delta.enableChangeDataFeed": "true"
                },
                "schema_path": "customer_schema.json",
                "cdc_settings": {
                    "keys": [
                        "CUSTOMER_ID"
                    ],
                    "scd_type": "2",
                    "sequence_by": "LOAD_TIMESTAMP",
                    "except_column_list": [
                        "LOAD_TIMESTAMP"
                    ],
                    "ignore_null_updates": false,
                    "apply_as_deletes": "DELETE_FLAG = 1"
                },
                "sources": [
                    "v_customer"
                ]
            }
        }
    ]
}
```
Annotations:
- The presence of `cdc_settings` turns the flow into a **merge** flow, that is, AUTO CDC (D/build/spec-reference/nodespec.rst:535-537).
- `sequence_by: LOAD_TIMESTAMP` orders events per key. With SCD2, the `__START_AT`/`__END_AT` columns carry sequence values, which is why `LOAD_TIMESTAMP` sits in `except_column_list` (inferred from SDP semantics and TP/DESIGN.md:299-306).
- `apply_as_deletes` compares a BOOLEAN column with `1` (the schema has `"type": "boolean"` at PS/base_samples/silver/schemas/customer_schema.json:29-30). This is the same boolean-vs-int pattern the maintainers had to make "ANSI-safe" in their own quarantine filter (commit deece3d changed `where(f"{col} = 1")` to `where(F.col(col))`). SUSPECTED to fail under ANSI mode; prefer `DELETE_FLAG = true`, as the multi-source sample does (PS/multi_source_streaming_samples/dataflowspec/customer_multi_streaming_basic_main.json:123).

A richer silver feed (history tracking, business-time sequencing, table-mode quarantine into an explicit schema): `TP/src/dataflows/silver/dataflowspec/customer_address_main.json`, lines 36-64.
```json
                "cdc_settings": {
                    "keys": [
                        "customer_key"
                    ],
                    "scd_type": "2",
                    "sequence_by": "effective_date",
                    "apply_as_deletes": "cdc_operation = 'D'",
                    "except_column_list": [
                        "load_timestamp",
                        "effective_date",
                        "cdc_operation"
                    ],
                    "ignore_null_updates": false,
                    "track_history_column_list": [
                        "address",
                        "nation_key"
                    ]
                },
                "data_quality": {
                    "enabled": true,
                    "expectations_path": "./customer_address_dqe.json",
                    "quarantine": {
                        "mode": "table",
                        "target": {
                            "target_format": "delta",
                            "database": "{silver_schema}"
                        }
                    }
                },
```
Annotations:
- Sequencing by the business `effective_date` rather than load time is what lets a late-arriving 1994 correction slot into history between the 1992 and 1996 versions (TP/GUIDE.md:153-157; TP/README.md:120-124).
- `database` without `table` in the quarantine block is exactly the case fixed by #153: the table becomes `<target>_quarantine` inside `{silver_schema}`.

**Gold: materialized views, including incremental-strict refresh and a chained MV.** Source: `PS/base_samples/gold/dataflowspec/gold_materialized_views_main.json`, lines 1-15.
```json
{
    "data_flow_id": "base_gold_materialized_views",
    "data_flow_group": "base_gold_samples",
    "data_flow_type": "nodespec",
    "nodes": [
        {
            "name": "target_base_dim_customer_mv",
            "node_type": "target",
            "config": {
                "table": "base_dim_customer_mv",
                "table_type": "mv",
                "sql_statement": "SELECT * FROM {silver_schema}.base_customer_scd2",
                "comment": "Gold materialized view of silver customer table"
            }
        },
```
Lines 16-40:
```json
        {
            "name": "target_base_dim_customer_mv_incremental",
            "node_type": "target",
            "config": {
                "table": "base_dim_customer_mv_incremental",
                "table_type": "mv",
                "sql_statement": "SELECT c.CUSTOMER_ID, c.FIRST_NAME, c.LAST_NAME, c.EMAIL, ca.CITY, ca.STATE FROM {silver_schema}.base_customer_scd2 c INNER JOIN {silver_schema}.base_customer_address_scd2 ca ON c.CUSTOMER_ID = ca.CUSTOMER_ID",
                "refresh_policy": "incremental_strict",
                "config_flags": [
                    "disable_operational_metadata"
                ]
            }
        },
        {
            "name": "target_base_dim_customer_mv_chained",
            "node_type": "target",
            "config": {
                "table": "base_dim_customer_mv_chained",
                "table_type": "mv",
                "sql_statement": "SELECT * FROM live.base_dim_customer_mv_incremental WHERE STATE IS NOT NULL",
                "comment": "Chained MV filtering non-null states from base_dim_customer_mv_incremental"
            }
        }
    ]
}
```
Annotations:
- MV targets need no source node; the SQL is the definition.
- Cross-pipeline reads use fully qualified `{silver_schema}` names. In-pipeline reads must use `live.` so SDP orders the graph (TP/GUIDE.md:245-250).
- `incremental_strict` is "Beta, requires DBR 17.3+" and "disallows non-deterministic functions (e.g. `current_timestamp()`)", hence `disable_operational_metadata` (D/features/platform/materialized-views.rst:232-235).
- Modeling smell: the incremental MV joins two SCD2 **histories** on the key without a `__END_AT IS NULL` or as-of predicate, so it emits the cross product of versions. SUSPECTED by reading the SQL; see risk R10.

### 2.9 Validation reality: what I ran

I ran `scripts/validate_dataflows.py --no-mapping` on a scratch copy.

| Input | Result | Reason |
|---|---|---|
| All 63 `samples/**/*_main.json` | pass | |
| Example in D/features/metadata/spec-format.rst:176-200 | **5 errors** | `sourceType: autoloader`, extra `sourceFormat`, `quarantineMode: "on"`, missing `sourceViewName`, missing expectations path |
| Example in D/build/spec-reference/flows.rst:18-113 | fails | `quarantineTargetDetails: {}` requires `targetFormat` (SCH/definitions_main.json:155) |
| Doc `versionType: "datetime"` (D/build/spec-reference/cdc.rst:122) | fails | Enum is `integer`/`timestamp` |
| `deduplicateMode` at settings level (D/build/spec-reference/cdc.rst:94) | fails | It belongs under `source` |
| nodespec `scd_type: 2` (an int), or quarantine `mode: "off"` | fail | String `"2"` required; enum is `flag`/`table` |
| nodespec `cdc_settings` on an `mv` target | fails (correct) | `table_type` guard |
| **Legacy** `delta` source with `{"databaseTYPO":..,"bogusKey":123}`, a `.txt` schemaPath, partition plus cluster columns, and a bogus `flowDetails` | **passes** | Draft 7 ignores `dependentSchemas` (below) |
| nodespec `partition_columns` + `cluster_by_auto` | passes | Only partition plus `cluster_by_columns` is forbidden |

**Key finding (CONFIRMED).** Both the engine and the CI script validate with `jsonschema.Draft7Validator` (ENG/utility.py:108-113; scripts/validate_dataflows.py:42,335). Draft 7 does not implement the `dependentSchemas` keyword, which was introduced in 2019-09. That keyword carries all per-type rules in the legacy schemas: 9 occurrences across 7 files, for example SCH/spec_standard.json:31, SCH/flow_group.json:20,38,125 and SCH/definitions_targets.json:55,166.
- As a result, legacy `sourceDetails`, `targetDetails`, `flowDetails`, staging-table and sink shapes are **never schema-checked**; mistakes surface at run time.
- nodespec uses `if`/`then`, which Draft 7 supports, so typos there are caught.

---

## 3. Pattern catalogue

"ST" is a streaming table. "Under the hood" combines doc statements, engine code, and (platform) knowledge where marked.

| Pattern | Customer problem it solves | Key spec settings | What SDP does under the hood | Sample path |
|---|---|---|---|---|
| Bronze 1:1 append | Land source tables faithfully, with lineage | source `delta` + `cdf_enabled`, `mode: stream`; target without `cdc_settings` | `append_flow` into an ST; one checkpoint per flow `f_<view>`; reads upstream CDF incrementally | PS/base_samples/bronze/dataflowspec/customer_main.json |
| Schema-on-read Auto Loader | Many files; evolving source schemas | `cloud_files`; `cloudFiles.format: parquet`, `cloudFiles.schemaEvolutionMode: addNewColumns`, `pathGlobFilter` | Auto Loader stream; schema inferred once, evolved on new columns (old rows read NULL); file progress kept in the checkpoint (platform) | TP/src/templates/bronze_parquet_ingestion_template.json:34-47 |
| Kafka ingest | Event streams | `kafka`; `kafka.bootstrap.servers` via `${secret.*}`, `subscribe`, `startingOffsets` | Structured Streaming Kafka source; offsets in the flow checkpoint (platform) | samples/feature_samples/src/dataflows/kafka_samples/dataflowspec/kafka_source_basic_main.json |
| SCD1 upsert | Current-state data; idempotent fact upserts | `cdc_settings.scd_type: "1"`, `keys`, `sequence_by` | AUTO CDC overwrite per key; out-of-order events resolved by `sequence_by`; deletes become tombstones hidden by a view (D/features/platform/soft-deletes.rst:19) | TP/src/dataflows/silver/dataflowspec/silver_scd1_main.json; TP/src/dataflows/gold/dataflowspec/fct_order_lines_main.json:35-46 |
| SCD2 history | Audit and as-of analysis | `scd_type: "2"`, `except_column_list`, `track_history_*`, `apply_as_deletes` | AUTO CDC keeps `__START_AT`/`__END_AT` from `sequence_by` values; late events are inserted into history; a delete closes the open row | PS/base_samples/silver/dataflowspec/customer_main.json |
| CDC from historical snapshots | Source only provides full dumps (versioned files or table versions) | Target-only node with `cdc_snapshot_settings.snapshot_type: historical`, `source_type: file|table`, `version_type`, `datetime_format`, `{version}`/`{fragment}`/regex paths, `deduplicate_mode`; operational metadata disabled | AUTO CDC FROM SNAPSHOT processes versions in order, diffing consecutive snapshots; new versions are picked up on each update (D/features/platform/cdc.rst:41-45) | FS/historical_snapshot_*_main.json (10 variants) |
| CDC from periodic snapshots | Table overwritten each load | Batch source node plus `snapshot_type: periodic` | One snapshot per update, versioned by ingestion time (D/features/platform/cdc.rst:39) | FS/periodic_snapshot_scd1_main.json, FS/periodic_snapshot_scd2_main.json |
| Snapshot to CDC stream (building block) | Combine snapshot sources with streaming patterns | Bronze **SCD1** snapshot target (CDF on), then silver reads its CDF with `apply_as_deletes: "cdc_change_type = 'delete'"` | SCD1 is required so physical deletes appear as CDF deletes; "SCD2 does not support this" (D/build/patterns/cdc-stream-from-snapshot.rst:49) | PS/snapshot_samples/dataflowspec/bronze_customer_*_snapshot_main.json, PS/snapshot_samples/dataflowspec/silver_customer_*_snapshot_main.json |
| Multi-source streaming (append fan-in) | Several sources share one business key | Staging ST with 2+ `sources` (append); merge ST with `cdc_settings` + `ignore_null_updates: true`; CDF re-read from `live`; SQL transform; final SCD2 | One checkpoint per append flow; AUTO CDC coalesces partial rows (nulls keep old values); **more SCD2 versions with late arrivals** (D/build/patterns/multi-source-streaming.rst:116-117); flows can be added or removed without a full refresh (D/architecture/index.rst:413) | PS/multi_source_streaming_samples/dataflowspec/customer_multi_streaming_basic_main.json (+ decomposed staging/final) |
| Stream-static basic | Enrich a driving stream with lookup tables | `delta_join` with `join_mode: stream|static`, `joins[{join_type, condition}]` | Static side read **in full as a batch** per micro-batch, then a plain join (ENG/dataflow/sources/delta_join.py:83,99); lookup changes are not reflected until the key re-arrives (D/build/patterns/stream-static-basic.rst:92) | PS/stream_static_samples/dataflowspec/silver_customer_stream_static_basic_main.json |
| Stream-static "streaming DWH" | Reflect changes in **any** joined table | Keys-only fan-in into append ST, then SCD2 on keys + `version_ts`, then CDF, then `delta_join` or SQL as-of joins to every table, then SCD2 target | Any source change re-drives its key through the join; as-of range predicates choose the right versions | PS/stream_static_samples/dataflowspec/*streaming_dwh*, PS/stream_static_samples/dataflowspec/gold_dim_customer_{json,sql}_main.json; TP/src/dataflows/gold/dataflowspec/dim_customer_main.json |
| Gold materialized views | Serving dimensions, facts and aggregates | `table_type: mv`, `sql_statement`/`sql_path`, `refresh_policy`, chaining via `live.` | MV refresh, incremental when possible; needs row tracking on sources (D/features/platform/materialized-views.rst:30-37); `incremental_strict` refuses non-deterministic SQL | PS/base_samples/gold/dataflowspec/gold_materialized_views_main.json; TP/src/dataflows/gold/dataflowspec/dimensions_main.json, TP/src/dataflows/gold/dataflowspec/facts_aggregated_main.json |
| Point-in-time star fact | Facts must reference the dimension version valid at event time | SQL transform with as-of joins, `xxhash64` surrogate keys, `COALESCE(sk,-1)` unknown member | Stream-static join resolves the key once, at upsert time; a late dimension needs a fact full refresh (TP/DESIGN.md:308-327) | TP/src/dataflows/gold/dml/fct_order_lines.sql |
| DQ + quarantine flag | Keep all rows but mark bad ones | `data_quality.quarantine.mode: flag` | Rules become `expect_all`; adds `is_quarantined` | FS/quarantine_flag_main.json |
| DQ + quarantine table | Route bad rows to triage | `mode: table` (+ `target.database/table`) | Extra append flow into `<target>_quarantine`; main target keeps its actions | FS/quarantine_table_main.json, FS/quarantine_table_with_cdc_main.json; TP/src/dataflows/silver/dataflowspec/orders_main.json |
| Once flow (backfill) | One-time historical load into an existing ST | Target `once: true` + batch source; pinned flow name | `append_flow(once=True)` runs once; a batch read is forced (commit f6fe798, #22) | FS/append_view_once_flow_main.json |
| Append SQL (discouraged) | Quick SQL-defined source | `source_type: sql` with `STREAM(...)` | Append from SQL; warns at build time; no table-mode quarantine | FS/append_sql_flow_main.json |
| Python source / transform | Logic SQL can't express | `get_df(spark, tokens)` source; `apply_transform(df[, tokens])` | Python-defined view (D/features/python/functions.rst:206-217; D/features/python/source.rst:165-177) | FS/python_source_main.json, FS/python_transform_main.json (+ `*_extension`); FS/python_library_install_demo_main.json (a bundled wheel, `phonenumbers`, installed via pipeline `environment.dependencies`) |
| Sinks | Push to external Delta, Kafka or custom targets | `target_type: delta_sink|kafka_sink|foreach_batch_sink`; `sink_options` / `sink_config` | SDP sink API (`pipelines.externalSink.enabled`, ENG/config/default/global.json:9); `foreach_batch` SQL must read `micro_batch_view` in batch form (D/build/spec-reference/target-details.rst:220-224) | FS/sink_delta_uc_table_main.json, FS/sink_foreach_batch_*; kafka_samples/dataflowspec/kafka_sink_main.json |
| Table migration | Adopt existing HMS/UC tables without reprocessing | `table_migration{catalog_type, source{select_exp...}, auto_starting_versions_enabled}` + `table_migration_state_volume_path` | One-time import flow; CSV state in a UC volume; sources resume at `startingVersion = baseline + 1`, or `WHERE 1=0` until ready (D/features/migrations/table-migration.rst:164-165) | FS/table_migration_append_only_main.json, FS/table_migration_scd2_main.json |
| Templates | Many near-identical flows | Template definition (`parameters` + `template`) + usage (`template` + `parameter_sets`) | Expanded at init into N specs, each validated (D/features/metadata/templates.rst:28-30) | TP/src/templates/*; samples/feature_samples/src/templates/cdc_stream_from_snapshot_template.json |
| DDL schema | Constraints, generated columns, masks | `schema_path: *.ddl` | DDL applied to the table definition | FS/ddl_schema_main.json + samples/feature_samples/src/dataflows/feature_samples/schemas/target/feature_ddl_schema.ddl |
| Spec version mapping | Keep old spec shapes running after upgrades | `dataFlowVersion` + `dataflow_spec_mapping/<ver>` (`rename_all` / `rename_specific` / `move` / `delete`) | Keys rewritten before validation (ENG/config/default/dataflow_spec_mapping/0.2.0/dataflow_spec_mapping.json:1-24) | FS/version_mapping_*_main.json |
| Mixed ST + MV in one spec | Keep one logical pipeline in one file | nodespec targets with different `table_type` | Lowered into a flow spec plus MV specs (D/build/spec-reference/nodespec.rst:520-522,538) | FS/materialized_views_main.json |
| Data Vault (hubs, links, satellites) | Claimed modeling paradigm | None shipped. (inferred) Hubs as 1:1 SCD1/append, satellites as SCD2, links as multi-source | — | **No sample.** Claimed at README.md:18 and D/build/patterns/basic-1-1.rst:27 (CONFIRMED absent) |

---

## 4. The TPCH sample, end to end

**Purpose.** Treat `samples.tpch` (TPC-H scale factor ~5: 7.5M orders, ~30M line items) as an "ERP database" and build a real warehouse on it (TP/README.md:6-15; TP/DESIGN.md:19-40).

**Deploy and run.** `./deploy_tpch_and_test.sh ... --warehouse_id <id>` runs deploy, then setup, then Run 1 (full refresh), Run 2 and Run 3 (TP/README.md:67-76). The SQL warehouse is optional; it only backs Genie and the dashboards (samples/common.sh:117-149).

0. **Setup job** (one-time, slow). Creates the schemas and the staging volume, then lands **12 Parquet staging entities from 8 simulated source systems**. Customer and supplier are split across CRM, procurement and vendor-management systems so gold has a real multi-source merge to do (TP/DESIGN.md:452-494). An optional "realism" pass reshapes distributions deterministically, preserving volumes and the pinned demo keys (TP/DESIGN.md:3.21).
1. **Bronze: schema-on-read.**
   - One template (`bronze_parquet_ingestion_template`) and one usage spec with 12 `parameter_sets` expand to 12 `cloud_files` flows (TP/src/dataflows/bronze/dataflowspec/bronze_ingestion_main.json:1-10).
   - Settings: Parquet, `cloudFiles.schemaEvolutionMode: addNewColumns`, CDF on, and one schema per source system (TP/src/templates/bronze_parquet_ingestion_template.json:34-60).
   - No projection happens in bronze: "faithful raw passthrough" (TP/DESIGN.md:128-135).
2. **Silver: conform and historize** (12 entities):
   - `silver_scd2_template` with 6 sets: customer, customer_phone, supplier, supplier_address, supplier_phone, part.
   - `silver_scd1_template` with 2 sets: region, nation.
   - `silver_append_template` with 2 sets: lineitem, partsupp.
   - Two standalone DQ specs:
     - `customer_address`: SCD2 + table quarantine on `nation_key IS NOT NULL`.
     - `orders`: append + table quarantine on `order_key IS NOT NULL` and `total_price >= 0` (TP/src/dataflows/silver/expectations/orders_dqe.json:2-13).
   - Every silver target has CDF and row tracking. SCD2 templates hard-code `apply_as_deletes: "cdc_operation = 'D'"` (TP/src/templates/silver_scd2_template.json:73-80).
   - Customer and supplier feeds `sequence_by effective_date`, putting SCD2 windows on the **business timeline**, which point-in-time joins need (TP/DESIGN.md:137-148; TP/GUIDE.md:255-259).
   - Why three templates? "the template engine has **no conditional logic**" (TP/DESIGN.md:267-273).
3. **Gold: star schema** (the gold pipeline is filtered with `pipeline.dataFlowGroupFilter: tpch_gold`, TP/resources/serverless/pipelines/tpch_gold_pipeline.yml:20):
   - **`dim_customer`**: the streaming-DWH pattern as a streaming table.
     - Three silver SCD2 feeds append `{customer_key, __START_AT as version_ts}` into `stg_customer_appnd_keys`.
     - An SCD2 dedupe keyed on `customer_key`, sequenced by `version_ts`, runs next.
     - Its CDF feeds `dim_customer.sql`, which does as-of joins to customer, address and phone plus nation and region, and computes `xxhash64('customer', key, __START_AT)` (TP/src/dataflows/gold/dataflowspec/dim_customer_main.json:6-158; TP/src/dataflows/gold/dml/dim_customer.sql:1-28).
   - **`dim_supplier`, `dim_part`, `dim_location`, `dim_date`**: materialized views. Supplier, part and location add a `-1` "Unknown" member via `UNION ALL` (TP/src/dataflows/gold/dml/dim_supplier.sql:19-33). `dim_date` is generated with a 1 April fiscal year (TP/DESIGN.md:3.8).
   - **`fct_order_lines`**: a streaming table fed by **SCD1 AUTO CDC keyed on (`order_key`, `line_number`)**, not a pure append, which makes re-delivery idempotent (TP/src/dataflows/gold/dataflowspec/fct_order_lines_main.json:35-46).
     - Its SQL stream-static-joins lineitem CDF to silver orders and to `live.dim_*` as-of `order_date` (TP/src/dataflows/gold/dml/fct_order_lines.sql:33-49).
   - `fct_part_supply` plus 5 aggregate MVs (TP/src/dataflows/gold/dataflowspec/facts_aggregated_main.json). The "Built by (`dataFlowType: materialized_view`)" note at TP/DESIGN.md:199 is now stale.
   - After gold: UC metric views (`CREATE VIEW ... WITH METRICS`) and an optional Genie space are created by notebook tasks, and two Lakeview dashboards are declared as native bundle resources (TP/resources/serverless/jobs/tpch_run_1_job.yml:29-50; TP/DESIGN.md:3.19-3.20).
4. **Runs** (TP/GUIDE.md:117-160):
   - **Run 1**: every pipeline with `full_refresh: true`, run in order bronze, silver, gold (TP/resources/serverless/jobs/tpch_run_1_job.yml:9-26).
   - **Run 2** (`full_refresh: false`):
     - SCD2 changes effective 1996;
     - large fact growth;
     - schema evolution (`loyalty_tier` appears in bronze only);
     - a late-arriving part `9000001` that resolves to `part_sk = -1`;
     - quarantine rows.
   - **Run 3**:
     - supplier update (1997) and delete (a tombstone closes the version);
     - a backdated 1994 address correction slotting between 1992 and 1996 while 1996 stays current;
     - the late part arrives, but the Run-2 fact keeps `-1` until a full refresh (TP/DESIGN.md:308-327).
5. **Gotchas the sample documents** (TP/GUIDE.md:245-266):
   - Reference in-pipeline datasets as `live.<table>`.
   - Append-only facts have no `__START_AT`.
   - Use a business `effective_date`, not processing time, for point-in-time.
   - Metric views allow only star joins off `source`.
   - Keep staging types identical across batches, or schema-on-read bronze rescues values to NULL.

**My additional observations:**
- SUSPECTED: `JOIN {silver_schema}.orders` is an **inner** stream-static join (TP/src/dataflows/gold/dml/fct_order_lines.sql:35). A line item that arrives before its order header is dropped permanently, because stream-static joins do not retry (inferred from D/build/patterns/stream-static-basic.rst:92). The demo is safe only because silver orders and lineitem land in the same run.
- CONFIRMED: TP/DESIGN.md:263-265 describes a template value `"{bronze_${param.sourceSystem}_schema}"` and links `docs/source/feature_templates.rst`. The current template uses `${param.database}` and never uses its declared `sourceSystem` parameter (TP/src/templates/bronze_parquet_ingestion_template.json:8-11,29-63), and the link target no longer exists.

---

## 5. Operating model: DABs, environments and upgrades

**Two bundle types** (D/architecture/index.rst:45-60):
- The **Framework Bundle** contains the engine, default config, JSON schemas and `databricks.yml`. It deploys to `/Workspace/Users/<owner>/.bundle/lakeflow_framework/<target>/<version>/files/src` (databricks.yml:24).
- **Pipeline Bundles** hold `src/dataflows` (specs, schemas, `dml`, expectations, `python_functions`), `src/pipeline_configs` (global, substitutions, secrets), optional `src/python`, `src/libraries` and `src/init/{pre,post}`, and `resources/*.yml` pipeline and job definitions (D/build/bundle-structure.rst:58-109).
- Deploy order is framework first, then pipelines (D/deploy/before-you-deploy.rst:9-17).
- Ownership (D/deploy/before-you-deploy.rst:29-53):
  - Framework: platform CI/CD deploying as an owning service principal in every environment.
  - Pipelines: developers deploy locally in dev; CI/CD deploys as a service principal above dev.

**Pipeline resource wiring** (D/build/bundle-steps.rst:311-328):
- Every pipeline's library is the framework notebook `${var.framework_source_path}/dlt_pipeline`.
- `configuration:` passes `bundle.sourcePath`, `framework.sourcePath`, `bundle.target`, `pipeline.layer`, `logicalEnv`, and optional filters:
  - `pipeline.dataFlowIdFilter`
  - `pipeline.dataFlowGroupFilter`
  - `pipeline.flowGroupIdFilter`
  - `pipeline.fileFilter`
  - `pipeline.targetTableFilter` (the docs misspell it; see R3)
- Other options: `pipeline.ignoreValidationErrors` (D/features/metadata/validation.rst:61-94), `logLevel`, and `root_path` for the Pipeline Editor UI (D/features/authoring/ui-integration.rst:18-45).
- The entry notebook runs `%pip install -r ../requirements.txt` on every update (src/dlt_pipeline.ipynb:9).

**Environments:**
- **DAB targets.** `bundle.target` becomes the reserved token `workspace_env`, which selects the file `<target>_substitutions.json` (and `<target>_secrets.json`) in both the framework config directory and `src/pipeline_configs` (ENG/dlt_pipeline_builder.py:159,326-339).
- **Substitution precedence.** "Global substitutions and Pipeline substitutions are merged, with Pipeline substitutions taking precedence" (D/features/metadata/substitutions.rst:55). The code confirms it: `merge_dicts_recursively(pipeline_subs, framework_subs)`, where the first argument wins (ENG/substitution_manager.py:71-76; ENG/utility.py:500-511).
- **Logical environments** add a suffix such as `_jd` to pipeline and UC names, so many developers can share one workspace (D/features/environments/logical-environments.rst:17-19). Pass it via `BUNDLE_VAR_logical_env` or `--var`, then flow it into `logicalEnv` and the `{logical_env}` token.
- **Secrets** live in the `<target>_secrets.json` alias map `{alias: {scope, key, exceptionEnabled?}}` (SCH/secrets.json) and are referenced as `${secret.alias}`, including embedded in larger strings (fix #147).
  - Values are "not cached" and appear as `[REDACTED]` in logs (D/features/configuration/secrets-management.rst:28-33).
  - The doc points at `src/pipeline_config/` (singular), but the folder is `src/pipeline_configs/` (D/features/configuration/secrets-management.rst:43-44 vs ENG/constants.py:165).
- **Configuration layering:**
  1. Framework defaults: `ENG/config/default/global.json`, operational metadata, spec mappings.
  2. `src/local/config` sparse deep-merge overlay (ADR-0006).
  3. Pipeline `src/pipeline_configs/global.json` for keys that allow it. Pipeline settings win "where settings can be configured in both" (D/architecture/index.rst:95-99).

  Mandatory table properties beat per-table properties (section 2.6).

**Local sparse-config overlay (ADR-0006).** `src/local/` is the fork-safe, customer-owned area: "never touched by upstream framework upgrades or template merges" (src/local/README.md:5).
- `local/config/*.json` files are deep-merged over the defaults:
  - dicts merge recursively;
  - lists and scalars are replaced wholesale;
  - directory configs such as `dataflow_spec_mapping/` are replaced entirely (ADR/0006-local-config-sparse-overlay.md:75-92).
- `local/libraries`, `local/python` and `local/init/{pre,post}` extend all pipelines. Framework-level init scripts run before pipeline-level ones, in sorted order, skipping files that start with `_`, via `runpy` (src/local/init/pre/README.md:6-13).
- Caveat: substitutions and secrets files are **not** covered by the overlay (ADR/0006-local-config-sparse-overlay.md:122-124).

**How a customer upgrades without losing customizations:**
1. Fork the upstream repository and promote upstream releases **manually** after platform review (D/deploy/ci-cd.rst:84-85).
2. Never edit `lakeflow_framework/config/default/`. Put org changes in `src/local/` (config, libraries, python, init).
3. Release by deploying twice, to `current` and to `<version>` (for example `1.2.3`). This keeps a rollback copy (D/features/environments/versioning-framework.rst:23-27; D/deploy/ci-cd.rst:86-98).
4. Pipelines normally point at `current`. For phased rollouts, pin some bundles' `framework_source_path` to a version. On regression, repoint to the last good version with no framework redeploy (D/deploy/ci-cd.rst:146-161).
5. Keep old specs running with `dataFlowVersion` plus spec mappings (D/features/environments/versioning-dataflow-specs.rst). Move to nodespec with `scripts/migrate_to_nodespec.py`, which pins legacy flow names so checkpoints survive (ADR/0010-unified-nodespec-dataflow-spec.md:109-117).
6. Watch deprecation windows. `extensions/`, `config/override/` and the flat `src/*.py` import shims are removed at v1.0.0 (ADR/0002-extensions-deprecation.md:27; ADR/0006-local-config-sparse-overlay.md:99-105; ADR/0008-lakeflow-framework-package.md:124-129).

(inferred) The catch is that `current` is a **mutable pointer**: promoting a release changes every unpinned pipeline on its next update. Treat a framework promotion as a fleet-wide change with a canary set of pinned pipelines.

---

## 6. ADR digest (0001-0010)

| ADR | Decision | Context | Alternatives rejected | Lesson for framework designers |
|---|---|---|---|---|
| 0001 Canonical `src/` layout | Pipeline bundles get `src/libraries` (wheels plus sys.path), `src/python` (spec-referenced code), `src/init/pre|post` (lifecycle scripts). The framework's custom code goes only under `src/local/`. Lifecycle hooks are called "init scripts" (ADR/0001-bundle-src-layout.md:23-54) | One catch-all `extensions/` mixed importable modules with lifecycle scripts and had no fork-safe customer area (ADR/0001-bundle-src-layout.md:9-21) | Keeping `extensions/`; the unreleased `extensions/libraries` variant (implicit) | Give separate concerns (install-time libraries, spec-referenced code, lifecycle hooks, customer overrides) separate, documented homes. Name the "local" area after known conventions (`git config --local`, `local_settings.py`) |
| 0002 `extensions/` deprecation | Warn in v0.13.0, remove at v1.0.0. Drop the never-released path immediately (ADR/0002-extensions-deprecation.md:25-28) | Only released behavior carries a backward-compatibility obligation | — | Deprecate with warnings plus mechanical migration. The ADR contradicts itself: "removed in the first minor version after" (ADR/0002-extensions-deprecation.md:30) vs removal at v1.0.0 (ADR/0002-extensions-deprecation.md:27). State one policy |
| 0003 Pluggable logger | `logger.json` specifies a factory `(dbutils, spark, **kwargs)`. The resolved level is injected; failures fall back to the default logger and **never crash the pipeline** (ADR/0003-pluggable-logger-architecture.md:23,44-59) | Customers need Splunk, Datadog or App Insights without patching the framework | Hard-coded stdout logger; code-level integration (implicit) | Make observability integrations config-only and fail-safe, and define a behavioral contract (methods, `exc_info`, lazy level checks) |
| 0004 `mirror_to_stdout` defaults to false | With a custom logger, the default stdout logger is silenced; `CompositeLogger` provides opt-in dual output (ADR/0004-mirror-to-stdout-default.md:32-50) | Duplicate mixed-format lines in the Logs UI and wasted ingestion quota | Always emit both | Choose defaults that avoid duplicates, and call out that the default is a breaking change (ADR/0004-mirror-to-stdout-default.md:66-68) |
| 0005 `sys.path` registration decoupled from the logger | `register_bundle_sys_paths(logger=None)` runs silently before the logger resolves (ADR/0005-syspath-registration-decoupled-from-logger.md:33-47) | Circular dependency: the logger module may live on paths that need a logger to register (ADR/0005-syspath-registration-decoupled-from-logger.md:20-27) | Passing a bare `logging.getLogger`, which forced plain-text output | Make bootstrap code dependency-free (optional collaborators) so initialization order cannot deadlock |
| 0006 Sparse local config overlay | `src/local/config/*` deep-merges over defaults; override detection moves to callers; `config/override/` is deprecated (ADR/0006-local-config-sparse-overlay.md:36-44,75-83) | Whole-tree copies went silently stale on upgrade, and one `logger.json` override accidentally switched on the whole override tree (ADR/0006-local-config-sparse-overlay.md:15-26) | Whole-tree override | Upgrade-safe customization means **sparse overlays plus deep merge**, with loaders kept pure. Document merge semantics (lists replace) |
| 0007 Scripted versioned docs | Build scripts publish `main` as `current` plus selected tags with a shared `versions.json`; historical tags build with main's `conf.py` (ADR/0007-scripted-versioned-docs-and-ui-scope.md:23-49) | Need deterministic, reproducible versioned docs on GitHub Pages | `sphinx-multiversion` "proved brittle" (ADR/0007-scripted-versioned-docs-and-ui-scope.md:18) | Keep docs builds scripted and testable, with minimal theme customization |
| 0008 pip-installable package | A `src/lakeflow_framework/` package with bundled config and schemas; `VERSION` is the single source of truth; compat shims for bare imports until v1.0.0 (ADR/0008-lakeflow-framework-package.md:33-129) | Bare module names could shadow customer modules; no wheel distribution; data files outside any package (ADR/0008-lakeflow-framework-package.md:17-30) | "Copy the source" distribution only | Namespace your package early. Note: `lakeflow-framework` is **not** on public PyPI (404 on 2026-09-29), so "pip install" implies a self-built wheel (R12) |
| 0009 Workspace-files-first resolution | Resolution order: workspace files `{framework_path}/lakeflow_framework/config/default`, then `importlib.resources`, then the local overlay (ADR/0009-strategy-b-workspace-files-first-resolver.md:52-83) | Flat-deploy and wheel installs coexist | A: package-first, which silently changes flat-deploy behavior; C: explicit-only, boilerplate at 15+ call sites (ADR/0009-strategy-b-workspace-files-first-resolver.md:29-50) | "Explicit wins": never let a new distribution channel silently override what customers configured. Doc nit: the overlay path shown as `{framework_path}/src/local/config` (ADR/0009-strategy-b-workspace-files-first-resolver.md:80) is really `{framework_path}/local/config` (ENG/constants.py:78) |
| 0010 Unified `nodespec` | One node-graph spec (source, transformation, target); `sources` belongs to targets; flow names derived or pinned; ST and MV allowed in one spec; inline SQL/Python sources warned; MV inline `source_view` removed (breaking) (ADR/0010-unified-nodespec-dataflow-spec.md:61-117,284-298) | Three formats to learn, leaking internals, deep nesting, implicit topology, ST/MV split (ADR/0010-unified-nodespec-dataflow-spec.md:23-52) | Keeping three formats; a primary/secondary target flag (ADR/0010-unified-nodespec-dataflow-spec.md:337) | Model the user's mental model (a node graph), **lower** it onto the existing engine (no capability loss), and protect streaming state (pinned flow names) when migrating |

---

## 7. CHANGELOG themes: what breaks in practice

`CHANGELOG.md` is empty (0 bytes, CONFIRMED), even though the docs advise "Keep a changelog" (D/features/environments/versioning-framework.rst:113). The themes below come from the public history (84 commits). Where a hash is not otherwise marked, the commit's own body describes the bug.

| Theme | Real incidents (commit, PR) | What it teaches about SDP pipelines |
|---|---|---|
| **Identifier qualification** | Quarantine name double-qualified as `main.schema.main.schema.orders_quarantine`, failing with "supports at most three parts" (1b8170a, #110). The fix regressed: an unqualified quarantine name lost its `database` and "dropped ... into the pipeline default schema" (0e8d0ca, #153). CDC snapshot table identifier parsing (c504223, #49). Table migration config not resolving the logical env (41a4aa8, #33) | Catalog/schema/table assembly is the most fragile string logic in a UC pipeline. Unit-test all four combinations (qualified or not, with or without database) |
| **Validation that silently did not run** | nodespec specs were **never schema-validated at runtime**: a wrong path plus a schema with only `$defs` meant `os.path.exists` fell through to `errors = []` (fca1b4e, #142/#135). The validator rejected template-form specs (c146bfb, #51). The MV schema lacked `clusterByAuto` (8404904, #6). My finding: Draft 7 ignores `dependentSchemas` (section 2.9) | "No errors" is not "validated". Fail closed when a schema is missing, and add a test that an **invalid** spec is rejected |
| **Spark SQL semantics / ANSI** | `where("is_quarantined = 1")` on a boolean was not ANSI-safe; rules containing `OR` were not parenthesized (deece3d, #141) | Serverless/new runtimes tighten SQL typing. Compare booleans as booleans and parenthesize generated predicates |
| **Serverless and environment restrictions** | `dbutils.fs.ls()` threw `Py4JSecurityException` on restricted serverless, so a Spark `binaryFile` fallback was added; parquet directories were counted as multiple snapshot versions (bb91ba6, #83). `workspace.host` was mandatory but empty in some DAB targets, failing every pipeline (24b58d7, #145/#138) | Code written on classic clusters breaks on serverless/Unity Catalog. Avoid driver-side file APIs, and do not make unused configuration mandatory |
| **Packaging and supply chain** | `pyyaml` missing from wheel dependencies, so YAML failed in clean installs (d910588, #143). CI moved to JFrog OIDC (fa0b8f1, #114) and skips fork PRs (5b78540, #146) | Test the wheel in a clean environment. Security controls can remove CI coverage for external contributors |
| **Concurrency** | `JSONValidator` shared a `RefResolver` across threads, giving a `KeyError` on `definitions/views` during parallel validation (eb7e96e, #95) | Builder parallelization (D/features/configuration/builder-parallelization.rst) needs thread-local state for non-thread-safe libraries |
| **Plain Python in rarely-run paths** | `list(set(x.copy().extend(*y)))`: `extend` returns `None`, so every table-migration SCD2 spec with `except_column_list` raised `TypeError` (f1eea62, #144/#137) | Migration and backfill paths run once per table, so they need unit tests more than hot paths do |
| **Determinism vs operational metadata** | Operational metadata had to be disabled on MVs and periodic snapshots (8982585, #21); `incremental_strict` forbids `current_timestamp()` (D/features/platform/materialized-views.rst:235) | Audit columns built from `current_timestamp()` break snapshot diffing and incremental MV refresh |
| **Streaming semantics** | `once` append flows need a forced batch read (f6fe798, #22); quarantine exclude-columns for CDC tables (5146e69, #32) | Once-flows and CDC column handling are where declarative wrappers leak |
| **Secrets and substitutions** | `${secret.*}` only worked as a whole field, not inside a JAAS string (dab8766, #147). Sample catalog rewrites broke on underscored names and whitespace (deaab39, #131; comments at samples/common.sh:403-406,504-508) | Token systems need embedded interpolation plus redaction; regex-based config rewriting is brittle |
| **Templates and path resolution** | Typed template defaults (601af3e, #130); fallback to `templates/dml` and `templates/schemas` (8850a38, #151) | Reuse mechanisms grow a resolution-order policy. Document it (D/features/metadata/templates.rst "Search Priority") |
| **Portability of tooling** | `sed -i ''` (macOS) replaced by `perl -i -pe` for Linux/WSL (0d2b693, #44) | Deploy scripts are product code |

---

## 8. Operations, monitoring and debugging

**What the docs provide.** The Operations and Monitoring pages are stubs: "Under Construction" (D/operations.rst:6; D/monitoring_and_observability.rst:6). Nothing in docs, samples or skills queries the SDP **event log** or **system tables**; I grepped for `event_log` and `system.` (CONFIRMED absent). The TPCH "Pipeline Health & Governance" dashboard is data-level only: unknown-member counts, SCD2 depth and return rate, with no run, flow or expectation metrics (TP/src/dashboards/pipeline_health.lvdash.json datasets).

**Observability the framework does ship:**
- **Logs.** The logger is `lakeflowframework`, and `logLevel` is set in pipeline configuration. Pluggable loggers and a `mirror_to_stdout` option exist (D/features/configuration/logging.rst:14-66,439-461). To view: open the pipeline, then the Update, then Logs, then STDOUT (D/features/configuration/logging.rst:554-567). Non-owners need `spark.databricks.acl.needAdminPermissionToViewLogs: "false"` (D/features/configuration/logging.rst:578). A custom logger failure logs `Failed to initialize custom logger:` and falls back to the default (D/features/configuration/logging.rst:481-503).
- **Operational metadata columns.** They carry the pipeline update id and start time on every row, which lets you join data back to runs (section 2.6).
- **Quarantine.** `<target>_quarantine` tables or `is_quarantined` flags act as DQ triage queues.
- **Init-time validation.** All spec files are validated and a combined error list fails the pipeline (D/architecture/index.rst:246-249). `pipeline.ignoreValidationErrors` bypasses this in dev (D/features/metadata/validation.rst:61-94).

**Debugging a failing flow: a practical playbook** (repository evidence plus (platform) steps):
1. **Classify the failure phase.**
   - Initialization (spec load/validation, Python import, `ValueError: Pipeline settings error`).
   - Graph analysis (unresolved table or column).
   - Flow execution (expectation failure, CDC or type errors).
   - Silent data issue.
2. **Initialization failures:**
   - Validate locally: `python scripts/validate_dataflows.py <bundle> --no-mapping` (scripts/README.md:11-27).
   - Check suffixes (`*_main.json`) and format settings (D/features/metadata/spec-format.rst:115-162).
   - Check filter keys. A misspelled key is silently ignored and the pipeline runs **everything** (R3).
   - Check unresolved `{tokens}`, which are left verbatim (R4).
   - For legacy specs, remember that schema validation skips most detail checks (section 2.9).
3. **Analysis failures.** `UNRESOLVED_COLUMN` means spec keys or SQL do not match real columns (SK/docs/tested-medallion-example.md:139). In-pipeline references need `live.` (TP/GUIDE.md:245-250).
4. **Runtime failures:**
   - `expect_or_fail` rules.
   - ANSI type errors, for example boolean vs int (R9).
   - SCD2 keys with duplicate sequence values; for example fan-out joins produce them (R7).
   - Snapshot `datetime_format` parse errors (Python `strptime`).
   - Serverless file-listing restrictions (#83).
5. **Data-level symptoms:**
   - Quarantine growth.
   - `*_sk = -1` counts, meaning late dimensions.
   - Unexpected SCD2 version explosions from multi-source late arrivals (D/build/patterns/multi-source-streaming.rst:117).
   - Stale lookups in stream-static joins (D/build/patterns/stream-static-basic.rst:92).
6. **(platform) Use the event log.** This is missing from the repository. Query `event_log(TABLE(<catalog>.<schema>.<table>))` or `event_log('<pipeline_id>')`:
   - `event_type = 'flow_progress'` gives per-flow status, row counts and backlog;
   - `details:flow_progress.data_quality.expectations` gives passed and failed records per expectation;
   - `event_type = 'update_progress'` gives update state;
   - errors appear in `error` and `message`.

   Join to the operational metadata `pipeline_update_id` for row-level lineage (inferred).
7. **State problems:**
   - A renamed flow means a new checkpoint (D/features/platform/multi-source-streaming.rst:48-49). Pin flow names.
   - After a full refresh upstream, downstream CDF readers may need `starting_version_from_dlt_setup` (D/build/spec-reference/source-details.rst:112-114; D/build/patterns/cdc-stream-from-snapshot.rst:87).

---

## 9. AI skills and guidance

**What ships.** One Agent Skill, **`dataflow-spec-builder`**, lives in `skills/dataflowspec_builder/`. It is published on the docs site as an overview only, through symlinks (docs/source/ai-skills/dataflowspec-builder/index.md → `SK/README.md`; D/ai-skills/index.rst:4-16). Contents:
- `SKILL.md`: frontmatter (`name`, `description`), when to use, **when NOT to use** (native DLT requests; SK/SKILL.md:12-26), parameters, an 11-step workflow (SK/SKILL.md:41-55), a feature reference, pipeline YAML and `databricks.yml` templates, patterns, deploy commands.
- `assets/`: spec, pipeline and substitution templates, plus Python source/transform/sink stubs.
- `examples/`: an "energy" domain for bronze, silver, gold and templates.
- `references/`: patterns guide and field reference.
- `scripts/`: `scaffold_lakeflow_bundle.py`, `validate_specs.py`, deploy scripts.
- `docs/`: getting started, 30+ example prompts, architecture, a "tested medallion example".

**How users are told to work with AI:**
- Install the skill folder into Cursor (`~/.cursor/skills`), Claude Code (`~/.claude/skills`) or Genie Code (`/Workspace/Users/<you>/.assistant/skills/`) (SK/docs/getting-started.md).
- Always say "Data Flow Spec" or "dataflow-spec-builder" so the assistant does not produce native `@dlt.table` code (SK/README.md:82; SK/docs/example-prompts.md:5; SK/docs/getting-started.md:114-120).
- Verify the skill is loaded by asking "What Data Flow Spec patterns are available?".
- Example prompt (SK/docs/example-prompts.md:52-60): "Create a bronze Data Flow Spec for the raw_customers table with SCD Type 2. Track history on customer_name, rate_plan, and has_solar columns. Use account_id as the key and signup_date as the sequence column."
- The docs also give a generic LLM prompt for converting a schema to StructType JSON (D/features/metadata/schema-management.rst:81-89).
- JSON Schema IntelliSense in VS Code is the non-AI guardrail (D/features/authoring/auto-complete.rst).

**AI-stewardship findings (all CONFIRMED):**
- **Outdated target format.** The skill generates only legacy formats: 26 `dataFlowType` occurrences and **zero** nodespec. It pins "Data Flow Spec Framework (v0.4.0)" while the repository is v0.24.1 (SK/SKILL.md:8).
- **Wrong reference material.**
  - Snapshot example with `"versionType": "datetime"` (the schema rejects it) and `"datetimeFormat": "yyyyMMdd"` (the engine uses `strptime`), plus a prompt that teaches the same (SK/SKILL.md:412-413; SK/docs/example-prompts.md:67; ENG/dataflow/cdc_snapshot.py:585).
  - Flag mode described as adding "a `_quarantine` boolean column"; the real column is `is_quarantined` (SK/SKILL.md:490; ENG/constants.py:196).
  - An `expect_or_fail` rule named `unique_key` that only checks NOT NULL (SK/SKILL.md:470). Row-level expectations cannot enforce uniqueness.
- **The skill's own validator is wrong for today's specs.** It is hand-rolled (legacy camelCase keys, `parameterSets` only; SK/scripts/validate_specs.py:24,46). Run on `samples/pattern_samples`, it reports **64 errors on 16 valid nodespec specs**. On legacy samples it produces false positives for historical-snapshot specs, which must omit source fields (SCH/spec_standard.json:36-60).
- **Compounding risk.** AI-generated **legacy** specs with mistyped nested keys pass even the official schema validator (section 2.9) and fail only at run time.

**Recommended human-in-the-loop workflow (inferred):**
1. Prompt with explicit constraints: "nodespec, snake_case, `scd_type` as a string, strftime datetime formats, pin flow names, catalog/schema via `{tokens}`".
2. Validate with the framework's `scripts/validate_dataflows.py --no-mapping`, not the skill's script.
3. Diff against a nearest sample in `samples/`.
4. Deploy to dev with a logical env and run a validation-only update (platform).
5. Review the generated graph, expectations and quarantine counts before promotion.

---

## 10. Testing strategy

**Layers** (tests/README.md:22-67; pytest.ini:1-7):

| Layer | Location | Marker | Depends on |
|---|---|---|---|
| Unit | `tests/unit/` (mirrors the package) | none | `tests/fixtures/` only; `pipeline_context` fixture mocks the singletons |
| Golden and contract | `tests/unit/test_golden_specs.py`, `tests/unit/test_schema_contracts.py` | none | Expected template expansion and legacy mapping output (tests/fixtures/golden) |
| Integration | `tests/integration/` | `integration` | Full `samples/` checkout |
| Spark / BDD | — | `spark`, `bdd` | "Reserved for future", so no tests exist |

Conventions: "No DLT mocks: tests that need `@dp.table` belong in samples/E2E" (tests/README.md:75); use Python 3.12 (tests/README.md:20). The top-level `fixtures/` folder is only a placeholder (fixtures/.gitkeep holds a pandas CSV-loading snippet). The real fixtures live in `tests/fixtures/{specs,bundles,golden,schemas}`.

**Integration tests:**
- `test_validate_dataflows.py` validates every `*_main.json` in the three JSON bundles.
- `test_feature_samples_spec_builder.py` smoke-builds specs, but with `ignore_validation_errors=True` (tests/integration/test_feature_samples_spec_builder.py:26,59).

**Samples as end-to-end tests:**
- `samples/deploy_and_test.sh` deploys feature and pattern samples, runs `feature_samples_run_job`, then pattern runs 1-4 **sequentially**, stopping at the first failed job (samples/deploy_and_test.sh:66-145).
- `samples/deploy_tpch_and_test.sh` runs the TPCH setup, then runs 1-3 (samples/deploy_tpch_and_test.sh:154-170).
- The pass criterion is **job success only**: no row-count or data assertions (CONFIRMED by reading both scripts).
- The pattern jobs exercise incremental behavior: Run 1 uses `full_refresh: true`, Runs 2-4 use `false` (samples/pattern_samples/resources/serverless/jobs/pattern_samples_run_2_job.yml:17).
- The feature-samples job runs **every pipeline with `full_refresh: true`**, so feature samples never test incremental behavior (samples/feature_samples/resources/serverless/jobs/feature_samples_run_job.yml:25-72).

**CI** (.github/workflows/ci.yml): unit tests on same-repo PRs and pushes; docs spelling; Sphinx HTML with a **19-warning budget** (.github/workflows/ci.yml:151-152); `validate_dataflows.py samples/` when `samples/**` changes.

**Gaps (CONFIRMED):**
- Integration tests never run in CI (`-m "not integration and not spark"`, .github/workflows/ci.yml:92).
- A schema change under `src/.../schemas` does not trigger sample validation (the path filter is `samples/**`, .github/workflows/ci.yml:62-63,157).
- YAML specs are never schema-validated: the validator globs `*_main.json` (scripts/validate_dataflows.py:93) and the integration bundles exclude `yaml_sample` (tests/integration/conftest.py:17-22).
- Template bodies are only shape-checked in CI (scripts/validate_dataflows.py:116-121).
- The CI validator re-implements mapping logic with no `delete` operation (scripts/validate_dataflows.py:261-296), so it can drift from `ENG/dataflow_spec_builder/spec_mapper.py`.
- Fork PRs skip everything (.github/workflows/ci.yml:40,67).
- `pipeline_bundle_template/tests/main_test.py:1` and `samples/yaml_sample/tests/main_test.py:1` import a non-existent `bronze_sample.main` (a template leftover).

**What I would add (inferred):**
- Post-run assertions in the end-to-end scripts, for example expected SCD2 row counts per day and quarantine counts.
- An event-log check that expectation-failure totals match fixtures.
- Nightly `pytest -m integration`.
- A CI trigger on `src/lakeflow_framework/schemas/**`.
- A negative-validation test suite.

---

## 11. How SDP executes under the hood (as far as the docs explain it)

**Streaming tables vs materialized views.**
- A streaming table is fed by one or more flows. Append flows, or AUTO CDC flows, each process only new input and keep their own **checkpoint**, identified by the flow name (D/features/platform/multi-source-streaming.rst:40-53).
- A materialized view is a declarative query result that SDP refreshes, **incrementally** when the query and lineage allow. Incremental refresh needs row tracking on sources (D/features/platform/materialized-views.rst:21-37; TP/DESIGN.md:238-245).
- `refresh_policy` is `auto`, `incremental`, `incremental_strict` or `full`. It is Beta and requires DBR 17.3+ (D/features/platform/materialized-views.rst:232-235). (platform) `incremental_strict` errors rather than silently recomputing.
- Guidance: MVs are "generally the first choice" for gold unless you need streaming-first latency (D/build/patterns/gold-materialized-views.rst:18-20).

**Checkpoints and evolution.**
- Adding or removing flow groups and flows does not require a full refresh (D/architecture/index.rst:413).
- Renaming a flow creates a new checkpoint and forces a refresh (D/build/spec-reference/nodespec.rst:398-400). That is why nodespec supports pinned `{view, flow}` names.

**Full refresh vs incremental.**
- Jobs choose per task (`full_refresh: true|false`, as in TPCH Run 1 vs Runs 2-3).
- Consequences the docs call out:
  - Adding operational-metadata columns to existing tables requires a full refresh unless schema evolution is allowed (D/features/configuration/operational-metadata.rst:115).
  - Late dimensions only re-resolve in append facts after a full refresh (TP/DESIGN.md:319-327).
  - After an upstream reset, read CDF from the last "setup" version (`startingVersionFromDLTSetup`; D/build/spec-reference/source-details.rst:112-114).
  - Moving a legacy-publishing-mode pipeline to default publishing **drops and recreates tables and reprocesses** (D/features/platform/target-catalog-schema.rst:30-34).

**AUTO CDC semantics:**
- `keys` identify the row. `sequence_by` orders events, so out-of-order arrivals are resolved by sequence value, not arrival time (D/build/spec-reference/cdc.rst:38).
- SCD1 overwrites. SCD2 keeps versions with `__START_AT`/`__END_AT`, derived from sequence values (inferred from TP/README.md:120-124 and TP/DESIGN.md:299-306).
  - This makes a **backdated** event (the TPCH 1994 correction arriving in Run 3) slot into history.
  - Using a business date as `sequence_by` makes SCD2 windows business-time windows (TP/GUIDE.md:255-259).
- `track_history_*` limits which column changes open new versions.
- `ignore_null_updates` merges partial rows. This is the mechanism behind multi-source coalescing (D/build/spec-reference/cdc.rst:50).
- Deletes:
  - SCD1 keeps tombstones hidden by a view (D/features/platform/soft-deletes.rst:19).
  - SCD2 closes the version.
  - To **propagate physical deletes downstream through CDF**, the staging table must be SCD1 (D/build/patterns/cdc-stream-from-snapshot.rst:49).
- The framework defaults `spark.databricks.sql.streamingTable.cdf.applyChanges.returnPhysicalCdf: true` (ENG/config/default/global.json:7). No doc explains it. (inferred) It makes CDF reads of AUTO CDC targets return the physical changes that downstream CDF-chained patterns rely on.
- Snapshot CDC:
  - periodic: ingestion time is the version;
  - historical: versions are parsed from paths or version columns and processed in order (D/features/platform/cdc.rst:30-45).
  - Doc staleness: "historical ... can only be used in standard data flow types" (D/features/platform/cdc.rst:43; D/build/spec-reference/cdc.rst:78). Yet `legacy_samples/.../historical_snapshot_files_flow_main.json` is a `flow` spec with a historical-snapshot staging table (CONFIRMED).

**Expectations metrics:**
- `expect` keeps and counts; `expect_or_drop` drops and counts; `expect_or_fail` fails the update (D/features/data-quality/expectations.rst:72-74).
- The framework's flag mode downgrades every rule to `expect` (warn), so bad rows stay in the table and are only counted.
- (platform) Counts are emitted per flow in the event log (`flow_progress.data_quality.expectations`) and shown in the pipeline UI. The repository has no queries or dashboards for them (section 8).

**Serverless vs classic:**
- Every sample ships parallel `resources/serverless` (`serverless: true`) and `resources/classic` (`clusters: [${var.pipeline_cluster_config}]` with `mode: ENHANCED` autoscaling) trees. The deploy scripts copy one tree into `scratch/resources` (samples/common.sh:252-272; TP/databricks.yml:40-59).
- Serverless is the default (samples/common.sh:10).
- Serverless-specific pitfalls found in history: restricted `dbutils.fs.ls` (#83) and ANSI typing (#141).
- (inferred) The classic TPCH job cluster pins AWS-only `i3.xlarge` (TP/databricks.yml:55).

---

## 12. How to explain it

**(a) To a customer executive (about 30 seconds).** "Today every pipeline is hand-built, so quality depends on who wrote it and changes are slow. The Lakeflow Framework turns pipelines into reviewed configuration on top of Databricks' managed declarative pipelines.
- New sources become a short spec instead of a coding project.
- Data-quality rules and quarantine, audit columns, history tracking and table standards are applied the same way everywhere.
- The same definitions promote from dev to prod automatically.

You get faster delivery and consistent governance. The trade-offs: it is open-source code your platform team owns (no Databricks support SLA), and upgrades need a release process."

**(b) To a customer data engineer.** "You write a node graph: sources, then SQL or Python transforms, then targets.
- Each target is a streaming table or an MV.
- CDC is `cdc_settings` (keys, `sequence_by`, SCD1 or SCD2, deletes). Expectations and quarantine sit on the target.
- At pipeline start, the framework validates everything and declares the same SDP objects you would write by hand: append or AUTO CDC flows, expectations, MVs. It also applies tokens per environment.

Keep flow names stable (checkpoints). Use `live.` for in-pipeline reads. Pick the pattern that fits your join semantics: multi-source, stream-static, or the streaming DWH. Validate with `scripts/validate_dataflows.py`. Your custom code goes in `src/python`, and org-wide overrides go in the framework's `src/local`."

**(c) To an internal stakeholder (field or product).** "LFF is a solutions-accelerator layer over SDP and DABs that customers adopt to scale SDP across teams.
- Value: standardization, a Framework/Pipeline Bundle split for platform-team control, and an upgrade story (sparse `src/local` overlays plus version pinning).
- Watch-outs I found:
  - Operations docs are stubs.
  - Legacy-spec validation is shallow (a Draft 7 `dependentSchemas` gap).
  - The AI skill targets outdated legacy formats.
  - The docs promise `pip install` but there is no public PyPI package.
  - nodespec is only weeks out of beta.
- It is a good fit for platform-led customers with many similar flows, and a poor fit where teams need bespoke streaming logic or vendor support."

**How it scales (for any audience):**
- **Horizontal:** many pipelines per bundle, filtered by group. Decompose big pipelines into staging and final pipelines (D/build/patterns/scaling-decomposing-pipelines.rst:15-99), and respect pipeline and concurrency limits (D/build/patterns/scaling-decomposing-pipelines.rst:8-13).
- **Initialization cost** grows with the number of specs in the bundle, because **all** files are read and validated on every update (D/architecture/index.rst:246-252). Spec building is parallelized across driver cores minus one (D/features/configuration/builder-parallelization.rst).
- **Data volume** is SDP's problem: incremental flows and incremental MV refresh. The TPCH sample demonstrates about 30M line items (TP/README.md:6).

---

## 13. Interview-prep questions with crisp answers

1. **When would you NOT use SDP or a metadata-driven framework?**
   - No framework: small estate, highly bespoke logic, or streaming aggregations and windows, which the patterns exclude.
   - Not SDP: when you need imperative control of each write (complex multi-table transactions), sub-second latency, or non-Delta targets beyond the sinks (inferred).
   - Not LFF specifically: when the customer needs vendor support (README.md:68), or cannot own framework releases and the `current`-pointer blast radius.
2. **How do you handle late or out-of-order CDC events?**
   - Choose the right `sequence_by`. AUTO CDC orders per key by that column, not by arrival (D/build/spec-reference/cdc.rst:38).
   - For SCD2, a late event with an older sequence is inserted into history and newer versions stay current. TPCH's backdated 1994 row lands between the 1992 and 1996 versions because silver sequences by the business `effective_date` (TP/GUIDE.md:153-157).
   - Across multiple sources, expect extra SCD2 versions (D/build/patterns/multi-source-streaming.rst:117). For late dimensions in facts, use an unknown member (`-1`) and schedule a full refresh (TP/DESIGN.md:308-327).
3. **How does SCD2 work under the hood?**
   - The spec's `cdc_settings` with `scd_type: "2"` becomes an AUTO CDC (`apply_changes`) flow into a streaming table.
   - Per key, SDP keeps rows with `__START_AT`/`__END_AT` taken from `sequence_by`. A new version is opened when tracked columns change (`track_history_*`); `except_column_list` columns are not stored.
   - `apply_as_deletes` closes the open version.
   - Out-of-order input is resolved by sequence. The framework lowers any target with CDC to a `merge` flow (D/build/spec-reference/nodespec.rst:535-537).
4. **How do you backfill?** Options, by case:
   - A historical load into an existing streaming table: a `once: true` append flow from a batch source with a pinned flow name (FS/append_view_once_flow_main.json:18-31).
   - Adopting an existing table: `table_migration`, a one-time copy after which sources resume at baseline + 1 (D/features/migrations/table-migration.rst:99-165).
   - Historical snapshot files: `cdc_snapshot_settings.snapshot_type: historical`, which processes all versions in order.
   - Recomputing derived data: a task-level `full_refresh`.
   - Keep flow names stable so backfills do not reset other flows.
5. **Streaming table or MV? How does the spec decide?** `table_type` (`st` by default, or `mv`). Streaming tables for incremental ingest and CDC; MVs for gold aggregates, joins and serving. MVs refresh incrementally with row tracking and can use `refresh_policy`. The schema forbids CDC on MVs (SCH/spec_nodespec.json:362-384).
6. **Why does renaming a flow cause a full refresh, and how does LFF prevent it?** SDP keys a streaming checkpoint by flow name. nodespec derives `f_<node>`, or you pin `{view, flow}`. The migration script pins legacy names (ADR/0010-unified-nodespec-dataflow-spec.md:113-115).
7. **How do you add a new source to an existing target without reprocessing?** Add another entry to the target's `sources` (a new append flow with its own checkpoint). Existing flows and the target are untouched (D/architecture/index.rst:413).
8. **How do you handle deletes?**
   - `apply_as_deletes` for CDC: SCD1 tombstones, SCD2 closed versions.
   - For snapshot sources, stage as SCD1 so physical deletes appear as CDF deletes, then consume with `apply_as_deletes: "cdc_change_type = 'delete'"` (D/build/patterns/cdc-stream-from-snapshot.rst:49; PS/snapshot_samples/dataflowspec/silver_customer_file_snapshot_main.json:46).
9. **How is the same pipeline promoted to prod?**
   - One spec with `{tokens}`.
   - `<target>_substitutions.json` chosen by `bundle.target`, with pipeline tokens overriding framework tokens.
   - `<target>_secrets.json` aliases.
   - DAB targets deploying as service principals.
   - A logical env suffix for developer isolation (section 5).
10. **How do you upgrade the framework safely?**
    - Fork and promote deliberately.
    - Keep customizations in `src/local`, which is deep-merged and never overwritten.
    - Deploy `current` plus a version.
    - Canary with pinned `framework_source_path`, roll back by repointing, and use spec mappings or the migration script for format changes (ADR-0006; D/deploy/ci-cd.rst:146-161).
11. **Explain quarantine and its gotcha.**
    - Flag mode keeps all rows, downgrades rules to warn, and adds `is_quarantined`.
    - Table mode adds a parallel flow that copies failing rows to `<target>_quarantine`, while the main target keeps its rule actions.
    - Gotcha: bad rows leave the clean table only with `expect_or_drop` (ENG/dataflow/dataflow.py:225-227,427; ENG/dataflow/quarantine.py:142-247).
12. **A filter in the pipeline YAML seems ignored and all flows run. Why?** Keys are exact strings in `ENG/constants.py:24-28`. The docs' `pipeline.targetTableFiler` is misspelled (D/build/bundle-steps.rst:350,381), and unknown configuration keys are ignored. Also check `{token}` typos, because unknown tokens pass through verbatim.
13. **A stream-static join shows stale customer addresses. What is happening?** The static side is read in full each micro-batch, and changes surface only when the driving key re-appears (D/build/patterns/stream-static-basic.rst:92). Joining an append-only history table can also fan out rows (ENG/dataflow/sources/delta_join.py:83,99). Use the streaming-DWH pattern, or join to current-state or as-of dimension rows.
14. **How would you use an AI assistant on this framework, and what would you check?** Use the `dataflow-spec-builder` skill with explicit constraints. Then validate against the real JSON Schema, not the skill's script (which rejects valid nodespec), and check known AI errors: `versionType: datetime`, `yyyyMMdd`, integer `scd_type`, legacy format output. Finally run a dev update and inspect expectations (section 9).
15. **How does it scale?** Many pipelines, each filtered to a group. Decompose along staging and final pipelines. Per-flow checkpoints let you add sources cheaply. Initialization cost grows with bundle size, since all specs are read and validated on every update (parallelized across driver cores minus one). SDP scales the data plane (section 12).

---

## 14. Risks and questionable things spotted

| # | Label | Severity | Finding | Evidence |
|---|---|---|---|---|
| R1 | CONFIRMED | High | Legacy-spec validation silently skips every `dependentSchemas` rule (Draft 7), so bad `sourceDetails`, `targetDetails` and `flowDetails` pass CI and init validation. Demonstrated with bogus keys | ENG/utility.py:108-113; scripts/validate_dataflows.py:42,335; SCH/spec_standard.json:31; SCH/flow_group.json:20,38,125 |
| R2 | CONFIRMED (fixed) | High | Until 2026-09-02, nodespec specs were never schema-validated at runtime (path plus root `$ref` bug, silent `errors = []`) | commit fca1b4e (#142); fix visible at ENG/dataflow_spec_builder/dataflow_spec_builder.py:143 |
| R3 | CONFIRMED | High | Docs say `pipeline.targetTableFiler`; the engine reads `pipeline.targetTableFilter`. Copying the docs means the filter is ignored and all flows run | D/build/bundle-steps.rst:350,381; ENG/constants.py:28 |
| R4 | CONFIRMED | Medium | Unknown `{tokens}` are left verbatim with no warning. The Kafka sink sample uses `{kafka_servers}`, `{staging_schema}` and `{kafka_keystore_*}`, none of which the feature substitutions define | ENG/substitution_manager.py:149-155; samples/feature_samples/src/dataflows/kafka_samples/dataflowspec/kafka_sink_main.json:12,33,36-37; samples/feature_samples/src/pipeline_configs/dev_substitutions.json:2-10 |
| R5 | CONFIRMED | Medium | Operational-metadata docs use `payload` and `pipeline_update_id`, but the engine reads `sql`/`key` and sets `update_id`. A doc-copied config yields empty or null metadata | D/features/configuration/operational-metadata.rst:61,106,178,189; ENG/dataflow/operational_metadata.py:36-38,65 |
| R6 | CONFIRMED | Medium | The AI skill is stale (legacy-only, "v0.4.0"), its examples are wrong, and its validator raises 64 false errors on valid samples | SK/SKILL.md:8,412-413,470,490; SK/scripts/validate_specs.py:24,46 |
| R7 | CONFIRMED doc error / SUSPECTED impact | Medium | Stream-static Day-4 doc output shows one joined row, but the implementation joins the whole static append table, giving two rows for customer 1. Duplicate key plus sequence into SCD2 makes the outcome non-deterministic | D/build/patterns/stream-static-basic.rst:436-488; ENG/dataflow/sources/delta_join.py:83,99; samples/pattern_samples/src/notebooks/run_3_staging_load.ipynb (Brisbane row) |
| R8 | SUSPECTED | Medium | TPCH fact inner stream-static join to orders means lines arriving before their order header are lost | TP/src/dataflows/gold/dml/fct_order_lines.sql:35; D/build/patterns/stream-static-basic.rst:92 |
| R9 | SUSPECTED | Medium | `apply_as_deletes: "DELETE_FLAG = 1"` on BOOLEAN columns, the same class of bug fixed for ANSI in #141 | PS/base_samples/silver/dataflowspec/customer_main.json:37; PS/base_samples/silver/schemas/customer_schema.json:29-30; commit deece3d |
| R10 | SUSPECTED | Low-Medium | Gold sample MV joins two SCD2 histories on key only, so versions fan out | PS/base_samples/gold/dataflowspec/gold_materialized_views_main.json:22 |
| R11 | SUSPECTED (inferred) | Medium | Table-mode quarantine with `expect` rules duplicates bad rows in both clean and quarantine tables; users may assume table mode means exclusion | ENG/dataflow/dataflow.py:422-427; ENG/dataflow/quarantine.py:142-247 |
| R12 | CONFIRMED | Medium | `pip install lakeflow-framework` is documented, but the package 404s on public PyPI (2026-09-29; a control package returns 200) | D/get-started/what-is-lakeflow-framework.rst:4; D/deploy/framework/wheel.rst |
| R13 | CONFIRMED (fact) / SUSPECTED (risk) | Medium | `current` is a mutable fleet-wide pointer; production is told to use it by default | D/features/environments/versioning-framework.rst:65; D/deploy/ci-cd.rst:153-155 |
| R14 | CONFIRMED | Medium | CI gaps: no integration tests, no sample validation on schema changes, YAML never validated, template bodies unchecked, fork PRs skipped, end-to-end scripts have no data assertions | .github/workflows/ci.yml:40,62-63,92,157; scripts/validate_dataflows.py:93,116-121; scripts/README.md:9 (claims JSON/YAML validation); tests/integration/conftest.py:17-22 |
| R15 | CONFIRMED | Low | The entry notebook pip-installs requirements on every update: added latency, and it depends on an index or mirror (inferred air-gap risk) | src/dlt_pipeline.ipynb:9 |
| R16 | CONFIRMED | Low | `CHANGELOG.md` is 0 bytes; Operations and Monitoring docs are "Under Construction"; nothing uses the event log | CHANGELOG.md; D/operations.rst:6; D/monitoring_and_observability.rst:6 |
| R17 | CONFIRMED | Low | The pipeline bundle template is stale: `dlt_framework` path, legacy `target:` field, broken test, legacy spec formats. `yaml_sample` has the same broken test | pipeline_bundle_template/databricks.yml:14; `pipeline_bundle_template/resources/PIPELINE NAME_pipeline.yml`:8; pipeline_bundle_template/tests/main_test.py:1; samples/yaml_sample/tests/main_test.py:1 |
| R18 | CONFIRMED | Low | Doc examples that fail the schema: spec-format example (5 errors), flows example (`quarantineTargetDetails: {}`), `versionType: datetime`, `deduplicateMode` placement, and the `"contraint"` typo in the expectations template | D/features/metadata/spec-format.rst:181-199,225; D/build/spec-reference/flows.rst:25,48; D/build/spec-reference/cdc.rst:94,122; D/features/data-quality/expectations.rst:55 |
| R19 | CONFIRMED | Low | Doc/code mismatches: see the sub-list below this table | Sub-list below |
| R20 | CONFIRMED | Low | Doc example errors: see the sub-list below this table | Sub-list below |
| R21 | CONFIRMED | Low | Schema quirks: see the sub-list below this table | Sub-list below |
| R22 | CONFIRMED | Low | `MAIN_SPEC_FILE_SUFFIX = ("_main.json")` is a `str`, not a tuple, so the file-filter check iterates characters and accepts any path ending in one of `_mainjso.` | ENG/constants.py:113; ENG/dataflow_spec_builder/dataflow_spec_builder.py:773 |
| R23 | SUSPECTED | Low | The version may be bumped twice: contributors are told to bump `VERSION` manually, while a workflow already auto-bumps from branch names on merge | D/contributors/dev-git.rst:68-77; .github/workflows/main-build.yml:38-70 |
| R24 | CONFIRMED | Low | nodespec was introduced as "[BETA]" but the docs present it as the default with no caveat; no Data Vault sample despite claims; an orphan legacy sink spec (no `_main` suffix, "DISABLED" group, duplicate id); `custom_python_sink` has no working sample | commit 6b15bb8; D/build/spec-reference/nodespec.rst:8,17; README.md:18; FS/sink_custom_python_generate_cdc_feed.json:2-3 |
| R25 | SUSPECTED | Low | Deploy scripts rewrite tracked config files in place (backup/restore), a risk of committing mutated files; the TPCH classic cluster is AWS-only | samples/common.sh:324-417; TP/databricks.yml:55 |

**R19 detail: doc/code mismatches.**
- Secrets folder named `src/pipeline_config` (singular): D/features/configuration/secrets-management.rst:43-44.
- `allow_override` documented default `false` vs shipped `true`: D/features/metadata/spec-format.rst:82; ENG/config/default/global.json:4.
- Substitution example output needs an `_` separator the code does not add: D/features/metadata/substitutions.rst:130,264; ENG/substitution_manager.py:178.
- Local config README uses key `dataflow_spec_mapping_version`; the engine reads `dataflow_spec_version`: src/local/config/README.md:15; ENG/dlt_pipeline_builder.py:386.
- Target reference documents `clusterBy` and `spark_conf`; the schema uses `clusterByColumns` and `sparkConf`: D/build/spec-reference/target-details.rst:38,56.
- Logging doc says the default config has `enabled: false`, but no default `logger.json` ships: D/features/configuration/logging.rst:497.
- Staging tables "only Streaming Tables" vs `ST`/`MV` in the schema: D/architecture/index.rst:429; SCH/flow_group.json:35.
- Flows documented as an "array" vs an object in the schema: D/build/spec-reference/flows.rst:275; SCH/flow_group.json:8-10.
- Historical snapshots "only standard" vs a flow sample that uses them: D/build/spec-reference/cdc.rst:78.
- Deprecation version: v0.14.0 vs v0.13.0: D/features/configuration/framework-configuration.rst:142; src/local/config/README.md:45.
- ADR-0002 contradicts itself: ADR/0002-extensions-deprecation.md:27,30.
- ADR-0009 shows an extra `src/` in the overlay path: ADR/0009-strategy-b-workspace-files-first-resolver.md:80.

**R20 detail: doc example errors.**
- Basic 1:1 SCD2 Day-2 table: Jane's version is wrongly closed; new customers get the 01-01 start date; `_START_AT` has a single underscore instead of `__START_AT`: D/build/patterns/basic-1-1.rst:266-271.
- Snapshot-CDC Day 3 omits Joe's `updated_timestamp` change (SUSPECTED): D/build/patterns/cdc-stream-from-snapshot.rst:217-249.
- `**root_path**:` inside a YAML code block: D/features/authoring/ui-integration.rst:45.
- `spark_conf:` used where a pipeline resource needs `configuration:` (SUSPECTED): D/deploy/framework/wheel.rst:82.
- Stale paths: D/features/platform/materialized-views.rst:45; D/features/sources-targets/sql-source.rst:22; scripts/README.md:20.
- Broken references: D/build/spec-reference/nodespec.rst:141; tests/README.md:31; TP/DESIGN.md:265.
- Copy-paste text: D/build/spec-reference/flows.rst:4; D/features/sources-targets/sql-source.rst:62.
- Samples README: a non-existent "DPM" tier and a wrong `_test` default: samples/README.md:91,122-124.

**R21 detail: schema quirks.**
- `partition_columns` + `cluster_by_auto` is accepted: SCH/spec_nodespec.json:361.
- The legacy `targetFormat` enum omits `custom_python_sink`, which `definitions_targets` supports: SCH/spec_standard.json:19; SCH/spec_flows.json:15; SCH/definitions_targets.json:19.
- `materialized_views` (plural) in the flows enum: SCH/spec_flows.json:11.
- Kafka `subscribe` has default "latest": SCH/definitions_sources.json:275.
- `minItems` is placed inside an object item schema, so it has no effect: SCH/spec_template.json:28.
- `scd_type` is string-only in `cdc_settings` but also allows an integer in snapshot settings: SCH/definitions_main.json:13; SCH/spec_nodespec.json:488.

---

## 15. Glossary

| Term | Meaning (in this repository's usage) |
|---|---|
| SDP / Lakeflow SDP (formerly DLT) | Spark Declarative Pipelines. You declare datasets and flows; Databricks manages orchestration, checkpoints, retries and expectations |
| LFF | Lakeflow Framework, this repository |
| DAB / Declarative Automation Bundles | The Databricks bundle format and CLI (`databricks bundle deploy`) that deploys code and resources per target |
| Framework Bundle / Pipeline Bundle | The engine plus config (deployed once per version) / specs plus pipeline YAML (one per team or domain) |
| Data Flow Spec | One file (plus schemas, SQL and expectations) defining the logic for one target table or graph; must end in `_main.json`/`.yaml` |
| nodespec | The default node-graph spec (source, transformation, target; snake_case) |
| Legacy spec types | `standard` (1:1), `flow` (flow groups, staging tables, views), `materialized_view` (camelCase) |
| Flow / flow group | An SDP flow (append or AUTO CDC) into a target; a flow group is a legacy logical grouping of flows and staging tables |
| Staging table | A non-terminal target inside one spec (ST or MV) |
| ST / MV | Streaming table (incremental, checkpointed) / materialized view (declarative refresh) |
| AUTO CDC (`apply_changes`) | SDP API that merges change events into SCD1/SCD2 tables using `keys` + `sequence_by` |
| AUTO CDC FROM SNAPSHOT | Diffs successive full snapshots (periodic or historical) into CDC |
| SCD1 / SCD2 | Overwrite in place / keep history with `__START_AT`/`__END_AT` |
| `sequence_by` | Column defining event order per key; resolves out-of-order arrival |
| CDF | Delta Change Data Feed; `cdf_enabled` reads it and `delta.enableChangeDataFeed` writes it |
| Auto Loader (`cloudFiles`) | Incremental file ingestion with schema inference and evolution |
| Expectations | SDP data-quality rules: `expect` (warn), `expect_or_drop`, `expect_or_fail` |
| Quarantine | LFF feature: `flag` (the `is_quarantined` column) or `table` (`<target>_quarantine`) |
| Operational metadata | LFF audit struct `meta_load_details` (load timestamps, pipeline update id) per layer |
| Substitutions / tokens | `{token}` values per DAB target, plus prefix/suffix rules; `workspace_env` equals `bundle.target` |
| Logical environment | Name suffix (e.g. `_jd`) isolating developers' pipelines and schemas in a shared workspace |
| `framework_source_path` / `current` | Workspace path of the deployed framework; `current` is the moving latest-release copy |
| `src/local` | Framework-bundle, customer-owned, upgrade-safe overlay (config deep-merge, libraries, python, init) |
| Spec mapping | Versioned rename/move/delete rules that upgrade old spec shapes (`dataFlowVersion`) |
| Table migration | One-time import of an existing table, with version-state CSVs in a UC volume |
| `once` flow | An append flow that runs a single time (backfill) |
| Sink / `foreach_batch` / `micro_batch_view` | SDP outputs to external Delta or Kafka; custom per-micro-batch SQL/Python reading `micro_batch_view` |
| `delta_join` / stream-static join | LFF source joining a streaming driver to static (fully re-read) tables |
| Unknown member (`-1`) | Placeholder dimension row for facts whose dimension has not arrived yet |
| Surrogate key (`xxhash64`) | Deterministic hash of (dimension, natural key, `__START_AT`) used as a dimension key |
| UC metric view / Genie | Unity Catalog semantic-layer view queried with `MEASURE()` / AI/BI natural-language space |
| Liquid clustering / row tracking | Delta data layout without partitions / row IDs enabling incremental MV refresh |
| `refresh_policy` | MV refresh mode: `auto`, `incremental`, `incremental_strict` or `full` (Beta, DBR 17.3+) |
| Checkpoint / full refresh | Per-flow streaming state keyed by flow name / reset and reprocess of a table or pipeline |
| Event log | (platform) SDP's per-pipeline table of run, flow and expectation events. Not used by this repository |
