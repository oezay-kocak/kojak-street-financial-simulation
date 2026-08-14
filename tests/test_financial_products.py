from __future__ import annotations

import daten
from kojakstreet.core.financial_products import (
    derivative_allows_future_trade,
    derivative_allows_spot_trade,
    derivative_pricing_note,
    derivative_use_case,
    roll_expired_financial_products,
    update_financial_products,
)


def test_financial_product_universe_contains_requested_markets() -> None:
    instrument_types = {asset["instrument_type"] for asset in daten.derivatives.values()}

    assert {
        "Commodity Future",
        "Commodity Spread Future",
        "Corporate Credit Default Swap",
        "Credit Default Swap",
        "FX Forward",
        "Inflation Swap",
        "Input-Cost Spread",
        "Option",
        "Yield Future",
        "Freight Future",
    } <= instrument_types
    assert any(asset.get("underlying") == "FREIGHT" for asset in daten.derivatives.values())


def test_derivative_trade_modes_match_contract_settlement_style() -> None:
    future = next(asset for asset in daten.derivatives.values() if asset["instrument_type"] == "FX Forward")
    option = next(asset for asset in daten.derivatives.values() if asset["instrument_type"] == "Option")
    cds = next(asset for asset in daten.derivatives.values() if asset["instrument_type"] == "Credit Default Swap")

    assert derivative_allows_future_trade(future) is True
    assert derivative_allows_spot_trade(future) is False
    assert derivative_allows_spot_trade(option) is True
    assert derivative_allows_spot_trade(cds) is True
    assert "Hedges" in derivative_use_case(future)
    assert "scaled protection-value" in derivative_pricing_note(cds)
    assert "notional" in cds["pricing_note"]


def test_financial_products_reprice_from_market_data() -> None:
    future_ticker = next(ticker for ticker, asset in daten.derivatives.items() if asset["instrument_type"] == "Commodity Future")
    old_price = float(daten.derivatives[future_ticker]["kurs"])

    underlying = daten.derivatives[future_ticker]["underlying"]
    book = daten.rohstoffe if underlying in daten.rohstoffe else daten.processed_products
    previous_underlying_price = float(book[underlying]["kurs"])
    previous_history = list(daten.derivatives[future_ticker]["historie"])
    try:
        book[underlying]["kurs"] *= 1.05
        update_financial_products(daten, daten.datum.strftime("%d.%m.%Y"))

        assert float(daten.derivatives[future_ticker]["kurs"]) != old_price
        assert daten.derivatives[future_ticker]["historie"]
    finally:
        book[underlying]["kurs"] = previous_underlying_price
        daten.derivatives[future_ticker]["kurs"] = old_price
        daten.derivatives[future_ticker]["historie"] = previous_history


def test_options_keep_fixed_strike_until_contract_roll() -> None:
    option_ticker = next(ticker for ticker, asset in daten.derivatives.items() if asset["instrument_type"] == "Option")
    option = daten.derivatives[option_ticker]
    underlying = option["underlying"]
    book = daten.indizes if option["underlying_type"] == "Index" else daten.rohstoffe
    old_underlying_price = float(book[underlying]["kurs"])
    old_option = dict(option)
    old_history = list(option["historie"])
    old_date = daten.datum
    try:
        option["strike_price"] = 100.0
        option["option_type"] = "CALL"
        option["expires_at"] = (daten.datum.replace(day=1)).strftime("%Y-%m-%d")
        book[underlying]["kurs"] = 140.0

        update_financial_products(daten, daten.datum.strftime("%d.%m.%Y"))

        assert option["strike_price"] == 100.0
        assert float(option["intrinsic_value"]) == 40.0

        daten.datum = daten.datum.replace(day=2)
        roll_expired_financial_products(daten)

        assert option["strike_price"] == 140.0 * float(option["strike_moneyness"])
    finally:
        book[underlying]["kurs"] = old_underlying_price
        option.clear()
        option.update(old_option)
        option["historie"] = old_history
        daten.datum = old_date


