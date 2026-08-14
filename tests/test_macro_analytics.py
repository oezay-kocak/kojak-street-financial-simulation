from __future__ import annotations

import daten
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.macro import build_macro_analytics


def test_macro_analytics_builds_country_signals_and_trends() -> None:
    state = snapshot_from_legacy(daten)
    region = next(iter(state.macro))
    state.macro[region]["inflation"] = 0.045
    state.macro[region]["zins"] = 0.02
    state.macro_history[f"{region}_INF"] = [(0.02, "01.01.1990", ""), (0.045, "01.02.1990", "")]

    analytics = build_macro_analytics(state)
    country = next(country for country in analytics.countries if country.region == region)

    assert country.policy_signal == "Behind Curve"
    assert country.risk_signal == "Inflation Risk"
    assert country.inflation_trend == [0.02, 0.045]
    assert analytics.average_inflation > 0
