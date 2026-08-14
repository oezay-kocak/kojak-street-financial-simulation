from __future__ import annotations

from kojakstreet.ui_qt.chart_series import build_candles
from kojakstreet.ui_qt.widgets.qt_chart import _compact_value_ticks


def test_candle_series_uses_daily_buckets_for_short_range() -> None:
    candles, interval = build_candles([100.0 + index for index in range(22)], 22)

    assert interval == "Daily"
    assert len(candles) == 21
    assert candles[0].high > max(candles[0].open, candles[0].close)
    assert candles[0].low < min(candles[0].open, candles[0].close)


def test_candle_series_uses_weekly_buckets_for_six_month_range() -> None:
    candles, interval = build_candles([100.0 + index for index in range(132)], 132)

    assert interval == "Weekly"
    assert len(candles) >= 40


def test_candle_series_uses_monthly_buckets_for_one_year_range() -> None:
    candles, interval = build_candles([100.0 + index for index in range(264)], 264)

    assert interval == "Monthly"
    assert len(candles) >= 26


def test_candle_series_uses_yearly_buckets_for_long_all_range() -> None:
    candles, interval = build_candles([100.0 + index for index in range(1000)], 0)

    assert interval == "Yearly"
    assert len(candles) >= 7


def test_candle_series_uses_recorded_ohlc_values_when_available() -> None:
    history = [
        (100.0, "01.01.1990", "", 98.0, 104.0, 96.0),
        (103.0, "02.01.1990", "", 100.0, 106.0, 99.0),
    ]

    candles, interval = build_candles(history, 22)

    assert interval == "Daily"
    assert candles[0].open == 100.0
    assert candles[0].high == 106.0
    assert candles[0].low == 99.0
    assert candles[0].close == 103.0


def test_positioning_axis_uses_compact_value_labels() -> None:
    ticks = _compact_value_ticks(20_000_000.0)

    assert ticks == [
        (5_000_000, "5M"),
        (10_000_000, "10M"),
        (15_000_000, "15M"),
        (20_000_000, "20M"),
    ]
