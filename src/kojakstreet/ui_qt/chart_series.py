"""Shared chart-series helpers for broker-style price charts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from kojakstreet.core.ohlc import history_close, history_ohlc


@dataclass(frozen=True)
class Candle:
    open: float
    high: float
    low: float
    close: float
    date: str = ""


def history_date(point: Any) -> str:
    """Return the simulation/bucket date carried by a history point."""
    if isinstance(point, (date, datetime)):
        return point.date().isoformat() if isinstance(point, datetime) else point.isoformat()
    if isinstance(point, str):
        return point
    if isinstance(point, dict):
        return str(point.get("date", point.get("bucket_end", "")))
    if isinstance(point, (tuple, list)) and len(point) > 1:
        value = point[1]
        if isinstance(value, (date, datetime)):
            return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
        if isinstance(value, str):
            return value
    return ""


def history_ordinal(point: Any) -> float | None:
    value = history_date(point).strip()
    return _date_ordinal(value)


@lru_cache(maxsize=4096)
def _date_ordinal(value: str) -> float | None:
    """Dates repeat across instruments; cache text, never mutable history points."""
    if not value:
        return None
    try:
        return float(date.fromisoformat(value[:10]).toordinal())
    except ValueError:
        pass
    try:
        day, month, year = (int(part) for part in value[:10].split("."))
        return float(date(year, month, day).toordinal())
    except (TypeError, ValueError):
        pass
    for pattern in ("%d %b %Y", "%d %B %Y", "%b %Y", "%B %Y", "%Y-%m", "%Y"):
        try:
            return float(datetime.strptime(value, pattern).date().toordinal())  # noqa: DTZ007
        except ValueError:
            continue
    return None


def merge_history_by_date(*series: list[Any]) -> list[Any]:
    """Merge histories chronologically; later series own overlapping dates."""

    undated: list[Any] = []
    dated: dict[tuple[str, object], tuple[Any, float | None, str]] = {}
    for history in series:
        for point in history:
            date_text = history_date(point).strip()
            ordinal = history_ordinal(point)
            if ordinal is None and not date_text:
                undated.append(point)
                continue
            identity = (
                ("ordinal", int(ordinal))
                if ordinal is not None
                else ("text", date_text)
            )
            dated[identity] = (point, ordinal, date_text)
    ordered = sorted(
        dated.values(),
        key=lambda item: (
            item[1] is None,
            item[1] if item[1] is not None else 0.0,
            item[2],
        ),
    )
    return undated + [point for point, _ordinal, _date_text in ordered]


def _invalidates_order(method):
    def mutate(self, *args, **kwargs):
        self._ordered = False
        return method(self, *args, **kwargs)
    return mutate


class IncrementalHistory(list):
    """UI-owned normalized history with O(1) chronological append/replace.

    Points retain their original representation and are treated as immutable.
    External list mutations invalidate the ordering proof. A newly loaded,
    replaced or unordered list is normalized once before using the fast path.
    """

    __slots__ = ("_ordered", "_tail_ordinal")

    def __init__(self, points=()):
        super().__init__(merge_history_by_date(points))
        self._remember_order()

    def _remember_order(self):
        self._tail_ordinal = history_ordinal(self[-1]) if self else None
        self._ordered = True

    def append_point(self, point: Any, *, limit: int = 0) -> None:
        if not self._ordered:
            list.__setitem__(self, slice(None), merge_history_by_date(self))
            self._remember_order()
        ordinal = history_ordinal(point)
        if ordinal is not None and (not self or self._tail_ordinal is not None):
            if not self or ordinal > self._tail_ordinal:
                list.append(self, point)
                self._tail_ordinal = ordinal
            elif ordinal == self._tail_ordinal:
                list.__setitem__(self, -1, point)
            else:
                self._merge_point(point)
        else:
            self._merge_point(point)
        if limit > 0 and len(self) > limit:
            list.__delitem__(self, slice(None, -limit))

    def _merge_point(self, point):
        list.__setitem__(self, slice(None), merge_history_by_date(self, [point]))
        self._remember_order()

    append = _invalidates_order(list.append)
    extend = _invalidates_order(list.extend)
    insert = _invalidates_order(list.insert)
    pop = _invalidates_order(list.pop)
    remove = _invalidates_order(list.remove)
    clear = _invalidates_order(list.clear)
    reverse = _invalidates_order(list.reverse)
    sort = _invalidates_order(list.sort)
    __setitem__ = _invalidates_order(list.__setitem__)
    __delitem__ = _invalidates_order(list.__delitem__)
    __iadd__ = _invalidates_order(list.__iadd__)
    __imul__ = _invalidates_order(list.__imul__)


def incremental_history(points: list[Any]) -> IncrementalHistory:
    return points if isinstance(points, IncrementalHistory) else IncrementalHistory(points)


def candle_bucket(range_points: int, point_count: int) -> tuple[int, str]:
    """Return a sensible candle aggregation for the selected visible range."""
    if point_count <= 45 or range_points == 22:
        return 1, "Daily"
    if point_count <= 180 or range_points == 132:
        return 3, "Weekly"
    if range_points == 0 and point_count > 756:
        return 126, "Yearly"
    return 10, "Monthly"


def build_candles(points: list[Any], range_points: int) -> tuple[list[Candle], str]:
    """Aggregate price history into OHLC candles for the selected range."""
    if len(points) < 2:
        return [], "Daily"

    bucket_size, interval = candle_bucket(range_points, len(points))
    candles: list[Candle] = []
    previous_close = history_close(points[0])
    start_index = 1 if bucket_size == 1 else 0

    for index in range(start_index, len(points), bucket_size):
        bucket_points = points[index : index + bucket_size]
        if not bucket_points:
            continue
        has_ohlc = any(isinstance(point, dict) or (isinstance(point, (tuple, list)) and len(point) >= 6) for point in bucket_points)
        if has_ohlc:
            ohlc_points = [history_ohlc(point) for point in bucket_points]
            open_price = ohlc_points[0][0]
            close_price = ohlc_points[-1][3]
            high = max(point[1] for point in ohlc_points)
            low = min(point[2] for point in ohlc_points)
        else:
            close_values = [history_close(point) for point in bucket_points]
            open_price = previous_close
            close_price = close_values[-1]
            raw_high = max(open_price, *close_values)
            raw_low = min(open_price, *close_values)
            body = abs(close_price - open_price)
            range_hint = max(raw_high - raw_low, body, close_price * 0.002)
            wick = range_hint * 0.35
            high = raw_high + wick
            low = max(0.0, raw_low - wick)
        candles.append(Candle(open=open_price, high=high, low=low, close=close_price, date=history_date(bucket_points[-1])))
        previous_close = close_price

    return candles, interval
