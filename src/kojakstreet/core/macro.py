"""Macro analytics for dashboard views."""

from __future__ import annotations

from dataclasses import dataclass, field

from kojakstreet.core.ratings import DEFAULT_RATING, default_probability, normalize_rating
from kojakstreet.core.state import GameState


@dataclass(slots=True)
class CountryMacroAnalytics:
    region: str
    gdp: float
    growth: float
    rate: float
    inflation: float
    unemployment: float
    balance_sheet: float
    debt_to_gdp: float
    credit_growth: float
    expected_growth: float
    expected_inflation: float
    expected_rate: float
    macro_surprise: float
    rating: str
    default_probability: float
    policy_signal: str
    risk_signal: str
    rate_trend: list[float] = field(default_factory=list)
    inflation_trend: list[float] = field(default_factory=list)
    growth_trend: list[float] = field(default_factory=list)
    unemployment_trend: list[float] = field(default_factory=list)
    balance_sheet_trend: list[float] = field(default_factory=list)


@dataclass(slots=True)
class MacroAnalytics:
    countries: list[CountryMacroAnalytics] = field(default_factory=list)
    average_growth: float = 0.0
    average_rate: float = 0.0
    average_inflation: float = 0.0
    average_unemployment: float = 0.0
    average_default_probability: float = 0.0


def build_macro_analytics(state: GameState, *, include_trends: bool = True) -> MacroAnalytics:
    countries = []
    for region, data in state.macro.items():
        growth = float(data.get("bip_prozent", 0.0))
        rate = float(data.get("zins", 0.0))
        inflation = float(data.get("inflation", 0.0))
        unemployment = float(data.get("arbeitslosigkeit", 0.0))
        rating = normalize_rating(str(data.get("rating", DEFAULT_RATING)))
        countries.append(
            CountryMacroAnalytics(
                region=region,
                gdp=float(data.get("bip_abs", 0.0)),
                growth=growth,
                rate=rate,
                inflation=inflation,
                unemployment=unemployment,
                balance_sheet=float(data.get("balance_sheet", 0.0)),
                debt_to_gdp=float(data.get("debt_to_gdp", 0.0)),
                credit_growth=float(data.get("credit_growth", 0.0)),
                expected_growth=float(data.get("expected_growth", growth)),
                expected_inflation=float(data.get("expected_inflation", inflation)),
                expected_rate=float(data.get("expected_rate", rate)),
                macro_surprise=float(data.get("macro_surprise_momentum", 0.0)),
                rating=rating,
                default_probability=default_probability(rating),
                policy_signal=_policy_signal(rate, inflation, growth),
                risk_signal=_risk_signal(inflation, growth, unemployment),
                rate_trend=_history_values(state, f"{region}_ZINS") if include_trends else [],
                inflation_trend=_history_values(state, f"{region}_INF") if include_trends else [],
                growth_trend=_history_values(state, f"{region}_BIP") if include_trends else [],
                unemployment_trend=_history_values(state, f"{region}_ALO") if include_trends else [],
                balance_sheet_trend=_history_values(state, f"{region}_BS") if include_trends else [],
            )
        )

    count = len(countries) or 1
    return MacroAnalytics(
        countries=countries,
        average_growth=sum(country.growth for country in countries) / count,
        average_rate=sum(country.rate for country in countries) / count,
        average_inflation=sum(country.inflation for country in countries) / count,
        average_unemployment=sum(country.unemployment for country in countries) / count,
        average_default_probability=sum(country.default_probability for country in countries) / count,
    )


def _history_values(state: GameState, key: str, limit: int = 36) -> list[float]:
    values = []
    for entry in state.macro_history.get(key, [])[-limit:]:
        try:
            values.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
        except (TypeError, ValueError):
            continue
    return values


def _policy_signal(rate: float, inflation: float, growth: float) -> str:
    if inflation > 0.035 and rate < 0.05:
        return "Behind Curve"
    if inflation > 0.03 and rate >= 0.05:
        return "Tight"
    if growth < 0.0 and rate <= 0.025:
        return "Easing"
    if growth < 0.0:
        return "Growth Support"
    return "Stable"


def _risk_signal(inflation: float, growth: float, unemployment: float) -> str:
    if inflation > 0.04:
        return "Inflation Risk"
    if growth < 0.0:
        return "Recession Risk"
    if unemployment > 0.08:
        return "Labor Stress"
    if growth > 0.03 and inflation < 0.025:
        return "Expansion"
    return "Balanced"
