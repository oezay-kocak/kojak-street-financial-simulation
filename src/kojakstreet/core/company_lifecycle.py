"""Monthly company update and lifecycle engine."""

from __future__ import annotations

import random
from collections.abc import Callable
from types import ModuleType
from typing import Any

from kojakstreet.core.companies import (
    bankrupt_tickers,
    corporate_credit_score,
    fill_company_universe,
    rating_from_finances,
    remove_bankrupt_companies,
    update_company_finances,
)
from kojakstreet.core.fundamentals import stage_fundamental_repricing, update_stock_fundamentals
from kojakstreet.core.psychology import update_asset_expectations
from kojakstreet.core.ratings import DEFAULT_RATING, RATINGS, default_probability, rating_index

NewsCallback = Callable[[str, str], None]


def update_monthly_companies(daten: ModuleType) -> None:
    energy_shock = monthly_energy_shock(daten)
    metals_shock = (daten.rohstoffe["HG"]["kurs"] + daten.rohstoffe["LIT"]["kurs"]) / 200.0
    for ticker, asset in daten.aktien.items():
        hedge = company_hedge_profile(daten, asset)
        result = random.uniform(-0.18, 0.18)
        result += (float(asset.get("capacity_utilization", 0.85)) - 0.85) * 0.18
        result += float(asset.get("production_score", 0.0)) * 0.32
        result -= float(asset.get("supply_chain_shortage", 0.0)) * 0.10 * (1.0 - hedge["input_cost"])
        result += float(asset.get("refinancing_momentum", 0.0)) * 0.40
        asset["refinancing_momentum"] = float(asset.get("refinancing_momentum", 0.0)) * 0.65
        regional_factor = company_regional_factor(daten, asset)
        result += (regional_factor - 1.0) * 0.18
        if daten.aktives_event and asset["land"] in daten.aktives_event["laender"]:
            result -= 0.35 * (1.0 - hedge["event"])
        asset["news_momentum"] = result
        land_growth = daten.makro.get(asset["land"], {}).get("bip_prozent", 0.002)
        sector_factor = sector_energy_factor(asset["branche"], energy_shock, metals_shock) * regional_factor
        sector_factor = 1.0 + ((sector_factor - 1.0) * (1.0 - hedge["sector"]))
        update_stock_fundamentals(asset, land_growth, result, sector_factor)
        update_company_finances_for_asset(daten, asset, sector_factor)
        stage_fundamental_repricing(asset)
        update_asset_expectations(asset, "Stock")
        update_company_rating(asset)
        if ticker in daten.depot and asset["kurs"] > 10.0:
            pay_dividend(daten, ticker, asset, land_growth)


def monthly_energy_shock(daten: ModuleType) -> float:
    energy_prices = [daten.rohstoffe[code] for code in ("CL", "TTF")]
    current_level = sum(float(asset["kurs"]) for asset in energy_prices) / len(energy_prices)
    previous_level = sum(
        float(asset.get("company_sector_reference_price", asset["kurs"])) for asset in energy_prices
    ) / len(energy_prices)
    for asset in energy_prices:
        asset["company_sector_reference_price"] = float(asset["kurs"])
    return current_level / max(0.01, previous_level)


def update_company_lifecycle(daten: ModuleType, add_news_callback: NewsCallback) -> None:
    failed = bankrupt_tickers(daten)
    if not failed:
        return
    failed_assets = [(ticker, daten.aktien[ticker]) for ticker in failed if ticker in daten.aktien]
    names = [asset.get("name", ticker) for ticker, asset in failed_assets[:3]]
    sectors = sorted({str(asset.get("branche", "")) for _ticker, asset in failed_assets if asset.get("branche")})
    remove_bankrupt_companies(daten, failed)
    replacements = fill_company_universe(daten)
    add_news_callback(
        " INSOLVENCY: "
        + ", ".join(names)
        + f" defaulted in {', '.join(sectors) or 'the market'}. {len(replacements)} new IPOs entered the market.",
        "ROT",
    )


def update_company_finances_for_asset(daten: ModuleType, asset: dict[str, Any], sector_factor: float) -> None:
    update_company_finances(
        asset,
        local_rate=float(daten.makro.get(asset["land"], {}).get("zins", 0.035)),
        sector_factor=sector_factor,
    )
    hedge = asset.get("hedge_profile", {})
    if isinstance(hedge, dict):
        coverage = float(hedge.get("overall", 0.0))
        asset["free_cash_flow"] = float(asset.get("free_cash_flow", 0.0)) * (1.0 + coverage * 0.018)
        revenue = max(1.0, float(asset.get("revenue", 1.0)))
        asset["fcf_margin"] = float(asset.get("free_cash_flow", 0.0)) / revenue
        asset["hedge_benefit"] = coverage


