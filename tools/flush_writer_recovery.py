"""Full-size native crash/recovery comparison; control parallel AVG nondeterminism."""
import argparse
import json
import pickle
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/flush-remediation'
sys.path[:0] = [str(ROOT / 'src'), str(ROOT), str(ROOT / 'tools')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='large-crash-recovery')
    args = parser.parse_args()
    import duckdb
    from flush_remediation_compare import signature

    from kojakstreet.core.data_store import EconomicDataStore
    from kojakstreet.core.persistence_writer import RowJournal

    native_connect = duckdb.connect

    def controlled_connect(*args, **kwargs):
        connection = native_connect(*args, **kwargs)
        connection.execute('SET threads=1')
        return connection

    with (OUT / 'flush-rows.pickle').open('rb') as stream:
        rows = pickle.load(stream)
    baseline = OUT / (args.label + '-control.duckdb')
    assert not baseline.exists()
    shutil.copy2(OUT / 'before-flush.duckdb', baseline)
    with patch.object(duckdb, 'connect', controlled_connect):
        store = EconomicDataStore(baseline)
        store._pending_rows = defaultdict(list, rows['pending_rows'])
        store._pending_days = rows['pending_days']
        store._current_rows = rows['current_rows']
        store.flush()
        store.close()
    expected = signature(baseline)
    results = {}
    for stage in ('before_transaction', 'during_copy', 'before_commit', 'during_commit', 'after_commit', 'after_ack'):
        path = OUT / f'{args.label}-{stage}.duckdb'
        assert not path.exists()
        shutil.copy2(OUT / 'before-flush.duckdb', path)
        result = subprocess.run([
            sys.executable, str(ROOT / 'tools/flush_writer_probe.py'), '--crash', stage,
            '--database', str(path), '--large', '--backend-threads', '1',
        ], cwd=ROOT, capture_output=True, text=True, check=False, timeout=90)
        assert result.returncode == 91, result.stderr
        with patch.object(duckdb, 'connect', controlled_connect):
            store = EconomicDataStore(path)  # Production automatic journal recovery.
            history_id = store._history_id
            store.close()
        actual = signature(path)
        different = [table for table in expected if expected[table] != actual.get(table)]
        assert not RowJournal(path, history_id, create=False).pending
        results[stage] = {'exact': not different, 'different_tables': different,
                          'rows': sum(value['rows'] for value in actual.values()),
                          'tables': len(actual), 'exit_code': result.returncode}
        print(stage, results[stage], flush=True)
        (OUT / (args.label + '.json')).write_text(json.dumps({
            'backend_threads_for_both_sides': 1,
            'reason': 'Unmodified baseline has nonrepeatable parallel annual AVG; no tolerance or normalization.',
            'results': results,
        }, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
