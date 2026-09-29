"""Scratch observation test (not upstream): what does build() do when a spec transformer raises?"""
from __future__ import annotations

import lakeflow_framework.dataflow_spec_builder.dataflow_spec_builder as dsb
from lakeflow_framework.dataflow_spec_builder.dataflow_spec_builder import DataflowSpecBuilder


class _ExplodingTransformer:
    def transform(self, spec_data):
        raise RuntimeError("simulated transformer bug")


def test_transform_failure_behaviour(secrets_manager, framework_src_path, dataflow_bundle_tree,
                                     pipeline_context, monkeypatch, capsys):
    monkeypatch.setattr(dsb.SpecTransformerFactory, "create_transformer",
                        staticmethod(lambda dataflow_type: _ExplodingTransformer()))
    builder = DataflowSpecBuilder(bundle_path=str(dataflow_bundle_tree),
                                  framework_path=str(framework_src_path), filters={},
                                  secrets_manager=secrets_manager,
                                  ignore_validation_errors=False,   # strict mode
                                  max_workers=1)
    try:
        specs = builder.build()
        outcome = f"build() RETURNED {len(specs)} spec(s) despite transformer error (fail-open)"
    except Exception as exc:  # noqa: BLE001
        outcome = f"build() RAISED {type(exc).__name__}: {exc} (fail-closed)"
    print("\nOBSERVED:", outcome)
