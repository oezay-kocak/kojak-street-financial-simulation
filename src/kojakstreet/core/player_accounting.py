"""Player-only settlement marks and random stream, separate from world evolution."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from kojakstreet.core.simulation_state import AssetRepository


def player_uniform(daten: Any, low: float, high: float) -> float:
    rng = random.Random(0)
    state = getattr(daten, "player_rng_state", None)
    if state is None:
        seed = f"kojakstreet/player/v1/{getattr(daten, 'simulation_seed', 0)}"
        rng.seed(int.from_bytes(hashlib.sha256(seed.encode()).digest(), "big"))
    else:
        rng.setstate(state)
    value = rng.uniform(low, high)
    daten.player_rng_state = rng.getstate()
    return value


def bond_credit_uniform(daten: Any, bond: dict) -> float:
    """A keyed world credit event: same issue/date, regardless of ownership."""
    key = {
        "domain": "kojakstreet/bond-credit/v1",
        "seed": getattr(daten, "simulation_seed", 0),
        "issuer": str(bond.get("ticker", "")),
        "symbol": str(bond.get("symbol", "")),
        "currency": str(bond.get("land", "GD")),
        "date": daten.datum.isoformat(),
        "term": bond.get("laufzeit_tage", bond.get("initial_resttage", 365)),
    }
    seed = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).digest()
    return random.Random(int.from_bytes(seed, "big")).random()


def remove_player_assets(daten: Any, tickers: set[str], *, corporate: bool = False) -> None:
    for ticker in tickers:
        daten.depot.pop(ticker, None)
    for key, position in list(getattr(daten, "perpetuals", {}).items()):
        if str(position.get("ticker", "")) in tickers:
            daten.perpetuals.pop(key, None)
    if corporate:
        for bond in getattr(daten, "anleihen", []):
            if str(bond.get("ticker", "")) in tickers:
                bond.update(rating="D", defaulted=True)


def visible_news(daten: Any) -> list:
    world = list(getattr(daten, "NEWS_SPEICHER", []))
    player = list(getattr(daten, "PLAYER_NEWS_SPEICHER", []))
    if not player:
        return world

    def date_key(item):
        try:
            return date.fromisoformat("-".join(reversed(str(item[0]).split("."))))
        except (ValueError, TypeError, IndexError):
            return date.min

    return sorted([*player, *world], key=date_key, reverse=True)[:50]


@dataclass
class PlayerDay:
    date: datetime
    events: list[tuple] = field(default_factory=list)
    credit_rates: dict = field(default_factory=dict)
    settlement_contracts: dict = field(default_factory=dict)

    def apply_events(self, daten: Any) -> None:
        for event in self.events:
            kind, ticker, *values = event
            if kind in {"dividend", "crypto_fee"}:
                position = daten.depot.get(ticker)
                if position is None:
                    continue
                if kind == "dividend":
                    price, rate, currency = values
                    payout = position["stueck"] * price * rate
                else:
                    amount, currency = values
                    payout = amount * position["stueck"] * player_uniform(daten, 0.01, 0.03)
                daten.forex_depot[currency] = daten.forex_depot.get(currency, 0.0) + payout
            elif kind in {"company_default", "crypto_delist"}:
                remove_player_assets(daten, {ticker}, corporate=kind == "company_default")


class SettlementView:
    """Use pre-roll contracts and pre-policy credit marks with current holdings."""

    def __init__(self, daten: Any, day: PlayerDay):
        self._daten = daten
        self.datum = day.date
        self.derivatives = day.settlement_contracts
        self.makro = daten.makro
        self.assets = AssetRepository(self)

    def __getattr__(self, name: str):
        return getattr(self._daten, name)
