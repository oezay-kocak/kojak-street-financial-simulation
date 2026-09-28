from __future__ import annotations

import os
import time
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel

import daten
from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.live_process import LiveSimulationProcess
from kojakstreet.core.ohlc import history_close
from kojakstreet.ui_qt.app import KojakStreetWindow
from kojakstreet.ui_qt.chart_history_cache import ChartHistoryCache, history_key
from kojakstreet.ui_qt.chart_series import history_date
from kojakstreet.ui_qt.views.markets_view import MarketsView
from kojakstreet.ui_qt.widgets.asset_chart_panel import AssetChartPanel
from kojakstreet.ui_qt.widgets.qt_chart import FastChartView, LegendSwatch
from kojakstreet.ui_qt.widgets.stock_detail_dialog import StockDetailView


def _dated_history(count: int, start: float = 100.0) -> list[tuple[float, str, str, float, float, float]]:
    first = date(2025, 1, 1)
    return [
        (
            start + index,
            (first + timedelta(days=index)).isoformat(),
            "Daily",
            start + index - 0.5,
            start + index + 1.0,
            start + index - 1.0,
        )
        for index in range(count)
    ]


def _asset_rows(view: MarketsView, asset_type: str = "Stock") -> list[dict]:
    return [row for row in view.model.rows if row["asset_type"] == asset_type]


def test_recent_ranges_and_a_b_a_revisit_use_local_history_without_provider() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    calls: list[tuple[str, str, int]] = []

    def provider(asset_type: str, ticker: str, limit: int) -> list:
        calls.append((asset_type, ticker, limit))
        return []

    view = MarketsView(state, history_provider=provider)
    first, second = _asset_rows(view)[:2]
    first["data"]["historie"] = _dated_history(400, 100.0)
    second["data"]["historie"] = _dated_history(400, 200.0)
    for row in (first, second, first):
        source_row = view.model.row_for_asset(row["ticker"], row["asset_type"])
        proxy_index = view.proxy_model.mapFromSource(view.model.index(source_row, 0))
        view._open_asset_detail(proxy_index)
        view.stock_detail_view.set_range(264)
        assert len(view.stock_detail_view._history_points()) == 264

    assert app is not None
    assert calls == []


def test_stale_history_response_cannot_replace_current_asset() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    view = MarketsView(state)
    first, second = _asset_rows(view)[:2]
    second_index = view.proxy_model.mapFromSource(view.model.index(view.model.row_for_ticker(second["ticker"]), 0))
    view._open_asset_detail(second_index)
    view.stock_detail_view.set_range(0)
    first_key = history_key(first["asset_type"], first["ticker"], 0)

    accepted = view.apply_history_response(first_key, _dated_history(20, 500.0))

    assert app is not None
    assert accepted is False
    assert view.stock_detail_view.ticker == second["ticker"]


def test_chart_history_cache_is_bounded() -> None:
    cache = ChartHistoryCache(max_entries=3)
    for index in range(7):
        cache.put(history_key("Stock", f"S{index}", 132), _dated_history(2, 100.0 + index))
    assert len(cache) == 3
    assert cache.get(history_key("Stock", "S0", 132)) is None


def test_live_quote_preserves_chart_state_and_does_not_reload_history() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    calls: list[tuple[str, str, int]] = []

    def provider(asset_type: str, ticker: str, limit: int) -> list:
        calls.append((asset_type, ticker, limit))
        return _dated_history(min(limit, 40))

    view = MarketsView(state, history_provider=provider)
    row = _asset_rows(view)[0]
    row["data"]["historie"] = _dated_history(40)
    source_row = view.model.row_for_ticker(row["ticker"])
    proxy_index = view.proxy_model.mapFromSource(view.model.index(source_row, 0))
    view._open_asset_detail(proxy_index)
    detail = view.stock_detail_view
    detail.set_range(22)
    detail.set_chart_mode("Candle")
    detail.set_indicator(20, True)
    calls.clear()

    view.apply_live_quotes(
        [{
            "asset_type": row["asset_type"],
            "ticker": row["ticker"],
            "price": float(row["data"]["kurs"]) + 1.0,
            "change": 0.5,
            "market_cap": float(row["data"].get("market_cap", 0.0)),
            "region": row["region"],
        }],
        date_text="2026-09-22",
    )

    assert app is not None
    assert calls == []
    assert detail.range_points == 22
    assert detail.chart_mode == "Candle"
    assert detail.enabled_indicators == {20}
    assert detail._history_points()
    assert row["data"]["historie"][-1][1] == "2026-09-22"


