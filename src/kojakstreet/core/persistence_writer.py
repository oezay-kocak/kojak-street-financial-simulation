"""Durable bounded row journal and the sole ordered analytical SQL owner."""
from __future__ import annotations

import hashlib
import json
import os
import queue
import threading
import time
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path

HEADER_BYTES = 4096
MAX_BATCH_BYTES = 64 * 1024 * 1024


class BatchTooLarge(ValueError):
    """The caller must drain and persist this batch synchronously."""


@dataclass(frozen=True)
class RowBatch:
    sequence: int
    history_id: str
    pending: tuple
    current: tuple
    days: tuple

    @classmethod
    def freeze(cls, sequence, history_id, pending, current, days):
        # Rows contain schema scalars, never assets, arrays or world references.
        def frozen(tables):
            result = []
            for table, rows in tables.items():
                immutable = tuple(tuple(row) for row in rows)
                if any(type(value) not in (str, int, float, type(None)) for row in immutable for value in row):
                    raise TypeError('Persistence rows must contain immutable schema scalars')
                result.append((table, immutable))
            return tuple(result)
        return cls(sequence, history_id, frozen(pending), frozen(current), tuple(sorted(days)))

    def encode(self):
        payload = json.dumps({
            'sequence': self.sequence, 'history_id': self.history_id,
            'pending': self.pending, 'current': self.current, 'days': self.days,
        }, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        if len(payload) > MAX_BATCH_BYTES:
            raise BatchTooLarge('Persistence batch exceeds the bounded journal capacity')
        return payload

    @classmethod
    def decode(cls, payload):
        value = json.loads(payload)
        return cls.freeze(value['sequence'], value['history_id'], dict(value['pending']),
                          dict(value['current']), value['days'])


class RowJournal:
    """Two reusable files; complete header is fsynced before publication.

    Payload is flushed while the slot is EMPTY, then the PENDING header is
    written and flushed. After DuckDB COMMIT, EMPTY is flushed before reuse.
    A torn/corrupt header or checksum is surfaced, never guessed or ignored.
    Both files stay in place: reclamation does not depend on durable unlink.
    """
    def __init__(self, path: Path, history_id: str, *, create=True):
        self.paths = [Path(str(path) + f'.row-journal-{index}') for index in range(2)]
        existing = [slot.exists() for slot in self.paths]
        if any(existing) and not all(existing):
            raise ValueError('Incomplete persistence journal: a durable slot is missing')
        self.history_id = history_id
        self.sequence = 0
        self.lock = threading.Lock()
        self.pending = []
        for index, slot in enumerate(self.paths):
            if not slot.exists():
                if create:
                    with slot.open('xb') as stream:
                        self.header(stream, {'version': 1, 'state': 'empty', 'sequence': 0,
                                             'history_id': history_id})
                continue
            with slot.open('rb') as stream:
                raw = stream.read(HEADER_BYTES).rstrip(b'\0')
                try:
                    value = json.loads(raw)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise ValueError('Corrupt persistence journal header') from exc
                if value.get('version') != 1 or value.get('history_id') != history_id:
                    raise ValueError('Persistence journal belongs to another history/version')
                self.sequence = max(self.sequence, int(value['sequence']))
                if value['state'] == 'empty':
                    continue
                if value['state'] != 'pending' or not 0 < value['bytes'] <= MAX_BATCH_BYTES:
                    raise ValueError('Invalid persistence journal state/length')
                payload = stream.read(value['bytes'])
                if len(payload) != value['bytes'] or hashlib.sha256(payload).hexdigest() != value['sha256']:
                    raise ValueError('Corrupt persistence journal payload')
                batch = RowBatch.decode(payload)
                if batch.sequence != value['sequence'] or batch.history_id != history_id:
                    raise ValueError('Persistence journal identity mismatch')
                self.pending.append((index, batch))
        self.pending.sort(key=lambda item: item[1].sequence)
        sequences = [batch.sequence for _, batch in self.pending]
        if len(sequences) != len(set(sequences)):
            raise ValueError('Duplicate persistence journal sequence')

    @staticmethod
    def header(stream, value):
        encoded = json.dumps(value, separators=(',', ':')).encode('utf-8')
        if len(encoded) > HEADER_BYTES:
            raise ValueError('Journal header overflow')
        stream.seek(0)
        stream.write(encoded.ljust(HEADER_BYTES, b'\0'))
        stream.flush()
        os.fsync(stream.fileno())

    def stage(self, slot, batch):
        started = time.perf_counter()
        payload = batch.encode()
        with self.lock, self.paths[slot].open('r+b') as stream:
            stream.seek(HEADER_BYTES)
            stream.write(payload)
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())
            self.header(stream, {'version': 1, 'state': 'pending', 'sequence': batch.sequence,
                                 'history_id': batch.history_id, 'bytes': len(payload),
                                 'sha256': hashlib.sha256(payload).hexdigest()})
        return {'handoff_ms': (time.perf_counter() - started) * 1000, 'bytes': len(payload)}

    def acknowledge(self, slot, sequence):
        with self.lock, self.paths[slot].open('r+b') as stream:
            self.header(stream, {'version': 1, 'state': 'empty', 'sequence': sequence,
                                 'history_id': self.history_id})


