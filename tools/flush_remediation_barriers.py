"""Native backend Save/Load and shutdown latency, with actual queued SQL work."""
import argparse
import json
import os
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/flush-remediation'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--reference', action='store_true')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--modes', nargs='+', choices=('idle', 'active', 'queued'),
                        default=('idle', 'active', 'queued'))
    args = parser.parse_args()
    source = OUT / 'baseline' if args.reference else ROOT
    os.environ['KOJAK_AUDIT_PROJECT_ROOT'] = str(source)
    sys.path[:0] = [str(source / 'src'), str(source), str(ROOT / 'tools')]
    from day_transition_audit import make_runtime

    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, restore
    from kojakstreet.live_process import economic_signature

    prepared = make_runtime(OUT / (args.label + '-prepare'), 'end')
    prepared.data_store.auto_flush = False
    for _ in range(30):
        prepared.advance_day()
    store = prepared.data_store
    pending = {name: tuple(rows) for name, rows in store._pending_rows.items()}
    current = {name: tuple(rows) for name, rows in store._current_rows.items()}
    days = set(store._pending_days)
    session = {name: tuple(rows) for name, rows in store._session_rows.items()}
    payload = capture(prepared.daten)
    store._connection.execute('CHECKPOINT')
    store._connection.close()
    store._connection = None
    base = OUT / (args.label + '-base.duckdb')
    assert not base.exists()
    shutil.copy2(store.path, base)
    prepared.close()
    results = []
    for mode in args.modes:
        for repetition in range(args.repeats):
            directory = OUT / f'{args.label}-{mode}-{repetition}'
            assert not directory.exists()
            directory.mkdir()
            shutil.copy2(base, directory / 'kojakstreet.duckdb')
            runtime = IntegratedRuntime(source, data_dir=directory, seed=1729)
            store = runtime.data_store
            restore(runtime.daten, payload)
            runtime.state.sync_from_legacy()
            runtime.market.warm_runtime_indexes()
            store.auto_flush = False
            store._pending_rows = defaultdict(list, {name: list(rows) for name, rows in pending.items()})
            store._current_rows = {name: list(rows) for name, rows in current.items()}
            store._pending_days = set(days)
            store._session_rows = defaultdict(list, {name: list(rows) for name, rows in session.items()})
            if not args.reference:
                store.enable_background_flush()
            try:
                if mode == 'idle':
                    store.flush()
                elif not args.reference:
                    store.flush(defer=True)
                    if mode == 'queued':
                        runtime.advance_day()
                        store.flush(defer=True)
                elif mode == 'queued':
                    runtime.advance_day()
                row = {'mode': mode, 'repetition': repetition,
                       'depth_before_save': 2 - store._writer.free.qsize() if not args.reference else 0}
                if mode == 'queued' and not args.reference:
                    assert row['depth_before_save'] == 2
                started = time.perf_counter()
                runtime.save_game()
                row['save_ms'] = (time.perf_counter() - started) * 1000
                saved = economic_signature(runtime.daten)
                started = time.perf_counter()
                runtime.load_game()
                row['load_ms'] = (time.perf_counter() - started) * 1000
                assert economic_signature(runtime.daten) == saved
                row['immediate_load_exact'] = True
                if mode != 'idle' and not args.reference:
                    store.flush(defer=True)
                    if mode == 'queued':
                        runtime.advance_day()
                        store.flush(defer=True)
                row['depth_before_shutdown'] = 2 - store._writer.free.qsize() if not args.reference else 0
                if mode == 'queued' and not args.reference:
                    assert row['depth_before_shutdown'] == 2
                started = time.perf_counter()
                runtime.close()
                row['shutdown_ms'] = (time.perf_counter() - started) * 1000
                if not args.reference:
                    row['metrics'] = [dict(metric) for metric in store._writer.metrics]
                    assert store._writer.closed and not store._writer.error
                results.append(row)
                print(args.label, mode, repetition, round(row['save_ms'], 2),
                      round(row['shutdown_ms'], 2), flush=True)
            finally:
                runtime.close()
    (OUT / (args.label + '.json')).write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
