"""State containers for the next-generation Kojak Street core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class GameState:
    """Explicit state object used by the future PySide6 app.

    The current legacy app stores state in module-level variables in `daten.py`.
    This object gives the new app a stable target shape while adapters are built.
    """

    date: datetime
    cash: float
    display_currency: str
    stocks: dict[str, dict[str, Any]] = field(default_factory=dict)
    commodities: dict[str, dict[str, Any]] = field(default_factory=dict)
    processed_products: dict[str, dict[str, Any]] = field(default_factory=dict)
    cryptos: dict[str, dict[str, Any]] = field(default_factory=dict)
    funds: dict[str, dict[str, Any]] = field(default_factory=dict)
    indices: dict[str, dict[str, Any]] = field(default_factory=dict)
    derivatives: dict[str, dict[str, Any]] = field(default_factory=dict)
    portfolio: dict[str, dict[str, Any]] = field(default_factory=dict)
    perpetuals: dict[str, dict[str, Any]] = field(default_factory=dict)
    fx_balances: dict[str, float] = field(default_factory=dict)
    loans: dict[str, float] = field(default_factory=dict)
    bonds: list[dict[str, Any]] = field(default_factory=list)
    bond_market: list[dict[str, Any]] = field(default_factory=list)
    news: list[tuple[str, str, str]] = field(default_factory=list)
    macro: dict[str, dict[str, Any]] = field(default_factory=dict)
    macro_history: dict[str, list[Any]] = field(default_factory=dict)
    global_macro: dict[str, Any] = field(default_factory=dict)
    global_macro_history: dict[str, list[Any]] = field(default_factory=dict)
    forex_history: dict[str, list[Any]] = field(default_factory=dict)
    currency_strength: dict[str, float] = field(default_factory=dict)
    portfolio_history: list[Any] = field(default_factory=list)
    realized_pnl_history: list[Any] = field(default_factory=list)
