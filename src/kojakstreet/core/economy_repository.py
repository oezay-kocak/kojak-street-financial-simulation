"""Typed access layer for the structured economic data store."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kojakstreet.core.runtime_context import SimulationDelta


class EconomyRepository:
    """Small stable facade over the DataStore current-state tables.

    New simulation features and UI views should use this repository instead of
    reaching into legacy dictionaries directly.
    """

    def __init__(self, data_store: Any) -> None:
        self.data_store = data_store

    def assets(self) -> list[dict[str, object]]:
        return self._rows("asset_quote_rows")

    def asset_by_ticker(self) -> dict[str, dict[str, object]]:
        return self.by_key(self.assets(), "ticker")

    def products(self) -> list[dict[str, object]]:
        return self._rows("product_current_rows")

    def product_by_code(self) -> dict[str, dict[str, object]]:
        return self.by_key(self.products(), "code")

    def companies(self) -> list[dict[str, object]]:
        return self._rows("company_current_rows")

    def company_flows(self) -> list[dict[str, object]]:
        return self._rows("company_output_current_rows")

    def countries(self) -> list[dict[str, object]]:
        return self._rows("country_current_rows")

    def country_by_region(self) -> dict[str, dict[str, object]]:
        return self.by_key(self.countries(), "region")

    def country_trade(self) -> list[dict[str, object]]:
        return self._rows("country_trade_current_rows")

    def funds(self) -> list[dict[str, object]]:
        return [row for row in self.assets() if row.get("asset_type") == "Fund"]

    def fund_allocations(self) -> list[dict[str, object]]:
        return self._rows("fund_allocation_current_rows")

    def forex_pairs(self) -> list[dict[str, object]]:
        return self._rows("forex_current_rows")

    def bonds(self) -> list[dict[str, object]]:
        return self._rows("bond_current_rows")

    def portfolio(self) -> list[dict[str, object]]:
        return self._rows("portfolio_current_rows")

    def portfolio_summary(self) -> dict[str, object]:
        rows = self.portfolio()
        return rows[0] if rows else {}

    def events(self) -> list[dict[str, object]]:
        return self._rows("event_current_rows")

    def news(self) -> list[dict[str, object]]:
        return self._rows("news_current_rows")

    def phase_metrics(self) -> list[dict[str, object]]:
        return self._rows("phase_metric_current_rows")

    def current_version(self) -> int:
        if hasattr(self.data_store, "current_version"):
            return int(self.data_store.current_version())
        return 0

    def current_delta(self) -> SimulationDelta:
        if hasattr(self.data_store, "current_delta"):
            return self.data_store.current_delta()
        return SimulationDelta(self.current_version(), "", frozenset())

    def health(self) -> dict[str, int | bool]:
        if hasattr(self.data_store, "architecture_health"):
            return self.data_store.architecture_health()
        return {"structured_ready": False, "duckdb_truth_ready": False}

    def by_key(self, rows: list[dict[str, object]], key: str) -> dict[str, dict[str, object]]:
        return {str(row.get(key, "")): row for row in rows if row.get(key)}

    def _rows(self, method_name: str) -> list[dict[str, object]]:
        method: Callable[[], list[dict[str, object]]] | None = getattr(self.data_store, method_name, None)
        return method() if method is not None else []
