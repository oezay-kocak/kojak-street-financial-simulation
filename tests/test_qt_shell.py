from __future__ import annotations

import os
import time
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableView,
)

import daten
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.runtime_context import SimulationDelta
from kojakstreet.ui_qt.app import KojakStreetWindow
from kojakstreet.ui_qt.views.supply_chain_view import _history_points, _smooth_supply_points


class FakeRuntime:
    def __init__(self, state):
        self.state = state
        self.running = False

    def set_running(self, running: bool) -> None:
        self.running = running

    def step_day(self):
        self.state = replace(self.state, date=self.state.date + timedelta(days=1))
        return self.state

    def advance_days(self, steps: int, view_key: str = "full"):
        for _ in range(steps):
            self.step_day()
        return self.state

    def asset_quote_rows(self):
        rows = []
        for asset_type, assets in [
            ("Stock", self.state.stocks),
            ("Commodity", self.state.commodities),
            ("Crypto", self.state.cryptos),
            ("Fund", self.state.funds),
            ("Index", self.state.indices),
        ]:
            for ticker, asset in assets.items():
                rows.append(
                    {
                        "ticker": ticker,
                        "asset_type": asset_type,
                        "price": float(asset.get("kurs", 0.0)),
                        "change": float(asset.get("aenderung", 0.0)),
                        "market_cap": float(asset.get("market_cap", 0.0)),
                        "region": str(asset.get("land", asset.get("ziel", "GD"))),
                    }
                )
        return rows

    def ticker_tape_quotes(self):
        return [
            {"ticker": str(row["ticker"]), "price": float(row["price"]), "change": float(row["change"])}
            for row in self.asset_quote_rows()[:4]
        ]


def test_qt_shell_can_render_legacy_market_snapshot() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)
    table = window.findChild(QTableView, "MarketTable")

    assert app is not None
    assert window.windowTitle() == "Kojak Street Pro"
    assert table is not None
    assert window.markets_view.proxy_model.rowCount() == 160


def test_qt_shell_top_bar_uses_cash_and_ticker_tape_only() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)
    labels = [label.text() for label in window.top_bar.findChildren(QLabel)]

    assert app is not None
    assert state.date.strftime("%d.%m.%Y") in labels
    assert set(window.top_bar.kpi_values) == {"Cash"}
    assert window.top_bar.kpi_values["Cash"].text().endswith(" GD")
    assert window.top_bar.ticker_tape.items
    assert window.top_bar.ticker_tape.minimumSizeHint().width() <= 300


def test_qt_shell_top_bar_applies_current_ticker_data_immediately() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)
    next_items = [{"ticker": "NEXT", "price": 101.0, "change": 2.5}]

    assert app is not None

    window.top_bar.ticker_tape.set_items(next_items)

    assert window.top_bar.ticker_tape.items == next_items
    assert window.top_bar.ticker_tape.pending_items is None

    window.top_bar.ticker_tape.offset = window.top_bar.ticker_tape._tile_width() - 1
    window.top_bar.ticker_tape.scroll()

    assert window.top_bar.ticker_tape.items == next_items
    assert window.top_bar.ticker_tape.pending_items is None


def test_qt_shell_switches_views_from_side_nav() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)
    stack = window.findChild(QStackedWidget)

    assert app is not None
    assert stack is not None
    assert stack.count() == 9

    window.side_nav.set_active_view("forex")

    assert stack.currentWidget() is window.views["forex"]

    window.side_nav.set_active_view("bondmarket")

    assert stack.currentWidget() is window.views["bondmarket"]

    window.side_nav.set_active_view("global_macro")

    assert stack.currentWidget() is window.views["global_macro"]

    window.side_nav.set_active_view("supply_chain")

    assert stack.currentWidget() is window.views["supply_chain"]

    window.side_nav.set_active_view("trade_map")

    assert stack.currentWidget() is window.views["trade_map"]


def test_qt_supply_chain_view_lists_products_and_filters() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)
    window.side_nav.set_active_view("supply_chain")
    table = window.findChild(QTableView, "SupplyChainTable")
    asset_filter = window.findChild(QComboBox, "SupplyChainTypeFilter")

    assert app is not None
    assert table is not None
    assert asset_filter is not None
    assert table.model().rowCount() == len(state.commodities)

    asset_filter.setCurrentText("Commodity")

    assert table.model().rowCount() == len(state.commodities)


