"""Ordered persistence must prove durable replay, bounded queues and Save barriers."""
import io
import math
import queue
import subprocess
import sys
import threading
from pathlib import Path

import duckdb
import pytest

from kojakstreet.core.data_store import EconomicDataStore
from kojakstreet.core.persistence_writer import (
    OrderedConnection,
    OrderedWriter,
    RowBatch,
    RowJournal,
)
from tools.flush_writer_probe import apply_batch

ROOT = Path(__file__).resolve().parents[1]


def prepare(path):
    store = EconomicDataStore(path)
    store._insert_rows('phase_metric_current', [('1991-01-29', 'old', 1.0)])
    history_id = store._history_id
    store.close()
    return history_id


def recover(path, history_id):
    journal = RowJournal(path, history_id, create=False)
    connection = duckdb.connect(str(path))
    try:
        for slot, batch in journal.pending:
            apply_batch(batch, connection)
            journal.acknowledge(slot, batch.sequence)
        return {table: connection.execute(f'SELECT * FROM {table} ORDER BY ALL').fetchall()
                for table in ('phase_metric_daily', 'phase_metric_current')}
    finally:
        connection.close()


def test_journal_freezes_scalars_and_roundtrips_exactly(tmp_path):
    path = tmp_path / 'rows.duckdb'
    rows = [('1991-01-30', 'ä "\\N\n', -0.0), ('1991-01-30', '', 1.0 / 3),
            ('1991-01-30', None, float('inf')), ('1991-01-30', 'nan', float('nan'))]
    batch = RowBatch.freeze(1, 'history', {'phase_metric_daily': rows}, {}, {'1991-01-30'})
    journal = RowJournal(path, 'history')
    journal.stage(0, batch)
    rows[0] = ('changed', 'changed', 100.0)
    restored = RowJournal(path, 'history', create=False).pending[0][1]
    assert repr(restored.pending) == repr(batch.pending)
    assert math.copysign(1, restored.pending[0][1][0][2]) == -1
    with pytest.raises(TypeError):
        RowBatch.freeze(2, 'history', {'phase_metric_daily': [('1991-01-30', {}, 0)]}, {}, set())


def test_corrupt_journal_is_surfaced(tmp_path):
    path = tmp_path / 'corrupt.duckdb'
    journal = RowJournal(path, 'history')
    journal.stage(0, RowBatch.freeze(1, 'history', {'phase_metric_daily': [('1991-01-30', 'a', 1)]}, {}, set()))
    with journal.paths[0].open('r+b') as stream:
        stream.seek(4096)
        stream.write(b'!')
    with pytest.raises(ValueError, match='payload'):
        RowJournal(path, 'history', create=False)
    with pytest.raises(ValueError, match='another history'):
        RowJournal(path, 'different', create=False)


def test_missing_journal_slot_is_surfaced_instead_of_recreated(tmp_path):
    path = tmp_path / 'missing-slot.duckdb'
    journal = RowJournal(path, 'history')
    journal.stage(0, RowBatch.freeze(1, 'history', {}, {}, set()))
    journal.paths[1].unlink()
    for create in (False, True):
        with pytest.raises(ValueError, match='slot is missing'):
            RowJournal(path, 'history', create=create)
        assert not journal.paths[1].exists()


def test_single_owner_bounded_queue_and_ordered_queries(tmp_path):
    path = tmp_path / 'bounded.duckdb'
    history_id = prepare(path)
    active, release, third_done = threading.Event(), threading.Event(), threading.Event()
    applied, owners = [], set()

    def apply(batch, raw):
        owners.add(threading.get_ident())
        if batch.sequence == 1:
            active.set()
            assert release.wait(10)
        apply_batch(batch, raw)
        applied.append(batch.sequence)

    writer = OrderedWriter(path, history_id, duckdb.connect, apply)
    try:
        def submit(sequence):
            rows = [(f'1991-01-{sequence:02d}', str(sequence), float(sequence))]
            return writer.submit({'phase_metric_daily': rows}, {'phase_metric_current': rows}, {rows[0][0]})

        first = submit(1)
        assert active.wait(5)
        second = submit(2)
        assert first['queue_depth'] == 1 and second['queue_depth'] == 2
        assert len(RowJournal(path, history_id, create=False).pending) == 2

        def third():
            submit(3)
            third_done.set()

        producer = threading.Thread(target=third)
        producer.start()
        assert not third_done.wait(0.1)
        release.set()
        assert third_done.wait(10)
        producer.join()
        writer.barrier()
        connection = OrderedConnection(writer)
        result = connection.execute('SELECT count(*) FROM phase_metric_daily')
        writer.call(lambda raw: raw.execute('SELECT 42').fetchall())
        assert result.fetchone() == (3,)
        assert applied == [1, 2, 3]
        assert owners == {writer.thread_id}
        assert writer.thread_id != threading.get_ident()
        assert all(metric['queue_depth'] <= 2 for metric in writer.metrics)
        assert RowJournal(path, history_id, create=False).pending == []
    finally:
        release.set()
        writer.close()


