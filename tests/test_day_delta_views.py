import threading
from copy import deepcopy
from datetime import datetime

from PySide6.QtWidgets import QApplication

from kojakstreet.core.state import GameState
from kojakstreet.live_process import LiveSimulationProcess
from kojakstreet.ui_qt.chart_history_cache import history_key
from kojakstreet.ui_qt.views.markets_view import MarketsView


def test_current_delta_updates_market_topology_without_mutating_authoritative_history():
    app = QApplication.instance() or QApplication([])
    state = GameState(date=datetime(1990, 1, 1), cash=100.0, display_currency="GD")  # noqa: DTZ001 - game calendar
    state.stocks["A"] = {"kurs": 2.0, "historie": [(1.0, "01.01.1990", ""), (2.0, "01.01.1990", "")]}
    source_history = deepcopy(state.stocks["A"]["historie"])
    view = MarketsView(state)
    try:
        assert state.stocks["A"]["historie"] == source_history
        state.stocks["B"] = {"kurs": 3.0, "historie": [(3.0, "01.01.1990", "")]}
        view.apply_live_quotes([], date_text="1990-01-01", current_state=state)
        assert {row["ticker"] for row in view.model.rows} == {"A", "B"}
        del state.stocks["A"]
        view.apply_live_quotes([], date_text="1990-01-01", current_state=state)
        assert [row["ticker"] for row in view.model.rows] == ["B"]
        assert app is not None
    finally:
        view.close()


def test_overlapping_tickers_do_not_trigger_daily_history_rebuild(monkeypatch):
    app = QApplication.instance() or QApplication([])
    state = GameState(date=datetime(1990, 1, 1), cash=100.0, display_currency="GD")  # noqa: DTZ001 - game calendar
    state.stocks["A"] = {"kurs": 2.0, "historie": [(2.0, "01.01.1990", "")]}
    state.indices["A"] = {"kurs": 3.0, "historie": [(3.0, "01.01.1990", "")]}
    view = MarketsView(state)
    try:
        def forbidden(*args, **kwargs):
            raise AssertionError("Unchanged market topology must not rebuild histories")
        monkeypatch.setattr(view, 'refresh', forbidden)
        view.apply_live_quotes([], date_text="1990-01-01", current_state=state)
        assert app is not None
    finally:
        view.close()


def test_loading_earlier_date_discards_future_chart_cache_and_local_points():
    app = QApplication.instance() or QApplication([])
    state = GameState(date=datetime(1990, 1, 20), cash=100.0, display_currency="GD")  # noqa: DTZ001 - game calendar
    state.stocks["A"] = {"kurs": 20.0, "historie": [(20.0, "1990-01-20", "")]}
    view = MarketsView(state)
    key = history_key("Stock", "A", 0)
    view.history_cache.put(key, state.stocks["A"]["historie"])
    restored = GameState(date=datetime(1990, 1, 1), cash=100.0, display_currency="GD")  # noqa: DTZ001 - game calendar
    restored.stocks["A"] = {"kurs": 1.0, "historie": [(1.0, "1990-01-01", "")]}
    try:
        view.refresh(restored)
        assert view.history_cache.get(key) is None
        assert restored.stocks["A"]["historie"] == [(1.0, "1990-01-01", "")]
        assert app is not None
    finally:
        view.close()


def test_deep_cache_replaces_same_day_numeric_and_ohlc_endpoints_without_refetch():
    process = LiveSimulationProcess.__new__(LiveSimulationProcess)
    process._history_lock = threading.Lock()
    fx = ("forex", "A/GD", 1200)
    asset = ("asset", "Stock", "A", 1200)
    process._history_cache = {fx: [1.0], asset: [(1.0, "1990-01-01", "old", .9, 1.1, .8)]}
    process._history_cache_dates = {fx: "1990-01-01", asset: "1990-01-01"}
    assert process._history_result(fx, [2., 3.], dated_rows=[(2., "1990-01-01"), (3., "1990-01-02")]) == [2., 3.]
    points = [(2., "1990-01-01", "final", 1.5, 2.5, 1.), (3., "1990-01-02", "new", 2., 4., 1.)]
    assert process._history_result(asset, points) == points
    assert process._history_cache[fx] == [1.0]