def test_qt_supply_chain_imbalance_filter_includes_surplus_rows() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)
    window.side_nav.set_active_view("supply_chain")
    table = window.findChild(QTableView, "SupplyChainTable")
    asset_filter = window.findChild(QComboBox, "SupplyChainTypeFilter")

    asset_filter.setCurrentText("Imbalance")
    balances = [
        float(table.model().metadata_at(index)["imbalance"])
        for index in range(table.model().rowCount())
    ]

    assert app is not None
    assert table is not None
    assert any(balance < -0.03 for balance in balances)
    assert all(abs(balance) > 0.03 for balance in balances)


def test_qt_supply_chain_detail_opens_and_preserves_selection_on_refresh() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)
    window.side_nav.set_active_view("supply_chain")
    view = window.views["supply_chain"]
    table = window.findChild(QTableView, "SupplyChainTable")

    assert app is not None
    assert table is not None

    selected_index = table.model().index(2, 0)
    selected_code = selected_index.data()
    view._open_row_detail(selected_index)  # type: ignore[attr-defined]

    assert view.pages.currentWidget() is view.detail_page  # type: ignore[attr-defined]
    assert view.selected_code == selected_code  # type: ignore[attr-defined]
    assert view.country_share_chart is not None  # type: ignore[attr-defined]
    country_shares = view._country_production_shares(selected_code)  # type: ignore[attr-defined]
    assert len(country_shares) == len(state.macro)
    assert abs(sum(share for _country, share in country_shares) - 100.0) < 0.01
    assert len({round(share, 1) for _country, share in country_shares}) >= 8

    view.refresh(state)  # type: ignore[attr-defined]

    assert view.pages.currentWidget() is view.detail_page  # type: ignore[attr-defined]
    assert view.selected_code == selected_code  # type: ignore[attr-defined]


def test_qt_supply_chain_hides_country_share_for_crypto_services() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)
    window.side_nav.set_active_view("supply_chain")
    view = window.views["supply_chain"]
    table = window.findChild(QTableView, "SupplyChainTable")

    assert app is not None
    assert table is not None

    crypto_row = next(
        row
        for row in view.rows  # type: ignore[attr-defined]
        if row["code"] == "CRSTORE"
    )
    view._draw_row_charts(crypto_row)  # type: ignore[attr-defined]

    assert view.country_share_chart.isHidden() is True  # type: ignore[attr-defined]


def test_supply_chain_history_smoothing_removes_isolated_display_spikes() -> None:
    smoothed = _smooth_supply_points([100.0, 101.0, 70.0, 101.5, 102.0, 112.0])

    assert min(smoothed[1:4]) > 95.0
    assert smoothed[-1] > smoothed[-2]
    assert smoothed[-1] < 112.0


def test_supply_chain_history_extraction_does_not_synthesize_start_points() -> None:
    assert _history_points({}, "supply_history") == []
    assert _history_points({"supply_history": [(123.0, "01.01.1990", "")]}, "supply_history") == [123.0]


def test_qt_stock_detail_shows_company_supply_chain_rows() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    ticker, stock = next((ticker, stock) for ticker, stock in state.stocks.items() if stock.get("output_mix"))

    window = KojakStreetWindow(state)
    window.markets_view.stock_detail_view.update_asset(ticker, stock, "Stock", state)
    window.markets_view.stock_detail_view.detail_tabs.setCurrentWidget(window.markets_view.stock_detail_view.supply_tab)
    table = window.markets_view.stock_detail_view.supply_table

    assert app is not None
    assert table is not None
    assert table.model().rowCount() >= len(stock["output_mix"])
    assert table.model().index(0, 0).data() == "Produces"


def test_qt_stock_detail_resolves_processed_product_market_rows_from_markets_profile() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten, profile="markets")
    ticker, stock = next(
        (ticker, stock)
        for ticker, stock in state.stocks.items()
        if any(code in state.processed_products for code in stock.get("output_mix", {}))
    )

    window = KojakStreetWindow(state)
    detail = window.markets_view.stock_detail_view
    detail.update_asset(ticker, stock, "Stock", state)
    detail.detail_tabs.setCurrentWidget(detail.supply_tab)
    rows = [detail.supply_table.model().metadata_at(index) for index in range(detail.supply_table.model().rowCount())]
    produced = next(row for row in rows if row["role"] == "Produces" and row["code"] in state.processed_products)

    assert app is not None
    assert produced["supply"] > 0.0
    assert produced["demand"] > 0.0
    assert produced["inventories"] > 0.0