@pytest.mark.parametrize('stage', ['before_transaction', 'during_copy', 'before_commit', 'during_commit', 'after_commit', 'after_ack'])
def test_process_crash_replays_durable_rows_without_loss_or_duplicates(tmp_path, stage):
    path = tmp_path / 'crash.duckdb'
    history_id = prepare(path)
    process = subprocess.run([
        sys.executable, str(ROOT / 'tools/flush_writer_probe.py'), '--crash', stage, '--database', str(path),
    ], cwd=ROOT, capture_output=True, text=True, check=False, timeout=45)
    assert process.returncode == 91, process.stderr
    raw = duckdb.connect(str(path))
    try:
        # Atomic native transaction: either the whole old or the whole new state.
        daily = raw.execute('SELECT phase FROM phase_metric_daily').fetchall()
        current = raw.execute('SELECT phase FROM phase_metric_current').fetchall()
        assert (daily, current) in [( [], [('old',)]), ([('new',)], [('new',)])]
    finally:
        raw.close()
    recovered = recover(path, history_id)
    assert [row[1:] for row in recovered['phase_metric_daily']] == [('new', 2.0)]
    assert [row[1:] for row in recovered['phase_metric_current']] == [('new', 2.0)]
    assert recover(path, history_id) == recovered


@pytest.mark.parametrize('mode', ['idle', 'active', 'queued'])
def test_runtime_save_load_and_shutdown_wait_for_durable_owner(tmp_path, mode):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, encode
    from kojakstreet.live_process import economic_signature

    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path / 'runtime', seed=1729)
    store = runtime.data_store
    store.enable_background_flush()
    release, active = threading.Event(), threading.Event()
    original = store._writer.apply

    def delayed(batch, raw):
        if batch.sequence == 1:
            active.set()
            assert release.wait(15)
        original(batch, raw)

    timer = None
    try:
        if mode != 'idle':
            store._writer.apply = delayed
            store.flush(defer=True)
            assert active.wait(5)
            if mode == 'queued':
                runtime.advance_day()
                store.flush(defer=True)
                assert store._writer.free.qsize() == 0

            def unblock():
                assert not runtime.save_path.exists()
                release.set()

            timer = threading.Timer(0.2, unblock)
            timer.start()
        runtime.save_game()
        assert not RowJournal(store.path, store._history_id, create=False).pending
        saved = economic_signature(runtime.daten)
        runtime.advance_day()
        expected = capture(runtime.daten)
        runtime.load_game()
        assert economic_signature(runtime.daten) == saved
        runtime.advance_day()
        assert encode(capture(runtime.daten)) == encode(expected)
        store.flush(defer=True)
        runtime.close()
        assert store._writer.closed
        assert not RowJournal(store.path, store._history_id, create=False).pending
        reopened = EconomicDataStore(store.path)
        try:
            assert reopened._history_id == store._history_id
            assert reopened.history_manifest()['latest_date'] is not None
        finally:
            reopened.close()
    finally:
        release.set()
        if timer:
            timer.join()
        runtime.close()