def test_yield_future_blends_macro_with_government_bond_market_yields() -> None:
    future_ticker = next(
        ticker
        for ticker, asset in daten.derivatives.items()
        if asset["instrument_type"] == "Yield Future" and asset["tenor_years"] == 30
    )
    future = daten.derivatives[future_ticker]
    country = future["underlying"]
    old_market = list(daten.bond_market)
    old_price = future["kurs"]
    try:
        daten.bond_market = [
            {
                "issuer_type": "Government",
                "region": country,
                "yield_to_maturity": 0.09,
                "maturity_years": 30.0,
            }
        ]

        update_financial_products(daten, daten.datum.strftime("%d.%m.%Y"))

        assert future["bond_market_yield"] == 0.09
        assert future["yield_rate"] > 0.04
        assert future["kurs"] < old_price
    finally:
        daten.bond_market = old_market
        future["kurs"] = old_price


def test_new_derivative_families_reprice_from_their_drivers() -> None:
    fx_ticker = next(ticker for ticker, asset in daten.derivatives.items() if asset["instrument_type"] == "FX Forward")
    inflation_ticker = next(ticker for ticker, asset in daten.derivatives.items() if asset["instrument_type"] == "Inflation Swap")
    spread_ticker = next(ticker for ticker, asset in daten.derivatives.items() if asset["instrument_type"] == "Commodity Spread Future")
    input_ticker = next(ticker for ticker, asset in daten.derivatives.items() if asset["instrument_type"] == "Input-Cost Spread")
    old_values = {
        fx_ticker: daten.derivatives[fx_ticker]["kurs"],
        inflation_ticker: daten.derivatives[inflation_ticker]["kurs"],
        spread_ticker: daten.derivatives[spread_ticker]["kurs"],
        input_ticker: daten.derivatives[input_ticker]["kurs"],
    }
    old_macro = {country: dict(row) for country, row in daten.makro.items()}
    old_xau = daten.rohstoffe["XAU"]["kurs"]
    old_long = daten.derivatives[spread_ticker]["long_leg"]
    old_output = daten.derivatives[input_ticker]["output_code"]
    old_long_price = daten.rohstoffe.get(old_long, daten.processed_products.get(old_long))["kurs"]
    output_asset = daten.processed_products[old_output]
    old_output_price = float(output_asset.get("kurs", 100.0))
    try:
        daten.rohstoffe["XAU"]["kurs"] *= 1.08
        quote = daten.derivatives[fx_ticker]["quote_currency"]
        daten.makro[quote]["zins"] = 0.09
        country = daten.derivatives[inflation_ticker]["underlying"]
        daten.makro[country]["inflation"] = 0.08
        daten.rohstoffe.get(old_long, daten.processed_products.get(old_long))["kurs"] = old_long_price * 1.20
        output_asset["kurs"] = old_output_price * 1.25

        update_financial_products(daten, daten.datum.strftime("%d.%m.%Y"))

        assert daten.derivatives[fx_ticker]["kurs"] != old_values[fx_ticker]
        assert daten.derivatives[inflation_ticker]["kurs"] != old_values[inflation_ticker]
        assert daten.derivatives[spread_ticker]["kurs"] != old_values[spread_ticker]
        assert daten.derivatives[input_ticker]["kurs"] != old_values[input_ticker]
    finally:
        for country, row in old_macro.items():
            daten.makro[country].clear()
            daten.makro[country].update(row)
        daten.rohstoffe["XAU"]["kurs"] = old_xau
        daten.rohstoffe.get(old_long, daten.processed_products.get(old_long))["kurs"] = old_long_price
        output_asset["kurs"] = old_output_price
        for ticker, value in old_values.items():
            daten.derivatives[ticker]["kurs"] = value


def test_leveraged_and_short_funds_are_limited_to_one_to_four_ratio() -> None:
    leveraged_types = {"Short ETF", "Leveraged ETF", "Short Leveraged ETF"}
    leveraged = [fund for fund in daten.fonds.values() if fund.get("fund_type") in leveraged_types]
    normal = [fund for fund in daten.fonds.values() if fund.get("fund_type") not in leveraged_types]

    assert leveraged
    assert len(normal) >= len(leveraged) * 4
    assert {fund.get("leverage") for fund in leveraged} <= {-2.0, -1.0, 2.0}
