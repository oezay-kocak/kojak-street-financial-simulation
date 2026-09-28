"""Simplified fiscal balance and credit-cycle mechanics."""

from __future__ import annotations

from types import ModuleType

from kojakstreet.core.ratings import DEFAULT_RATING, rating_spread


def ensure_country_financials(daten: ModuleType) -> None:
    for macro in getattr(daten, "makro", {}).values():
        gdp = max(1.0, float(macro.get("bip_abs", 1_000.0)))
        macro.setdefault("government_debt", gdp * 0.62)
        macro.setdefault("fiscal_deficit", gdp * 0.025)
        macro.setdefault("debt_to_gdp", float(macro.get("government_debt", gdp * 0.62)) / gdp)
        macro.setdefault("interest_burden", float(macro.get("government_debt", gdp * 0.62)) * float(macro.get("zins", 0.035)) / gdp)
        macro.setdefault("fiscal_impulse", 0.0)
        macro.setdefault("fiscal_adjustment", 0.0)
        macro.setdefault("sovereign_funding_rate", float(macro.get("zins", 0.035)) + rating_spread(macro.get("rating", DEFAULT_RATING)))
        macro.setdefault("private_credit", gdp * 0.92)
        macro.setdefault("credit_growth", 0.018)


def pre_macro_impulses(daten: ModuleType, country: str) -> dict[str, float]:
    ensure_country_financials(daten)
    macro = daten.makro[country]
    credit_growth = float(macro.get("credit_growth", 0.0))
    fiscal_impulse = float(macro.get("fiscal_impulse", 0.0))
    interest_burden = float(macro.get("interest_burden", 0.0))
    return {
        "credit_growth": credit_growth,
        "growth_impulse": _clamp((credit_growth * 0.10) + (fiscal_impulse * 0.08) - max(0.0, interest_burden - 0.035) * 0.06, -0.012, 0.012),
        "inflation_impulse": _clamp((credit_growth * 0.025) + max(0.0, fiscal_impulse) * 0.030, -0.003, 0.004),
    }


def update_country_financials(daten: ModuleType, country: str) -> None:
    ensure_country_financials(daten)
    macro = daten.makro[country]
    gdp = max(1.0, float(macro.get("bip_abs", 1_000.0)))
    growth = float(macro.get("bip_prozent", 0.01))
    inflation = float(macro.get("inflation", 0.02))
    unemployment = float(macro.get("arbeitslosigkeit", 0.06))
    rate = float(macro.get("zins", 0.035))
    debt = max(0.0, float(macro.get("government_debt", gdp * 0.62)))
    private_credit = max(1.0, float(macro.get("private_credit", gdp * 0.92)))

    automatic_stabilizers = max(0.0, unemployment - 0.052) * 0.42 + max(0.0, -growth) * 0.24
    debt_to_gdp = debt / gdp
    funding_target = _clamp(
        rate
        + rating_spread(macro.get("rating", DEFAULT_RATING))
        + max(0.0, debt_to_gdp - 0.75) * 0.012,
        0.002,
        0.25,
    )
    previous_funding_rate = float(macro.get("sovereign_funding_rate", funding_target))
    funding_rate = previous_funding_rate + (funding_target - previous_funding_rate) * 0.20
    interest_burden = debt_to_gdp * funding_rate

    # The deficit ratio is annualized; only one twelfth is added to debt each
    # monthly macro step. Consolidation builds gradually when debt service is
    # high, and unwinds when the balance sheet recovers.
    adjustment_target = _clamp(
        max(0.0, debt_to_gdp - 0.75) * 0.030
        + max(0.0, interest_burden - 0.035) * 0.45
        + max(0.0, debt_to_gdp - 1.50) * 0.020,
        0.0,
        0.11,
    )
    previous_adjustment = float(macro.get("fiscal_adjustment", 0.0))
    fiscal_adjustment = previous_adjustment + (adjustment_target - previous_adjustment) * 0.18
    cyclical_relief = max(0.0, growth - 0.02) * 0.18 + max(0.0, inflation - 0.03) * 0.08
    deficit_ratio = _clamp(
        0.018 + automatic_stabilizers + interest_burden * 0.18 - fiscal_adjustment - cyclical_relief,
        -0.045,
        0.14,
    )
    debt = max(0.0, debt + (gdp * deficit_ratio / 12.0))

    credit_target = _clamp(0.024 + growth * 0.42 - max(0.0, rate - 0.035) * 0.85 - max(0.0, inflation - 0.04) * 0.30, -0.10, 0.12)
    previous_credit_growth = float(macro.get("credit_growth", credit_target))
    credit_growth = previous_credit_growth + ((credit_target - previous_credit_growth) * 0.28)
    private_credit = max(gdp * 0.18, private_credit * (1.0 + credit_growth / 12.0))

    macro["government_debt"] = debt
    macro["fiscal_deficit"] = gdp * deficit_ratio
    macro["debt_to_gdp"] = debt / gdp
    macro["interest_burden"] = (debt / gdp) * funding_rate
    macro["sovereign_funding_rate"] = funding_rate
    macro["fiscal_adjustment"] = fiscal_adjustment
    macro["fiscal_impulse"] = _clamp(deficit_ratio - 0.025, -0.04, 0.08)
    macro["private_credit"] = private_credit
    macro["credit_growth"] = credit_growth


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
