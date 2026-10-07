"""Validate the frozen final source, then rerun final acceptance and Step latency."""
import hashlib
import json

import performance_remediation_final as runner


def verify_source():
    manifest = json.loads((runner.OUT / 'release-source-manifest.json').read_text())
    differences = [name for name, expected in manifest.items()
                   if hashlib.sha256((runner.ROOT / name).read_bytes()).hexdigest() != expected]
    assert not differences, differences


if __name__ == '__main__':
    preliminary = json.loads((runner.OUT / 'reaudit/qt-year-clean-valid.json').read_text())
    assert preliminary['finished'] and not preliminary['errors']
    assert preliminary['signature'] == json.loads((runner.OUT / 'reaudit/headless-year-clean.json').read_text())['signature']
    verify_source()
    source = (runner.OUT / 'reaudit').resolve()
    archive = (runner.OUT / 'reaudit-exploratory-delta-gc').resolve()
    assert source.is_relative_to(runner.OUT.resolve()) and archive.is_relative_to(runner.OUT.resolve())
    assert not archive.exists()
    source.rename(archive)
    runner.STAGES = [
        ('full-tests-final', ['-m', 'pytest', '-q', '--junitxml=.cache/performance-remediation/final-tests.xml']),
        ('reaudit-final', ['tools/performance_remediation_benchmark.py', 'reaudit']),
        ('production-thread-final', ['tools/day_transition_audit_validation.py', 'production']),
        ('reaudit-validation-final', ['tools/day_transition_audit_validation.py', 'records']),
        ('step-after-final', ['tools/performance_remediation_benchmark.py', 'step-after']),
        ('final-report', ['tools/performance_remediation_report.py']),
    ]
    runner.main()
    verify_source()
