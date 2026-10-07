"""Native cadence with separate, truthful ordered-writer evidence."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/flush-remediation'
SOURCE = Path(os.environ.get('KOJAK_AUDIT_PROJECT_ROOT', ROOT)).resolve()
sys.path[:0] = [str(SOURCE / 'src'), str(SOURCE), str(ROOT / 'tools')]


def main():
    import max_performance_benchmark as driver

    driver.__file__ = __file__
    if len(sys.argv) > 1 and sys.argv[1] == 'worker':
        import threading
        from contextlib import contextmanager
        from functools import wraps

        import day_transition_audit_support as audit

        from kojakstreet import live_worker
        from kojakstreet.core.data_store import EconomicDataStore

        audit.install()
        # The old store hooks also access ACTIVE outside their timed span.
        # Bypass the entire observer on the SQL owner, including that access.
        def dispatch(main, production):
            @wraps(main)
            def call(*args, **kwargs):
                return (production if threading.current_thread().name == 'ordered-persistence' else main)(*args, **kwargs)
            return call

        for name, function in list(vars(EconomicDataStore).items()):
            if getattr(function, '_audit_wrapped', False):
                setattr(EconomicDataStore, name, dispatch(function, function.__wrapped__))
        inserted = EconomicDataStore._insert_rows
        captured = dict(zip(inserted.__code__.co_freevars,
                            (cell.cell_contents for cell in inserted.__closure__)))
        EconomicDataStore._insert_rows = dispatch(inserted, captured['original_insert'])

        original_load, original_execute = live_worker._load_runtime, live_worker._execute
        original_span = audit.span

        @contextmanager
        def main_span(label):
            # Legacy observers assumed sequential execution and finalize their
            # mutable dictionaries at publication. Background spans have their
            # own durable-writer metrics; never append to a finalized GUI row.
            if threading.current_thread().name == 'ordered-persistence':
                yield
            else:
                with original_span(label):
                    yield

        audit.span = main_span
        observed = []

        def load(*args, **kwargs):
            runtime = original_load(*args, **kwargs)
            if os.environ.get('KOJAK_FLUSH_INTERVAL'):
                runtime.data_store.flush_interval_days = int(os.environ['KOJAK_FLUSH_INTERVAL'])
            observed.append(runtime.data_store)
            return runtime

        def execute(runtime, command, arguments):
            result = original_execute(runtime, command, arguments)
            writer = getattr(runtime.data_store, '_writer', None)
            if audit.ACTIVE is not None and writer is not None:
                audit.ACTIVE['persistence_writer'] = {
                    'queue_depth': 2 - writer.free.qsize(),
                    'sequence': writer.journal.sequence,
                    'metrics': [dict(value) for value in writer.metrics],
                    'error': repr(writer.error) if writer.error else None,
                }
            return result

        live_worker._load_runtime, live_worker._execute = load, execute
        try:
            driver.worker()
        finally:
            output = Path(sys.argv[sys.argv.index('--output') + 1])
            data = [{'metrics': [dict(value) for value in store._writer.metrics],
                     'closed': store._writer.closed, 'error': repr(store._writer.error) if store._writer.error else None,
                     'journal_bytes': sum(path.stat().st_size for path in store._writer.journal.paths)}
                    for store in observed if getattr(store, '_writer', None) is not None]
            (OUT / (output.stem + '-writer.json')).write_text(json.dumps(data, indent=2), encoding='utf-8')
    else:
        driver.benchmark()


if __name__ == '__main__':
    main()
