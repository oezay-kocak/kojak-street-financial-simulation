"""Global macro aggregates and market-impact signals."""

from __future__ import annotations

import random

from kojakstreet.core.expectations import expectation_aggregates, update_daily_expectations

METRICS = {
    "global_m2": "Global M2",
    "central_bank_balance_sheets": "Central Bank Balance Sheets",
    "rrp": "Global RRP",
    "tga": "Global TGA",
    "avg_3y_yield": "Avg 3Y Gov. Yield",
    "avg_5y_yield": "Avg 5Y Gov. Yield",
    "avg_10y_yield": "Avg 10Y Gov. Yield",
    "yield_curve_3y10y": "3Y-10Y Yield Curve",
    "global_cpi": "Global CPI",
    "global_gdp_growth": "Global GDP Growth",
    "global_unemployment": "Global Unemployment",
    "expected_global_growth": "Expected Global Growth",
    "expected_global_cpi": "Expected Global CPI",
    "expected_avg_policy_rate": "Expected Avg Policy Rate",
    "macro_surprise_index": "Macro Surprise Index",
    "vix": "VIX",
    "net_liquidity": "Net Liquidity",
    "regime_risk_score": "Regime Risk Score",
    "regime_inflation_score": "Regime Inflation Score",
    "regime_growth_score": "Regime Growth Score",
    "regime_liquidity_score": "Regime Liquidity Score",
    "regime_credit_stress": "Regime Credit Stress",
}


def ensure_global_macro(daten_module) -> None:
    if not hasattr(daten_module, "global_macro"):
        daten_module.global_macro = {}
    if not hasattr(daten_module, "GLOBAL_MACRO_HISTORIE"):
        daten_module.GLOBAL_MACRO_HISTORIE = {key: [] for key in METRICS}
    for key in METRICS:
        daten_module.GLOBAL_MACRO_HISTORIE.setdefault(key, [])

    macro = daten_module.global_macro
    if "avg_3y_yield" not in macro and "avg_1y_yield" in macro:
        macro["avg_3y_yield"] = float(macro["avg_1y_yield"]) + 0.003
    if "yield_curve_3y10y" not in macro and "yield_curve_1y10y" in macro:
        macro["yield_curve_3y10y"] = float(macro["yield_curve_1y10y"])
    aggregates = _country_aggregates(daten_module)
    balance_sheets = aggregates["balance_sheets"]
    macro.setdefault("global_m2", 100_000.0)
    macro.setdefault("central_bank_balance_sheets", balance_sheets)
    macro.setdefault("rrp", 7_500.0)
    macro.setdefault("tga", 4_500.0)
    macro.setdefault("avg_3y_yield", aggregates["avg_rate"] + 0.003)
    macro.setdefault("avg_5y_yield", aggregates["avg_rate"] + 0.005)
    macro.setdefault("avg_10y_yield", aggregates["avg_rate"] + 0.010)
    macro.setdefault("yield_curve_3y10y", 0.007)
    macro.setdefault("global_cpi", aggregates["avg_inflation"])
    macro.setdefault("global_gdp_growth", aggregates["avg_growth"])
    macro.setdefault("global_unemployment", aggregates["avg_unemployment"])
    expectations = expectation_aggregates(daten_module)
    macro.setdefault("expected_global_growth", expectations["expected_growth"])
    macro.setdefault("expected_global_cpi", expectations["expected_inflation"])
    macro.setdefault("expected_avg_policy_rate", expectations["expected_rate"])
    macro.setdefault("macro_surprise_index", expectations["surprise_index"])
    macro.setdefault("vix", 18.0)
    macro.setdefault("net_liquidity", macro["global_m2"] + balance_sheets - macro["rrp"] - macro["tga"])
    _append_histories(daten_module)


