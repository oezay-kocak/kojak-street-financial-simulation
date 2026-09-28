"""Reproducible, read-only long-run diagnostics for the Kojak Street economy.

The tool deliberately leaves production modules untouched.  It instantiates the
same ``IntegratedRuntime`` used by Qt, advances that runtime, and writes compact
JSON/CSV observations.  ``--store-mode disabled`` is intended for expensive
economic-soak runs: it preserves the simulation path but disables only the
analytical DuckDB side effect after runtime construction.  Storage measurements
must use ``--store-mode full`` and are labelled accordingly in the output.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np


NUMERIC_METRICS = {
    "macro": (
        "bip_abs", "bip_prozent", "inflation", "arbeitslosigkeit", "zins",
        "balance_sheet", "fiscal_deficit", "debt_to_gdp", "credit_growth",
        "interest_burden", "fiscal_adjustment", "sovereign_funding_rate", "default_probability",
        "trade_balance", "import_dependency", "export_strength",
        "expected_growth", "expected_inflation", "macro_surprise_momentum",
    ),
    "company": (
        "kurs", "market_cap", "revenue", "revenue_growth", "free_cash_flow",
        "fcf_margin", "eps", "dividend_yield", "cash_reserves", "debt",
        "debt_to_market_cap", "production_capacity", "capacity_utilization",
        "input_availability", "supply_chain_shortage", "production_score",
        "funding_rate", "interest_coverage", "credit_score", "distress_months",
        "sentiment", "fear", "euphoria", "crowding", "expectation", "surprise",
    ),
    "commodity": (
        "kurs", "supply", "demand", "inventories", "shortage", "surplus",
        "imbalance", "price_pressure", "production", "extraction_cost",
        "sentiment", "fear", "euphoria", "crowding", "surprise",
    ),
    "global": (
        "global_gdp_growth", "global_cpi", "global_unemployment", "global_m2",
        "central_bank_balance_sheets", "tga", "rrp", "net_liquidity", "vix",
        "avg_3y_yield", "avg_5y_yield", "avg_10y_yield", "yield_curve_3y10y",
        "macro_surprise_index", "regime_risk_score", "regime_credit_stress",
    ),
    "market_psychology": (
        "risk_appetite", "fear", "liquidity_confidence", "inflation_fear",
        "recession_fear", "speculation",
    ),
    "crypto": (
        "kurs", "aenderung", "market_cap", "transactions", "chain_fees",
        "active_wallets", "network_utilization", "market_share", "sentiment",
        "fear", "euphoria", "crowding",
    ),
    "fund": ("kurs", "aenderung", "market_cap", "aum", "aum_change"),
    "index": ("kurs", "aenderung", "market_cap"),
    "derivative": ("kurs", "aenderung", "market_cap", "open_interest"),
    "bond": ("price", "yield_to_maturity", "default_risk", "duration", "liquidity"),
    "fx": ("rate",),
}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    point = (len(ordered) - 1) * fraction
    lower = math.floor(point)
    upper = math.ceil(point)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - point) + ordered[upper] * (point - lower)


def summarize(values: Iterable[float]) -> dict[str, float | int | None]:
    finite = [number for value in values if (number := _finite(value)) is not None]
    if not finite:
        return {"n": 0, "min": None, "p05": None, "median": None, "p95": None, "max": None, "mean": None, "stdev": None}
    return {
        "n": len(finite),
        "min": min(finite),
        "p05": _quantile(finite, 0.05),
        "median": _quantile(finite, 0.50),
        "p95": _quantile(finite, 0.95),
        "max": max(finite),
        "mean": statistics.fmean(finite),
        "stdev": statistics.pstdev(finite) if len(finite) > 1 else 0.0,
    }


def pearson(left: list[float], right: list[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(left, right) if _finite(x) is not None and _finite(y) is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    mean_x, mean_y = statistics.fmean(xs), statistics.fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denominator = math.sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
    return numerator / denominator if denominator else None


def _return(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0.0):
        return None
    return current / previous - 1.0


def _mean_field(rows: Iterable[dict[str, Any]], key: str) -> float | None:
    values = [value for row in rows if (value := _finite(row.get(key))) is not None]
    return statistics.fmean(values) if values else None


def _rss_bytes() -> int | None:
    if os.name != "nt":
        try:
            import resource
            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
        except Exception:
            return None
    try:
        import ctypes
        from ctypes import wintypes

        class MemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = MemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = ctypes.c_void_p
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
        get_memory.restype = wintypes.BOOL
        handle = get_process()
        if get_memory(handle, ctypes.byref(counters), counters.cb):
            return int(counters.WorkingSetSize)
    except Exception:
        return None
    return None


def _storage_inventory(runtime: Any) -> dict[str, Any]:
    store = runtime.data_store
    store.flush()
    connection = store._connection
    if connection is None:
        return {"enabled": False}
    tables = [row[0] for row in connection.execute("SHOW TABLES").fetchall()]
    row_counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
    database_size = [list(row) for row in connection.execute("PRAGMA database_size").fetchall()]
    columns = {
        table: [row[0] for row in connection.execute(f'DESCRIBE "{table}"').fetchall()]
        for table in tables
    }
    return {
        "enabled": True,
        "transient": bool(store.transient),
        "file_bytes": store.path.stat().st_size if store.path.exists() else 0,
        "database_size_pragma": database_size,
        "tables": {table: {"rows": row_counts[table], "columns": columns[table]} for table in tables},
        "session_rows": {table: len(rows) for table, rows in store._session_rows.items()},
    }


def _benchmark_queries(runtime: Any, repeats: int = 3) -> dict[str, Any]:
    connection = runtime.data_store._connection
    if connection is None:
        return {}
    stock = next(iter(runtime.daten.aktien))
    product = "CL" if "CL" in runtime.daten.rohstoffe else next(iter(runtime.daten.rohstoffe))
    region = next(iter(runtime.daten.makro))
    cases = {
        "asset_limit_520": ("SELECT date, price FROM asset_daily WHERE ticker=? AND asset_type='Stock' ORDER BY date DESC LIMIT 520", [stock]),
        "asset_all": ("SELECT date, price FROM asset_daily WHERE ticker=? AND asset_type='Stock' ORDER BY date", [stock]),
        "product_limit_520": ("SELECT date, price FROM product_daily WHERE code=? ORDER BY date DESC LIMIT 520", [product]),
        "product_all": ("SELECT date, price FROM product_daily WHERE code=? ORDER BY date", [product]),
        "country_all": ("SELECT date, gdp, inflation, unemployment, rate FROM country_daily WHERE region=? ORDER BY date", [region]),
    }
    result: dict[str, Any] = {}
    for name, (sql, params) in cases.items():
        durations, rows = [], 0
        for _ in range(repeats):
            start = time.perf_counter()
            fetched = connection.execute(sql, params).fetchall()
            durations.append(time.perf_counter() - start)
            rows = len(fetched)
        result[name] = {"rows": rows, "seconds": summarize(durations)}
    return result


def run_audit(project_root: Path, output: Path, seed: int, days: int, store_mode: str) -> dict[str, Any]:
    random.seed(seed)
    np.random.seed(seed)
    sys.path[:0] = [str(project_root / "src"), str(project_root)]
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime

    run_dir = output.parent / f"runtime-seed-{seed}-{days}d-{store_mode}"
    run_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    runtime = IntegratedRuntime(project_root, data_dir=run_dir)
    init_seconds = time.perf_counter() - started
    initial_rss = _rss_bytes() or 0
    if store_mode == "disabled":
        runtime.data_store.enabled = False

    d = runtime.daten
    collections: dict[str, dict[str, list[float]]] = {
        group: {metric: [] for metric in metrics} for group, metrics in NUMERIC_METRICS.items()
    }
    anomaly_counts: Counter[str] = Counter()
    regime_days: Counter[str] = Counter()
    regime_transitions: Counter[str] = Counter()
    sector_rows: list[dict[str, Any]] = []
    lifecycle_rows: list[dict[str, Any]] = []
    causality: dict[str, list[float]] = defaultdict(list)
    previous_regime = str(getattr(d, "market_regime", "Unknown"))
    previous_month: dict[str, float | None] = {}
    previous_year_sector: dict[str, float] = {}
    peak_rss = _rss_bytes() or 0

    def collect(scope: str) -> None:
        nonlocal previous_month, previous_year_sector, peak_rss
        if scope == "month":
            for row in d.makro.values():
                for metric in NUMERIC_METRICS["macro"]:
                    value = _finite(row.get(metric))
                    if value is None:
                        anomaly_counts[f"macro.{metric}.nonfinite"] += 1
                    else:
                        collections["macro"][metric].append(value)
            for row in d.rohstoffe.values():
                for metric in NUMERIC_METRICS["commodity"]:
                    value = _finite(row.get(metric))
                    if value is None:
                        anomaly_counts[f"commodity.{metric}.nonfinite"] += 1
                    else:
                        collections["commodity"][metric].append(value)
            for metric in NUMERIC_METRICS["global"]:
                value = _finite(d.global_macro.get(metric))
                if value is None:
                    anomaly_counts[f"global.{metric}.nonfinite"] += 1
                else:
                    collections["global"][metric].append(value)
            for metric in NUMERIC_METRICS["market_psychology"]:
                value = _finite(d.market_psychology.get(metric))
                if value is not None:
                    collections["market_psychology"][metric].append(value)
            for group, rows in (
                ("crypto", d.kryptos.values()),
                ("fund", d.fonds.values()),
                ("index", d.indizes.values()),
                ("derivative", d.derivatives.values()),
                ("bond", getattr(d, "bond_market", [])),
            ):
                for row in rows:
                    for metric in NUMERIC_METRICS[group]:
                        value = _finite(row.get(metric))
                        if value is not None:
                            collections[group][metric].append(value)
            for history in getattr(d, "FOREX_PAARE_HISTORIE", {}).values():
                if not history:
                    continue
                entry = history[-1]
                value = _finite(entry[0] if isinstance(entry, (tuple, list)) else entry)
                if value is not None:
                    collections["fx"]["rate"].append(value)

            sector_prices = {
                sector: _mean_field((row for row in d.aktien.values() if row.get("branche") == sector), "kurs")
                for sector in d.BRANCHEN
            }
            oil = _finite(d.rohstoffe.get("CL", {}).get("kurs"))
            rate = _mean_field(d.makro.values(), "zins")
            surprise = _finite(d.global_macro.get("macro_surprise_index"))
            fear = _finite(d.market_psychology.get("recession_fear"))
            market = _mean_field(d.aktien.values(), "kurs")
            current = {"oil": oil, "rate": rate, "surprise": surprise, "fear": fear, "market": market}
            for sector in ("Öl und Gas", "Finanzen", "Immobilien"):
                current[sector] = sector_prices.get(sector)
            if previous_month:
                causality["oil_return"].append(_return(oil, previous_month.get("oil")) or 0.0)
                causality["oil_gas_return"].append(_return(current["Öl und Gas"], previous_month.get("Öl und Gas")) or 0.0)
                causality["rate_change"].append((rate or 0.0) - (previous_month.get("rate") or 0.0))
                causality["financials_return"].append(_return(current["Finanzen"], previous_month.get("Finanzen")) or 0.0)
                causality["real_estate_return"].append(_return(current["Immobilien"], previous_month.get("Immobilien")) or 0.0)
                causality["macro_surprise"].append(surprise or 0.0)
                causality["recession_fear"].append(fear or 0.0)
                causality["market_return"].append(_return(market, previous_month.get("market")) or 0.0)
            previous_month = current

        if scope == "year":
            for row in d.aktien.values():
                for metric in NUMERIC_METRICS["company"]:
                    value = _finite(row.get(metric))
                    if value is None:
                        anomaly_counts[f"company.{metric}.nonfinite"] += 1
                    else:
                        collections["company"][metric].append(value)
            year = int(d.datum.year)
            for sector in d.BRANCHEN:
                companies = [row for row in d.aktien.values() if row.get("branche") == sector]
                price = _mean_field(companies, "kurs")
                key = sector
                sector_rows.append({
                    "seed": seed, "date": d.datum.strftime("%Y-%m-%d"), "year": year,
                    "sector": sector, "companies": len(companies), "mean_price": price,
                    "annual_price_return": _return(price, previous_year_sector.get(key)),
                    "mean_revenue_growth": _mean_field(companies, "revenue_growth"),
                    "mean_fcf_margin": _mean_field(companies, "fcf_margin"),
                    "mean_free_cash_flow": _mean_field(companies, "free_cash_flow"),
                    "mean_market_cap": _mean_field(companies, "market_cap"),
                    "total_market_cap": sum(float(row.get("market_cap", 0.0)) for row in companies),
                    "mean_capacity_utilization": _mean_field(companies, "capacity_utilization"),
                    "mean_shortage": _mean_field(companies, "supply_chain_shortage"),
                })
                if price is not None:
                    previous_year_sector[key] = price
            lifecycle_rows.append({
                "date": d.datum.strftime("%Y-%m-%d"), "active_companies": len(d.aktien),
                "retired_tickers": len(getattr(d, "retired_company_tickers", set())),
                "rating_upgrades": sum(int(row.get("rating_upgrades", 0)) for row in d.aktien.values()),
                "rating_downgrades": sum(int(row.get("rating_downgrades", 0)) for row in d.aktien.values()),
                "distress_episodes": sum(int(row.get("distress_episodes", 0)) for row in d.aktien.values()),
                "companies_in_distress": sum(int(row.get("distress_months", 0)) > 0 for row in d.aktien.values()),
                "cryptos": len(d.kryptos), "funds": len(d.fonds), "bonds": len(getattr(d, "bond_market", [])),
            })
        peak_rss = max(peak_rss, _rss_bytes() or 0)

    initial_counts = {name: len(getattr(d, name, {})) for name in ("aktien", "rohstoffe", "processed_products", "kryptos", "fonds", "indizes", "derivatives", "makro")}
    initial_ratings = {
        "companies": dict(Counter(str(row.get("rating", "")) for row in d.aktien.values())),
        "sovereigns": dict(Counter(str(row.get("rating", "")) for row in d.makro.values())),
    }
    simulation_started = time.perf_counter()
    simulation_cpu_started = time.process_time()
    for day_index in range(1, days + 1):
        runtime.advance_day()
        regime = str(getattr(d, "market_regime", "Unknown"))
        regime_days[regime] += 1
        if regime != previous_regime:
            regime_transitions[f"{previous_regime} -> {regime}"] += 1
            previous_regime = regime
        if day_index % 30 == 0 or day_index == days:
            collect("month")
        if day_index % 365 == 0 or day_index == days:
            collect("year")
    simulation_seconds = time.perf_counter() - simulation_started
    simulation_cpu_seconds = time.process_time() - simulation_cpu_started

    storage = _storage_inventory(runtime) if store_mode == "full" else {"enabled": False, "mode": "disabled after initialization"}
    benchmarks = _benchmark_queries(runtime) if store_mode == "full" else {}
    final_counts = {name: len(getattr(d, name, {})) for name in initial_counts}
    results = {
        "schema_version": 1,
        "run": {
            "seed": seed, "days": days, "nominal_years": days / 365.0,
            "start_date": "1990-01-01", "end_date": d.datum.strftime("%Y-%m-%d"),
            "store_mode": store_mode, "runtime_path": "IntegratedRuntime.advance_day",
            "simulation_fidelity": "full runtime including DuckDB" if store_mode == "full" else "full economic runtime with DuckDB recording disabled",
            "init_seconds": init_seconds, "simulation_seconds": simulation_seconds,
            "simulation_cpu_seconds": simulation_cpu_seconds,
            "days_per_second": days / simulation_seconds,
            "initial_rss_bytes": initial_rss,
            "peak_observed_rss_bytes": peak_rss,
        },
        "universe": {
            "initial": initial_counts,
            "final": final_counts,
            "ratings_initial": initial_ratings,
            "ratings_final": {
                "companies": dict(Counter(str(row.get("rating", "")) for row in d.aktien.values())),
                "sovereigns": dict(Counter(str(row.get("rating", "")) for row in d.makro.values())),
            },
            "lifecycle_yearly": lifecycle_rows,
        },
        "distributions": {group: {metric: summarize(values) for metric, values in metrics.items()} for group, metrics in collections.items()},
        "regimes": {"days": dict(regime_days), "transitions": dict(regime_transitions)},
        "causal_proxies": {
            "oil_return_vs_oil_gas_sector_return": pearson(causality["oil_return"], causality["oil_gas_return"]),
            "rate_change_vs_financials_return": pearson(causality["rate_change"], causality["financials_return"]),
            "rate_change_vs_real_estate_return": pearson(causality["rate_change"], causality["real_estate_return"]),
            "macro_surprise_vs_market_return": pearson(causality["macro_surprise"], causality["market_return"]),
            "recession_fear_vs_market_return": pearson(causality["recession_fear"], causality["market_return"]),
            "monthly_observations": len(causality["market_return"]),
            "interpretation": "Descriptive contemporaneous correlations; they do not establish causality.",
        },
        "anomalies": dict(anomaly_counts),
        "storage": storage,
        "query_benchmarks": benchmarks,
    }
    runtime.close()

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    sector_path = output.with_name(output.stem + "-sectors.csv")
    if sector_rows:
        with sector_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(sector_rows[0]))
            writer.writeheader()
            writer.writerows(sector_rows)
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--store-mode", choices=("full", "disabled"), default="disabled")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.days < 1:
        raise SystemExit("--days must be positive")
    result = run_audit(args.project_root.resolve(), args.output.resolve(), args.seed, args.days, args.store_mode)
    print(json.dumps(result["run"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
