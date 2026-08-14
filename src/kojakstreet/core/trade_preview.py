"""Non-mutating trade-ticket previews for UI and tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kojakstreet.core.accounting import asset_price, asset_region, convert_amount
from kojakstreet.core.countries import RESERVE_CURRENCY
from kojakstreet.core.financial_products import CDS_CONTRACT_SCALE, CDS_CONTRACT_TYPES, derivative_allows_spot_trade
from kojakstreet.core.market_data_service import MarketDataService


@dataclass(frozen=True, slots=True)
class TradePreview:
    ticker: str
    side: str
    region: str
    price: float
    quantity: float
    notional: float
    margin: float
    leverage: int
    liquidation_price: float | None = None
    contract_size: float | None = None
    payout_hint: float | None = None
    reserve_cost: float | None = None
    is_valid: bool = True
    message: str = ""
    required_amount: float = 0.0
    available_amount: float = 0.0
    max_quantity: float | None = None


def build_trade_preview(daten: Any, ticker: str, side: str, quantity: float, leverage: int = 1) -> TradePreview:
    quote = MarketDataService(daten).quote(ticker)
    price = float(quote.price if quote is not None else asset_price(daten, ticker) or 0.0)
    region = str(quote.region if quote is not None else asset_region(daten, ticker) or RESERVE_CURRENCY)
    leverage = max(1, int(leverage))
    quantity = max(0.0, float(quantity))
    notional = quantity * price
    margin = notional / leverage
    derivative = getattr(daten, "derivatives", {}).get(ticker, {})
    instrument_type = str(derivative.get("instrument_type", ""))
    contract_size = None
    payout_hint = None
    if instrument_type in CDS_CONTRACT_TYPES:
        contract_size = float(derivative.get("notional", 0.0)) / CDS_CONTRACT_SCALE
        payout_hint = quantity * contract_size * (1.0 - float(derivative.get("recovery_rate", 0.40)))
    reserve_cost = convert_amount(daten, notional if side in {"BUY", "SELL"} else margin, region, RESERVE_CURRENCY)
    validation_amount = quantity if side in {"BUY", "SELL"} else margin
    validation = validate_trade_request(
        daten,
        ticker,
        "SPOT" if side in {"BUY", "SELL"} else "FUTURE",
        side,
        validation_amount,
        leverage,
    )
    return TradePreview(
        ticker=ticker,
        side=side,
        region=region,
        price=price,
        quantity=quantity,
        notional=notional,
        margin=margin,
        leverage=leverage,
        liquidation_price=_liquidation(price, side, leverage) if side in {"LONG", "SHORT"} else None,
        contract_size=contract_size,
        payout_hint=payout_hint,
        reserve_cost=reserve_cost,
        is_valid=validation.is_valid,
        message=validation.message,
        required_amount=validation.required_amount,
        available_amount=validation.available_amount,
        max_quantity=validation.max_quantity,
    )


@dataclass(frozen=True, slots=True)
class TradeValidation:
    is_valid: bool
    message: str = ""
    required_amount: float = 0.0
    available_amount: float = 0.0
    max_quantity: float | None = None


def validate_trade_request(
    daten: Any,
    ticker: str,
    mode: str,
    side: str,
    amount: float,
    leverage: int = 1,
) -> TradeValidation:
    mode = mode.upper()
    side = side.upper()
    amount = max(0.0, float(amount))
    if amount <= 0.0:
        return TradeValidation(False, "Amount must be positive.")
    service = MarketDataService(daten)
    quote = service.quote(ticker)
    if quote is None or quote.price <= 0.0:
        return TradeValidation(False, "Unknown or non-tradable asset.")
    if quote.asset_type == "Index":
        return TradeValidation(False, "Indices are not directly tradable.")
    if mode == "SPOT":
        asset = getattr(daten, "derivatives", {}).get(ticker, {})
        if quote.asset_type == "Derivative" and isinstance(asset, dict) and not derivative_allows_spot_trade(asset):
            return TradeValidation(False, "This derivative trades through futures only.")
        if side == "BUY":
            required = amount * quote.price
            available = _available_in_asset_currency_or_gd(daten, quote.region)
            max_quantity = available / quote.price if quote.price > 0.0 else 0.0
            if available + 1e-9 < required:
                return TradeValidation(False, f"Insufficient {quote.region} balance or GD reserve.", required, available, max_quantity)
            return TradeValidation(True, "", required, available, max_quantity)
        if side == "SELL":
            held = float(_portfolio_positions(daten).get(ticker, {}).get("stueck", 0.0))
            if held + 1e-9 < amount:
                return TradeValidation(False, "Not enough inventory.", amount, held, held)
            return TradeValidation(True, "", amount, held, held)
        return TradeValidation(False, "Unsupported spot side.")
    if mode == "FUTURE":
        if side not in {"LONG", "SHORT"}:
            return TradeValidation(False, "Future direction must be LONG or SHORT.")
        if leverage < 1 or leverage > 5:
            return TradeValidation(False, "Leverage must be between 1x and 5x.")
        required = amount
        available = _available_in_asset_currency_or_gd(daten, quote.region)
        max_quantity = (available * max(1, int(leverage))) / quote.price if quote.price > 0.0 else 0.0
        if available + 1e-9 < required:
            return TradeValidation(False, f"Insufficient {quote.region} balance or GD reserve.", required, available, max_quantity)
        return TradeValidation(True, "", required, available, max_quantity)
    return TradeValidation(False, "Unsupported trade mode.")


def _available_in_asset_currency_or_gd(daten: Any, region: str) -> float:
    local = _balance(daten, region)
    reserve = _balance(daten, RESERVE_CURRENCY)
    reserve_in_region = convert_amount(daten, reserve, RESERVE_CURRENCY, region)
    return max(local, reserve_in_region)


def _balance(daten: Any, region: str) -> float:
    portfolio = getattr(daten, "portfolio", None)
    if isinstance(portfolio, dict):
        balances = getattr(daten, "fx_balances", {})
        return float(balances.get(region, 0.0))
    balances = getattr(portfolio, "fx_balances", None) if portfolio is not None else None
    if balances is None:
        balances = getattr(daten, "forex_depot", getattr(daten, "fx_balances", {}))
    return float(balances.get(region, 0.0))


def _portfolio_positions(daten: Any) -> dict[str, dict[str, Any]]:
    portfolio = getattr(daten, "portfolio", None)
    if isinstance(portfolio, dict):
        return portfolio
    positions = getattr(portfolio, "positions", None) if portfolio is not None else None
    if positions is None:
        positions = getattr(daten, "depot", {})
    return positions


def _liquidation(price: float, side: str, leverage: int) -> float:
    if side == "SHORT":
        return price * (1.0 + 1.0 / leverage)
    return price * (1.0 - 1.0 / leverage)
