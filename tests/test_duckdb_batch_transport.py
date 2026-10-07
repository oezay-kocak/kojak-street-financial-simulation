"""Persistence transport must retain bound-value and transaction semantics."""
import math
from datetime import date

import duckdb
import pytest

from kojakstreet.core.data_store import EconomicDataStore


def normalized(rows):
    return [["NaN" if isinstance(value, float) and math.isnan(value) else value
             for value in row] for row in rows]


@pytest.mark.parametrize("table", ["phase_metric_daily", "phase_metric_current"])
def test_phase_batches_match_parameter_binding_for_text_nulls_and_numeric_edges(tmp_path, table):
    store = EconomicDataStore(tmp_path / "batch.duckdb")
    assert store.enabled
    rows = [("1991-01-30", text, value) for text, value in [
        ("ordinary", 1.0 / 3.0), ("", None), (None, 0.0), (r"\N", -0.0),
        ('commas, quotes " and line\nbreaks ä 漢字', -1.25),
        ("NaN", float("nan")), ("positive infinity", float("inf")),
        ("negative infinity", -float("inf")),
    ]]
    try:
        connection = store._connection
        connection.execute(f"CREATE TEMP TABLE expected AS SELECT * FROM {table} WHERE FALSE")
        connection.executemany("INSERT INTO expected VALUES (?, ?, ?)", rows)
        expected = connection.execute("SELECT * FROM expected ORDER BY ALL").fetchall()
        store._insert_rows(table, rows)
        actual = connection.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
        assert normalized(actual) == normalized(expected)
    finally:
        store.close()


def test_failed_flush_rolls_back_and_retains_retry_buffer(tmp_path, monkeypatch):
    store = EconomicDataStore(tmp_path / "retry.duckdb")
    assert store.enabled
    original = [("1991-01-29", "original", 0.25)]
    pending = [("1991-01-30", 'new "metric"', 0.75)]
    store._insert_rows("phase_metric_current", original)
    store._pending_rows = {"phase_metric_daily": pending}
    store._pending_days = {"1991-01-30"}
    store._current_rows = {"phase_metric_current": pending}
    replace = store._replace_current_rows
    def fail_after_replacement(*args, **kwargs):
        replace(*args, **kwargs)
        raise RuntimeError("injected failure before COMMIT")
    monkeypatch.setattr(store, "_replace_current_rows", fail_after_replacement)
    with pytest.raises(RuntimeError, match="before COMMIT"):
        store.flush()
    assert store._connection.execute("SELECT * FROM phase_metric_daily").fetchall() == []
    assert store._connection.execute("SELECT * FROM phase_metric_current").fetchall() == [(date(1991, 1, 29), "original", 0.25)]
    assert store._pending_rows == {"phase_metric_daily": pending}
    assert store._pending_days == {"1991-01-30"}
    monkeypatch.setattr(store, "_replace_current_rows", replace)
    store.flush()
    assert store._pending_rows == {}
    assert store._connection.execute("SELECT * FROM phase_metric_current").fetchall() == [(date(1991, 1, 30), 'new "metric"', 0.75)]
    store.close()
    reopened = EconomicDataStore(tmp_path / "retry.duckdb")
    try:
        assert reopened._connection.execute("SELECT * FROM phase_metric_daily").fetchall() == [(date(1991, 1, 30), 'new "metric"', 0.75)]
    finally:
        reopened.close()


def test_parameter_batch_tempfile_is_cleaned_after_copy_error(tmp_path, monkeypatch):
    import tempfile
    from pathlib import Path

    from kojakstreet.core import data_store
    folder = tmp_path / "owner's CSV files"
    folder.mkdir()
    created = []
    original = tempfile.NamedTemporaryFile
    def temporary(*args, **kwargs):
        kwargs['dir'] = folder
        handle = original(*args, **kwargs)
        created.append(Path(handle.name))
        return handle
    store = EconomicDataStore(tmp_path / 'cleanup.duckdb')
    monkeypatch.setattr(data_store.tempfile, 'NamedTemporaryFile', temporary)
    try:
        with pytest.raises(duckdb.Error):
            store._insert_rows('phase_metric_daily', [('not-a-date', 'invalid', 1.0)])
        assert all(not path.exists() for path in created)
        store._insert_rows('phase_metric_daily', [('1991-01-30', 'valid', 1.0)])
        assert all(not path.exists() for path in created)
        assert store._connection.execute('SELECT phase FROM phase_metric_daily').fetchall() == [('valid',)]
    finally:
        store.close()
