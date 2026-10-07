"""Exact isolated no-player reference for the retail boundary pass."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/retail-decoupling"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()
    source = OUT / "baseline" if args.reference else ROOT
    sys.path[:0] = [str(source / "src"), str(source), str(ROOT / "tools")]
    from performance_remediation_determinism import current_signature, database_signature, digest

    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture

    directory = OUT / (args.label + "-world")
    if directory.exists():
        raise RuntimeError("Use a fresh evidence label")
    runtime = IntegratedRuntime(source, data_dir=directory, seed=1729)
    result = {"source": str(source), "days": [], "checkpoints": {}}
    try:
        for day in range(1, args.days + 1):
            runtime.advance_day()
            result["days"].append(current_signature(runtime))
            if day in {15, 31, 181, 365}:
                payload = capture(runtime.daten)
                result["checkpoints"][str(day)] = digest(
                    {"checkpoint": payload["checkpoint"], "rng": payload["rng"]}
                )
            if day % 30 == 0:
                print(args.label, day, flush=True)
        payload = capture(runtime.daten)
        result["final_checkpoint"] = digest(
            {"checkpoint": payload["checkpoint"], "rng": payload["rng"]}
        )
        runtime.data_store.flush()
        result["database"] = database_signature(runtime)
        (OUT / (args.label + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(args.label, "complete", flush=True)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
