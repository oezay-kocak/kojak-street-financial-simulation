"""Matched isolated-process CPU/wall and feature payload measurements."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/workforce-implementation"


def describe(values):
    ordered = sorted(values)
    return {"median": statistics.median(values), "p95": ordered[int((len(ordered) - 1) * .95)], "count": len(values)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    source = OUT / "baseline" if args.reference else ROOT
    sys.path[:0] = [str(source / "src"), str(source)]
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, encode
    from kojakstreet.live_process import game_state_payload
    from kojakstreet.visible_state import project_visible_state
    from kojakstreet.world_generator import _peak_rss_bytes

    path = OUT / args.label
    assert not path.exists()
    runtime = IntegratedRuntime(source, data_dir=path, seed=1729)
    try:
        runtime.data_store.enable_background_flush()
        rows = []
        for _ in range(90):
            when = runtime.daten.datum
            wall, cpu = time.perf_counter(), time.process_time()
            runtime.advance_day()
            rows.append({"report": when.day == 15, "wall_ms": (time.perf_counter() - wall) * 1000,
                         "cpu_ms": (time.process_time() - cpu) * 1000})
        result = {"reference": args.reference, "ordinary": {}, "report": {}}
        for report, name in ((False, "ordinary"), (True, "report")):
            for kind in ("wall_ms", "cpu_ms"):
                result[name][kind] = describe([r[kind] for r in rows if r["report"] == report])
        state, _, _ = project_visible_state(runtime, {"view": "markets"})
        result["markets_payload_bytes"] = len(json.dumps(game_state_payload(state)).encode())
        result["checkpoint_bytes"] = len(json.dumps(encode(capture(runtime.daten))).encode())
        result["peak_rss_bytes"] = _peak_rss_bytes()
        if not args.reference:
            from kojakstreet.core.workforce import aggregate
            samples = []
            for _ in range(100):
                started = time.perf_counter()
                aggregate(runtime.daten, force=True)
                samples.append((time.perf_counter() - started) * 1000)
            result["aggregation_ms"] = describe(samples)
            state, _, _ = project_visible_state(runtime, {"view": "macro", "selection": {"region": "Ameron", "area": "population_society"}})
            result["selected_population_payload_bytes"] = len(json.dumps(game_state_payload(state)).encode())
            result["feature_checkpoint_bytes"] = len(json.dumps({c: {k: m[k] for k in ("workforce", "birth_rate", "death_rate")} for c, m in runtime.daten.makro.items()}).encode())
        (path / "cost.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
