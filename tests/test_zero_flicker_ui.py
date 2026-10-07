from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QPersistentModelIndex, Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QTableView

import daten
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.bonds import build_bond_offers
from kojakstreet.ui_qt.app import KojakStreetWindow
from kojakstreet.ui_qt.models.simple_table_model import SimpleTableModel
from kojakstreet.ui_qt.views.bondmarket_view import BondMarketView, BondOfferTableModel
from kojakstreet.ui_qt.widgets.qt_chart import FastChartView
from kojakstreet.ui_qt.widgets.stock_detail_dialog import StockDetailView
from kojakstreet.ui_qt.widgets.top_bar import TickerTape
from kojakstreet.visible_state import ticker_items


def test_company_overview_patches_existing_cards_and_keeps_focus(qt_application):
    state = snapshot_from_legacy(daten)
    ticker, asset = next(iter(state.stocks.items()))
    detail = StockDetailView()
    detail.update_asset(ticker, deepcopy(asset), "Stock", state)
    detail.detail_tabs.setCurrentWidget(detail.overview_tab)
    detail.show()
    qt_application.processEvents()
    cards = list(detail._fundamental_cards)
    labels = dict(detail._kpi_value_widgets)
    detail.order_quantity.setText("7")
    detail.order_quantity.setFocus()
    updated = {**asset, "kurs": 12345.67, "market_cap": 987654321.0}
    detail.update_live_quote(updated, state)
    assert detail._fundamental_cards == cards
    assert detail._kpi_value_widgets == labels
    assert "12,345.67" in labels["Price"].text()
    assert detail.detail_tabs.currentWidget() is detail.overview_tab
    assert detail.order_quantity.text() == "7"
    assert detail.order_quantity.hasFocus()


def test_supply_values_do_not_reset_model_or_scroll(qt_application):
    state = snapshot_from_legacy(daten)
    ticker, asset = next(
        (key, value) for key, value in state.stocks.items() if value.get("output_mix")
    )
    detail = StockDetailView()
    detail.update_asset(ticker, deepcopy(asset), "Stock", state)
    detail.detail_tabs.setCurrentWidget(detail.supply_tab)
    detail.resize(900, 450)
    detail.show()
    qt_application.processEvents()
    resets = QSignalSpy(detail.supply_model.modelReset)
    selected = detail._selected_supply_identity()
    before_scroll = detail.supply_table.verticalScrollBar().value()
    detail.update_live_quote({**asset, "production_capacity": 100000.0}, state)
    assert resets.count() == 0
    assert detail._selected_supply_identity() == selected
    assert detail.supply_table.verticalScrollBar().value() == before_scroll


def test_sorted_table_patch_keeps_logical_selection_and_scroll(qt_application):
    model = SimpleTableModel(["Key", "Price"])
    rows = [[f"ID{i:03}", i] for i in range(200)]
    model.set_rows(rows, sort_values=[[row[0], row[1]] for row in rows])
    table = QTableView()
    table.setModel(model)
    table.resize(350, 200)
    table.show()
    model.fetchMore()
    model.sort(1, Qt.SortOrder.DescendingOrder)
    table.selectRow(4)
    qt_application.processEvents()
    table.verticalScrollBar().setValue(40)
    selected = QPersistentModelIndex(table.currentIndex())
    identity = selected.data()
    resets = QSignalSpy(model.modelReset)
    changed = [[row[0], row[1] + 1] for row in rows]
    model.set_rows(changed, sort_values=[[row[0], row[1]] for row in changed])
    assert resets.count() == 0
    assert selected.data() == identity
    assert table.verticalScrollBar().value() == 40
    assert model.loaded_rows == 200


def test_bond_price_changes_preserve_model_identity_and_sorted_selection(qt_application):
    state = snapshot_from_legacy(daten)
    offers = build_bond_offers(state, "All")[:20]
    model = BondOfferTableModel(offers)
    model.sort(6, Qt.SortOrder.DescendingOrder)
    index = QPersistentModelIndex(model.index(3, 0))
    symbol = index.data()
    resets = QSignalSpy(model.modelReset)
    changed = [replace(offer, price=offer.price + i) for i, offer in enumerate(offers)]
    model.set_offers(changed)
    assert resets.count() == 0
    assert index.data() == symbol
    assert sorted((offer.price for offer in changed), reverse=True) == [
        offer.price for offer in model.offers
    ]


def test_unchanged_bond_dropdowns_keep_option_models(qt_application):
    state = snapshot_from_legacy(daten)
    view = BondMarketView(state)
    combos = [view.category_filter, view.region_filter, view.rating_filter, view.maturity_filter]
    spies = [
        (QSignalSpy(combo.model().rowsRemoved), QSignalSpy(combo.model().rowsInserted))
        for combo in combos
    ]
    selected = [(combo.currentText(), combo.currentData()) for combo in combos]
    for _ in range(4):
        view._populate_filter()
    assert all(removed.count() == inserted.count() == 0 for removed, inserted in spies)
    assert [(combo.currentText(), combo.currentData()) for combo in combos] == selected


