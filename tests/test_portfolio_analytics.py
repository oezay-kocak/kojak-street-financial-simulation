from __future__ import annotations

from copy import deepcopy

import daten
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.portfolio import build_portfolio_analytics


def test_portfolio_analytics_calculates_unrealized_pnl_and_exposure() -> None:
    state = snapshot_from_legacy(daten)
    ticker, asset = next(iter(state.stocks.items()))
    state.portfolio = {ticker: {"stueck": 10.0, "kaufkurs": 80.0}}
    state.stocks = deepcopy(state.stocks)
    state.stocks[ticker]["kurs"] = 100.0

    state.currency_strength = {key: 1.0 for key in state.currency_strength}
    state.commodities["XAU"]["kurs"] = 100.0
    analytics = build_portfolio_analytics(state)

    assert analytics.total_value_gd == 1000.0
    assert analytics.total_cost_gd == 800.0
    assert analytics.unrealized_pnl_gd == 200.0
    assert analytics.unrealized_pnl_percent == 25.0
    assert analytics.region_exposure[asset["land"]] == 1000.0
    assert analytics.asset_type_exposure["Stock"] == 1000.0


def test_portfolio_analytics_classifies_derivative_positions() -> None:
    state = snapshot_from_legacy(daten)
    ticker, asset = next(iter(state.derivatives.items()))
    state.portfolio = {ticker: {"stueck": 5.0, "kaufkurs": 90.0}}
    state.derivatives = deepcopy(state.derivatives)
    state.derivatives[ticker]["kurs"] = 100.0

    state.currency_strength = {key: 1.0 for key in state.currency_strength}
    state.commodities["XAU"]["kurs"] = 100.0
    analytics = build_portfolio_analytics(state)

    assert analytics.positions[0].asset_type == "Derivative"
    assert analytics.asset_type_exposure["Derivative"] == 500.0
    assert analytics.region_exposure[asset["land"]] == 500.0
