"""Small UI-side LRU cache for already-renderable chart histories."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from kojakstreet.ui_qt.chart_series import merge_history_by_date


@dataclass(frozen=True)
class ChartHistoryKey:
    asset_type: str
    ticker: str
    range_points: int
    resolution: str


class ChartHistoryCache:
    """Bounded histories keyed by entity and requested chart resolution."""

    def __init__(self, max_entries: int = 32) -> None:
        self.max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[ChartHistoryKey, list[Any]] = OrderedDict()

    def get(self, key: ChartHistoryKey) -> list[Any] | None:
        rows = self._entries.get(key)
        if rows is None:
            return None
        self._entries.move_to_end(key)
        return list(rows)

    def put(self, key: ChartHistoryKey, rows: list[Any]) -> None:
        if not rows:
            return
        self._entries[key] = list(rows)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def update_live(self, asset_type: str, ticker: str, point: Any) -> None:
        for key in list(self._entries):
            if key.asset_type != asset_type or key.ticker != ticker:
                continue
            rows = merge_history_by_date(self._entries[key], [point])
            self._entries[key] = rows
            if key.range_points > 0 and len(rows) > key.range_points:
                del rows[:-key.range_points]
            self._entries.move_to_end(key)

    def __len__(self) -> int:
        return len(self._entries)


def history_key(asset_type: str, ticker: str, range_points: int) -> ChartHistoryKey:
    return ChartHistoryKey(
        str(asset_type),
        str(ticker),
        int(range_points),
        "adaptive" if int(range_points) <= 0 else "daily",
    )


def point_budget(range_points: int) -> int:
    return 1200 if int(range_points) <= 0 else max(2, int(range_points))
