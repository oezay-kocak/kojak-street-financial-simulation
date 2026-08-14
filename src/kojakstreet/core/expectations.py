"""Simple macro expectation layer for market pricing."""

from __future__ import annotations

from types import ModuleType


def ensure_macro_expectations(daten: ModuleType) -> None:
    for macro in getattr(daten, "makro", {}).values():
        growth = float(macro.get("bip_prozent", 0.01))
        inflation = float(macro.get("inflation", 0.02))
        unemployment = float(macro.get("arbeitslosigkeit", 0.06))
        rate = float(macro.get("zins", 0.035))
        macro.setdefault("expected_growth", growth)
        macro.setdefault("expected_inflation", inflation)
        macro.setdefault("expected_unemployment", unemployment)
        macro.setdefault("expected_rate", rate)
        macro.setdefault("growth_surprise", 0.0)
        macro.setdefault("inflation_surprise", 0.0)
        macro.setdefault("unemployment_surprise", 0.0)
        macro.setdefault("rate_surprise", 0.0)
        macro.setdefault("macro_surprise_momentum", 0.0)


def update_daily_expectations(daten: ModuleType) -> None:
    ensure_macro_expectations(daten)
    for country, macro in getattr(daten, "makro", {}).items():
        targets = _event_adjusted_targets(daten, country, macro)
        speed = 0.026 if targets["event_active"] else 0.010
        macro["expected_growth"] = _smooth(float(macro["expected_growth"]), targets["growth"], speed)
        macro["expected_inflation"] = _smooth(float(macro["expected_inflation"]), targets["inflation"], speed)
        macro["expected_unemployment"] = _smooth(
            float(macro["expected_unemployment"]),
            targets["unemployment"],
            0.020 if targets["event_active"] else 0.008,
        )
        expected_rate_target = _policy_rate_target(
            float(macro["expected_growth"]),
            float(macro["expected_inflation"]),
        )
        macro["expected_rate"] = _smooth(float(macro["expected_rate"]), expected_rate_target, 0.018)
        for key in ("growth_surprise", "inflation_surprise", "unemployment_surprise", "rate_surprise"):
            macro[key] = float(macro.get(key, 0.0)) * 0.92
        macro["macro_surprise_momentum"] = float(macro.get("macro_surprise_momentum", 0.0)) * 0.90


def record_macro_report(daten: ModuleType, countries: list[str] | None = None) -> None:
    ensure_macro_expectations(daten)
    target_countries = countries or list(getattr(daten, "makro", {}))
    for country in target_countries:
        macro = daten.makro[country]
        growth_surprise = float(macro.get("bip_prozent", 0.0)) - float(macro.get("expected_growth", 0.0))
        inflation_surprise = float(macro.get("inflation", 0.0)) - float(macro.get("expected_inflation", 0.0))
        unemployment_surprise = float(macro.get("arbeitslosigkeit", 0.0)) - float(macro.get("expected_unemployment", 0.0))
        macro["growth_surprise"] = growth_surprise
        macro["inflation_surprise"] = inflation_surprise
        macro["unemployment_surprise"] = unemployment_surprise
        macro["macro_surprise_momentum"] = _clamp(
            (growth_surprise * 2.8) - (max(0.0, inflation_surprise) * 1.6) - (unemployment_surprise * 2.2),
            -0.08,
            0.08,
        )
        macro["expected_growth"] = _smooth(float(macro.get("expected_growth", 0.0)), float(macro.get("bip_prozent", 0.0)), 0.45)
        macro["expected_inflation"] = _smooth(
            float(macro.get("expected_inflation", 0.0)),
            float(macro.get("inflation", 0.0)),
            0.45,
        )
        macro["expected_unemployment"] = _smooth(
            float(macro.get("expected_unemployment", 0.0)),
            float(macro.get("arbeitslosigkeit", 0.0)),
            0.40,
        )


def record_policy_report(daten: ModuleType, countries: list[str] | None = None) -> None:
    ensure_macro_expectations(daten)
    target_countries = countries or list(getattr(daten, "makro", {}))
    for country in target_countries:
        macro = daten.makro[country]
        rate_surprise = float(macro.get("zins", 0.0)) - float(macro.get("expected_rate", 0.0))
        macro["rate_surprise"] = rate_surprise
        macro["macro_surprise_momentum"] = _clamp(
            float(macro.get("macro_surprise_momentum", 0.0)) - max(0.0, rate_surprise) * 1.8,
            -0.08,
            0.08,
        )
        macro["expected_rate"] = _smooth(float(macro.get("expected_rate", 0.0)), float(macro.get("zins", 0.0)), 0.65)


def expectation_aggregates(daten: ModuleType) -> dict[str, float]:
    ensure_macro_expectations(daten)
    countries = list(getattr(daten, "makro", {}))
    if not countries:
        return {
            "expected_growth": 0.01,
            "expected_inflation": 0.02,
            "expected_rate": 0.035,
            "surprise_index": 0.0,
        }
    total_gdp = sum(float(daten.makro[country].get("bip_abs", 1.0)) for country in countries) or 1.0

    def weighted(key: str) -> float:
        return sum(
            float(daten.makro[country].get(key, 0.0)) * (float(daten.makro[country].get("bip_abs", 1.0)) / total_gdp)
            for country in countries
        )

    return {
        "expected_growth": weighted("expected_growth"),
        "expected_inflation": weighted("expected_inflation"),
        "expected_rate": weighted("expected_rate"),
        "surprise_index": weighted("macro_surprise_momentum"),
    }


def _policy_rate_target(growth: float, inflation: float) -> float:
    return _clamp(0.035 + ((inflation - 0.02) * 1.45) + ((growth - 0.015) * 0.45), 0.0, 0.095)


def _event_adjusted_targets(daten: ModuleType, country: str, macro: dict) -> dict[str, float | bool]:
    growth = float(macro.get("bip_prozent", 0.01))
    inflation = float(macro.get("inflation", 0.02))
    unemployment = float(macro.get("arbeitslosigkeit", 0.06))
    event = getattr(daten, "aktives_event", None)
    if not event or country not in event.get("laender", []):
        return {
            "growth": growth,
            "inflation": inflation,
            "unemployment": unemployment,
            "event_active": False,
        }

    growth_drag = min(0.0, float(event.get("bip_makel", 0.0)))
    shock = abs(growth_drag)
    return {
        "growth": growth + growth_drag,
        "inflation": inflation + (shock * 0.42),
        "unemployment": unemployment + (shock * 0.72),
        "event_active": True,
    }


def _smooth(current: float, target: float, speed: float) -> float:
    return current + ((target - current) * speed)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
