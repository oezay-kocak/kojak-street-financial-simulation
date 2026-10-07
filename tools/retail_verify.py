"""Serial UI/performance evidence, then isolated full-suite and year verification."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/retail-decoupling"


def run(arguments):
    print("Verifying", " ".join(arguments), flush=True)
    subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-accounting", action="store_true")
    args = parser.parse_args()
    if not args.skip_accounting:
        run([
            "-m", "pytest", "tests/test_retail_boundary.py", "-k",
            "not world_and_rng_are_identical", "-q", "-o",
            "cache_dir=.cache/retail-decoupling/pytest-cache",
            "--basetemp=.cache/retail-decoupling/accounting-final",
            "--junitxml=.cache/retail-decoupling/accounting-final.xml",
        ])
    samples = (
        ("year", "1990-12-31", "2", "windows", "markets", "none", None),
        ("all-young", "1990-01-10", "27", "offscreen", None, "none", None),
        ("all-mature", "end", "27", "offscreen", None, "none", None),
        ("company-chart", "end", "6", "windows", "markets", "detail", None),
        ("company-overview", "end", "6", "windows", "markets", "detail", "overview"),
        ("company-supply", "end", "6", "windows", "markets", "detail", "supply"),
    )
    for label, checkpoint, days, display, view, chart, tab in samples:
        arguments = [
            "tools/zero_flicker_benchmark.py", "--label", "retail-final-" + label,
            "--checkpoint", checkpoint, "--days", days, "--display", display,
            "--chart", chart,
        ]
        if view:
            arguments += ["--view", view]
        if tab:
            arguments += ["--detail-tab", tab]
        run(arguments)
    run([
        "tools/visible_sync_navigation.py", "--label", "retail-final-navigation",
        "--checkpoint", "end", "--repeats", "2",
    ])
    run(["tools/retail_accounting_probe.py"])
    print("Starting full regression suite and final exact 365-day reference", flush=True)
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    tests = subprocess.Popen([
        sys.executable, "-m", "pytest", "-q", "-o",
        "cache_dir=.cache/retail-decoupling/pytest-cache",
        "--basetemp=.cache/retail-decoupling/full-final",
        "--junitxml=.cache/retail-decoupling/full-final.xml",
    ], cwd=ROOT, env=environment)
    year = subprocess.Popen([
        sys.executable, "tools/retail_validation.py", "no-player-final",
    ], cwd=ROOT, env=environment)
    codes = [tests.wait(), year.wait()]
    if any(codes):
        raise RuntimeError(f"Correctness verification failed: {codes}")
    before = json.loads((OUT / "no-player-before.json").read_text(encoding="utf-8"))
    after = json.loads((OUT / "no-player-final.json").read_text(encoding="utf-8"))
    comparison = {key: before[key] == after[key] for key in (
        "days", "checkpoints", "final_checkpoint", "database",
    )}
    (OUT / "no-player-final-comparison.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8",
    )
    assert all(comparison.values()), comparison
    print("Full suite and exact 365-day reference passed", flush=True)


if __name__ == "__main__":
    main()
