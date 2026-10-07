from __future__ import annotations

import os
from datetime import datetime, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QTableView,
    QTabWidget,
)

import daten
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.views.bondmarket_view import BondMarketView
from kojakstreet.ui_qt.views.forex_view import ForexView
from kojakstreet.ui_qt.views.global_macro_view import GlobalMacroView
from kojakstreet.ui_qt.views.macro_view import MacroView
from kojakstreet.ui_qt.views.news_view import NewsView
from kojakstreet.ui_qt.views.portfolio_view import PortfolioView
from kojakstreet.ui_qt.views.trade_map_view import TradeMapCanvas, TradeMapView
from kojakstreet.ui_qt.widgets.empty_state import EmptyState
from kojakstreet.ui_qt.widgets.view_header import ViewHeader


def test_portfolio_view_renders_positions_and_balances_tables() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    state.portfolio = {"TSLA": {"stueck": 10.0, "kaufkurs": 80.0}}

    view = PortfolioView(state)
    positions = view.findChild(QTableView, "PositionsTable")
    tabs = view.findChild(QTabWidget, "PortfolioTabs")
    bonds = view.findChild(QTableView, "PortfolioBondsTable")
    currencies = view.findChild(QTableView, "PortfolioCurrenciesTable")
    header = view.findChild(ViewHeader)

    assert app is not None
    assert header is not None
    assert positions is not None
    assert tabs is not None
    assert bonds is not None
    assert currencies is not None
    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Assets", "Bonds", "Currencies"]
    assert positions.model().columnCount() == 12
    assert bonds.model().columnCount() == 12
    assert currencies.model().columnCount() == 4
    assert positions.model().rowCount() == 1
    assert view.empty_state.isHidden()
    assert not view.chart_panel.isHidden()
    assert view.close_future_button.isHidden()


def test_portfolio_view_draws_selected_position_history() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten, profile="portfolio")
    ticker = next(iter(state.stocks))
    state.portfolio = {ticker: {"stueck": 10.0, "kaufkurs": 80.0}}
    state.stocks[ticker]["historie"] = [(100.0 + index, "01.01.1990", "") for index in range(12)]

    view = PortfolioView(state)
    table = view.findChild(QTableView, "PositionsTable")

    assert app is not None
    assert table is not None

    table.selectRow(0)

    assert view.chart_panel.chart_draw_count == 1
    assert len(view.chart_panel._chart_points) == 12


def test_portfolio_view_shows_empty_state_only_without_positions() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten, profile="portfolio")
    state.portfolio = {}
    state.perpetuals = {}

    view = PortfolioView(state)

    assert app is not None
    assert not view.empty_state.isHidden()
    assert view.chart_panel.isHidden()


def test_macro_view_renders_country_rows() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MacroView(state)
    table = view.findChild(QTableView, "MacroTable")

    assert app is not None
    assert table is not None
    assert table.model().rowCount() >= len(state.macro)
    assert table.model().columnCount() == 8
    assert table.model().headerData(0, Qt.Horizontal) == "Region"
    assert table.model().headerData(6, Qt.Horizontal) == "Balance Sheet"
    assert table.model().headerData(7, Qt.Horizontal) == "Rating"

    view._open_country_detail(0)

    assert view.pages.currentWidget() is view.detail_view
    assert {"Default Prob.", "Trade Balance", "Import Dep.", "Debt/GDP", "Credit Growth"} <= set(view.detail_view.kpi_values)
    assert "Bottleneck" not in view.detail_view.subtitle.text()
    view.detail_view.tabs.setCurrentIndex(1)
    production_table = view.detail_view.findChild(QTableView, "CountryProductionTable")
    assert production_table is not None
    assert production_table.model().columnCount() == 4
    assert [production_table.model().headerData(index, Qt.Horizontal) for index in range(4)] == [
        "Product",
        "Produced",
        "Demanded",
        "Gap",
    ]


