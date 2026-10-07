"""Small UI-side LRU cache for already-renderable chart histories."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from kojakstreet.ui_qt.chart_series import IncrementalHistory, history_ordinal


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
        self._entries: OrderedDict[ChartHistoryKey, IncrementalHistory] = OrderedDict()

    def get(self, key: ChartHistoryKey) -> list[Any] | None:
        rows = self._entries.get(key)
        if rows is None:
            return None
        self._entries.move_to_end(key)
        return list(rows)

    def put(self, key: ChartHistoryKey, rows: list[Any]) -> None:
        if not rows:
            return
        self._entries[key] = IncrementalHistory(rows)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def update_live(self, asset_type: str, ticker: str, point: Any) -> None:
        for key in list(self._entries):
            if key.asset_type != asset_type or key.ticker != ticker:
                continue
            self._entries[key].append_point(point, limit=key.range_points)
            self._entries.move_to_end(key)

    def update_current_books(self, books: dict[str, dict]) -> None:
        """Keep cached ALL tails beyond the local 520-point window.

        Only the at most 32 cached series are inspected. Walk backwards to the
        cache boundary, then append the authoritative points with their OHLC.
        This also retains intermediate days from a multi-day worker response.
        """
        for key, rows in self._entries.items():
            recent = books.get(key.asset_type, {}).get(key.ticker, {}).get("historie", [])
            cutoff = history_ordinal(rows[-1]) if rows else None
            tail = []
            for point in reversed(recent):
                ordinal = history_ordinal(point)
                if ordinal is None or cutoff is None:
                    merged = IncrementalHistory([*rows, *recent])
                    self._entries[key] = IncrementalHistory(merged[-key.range_points:]) if key.range_points > 0 else merged
                    tail.clear()
                    break
                if ordinal < cutoff:
                    break
                tail.append(point)
            if tail:
                for point in reversed(tail):
                    rows.append_point(point, limit=key.range_points)

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