def test_qt_stock_supply_chain_chart_has_no_ema_and_preserves_selected_row() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    ticker, stock = next((ticker, stock) for ticker, stock in state.stocks.items() if stock.get("output_mix"))

    window = KojakStreetWindow(state)
    detail = window.markets_view.stock_detail_view
    detail.update_asset(ticker, stock, "Stock", state)
    detail.detail_tabs.setCurrentWidget(detail.supply_tab)
    table = detail.supply_table

    assert app is not None
    assert table.model().rowCount() > 0

    target_row = min(1, table.model().rowCount() - 1)
    table.selectRow(target_row)
    detail._draw_selected_supply_metric()
    selected_code = table.model().index(target_row, 1).data()

    assert detail.selected_metric_label.endswith("Company Qty")
    assert detail.legend_labels == []

    detail.update_asset(ticker, stock, "Stock", state)

    assert table.model().index(table.currentIndex().row(), 1).data() == selected_code
    assert detail.selected_metric_label.endswith("Company Qty")
    assert detail.legend_labels == []


def test_qt_market_filters_hide_non_matching_rows() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)
    table = window.findChild(QTableView, "MarketTable")
    search = window.findChild(QLineEdit, "MarketSearchInput")
    asset_filter = window.findChild(QComboBox, "MarketTypeFilter")

    assert app is not None
    assert table is not None
    assert search is not None
    assert asset_filter is not None
    ticker = next(iter(state.stocks))

    search.setText(ticker)

    assert window.markets_view.proxy_model.rowCount() == 1
    source = window.markets_view.proxy_model.mapToSource(window.markets_view.proxy_model.index(0, 0))
    assert window.markets_view.model.rows[source.row()]["ticker"] == ticker

    search.clear()
    asset_filter.setCurrentText("Crypto")

    expected_crypto_rows = sum(1 for row in window.markets_view.model.rows if row["asset_type"] == "Crypto")
    assert window.markets_view.proxy_model.rowCount() == expected_crypto_rows
    for row in range(window.markets_view.proxy_model.rowCount()):
        source = window.markets_view.proxy_model.mapToSource(window.markets_view.proxy_model.index(row, 0))
        assert window.markets_view.model.rows[source.row()]["asset_type"] == "Crypto"


def test_qt_shell_step_advances_runtime_snapshot() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)

    window = KojakStreetWindow(state, runtime)
    step_button = window.findChild(QPushButton, "ActionButton")

    assert app is not None
    assert step_button is not None

    window.step_simulation()
    _wait_for_simulation(window)

    assert window.state.date == state.date + timedelta(days=1)
    assert window.top_bar.date_value.text() == window.state.date.strftime("%d.%m.%Y")


def test_qt_shell_keeps_macro_view_instance_on_day_step() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)

    window = KojakStreetWindow(state, runtime)
    window.set_active_view("macro")
    macro_view = window.views["macro"]

    assert app is not None

    window.step_simulation()
    _wait_for_simulation(window)

    assert window.active_view_key == "macro"
    assert window.stack.currentWidget() is macro_view
    assert window.views["macro"] is macro_view


def test_qt_shell_keeps_portfolio_visible_on_day_step() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)
    window = KojakStreetWindow(state, runtime)

    window.set_active_view("portfolio")
    assert window.stack.currentWidget() is window.views["portfolio"]

    window.state = runtime.step_day()
    window._refresh_active_view()

    assert app is not None
    assert window.active_view_key == "portfolio"
    assert window.stack.currentWidget() is window.views["portfolio"]


def test_qt_shell_keeps_news_view_instance_on_day_step() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)

    window = KojakStreetWindow(state, runtime)
    window.set_active_view("news")
    news_view = window.views["news"]

    assert app is not None

    window.step_simulation()
    _wait_for_simulation(window)

    assert window.active_view_key == "news"
    assert window.stack.currentWidget() is news_view
    assert window.views["news"] is news_view


def test_qt_shell_running_tick_can_update_status_without_view_refresh() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)
    window = KojakStreetWindow(state, runtime)
    window.set_active_view("macro")
    macro_view = window.views["macro"]
    original_date = window.state.date

    runtime.set_running(True)
    window.pending_ticks = 0
    window.refresh_every_ticks = 5
    window._request_simulation_steps(1, force_refresh=False)
    _wait_for_simulation(window)

    assert app is not None
    assert window.stack.currentWidget() is macro_view
    assert window.state.date == original_date
    assert window.top_bar.date_value.text() == (original_date + timedelta(days=1)).strftime("%d.%m.%Y")


