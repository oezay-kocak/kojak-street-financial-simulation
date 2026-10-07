"""Measure the production writer on durable cloned analytical data and rows only."""
import argparse
import json
import pickle
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/flush-remediation'
sys.path[:0] = [str(ROOT / 'src'), str(ROOT), str(ROOT / 'tools')]

from tools.process_crash import crash_exit


def apply_batch(batch, connection):
    from kojakstreet.core.data_store import EconomicDataStore
    return EconomicDataStore._write_row_batch(batch, connection)


def main():
    import duckdb
    from day_transition_audit_support import rss_bytes

    from kojakstreet.core.data_store import EconomicDataStore
    from kojakstreet.core.persistence_writer import OrderedWriter

    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='writer-prototype')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--crash', choices=('before_transaction', 'during_copy', 'before_commit', 'during_commit', 'after_commit', 'after_ack'))
    parser.add_argument('--database', type=Path)
    parser.add_argument('--large', action='store_true')
    parser.add_argument('--backend-threads', type=int)
    args = parser.parse_args()
    if args.crash:
        import threading
        store = EconomicDataStore(args.database)
        history_id = store._history_id
        store._connection.close()

        class CrashConnection:
            def __init__(self, raw):
                self.raw = raw

            def __getattr__(self, key):
                return getattr(self.raw, key)

            def execute(self, sql, *values, **kwargs):
                command = sql.strip().split()[0].upper()
                if (args.crash == 'before_transaction' and command == 'BEGIN') or (args.crash == 'before_commit' and command == 'COMMIT'):
                    crash_exit()
                if args.crash == 'during_commit' and command == 'COMMIT':
                    threading.Timer(0.05 if args.large else 0.001, crash_exit).start()
                if args.crash == 'during_copy' and args.large and command == 'COPY':
                    threading.Timer(0.001, crash_exit).start()
                result = self.raw.execute(sql, *values, **kwargs)
                if (args.crash == 'during_copy' and command == 'COPY') or (args.crash == 'after_commit' and command == 'COMMIT'):
                    crash_exit()
                return self if result is self.raw else result

        def crash_connect(path):
            connection = duckdb.connect(path)
            if args.backend_threads:
                connection.execute(f'SET threads={args.backend_threads}')
            return CrashConnection(connection)
        writer = OrderedWriter(args.database, history_id, crash_connect, apply_batch)
        if args.large:
            with (OUT / 'flush-rows.pickle').open('rb') as stream:
                rows = pickle.load(stream)
        else:
            pending = [('1991-01-30', 'new', 2.0)]
            rows = {'pending_rows': {'phase_metric_daily': pending},
                    'current_rows': {'phase_metric_current': pending}, 'pending_days': {'1991-01-30'}}
        writer.submit(rows['pending_rows'], rows['current_rows'], rows['pending_days'])
        writer.barrier()
        crash_exit()
    with (OUT / 'flush-rows.pickle').open('rb') as stream:
        rows = pickle.load(stream)
    results = []
    for index in range(args.repeats):
        path = OUT / f'{args.label}-{index}.duckdb'
        assert not path.exists()
        shutil.copy2(OUT / 'before-flush.duckdb', path)
        store = EconomicDataStore(path)
        history_id = store._history_id
        store._connection.close()
        store._connection = None
        writer = OrderedWriter(path, history_id, duckdb.connect, apply_batch)
        started, rss_before = time.perf_counter(), rss_bytes()
        metric = writer.submit(rows['pending_rows'], rows['current_rows'], rows['pending_days'])
        visible_at = time.perf_counter()
        rss_handoff = rss_bytes()
        writer.barrier()
        result = {'handoff_ms': (visible_at - started) * 1000,
                  'total_ms': (time.perf_counter() - started) * 1000,
                  'rss_before': rss_before, 'rss_handoff': rss_handoff,
                  'rss_done': rss_bytes(), 'metric': dict(writer.metrics[-1]),
                  'journal_bytes': sum(path.stat().st_size for path in writer.journal.paths)}
        results.append(result)
        writer.close()
        print(args.label, index, round(result['handoff_ms'], 2), round(result['total_ms'], 2), metric['bytes'], flush=True)
    (OUT / (args.label + '.json')).write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