def test_ticker_reorders_only_offscreen_cells_and_updates_visible_old_quote(qt_application):
    tape = TickerTape()
    tape.resize(300, 60)
    initial = [{"ticker": f"T{i}", "price": 99.99, "change": 1.0} for i in range(8)]
    tape.set_items(initial)
    tape.offset = tape._tile_width() - 100
    visible = tape._visible_cells()
    assert visible == {0}
    origin = -tape._tile_width() + tape.offset
    geometry = (tape.offset, tape._item_starts[:], tape.content_width)
    incoming = (
        [{"ticker": "NEW", "price": 101.0, "change": 9.0}]
        + [{**item, "price": 100.0} for item in reversed(initial[1:])]
        + [{"ticker": "T0", "price": 100.01, "change": -2.0, "ranked": False}]
    )
    tape.set_items(incoming)
    assert tape.items[0]["ticker"] == "T0"
    assert tape.items[0]["price"] == 100.01
    assert (tape.offset, tape._item_starts, tape.content_width) == geometry
    assert -tape._tile_width() + tape.offset == origin
    for _ in range(500):
        tape.scroll()
    assert "T0" not in {item["ticker"] for item in tape.items}
    assert {item["ticker"] for item in tape.items} == {
        item["ticker"] for item in incoming if item.get("ranked", True)
    }
    assert len(tape._layout_cache) <= len(tape.items)


def test_worker_supplies_current_values_for_ticker_leaving_ranking():
    from types import SimpleNamespace

    asset = lambda price, change: {"kurs": price, "aenderung": change}
    world = SimpleNamespace(
        aktien={str(i): asset(i + 100, i) for i in range(10)},
        rohstoffe={},
        kryptos={},
        indizes={},
        _tape_display_ids=[("Stock", "0")],
    )
    quotes = ticker_items(world)
    extra = next(item for item in quotes if item["ticker"] == "0")
    assert extra == {
        "ticker": "0",
        "price": 100,
        "change": 0,
        "ranked": False,
        "asset_type": "Stock",
    }
    assert len(quotes) == 5


def test_ticker_distinguishes_stock_and_index_with_same_symbol(qt_application):
    tape = TickerTape()
    items = [
        {"asset_type": "Stock", "ticker": "SAME", "price": 10.0, "change": 2.0},
        {"asset_type": "Index", "ticker": "SAME", "price": 1000.0, "change": 3.0},
    ]
    tape.set_items(items)
    tape.set_items([{**item, "price": item["price"] + 1} for item in items])
    assert {(item["asset_type"], item["price"]) for item in tape.items} == {
        ("Stock", 11),
        ("Index", 1001),
    }


def test_multi_line_and_candle_ticks_reuse_graphics(qt_application):
    chart = FastChartView()
    chart.plot_lines(
        [("Price", [10, 11, 12], "#14b8a6"), ("EMA 20", [9, 10, 11], "#22d3ee")], legend=True
    )
    curves = list(chart._series_items)
    legend = [chart.legend_layout.itemAt(i).widget() for i in range(chart.legend_layout.count())]
    chart.plot_lines(
        [("Price", [10, 11, 13], "#14b8a6"), ("EMA 20", [9, 10, 12], "#22d3ee")], legend=True
    )
    assert chart._series_items == curves
    assert [
        chart.legend_layout.itemAt(i).widget() for i in range(chart.legend_layout.count())
    ] == legend
    assert list(curves[0].yData) == [10, 11, 13]
    chart.plot_candles([(10, "01.01.1990", ""), (11, "02.01.1990", "")], range_points=22)
    candle = chart._candle_item
    chart.plot_candles([(10, "01.01.1990", ""), (12, "02.01.1990", "")], range_points=22)
    assert chart._candle_item is candle
    assert candle.data[-1][2] == 12


def test_busy_day_keeps_navigation_enabled_and_defers_pause_and_detail_request(
    monkeypatch, qt_application
):
    state = snapshot_from_legacy(daten)

    class Runtime:
        running = False
        busy = False

        def ticker_tape_quotes(self):
            return ticker_items(daten)

        def snapshot_for_view(self, view):
            return state

        def sync_visible_scope(self, scope):
            if self.busy:
                raise AssertionError("UI must not wait for the worker during a day")
            return state

        def set_running(self, running):
            raise AssertionError("UI must defer pause during a day")

    window = KojakStreetWindow(state, Runtime())
    monkeypatch.setattr(window, "_ensure_simulation_worker", lambda: None)
    monkeypatch.setattr(window, "_shutdown_simulation_worker", lambda: None)
    window._request_simulation_steps(1, force_refresh=False)
    window.runtime.busy = True
    assert window.markets_view.isEnabled()
    assert window.top_bar.step_button.isEnabled()
    window._visible_scope_provider()(
        {"view": "markets", "selection": {"ticker": "ABX", "tab": "overview"}}
    )
    assert window._pending_scope["selection"]["tab"] == "overview"
    window.top_bar.run_button.setChecked(False)
    window.toggle_simulation()
    assert window._pending_running is False
    assert not window.timer.isActive()