def test_macro_view_live_rows_refresh_open_country_detail(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    view = MacroView(state)
    table = view.findChild(QTableView, "MacroTable")

    assert app is not None
    assert table is not None

    view._open_country_detail(0)
    calls: list[str] = []
    monkeypatch.setattr(view.detail_view, "refresh", lambda _state: calls.append("refresh"))

    rows = [
        {
            "region": region,
            "population": macro.get("bevoelkerung", 0.0),
            "gdp": macro.get("bip_abs", 0.0),
            "growth": macro.get("bip_prozent", 0.0),
            "rate": macro.get("zins", 0.0),
            "inflation": macro.get("inflation", 0.0),
            "unemployment": macro.get("arbeitslosigkeit", 0.0),
            "rating": macro.get("rating", "BBB"),
        }
        for region, macro in state.macro.items()
    ]
    view.apply_live_current_rows(rows)

    assert calls == ["refresh"]
    assert view.detail_view.region == table.model().index(0, 0).data()
    assert view.detail_view.tabs.count() == 5
    assert [view.detail_view.tabs.tabText(i).replace("&&", "&") for i in range(5)] == [
        "Overview", "Production", "Trade", "Sectors", "Society & Politics",
    ]

    view.detail_view.tabs.setCurrentIndex(1)
    view.detail_view._open_production_metric(0)

    assert view.pages.currentWidget() is view.metric_detail

    view.metric_detail.back_requested.emit()

    assert view.pages.currentWidget() is view.detail_view


def test_global_macro_view_renders_liquidity_dashboard() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = GlobalMacroView(state)
    table = view.findChild(QTableView, "GlobalMacroTable")

    assert app is not None
    assert view.kpi_values["global_m2"].text() != "-"
    assert view.kpi_values["net_liquidity"].text() != "-"
    assert table is not None
    assert table.model().rowCount() == len(state.global_macro)
    assert table.model().columnCount() == 5

    table.selectRow(3)
    selected_indicator = table.model().index(table.currentIndex().row(), 0).data()
    view.refresh(state)

    assert table.model().index(table.currentIndex().row(), 0).data() == selected_indicator

    view._open_metric_detail(0)

    assert view.pages.currentWidget() is view.detail_view
    assert view.detail_view.asset_type == "GlobalMacro"
    assert view.detail_view.kpi_frame.isHidden() is True
    assert view.detail_view.title.text() == table.model().index(0, 0).data()


def test_bondmarket_view_renders_legacy_bond_offers() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = BondMarketView(state)
    table = view.findChild(QTableView, "BondMarketTable")
    category_filter = view.findChild(QComboBox, "BondCategoryFilter")
    region_filter = view.findChild(QComboBox, "BondRegionFilter")
    rating_filter = view.findChild(QComboBox, "BondRatingFilter")
    maturity_filter = view.findChild(QComboBox, "BondMaturityFilter")

    assert app is not None
    assert table is not None
    assert category_filter is not None
    assert region_filter is not None
    assert rating_filter is not None
    assert maturity_filter is not None
    assert table.model().columnCount() == 13
    assert table.model().rowCount() > 0
    assert category_filter.currentText() == "Government"
    assert "All" not in [category_filter.itemText(index) for index in range(category_filter.count())]
    assert "All Regions" not in [region_filter.itemData(index) for index in range(region_filter.count())]
    assert "All Ratings" not in [rating_filter.itemText(index) for index in range(rating_filter.count())]
    assert "All Maturities" not in [maturity_filter.itemText(index) for index in range(maturity_filter.count())]
    maturities = {table.model().index(row, 9).data().split(".")[0] for row in range(table.model().rowCount())}
    assert maturities.issubset({"2", "3"})

    view._open_bond_detail(0)

    assert view.pages.currentWidget() is view.bond_detail_view
    assert view.bond_detail_view.asset_type == "Bond"
    assert view.bond_detail_view.kpi_frame.isHidden() is True
    assert view.bond_detail_view.legend_labels == []

    selected_symbol = view.bond_detail_view.ticker
    for bond in state.bond_market:
        if str(bond.get("symbol", "")) == selected_symbol:
            bond["historie"].append((float(bond["price"]) + 1.0, "02.01.1990", ""))
            break
    view.refresh(state)

    assert view.bond_detail_view.ticker == selected_symbol
    assert len(view.bond_detail_view._history_points()) >= 2


def test_bondmarket_filters_only_offer_available_ratings_and_maturities() -> None:
    app = QApplication.instance() or QApplication([])
    state = GameState(date=datetime(1990, 1, 1, tzinfo=timezone.utc), cash=0.0, display_currency="GD")
    rows = [
        {
            "symbol": "GOV-ALB-BBB-2Y",
            "issuer": "Central Government Albania",
            "issuer_type": "Government",
            "category": "Government",
            "region": "Albania",
            "rating": "BBB",
            "price": 100.0,
            "coupon": 0.04,
            "yield": 0.042,
            "maturity_years": 2.0,
        },
        {
            "symbol": "GOV-ALB-BB-10Y",
            "issuer": "Central Government Albania",
            "issuer_type": "Government",
            "category": "Government",
            "region": "Albania",
            "rating": "BB",
            "price": 96.0,
            "coupon": 0.055,
            "yield": 0.061,
            "maturity_years": 10.0,
        },
        {
            "symbol": "GOV-USA-AAA-30Y",
            "issuer": "Central Government USA",
            "issuer_type": "Government",
            "category": "Government",
            "region": "USA",
            "rating": "AAA",
            "price": 110.0,
            "coupon": 0.035,
            "yield": 0.033,
            "maturity_years": 30.0,
        },
    ]

    view = BondMarketView(state, current_provider=lambda: rows)
    rating_filter = view.findChild(QComboBox, "BondRatingFilter")
    maturity_filter = view.findChild(QComboBox, "BondMaturityFilter")

    assert app is not None
    assert rating_filter is not None
    assert maturity_filter is not None
    assert [rating_filter.itemText(index) for index in range(rating_filter.count())] == ["BBB", "BB"]
    assert [maturity_filter.itemText(index) for index in range(maturity_filter.count())] == ["0-3Y"]

    rating_filter.setCurrentText("BB")

    assert [maturity_filter.itemText(index) for index in range(maturity_filter.count())] == ["7-15Y"]
    assert view.model.rowCount() == 1
    assert view.model.index(0, 0).data() == "GOV-ALB-BB-10Y"


def test_forex_view_renders_currency_pairs() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = ForexView(state)
    table = view.findChild(QTableView, "ForexTable")

    assert app is not None
    assert table is not None
    assert len(view.kpi_values) == len(state.currency_strength) - 1
    assert "GLD" not in view.kpi_values
    assert table.model().columnCount() == 5
    assert table.model().rowCount() > 0
    visible_pairs = [
        table.model().index(row, 0).data()
        for row in range(table.model().rowCount())
    ]
    assert visible_pairs
    assert all("GLD" in pair for pair in visible_pairs)
    assert visible_pairs[0].startswith("GLD/")

    candle_button = next(button for button in view.chart_panel.findChildren(QPushButton) if button.text() == "Candle")
    candle_button.click()

    assert view.chart_panel.chart_mode == "Candle"

    first_index = table.model().index(0, 0)
    view._open_pair_detail(first_index)

    assert view.pages.currentWidget() is view.pair_detail_view
    assert view.pair_detail_view.asset_type == "Forex"
    assert view.pair_detail_view.kpi_frame.isHidden() is True


def test_news_view_renders_empty_feed_state() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    state.news = [
        ("01.02.1990", " ALERT - BREAKING NEWS: GENERAL STRIKE\nDetails", "ROT"),
        ("01.03.1990", " CENTRAL BANK DECISION: Policy rate UNCHANGED", "ZENTRALBANK"),
    ]

    view = NewsView(state)
    table = view.findChild(QTableView, "NewsTable")
    tabs = view.findChild(QTabWidget, "NewsTabs")
    calendar = view.findChild(QTableView, "EconomicCalendarTable")
    search = view.findChild(QLineEdit, "NewsSearchInput")
    priority_filter = view.findChild(QComboBox, "NewsPriorityFilter")

    assert app is not None
    assert tabs is not None
    assert [tabs.tabText(index) for index in range(tabs.count())] == ["Economic Calendar", "Market News"]
    assert table is not None
    assert calendar is not None
    assert calendar.model().columnCount() == 8
    assert calendar.model().rowCount() > 0
    assert calendar.model().headerData(6, Qt.Horizontal) == "Expected"
    assert calendar.model().headerData(7, Qt.Horizontal) == "Surprise"
    assert search is not None
    assert priority_filter is not None
    assert table.model().columnCount() == 7
    assert table.model().rowCount() == 2

    priority_filter.setCurrentText("High")
    visible_rows = [row for row in range(table.model().rowCount()) if not table.isRowHidden(row)]
    assert len(visible_rows) == 1

    priority_filter.setCurrentText("All Priorities")
    search.setText("central bank")
    visible_rows = [row for row in range(table.model().rowCount()) if not table.isRowHidden(row)]
    assert len(visible_rows) == 1


def test_trade_map_view_renders_fictional_country_routes() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = TradeMapView(state)
    canvas = view.findChild(TradeMapCanvas, "TradeMapCanvas")
    product_filter = view.findChild(QComboBox, "TradeMapProductFilter")

    assert app is not None
    assert canvas is not None
    assert product_filter is not None
    assert len(canvas.countries) == len(state.macro)
    assert canvas.flows
    assert product_filter.currentText() == "All Trade"
    assert product_filter.count() > 1

def test_news_view_empty_feed_has_empty_state() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    state.news = []

    view = NewsView(state)
    empty = view.findChild(EmptyState)

    assert app is not None
    assert empty is not None
