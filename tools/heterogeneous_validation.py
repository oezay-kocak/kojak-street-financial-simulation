"""Isolated evidence for initialization roots, exact references and runtime gates."""
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
OUT = ROOT / ".cache/heterogeneous-start"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def digest(value):
    from kojakstreet.core.checkpoints import encode
    return hashlib.sha256(json.dumps(encode(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def summary(data):
    from kojakstreet.core.global_macro import _observed_government_yields
    from kojakstreet.core.heterogeneous_start import (
        GDP_BUDGET,
        MARKET_CAP_BUDGET,
        POPULATION_BUDGET,
    )
    from kojakstreet.core.indices import COMPOSITE_TICKERS
    from kojakstreet.core.market_data_service import MarketDataService
    from kojakstreet.core.production_chains import _balance_profile
    countries = []
    for country, macro in data.makro.items():
        stocks = {t: a for t, a in data.aktien.items() if a["land"] == country}
        indices = [a for a in data.indizes.values() if a["land"] == country]
        broad = data.indizes[COMPOSITE_TICKERS[country]]
        assert len(stocks) == 64 and set(Counter(a["branche"] for a in stocks.values()).values()) == {4}
        assert len(indices) == 17 and set(broad["constituents"]) == set(stocks)
        assert broad["market_cap"] == sum(a["market_cap"] for a in stocks.values())
        countries.append({"country": country, "population": macro["bevoelkerung"], "GDP": macro["bip_abs"],
                          "GDP_per_capita_proxy": macro["bip_abs"] / macro["bevoelkerung"],
                          "market_cap": sum(a["market_cap"] for a in stocks.values()),
                          "capacity": sum(a["production_capacity"] for a in stocks.values())})
    caps = sorted([a["market_cap"] for a in data.aktien.values()], reverse=True)
    assert sum(c["population"] for c in countries) == POPULATION_BUDGET
    assert sum(c["GDP"] for c in countries) == GDP_BUDGET
    assert sum(caps) == MARKET_CAP_BUDGET
    assert len(data.aktien) == 1280 and len(data.indizes) == 340
    assert sum(q.asset_type == "Index" for q in MarketDataService(data).quotes()) == 340
    assert max(c["GDP"] for c in countries) / GDP_BUDGET <= .20
    assert max(c["market_cap"] for c in countries) / MARKET_CAP_BUDGET <= .20
    assert all(a["eps"] == max(.1, a["free_cash_flow"] / a["aktien_anzahl"]) for a in data.aktien.values())
    assert all(a["previous_eps"] == a["eps"] and a["previous_revenue"] == a["revenue"] for a in data.aktien.values())
    assert all(not a["historie"] for book in (data.aktien, data.rohstoffe, data.kryptos, data.fonds, data.indizes, data.derivatives) for a in book.values())
    viability = []
    for code, product in {**data.rohstoffe, **data.processed_products}.items():
        assert product["supply"] > 0 and product["demand"] > 0 and product["inventories"] >= 0
        profile = _balance_profile(code)
        ratio = product["supply"] / product["demand"]
        lower, upper = product["demand"] * profile["supply_floor"], product["demand"] * profile["supply_ceiling"]
        # The second bootstrap smooths both sides; a handful of elementary
        # operations can round a boundary by a few machine representable steps.
        assert lower - 4 * math.ulp(lower) <= product["supply"] <= upper + 4 * math.ulp(upper), {
            "code": code, "supply": product["supply"], "demand": product["demand"], "profile": profile,
        }
        viability.append({"code": code, "ratio": ratio, "floor": profile["supply_floor"],
                          "ceiling": profile["supply_ceiling"], "producer_count": product.get("producer_count", 0)})
    observed = _observed_government_yields(data, .035)
    return {"countries": countries, "company_min_median_max": [caps[-1], (caps[639] + caps[640]) / 2, caps[0]],
            "top_company_shares": {str(n): sum(caps[:n]) / MARKET_CAP_BUDGET for n in (1, 10, 50)},
            "viability": viability, "observed_yields": observed,
            "asset_counts": {book: len(getattr(data, book)) for book in ("aktien", "rohstoffe", "processed_products", "kryptos", "fonds", "indizes", "bond_market", "derivatives")}}


def capture_run(args):
    source = OUT / "baseline" if args.reference else ROOT
    sys.path[:0] = [str(source / "src"), str(source), str(ROOT / "tools")]
    from performance_remediation_determinism import database_signature

    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, encode
    from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode

    directory = OUT / args.label
    assert not directory.exists(), "Use a fresh label"
    started = time.perf_counter()
    if args.mode == "ESTABLISHED":
        from kojakstreet.world_generator import generate
        bundle = directory / "bundle"
        generate(source, bundle, args.seed, 50,
                 diagnostic_days=args.days if not args.hybrid else None, burn_in_days=2)
        runtime = IntegratedRuntime.open_world_bundle(source, bundle)
    else:
        kwargs = {}
        if args.mode == "HETEROGENEOUS":
            kwargs["world_config"] = WorldGenerationConfig(mode=WorldMode.HETEROGENEOUS, seed=args.seed,
                                                          world_id=f"validation-{args.seed}", created_at="validation").normalized()
        runtime = IntegratedRuntime(source, data_dir=directory / "data", seed=args.seed, **kwargs)
    result = {"generation_seconds": time.perf_counter() - started, "seed": args.seed, "mode": args.mode,
              "days": [], "checkpoints": {}}
    try:
        from kojakstreet.world_generator import _peak_rss_bytes
        result["peak_day1_memory_bytes"] = _peak_rss_bytes()
        if args.benchmark:
            from kojakstreet.core.market_data_service import MarketDataService
            service = MarketDataService(runtime.daten)
            samples = []
            for sample in range(105):
                started = time.perf_counter()
                service.quotes()
                if sample >= 5:
                    samples.append((time.perf_counter() - started) * 1000)
            result["quote_batch_ms"] = {"n": len(samples), "median": statistics.median(samples),
                                        "p95": sorted(samples)[94], "max": max(samples)}
        initial = capture(runtime.daten)
        write(directory / "day1-checkpoint.json", encode(initial))
        if args.mode == "HETEROGENEOUS":
            result["day1"] = summary(runtime.daten)
        if args.writer:
            runtime.data_store.enable_background_flush()
        if args.mode != "ESTABLISHED":
            for day in range(1, args.days + 1):
                writer = getattr(runtime.data_store, "_writer", None)
                before_sequence = writer.journal.sequence if writer else 0
                date = runtime.daten.datum.isoformat()
                started = time.perf_counter()
                runtime.advance_day()
                result["days"].append({"day": day, "seconds": time.perf_counter() - started,
                                       "start_date": date,
                                       "flush_staged": bool(writer and writer.journal.sequence != before_sequence),
                                       "phases": {item["phase"]: item["duration_ms"] for item in
                                                  getattr(runtime.daten, "simulation_phase_timings", [])}})
                if day in {1, 31, 181, 365}:
                    checkpoint = capture(runtime.daten)
                    result["checkpoints"][str(day)] = digest(checkpoint)
                    if day == 1:
                        write(directory / "day2-checkpoint.json", encode(checkpoint))
                if day % 30 == 0:
                    print(args.label, day, flush=True)
        result["final_checkpoint"] = digest(capture(runtime.daten))
        result["final_date"] = runtime.daten.datum.isoformat()
        result["game_active"] = runtime.daten.SPIEL_AKTIV
        runtime.data_store.flush()
        result["database"] = database_signature(runtime)
        if args.writer:
            result["writer_metrics"] = [dict(x) for x in runtime.data_store._writer.metrics]
        result["checkpoint_bytes"] = (directory / "day1-checkpoint.json").stat().st_size
        result["store_bytes"] = runtime.data_store.path.stat().st_size
        write(directory / "result.json", result)
    finally:
        runtime.close()
    print(args.label, "complete", flush=True)


def sweep(label):
    """Cheap root sampling plus twenty real, fully bootstrapped economies."""
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    import numpy as np

    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.companies import BRANCHEN
    from kojakstreet.core.countries import COUNTRY_SYMBOLS
    from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
    from kojakstreet.core.heterogeneous_start import COMPANY_CLASSES, generate_roots

    directory = OUT / label
    assert not directory.exists(), "Use a fresh label"
    directory.mkdir()
    countries = list(COUNTRY_SYMBOLS)
    results = {"roots": [], "worlds": []}
    for seed in range(100):
        roots = generate_roots(seed, countries, BRANCHEN)
        caps = sorted([v for a in roots.company_caps.values() for v in a], reverse=True)
        pop = [roots.population[c] for c in countries]
        gdp = [roots.gdp[c] for c in countries]
        markets = [roots.country_caps[c] for c in countries]
        classes = Counter(c for rows in roots.company_classes.values() for c in rows)
        assert sum(pop) == 400_000_000 and sum(gdp) == 100_000 and sum(caps) == 1_280_000_000_000
        assert classes == {name: count for name, count, _, _ in COMPANY_CLASSES}
        assert 5_000_000 <= min(pop) <= max(pop) <= 50_000_000
        assert min(gdp) >= 1000 and .10 <= max(gdp) / 100_000 <= .20
        assert max(markets) / 1_280_000_000_000 <= .20 and caps[0] <= 18_000_000_000
        sector_caps = {s: sum(sum(roots.company_caps[c, s]) for c in countries) for s in BRANCHEN}
        assert max(sector_caps.values()) / 1_280_000_000_000 < .25
        record = {"seed": seed, "countries": [{"country": c, "population": roots.population[c],
                  "population_class": roots.population_class[c], "productivity": roots.productivity[c],
                  "GDP": roots.gdp[c], "GDP_per_capita_proxy": roots.gdp[c] / roots.population[c],
                  "market_cap": roots.country_caps[c], "requested_market_cap": roots.requested_country_caps[c]} for c in countries],
                  "population_min_median_max": [min(pop), statistics.median(pop), max(pop)],
                  "GDP_min_median_max": [min(gdp), statistics.median(gdp), max(gdp)],
                  "company_min_median_max": [caps[-1], statistics.median(caps), caps[0]],
                  "GDP_max_share": max(gdp) / 100_000, "market_max_share": max(markets) / 1_280_000_000_000,
                  "population_GDP_correlation": float(np.corrcoef(pop, gdp)[0, 1]),
                  "GDP_market_correlation": float(np.corrcoef(gdp, markets)[0, 1]),
                  "target_calibration_max_relative": max(abs(roots.country_caps[c] / roots.requested_country_caps[c] - 1) for c in countries),
                  "class_counts": dict(classes), "sector_caps": sector_caps,
                  "top_company_shares": {str(n): sum(caps[:n]) / 1_280_000_000_000 for n in (1, 10, 50)},
                  "flags": []}
        results["roots"].append(record)
    write(directory / "root-statistics.json", results["roots"])
    for seed in range(20):
        cfg = WorldGenerationConfig(mode=WorldMode.HETEROGENEOUS, seed=seed,
                                    world_id=f"sweep-{seed}", created_at="sweep").normalized()
        runtime = IntegratedRuntime(ROOT, data_dir=directory / f"world-{seed}", world_config=cfg)
        try:
            record = summary(runtime.daten)
            runtime.advance_day()
            assert all(runtime.daten.makro[c]["bip_abs"] == row["GDP"] for c, row in zip(countries, record["countries"]))
            record["seed"] = seed
            results["worlds"].append(record)
        finally:
            runtime.close()
        print(label, "world", seed, flush=True)
        write(directory / "world-statistics.json", results["worlds"])
    print(label, "100 root seeds and 20 complete worlds passed", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--mode", choices=("GENESIS", "HETEROGENEOUS", "ESTABLISHED"), default="HETEROGENEOUS")
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--hybrid", action="store_true")
    parser.add_argument("--writer", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--sweep", action="store_true")
    args = parser.parse_args()
    if args.sweep:
        sweep(args.label)
    else:
        capture_run(args)


if __name__ == "__main__":
    main()
