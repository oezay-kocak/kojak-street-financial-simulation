from __future__ import annotations

from kojakstreet.core.fundamentals import (
    consume_fundamental_repricing,
    ema_diff,
    ema_values,
    ensure_stock_fundamentals,
    fundamental_price_signal,
    stage_fundamental_repricing,
    update_stock_fundamentals,
)


def test_fundamentals_initialize_stock_metrics() -> None:
    asset = {
        "branche": "Technologie",
        "kurs": 100.0,
        "market_cap": 1_000_000_000.0,
        "aktien_anzahl": 10_000_000.0,
    }

    ensure_stock_fundamentals(asset)

    assert asset["revenue"] > 0
    assert asset["free_cash_flow"] > 0
    assert asset["dividend_yield"] >= 0
    assert asset["revenue_growth"] == 0.0


def test_ema_helpers_track_latest_price_distance() -> None:
    values = [100.0, 102.0, 104.0, 106.0]

    ema = ema_values(values, 3)

    assert len(ema) == len(values)
    assert ema[-1] < values[-1]
    assert ema_diff([(value, "date", "") for value in values], 3) > 0


def test_fundamentals_keep_previous_month_comparisons() -> None:
    asset = {
        "branche": "Technologie",
        "kurs": 100.0,
        "market_cap": 1_000_000_000.0,
        "aktien_anzahl": 10_000_000.0,
    }
    ensure_stock_fundamentals(asset)
    first_revenue = asset["revenue"]
    first_fcf = asset["free_cash_flow"]

    update_stock_fundamentals(asset, macro_growth=0.02, result=0.10, sector_factor=1.0)

    assert asset["previous_revenue"] == first_revenue
    assert asset["previous_free_cash_flow"] == first_fcf
    assert asset["revenue"] != first_revenue


def test_fundamental_price_signal_is_finite_and_consumed_once() -> None:
    asset = {
        "branche": "Technologie",
        "kurs": 100.0,
        "market_cap": 100_000_000.0,
        "revenue_growth": 0.30,
        "free_cash_flow": 50_000_000.0,
        "dividend_yield": 0.08,
    }

    signal = fundamental_price_signal(asset)
    assert 0.0 < signal <= 0.12
    stage_fundamental_repricing(asset, trading_days=4)
    consumed = [consume_fundamental_repricing(asset) for _ in range(5)]
    assert sum(consumed) == signal
    assert consumed[-1] == 0.0
