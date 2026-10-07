"""Isolated deterministic validation through the production visible worker path."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]
from performance_remediation_determinism import current_signature, database_signature, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--label", default="determinism")
    args = parser.parse_args()
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture
    from kojakstreet.live_worker import _execute
    from kojakstreet.visible_state import VIEWS

    output = ROOT / ".cache/visible-ui-sync"
    if not args.label.replace("-", "").isalnum():
        raise ValueError("Use an alphanumeric validation label")
    directory = output / f"{args.label}-world"
    if directory.exists():
        raise RuntimeError("Refusing to reuse a deterministic evidence directory")
    runtime = IntegratedRuntime(ROOT, data_dir=directory, seed=1729)
    result = {"source": str(ROOT), "seed": 1729, "days": [], "checkpoints": {}}
    views = sorted(VIEWS)
    try:
        for day in range(args.days):
            scope = {"view": views[day % len(views)]}
            if scope["view"] == "markets":
                scope["selection"] = {
                    "kind": "Stock",
                    "ticker": list(runtime.daten.aktien)[900],
                    "tab": ("overview", "supply", "chart")[(day // len(views)) % 3],
                }
            elif scope["view"] == "macro":
                scope["selection"] = {"region": next(iter(runtime.daten.makro)),
                                      "tab": (day // len(views)) % 4}
            _execute(runtime, "advance", {"steps": 1, "scope": scope})
            result["days"].append(current_signature(runtime))
            if day + 1 in {15, 31, 181, 365}:
                result["checkpoints"][str(day + 1)] = digest(capture(runtime.daten))
            if (day + 1) % 30 == 0:
                print("visible worker", day + 1, flush=True)
        result["final_checkpoint"] = digest(capture(runtime.daten))
        runtime.data_store.flush()
        result["database"] = database_signature(runtime)
        (output / f"{args.label}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        baseline = json.loads(
            (ROOT / ".cache/performance-remediation/determinism-final.json").read_text()
        )
        comparison = {
            key: result[key] == baseline[key]
            for key in ("days", "checkpoints", "final_checkpoint", "database")
        }
        (output / f"{args.label}-comparison.json").write_text(json.dumps(comparison, indent=2))
        assert all(comparison.values()), comparison
        print("365-day world, RNG, checkpoints and database exact", flush=True)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
