"""Isolated before/after economic, calibration and performance evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/workforce-implementation"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def distribution(values):
    values = sorted(float(v) for v in values)
    return {"min": values[0], "median": statistics.median(values), "p95": values[int((len(values) - 1)*.95)],
            "max": values[-1], "sum": sum(values), "count": len(values)}


def snapshot(state):
    result = {
        "date": state.datum.isoformat(),
        "population": distribution(m["bevoelkerung"] for m in state.makro.values()),
        "population_growth": distribution(m["population_growth"] for m in state.makro.values()),
        "gdp": distribution(m["bip_abs"] for m in state.makro.values()),
        "growth": distribution(m["bip_prozent"] for m in state.makro.values()),
        "unemployment": distribution(m["arbeitslosigkeit"] for m in state.makro.values()),
        "inflation": distribution(m["inflation"] for m in state.makro.values()),
        "companies": len(state.aktien), "retired_companies": len(getattr(state, "retired_company_tickers", ())),
        "revenue": distribution(a["revenue"] for a in state.aktien.values()),
        "fcf": distribution(a["free_cash_flow"] for a in state.aktien.values()),
        "market_cap": distribution(a["market_cap"] for a in state.aktien.values()),
        "production": distribution(a["supply"] for a in {**state.rohstoffe, **state.processed_products}.values()),
        "company_ratings": dict(Counter(a["rating"] for a in state.aktien.values())),
        "sectors": {},
    }
    for sector in state.BRANCHEN:
        assets = [a for a in state.aktien.values() if a["branche"] == sector]
        result["sectors"][sector] = {k: sum(a[k] for a in assets) for k in ("revenue", "free_cash_flow", "market_cap", "production_capacity")}
    if all("workforce" in m for m in state.makro.values()):
        result["birth_rate"] = distribution(m["birth_rate"] for m in state.makro.values())
        result["death_rate"] = distribution(m["death_rate"] for m in state.makro.values())
        result["coverage"] = distribution(v for m in state.makro.values() for v in m["workforce"]["coverage"].values())
        result["shortage"] = distribution(v for m in state.makro.values() for v in m["workforce"]["shortage"].values())
        result["contribution"] = distribution(v for m in state.makro.values() for v in m["workforce"]["contributions"].values())
        result["distress"] = sum(int(a.get("distress_months", 0)) >= 3 for a in state.aktien.values())
    return result


def source_setup(reference):
    source = OUT / "baseline" if reference else ROOT
    sys.path[:0] = [str(source / "src"), str(source), str(source / "tools")]
    return source


def checkpoint_digest(state):
    from kojakstreet.core.checkpoints import capture, encode
    digest = hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True, ensure_ascii=False).iterencode(encode(capture(state))):
        digest.update(chunk.encode())
    return digest.hexdigest()


def run(args):
    source = source_setup(args.reference)
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, encode
    from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
    from kojakstreet.world_generator import _peak_rss_bytes
    if args.disable_workforce_effect:
        import kojakstreet.core.company_lifecycle as lifecycle
        from kojakstreet.core import workforce
        lifecycle.company_contribution = lambda *_: 0.0
        workforce.company_contribution = lambda *_: 0.0
    directory = OUT / args.label
    assert not directory.exists(), "Use a fresh label"
    if args.mode == "ESTABLISHED":
        import kojakstreet.core.established_world as generator
        original_write = generator.write_compressed_checkpoint

        def checked_write(path, payload):
            invalid = []

            def visit(value, trail):
                if isinstance(value, float) and not math.isfinite(value):
                    invalid.append({"path": trail, "value": repr(value)})
                elif isinstance(value, dict):
                    for key, item in value.items():
                        visit(item, trail + [str(key)])
                elif isinstance(value, (list, tuple)):
                    for index, item in enumerate(value):
                        visit(item, trail + [str(index)])
            visit(payload, [])
            if invalid:
                write(directory / "invalid-checkpoint-values.json", invalid)
                raise ValueError(f"{len(invalid)} nonfinite checkpoint values; see diagnostic")
            return original_write(path, payload)

        generator.write_compressed_checkpoint = checked_write
        from kojakstreet.world_generator import generate
        start = time.perf_counter()
        bundle = generate(source, directory / "bundle", args.seed, 50, burn_in_days=args.burn_in_days)
        if args.prepare_only:
            print(str(bundle), flush=True)
            return
        generation_seconds = time.perf_counter() - start
        runtime = IntegratedRuntime.open_world_bundle(source, bundle)
        generation_metadata = json.loads((bundle / "world.json").read_text(encoding="utf-8"))["generation"]
    else:
        config = WorldGenerationConfig(mode=WorldMode(args.mode), seed=args.seed).normalized()
        start = time.perf_counter()
        runtime = IntegratedRuntime(source, data_dir=directory / "data", world_config=config, seed=args.seed)
        generation_seconds = time.perf_counter() - start
        generation_metadata = None
    try:
        runtime.data_store.enable_background_flush()
        result = {"mode": args.mode, "seed": args.seed, "reference": args.reference,
                  "generation_seconds": generation_seconds, "generation_metadata": generation_metadata,
                  "initial": snapshot(runtime.daten), "days": [], "reports": []}
        checkpoint = encode(capture(runtime.daten))
        result["initial_rng_digest"] = hashlib.sha256(json.dumps(checkpoint["rng"], sort_keys=True).encode()).hexdigest()
        result["initial_checkpoint_bytes"] = len(json.dumps(checkpoint, ensure_ascii=False).encode())
        del checkpoint
        for index in range(args.days):
            when = runtime.daten.datum
            start = time.perf_counter()
            runtime.advance_day()
            duration = time.perf_counter() - start
            result["days"].append({"date": when.isoformat(), "ms": duration * 1000,
                                   "report": when.day == 15,
                                   "phases": runtime.daten.simulation_phase_timings})
            if when.day == 15:
                result["reports"].append(snapshot(runtime.daten))
            if (index + 1) % 30 == 0:
                print(f"{args.label}: {index+1}/{args.days}", flush=True)
        result["final"] = snapshot(runtime.daten)
        result["peak_rss_bytes"] = _peak_rss_bytes()
        write(directory / "simulation-result.json", result)
        runtime.set_running(False)
        start = time.perf_counter()
        runtime.save_game()
        result["save_ms"] = (time.perf_counter() - start) * 1000
        saved = checkpoint_digest(runtime.daten)
        runtime.advance_day()
        expected = checkpoint_digest(runtime.daten)
        start = time.perf_counter()
        runtime.load_game()
        result["load_ms"] = (time.perf_counter() - start) * 1000
        assert checkpoint_digest(runtime.daten) == saved
        runtime.advance_day()
        assert checkpoint_digest(runtime.daten) == expected
        result["save_load_continuation_exact"] = True
        runtime.data_store.flush()
        writer = runtime.data_store._writer
        result["writer"] = {"batches": len(writer.metrics),
                            "max_queue_depth": max((m["queue_depth"] for m in writer.metrics), default=0)}
        result["tables"] = {table: runtime.data_store._connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                            for (table,) in runtime.data_store._connection.execute("SHOW TABLES").fetchall()}
        result["store_bytes"] = runtime.data_store.path.stat().st_size
        write(directory / "result.json", result)
        print(json.dumps({"label": args.label, "passed": True, "final_population": result["final"]["population"]["sum"]}), flush=True)
    finally:
        runtime.close()


def calibrate(args):
    source_setup(False)
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
    from kojakstreet.core.workforce import POOLS, country_roots
    roots = []
    for seed in range(100):
        for country in ("Ameron", "Albionia", "Ardonia", "Valoria", "Romara", "Soleria", "Nordmark", "Sarmatia", "Danubria", "Carpathia", "Anatria", "Azaria", "Indara", "Hanxia", "Pacifica", "Koryo", "Amazonia", "Canadia", "Auroria", "Savanna"):
            shares, birth, death = country_roots(seed, country, heterogeneous=True)
            assert sum(shares.values()) == 1.0
            assert .30 <= shares["basic"] <= .50 and .32 <= shares["skilled"] <= .48 and .12 <= shares["highly_qualified"] <= .30
            assert .008 <= birth <= .016 and .006 <= death <= .011
            assert country_roots(seed, country, heterogeneous=True) == (shares, birth, death)
            roots.append({"seed": seed, "country": country, "shares": shares, "birth": birth, "death": death})
    directory = OUT / args.label
    assert not directory.exists()
    worlds = []
    for seed in range(20):
        cfg = WorldGenerationConfig(mode=WorldMode.HETEROGENEOUS, seed=seed).normalized()
        runtime = IntegratedRuntime(ROOT, data_dir=directory / f"seed-{seed}", world_config=cfg)
        try:
            row = snapshot(runtime.daten)
            row["seed"] = seed
            row["countries"] = {c: {"population": m["bevoelkerung"], "shares": m["workforce"]["shares"],
                                    **{p: {k: m["workforce"][k][p] for k in ("supply", "demand", "coverage", "shortage")} for p in POOLS}}
                                  for c, m in runtime.daten.makro.items()}
            worlds.append(row)
            print(f"calibration: {seed+1}/20", flush=True)
        finally:
            runtime.close()
    write(directory / "result.json", {"root_checks": len(roots), "roots": roots, "worlds": worlds})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "calibrate"))
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--disable-workforce-effect", action="store_true")
    parser.add_argument("--label", required=True)
    parser.add_argument("--mode", default="GENESIS", choices=("GENESIS", "HETEROGENEOUS", "ESTABLISHED"))
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--burn-in-days", type=int, default=365)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    (run if args.action == "run" else calibrate)(args)


if __name__ == "__main__":
    main()
