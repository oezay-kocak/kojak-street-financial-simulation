"""Portfolio, credit and net-worth calculations for the integrated runtime."""

from __future__ import annotations

from typing import Any

from kojakstreet.core.countries import RESERVE_CURRENCY
from kojakstreet.core.market_data_service import MarketDataService


def asset_price(daten: Any, ticker: str) -> float | None:
    assets = getattr(daten, "assets", None)
    if assets is not None and hasattr(assets, "price"):
        return assets.price(ticker)
    return MarketDataService(daten).price(ticker)


def asset_region(daten: Any, ticker: str) -> str | None:
    assets = getattr(daten, "assets", None)
    if assets is not None and hasattr(assets, "region"):
        return assets.region(ticker)
    return MarketDataService(daten).region(ticker)


def currency_strength(daten: Any, region: str) -> float:
    if region == "GD":
        try:
            commodities = getattr(daten, "rohstoffe", getattr(daten, "commodities", {}))
            return max(0.0001, float(commodities["XAU"]["kurs"]) / 100.0)
        except (AttributeError, KeyError, TypeError, ValueError):
            return 1.0
    strengths = getattr(daten, "waehrungen_staerke", getattr(daten, "currency_strength", {}))
    return max(0.0001, float(strengths.get(region, 1.0)))


def convert_amount(daten: Any, amount: float, source_region: str, target_region: str) -> float:
    if source_region == target_region:
        return amount
    return amount * (currency_strength(daten, source_region) / currency_strength(daten, target_region))


def get_net_worth(daten: Any) -> float:
    total_value = convert_amount(daten, daten.bargeld, RESERVE_CURRENCY, RESERVE_CURRENCY)
    for land, amount in daten.forex_depot.items():
        total_value += convert_amount(daten, amount, land, "GD")
    for ticker, position in daten.depot.items():
        quantity = position.get("stueck", 0)
        price = asset_price(daten, ticker)
        region = asset_region(daten, ticker)
        if quantity > 0 and price is not None and region is not None:
            total_value += convert_amount(daten, quantity * price, region, RESERVE_CURRENCY)
    for bond in daten.anleihen:
        total_value += convert_amount(daten, _owned_bond_market_value(daten, bond), bond.get("land", RESERVE_CURRENCY), RESERVE_CURRENCY)
    for position in getattr(daten, "perpetuals", {}).values():
        ticker = position.get("ticker", "")
        price = asset_price(daten, ticker)
        if price is None:
            continue
        entry = float(position.get("einstiegskurs", price))
        size = float(position.get("groesse", 0.0))
        margin = float(position.get("margin", 0.0))
        pnl = (price - entry) * size if position.get("typ") == "LONG" else (entry - price) * size
        total_value += convert_amount(daten, max(0.0, margin + pnl), position.get("land", RESERVE_CURRENCY), RESERVE_CURRENCY)

    open_debt = 0.0
    for land, debt in daten.kredite.items():
        open_debt += convert_amount(daten, debt, land, RESERVE_CURRENCY)
    return total_value - open_debt


def _owned_bond_market_value(daten: Any, bond: dict) -> float:
    nominal = float(bond.get("nominal", 0.0))
    if nominal <= 0.0:
        return 0.0
    if "market_price" in bond:
        return nominal * float(bond.get("market_price", 100.0)) / 100.0
    if "price" in bond:
        return nominal * float(bond.get("price", 100.0)) / 100.0
    symbol = str(bond.get("symbol", ""))
    if symbol:
        lookup = getattr(daten, "bond_market_by_symbol", {})
        market_bond = lookup.get(symbol) if isinstance(lookup, dict) else None
        if isinstance(market_bond, dict):
            return nominal * float(market_bond.get("price", 100.0)) / 100.0
    return nominal


def update_credit_interest(daten: Any) -> None:
    loans = getattr(getattr(daten, "portfolio", None), "loans", daten.kredite)
    fx_balances = getattr(getattr(daten, "portfolio", None), "fx_balances", daten.forex_depot)
    for land, debt in loans.items():
        if debt <= 0:
            continue
        macro = daten.makro.get(land, {"zins": 0.05})
        daily_interest = (debt * (macro.get("zins", 0.05) + 0.06)) / 365.0
        fx_balances[land] = fx_balances.get(land, 0.0) - daily_interest