class OrderedWriter:
    """The only owner of a DuckDB connection; queries are ordered barriers too."""
    def __init__(self, path, history_id, connect, apply, on_error=None):
        self.path = Path(path)
        self.journal = RowJournal(self.path, history_id)
        self.apply = apply
        self.on_error = on_error
        self.jobs = queue.Queue(maxsize=3)
        self.free = queue.Queue(maxsize=2)
        self.error = None
        self.metrics = deque(maxlen=128)
        self.thread_id = None
        self.raw = None
        self.closed = False
        self.ready = Future()
        self.thread = threading.Thread(target=self.run, args=(connect,), name='ordered-persistence', daemon=False)
        self.thread.start()
        self.ready.result()

    def check(self):
        if self.error is not None:
            raise RuntimeError('Persistence writer failed; durable row journal retained for recovery') from self.error
        if self.closed:
            raise RuntimeError('Persistence writer is closed')

    def run(self, connect):
        self.thread_id = threading.get_ident()
        try:
            self.raw = connect(str(self.path))
            for slot, batch in self.journal.pending:
                self.apply(batch, self.raw)
                self.journal.acknowledge(slot, batch.sequence)
            for slot in range(2):
                self.free.put(slot)
            self.ready.set_result(None)
        except BaseException as exc:  # noqa: BLE001 -- always release/wake callers on owner failure
            self.error = exc
            if self.raw is not None:
                try:
                    self.raw.close()
                except Exception as close_error:  # noqa: BLE001 -- preserve the startup failure
                    exc.add_note(f'Closing failed persistence connection: {close_error!r}')
            self.ready.set_exception(exc)
            return
        while True:
            kind, value, future = self.jobs.get()
            try:
                if kind == 'close':
                    self.raw.close()
                    future.set_result(None)
                    return
                if self.error is not None:
                    raise RuntimeError('Persistence owner stopped after a failed batch') from self.error
                if kind == 'batch':
                    slot, batch, metric = value
                    started = time.perf_counter()
                    self.apply(batch, self.raw)
                    metric.update(writer_ms=(time.perf_counter() - started) * 1000,
                                  committed_at=time.perf_counter(), sequence=batch.sequence)
                    self.journal.acknowledge(slot, batch.sequence)
                    self.metrics.append(metric)
                    self.free.put(slot)
                else:
                    future.set_result(value(self.raw))
            except BaseException as exc:  # noqa: BLE001 -- always release/wake callers on owner failure
                if kind == 'close':
                    future.set_exception(exc)
                    return
                if kind == 'batch':
                    first_failure = self.error is None
                    if first_failure:
                        self.error = exc
                    self.metrics.append({**value[2], 'sequence': value[1].sequence, 'error': repr(exc)})
                    if first_failure and self.on_error:
                        try:
                            self.on_error(exc)
                        except Exception:  # noqa: BLE001, S110 -- original failure stays latched; reporting cannot strand callers
                            pass
                elif future is not None:
                    future.set_exception(exc)
            finally:
                self.jobs.task_done()

    def submit(self, pending, current, days):
        self.check()
        started = time.perf_counter()
        while True:
            try:
                slot = self.free.get(timeout=0.05)
                break
            except queue.Empty:
                self.check()
        slot_at = time.perf_counter()
        self.check()
        self.journal.sequence += 1
        try:
            batch = RowBatch.freeze(self.journal.sequence, self.journal.history_id, pending, current, days)
        except BaseException:
            self.journal.sequence -= 1
            self.free.put(slot)
            raise
        frozen_at = time.perf_counter()
        try:
            metric = self.journal.stage(slot, batch)
        except BatchTooLarge:
            self.journal.sequence -= 1
            self.free.put(slot)
            raise
        except BaseException:
            # No published acknowledgement. Do not reuse an ambiguous header.
            self.error = RuntimeError('Durable row-journal handoff failed')
            raise
        metric.update(backpressure_ms=(time.perf_counter() - started) * 1000 - metric['handoff_ms'],
                      queue_wait_ms=(slot_at - started) * 1000,
                      freeze_ms=(frozen_at - slot_at) * 1000,
                      queued_at=time.perf_counter(), rows=sum(len(rows) for _, rows in batch.pending),
                      queue_depth=2 - self.free.qsize())
        self.jobs.put(('batch', (slot, batch, metric), None))
        self.check()
        return metric

    def call(self, function):
        if threading.get_ident() == self.thread_id:
            return function(self.raw)
        self.check()
        future = Future()
        self.jobs.put(('call', function, future))
        return future.result()

    def barrier(self):
        self.call(lambda _raw: None)

    def close(self):
        if self.closed:
            return
        future = Future()
        self.jobs.put(('close', None, future))
        try:
            future.result()
        finally:
            self.thread.join()
            self.closed = True
        if self.error:
            raise RuntimeError('Persistence writer closed with unreplayed durable batches') from self.error


class OrderedConnection:
    """Materialize a result atomically, so queued work cannot overwrite it."""
    def __init__(self, writer):
        self.writer, self.result = writer, deque()

    def execute(self, sql, *args, **kwargs):
        if threading.get_ident() == self.writer.thread_id:
            return self.writer.raw.execute(sql, *args, **kwargs)
        self.result = deque(self.writer.call(lambda raw: raw.execute(sql, *args, **kwargs).fetchall()))
        return self

    def executemany(self, sql, *args, **kwargs):
        if threading.get_ident() == self.writer.thread_id:
            return self.writer.raw.executemany(sql, *args, **kwargs)
        self.result = deque(self.writer.call(lambda raw: raw.executemany(sql, *args, **kwargs).fetchall()))
        return self

    def fetchone(self):
        return self.result.popleft() if self.result else None

    def fetchall(self):
        rows = list(self.result)
        self.result.clear()
        return rows

    def fetchmany(self, size=1):
        return [self.result.popleft() for _ in range(min(size, len(self.result)))]

    def close(self):
        self.writer.close()
