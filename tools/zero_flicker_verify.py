"""Serial performance samples, followed by independent isolated correctness runs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    samples = (
        ("zero-final-native-mature", "end", "40", "windows", "markets", "none"),
        ("zero-final-native-young", "1990-01-10", "20", "windows", "markets", "none"),
        ("zero-final-year", "1990-12-31", "2", "windows", "markets", "none"),
        ("zero-final-all-young", "1990-01-10", "27", "offscreen", None, "none"),
        ("zero-final-all-mature", "end", "27", "offscreen", None, "none"),
        ("zero-final-company-chart", "end", "6", "windows", "markets", "detail"),
    )
    for label, checkpoint, days, display, view, chart in samples:
        command = [
            sys.executable,
            "tools/zero_flicker_benchmark.py",
            "--label",
            label,
            "--checkpoint",
            checkpoint,
            "--days",
            days,
            "--display",
            display,
            "--chart",
            chart,
        ]
        if view:
            command += ["--view", view]
        print("Measuring", label, flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    print("Running full suite and 365-day deterministic comparison", flush=True)
    tests = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--basetemp",
            ".cache/precompute-audit/full-final",
            "--junitxml",
            ".cache/precompute-audit/full-final.xml",
        ],
        cwd=ROOT,
        env=environment,
    )
    deterministic = subprocess.Popen(
        [sys.executable, "tools/visible_sync_validation.py", "--label", "zero-final-determinism"],
        cwd=ROOT,
        env=environment,
    )
    codes = [tests.wait(), deterministic.wait()]
    if any(codes):
        raise RuntimeError(f"Correctness validation failed: {codes}")
    print("All performance and correctness runs completed", flush=True)


if __name__ == "__main__":
    main()
