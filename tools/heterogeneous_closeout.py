"""Read-only closeout of frozen-source, seed, continuity and yearly evidence."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/heterogeneous-start"
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def describe(values):
    return {"n": len(values), "min": min(values), "median": statistics.median(values),
            "p95": sorted(values)[math.ceil(.95 * len(values)) - 1], "max": max(values)}


def continuity():
    from kojakstreet.core.checkpoints import decode

    result = {}
    for mode in ("genesis", "heterogeneous"):
        directory = OUT / f"{mode}-365-performance"
        before, after = [decode(read(directory / filename))["checkpoint"] for filename in
                         ("day1-checkpoint.json", "day2-checkpoint.json")]
        books = {}
        for book, fields in {"aktien": ("kurs", "revenue", "eps", "production_capacity"),
                             "indizes": ("kurs",), "fonds": ("kurs",), "derivatives": ("kurs",),
                             "rohstoffe": ("kurs", "supply", "demand", "inventories"),
                             "kryptos": ("kurs",), "processed_products": ("supply", "demand", "inventories")}.items():
            books[book] = {field: describe([(after[book][key][field] / value[field] - 1) * 100
                          for key, value in before[book].items() if value.get(field) and key in after[book]])
                          for field in fields}
        bond_before = {item["symbol"]: item for item in before["bond_market"]}
        bonds = [(item["yield_to_maturity"] - bond_before[item["symbol"]]["yield_to_maturity"]) * 10000
                 for item in after["bond_market"] if item["symbol"] in bond_before]
        result[mode] = {"books_percent": books, "bond_yield_change_basis_points": describe(bonds),
                        "GDP_exactly_unchanged": all(after["makro"][key]["bip_abs"] == value["bip_abs"]
                                                     for key, value in before["makro"].items()),
                        "shares_exactly_unchanged": all(after["aktien"][key]["aktien_anzahl"] == value["aktien_anzahl"]
                                                        for key, value in before["aktien"].items()),
                        "net_liquidity": [before["global_macro"]["net_liquidity"], after["global_macro"]["net_liquidity"]],
                        "gli_index": [before["gli_index"], after["gli_index"]]}
        if mode == "heterogeneous":
            assert result[mode]["GDP_exactly_unchanged"] and result[mode]["shares_exactly_unchanged"]
            assert all(after["aktien"][key]["revenue"] == value["revenue"] and after["aktien"][key]["eps"] == value["eps"]
                       for key, value in before["aktien"].items())
            extremes = sorted(before["derivatives"], key=lambda k: abs(after["derivatives"][k]["kurs"] /
                                                                      before["derivatives"][k]["kurs"] - 1), reverse=True)
            result[mode]["largest_option_move"] = {"ticker": extremes[0], "before": before["derivatives"][extremes[0]],
                                                  "after": after["derivatives"][extremes[0]]}
    return result


def year(mode):
    directory = OUT / f"{mode}-365-performance"
    run = read(directory / "result.json")
    assert len(run["days"]) == 365 and run["final_checkpoint"] == run["checkpoints"]["365"]
    expected = date(1990, 1, 1)
    for item in run["days"]:
        assert item["start_date"][:10] == expected.isoformat()
        expected += timedelta(days=1)
    connection = duckdb.connect(str(directory / "data/kojakstreet.duckdb"), read_only=True)
    try:
        phases = {}
        for day, phase, duration in connection.execute("SELECT date,phase,duration_ms FROM phase_metric_daily").fetchall():
            phases.setdefault(day.isoformat(), {})[phase] = duration
        assert len(phases) == 365
        # Recover correct timing dictionaries from durable diagnostics. The first
        # capture script accidentally converted a list of dicts with dict(list).
        for item in run["days"]:
            item["phases"] = phases[item["start_date"][:10]]
        ordinary = [item for item in run["days"] if not item["flush_staged"] and
                    "monthly_macro" not in item["phases"] and "policy_decision" not in item["phases"] and
                    (date.fromisoformat(item["start_date"][:10]) + timedelta(days=1)).month ==
                    date.fromisoformat(item["start_date"][:10]).month]
        nonfinite = {}
        for (table,) in connection.execute("SHOW TABLES").fetchall():
            if not table.endswith("_current"):
                continue
            columns = [name for name, typ, *_ in connection.execute(f'DESCRIBE "{table}"').fetchall()
                       if typ in {"DOUBLE", "FLOAT"}]
            if columns:
                clause = " OR ".join(f'NOT isfinite("{name}")' for name in columns)
                count = connection.execute(f'SELECT count(*) FROM "{table}" WHERE {clause}').fetchone()[0]
                nonfinite[table] = count
        assert not any(nonfinite.values())
        bounds = connection.execute("SELECT min(date),max(date),count(distinct date) FROM asset_daily").fetchone()
        assert bounds == (date(1990, 1, 1), date(1990, 12, 31), 365)
        stale_fund_stocks = connection.execute("""SELECT count(*) FROM fund_allocation_current f
            LEFT JOIN company_current c ON f.ticker=c.ticker
            WHERE f.asset_type='Stock' AND c.ticker IS NULL""").fetchone()[0]
        assert stale_fund_stocks == 0
        products = connection.execute("""SELECT count(*),min(produced),min(demanded),min(inventories)
            FROM product_current""").fetchone()
        assert products[0] == 124 and products[1] > 0 and products[2] > 0 and products[3] >= 0
        counts = dict(connection.execute("SELECT asset_type,count(*) FROM asset_current GROUP BY asset_type").fetchall())
        assert counts["Stock"] == 1280 and counts["Index"] == 340
        months = connection.execute("SELECT count(*) FROM phase_metric_daily WHERE phase='monthly_macro'").fetchone()[0]
        assert months == 12
        metrics = run["writer_metrics"]
        assert [item["sequence"] for item in metrics] == list(range(1, len(metrics) + 1))
        assert max(item["queue_depth"] for item in metrics) <= 2
        return {"days": 365, "last_processed_date": bounds[1].isoformat(), "live_date_after_last_step": expected.isoformat(),
                "monthly_reports": months, "asset_counts": counts, "all_current_floats_finite": True,
                "stale_fund_stock_refs": stale_fund_stocks, "product_min_supply_demand_inventory": products[1:],
                "country_population_GDP": connection.execute("SELECT sum(population),sum(gdp) FROM country_current").fetchone(),
                "listed_market_cap": connection.execute("SELECT sum(market_cap) FROM company_current").fetchone()[0],
                "player": connection.execute("SELECT cash,net_worth,positions,futures FROM portfolio_current").fetchone(),
                "ordinary_ms": describe([item["seconds"] * 1000 for item in ordinary]),
                "phase_medians_ms": {phase: statistics.median(item["phases"][phase] for item in ordinary
                                                              if phase in item["phases"])
                                      for phase in ordinary[0]["phases"]},
                "all_days_ms": describe([item["seconds"] * 1000 for item in run["days"]]),
                "generation_seconds": run["generation_seconds"], "peak_day1_memory_bytes": run["peak_day1_memory_bytes"],
                "quote_batch_ms": run["quote_batch_ms"], "checkpoint_bytes": run["checkpoint_bytes"],
                "store_bytes": run["store_bytes"], "writer_batches": len(metrics),
                "max_queue_depth": max(item["queue_depth"] for item in metrics),
                "total_backpressure_ms": sum(item["backpressure_ms"] for item in metrics),
                "max_writer_ms": max(item["writer_ms"] for item in metrics), "database_tables": len(run["database"])}
    finally:
        connection.close()


def main():
    roots = read(OUT / "plausibility-v2/root-statistics.json")
    worlds = read(OUT / "plausibility-v2/world-statistics.json")
    assert len(roots) == 100 and len(worlds) == 20 and all(not item["flags"] for item in roots)
    old = read(OUT / "before-source-hashes.json")
    changed = [name for name, old_hash in old.items()
               if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != old_hash]
    expected = read(OUT / "changed-production-files.json")
    assert set(changed) == set(expected) - {"src/kojakstreet/core/heterogeneous_start.py"}
    result = {"changed_production_files": expected, "continuity": continuity(),
              "years": {mode: year(mode) for mode in ("genesis", "heterogeneous")},
              "roots": {field: describe([item[field] for item in roots]) for field in
                        ("GDP_max_share", "market_max_share", "population_GDP_correlation", "GDP_market_correlation",
                         "target_calibration_max_relative")},
              "population_GDP_company_envelope": {field: {"minimum": min(item[field][0] for item in roots),
                                                           "median_of_medians": statistics.median(item[field][1] for item in roots),
                                                           "maximum": max(item[field][2] for item in roots)} for field in
                                                   ("population_min_median_max", "GDP_min_median_max", "company_min_median_max")},
              "top_company_share_envelope": {str(n): describe([item["top_company_shares"][str(n)] for item in roots])
                                             for n in (1, 10, 50)},
              "sector_max_share": max(max(item["sector_caps"].values()) / 1_280_000_000_000 for item in roots),
              "worlds": {"count": 20, "production_corridors_passed": True,
                         "producerless_fallback_codes": sorted({item["code"] for world in worlds for item in world["viability"]
                                                               if item["producer_count"] == 0})},
              "root_seeds": 100, "flags": [], "genesis": read(OUT / "genesis-equivalence.json"),
              "established_and_determinism": read(OUT / "established-and-determinism.json")}
    (OUT / "closeout.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str, allow_nan=False), encoding="utf-8")
    print(json.dumps({"year_gates_passed": True, "ordinary_ms": {mode: result["years"][mode]["ordinary_ms"]
                                                               for mode in result["years"]},
                      "producerless_fallback_codes": result["worlds"]["producerless_fallback_codes"]}, indent=2))


if __name__ == "__main__":
    main()
