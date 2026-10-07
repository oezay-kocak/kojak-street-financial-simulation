"""Serial native measurements keep correctness jobs out of timing runs."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    reference = sys.argv[1] == "reference"
    if reference:
        runs = [
            ("max-before-young", "1990-01-10", 12, []),
            ("max-before-company-chart", "end", 6, ["--chart", "detail"]),
            ("max-before-company-overview", "end", 6, ["--chart", "detail", "--detail-tab", "overview"]),
            ("max-before-company-supply", "end", 6, ["--chart", "detail", "--detail-tab", "supply"]),
            ("max-stacks-before", "end", 3, ["--stacks"]),
        ]
    else:
        runs = [
            ("max-final-mature", "end", 40, []),
            ("max-final-young", "1990-01-10", 20, []),
            ("max-final-company-chart", "end", 6, ["--chart", "detail"]),
            ("max-final-company-overview", "end", 6, ["--chart", "detail", "--detail-tab", "overview"]),
            ("max-final-company-supply", "end", 6, ["--chart", "detail", "--detail-tab", "supply"]),
            ("max-final-all-young", "1990-01-10", 27, ["all"]),
            ("max-final-all-mature", "end", 27, ["all"]),
            ("max-final-year", "1990-12-31", 2, []),
            ("max-profile-final", "end", 40, ["--profile"]),
            ("max-profile-year", "1990-12-31", 2, ["--profile"]),
            ("max-stacks-final", "end", 3, ["--stacks"]),
            ("max-allocations-final", "end", 3, ["--trace-ui", "--trace-worker"]),
        ]
    env = os.environ.copy()
    if reference:
        env["KOJAK_AUDIT_PROJECT_ROOT"] = str(ROOT / ".cache/max-performance/baseline")
    else:
        env.pop("KOJAK_AUDIT_PROJECT_ROOT", None)
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    for label, checkpoint, days, extra in runs[start:]:
        command = [
            sys.executable, str(ROOT / "tools/max_performance_benchmark.py"),
            "--label", label, "--checkpoint", checkpoint, "--days", str(days),
            "--display", "windows",
        ]
        if "all" not in extra:
            command += ["--view", "markets", *extra]
        print("Starting", label, flush=True)
        subprocess.run(command, cwd=ROOT, env=env, check=True)
    if not reference:
        subprocess.run([
            sys.executable, str(ROOT / "tools/visible_sync_navigation.py"),
            "--label", "max-final-navigation", "--checkpoint", "end", "--repeats", "2",
        ], cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
