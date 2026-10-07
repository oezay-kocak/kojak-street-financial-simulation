"""Run final acceptance stages sequentially, preserving logs and exit codes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/performance-remediation'
STAGES = [
    ('step-after', ['tools/performance_remediation_benchmark.py', 'step-after']),
    ('full-tests', ['-m', 'pytest', '-q', '--junitxml=.cache/performance-remediation/final-tests.xml']),
    ('determinism-final', ['tools/performance_remediation_determinism.py', 'determinism-final']),
    ('determinism-compare', ['tools/performance_remediation_compare.py', 'determinism']),
    ('reaudit', ['tools/performance_remediation_benchmark.py', 'reaudit']),
    ('production-thread-control', ['tools/day_transition_audit_validation.py', 'production']),
    ('audit-record-validation', ['tools/day_transition_audit_validation.py', 'records']),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', choices=[name for name, _ in STAGES], default=STAGES[0][0])
    args = parser.parse_args()
    env = os.environ.copy()
    env['KOJAK_AUDIT_OUTPUT'] = str(OUT / 'reaudit')
    journal_path = OUT / 'final-stages.json'
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else []
    begin = next(i for i, (name, _) in enumerate(STAGES) if name == args.start)
    for name, command in STAGES[begin:]:
        print('START', name, flush=True)
        started = time.perf_counter()
        with (OUT / f'{name}-run.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-X', 'utf8', *command], cwd=ROOT,
                                       env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding='utf-8')
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end='', flush=True)
            code = process.wait()
        journal.append({'stage': name, 'seconds': time.perf_counter() - started,
                        'exit_code': code, 'command': command})
        journal_path.write_text(json.dumps(journal, indent=2), encoding='utf-8')
        if code:
            raise SystemExit(code)
        print('COMPLETE', name, flush=True)


if __name__ == '__main__':
    main()
