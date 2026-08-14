"""Macro-economic engine boundary for daily and monthly simulation steps."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kojakstreet.core import macro_calculations


NewsCallback = Callable[[str, str], None]


class MacroEngine:
    def __init__(self, state: Any) -> None:
        self.state = state

    def update_global_liquidity(self) -> None:
        macro_calculations.update_global_liquidity_index(self.state)

    def update_monthly_economy(self, add_news: NewsCallback) -> None:
        macro_calculations.update_makro_oekonomie(add_news, self.state)
        macro_calculations.update_sovereign_ratings(self.state)

    def run_policy_decision(self, add_news: NewsCallback) -> None:
        macro_calculations.fuehre_monatlichen_zinsentscheid_durch(add_news, self.state)
