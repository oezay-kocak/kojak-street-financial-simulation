"""Sequential clean diagnostics, deterministic reference and real Step baseline."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.cache/performance-remediation'
for label in ('before','after'):
    source=OUT/f'duckdb-{label}'
    target=OUT/f'duckdb-{label}-exploratory-close-counter'
    source.resolve().relative_to(ROOT.resolve())
    target.resolve().relative_to(ROOT.resolve())
    if target.exists():raise RuntimeError(f'Archive already exists: {target}')
    source.rename(target)
jobs=[
    ['tools/performance_remediation_duckdb.py','before'],
    ['tools/performance_remediation_duckdb.py','after'],
    ['tools/performance_remediation_duckdb_summary.py'],
    ['tools/performance_remediation_determinism.py','determinism-reference','--reference'],
    ['tools/performance_remediation_benchmark.py','step-before'],
]
for job in jobs:
    print('START',job,flush=True)
    subprocess.run([sys.executable,'-X','utf8',*job],cwd=ROOT,check=True)