def test_writer_failure_is_latched_reported_and_recoverable(tmp_path):
    path = tmp_path / 'failed-owner.duckdb'
    history_id = prepare(path)
    observed = []
    release = threading.Event()

    def fail(batch, raw):
        assert release.wait(5)
        raise OSError('injected writer failure')

    writer = OrderedWriter(path, history_id, duckdb.connect, fail, on_error=observed.append)
    rows = [('1991-01-30', 'new', 2.0)]
    writer.submit({'phase_metric_daily': rows}, {'phase_metric_current': rows}, {'1991-01-30'})
    later = [('1991-01-31', 'later', 3.0)]
    writer.submit({'phase_metric_daily': later}, {'phase_metric_current': later}, {'1991-01-31'})
    release.set()
    with pytest.raises(RuntimeError):
        writer.barrier()
    assert len(observed) == 1
    assert isinstance(writer.error, OSError)
    with pytest.raises(RuntimeError):
        writer.check()
    with pytest.raises(RuntimeError):
        writer.close()
    assert not writer.thread.is_alive()
    recovered = recover(path, history_id)
    assert [row[1:] for row in recovered['phase_metric_daily']] == [('new', 2.0), ('later', 3.0)]
    assert recovered['phase_metric_current'][0][1:] == ('later', 3.0)


def test_oversized_batch_uses_durable_synchronous_fallback(tmp_path, monkeypatch):
    from kojakstreet.core import persistence_writer
    store = EconomicDataStore(tmp_path / 'large-fallback.duckdb')
    store.enable_background_flush()
    rows = [('1991-01-30', 'large enough', 2.0)]
    store._pending_rows = {'phase_metric_daily': rows}
    store._current_rows = {'phase_metric_current': rows}
    store._pending_days = {'1991-01-30'}
    monkeypatch.setattr(persistence_writer, 'MAX_BATCH_BYTES', 32)
    try:
        store.flush(defer=True)
        assert store._writer.error is None
        assert store._writer.free.qsize() == 2
        assert store._connection.execute('SELECT phase FROM phase_metric_daily').fetchall() == [('large enough',)]
        assert not RowJournal(store.path, store._history_id, create=False).pending
    finally:
        store.close()


def test_journal_fsync_failure_cannot_acknowledge_or_drop_buffer(tmp_path, monkeypatch):
    from kojakstreet.core import persistence_writer
    store = EconomicDataStore(tmp_path / 'fsync.duckdb')
    store.enable_background_flush()
    rows = [('1991-01-30', 'unpublished', 2.0)]
    store._pending_rows = {'phase_metric_daily': rows}
    store._pending_days = {'1991-01-30'}
    native_fsync = persistence_writer.os.fsync
    monkeypatch.setattr(persistence_writer.os, 'fsync', lambda _fd: (_ for _ in ()).throw(OSError('injected fsync')))
    try:
        with pytest.raises(OSError, match='fsync'):
            store.flush(defer=True)
        assert store._pending_rows == {'phase_metric_daily': rows}
        with pytest.raises(RuntimeError):
            store.wait_for_persistence()
    finally:
        monkeypatch.setattr(persistence_writer.os, 'fsync', native_fsync)
        with pytest.raises(RuntimeError):
            store.close()
    reopened = EconomicDataStore(store.path)
    try:
        assert reopened._connection.execute('SELECT count(*) FROM phase_metric_daily').fetchone() == (0,)
    finally:
        reopened.close()


def test_failure_event_does_not_consume_a_command_response():
    from types import SimpleNamespace

    from kojakstreet.live_process import LiveSimulationProcess
    runtime = object.__new__(LiveSimulationProcess)
    runtime._responses = queue.Queue()
    runtime._stderr = []
    runtime._process = SimpleNamespace(stdout=io.StringIO(
        '{"event":"persistence_error","error":"disk failed"}\n'
        '{"id":"command","ok":true,"result":{}}\n'
    ))
    runtime._read_stdout()
    assert runtime.poll_persistence_error() == 'disk failed'
    assert runtime._responses.get_nowait()['id'] == 'command'
    assert runtime._responses.empty()


def test_startup_replay_failure_survives_a_connection_close_failure(tmp_path):
    path = tmp_path / 'startup-failure.duckdb'
    journal = RowJournal(path, 'history')
    journal.stage(0, RowBatch.freeze(1, 'history', {}, {}, set()))

    class BrokenConnection:
        def close(self):
            raise OSError('close also failed')

    def fail(_batch, _connection):
        raise OSError('replay failed')

    with pytest.raises(OSError, match='replay failed') as caught:
        OrderedWriter(path, 'history', lambda _path: BrokenConnection(), fail)
    assert 'close also failed' in caught.value.__notes__[0]
    assert len(RowJournal(path, 'history', create=False).pending) == 1
