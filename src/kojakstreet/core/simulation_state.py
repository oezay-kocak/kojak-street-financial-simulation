"""Typed in-memory state boundary around the legacy save module."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import timedelta
from types import ModuleType
from typing import Any

from kojakstreet.core.countries import RESERVE_CURRENCY


class AssetRepository:
    """Typed access to all tradeable asset universes."""

    def __init__(self, state: "SimulationState") -> None:
        self.state = state

    @property
    def stocks(self) -> dict[str, dict]:
        return self.state.aktien

    @property
    def commodities(self) -> dict[str, dict]:
        return self.state.rohstoffe

    @property
    def cryptos(self) -> dict[str, dict]:
        return self.state.kryptos

    @property
    def funds(self) -> dict[str, dict]:
        return self.state.fonds

    @property
    def indices(self) -> dict[str, dict]:
        return self.state.indizes

    @property
    def derivatives(self) -> dict[str, dict]:
        return self.state.derivatives

    def universes(self) -> tuple[dict[str, dict], ...]:
        return (self.stocks, self.commodities, self.cryptos, self.funds, self.derivatives)

    def get(self, ticker: str) -> dict | None:
        for universe in (*self.universes(), self.indices):
            if ticker in universe:
                return universe[ticker]
        return None

    def price(self, ticker: str) -> float | None:
        asset = self.get(ticker)
        if asset is None:
            return None
        try:
            return float(asset["kurs"])
        except (KeyError, TypeError, ValueError):
            return None

    def region(self, ticker: str) -> str | None:
        if ticker in self.stocks:
            return str(self.stocks[ticker].get("land", RESERVE_CURRENCY))
        if ticker in self.commodities or ticker in self.cryptos:
            return RESERVE_CURRENCY
        if ticker in self.funds:
            return str(self.funds[ticker].get("ziel", RESERVE_CURRENCY))
        if ticker in self.derivatives:
            return str(self.derivatives[ticker].get("land", RESERVE_CURRENCY))
        return None


class PortfolioRepository:
    """Typed access to portfolio, cash, credit and derivative state."""

    def __init__(self, state: "SimulationState") -> None:
        self.state = state

    @property
    def positions(self) -> dict[str, dict]:
        return self.state.depot

    @property
    def perpetuals(self) -> dict[str, dict]:
        return self.state.perpetuals

    @property
    def fx_balances(self) -> dict[str, float]:
        return self.state.forex_depot

    @property
    def loans(self) -> dict[str, float]:
        return self.state.kredite

    @property
    def bonds(self) -> list[dict]:
        return self.state.anleihen


class MacroRepository:
    """Typed access to countries, macro rows and currency strengths."""

    def __init__(self, state: "SimulationState") -> None:
        self.state = state

    @property
    def countries(self) -> Mapping[str, str]:
        return self.state.LAENDER

    @property
    def rows(self) -> dict[str, dict]:
        return self.state.makro

    @property
    def currency_strength(self) -> dict[str, float]:
        return self.state.waehrungen_staerke

    def country_names(self) -> Iterable[str]:
        return self.countries.keys()


class SimulationState:
    """Modern state facade; legacy data remains the backing store during migration."""

    _BOUND_NAMES = {
        "aktien",
        "rohstoffe",
        "kryptos",
        "fonds",
        "indizes",
        "derivatives",
        "processed_products",
        "makro",
        "LAENDER",
        "WAEHRUNGEN",
        "waehrungen_staerke",
        "FOREX_PAARE_HISTORIE",
        "MAKRO_HISTORIE",
        "GLOBAL_MACRO_HISTORIE",
        "DEPOT_VERMOEGEN_HISTORIE",
        "NEWS_SPEICHER",
        "global_macro",
        "depot",
        "perpetuals",
        "forex_depot",
        "kredite",
        "anleihen",
        "bond_market",
        "realisierte_guv_historie",
    }

    __slots__ = ("legacy_data", "assets", "portfolio", "macro", *_BOUND_NAMES)

    def __init__(self, legacy_data: ModuleType) -> None:
        object.__setattr__(self, "legacy_data", legacy_data)
        self.sync_from_legacy()
        object.__setattr__(self, "assets", AssetRepository(self))
        object.__setattr__(self, "portfolio", PortfolioRepository(self))
        object.__setattr__(self, "macro", MacroRepository(self))

    @classmethod
    def from_legacy(cls, legacy_data: ModuleType) -> "SimulationState":
        return cls(legacy_data)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.legacy_data, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"legacy_data", "assets", "portfolio", "macro"}:
            object.__setattr__(self, name, value)
            return
        if name in self._BOUND_NAMES:
            object.__setattr__(self, name, value)
            setattr(self.legacy_data, name, value)
            return
        if name in {"date", "datum"}:
            self.legacy_data.datum = value
            return
        if name == "is_active":
            self.legacy_data.SPIEL_AKTIV = bool(value)
            return
        if name == "is_paused":
            self.legacy_data.spiel_pausiert = bool(value)
            return
        setattr(self.legacy_data, name, value)

    @property
    def date(self) -> Any:
        return self.datum

    @date.setter
    def date(self, value: Any) -> None:
        self.legacy_data.datum = value

    @property
    def is_active(self) -> bool:
        return bool(getattr(self.legacy_data, "SPIEL_AKTIV", True))

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.legacy_data.SPIEL_AKTIV = bool(value)

    @property
    def is_paused(self) -> bool:
        return bool(getattr(self.legacy_data, "spiel_pausiert", False))

    @is_paused.setter
    def is_paused(self, value: bool) -> None:
        self.legacy_data.spiel_pausiert = bool(value)

    def mark_completed_today(self) -> None:
        self.legacy_data.last_completed_simulation_date = self.legacy_data.datum

    def advance_one_day(self) -> None:
        self.legacy_data.datum += timedelta(days=1)

    @property
    def datum(self) -> Any:
        return self.legacy_data.datum

    @datum.setter
    def datum(self, value: Any) -> None:
        self.legacy_data.datum = value

    def sync_from_legacy(self) -> None:
        for name in self._BOUND_NAMES:
            if hasattr(self.legacy_data, name):
                object.__setattr__(self, name, getattr(self.legacy_data, name))
            elif name == "derivatives":
                self.derivatives = {}
