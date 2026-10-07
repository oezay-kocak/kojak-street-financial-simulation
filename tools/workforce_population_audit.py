"""Read-only domain audit; all calculations use detached diagnostic state.

No runtime, writer, player session, workforce model or production patch is created.
Existing checkpoints and DuckDB evidence are opened for reading only.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".cache/workforce-audit"


def load_checkpoint(path):
    from kojakstreet.core.checkpoints import decode
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return decode(json.load(stream))
    return decode(json.loads(path.read_text(encoding="utf-8")))


def main():
    import duckdb
    import numpy as np

    from kojakstreet.core.checkpoints import decode, encode, restore
    from kojakstreet.core.companies import BRANCHEN
    from kojakstreet.core.countries import COUNTRY_STYLES
    from kojakstreet.core.fast_history import _advance_correlated_state, _uniform
    from kojakstreet.core.fundamentals import SECTOR_PROFILES, update_stock_fundamentals
    from kojakstreet.core.label_codes import stable_label_code
    from kojakstreet.core.macro_calculations import update_makro_oekonomie
    from kojakstreet.core.production_chains import (
        SECTOR_INPUT_WEIGHTS,
        SECTOR_OUTPUTS,
        _initial_country_sector_focus,
        _sector_capacity_multiplier,
        update_population,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    evidence = {"scope": "audit only; detached calculations and read-only existing evidence"}
    cases = []
    for growth, unemployment, population in [(.015, .06, 20e6), (0, .06, 20e6),
                                            (-.06, .22, 20e6), (.045, .02, 20e6),
                                            (-1, .99, 2e6), (1, .02, 20e6)]:
        state = SimpleNamespace(makro={"case": {"bip_prozent": growth,
                                "arbeitslosigkeit": unemployment, "bevoelkerung": population}})
        rng_before = random.getstate()
        update_population(state)
        expected = max(-.0025, min(.0035, (growth - .005) * .025 - max(0, unemployment - .08) * .010))
        actual = state.makro["case"]
        assert actual["population_growth"] == expected
        assert actual["bevoelkerung"] == max(2e6, population * (1 + expected))
        assert rng_before == random.getstate()
        cases.append({"g": growth, "u": unemployment, "before": population, **actual,
                      "constant_inputs_annual_change": (1 + expected)**12 - 1})
    evidence["population_cases"] = cases

    base = ROOT / ".cache/heterogeneous-start"
    worlds = {
        "Genesis": base / "genesis-365-performance/day1-checkpoint.json",
        "Heterogeneous": base / "heterogeneous-365-performance/day1-checkpoint.json",
        "Established_hybrid_diagnostic": base / "current-established-hybrid/bundle/checkpoint.json.gz",
        "Established_daily_diagnostic": base / "current-established-daily/bundle/checkpoint.json.gz",
    }
    snapshots = {}
    for name, path in worlds.items():
        payload = load_checkpoint(path)
        world = payload["checkpoint"]
        snapshots[name] = world
        country_capacity = defaultdict(float)
        counts = Counter()
        for asset in world["aktien"].values():
            country_capacity[asset["land"]] += asset["production_capacity"]
            counts[(asset["land"], asset["branche"])] += 1
        capacity_per_person = [country_capacity[c] / m["bevoelkerung"] for c, m in world["makro"].items()]
        evidence.setdefault("worlds", {})[name] = {
            "path": str(path.relative_to(ROOT)), "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "date": world["datum"].isoformat(), "countries": len(world["makro"]), "companies": len(world["aktien"]),
            "population_total": sum(m["bevoelkerung"] for m in world["makro"].values()),
            "population_range": [min(m["bevoelkerung"] for m in world["makro"].values()), max(m["bevoelkerung"] for m in world["makro"].values())],
            "unemployment_range": [min(m["arbeitslosigkeit"] for m in world["makro"].values()), max(m["arbeitslosigkeit"] for m in world["makro"].values())],
            "capacity_per_person_max_min_ratio": max(capacity_per_person) / min(capacity_per_person),
            "companies_per_country_sector_range": [min(counts.values()), max(counts.values())],
            "stored_population_growth_range": [min(m["population_growth"] for m in world["makro"].values()), max(m["population_growth"] for m in world["makro"].values())],
        }
        # Full data-only roundtrip, including existing population/unemployment and RNG.
        restored = SimpleNamespace()
        restore(restored, decode(json.loads(json.dumps(encode(payload), allow_nan=False))))
        assert restored.makro == world["makro"]
        assert random.getstate() == payload["rng"]["python"]
        restored_np_rng = np.random.get_state()
        assert restored_np_rng[0] == payload["rng"]["numpy"][0]
        assert np.array_equal(restored_np_rng[1], payload["rng"]["numpy"][1])
        assert restored_np_rng[2:] == payload["rng"]["numpy"][2:]
        evidence["worlds"][name]["macro_roundtrip_exact"] = True

    # Observe actual macro RNG draws on detached state, with and without a crisis.
    macro_checks = []
    for crisis in (False, True):
        state = SimpleNamespace(**copy.deepcopy(snapshots["Genesis"]))
        country = next(iter(state.LAENDER))
        state.LAENDER = [country]
        state.makro = {country: state.makro[country]}
        old_u = state.makro[country]["arbeitslosigkeit"]
        state.aktives_event = {"laender": [country], "bip_makel": -.02} if crisis else None
        draws = []
        original = random.uniform
        def observed_uniform(low, high, draw_function=original, recorded=draws):
            result = draw_function(low, high)
            recorded.append([low, high, result])
            return result
        random.uniform = observed_uniform
        try:
            update_makro_oekonomie(lambda *_: None, state)
        finally:
            random.uniform = original
        updated = state.makro[country]
        after_event = old_u + (draws[2][2] if crisis else 0)
        expected_u = max(.02, after_event + (.015 - updated["bip_prozent"])*.45 + (.052 - after_event)*.18 + draws[4 if crisis else 2][2])
        assert math.isclose(expected_u, updated["arbeitslosigkeit"], abs_tol=1e-15)
        macro_checks.append({"crisis": crisis, "draws": draws, "old_u": old_u,
                             "g_new": updated["bip_prozent"], "u_new": updated["arbeitslosigkeit"]})
    evidence["macro_checks"] = macro_checks

    # Actual coarse advance: demonstrates separate population formula and stale growth field.
    coarse = SimpleNamespace(**copy.deepcopy(snapshots["Genesis"]))
    old = copy.deepcopy(coarse.makro)
    py_rng, np_rng = random.getstate(), np.random.get_state()
    when, dt, seed = date(1990, 12, 31), 1.0, 1729
    _advance_correlated_state(coarse, seed, when, dt)
    for country, macro in coarse.makro.items():
        rate = max(-.01, min(.025, .004 + _uniform(seed, when, f"population:{country}", -.006, .012)))
        assert macro["bevoelkerung"] == max(100_000, old[country]["bevoelkerung"] * (1 + rate * dt))
        assert macro["population_growth"] == old[country]["population_growth"]
    assert py_rng == random.getstate()
    after_np_rng = np.random.get_state()
    assert np_rng[0] == after_np_rng[0]
    assert np.array_equal(np_rng[1], after_np_rng[1])
    assert np_rng[2:] == after_np_rng[2:]
    evidence["coarse_population_check"] = {"countries_checked": len(coarse.makro), "global_rng_unchanged": True,
                                          "population_growth_field_unchanged": True}

    store_checks = {}
    for name in ("genesis", "heterogeneous"):
        path = base / f"{name}-365-performance/data/kojakstreet.duckdb"
        con = duckdb.connect(str(path), read_only=True)
        rows = con.execute("SELECT date, region, population, growth, unemployment FROM country_daily ORDER BY region, date").fetchall()
        groups = defaultdict(list)
        for row in rows:
            groups[row[1]].append(row)
        maximum_residual = 0.0
        for series in groups.values():
            for previous, current in pairwise(series):
                monthly = max(-.0025, min(.0035, (current[3] - .005)*.025 - max(0, current[4] - .08)*.010))
                expected = max(2e6, previous[2]*(1 + monthly))
                maximum_residual = max(maximum_residual, abs(current[2] - expected))
        assert maximum_residual < 1e-6
        assert all(r[0].day == 15 for r in rows)
        store_checks[name] = {"rows": len(rows), "dates": sorted({r[0].isoformat() for r in rows}),
                             "maximum_population_formula_residual": maximum_residual, "opened_read_only": True}
        con.close()
    evidence["existing_365_day_store_checks"] = store_checks

    # No workforce ratios: neutral three-scalar accumulation measures operation cost only.
    assets = list(snapshots["Heterogeneous"]["aktien"].values())
    country_ids = {country: i for i, country in enumerate(snapshots["Heterogeneous"]["makro"])}
    def aggregate():
        totals = [[0.0, 0.0, 0.0] for _ in country_ids]
        for asset in assets:
            total = totals[country_ids[asset["land"]]]
            value = float(asset["production_capacity"])
            for k in range(3):
                total[k] += value
        return totals
    for _ in range(10):
        aggregate()
    timings = []
    for _ in range(101):
        start = time.perf_counter()
        for _ in range(20):
            aggregate()
        timings.append((time.perf_counter() - start) / 20 * 1000)
    evidence["aggregation_microbenchmark"] = {"companies": len(assets), "countries": len(country_ids),
        "median_ms": statistics.median(timings), "p95_ms": sorted(timings)[95], "samples": len(timings),
        "limitation": "neutral three-accumulator workload only, no UI/DB/model/calibration or whole-day timing"}

    sensitivity = []
    template = next(iter(snapshots["Genesis"]["aktien"].values()))
    for delta in (.01, .03, .05, .10):
        before = copy.deepcopy(template)
        after = copy.deepcopy(template)
        update_stock_fundamentals(before, .015, 0, 1)
        update_stock_fundamentals(after, .015, 0, 1 + delta)
        result_after = copy.deepcopy(template)
        update_stock_fundamentals(result_after, .015, delta, 1)
        result_base_year, result_after_year = copy.deepcopy(template), copy.deepcopy(template)
        for _ in range(12):
            update_stock_fundamentals(result_base_year, .015, 0, 1)
            update_stock_fundamentals(result_after_year, .015, delta, 1)
        sensitivity.append({"modifier": delta, "daily_level_365_factor": (1 + delta)**365,
            "monthly_level_12_factor": (1 + delta)**12,
            "sector_factor_monthly_growth_delta_pp": (after["revenue_growth"] - before["revenue_growth"])*100,
            "sector_factor_fcf_margin_delta_pp": (after["fcf_margin"] - before["fcf_margin"])*100,
            "sector_factor_12_step_revenue_ratio_fixed_inputs": ((1 + after["revenue_growth"])/(1 + before["revenue_growth"]))**12,
            "result_first_month_growth_delta_pp": (result_after["revenue_growth"] - before["revenue_growth"])*100,
            "result_first_month_margin_delta_pp": (result_after["fcf_margin"] - before["fcf_margin"])*100,
            "result_12_month_revenue_ratio": result_after_year["revenue"] / result_base_year["revenue"]})
    evidence["shadow_sensitivity"] = sensitivity

    sectors = [{"name": sector, "id": stable_label_code(sector, category="sector"),
                "display_name": sector, "initial_companies_per_country": 4,
                "outputs": SECTOR_OUTPUTS[sector], "inputs": SECTOR_INPUT_WEIGHTS[sector],
                "profile": SECTOR_PROFILES[sector], "capacity_multiplier": _sector_capacity_multiplier(sector)} for sector in BRANCHEN]
    assert len(sectors) == 16 and len({s["id"] for s in sectors}) == 16
    evidence["sectors"] = sectors
    # Mechanical source inventory only; no workforce ratios or model written.
    used_focuses = set()
    focus_rows = []
    for country in COUNTRY_STYLES:
        focus = _initial_country_sector_focus(country, used_focuses)
        used_focuses.update(focus)
        focus_rows.append((country, focus))
    evidence["initial_country_focus"] = dict(focus_rows)
    lines = ["# Sektorinventur zum Workforce-Audit – 7. Oktober 2026", "",
             "Automatisch aus den unveränderten Produktionskonstanten gelesen. Keine Workforce-Anteile festgelegt.", "",
             "| Kanonischer Name / Display | Stabile ID | Firmen je Land beim Start | P/S | FCF-Grundmarge | Grunddividende | Kapazitäts-Wachstumsmodifier |",
             "|---|---|---|---|---|---|---|"]
    for sector in sectors:
        profile = sector["profile"]
        lines.append(f'| {sector["name"]} | {sector["id"]} | 4 | {profile["ps"]:g} | {profile["fcf_margin"]*100:g} % | {profile["dividend_yield"]*100:g} % | {sector["capacity_multiplier"]:g} |')
    lines += ["", "Die Modifier gelten nur im bestehenden Engpass-Expansionszweig. Bei normaler Auslastung ist Growth .005, bei Auslastung unter .50 −.006; Kapazität wird täglich .75/.25 zur Umsatzbasis zurückgeführt. Kein Beschäftigtenbestand. Produkt-Angebotskorridore haben eigene essential/industrial/cyclical/strategic/discretionary-Profile; eine Branche kann Produkte aus mehreren Profilen enthalten.", "",
              "## Outputs und sektorale Inputs", "",
              "Inputgewichte sind bestehende wirtschaftliche Nachfragegewichte, keine Mitarbeiteranteile. Produktrezepte in `PROCESSED_PRODUCTS`/`INPUT_RECIPES` kommen zusätzlich hinzu. Ein Unternehmen nutzt seinen Teilmix dieser sektoralen Outputliste; nicht jede Firma produziert alles."]
    for sector in sectors:
        lines += ["", f'### {sector["name"]} ({sector["id"]})', "",
                  "Outputs: " + ", ".join(sector["outputs"]) + ".", "",
                  "Sektorale Inputs: " + "; ".join(f"{code}={weight:g}" for code, weight in sector["inputs"].items()) + "."]
    lines += ["", "## Länderfokus und Bonusmechanik", "",
              "Alle Sektoren verwenden dieselbe Funktion `_country_sector_bonus`: Fokuswert (sonst 1) × clamp(1.05−Defaultwahrscheinlichkeit×.75,.72,1.08). Regionale Angebote werden danach auf globales Angebot normalisiert. Der Fokus ist kein zusätzlicher globaler Produktivitätsroot.", "",
              "Anfangsfokuswerte bei regulärer Länderreihenfolge und gemeinsamem `used_focuses`-Set:", "",
              "| Land | Vier Branchen mit Fokuswert |", "|---|---|"]
    for country, focus in focus_rows:
        lines.append("| " + country + " | " + "; ".join(f"{name} ×{value:g}" for name, value in focus.items()) + " |")
    lines += ["", "Die Initialisierung verwendet 1.18 für bevorzugte Branchen, +.08 solange eine Branche noch nicht im gemeinsamen Fokusset vorkam, sowie einen positionsabhängigen Zuschlag (Position modulo 3)×.04. Das ist keine zeitliche Rotation. Die bestehende zeitliche Veränderung erfolgt nach mindestens fünf Kalenderjahren: stärkste Kapazitätsbranche +.08 bis 1.38, schwächster anderer Fokus −.05 bis 1.02; Produktfokus wird neu abgeleitet. Initialer Produktfokus: erste drei Outputs je Fokusbranche ×1.10. Heterogeneous verwendet für die Firmenplatzierung statische bevorzugte Mitgliedschaft, keine laufenden Bonuswerte.", "",
              "## Weitere Sektormodifikatoren", "",
              "Monatliches `sector_energy_factor`: Transport/Automobil/Chemie/Maschinenbau/Landwirtschaft max(.70,1−(Energiepreisrelation−1)×.25); Öl/Gas min(1.40,1+(Relation−1)×.30); Technologie zusätzlich max(.75,1−(Metallschock−1)×.20). Stromerzeuger erhalten keinen gesonderten Energie-Windfall. Der regionale Faktor (.78–1.18) wird hinzugenommen; Unternehmens-Hedge schwächt Sektorexposition ab.", "",
              "Tägliches `stock_energy_price_signal` ist ein separater Kurskanal: Energie-Return auf ±.08 begrenzt, Transport/Automobil/Maschinenbau/Landwirtschaft −.30×Return, Öl/Gas +.18×Return, sonst 0. Das ist keine Arbeitsproduktivität. Kein Workforce-Effekt sollte zugleich in beide Kanäle eingebaut werden.", "",
              "## Quellen", ""]
    sources = [("core/companies.py", 20), ("core/label_codes.py", 8), ("core/fundamentals.py", 7),
               ("core/production_chains.py", 315), ("core/production_chains.py", 334),
               ("core/production_chains.py", 1403), ("core/production_chains.py", 1430),
               ("core/production_chains.py", 1473), ("core/production_chains.py", 1636),
               ("core/company_lifecycle.py", 284), ("core/market_calculations.py", 358)]
    for source, line in sources:
        absolute = (ROOT / "src/kojakstreet" / source).as_posix()
        lines.append(f"- [{source}:{line}](<{absolute}:{line}>)")
    (ROOT / "docs/workforce-sector-inventory-2026-10-07.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = json.loads((OUT / "before-hashes.json").read_text(encoding="utf-8-sig"))
    current = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in [ROOT / "daten.py", ROOT / "speicher.py", *sorted((ROOT / "src").rglob("*.py")), *sorted((ROOT / "tests").rglob("*.py"))]}
    differences = sorted(k for k in set(before) | set(current) if before.get(k) != current.get(k))
    assert not differences, differences
    evidence["production_test_hash_check"] = {"files": len(current), "differences": differences}
    (OUT / "diagnostics.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"result": "passed", "unchanged_files": len(current), "worlds": len(worlds),
                      "benchmark": evidence["aggregation_microbenchmark"], "output": str(OUT / "diagnostics.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