def update_global_macro(daten_module) -> None:
    ensure_global_macro(daten_module)
    update_daily_expectations(daten_module)
    macro = daten_module.global_macro
    aggregates = _country_aggregates(daten_module)
    expectations = expectation_aggregates(daten_module)
    observed_yields = _observed_government_yields(daten_module, aggregates["avg_rate"])
    market_pressure = _market_risk_pressure(daten_module)
    previous_net_liquidity = float(macro.get("net_liquidity", 1.0))
    previous_vix = float(macro.get("vix", 18.0))
    avg_rate = aggregates["avg_rate"]
    avg_growth = aggregates["avg_growth"]
    avg_inflation = aggregates["avg_inflation"]
    avg_unemployment = aggregates["avg_unemployment"]
    balance_sheets = aggregates["balance_sheets"]

    m2_impulse = (avg_growth / 365.0) + max(0.0, (0.035 - avg_rate)) * 0.0015
    macro["global_m2"] = max(10_000.0, float(macro["global_m2"]) * (1.0 + m2_impulse + random.uniform(-0.0002, 0.00035)))
    macro["central_bank_balance_sheets"] = balance_sheets

    rrp_target = 5_000.0 + max(0.0, avg_rate - 0.025) * 180_000.0
    tga_target = 3_500.0 + max(0.0, avg_rate - 0.020) * 80_000.0 + max(0.0, -avg_growth) * 45_000.0
    macro["rrp"] = _drift(float(macro["rrp"]), rrp_target, 0.015, -120.0, 160.0)
    macro["tga"] = _drift(float(macro["tga"]), tga_target, 0.012, -100.0, 140.0)

    macro["avg_3y_yield"] = observed_yields["3y"]
    macro["avg_5y_yield"] = observed_yields["5y"]
    macro["avg_10y_yield"] = observed_yields["10y"]
    macro["yield_curve_3y10y"] = max(-0.035, min(0.055, macro["avg_10y_yield"] - macro["avg_3y_yield"]))
    macro["global_cpi"] = avg_inflation
    macro["global_gdp_growth"] = avg_growth
    macro["global_unemployment"] = avg_unemployment
    macro["expected_global_growth"] = expectations["expected_growth"]
    macro["expected_global_cpi"] = expectations["expected_inflation"]
    macro["expected_avg_policy_rate"] = expectations["expected_rate"]
    macro["macro_surprise_index"] = expectations["surprise_index"]
    macro["net_liquidity"] = macro["global_m2"] + balance_sheets - macro["rrp"] - macro["tga"]

    liquidity_shock = _percent_change(macro["net_liquidity"], previous_net_liquidity)
    stress = 16.0
    stress += max(0.0, -avg_growth) * 280.0
    stress += max(0.0, avg_inflation - 0.035) * 180.0
    stress += max(0.0, avg_unemployment - 0.07) * 150.0
    stress += max(0.0, -macro["yield_curve_3y10y"]) * 260.0
    stress += max(0.0, -macro["macro_surprise_index"]) * 90.0
    stress -= max(0.0, liquidity_shock) * 220.0
    stress += market_pressure
    if getattr(daten_module, "aktives_event", None):
        stress += 8.0
    macro["vix"] = max(8.0, min(90.0, previous_vix * 0.88 + stress * 0.12 + random.uniform(-0.45, 0.55)))
    _append_histories(daten_module)


def global_market_signals(daten_module) -> dict[str, float]:
    ensure_global_macro(daten_module)
    macro = daten_module.global_macro
    history = daten_module.GLOBAL_MACRO_HISTORIE.get("net_liquidity", [])
    current_net = float(macro.get("net_liquidity", 1.0))
    previous_net = float(history[-2][0]) if len(history) >= 2 and isinstance(history[-2], (tuple, list)) else current_net
    liquidity_impulse = max(-0.04, min(0.04, _percent_change(current_net, previous_net)))
    vix = float(macro.get("vix", 18.0))
    risk_pressure = max(-0.08, min(0.18, (vix - 18.0) / 100.0))
    curve = float(macro.get("yield_curve_3y10y", macro.get("yield_curve_1y10y", 0.01)))
    return {
        "liquidity_impulse": liquidity_impulse,
        "risk_pressure": risk_pressure,
        "yield_curve": curve,
        "global_growth": float(macro.get("global_gdp_growth", 0.01)),
        "expected_growth": float(macro.get("expected_global_growth", macro.get("global_gdp_growth", 0.01))),
        "expected_cpi": float(macro.get("expected_global_cpi", macro.get("global_cpi", 0.02))),
        "macro_surprise": float(macro.get("macro_surprise_index", 0.0)),
        "global_cpi": float(macro.get("global_cpi", 0.02)),
        "vix": vix,
    }


