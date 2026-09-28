from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

import daten
import pytest
from kojakstreet.core.accounting import convert_amount
from kojakstreet.core.countries import COUNTRIES
from kojakstreet.core.portfolio_risk import (
    update_future_settlements,
    update_spot_derivative_settlements,
)
from kojakstreet.core.trading import (
    TradeError,
    exchange_currency,
    execute_spot_trade,
    liquidation_price,
    open_perpetual,
)


def test_spot_trade_can_buy_foreign_asset_with_gold_dinar() -> None:
    old_cash = daten.bargeld
    old_fx = deepcopy(daten.forex_depot)
    old_depot = deepcopy(daten.depot)
    ticker = next(iter(daten.aktien))
    try:
        daten.bargeld = 0.0
        daten.forex_depot = {currency: 0.0 for currency in daten.WAEHRUNGEN}
        daten.forex_depot["GD"] = 25_000.0
        daten.depot = {}
        execute_spot_trade(daten, ticker, 10.0, "BUY")

        assert daten.depot[ticker]["stueck"] == 10.0
        assert daten.forex_depot["GD"] < 25_000.0
    finally:
        daten.bargeld = old_cash
        daten.forex_depot = old_fx
        daten.depot = old_depot


def test_future_trade_records_leverage_and_liquidation_price() -> None:
    old_fx = deepcopy(daten.forex_depot)
    old_perpetuals = deepcopy(daten.perpetuals)
    try:
        daten.forex_depot = {currency: 0.0 for currency in daten.WAEHRUNGEN}
        daten.forex_depot["GD"] = 25_000.0
        daten.perpetuals = {}
        ticker = next(iter(daten.kryptos))

        open_perpetual(daten, ticker, "LONG", 5, 1_000.0)

        position = daten.perpetuals[f"{ticker}_LONG"]
        assert position["hebel"] == 5
        assert liquidation_price(position) == position["einstiegskurs"] * 0.8
    finally:
        daten.forex_depot = old_fx
        daten.perpetuals = old_perpetuals


def test_derivative_future_records_expiry_and_settles_at_maturity() -> None:
    old_fx = deepcopy(daten.forex_depot)
    old_perpetuals = deepcopy(daten.perpetuals)
    old_realized = list(daten.realisierte_guv_historie)
    old_date = daten.datum
    future_ticker = next(
        ticker
        for ticker, asset in daten.derivatives.items()
        if asset["instrument_type"] == "Commodity Future" and asset["tenor_months"] == 1
    )
    old_price = daten.derivatives[future_ticker]["kurs"]
    trade_date = old_date.replace(year=1990, month=1, day=1)
    news: list[tuple[str, str]] = []
    try:
        daten.datum = trade_date
        daten.forex_depot = {currency: 0.0 for currency in daten.WAEHRUNGEN}
        daten.forex_depot["GD"] = 25_000.0
        daten.perpetuals = {}
        daten.realisierte_guv_historie = []

        open_perpetual(daten, future_ticker, "LONG", 2, 1_000.0)

        position_id, position = next(iter(daten.perpetuals.items()))
        entry = float(position["einstiegskurs"])
        size = float(position["groesse"])
        assert position_id.endswith("_19900131")
        assert position["position_type"] == "DATED_FUTURE"
        assert position["expires_at"] == "1990-01-31"

        daten.datum = trade_date + timedelta(days=29)
        update_future_settlements(daten, lambda text, category: news.append((text, category)))

        assert position_id in daten.perpetuals

        daten.derivatives[future_ticker]["kurs"] = entry + 10.0
        daten.datum = trade_date + timedelta(days=30)
        update_future_settlements(daten, lambda text, category: news.append((text, category)))

        expected_pnl = 10.0 * size
        assert position_id not in daten.perpetuals
        assert daten.realisierte_guv_historie[-1][1] == expected_pnl
        assert daten.forex_depot["GD"] == pytest.approx(24_000.0 + 1_000.0 + expected_pnl)
        assert news[-1][1] == "GRUEN"
        assert "FUTURE SETTLEMENT" in news[-1][0]
    finally:
        daten.forex_depot = old_fx
        daten.perpetuals = old_perpetuals
        daten.realisierte_guv_historie = old_realized
        daten.datum = old_date
        daten.derivatives[future_ticker]["kurs"] = old_price


def test_expiring_derivatives_cannot_be_bought_as_spot_assets() -> None:
    future_ticker = next(
        ticker
        for ticker, asset in daten.derivatives.items()
        if asset["instrument_type"] == "Commodity Future" and asset["tenor_months"] == 1
    )

    with pytest.raises(TradeError, match="futures only"):
        execute_spot_trade(daten, future_ticker, 1.0, "BUY")


