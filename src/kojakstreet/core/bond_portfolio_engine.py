"""Owned-bond portfolio engine boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kojakstreet.core import bond_calculations


NewsCallback = Callable[[str, str], None]


class BondPortfolioEngine:
    def __init__(self, state: Any) -> None:
        self.state = state

    def update_owned_bonds(self, add_news: NewsCallback) -> None:
        bond_calculations.update_laufende_anleihen(add_news, self.state)