def _country_aggregates(daten_module) -> dict[str, float]:
    countries = list(getattr(daten_module, "LAENDER", []))
    if not countries:
        return {"avg_rate": 0.035, "avg_growth": 0.01, "avg_inflation": 0.02, "avg_unemployment": 0.06, "balance_sheets": 5_000.0}
    weights = []
    total_gdp = sum(float(daten_module.makro[country].get("bip_abs", 1.0)) for country in countries)
    for country in countries:
        gdp = float(daten_module.makro[country].get("bip_abs", 1.0))
        weights.append(gdp / total_gdp if total_gdp > 0 else 1.0 / len(countries))

    def weighted(key: str, default: float) -> float:
        return sum(float(daten_module.makro[country].get(key, default)) * weight for country, weight in zip(countries, weights))

    return {
        "avg_rate": weighted("zins", 0.035),
        "avg_growth": weighted("bip_prozent", 0.01),
        "avg_inflation": weighted("inflation", 0.02),
        "avg_unemployment": weighted("arbeitslosigkeit", 0.06),
        "balance_sheets": sum(float(daten_module.makro[country].get("balance_sheet", 0.0)) for country in countries),
    }


def _observed_government_yields(daten_module, avg_rate: float) -> dict[str, float]:
    market = [
        bond
        for bond in getattr(daten_module, "bond_market", [])
        if str(bond.get("issuer_type", bond.get("bond_type", ""))) == "Government"
        and float(bond.get("yield_to_maturity", bond.get("yield", 0.0)) or 0.0) > 0.0
    ]
    if not market:
        return {
            "3y": avg_rate + 0.003,
            "5y": avg_rate + 0.005,
            "10y": avg_rate + 0.010,
        }
    y3 = _target_yield(market, 3.0, avg_rate + 0.003)
    y5 = max(y3 + 0.0005, _target_yield(market, 5.0, avg_rate + 0.005))
    y10 = max(y5 + 0.0005, _target_yield(market, 10.0, avg_rate + 0.010))
    return {"3y": y3, "5y": y5, "10y": y10}


def _target_yield(market: list[dict], target_years: float, fallback: float) -> float:
    weighted_total = 0.0
    total_weight = 0.0
    max_distance = max(1.75, target_years * 0.45)
    for bond in market:
        years = float(bond.get("maturity_years", bond.get("term_years", 0.0)) or 0.0)
        ytm = float(bond.get("yield_to_maturity", bond.get("yield", fallback)) or fallback)
        distance = abs(years - target_years)
        if years <= 0.0 or distance > max_distance:
            continue
        weight = 1.0 / (0.35 + distance)
        weighted_total += ytm * weight
        total_weight += weight
    return max(0.0, weighted_total / total_weight) if total_weight else max(0.0, fallback)


def _market_risk_pressure(daten_module) -> float:
    changes: list[float] = []
    for asset_book in (
        getattr(daten_module, "aktien", {}),
        getattr(daten_module, "kryptos", {}),
        getattr(daten_module, "fonds", {}),
        getattr(daten_module, "indizes", {}),
    ):
        for asset in asset_book.values():
            try:
                changes.append(float(asset.get("aenderung", 0.0)) / 100.0)
            except (TypeError, ValueError):
                continue
    if not changes:
        return 0.0
    average_change = sum(changes) / len(changes)
    downside = max(0.0, -average_change)
    dispersion = sum(abs(change - average_change) for change in changes) / len(changes)
    return min(18.0, downside * 520.0 + dispersion * 120.0)


def _append_histories(daten_module) -> None:
    date_text = daten_module.datum.strftime("%d.%m.%Y")
    for key in METRICS:
        value = float(daten_module.global_macro.get(key, 0.0))
        history = daten_module.GLOBAL_MACRO_HISTORIE.setdefault(key, [])
        if history and isinstance(history[-1], (tuple, list)) and len(history[-1]) > 1 and history[-1][1] == date_text:
            history[-1] = (value, date_text, "")
        else:
            history.append((value, date_text, ""))
        if len(history) > 520:
            del history[:-520]


def _drift(current: float, target: float, speed: float, noise_low: float, noise_high: float) -> float:
    return max(0.0, current + ((target - current) * speed) + random.uniform(noise_low, noise_high))


def _percent_change(current: float, previous: float) -> float:
    return (current - previous) / previous if previous else 0.0