def test_run_stop_live_history_has_one_point_per_date_and_stale_all_preserves_tail() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    ticker = next(iter(state.stocks))
    state.stocks[ticker]["historie"] = _dated_history(20)
    stale_state = deepcopy(state)
    stale_all = list(state.stocks[ticker]["historie"][:-3])

    class RuntimeStub:
        running = False
        snapshot_calls = 0

        def set_running(self, running: bool) -> None:
            self.running = running

        def snapshot_for_view(self, _view_key: str):
            self.snapshot_calls += 1
            return deepcopy(stale_state)

        def asset_history(self, _asset_type: str, _ticker: str, _limit: int) -> list:
            return list(stale_all)

    runtime = RuntimeStub()
    window = KojakStreetWindow(state, runtime)
    view = window.markets_view
    row = next(item for item in _asset_rows(view) if item["ticker"] == ticker)
    source_row = view.model.row_for_asset(ticker, row["asset_type"])
    proxy_index = view.proxy_model.mapFromSource(view.model.index(source_row, 0))
    view._open_asset_detail(proxy_index)
    detail = view.stock_detail_view
    detail.set_range(264)
    detail.set_chart_mode("Candle")
    initial_history = list(row["data"]["historie"])

    def log_stage(source: str, current_date: str) -> None:
        history = list(row["data"]["historie"])
        dates = [history_date(point) for point in history]
        print(
            "LIVE_CHART_STAGE",
            f"asset={ticker}",
            f"range={detail.range_points}",
            f"length={len(history)}",
            f"final_dates={dates[-5:]}",
            f"current_date_count={dates.count(current_date)}",
            f"source={source}",
        )

    def apply_day(day: date, price: float) -> None:
        view.apply_live_quotes(
            [{
                "asset_type": row["asset_type"],
                "ticker": ticker,
                "price": price,
                "change": 0.1,
                "market_cap": float(row["data"].get("market_cap", 0.0)),
                "region": row["region"],
            }],
            date_text=day.isoformat(),
        )

    try:
        window.top_bar.run_button.setChecked(True)
        window.toggle_simulation()
        first_days = [date(2026, 9, 23) + timedelta(days=index) for index in range(5)]
        for index, day in enumerate(first_days):
            apply_day(day, 500.0 + index)
            if index == 0:
                apply_day(day, 501.0)
            log_stage("daily delta", day.isoformat())
        window.top_bar.run_button.setChecked(False)
        window.toggle_simulation()

        after_five = list(row["data"]["historie"])
        after_five_by_date = {history_date(point): point for point in after_five}
        assert len(after_five) == len(initial_history) + 5
        assert len({history_date(point) for point in after_five}) == len(after_five)
        assert runtime.snapshot_calls == 0
        assert detail.range_points == 264
        assert detail.chart_mode == "Candle"
        log_stage("run stop", first_days[-1].isoformat())

        view.refresh(deepcopy(stale_state))
        row = next(item for item in _asset_rows(view) if item["ticker"] == ticker)
        assert len(row["data"]["historie"]) == len(initial_history) + 5
        log_stage("snapshot merge", first_days[-1].isoformat())

        window.top_bar.run_button.setChecked(True)
        window.toggle_simulation()
        second_days = [date(2026, 9, 28) + timedelta(days=index) for index in range(3)]
        for index, day in enumerate(second_days):
            apply_day(day, 600.0 + index)
            log_stage("daily delta", day.isoformat())
        window.top_bar.run_button.setChecked(False)
        window.toggle_simulation()

        final_history = list(row["data"]["historie"])
        final_dates = [history_date(point) for point in final_history]
        assert len(final_history) == len(initial_history) + 8
        assert final_dates == sorted(final_dates)
        assert len(set(final_dates)) == len(final_dates)
        assert all(after_five_by_date[day.isoformat()] == next(
            point for point in final_history if history_date(point) == day.isoformat()
        ) for day in first_days)
        assert runtime.snapshot_calls == 0
        assert detail.range_points == 264
        assert detail.chart_mode == "Candle"
        log_stage("run stop", second_days[-1].isoformat())

        detail.set_range(0)
        all_key = history_key(row["asset_type"], ticker, 0)
        assert view.apply_history_response(all_key, stale_all) is True
        all_dates = [history_date(point) for point in detail.data["historie"]]
        assert all(day.isoformat() in all_dates for day in first_days + second_days)
        assert len(all_dates) == len(set(all_dates))
        assert detail.range_points == 0
        assert detail.chart_mode == "Candle"
        log_stage("async history merge", second_days[-1].isoformat())
    finally:
        window.close()
        app.processEvents()


