# Case study 03: fail-open patterns, where errors surface far from the cause (or never)

**Theme:** code that catches an error and carries on turns a *loud, local* failure into a *quiet, distant* one. Of all the bug classes I found across the six repos, this is the one I would review hardest in customer code and in AI-generated code.

## Instances found and verified

| # | Where | Pattern | Consequence | Status |
|---|---|---|---|---|
| 1 | `lakeflow_framework/src/lakeflow_framework/dataflow_spec_builder/dataflow_spec_builder.py:499-540` | A spec-transform exception is logged as a WARNING and the **untransformed** payload is passed on. The `ignore_validation_errors` flag only changes logging | The run fails later with an unrelated `TypeError: DataflowSpec.__init__() got an unexpected keyword argument 'sourceSystem'`. The real cause ("simulated transformer bug") sits in an earlier WARNING line | CONFIRMED by a scratch test with the repo's fixtures ([`evidence/test_scratch_transform_fail_open.py`](evidence/test_scratch_transform_fail_open.py)) |
| 2 | `vibe-coding-workshop-template/.../silver/01-dlt-expectations-patterns/SKILL.md:147-165` | The DQ-rules loader wraps everything in `try … except Exception as e: print(f"Note: Could not load DQ rules: {e}")` | The rules cache stays empty and `expect_all_or_drop({})` enforces **nothing**. The pipeline is green, with zero data quality | CONFIRMED (code read) |
| 3 | `vibe-coding-workshop-template/.../ml/00-ml-pipeline-setup/scripts/create_feature_tables_template.py:275-281` (also train and inference templates) | `except Exception: … dbutils.notebook.exit(f"FAILED: {e}")` | `notebook.exit` ends the notebook **normally** with a return value, so the job task reports success and downstream tasks run | CONFIRMED (code). The platform behaviour is standard `dbutils.notebook.exit` semantics |
| 4 | `technical-services-solutions/.../pbi-aibi-converter/app_for_conversions/converter.py:2703-2719, 2971-3058` | LLM-output "repair" rewrites SQL: pops `HAVING`, drops aggregate `ORDER BY`, keeps `LIMIT`, and fuzzy-swaps unknown columns (`unit_cost→unit_count`). Validation results are displayed but don't gate publish | Top-N dashboards silently show N arbitrary raw rows; a misspelled column silently becomes a *different* real column | CONFIRMED (code). The rewrite was reproduced with sqlglot by the deep-read |
| 5 | `vibe-coding-workshop-template/scripts/genie_gate.py` | Six prompt-tree checks print SKIP and return True when the private prompt tree is absent | The gate is green on a public clone with 6 of 7 checks not run | CONFIRMED by execution (deep-read) |
| 6 | `consort/consort/smells/supersession.ts:286-296` + `:232` | `readGreenFailure` **deletes** the failure record when the git-status fingerprint changes. The repair-attempt counter lives in that record | A repair that adds a file resets the count, so the 3-round cap never trips | CONFIRMED (code). Reproduced with the repo's functions by the deep-read |
| 7 | `vibe-coding-workshop-template/.../gold/01-gold-layer-setup` | FK/PK constraint failures are "warn + continue" | A model can ship with no constraints and a green job | CONFIRMED (per deep-read) |

## The counter-example: fail *closed*

`databricks-waf` is built around the opposite principle, "Not measured never becomes pass":
- A collector returns `unmeasurable` rather than zero rows.
- A **truncated** result *throws*, with the message "the rows it did return are part of the answer rather than the answer".
- `unmeasurable` gets no credit in scoring and **widens** a `[low, high]` range instead of pretending.
- An attestation may fill a gap but never overturn a measurement.

`consort`'s deploy gate refuses approval unless `reachable === true && verify.passed === true`. These are the patterns to steal.

## Rules I apply (and would ask an Assistant to apply)

1. **Fail where the cause is.** If you must continue, *record* the degradation in a way the output carries: a status column, a metric, a non-empty `errors` list that fails the job at the end.
2. **Never convert an exception into a success signal.** `notebook.exit("FAILED")`, `return {}`, `SKIP == PASS` and `print` + continue are all success signals.
3. **Never "repair" semantics silently.** A syntax fix that changes meaning (dropping `HAVING`, swapping columns) is worse than an error.
4. **Validation that doesn't gate is a report, not validation.**
5. **Counters that bound loops must live somewhere that can't be invalidated** by the thing being counted.
6. **When debugging a baffling error, look *upstream* for a swallowed one.** Search the logs for `WARN`/`Note:`/`skip` before the failure.

## How to spot it in a review (grep list)

```
except Exception            # then read what the handler does
except:                     # bare except
pass$                       # swallowed
print(.*[Ee]rror            # printed instead of raised
notebook.exit(.*FAIL
return {}  / return []      # inside an except
|| true                     # shell: masks failure (also seen in orderflow CI)
continue-on-error: true     # CI: check that a later step re-fails
```
