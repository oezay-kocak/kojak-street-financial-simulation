"""Service facade for portfolio trading mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kojakstreet.core.trade_preview import TradeValidation, validate_trade_request
from kojakstreet.core.trading import close_perpetual, exchange_currency, execute_spot_trade, open_perpetual


@dataclass(frozen=True, slots=True)
class TradeResult:
    action: str
    changed: bool = True
    received: float | None = None


class TradingService:
    """Stable boundary around legacy trading mutations."""

    def __init__(self, state: Any) -> None:
        self.state = state

    def trade_spot(self, ticker: str, quantity: float, side: str) -> TradeResult:
        execute_spot_trade(self.state, ticker, quantity, side)
        return TradeResult(action="spot")

    def validate_trade(self, ticker: str, mode: str, side: str, amount: float, leverage: int = 1) -> TradeValidation:
        return validate_trade_request(self.state, ticker, mode, side, amount, leverage)

    def open_future(self, ticker: str, direction: str, leverage: int, margin: float) -> TradeResult:
        open_perpetual(self.state, ticker, direction, leverage, margin)
        return TradeResult(action="future_open")

    def close_future(self, position_id: str) -> TradeResult:
        close_perpetual(self.state, position_id)
        return TradeResult(action="future_close")

    def exchange_currency(self, source_region: str, target_region: str, amount: float) -> TradeResult:
        received = exchange_currency(self.state, source_region, target_region, amount)
        return TradeResult(action="currency_exchange", received=received)