def test_option_spot_position_settles_intrinsic_value_at_expiry() -> None:
    old_fx = deepcopy(daten.forex_depot)
    old_depot = deepcopy(daten.depot)
    old_realized = list(daten.realisierte_guv_historie)
    old_date = daten.datum
    option_ticker = next(
        ticker
        for ticker, asset in daten.derivatives.items()
        if asset["instrument_type"] == "Option" and asset["underlying_type"] == "Commodity"
    )
    option = daten.derivatives[option_ticker]
    underlying = option["underlying"]
    old_option = dict(option)
    old_underlying_price = daten.rohstoffe[underlying]["kurs"]
    news: list[tuple[str, str]] = []
    try:
        daten.forex_depot = {currency: 0.0 for currency in daten.WAEHRUNGEN}
        daten.forex_depot["GD"] = 25_000.0
        daten.depot = {}
        daten.realisierte_guv_historie = []
        option.update(
            {
                "kurs": 5.0,
                "option_type": "CALL",
                "strike_price": 100.0,
                "expires_at": old_date.strftime("%Y-%m-%d"),
            }
        )
        daten.rohstoffe[underlying]["kurs"] = 125.0

        execute_spot_trade(daten, option_ticker, 2.0, "BUY")
        update_spot_derivative_settlements(daten, lambda text, category: news.append((text, category)))

        assert option_ticker not in daten.depot
        assert daten.forex_depot["GD"] == 25_000.0 - 10.0 + 50.0
        assert daten.realisierte_guv_historie[-1][1] == 40.0
        assert "OPTION SETTLEMENT" in news[-1][0]
    finally:
        daten.forex_depot = old_fx
        daten.depot = old_depot
        daten.realisierte_guv_historie = old_realized
        daten.datum = old_date
        option.clear()
        option.update(old_option)
        daten.rohstoffe[underlying]["kurs"] = old_underlying_price


def test_cds_position_pays_out_on_sovereign_default_trigger() -> None:
    old_fx = deepcopy(daten.forex_depot)
    old_depot = deepcopy(daten.depot)
    old_realized = list(daten.realisierte_guv_historie)
    old_date = daten.datum
    cds_ticker = next(ticker for ticker, asset in daten.derivatives.items() if asset["instrument_type"] == "Credit Default Swap")
    cds = daten.derivatives[cds_ticker]
    country = cds["underlying"]
    old_cds = dict(cds)
    old_macro = dict(daten.makro[country])
    news: list[tuple[str, str]] = []
    try:
        daten.forex_depot = {currency: 0.0 for currency in daten.WAEHRUNGEN}
        daten.forex_depot[country] = 25_000.0
        daten.depot = {}
        daten.realisierte_guv_historie = []
        cds.update({"kurs": 25.0, "notional": 10_000_000.0, "recovery_rate": 0.40})
        daten.makro[country]["default_probability"] = 0.50

        execute_spot_trade(daten, cds_ticker, 1.0, "BUY")
        update_spot_derivative_settlements(daten, lambda text, category: news.append((text, category)))

        assert cds_ticker not in daten.depot
        assert daten.forex_depot[country] == 25_000.0 - 25.0 + 600.0
        assert daten.realisierte_guv_historie[-1][1] == convert_amount(daten, 575.0, country, "GD")
        assert "CDS SETTLEMENT" in news[-1][0]
    finally:
        daten.forex_depot = old_fx
        daten.depot = old_depot
        daten.realisierte_guv_historie = old_realized
        daten.datum = old_date
        cds.clear()
        cds.update(old_cds)
        daten.makro[country].clear()
        daten.makro[country].update(old_macro)


def test_corporate_cds_position_pays_out_on_company_default_trigger() -> None:
    old_fx = deepcopy(daten.forex_depot)
    old_depot = deepcopy(daten.depot)
    old_realized = list(daten.realisierte_guv_historie)
    cds_ticker = next(
        ticker
        for ticker, asset in daten.derivatives.items()
        if asset["instrument_type"] == "Corporate Credit Default Swap"
    )
    cds = daten.derivatives[cds_ticker]
    company_ticker = cds["underlying"]
    company = daten.aktien[company_ticker]
    old_cds = dict(cds)
    old_company = dict(company)
    news: list[tuple[str, str]] = []
    try:
        daten.forex_depot = {currency: 0.0 for currency in daten.WAEHRUNGEN}
        daten.forex_depot[company["land"]] = 25_000.0
        daten.depot = {}
        daten.realisierte_guv_historie = []
        cds.update({"kurs": 30.0, "notional": 10_000_000.0, "recovery_rate": 0.35})
        company["rating"] = "D"

        execute_spot_trade(daten, cds_ticker, 1.0, "BUY")
        update_spot_derivative_settlements(daten, lambda text, category: news.append((text, category)))

        assert cds_ticker not in daten.depot
        assert daten.forex_depot[company["land"]] == 25_000.0 - 30.0 + 650.0
        assert daten.realisierte_guv_historie[-1][1] == convert_amount(daten, 620.0, company["land"], "GD")
        assert "CDS SETTLEMENT" in news[-1][0]
    finally:
        daten.forex_depot = old_fx
        daten.depot = old_depot
        daten.realisierte_guv_historie = old_realized
        cds.clear()
        cds.update(old_cds)
        company.clear()
        company.update(old_company)


def test_exchange_currency_preview_formula_matches_trade_result() -> None:
    old_fx = deepcopy(daten.forex_depot)
    old_cash = daten.bargeld
    try:
        daten.forex_depot = {currency: 0.0 for currency in daten.WAEHRUNGEN}
        daten.forex_depot["GD"] = 1_000.0
        daten.bargeld = 0.0

        target = COUNTRIES[0].name
        received = exchange_currency(daten, "GD", target, 100.0)

        assert received > 0
        assert daten.forex_depot["GD"] == 900.0
        assert daten.forex_depot[target] >= received
    finally:
        daten.forex_depot = old_fx
        daten.bargeld = old_cash
