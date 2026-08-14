"""Daily portfolio risk mechanics that mutate the runtime portfolio state."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from types import ModuleType

from kojakstreet.core.accounting import (
    asset_price,
    asset_region,
    convert_amount,
    update_credit_interest,
)
from kojakstreet.core.financial_products import (
    CDS_CONTRACT_SCALE,
    CDS_CONTRACT_TYPES,
    CDS_NOTIONAL,
    CDS_RECOVERY_RATE,
)
from kojakstreet.core.trading import settle_perpetual

NewsCallback = Callable[[str, str], None]


def update_credit_interest_charges(daten: ModuleType) -> None:
    update_credit_interest(daten)


def update_future_settlements(daten: ModuleType, add_news: NewsCallback) -> None:
    today = getattr(daten, "datum", None)
    if not isinstance(today, datetime):
        return
    for position_id, position in list(daten.perpetuals.items()):
        expires_at = _parse_expiry(position.get("expires_at"))
        if expires_at is None or today < expires_at:
            continue
        result = settle_perpetual(daten, position_id)
        add_news(
            f" FUTURE SETTLEMENT: {position['typ']} on {result['ticker']} expired with PnL {float(result['pnl']):,.2f} {result['region']}.",
            "GRUEN" if float(result["pnl"]) >= 0 else "ROT",
        )


def update_spot_derivative_settlements(daten: ModuleType, add_news: NewsCallback) -> None:
    today = getattr(daten, "datum", None)
    if not isinstance(today, datetime):
        return
    for ticker, position in list(getattr(daten, "depot", {}).items()):
        instrument_type = str(position.get("instrument_type", ""))
        if instrument_type == "Option":
            _settle_option_if_expired(daten, ticker, position, today, add_news)
        elif instrument_type in CDS_CONTRACT_TYPES:
            _settle_cds_if_triggered(daten, ticker, position, today, add_news)


def update_perpetual_liquidations(daten: ModuleType, add_news: NewsCallback) -> None:
    positions_to_delete = []
    for position_id, position in daten.perpetuals.items():
        ticker = position["ticker"]
        current_price = asset_price(daten, ticker)
        if current_price is None:
            continue
        entry_price = position["einstiegskurs"]
        leverage = position["hebel"]
        liquidated = False
        if position["typ"] == "LONG":
            liquidated = current_price <= entry_price * (1.0 - (1.0 / leverage))
        elif position["typ"] == "SHORT":
            liquidated = current_price >= entry_price * (1.0 + (1.0 / leverage))
        if liquidated:
            positions_to_delete.append(position_id)
            add_news(
                f" LIQUIDATION: {leverage}x {position['typ']} on {ticker} closed.",
                "ROT",
            )
    for position_id in positions_to_delete:
        del daten.perpetuals[position_id]


def _settle_option_if_expired(
    daten: ModuleType,
    ticker: str,
    position: dict,
    today: datetime,
    add_news: NewsCallback,
) -> None:
    expires_at = _parse_expiry(position.get("expires_at"))
    if expires_at is None or today < expires_at:
        return
    quantity = float(position.get("stueck", 0.0))
    strike = float(position.get("strike_price", 0.0))
    spot = _underlying_spot(daten, position)
    option_type = str(position.get("option_type", "CALL"))
    intrinsic = max(0.0, spot - strike) if option_type == "CALL" else max(0.0, strike - spot)
    payout = quantity * intrinsic
    region = asset_region(daten, ticker) or str(getattr(daten, "anzeige_waehrung", "GD"))
    pnl = payout - quantity * float(position.get("kaufkurs", 0.0))
    if payout > 0:
        _credit(daten, payout, region)
    getattr(daten, "realisierte_guv_historie", []).append((today, convert_amount(daten, pnl, region, "GD")))
    del daten.depot[ticker]
    add_news(
        f" OPTION SETTLEMENT: {ticker} expired with payout {payout:,.2f} {region}.",
        "GRUEN" if pnl >= 0 else "ROT",
    )


def _settle_cds_if_triggered(
    daten: ModuleType,
    ticker: str,
    position: dict,
    today: datetime,
    add_news: NewsCallback,
) -> None:
    expires_at = _parse_expiry(position.get("expires_at"))
    underlying = str(position.get("underlying", ""))
    underlying_type = str(position.get("underlying_type", "Sovereign"))
    reference = (
        getattr(daten, "aktien", {}).get(underlying, {})
        if underlying_type == "Corporate"
        else getattr(daten, "makro", {}).get(underlying, {})
    )
    triggered = _cds_default_triggered(reference)
    if not triggered and (expires_at is None or today < expires_at):
        return
    quantity = float(position.get("stueck", 0.0))
    notional = float(position.get("notional", CDS_NOTIONAL)) / CDS_CONTRACT_SCALE
    recovery_rate = float(position.get("recovery_rate", CDS_RECOVERY_RATE))
    payout = quantity * notional * (1.0 - recovery_rate) if triggered else 0.0
    region = asset_region(daten, ticker) or str(position.get("land", underlying))
    pnl = payout - quantity * float(position.get("kaufkurs", 0.0))
    if payout > 0:
        _credit(daten, payout, region)
    getattr(daten, "realisierte_guv_historie", []).append((today, convert_amount(daten, pnl, region, "GD")))
    del daten.depot[ticker]
    label = "triggered" if triggered else "expired"
    add_news(
        f" CDS SETTLEMENT: {ticker} {label} with payout {payout:,.2f} {region}.",
        "GRUEN" if pnl >= 0 else "ROT",
    )


def _cds_default_triggered(macro: dict) -> bool:
    rating = str(macro.get("rating", "")).upper()
    default_probability = float(macro.get("default_probability", macro.get("default_prob", 0.0)))
    return rating == "D" or default_probability >= 0.45 or bool(macro.get("sovereign_default"))


def _underlying_spot(daten: ModuleType, position: dict) -> float:
    ticker = str(position.get("underlying", ""))
    asset_type = str(position.get("underlying_type", ""))
    if asset_type == "Index":
        asset = getattr(daten, "indizes", {}).get(ticker, {})
    elif asset_type == "Commodity":
        asset = getattr(daten, "rohstoffe", {}).get(ticker, {})
    else:
        asset = {}
    return float(asset.get("kurs", 0.0))


def _credit(daten: ModuleType, amount: float, region: str) -> None:
    portfolio = getattr(daten, "portfolio", None)
    balances = getattr(portfolio, "fx_balances", None) if portfolio is not None else None
    if balances is None:
        balances = daten.forex_depot
    balances[region] = balances.get(region, 0.0) + amount


def _parse_expiry(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
