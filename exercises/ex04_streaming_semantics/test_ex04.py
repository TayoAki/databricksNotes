"""Streaming semantics, pinned down as tests (Delta source -> Delta sink, availableNow trigger)."""
from __future__ import annotations

import pytest
from delta.tables import DeltaTable

from ex04_streaming_semantics import streaming_lab as L


def _rows(spark, path):
    if not DeltaTable.isDeltaTable(spark, path):
        return []
    return [tuple(r) for r in spark.read.format("delta").load(path).collect()]


def test_checkpoint_gives_exactly_once_incremental_processing(spark, tmp_path):
    src, sink, cp = (str(tmp_path / x) for x in ("src", "sink", "cp"))
    L.append_events(spark, src, [("e1", "C1", L.ts("2026-09-01 10:00"), 10),
                                 ("e2", "C1", L.ts("2026-09-01 10:01"), 20)])
    assert L.run_available_now(L.passthrough(spark, src), sink, cp)["input_rows"] == 2
    assert L.run_available_now(L.passthrough(spark, src), sink, cp)["input_rows"] == 0   # replay: nothing
    L.append_events(spark, src, [("e3", "C2", L.ts("2026-09-01 10:02"), 5)])
    assert L.run_available_now(L.passthrough(spark, src), sink, cp)["input_rows"] == 1   # only the new row
    assert len(_rows(spark, sink)) == 3


def test_append_mode_window_waits_for_the_watermark(spark, tmp_path):
    src, sink, cp = (str(tmp_path / x) for x in ("src", "sink", "cp"))
    L.append_events(spark, src, [("e1", "C1", L.ts("2026-09-01 10:00"), 10),
                                 ("e2", "C1", L.ts("2026-09-01 10:05"), 20)])
    L.run_available_now(L.windowed_revenue(spark, src), sink, cp)
    # All events for window [10:00, 10:10) have arrived, but watermark = 10:05 - 10min = 09:55
    assert _rows(spark, sink) == []
    L.append_events(spark, src, [("e3", "C1", L.ts("2026-09-01 10:30"), 7)])     # watermark -> 10:20
    L.run_available_now(L.windowed_revenue(spark, src), sink, cp)
    assert [(str(ws), rev, n) for ws, rev, n in _rows(spark, sink)] == [("2026-09-01 10:00:00", 30, 2)]
    # ...and the 10:30 window will not be published until later data moves the watermark again
    L.run_available_now(L.windowed_revenue(spark, src), sink, cp)
    assert len(_rows(spark, sink)) == 1


def test_constant_event_time_watermark_never_emits_in_append_mode(spark, tmp_path):
    """lakeflow_framework table_import.py builds its 'closed rows' with this construction."""
    src, sink, cp = (str(tmp_path / x) for x in ("src", "sink", "cp"))
    L.append_events(spark, src, [("e1", "C1", L.ts("2026-01-01"), 1), ("e2", "C1", L.ts("2026-02-01"), 2),
                                 ("e3", "C2", L.ts("2026-01-15"), 3)])
    progress = L.run_available_now(L.latest_per_key_constant_watermark(spark, src), sink, cp)
    assert progress["input_rows"] == 3          # rows were read...
    assert _rows(spark, sink) == []             # ...but the window [2000-01-01 00:00, 00:10) never closes


def test_delta_sink_rejects_update_mode(spark, tmp_path):
    src, sink, cp = (str(tmp_path / x) for x in ("src", "sink", "cp"))
    L.append_events(spark, src, [("e1", "C1", L.ts("2026-01-01"), 1)])
    with pytest.raises(Exception, match="DELTA_UNSUPPORTED_OUTPUT_MODE"):
        L.run_available_now(L.latest_per_key_constant_watermark(spark, src), sink, cp, mode="update")


def test_stream_static_join_uses_dimension_as_of_processing_time(spark, tmp_path):
    src, sink, cp, dim = (str(tmp_path / x) for x in ("src", "sink", "cp", "dim"))
    spark.createDataFrame([("C1", "SMB")], "customer_id STRING, segment STRING").write.format("delta").save(dim)
    L.append_events(spark, src, [("e1", "C1", L.ts("2026-09-01 10:00"), 10)])
    L.run_available_now(L.enrich_stream_with_static(spark, src, dim), sink, cp)
    (spark.createDataFrame([("C1", "Enterprise")], "customer_id STRING, segment STRING")
     .write.format("delta").mode("overwrite").save(dim))
    L.append_events(spark, src, [("e2", "C1", L.ts("2026-09-01 11:00"), 10)])
    L.run_available_now(L.enrich_stream_with_static(spark, src, dim), sink, cp)
    assert sorted(_rows(spark, sink)) == [("e1", "C1", "SMB"),           # NOT re-joined
                                          ("e2", "C1", "Enterprise")]
