"""Exact current-source reference, including player cases and durable content."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/max-performance"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--checkpoint")
    parser.add_argument("--players", action="store_true")
    args = parser.parse_args()
    source = OUT / "baseline" if args.reference else ROOT
    sys.path[:0] = [str(source / "src"), str(source), str(ROOT / "tools"), str(ROOT / "tests")]
    from performance_remediation_determinism import current_signature, database_signature, digest

    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, decode, restore

    directory = OUT / (args.label + "-world")
    assert not directory.exists(), "Choose a fresh evidence label"
    runtime = IntegratedRuntime(source, data_dir=directory, seed=1729)
    result = {"source": str(source), "days": [], "checkpoints": {}}
    try:
        if args.checkpoint:
            payload = decode(json.loads((ROOT / f".cache/day-transition-audit/checkpoint-{args.checkpoint}.json").read_text(encoding="utf-8")))
            restore(runtime.daten, payload)
            runtime.state.sync_from_legacy()
            runtime.market.warm_runtime_indexes()
        if args.players:
            from test_retail_boundary import ACTIONS, action, reset

            runtime.set_running(True)
            initial = capture(runtime.daten)
            result["players"] = {}
            for month, day in ((1, 10), (1, 15), (1, 31), (12, 31)):
                for name in ACTIONS:
                    reset(runtime, initial)
                    runtime.daten.datum = runtime.daten.datum.replace(year=1990, month=month, day=day)
                    stock = next(t for t in runtime.daten.aktien if t not in runtime.daten.indizes)
                    if name == "stock_sell":
                        runtime.trading.trade_spot(stock, 2, "BUY")
                    elif name == "short_close":
                        runtime.trading.open_future(stock, "SHORT", 5, 100)
                    action(runtime, name)
                    rows = []
                    for _ in range(1 if name == "margin_call" else 2):
                        runtime.simulation.step_day()
                        rows.append(digest(capture(runtime.daten)))
                    result["players"][f"{month}-{day}:{name}"] = rows
                print(args.label, "player boundary", month, day, flush=True)
        else:
            for day in range(1, args.days + 1):
                runtime.advance_day()
                result["days"].append(current_signature(runtime))
                if day in {15, 31, 181, 365}:
                    result["checkpoints"][str(day)] = digest(capture(runtime.daten))
                if day % 30 == 0:
                    print(args.label, day, flush=True)
            result["final_checkpoint"] = digest(capture(runtime.daten))
            runtime.data_store.flush()
            result["database"] = database_signature(runtime)
        (OUT / (args.label + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(args.label, "complete", flush=True)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
