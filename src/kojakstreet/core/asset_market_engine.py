"""Asset-market engine boundary for daily price updates."""

from __future__ import annotations

from typing import Any

from kojakstreet.core import market_calculations


class AssetMarketEngine:
    """Owns the prepared runtime path for all tradeable market prices."""

    def __init__(self, state: Any) -> None:
        self.state = state

    def update_daily_prices(self) -> None:
        market_calculations.update_markt_kurse(self.state)

    def warm_runtime_indexes(self) -> None:
        market_calculations.market_runtime_assets(self.state)
