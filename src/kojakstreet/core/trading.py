"""Trading mutations shared by the Qt runtime."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from kojakstreet.core.accounting import asset_price, asset_region, convert_amount
from kojakstreet.core.countries import RESERVE_CURRENCY
from kojakstreet.core.financial_products import (
    CDS_CONTRACT_TYPES,
    EXPIRING_DERIVATIVE_CONTRACT_TYPES,
    derivative_allows_spot_trade,
)


class TradeError(ValueError):
    """Raised when a requested trade cannot be executed."""


def execute_spot_trade(daten: Any, ticker: str, quantity: float, side: str) -> None:
    if quantity <= 0:
        raise TradeError("Quantity must be positive.")
    price = asset_price(daten, ticker)
    region = asset_region(daten, ticker)
    if price is None or region is None:
        raise TradeError("Unknown or non-tradable asset.")
    if ticker in getattr(daten, "indizes", {}):
        raise TradeError("Indices are not directly tradable.")
    derivative = getattr(daten, "derivatives", {}).get(ticker)
    if isinstance(derivative, dict) and not derivative_allows_spot_trade(derivative):
        raise TradeError("This derivative trades through futures only.")

    notional = quantity * price
    portfolio = _portfolio(daten)
    if side == "BUY":
        _debit_asset_currency_or_gd(daten, notional, region)
        position = portfolio.positions.setdefault(ticker, {"stueck": 0.0, "kaufkurs": 0.0})
        old_quantity = float(position.get("stueck", 0.0))
        old_average = float(position.get("kaufkurs", 0.0))
        new_quantity = old_quantity + quantity
        position["kaufkurs"] = ((old_quantity * old_average) + notional) / new_quantity
        position["stueck"] = new_quantity
        _copy_spot_derivative_contract(daten, ticker, position)
        return

    if side == "SELL":
        position = portfolio.positions.get(ticker)
        if not position or float(position.get("stueck", 0.0)) < quantity:
            raise TradeError("Not enough inventory.")
        average = float(position.get("kaufkurs", 0.0))
        pnl_local = quantity * (price - average)
        position["stueck"] = float(position.get("stueck", 0.0)) - quantity
        if position["stueck"] <= 0:
            del portfolio.positions[ticker]
        _credit(daten, notional, region)
        daten.realisierte_guv_historie.append((daten.datum, convert_amount(daten, pnl_local, region, "GD")))
        return

    raise TradeError("Unsupported spot side.")


def open_perpetual(daten: Any, ticker: str, direction: str, leverage: int, margin: float) -> None:
    if margin <= 0:
        raise TradeError("Margin must be positive.")
    if leverage < 1 or leverage > 5:
        raise TradeError("Leverage must be between 1x and 5x.")
    price = asset_price(daten, ticker)
    region = asset_region(daten, ticker)
    if price is None or region is None:
        raise TradeError("Unknown or non-tradable asset.")
    if ticker in getattr(daten, "indizes", {}):
        raise TradeError("Indices are not directly tradable.")
    direction = direction.upper()
    if direction not in {"LONG", "SHORT"}:
        raise TradeError("Future direction must be LONG or SHORT.")

    _debit_asset_currency_or_gd(daten, margin, region)
    portfolio = _portfolio(daten)
    size = (margin * leverage) / price
    derivative = getattr(daten, "derivatives", {}).get(ticker, {})
    expires_at = _future_expiry_date(daten, derivative) if _is_expiring_future(derivative) else None
    key = f"{ticker}_{direction}_{expires_at:%Y%m%d}" if expires_at is not None else f"{ticker}_{direction}"
    if key in portfolio.perpetuals:
        position = portfolio.perpetuals[key]
        old_size = float(position.get("groesse", 0.0))
        new_size = old_size + size
        position["einstiegskurs"] = (
            (old_size * float(position.get("einstiegskurs", price))) + (size * price)
        ) / new_size
        position["groesse"] = new_size
        position["margin"] = float(position.get("margin", 0.0)) + margin
        position["hebel"] = leverage
    else:
        position = {
            "ticker": ticker,
            "typ": direction,
            "hebel": leverage,
            "margin": margin,
            "groesse": size,
            "einstiegskurs": price,
            "land": region,
        }
        if expires_at is not None:
            position.update(
                {
                    "position_type": "DATED_FUTURE",
                    "instrument_type": derivative.get("instrument_type"),
                    "tenor_months": derivative.get("tenor_months"),
                    "expires_at": expires_at.strftime("%Y-%m-%d"),
                }
            )
        portfolio.perpetuals[key] = position


def close_perpetual(daten: Any, position_id: str) -> None:
    settle_perpetual(daten, position_id)


def settle_perpetual(daten: Any, position_id: str) -> dict[str, float | str]:
    portfolio = _portfolio(daten)
    position = portfolio.perpetuals.get(position_id)
    if not position:
        raise TradeError("Future position not found.")
    ticker = str(position.get("ticker", ""))
    price = asset_price(daten, ticker)
    if price is None:
        raise TradeError("Underlying price not found.")
    entry = float(position.get("einstiegskurs", price))
    size = float(position.get("groesse", 0.0))
    region = str(position.get("land", "GD"))
    pnl = (price - entry) * size if position.get("typ") == "LONG" else (entry - price) * size
    payout = max(0.0, float(position.get("margin", 0.0)) + pnl)
    _credit(daten, payout, region)
    daten.realisierte_guv_historie.append((daten.datum, convert_amount(daten, pnl, region, "GD")))
    del portfolio.perpetuals[position_id]
    return {"ticker": ticker, "pnl": pnl, "payout": payout, "region": region}


def exchange_currency(daten: Any, source_region: str, target_region: str, amount: float) -> float:
    if amount <= 0:
        raise TradeError("Amount must be positive.")
    if source_region == target_region:
        raise TradeError("Source and target currency must differ.")
    if _balance(daten, source_region) < amount:
        raise TradeError("Insufficient source currency balance.")
    received = convert_amount(daten, amount, source_region, target_region)
    _debit(daten, amount, source_region)
    _credit(daten, received, target_region)
    return received


def liquidation_price(position: dict) -> float:
    entry = float(position.get("einstiegskurs", 0.0))
    leverage = max(1.0, float(position.get("hebel", 1.0)))
    if position.get("typ") == "SHORT":
        return entry * (1.0 + (1.0 / leverage))
    return entry * (1.0 - (1.0 / leverage))


def _is_expiring_future(asset: dict) -> bool:
    return asset.get("instrument_type") in EXPIRING_DERIVATIVE_CONTRACT_TYPES


def _future_expiry_date(daten: Any, asset: dict) -> datetime:
    current_date = getattr(daten, "datum", getattr(daten, "date", None))
    if not isinstance(current_date, datetime):
        raise TradeError("Simulation date is required for expiring futures.")
    tenor_months = max(1.0, float(asset.get("tenor_months", 1.0)))
    return current_date + timedelta(days=round(tenor_months * 30))


def _copy_spot_derivative_contract(daten: Any, ticker: str, position: dict) -> None:
    derivative = getattr(daten, "derivatives", {}).get(ticker)
    if not isinstance(derivative, dict):
        return
    instrument_type = str(derivative.get("instrument_type", ""))
    if instrument_type != "Option" and instrument_type not in CDS_CONTRACT_TYPES:
        return
    for key in (
        "instrument_type",
        "underlying",
        "underlying_type",
        "option_type",
        "strike_price",
        "strike_moneyness",
        "tenor_months",
        "issue_date",
        "expires_at",
        "notional",
        "recovery_rate",
    ):
        if key in derivative:
            position[key] = derivative[key]


def _debit_asset_currency_or_gd(daten: Any, amount: float, region: str) -> None:
    if _balance(daten, region) >= amount:
        _debit(daten, amount, region)
        return
    gd_amount = convert_amount(daten, amount, region, RESERVE_CURRENCY)
    if _balance(daten, RESERVE_CURRENCY) >= gd_amount:
        _debit(daten, gd_amount, RESERVE_CURRENCY)
        return
    raise TradeError(f"Insufficient {region} balance and GD reserve.")


def _portfolio(daten: Any) -> Any:
    return getattr(daten, "portfolio", None) or _LegacyPortfolio(daten)


def _balance(daten: Any, region: str) -> float:
    return float(_portfolio(daten).fx_balances.get(region, 0.0))


def _debit(daten: Any, amount: float, region: str) -> None:
    balances = _portfolio(daten).fx_balances
    balances[region] = balances.get(region, 0.0) - amount


def _credit(daten: Any, amount: float, region: str) -> None:
    balances = _portfolio(daten).fx_balances
    balances[region] = balances.get(region, 0.0) + amount


class _LegacyPortfolio:
    def __init__(self, daten: Any) -> None:
        self.positions = daten.depot
        self.perpetuals = daten.perpetuals
        self.fx_balances = daten.forex_depot
