import json
import statistics
from pathlib import Path
import day_transition_audit_summary as aggregate

root = Path(__file__).resolve().parents[1] / '.cache/performance-remediation'
for label in ('step-before', 'step-after'):
    path = root / label / 'qt-manual-step-valid.json'
    if not path.exists():
        continue
    result = aggregate.load_run(path)
    rows = result['rows']
    print(label)
    for key in ('total_ms', 'simulation_ms', 'persistence_transfer_ms', 'model_ms', 'paint_wait_ms',
                'heartbeat_max_ms', 'parent_gc_ms', 'response_bytes'):
        print(key, round(statistics.median(r[key] for r in rows), 2))
    for key in sorted({key for row in rows for key in row['spans']}):
        value = statistics.median(r['spans'].get(key, 0) for r in rows)
        if value > 3:
            print(key, round(value, 2))
