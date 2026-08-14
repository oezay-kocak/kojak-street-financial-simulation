"""Runtime contracts that separate legacy state, engines and UI-facing data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SimulationDelta:
    """Small description of the current-state tables changed by a simulation step."""

    version: int
    date_text: str
    tables: frozenset[str] = field(default_factory=frozenset)

    def changed(self, table: str) -> bool:
        return table in self.tables


@dataclass(slots=True)
class RuntimeServices:
    """Explicit service registry for modern engines around legacy state."""

    market: Any
    trading: Any
    macro: Any | None = None
    bond_portfolio: Any | None = None
    production: Any | None = None


@dataclass(slots=True)
class RuntimeContext:
    """Explicit runtime boundary around the legacy module and modern services."""

    legacy_data: Any
    simulation: Any
    data_store: Any
    repository: Any
    services: RuntimeServices | None = None
    state: Any | None = None

    @property
    def current_version(self) -> int:
        return int(self.data_store.current_version()) if hasattr(self.data_store, "current_version") else 0

    def current_delta(self) -> SimulationDelta:
        if hasattr(self.data_store, "current_delta"):
            return self.data_store.current_delta()
        return SimulationDelta(self.current_version, "", frozenset())