def company_hedge_profile(daten: ModuleType, asset: dict[str, Any]) -> dict[str, float]:
    sector = str(asset.get("branche", ""))
    output_mix = asset.get("output_mix") or {asset.get("specialization", ""): 1.0}
    input_signature = tuple(sorted(str(code) for code in output_mix))
    if asset.get("_hedge_input_signature") == input_signature:
        energy_exposure, metals_exposure, logistics_exposure = asset["_hedge_input_exposures"]
    else:
        input_codes = _company_input_codes(output_mix)
        energy_exposure = _input_share(input_codes, {"CL", "TTF", "NEWC", "FUEL", "FREIGHT", "SHIP", "AIRF"})
        metals_exposure = _input_share(input_codes, {"HG", "LIT", "COB", "NIK", "ALU", "STL", "XPD", "RHD", "XPT"})
        logistics_exposure = _input_share(input_codes, {"FREIGHT", "SHIP", "AIRF", "RAIL", "PORT", "WARE", "FUEL"})
        asset["_hedge_input_signature"] = input_signature
        asset["_hedge_input_exposures"] = (energy_exposure, metals_exposure, logistics_exposure)
    local_macro = daten.makro.get(str(asset.get("land", "")), {})
    rate_stress = max(0.0, float(local_macro.get("zins", 0.035)) - 0.04)
    inflation_stress = max(0.0, float(local_macro.get("inflation", 0.02)) - 0.03)
    credit_stress = max(0.0, float(local_macro.get("default_probability", 0.02)) - 0.04)
    base = {
        "Transport und Logistik": 0.44,
        "Automobil": 0.36,
        "Chemie": 0.34,
        "Maschinenbau": 0.30,
        "Landwirtschaft": 0.32,
        "Stromerzeuger": 0.26,
        "Technologie": 0.24,
        "Finanzen": 0.42,
        "Immobilien": 0.30,
        "Einzelhandel": 0.24,
    }.get(sector, 0.16)
    input_cost = _bounded(base + energy_exposure * 0.22 + metals_exposure * 0.14 + logistics_exposure * 0.16, 0.0, 0.62)
    rates = _bounded((0.28 if sector in {"Finanzen", "Immobilien", "Stromerzeuger"} else 0.12) + rate_stress * 2.5, 0.0, 0.55)
    inflation = _bounded((0.18 if sector in {"Konsumgüter", "Einzelhandel", "Transport und Logistik"} else 0.10) + inflation_stress * 2.0, 0.0, 0.46)
    credit = _bounded((0.26 if sector == "Finanzen" else 0.08) + credit_stress * 2.2, 0.0, 0.50)
    event = _bounded((input_cost * 0.50) + (rates * 0.18) + (inflation * 0.20) + (credit * 0.12), 0.0, 0.48)
    overall = _bounded((input_cost + rates + inflation + credit) / 4.0, 0.0, 0.52)
    profile = {
        "input_cost": input_cost,
        "rates": rates,
        "inflation": inflation,
        "credit": credit,
        "event": event,
        "sector": _bounded(max(input_cost, rates, inflation) * 0.65, 0.0, 0.42),
        "overall": overall,
    }
    asset["hedge_profile"] = profile
    asset["hedge_summary"] = _hedge_summary(profile)
    return profile


def _company_input_codes(output_mix: dict[str, Any]) -> set[str]:
    from kojakstreet.core.production_chains import INPUT_RECIPES, PROCESSED_PRODUCTS

    codes: set[str] = set()
    for output_code in output_mix:
        recipe = INPUT_RECIPES.get(str(output_code), {})
        if recipe:
            codes.update(recipe)
            continue
        definition = PROCESSED_PRODUCTS.get(str(output_code), {})
        codes.update(str(item) for item in definition.get("inputs", []))
    return codes


def _input_share(input_codes: set[str], watched: set[str]) -> float:
    if not input_codes:
        return 0.0
    return len(input_codes & watched) / len(input_codes)


def _hedge_summary(profile: dict[str, float]) -> str:
    ranked = sorted(
        [
            ("Input Cost", profile.get("input_cost", 0.0)),
            ("Rates", profile.get("rates", 0.0)),
            ("Inflation", profile.get("inflation", 0.0)),
            ("Credit", profile.get("credit", 0.0)),
        ],
        key=lambda item: item[1],
        reverse=True,
    )
    label, value = ranked[0]
    return f"{label} hedge {value * 100.0:.0f}%"


