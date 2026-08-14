"""Market-regime classifier for macro dashboards and asset explanations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MarketRegime:
    name: str
    risk_score: float
    inflation_score: float
    growth_score: float
    liquidity_score: float
    credit_stress: float


def classify_market_regime(daten: Any) -> MarketRegime:
    macro_values = [row for row in getattr(daten, "makro", {}).values() if isinstance(row, dict)]
    global_macro = getattr(daten, "global_macro", {})
    growth = _avg(float(row.get("bip_prozent", 0.01)) for row in macro_values)
    inflation = _avg(float(row.get("inflation", 0.02)) for row in macro_values)
    rate = _avg(float(row.get("zins", 0.035)) for row in macro_values)
    unemployment = _avg(float(row.get("arbeitslosigkeit", 0.06)) for row in macro_values)
    debt = _avg(float(row.get("debt_to_gdp", 0.62)) for row in macro_values)
    curve = float(global_macro.get("yield_curve_3y10y", 0.008))
    vix = float(global_macro.get("vix", 18.0))
    liquidity = float(global_macro.get("net_liquidity", getattr(daten, "gli_index", 15420.0)))

    growth_score = _clamp((growth - 0.012) / 0.035, -1.0, 1.0)
    inflation_score = _clamp((inflation - 0.025) / 0.075, -1.0, 1.0)
    liquidity_score = _clamp((liquidity / 93000.0 - 1.0) * 2.0 - max(0.0, rate - 0.045) * 8.0, -1.0, 1.0)
    credit_stress = _clamp(max(0.0, debt - 0.75) * 1.4 + max(0.0, unemployment - 0.075) * 5.0 + max(0.0, -curve) * 16.0, 0.0, 1.0)
    risk_score = _clamp(growth_score * 0.35 + liquidity_score * 0.35 - credit_stress * 0.45 - max(0.0, vix - 22.0) / 45.0, -1.0, 1.0)

    if credit_stress > 0.58:
        name = "Credit Stress"
    elif inflation_score > 0.40 and growth_score < -0.10:
        name = "Stagflation"
    elif growth_score < -0.35 and inflation_score < 0.20:
        name = "Deflation Risk"
    elif risk_score > 0.30 and liquidity_score > 0.10:
        name = "Risk-On"
    elif inflation_score > 0.35:
        name = "Inflation Pressure"
    else:
        name = "Balanced"
    return MarketRegime(name, risk_score, inflation_score, growth_score, liquidity_score, credit_stress)


def update_market_regime(daten: Any) -> MarketRegime:
    regime = classify_market_regime(daten)
    macro = getattr(daten, "global_macro", None)
    if isinstance(macro, dict):
        macro.pop("market_regime", None)
        macro["regime_risk_score"] = regime.risk_score
        macro["regime_inflation_score"] = regime.inflation_score
        macro["regime_growth_score"] = regime.growth_score
        macro["regime_liquidity_score"] = regime.liquidity_score
        macro["regime_credit_stress"] = regime.credit_stress
    setattr(daten, "market_regime", regime.name)
    return regime


def _avg(values) -> float:
    items = [float(value) for value in values]
    return sum(items) / len(items) if items else 0.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