def test_qt_shell_running_tick_applies_live_market_quotes_without_full_refresh() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)
    window = KojakStreetWindow(state, runtime)
    market_view = window.views["markets"]
    first_row = market_view.model.rows[0]
    ticker = first_row["ticker"]
    asset_type = first_row["asset_type"]
    book = {
        "Stock": runtime.state.stocks,
        "Commodity": runtime.state.commodities,
        "Crypto": runtime.state.cryptos,
        "Fund": runtime.state.funds,
        "Index": runtime.state.indices,
    }[asset_type]
    original_date = window.state.date

    runtime.set_running(True)
    book[ticker]["kurs"] = 4321.0
    book[ticker]["aenderung"] = 3.25
    window._request_simulation_steps(1, force_refresh=False)
    _wait_for_simulation(window)

    assert app is not None
    assert window.state.date == original_date
    assert first_row["sort_values"][6] == 4321.0
    assert first_row["sort_values"][7] == 3.25


def test_qt_shell_daily_advance_keeps_workspace_interactive_and_combo_popup_open() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)
    window = KojakStreetWindow(state, runtime)
    combo = window.findChild(QComboBox, "MarketTypeFilter")

    assert app is not None
    assert combo is not None
    window.show()
    combo.setFocus()
    combo.showPopup()
    QApplication.processEvents()
    assert combo.view().isVisible()

    window._request_simulation_steps(1, force_refresh=False)

    assert window.stack.isEnabled()
    assert window.side_nav.isEnabled()
    assert combo.view().isVisible()

    combo.hidePopup()
    _wait_for_simulation(window)
    window.close()


def test_qt_shell_portfolio_live_delta_does_not_full_refresh_view() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)
    runtime.current_delta = lambda: SimulationDelta(
        1, state.date.strftime("%Y-%m-%d"), frozenset({"portfolio_current"})
    )
    runtime.portfolio_current_rows = lambda: [{"cash": 321.0, "positions": 2, "futures": 1}]
    window = KojakStreetWindow(state, runtime)
    window.set_active_view("portfolio")
    portfolio_view = window.views["portfolio"]
    calls: list[list[dict[str, object]]] = []
    portfolio_view.refresh = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("full refresh")
    )
    portfolio_view.apply_live_current_rows = lambda rows: calls.append(rows)

    window._apply_live_market_updates()

    assert app is not None
    assert calls == [[{"cash": 321.0, "positions": 2, "futures": 1}]]


def test_qt_shell_allows_perpetual_trades_for_derivative_futures_only() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)
    window = KojakStreetWindow(state, runtime)
    future_ticker = next(
        ticker
        for ticker, asset in state.derivatives.items()
        if asset.get("instrument_type") == "Inflation Swap"
    )
    option_ticker = next(
        ticker
        for ticker, asset in state.derivatives.items()
        if asset.get("instrument_type") == "Option"
    )

    assert app is not None
    assert window._allows_perpetual_trade(future_ticker) is True
    assert window._allows_perpetual_trade(option_ticker) is False


def test_qt_shell_queues_steps_on_persistent_worker() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    runtime = FakeRuntime(state)
    window = KojakStreetWindow(state, runtime)

    runtime.set_running(True)
    window.top_bar.run_button.setChecked(True)
    window._request_simulation_steps(1, force_refresh=False)
    window._request_simulation_steps(2, force_refresh=False)
    _wait_for_simulation(window)
    _wait_for_simulation(window)

    assert app is not None
    assert window.simulation_thread is not None
    assert window.pending_ticks == 3
    assert window.top_bar.date_value.text() == (state.date + timedelta(days=3)).strftime("%d.%m.%Y")

    window.top_bar.run_button.setChecked(False)
    window._shutdown_simulation_worker()


def test_qt_shell_has_fixed_1x_simulation_speed() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    window = KojakStreetWindow(state)

    assert app is not None
    assert window.top_bar.findChild(QComboBox, "SpeedBox") is None
    assert window._timer_interval_ms() == 2000
    assert window.ticks_per_timeout == 1
    assert window.refresh_every_ticks == 1


def _wait_for_simulation(window: KojakStreetWindow) -> None:
    deadline = time.monotonic() + 2.0
    while window.simulation_busy and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    QApplication.processEvents()
    assert not window.simulation_busy
