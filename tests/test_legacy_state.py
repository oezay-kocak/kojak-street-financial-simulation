from __future__ import annotations

import daten
from kojakstreet.adapters.legacy_state import UI_HISTORY_LIMIT, snapshot_from_legacy
from kojakstreet.core.countries import COUNTRIES
from kojakstreet.core.cryptos import TARGET_CRYPTO_COUNT


def test_snapshot_from_legacy_reads_asset_universe() -> None:
    state = snapshot_from_legacy(daten)

    assert state.cash == 25000.0
    assert state.fx_balances["GD"] == 25000.0
    assert len(state.stocks) > 250
    assert len(state.commodities) == 34
    assert len(state.processed_products) > 40
    assert len(state.cryptos) == TARGET_CRYPTO_COUNT
    assert len(state.macro) == len(COUNTRIES)
    assert all(country["bevoelkerung"] == 20_000_000.0 for country in state.macro.values())
    assert all("cash_reserves" in asset and "debt" in asset for asset in state.stocks.values())


def test_markets_snapshot_includes_fx_balances_for_trade_validation() -> None:
    state = snapshot_from_legacy(daten, profile="markets")

    assert state.fx_balances["GD"] == 25000.0


def test_portfolio_snapshot_includes_asset_histories_for_position_charts() -> None:
    ticker = next(iter(daten.aktien))
    original_history = daten.aktien[ticker]["historie"]
    daten.aktien[ticker]["historie"] = [(100.0 + index, "01.01.1990", "") for index in range(12)]
    try:
        state = snapshot_from_legacy(daten, profile="portfolio")
    finally:
        daten.aktien[ticker]["historie"] = original_history

    assert len(state.stocks[ticker]["historie"]) == 12


def test_snapshot_from_legacy_detaches_mutable_data() -> None:
    state = snapshot_from_legacy(daten)
    ticker = next(iter(state.stocks))

    state.stocks[ticker]["kurs"] = 999999.0
    state.stocks[ticker]["historie"].append((999999.0, "02.01.1990", ""))

    assert daten.aktien[ticker]["kurs"] != 999999.0
    assert not daten.aktien[ticker]["historie"] or daten.aktien[ticker]["historie"][-1][0] != 999999.0


def test_snapshot_from_legacy_limits_ui_history() -> None:
    ticker = next(iter(daten.aktien))
    original_history = daten.aktien[ticker]["historie"]
    daten.aktien[ticker]["historie"] = [(float(index), "01.01.1990", "") for index in range(700)]
    try:
        state = snapshot_from_legacy(daten)
    finally:
        daten.aktien[ticker]["historie"] = original_history

    assert len(state.stocks[ticker]["historie"]) == UI_HISTORY_LIMIT
    assert state.stocks[ticker]["historie"][0][0] == 180.0
