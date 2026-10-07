"""Matched quiet runtime probe without writer contention in the timed region."""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]


def main():
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
    from kojakstreet.core.market_data_service import MarketDataService

    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--mode", choices=("GENESIS", "HETEROGENEOUS"), required=True)
    parser.add_argument("--seed", type=int, default=1729)
    args = parser.parse_args()
    directory = ROOT / ".cache/heterogeneous-start" / args.label
    assert not directory.exists(), "Use a fresh evidence label"
    kwargs = {"world_config": WorldGenerationConfig(mode=WorldMode.HETEROGENEOUS, seed=args.seed)} if args.mode == "HETEROGENEOUS" else {}
    runtime = IntegratedRuntime(ROOT, data_dir=directory / "data", seed=args.seed, flush_interval_days=10000, **kwargs)
    samples = []
    try:
        service = MarketDataService(runtime.daten)
        index_samples = []
        for sample in range(105):
            started = time.perf_counter()
            rows = [service.quote(ticker, asset_type="Index") for ticker in runtime.daten.indizes]
            elapsed = (time.perf_counter() - started) * 1000
            assert len(rows) == 340 and all(row is not None and row.asset_type == "Index" for row in rows)
            if sample >= 5:
                index_samples.append(elapsed)
        for day in range(60):
            start_date = runtime.daten.datum
            started = time.perf_counter()
            runtime.advance_day()
            elapsed = (time.perf_counter() - started) * 1000
            phases = {item["phase"]: item["duration_ms"] for item in runtime.daten.simulation_phase_timings}
            if day >= 5 and "monthly_macro" not in phases and (start_date + timedelta(days=1)).month == start_date.month:
                samples.append({"day": day + 1, "ms": elapsed, "phases": phases})
        timings = sorted(item["ms"] for item in samples)
        result = {"mode": args.mode, "seed": args.seed, "timed_days": 60, "ordinary_samples": len(samples),
                  "median_ms": statistics.median(timings), "p95_ms": timings[math.ceil(.95 * len(timings)) - 1],
                  "max_ms": timings[-1], "samples": samples,
                  "index_quote_batch_ms": {"n": len(index_samples), "median": statistics.median(index_samples),
                                           "p95": sorted(index_samples)[94], "max": max(index_samples)}}
        (directory / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    finally:
        # Commit every row after timing; durability is retained, this is not an
        # alternative production flush policy or a change to the live writer.
        runtime.close()
    print(args.label, result["median_ms"], flush=True)


if __name__ == "__main__":
    main()
