import random
from datetime import date, timedelta

import pytest

from kojakstreet.ui_qt import chart_series
from kojakstreet.ui_qt.chart_history_cache import ChartHistoryCache, history_key
from kojakstreet.ui_qt.chart_series import IncrementalHistory, build_candles, merge_history_by_date


def test_current_state_cache_retains_all_days_beyond_local_window_and_exact_ohlc(monkeypatch):
    start = date(1990, 1, 1)
    expected = [(float(i), (start + timedelta(days=i)).isoformat(), "", i - .2, i + .5, i - .5)
                for i in range(730)]
    recent = expected[-520:]
    cache = ChartHistoryCache()
    key = history_key("Stock", "A", 0)
    cache.put(key, expected)
    def forbidden(*args, **kwargs):
        raise AssertionError("Ordered daily cache tails must not merge complete histories")
    monkeypatch.setattr(chart_series, 'merge_history_by_date', forbidden)
    for first in range(730, 1330, 5):
        points = [(float(i), (start + timedelta(days=i)).isoformat(), "", i - .2, i + .5, i - .5)
                  for i in range(first, first + 5)]
        expected.extend(points)
        recent = [*recent, *points][-520:]
        cache.update_current_books({"Stock": {"A": {"historie": recent}}})
    assert cache.get(key) == expected
    replacement = (999.0, expected[-1][1], "corrected", 998.0, 1001.0, 997.0)
    recent[-1] = expected[-1] = replacement
    cache.update_current_books({"Stock": {"A": {"historie": recent}}})
    assert cache.get(key) == expected


def test_incremental_stream_matches_existing_merge_including_corrections_and_rollover():
    rng = random.Random(8401)
    start = date(2020, 1, 1)
    original = [(10.0, "2020-01-03", "old"), (9.0, "01.01.2020", "old")]
    actual = IncrementalHistory(original)
    expected = merge_history_by_date(original)
    for index in range(800):
        day = start + timedelta(days=index if index % 11 else rng.randrange(index + 1))
        text = day.isoformat() if index % 2 else day.strftime("%d.%m.%Y")
        point = (rng.random() * 100, text, "Live", 10.0, 120.0, 2.0)
        actual.append_point(point, limit=520)
        expected = merge_history_by_date(expected, [point])[-520:]
        assert actual == expected
    assert build_candles(actual, 264) == build_candles(expected, 264)


def test_same_calendar_day_replaces_with_new_representation_and_ohlc():
    history = IncrementalHistory([(10.0, "02.01.2025", "old", 9.0, 12.0, 8.0)])
    point = {"date": "2025-01-02", "open": 10.0, "high": 15.0, "low": 7.0, "close": 14.0}
    history.append_point(point)
    assert history == [point]
    assert history[0] is point


def test_unknown_and_undated_points_keep_the_existing_fallback_semantics():
    actual = IncrementalHistory([4.0, (2.0, "z", ""), (1.0, "2025-01-02", "")])
    expected = list(actual)
    for point in [(8.0, "a", ""), (9.0, "z", "new"), 7.0, (3.0, "2025-01-01", "")]:
        actual.append_point(point)
        expected = merge_history_by_date(expected, [point])
        assert actual == expected


@pytest.mark.parametrize("mutate", [
    lambda rows: rows.reverse(),
    lambda rows: rows.append((30.0, "2024-01-01", "")),
    lambda rows: rows.__setitem__(0, (40.0, "2026-01-01", "")),
    lambda rows: rows.__iadd__([(50.0, "2024-01-01", "")]),
])
def test_external_list_mutations_invalidate_the_fast_path(mutate):
    rows = IncrementalHistory([(1.0, "2025-01-01", ""), (2.0, "2025-01-02", "")])
    mutate(rows)
    point = (5.0, "2025-01-03", "")
    expected = merge_history_by_date(rows, [point])
    rows.append_point(point)
    assert rows == expected


def test_normal_live_append_never_merges_existing_history(monkeypatch):
    start = date(2025, 1, 1)
    rows = IncrementalHistory([(float(i), (start + timedelta(days=i)).isoformat(), "") for i in range(520)])
    def unexpected(*args):
        pytest.fail("Chronological live update performed a full history merge")
    monkeypatch.setattr(chart_series, "merge_history_by_date", unexpected)
    for i in range(520, 620):
        point = (float(i), (start + timedelta(days=i)).isoformat(), "Live")
        rows.append_point(point, limit=520)
        rows.append_point(point, limit=520)
    assert len(rows) == 520
    assert rows[0][0] == 100
    assert rows[-1][0] == 619


def test_cache_preserves_deep_history_and_updates_same_date_once():
    cache = ChartHistoryCache(max_entries=2)
    key = history_key("Stock", "A", 0)
    history = [(float(i), (date(1990, 1, 1) + timedelta(days=i)).isoformat(), "") for i in range(1200)]
    cache.put(key, history)
    point = (999.0, history[-1][1], "Live")
    cache.update_live("Stock", "A", point)
    assert cache.get(key) == [*history[:-1], point]
    copy = cache.get(key)
    copy.clear()
    assert len(cache.get(key)) == 1200


def test_preview_candle_redraws_new_ohlc_without_losing_chart_settings():
    from PySide6.QtWidgets import QApplication

    from kojakstreet.ui_qt.widgets.asset_chart_panel import AssetChartPanel
    app = QApplication.instance() or QApplication([])
    panel = AssetChartPanel()
    history = [(10.0, "2025-01-01", "Daily", 9.0, 12.0, 8.0),
               (11.0, "2025-01-02", "Daily", 10.0, 13.0, 9.0)]
    data = {"name": "Example", "kurs": 11.0, "historie": history}
    panel.update_asset("EX", "Stock", data)
    panel.set_range(0)
    panel.set_chart_mode("Candle")
    count = panel.chart_draw_count
    point = (15.0, "2025-01-03", "Daily", 11.0, 17.0, 10.0)
    panel.update_live_quote({**data, "kurs": 15.0, "historie": [*history, point]})
    assert panel.chart_draw_count == count + 1
    assert panel._chart_history[-1] == point
    assert panel.chart_mode == "Candle"
    assert panel.range_points == 0
    panel.close()
    app.processEvents()
