"""Shared chart-series helpers for broker-style price charts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kojakstreet.core.ohlc import history_close, history_ohlc


@dataclass(frozen=True)
class Candle:
    open: float
    high: float
    low: float
    close: float


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
        candles.append(Candle(open=open_price, high=high, low=low, close=close_price))
        previous_close = close_price

    return candles, interval
