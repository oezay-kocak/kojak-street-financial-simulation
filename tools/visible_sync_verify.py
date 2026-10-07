"""Run final performance samples serially, then the full regression suite."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    samples = (
        ("final-all-young", "1990-01-10", "27", "offscreen", None),
        ("final-all-mature", "end", "27", "offscreen", None),
        ("final-native-young", "1990-01-10", "20", "windows", "markets"),
        ("final-year-boundary", "1990-12-31", "2", "windows", "markets"),
        ("final-native-mature", "end", "40", "windows", "markets"),
    )
    for label, checkpoint, days, display, view in samples:
        command = [
            sys.executable,
            "tools/visible_sync_benchmark.py",
            "--label",
            label,
            "--checkpoint",
            checkpoint,
            "--days",
            days,
            "--display",
            display,
        ]
        if view:
            command += ["--view", view]
        print("Validating", label, flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    print("Running full regression suite", flush=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "cache_dir=.cache/visible-ui-sync/pytest-cache",
            "--basetemp",
            ".cache/visible-ui-sync/full-final",
            "--junitxml",
            ".cache/visible-ui-sync/full-final.xml",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )


if __name__ == "__main__":
    main()
