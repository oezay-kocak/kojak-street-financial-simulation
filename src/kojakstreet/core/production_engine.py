"""Monthly real-economy production and lifecycle engine boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kojakstreet.core.company_lifecycle import update_company_lifecycle, update_monthly_companies
from kojakstreet.core.monthly_assets import (
    update_crypto_lifecycle,
    update_crypto_production_inputs,
    update_monthly_commodities,
    update_monthly_crypto,
)
from kojakstreet.core.performance import timed_phase
from kojakstreet.core.production_chains import update_production_chain
from kojakstreet.core.production_signals import emit_production_chain_news

NewsCallback = Callable[[str, str], None]


class ProductionEngine:
    def __init__(self, state: Any) -> None:
        self.state = state

    def update_companies(self) -> None:
        with timed_phase(self.state, "monthly_companies_core"):
            update_monthly_companies(self.state)

    def update_company_lifecycle(self, add_news: NewsCallback) -> None:
        update_company_lifecycle(self.state, add_news)

    def update_commodities(self, macro_growth: float) -> None:
        with timed_phase(self.state, "monthly_commodities_core"):
            update_monthly_commodities(self.state, macro_growth)

    def update_production_chain(self, add_news: NewsCallback) -> None:
        with timed_phase(self.state, "monthly_crypto_inputs"):
            update_crypto_production_inputs(self.state)
        with timed_phase(self.state, "monthly_production_chain_core"):
            update_production_chain(self.state)
        with timed_phase(self.state, "monthly_production_news"):
            emit_production_chain_news(self.state, add_news)

    def update_daily_production_chain(self) -> None:
        with timed_phase(self.state, "daily_crypto_inputs"):
            update_crypto_production_inputs(self.state)
        with timed_phase(self.state, "daily_production_chain_core"):
            update_production_chain(
                self.state,
                advance_population=False,
                rebalance_company_outputs=False,
            )

    def update_crypto(self, macro_growth: float, world_rate: float) -> None:
        with timed_phase(self.state, "monthly_crypto_core"):
            update_monthly_crypto(self.state, macro_growth, world_rate)

    def update_crypto_lifecycle(self, add_news: NewsCallback) -> None:
        update_crypto_lifecycle(self.state, add_news)