def test_save_load_restores_recent_history_to_markets_snapshot(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    runtime = IntegratedRuntime(root, data_dir=tmp_path / "save-load", seed=20260922, flush_interval_days=1000)
    try:
        ticker = next(iter(runtime.daten.aktien))
        saved_history = _dated_history(400, 300.0)
        runtime.daten.aktien[ticker]["historie"] = saved_history
        runtime.save_game()
        runtime.daten.aktien[ticker]["historie"] = []
        runtime.load_game()

        state = runtime.snapshot_for_view("markets")
        # V6 preserves the full computational lookback; only the view's range
        # selection below may reduce the displayed history.
        assert state.stocks[ticker]["historie"] == saved_history
        calls: list[tuple[str, str, int]] = []
        view = MarketsView(
            state,
            history_provider=lambda asset_type, symbol, limit: calls.append(
                (asset_type, symbol, limit)
            ) or [],
        )
        row = next(item for item in _asset_rows(view) if item["ticker"] == ticker)
        assert len(view._data_with_history(row, redraw_chart=True, panel=view.chart_panel)["historie"]) == 132
        view.stock_detail_view.set_range(264)
        assert len(view._data_with_history(row, redraw_chart=True, panel=view.stock_detail_view)["historie"]) == 264
        assert calls == []
    finally:
        runtime.close()
    assert app is not None


def test_first_visible_recent_and_all_latency_uses_local_series() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    ticker = next(iter(state.stocks))
    state.stocks[ticker]["historie"] = _dated_history(400)
    calls: list[int] = []

    def provider(_asset_type: str, _ticker: str, limit: int) -> list:
        calls.append(limit)
        return []

    view = MarketsView(state, history_provider=provider)
    row = next(item for item in _asset_rows(view) if item["ticker"] == ticker)
    source_row = view.model.row_for_asset(row["ticker"], row["asset_type"])
    proxy_index = view.proxy_model.mapFromSource(view.model.index(source_row, 0))
    view._open_asset_detail(proxy_index)
    detail = view.stock_detail_view
    timings: dict[str, float] = {}
    for label, points in (("6M", 132), ("1Y", 264), ("ALL", 0)):
        started = time.perf_counter()
        detail.set_range(points)
        app.processEvents()
        timings[label] = (time.perf_counter() - started) * 1000.0
        assert detail._history_points()
    print("CHART_LATENCY_MS", " ".join(f"{label}={value:.3f}" for label, value in timings.items()))
    assert calls == [1200]
    assert max(timings.values()) < 250.0


def test_all_history_is_point_budgeted_and_tabs_keep_chart_instance() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    calls: list[int] = []

    def provider(_asset_type: str, _ticker: str, limit: int) -> list:
        calls.append(limit)
        return _dated_history(min(limit, 80))

    view = MarketsView(state, history_provider=provider)
    row = _asset_rows(view, "Fund")[0]
    source_row = view.model.row_for_ticker(row["ticker"])
    proxy_index = view.proxy_model.mapFromSource(view.model.index(source_row, 0))
    view._open_asset_detail(proxy_index)
    detail = view.stock_detail_view
    calls.clear()
    chart_identity = id(detail.chart_view)

    detail.set_range(0)
    detail.detail_tabs.setCurrentWidget(detail.overview_tab)
    detail.detail_tabs.setCurrentWidget(detail.chart_tab)

    assert app is not None
    assert calls == [1200]
    assert id(detail.chart_view) == chart_identity
    assert detail.detail_tabs.tabText(detail.detail_tabs.indexOf(detail.overview_tab)) == "Overview"
    assert detail.detail_tabs.tabText(detail.detail_tabs.indexOf(detail.supply_tab)) == "Allocations"


def test_detail_tab_switch_preserves_chart_state_and_hidden_live_update(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    ticker = next(iter(state.stocks))
    state.stocks[ticker]["historie"] = _dated_history(300)
    history_calls: list[tuple[str, str, int]] = []

    def provider(asset_type: str, symbol: str, limit: int) -> list:
        history_calls.append((asset_type, symbol, limit))
        return []

    view = MarketsView(state, history_provider=provider)
    row = next(item for item in _asset_rows(view) if item["ticker"] == ticker)
    source_row = view.model.row_for_asset(ticker, row["asset_type"])
    proxy_index = view.proxy_model.mapFromSource(view.model.index(source_row, 0))
    view._open_asset_detail(proxy_index)
    detail = view.stock_detail_view
    detail.set_range(264)
    detail.set_chart_mode("Candle")
    detail.set_indicator(20, True)

    chart_identity = id(detail.chart_view)
    initial_history = detail._history_entries()
    initial_length = len(initial_history)
    initial_final = (history_date(initial_history[-1]), history_close(initial_history[-1]))
    initial_x = list(detail.chart_view.last_x_values)
    initial_view_range = deepcopy(detail.chart_view.plot.getPlotItem().vb.viewRange())
    draw_calls = 0
    original_draw = detail._draw_chart

    def tracked_draw() -> None:
        nonlocal draw_calls
        draw_calls += 1
        original_draw()

    monkeypatch.setattr(detail, "_draw_chart", tracked_draw)
    detail.detail_tabs.setCurrentWidget(detail.chart_tab)
    detail.detail_tabs.setCurrentWidget(detail.overview_tab)
    detail.detail_tabs.setCurrentWidget(detail.chart_tab)
    detail.detail_tabs.setCurrentWidget(detail.supply_tab)
    detail.detail_tabs.setCurrentWidget(detail.chart_tab)

    unchanged_history = detail._history_entries()
    assert id(detail.chart_view) == chart_identity
    assert detail.ticker == ticker
    assert len(unchanged_history) == initial_length
    assert (history_date(unchanged_history[-1]), history_close(unchanged_history[-1])) == initial_final
    assert detail.range_points == 264
    assert detail.chart_mode == "Candle"
    assert detail.enabled_indicators == {20}
    assert detail.chart_view.last_x_values == initial_x
    assert detail.chart_view.plot.getPlotItem().vb.viewRange() == initial_view_range
    assert history_calls == []
    assert draw_calls == 0

    detail.detail_tabs.setCurrentWidget(detail.overview_tab)
    live_date = "2026-10-01"
    live_price = float(row["data"]["kurs"]) + 7.0
    view.apply_live_quotes(
        [{
            "asset_type": row["asset_type"],
            "ticker": ticker,
            "price": live_price,
            "change": 0.25,
            "market_cap": float(row["data"].get("market_cap", 0.0)),
            "region": row["region"],
        }],
        date_text=live_date,
    )
    assert draw_calls == 1
    detail.detail_tabs.setCurrentWidget(detail.chart_tab)

    live_history = detail._history_entries()
    live_dates = [history_date(point) for point in live_history]
    assert id(detail.chart_view) == chart_identity
    assert detail.ticker == ticker
    assert live_dates.count(live_date) == 1
    assert history_close(live_history[-1]) == live_price
    assert detail.range_points == 264
    assert detail.chart_mode == "Candle"
    assert detail.enabled_indicators == {20}
    assert history_calls == []
    assert draw_calls == 1
    assert app is not None


def test_line_and_candle_modes_use_real_simulation_dates() -> None:
    app = QApplication.instance() or QApplication([])
    chart = FastChartView()
    history = _dated_history(30)
    prices = [row[0] for row in history]

    chart.plot_line(prices, dates=history, title="Price History", label="Price")
    assert chart.date_axis.date_mode is True
    assert chart._hover_points[0][2] == "2025-01-01"

    chart.plot_candles(history, range_points=22)
    assert chart.date_axis.date_mode is True
    assert "O " in chart._hover_points[0][3]
    assert " C " in chart._hover_points[0][3]
    assert app is not None


def test_full_detail_line_and_candle_have_distinct_irregular_time_coordinates() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    ticker, source = next(iter(state.stocks.items()))
    asset = dict(source)
    asset["historie"] = [
        {"date": day, "open": value - 1, "high": value + 2, "low": value - 2, "close": value}
        for day, value in [
            ("2020-12-31", 90.0),
            ("2021-12-31", 96.0),
            ("2023-01-31", 101.0),
            ("2023-07-31", 98.0),
            ("2024-02-29", 108.0),
            ("2025-01-17", 112.0),
        ]
    ]
    detail = StockDetailView(state=state)
    detail.update_asset(ticker, asset, "Stock", state)
    detail.set_range(0)

    assert detail.chart_view.date_axis.date_mode is True
    assert len(set(detail.chart_view.last_x_values)) == len(asset["historie"])
    detail.set_chart_mode("Candle")
    assert detail.chart_view.date_axis.date_mode is True
    assert len(set(detail.chart_view.last_x_values)) == detail.last_candle_count
    assert detail.chart_view.last_x_values == sorted(detail.chart_view.last_x_values)
    assert app is not None


def test_duplicate_dates_fall_back_to_distinct_non_date_coordinates() -> None:
    app = QApplication.instance() or QApplication([])
    chart = FastChartView()
    chart.plot_line([10.0, 11.0, 12.0], dates=["2025-01-01"] * 3, label="Price")
    assert chart.date_axis.date_mode is False
    assert chart.last_x_values == [0.0, 1.0, 2.0]
    assert app is not None


def test_custom_legend_uses_line_only_swatches_and_long_short_hides_price_axis() -> None:
    app = QApplication.instance() or QApplication([])
    chart = FastChartView(legend=True)
    history = _dated_history(10)
    dates = [row[1] for row in history]
    prices = [row[0] for row in history]
    chart.plot_lines(
        [("Price", prices, "#14b8a6"), ("EMA 20", prices, "#22d3ee")],
        dates=dates,
        legend=True,
    )
    labels = [label.text() for label in chart.legend_bar.findChildren(QLabel)]
    assert labels == ["Price", "EMA 20"]
    assert len(chart.legend_bar.findChildren(LegendSwatch)) == 2

    chart.plot_long_short_heatmap(10.0, 8.0)
    assert chart.plot.getAxis("right").isVisible() is False
    assert chart.plot.getAxis("left").isVisible() is True
    assert app is not None


def test_preview_reserves_date_axis_and_fundamentals_cards_are_responsive() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    ticker, source = next(iter(state.stocks.items()))
    asset = dict(source)
    asset["historie"] = _dated_history(132)

    preview = AssetChartPanel(state)
    preview.resize(560, 768)
    preview.update_asset(ticker, "Stock", asset)
    preview.show()
    app.processEvents()
    assert preview.chart_view.date_axis.height() >= 32
    if preview.positioning_view.isVisible():
        assert preview.chart_view.geometry().bottom() < preview.positioning_view.geometry().top()

    detail = StockDetailView(state=state)
    detail.resize(1366, 768)
    detail.update_asset(ticker, asset, "Stock", state)
    detail.show()
    app.processEvents()
    assert detail.width() == 1366
    assert detail.minimumSizeHint().width() <= 1366
    assert detail.chart_view.geometry().right() <= detail.chart_tab.width()

    detail.detail_tabs.setCurrentWidget(detail.overview_tab)
    app.processEvents()
    assert detail._fundamental_card_columns == 3
    headings = [label.text() for label in detail.kpi_frame.findChildren(QLabel)]
    assert {"MARKET", "FUNDAMENTALS", "CREDIT & CAPITAL", "DRIVERS"}.issubset(set(headings))
    assert detail.kpi_frame.height() < detail.detail_tabs.height()

    detail.resize(1600, 900)
    detail.detail_tabs.setCurrentWidget(detail.chart_tab)
    app.processEvents()
    assert detail.chart_view.geometry().right() <= detail.chart_tab.width()
    detail.detail_tabs.setCurrentWidget(detail.overview_tab)
    app.processEvents()
    assert detail._fundamental_card_columns == 4
    assert detail.minimumSizeHint().width() <= 1600
    assert app is not None


def test_process_isolated_tick_keeps_chart_controls_and_qt_events_flowing(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    bootstrap = IntegratedRuntime(root, data_dir=tmp_path / "worker", seed=20260922, flush_interval_days=1000)
    initial_state = bootstrap.snapshot_for_view("markets")
    process = LiveSimulationProcess.from_runtime(bootstrap, timeout_seconds=20.0)
    window = KojakStreetWindow(initial_state, process)
    events: list[float] = []
    heartbeat = QTimer()
    heartbeat.setInterval(5)
    heartbeat.timeout.connect(lambda: events.append(time.perf_counter()))
    try:
        row = _asset_rows(window.markets_view)[0]
        source_row = window.markets_view.model.row_for_ticker(row["ticker"])
        proxy_index = window.markets_view.proxy_model.mapFromSource(
            window.markets_view.model.index(source_row, 0)
        )
        window.markets_view._open_asset_detail(proxy_index)
        detail = window.markets_view.stock_detail_view
        detail.set_range(22)
        detail.set_chart_mode("Candle")
        chart_identity = id(detail.chart_view)

        heartbeat.start()
        started = time.perf_counter()
        window._request_simulation_steps(1, force_refresh=False)
        while window.simulation_busy and time.perf_counter() - started < 10.0:
            app.processEvents()
            time.sleep(0.002)
        app.processEvents()

        assert process.worker_pid != os.getpid()
        assert not window.simulation_busy
        assert len(events) >= 2
        assert detail.range_points == 22
        assert detail.chart_mode == "Candle"
        assert id(detail.chart_view) == chart_identity
    finally:
        heartbeat.stop()
        window.close()
        app.processEvents()
        process.close()
