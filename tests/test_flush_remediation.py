"""Exact replacement, text transport, and failed-transaction retry contracts."""
from datetime import date, datetime

import pytest

from kojakstreet.core.data_store import EconomicDataStore


@pytest.mark.parametrize('table,width', [
    ('news_events', 3), ('news_current', 3), ('event_log', 6), ('event_current', 6),
])
def test_text_batch_matches_bound_insert(tmp_path, table, width):
    store = EconomicDataStore(tmp_path / 'text.duckdb')
    texts = ['', None, r'\N', 'commas, quotes " and newline\nÃ¤ æ¼¢å­—']
    rows = [('1991-01-30', *([value] * (width - 1))) for value in texts]
    try:
        connection = store._connection
        connection.execute(f'CREATE TEMP TABLE expected AS SELECT * FROM {table} WHERE FALSE')
        placeholders = ','.join('?' for _ in range(width))
        connection.executemany(f'INSERT INTO expected VALUES ({placeholders})', rows)
        store._insert_rows(table, rows)
        assert connection.execute(f'SELECT * FROM {table} ORDER BY ALL').fetchall() == connection.execute('SELECT * FROM expected ORDER BY ALL').fetchall()
    finally:
        store.close()


@pytest.mark.parametrize('day', ['1991-01-30', date(1991, 1, 30), '1991-1-30'])
def test_replacement_preserves_other_dates_and_duplicate_rows(tmp_path, day):
    store = EconomicDataStore(tmp_path / 'dates.duckdb')
    try:
        store._insert_rows('phase_metric_daily', [
            ('1991-01-29', 'keep', 1.0), ('1991-01-30', 'old', 2.0),
        ])
        rows = [(day, 'replacement', 3.0), (day, 'replacement', 3.0)]
        store._replace_buffered_rows('phase_metric_daily', rows)
        assert store._connection.execute('SELECT * FROM phase_metric_daily ORDER BY ALL').fetchall() == [
            (date(1991, 1, 29), 'keep', 1.0),
            (date(1991, 1, 30), 'replacement', 3.0),
            (date(1991, 1, 30), 'replacement', 3.0),
        ]
    finally:
        store.close()


def test_noncanonical_date_is_not_interpolated_into_sql(tmp_path):
    store = EconomicDataStore(tmp_path / 'untrusted.duckdb')
    try:
        # DuckDB's bound DATE conversion accepts a date prefix. It must remain
        # a value, even when the suffix looks like executable SQL.
        store._replace_buffered_rows('phase_metric_daily', [
            ("1991-01-30'); DROP TABLE phase_metric_daily; --", 'suffix', 1.0),
        ])
        assert store._connection.execute('SELECT * FROM phase_metric_daily').fetchall() == [
            (date(1991, 1, 30), 'suffix', 1.0),
        ]
    finally:
        store.close()


class FailingConnection:
    def __init__(self, raw, phase):
        self.raw, self.phase, self.failed = raw, phase, False

    def __getattr__(self, key):
        return getattr(self.raw, key)

    def execute(self, sql, *args, **kwargs):
        command = sql.strip().split()[0].upper()
        if command == self.phase and not self.failed:
            self.failed = True
            raise RuntimeError('injected ' + self.phase)
        result = self.raw.execute(sql, *args, **kwargs)
        return self if result is self.raw else result


@pytest.mark.parametrize('phase', ['BEGIN', 'COPY', 'COMMIT'])
def test_failed_flush_is_atomic_and_exactly_retryable(tmp_path, phase):
    store = EconomicDataStore(tmp_path / 'failure.duckdb')
    current = [('1991-01-29', 'old', 1.0)]
    pending = [('1991-01-30', 'new', 2.0)]
    try:
        store._insert_rows('phase_metric_current', current)
        store._pending_rows = {'phase_metric_daily': pending}
        store._pending_days = {'1991-01-30'}
        store._current_rows = {'phase_metric_current': pending}
        store._connection = FailingConnection(store._connection, phase)
        with pytest.raises(RuntimeError, match='injected'):
            store.flush()
        assert store._pending_rows == {'phase_metric_daily': pending}
        assert store._pending_days == {'1991-01-30'}
        assert store._connection.execute('SELECT * FROM phase_metric_daily').fetchall() == []
        assert store._connection.execute('SELECT * FROM phase_metric_current').fetchall() == [(date(1991, 1, 29), 'old', 1.0)]
        store.flush()
        assert store._pending_rows == {} and store._pending_days == set()
    finally:
        store.close()
    reopened = EconomicDataStore(tmp_path / 'failure.duckdb')
    try:
        assert reopened._connection.execute('SELECT * FROM phase_metric_daily').fetchall() == [(date(1991, 1, 30), 'new', 2.0)]
        assert reopened._connection.execute('SELECT * FROM phase_metric_current').fetchall() == [(date(1991, 1, 30), 'new', 2.0)]
    finally:
        reopened.close()


def test_text_batch_retains_parameter_fallback_for_nontext_values(tmp_path):
    store = EconomicDataStore(tmp_path / 'fallback.duckdb')
    rows = [(datetime(1991, 1, 30), True, 123)]  # noqa: DTZ001 -- preserve legacy naive date input
    try:
        store._connection.execute('CREATE TEMP TABLE expected AS SELECT * FROM news_events WHERE FALSE')
        store._connection.executemany('INSERT INTO expected VALUES (?,?,?)', rows)
        store._insert_rows('news_events', rows)
        assert store._connection.execute('SELECT * FROM news_events').fetchall() == store._connection.execute('SELECT * FROM expected').fetchall()
    finally:
        store.close()


def test_ambiguous_commit_preserves_original_error_and_exact_retry(tmp_path):
    store = EconomicDataStore(tmp_path / 'ambiguous.duckdb')
    rows = [('1991-01-30', 'new', 2.0)]
    raw = store._connection

    class AfterCommit:
        def execute(self, sql, *args, **kwargs):
            result = raw.execute(sql, *args, **kwargs)
            if sql == 'COMMIT':
                raise OSError('commit acknowledgement lost')
            return result

    store._pending_rows = {'phase_metric_daily': rows}
    store._pending_days = {'1991-01-30'}
    store._current_rows = {'phase_metric_current': rows}
    store._connection = AfterCommit()
    try:
        with pytest.raises(OSError, match='acknowledgement lost') as caught:
            store.flush()
        assert 'Rollback also failed' in caught.value.__notes__[0]
        assert store._pending_rows == {'phase_metric_daily': rows}
        store._connection = raw
        store.flush()
        expected = [(date(1991, 1, 30), 'new', 2.0)]
        assert raw.execute('SELECT * FROM phase_metric_daily').fetchall() == expected
        assert raw.execute('SELECT * FROM phase_metric_current').fetchall() == expected
    finally:
        store._connection = raw
        store.close()