def update_company_rating(asset: dict[str, Any]) -> None:
    current_rating = asset.get("rating", DEFAULT_RATING)
    current_index = rating_index(current_rating)
    credit_score = corporate_credit_score(asset)
    target_index = rating_from_finances(asset, current_index, score=credit_score)
    pressure = float(asset.get("credit_rating_pressure", 0.0))
    gap = target_index - current_index
    if gap < 0:
        pressure -= min(1.5, 0.55 + abs(gap) * 0.12)
    elif gap > 0:
        pressure += min(2.0, 0.70 + gap * 0.16)
    else:
        pressure *= 0.50

    next_index = current_index
    if pressure <= -5.0:
        next_index = max(0, current_index - 1)
        pressure = 0.0
    elif pressure >= 3.0:
        next_index = min(len(RATINGS) - 1, current_index + 1)
        pressure = 0.0

    distress_before = int(asset.get("distress_months", 0))
    revenue = max(1.0, float(asset.get("revenue", 1.0)))
    distress_signals = sum(
        (
            float(asset.get("free_cash_flow", 0.0)) <= float(asset.get("interest_expense", 0.0)),
            float(asset.get("cash_reserves", 0.0)) / revenue < 0.02,
            float(asset.get("debt_to_market_cap", 0.0)) > 0.75,
            float(asset.get("interest_coverage", 4.0)) < 1.0,
        )
    )
    if distress_signals >= 3:
        distress_months = min(120, distress_before + 1)
    elif distress_signals >= 2:
        distress_months = max(0, distress_before)
    else:
        distress_months = max(0, distress_before - 2)
    if distress_before == 0 and distress_months > 0:
        asset["distress_episodes"] = int(asset.get("distress_episodes", 0)) + 1

    asset["rating"] = RATINGS[next_index]
    asset["default_probability"] = default_probability(asset["rating"])
    asset["credit_score"] = credit_score
    asset["credit_rating_target"] = RATINGS[target_index]
    asset["credit_rating_pressure"] = pressure
    asset["distress_months"] = distress_months
    if next_index != current_index:
        asset["rating_migrations"] = int(asset.get("rating_migrations", 0)) + 1
        key = "rating_upgrades" if next_index < current_index else "rating_downgrades"
        asset[key] = int(asset.get(key, 0)) + 1


def pay_dividend(daten: ModuleType, ticker: str, asset: dict[str, Any], land_growth: float) -> None:
    dividend_yield = float(asset.get("dividend_yield", 0.0))
    if dividend_yield <= 0 or (land_growth <= 0 and asset.get("free_cash_flow", 0.0) <= 0):
        return
    dividend = daten.depot[ticker]["stueck"] * asset["kurs"] * (dividend_yield / 12.0)
    daten.forex_depot[asset["land"]] = daten.forex_depot.get(asset["land"], 0.0) + dividend


def company_regional_factor(daten: ModuleType, asset: dict[str, Any]) -> float:
    country = str(asset.get("land", ""))
    macro = daten.makro.get(country, {})
    if not macro:
        return 1.0
    output_mix = asset.get("output_mix") or {asset.get("specialization"): 1.0}
    demand = macro.get("regional_demand", {})
    supply = macro.get("regional_supply", {})
    pressure = macro.get("regional_pressure", {})
    weighted_gap = 0.0
    weighted_pressure = 0.0
    total_share = 0.0
    for code, share in output_mix.items():
        share = float(share)
        local_demand = float(demand.get(code, 0.0))
        local_supply = max(1.0, float(supply.get(code, 0.0)))
        weighted_gap += _bounded((local_demand / local_supply) - 1.0, -0.35, 0.45) * share
        weighted_pressure += float(pressure.get(code, 0.0)) * share
        total_share += share
    if total_share > 0:
        weighted_gap /= total_share
        weighted_pressure /= total_share
    import_drag = float(macro.get("import_dependency", 0.0)) * 0.10
    export_boost = min(0.06, float(macro.get("export_strength", 0.0)) * 0.04)
    rating_boost = _bounded((0.035 - float(macro.get("default_probability", 0.02))) * 0.8, -0.08, 0.05)
    return _bounded(
        1.0 + weighted_gap * 0.12 + weighted_pressure * 0.08 + export_boost + rating_boost - import_drag,
        0.78,
        1.18,
    )


def sector_energy_factor(sector: str, energy_shock: float, metals_shock: float) -> float:
    factor = 1.0
    if sector in ["Transport und Logistik", "Automobil", "Chemie", "Maschinenbau", "Landwirtschaft"]:
        factor *= max(0.70, 1.0 - (energy_shock - 1.0) * 0.25)
    elif sector == "\u00d6l und Gas":
        factor *= min(1.40, 1.0 + (energy_shock - 1.0) * 0.30)
    # Utilities consume fuel through their production recipes. Treating the
    # same high fuel level as a sector-wide revenue windfall reverses that cost
    # exposure and compounds it again through monthly fundamentals.
    if sector == "Technologie":
        factor *= max(0.75, 1.0 - (metals_shock - 1.0) * 0.20)
    return factor


def _bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
