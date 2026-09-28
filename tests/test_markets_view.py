from __future__ import annotations

import os
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QTableView

import daten
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.countries import COUNTRY_SYMBOLS
from kojakstreet.ui_qt.models.market_table_model import MarketTableModel
from kojakstreet.ui_qt.views.markets_view import MarketsView
from kojakstreet.ui_qt.widgets.stock_detail_dialog import StockDetailView


def test_markets_view_filters_watchlist() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    table = view.findChild(QTableView)
    asset_filter = view.findChild(QComboBox, "MarketTypeFilter")

    assert app is not None
    assert table is not None
    assert asset_filter is not None

    asset_filter.setCurrentText("Watchlist")

    assert view.proxy_model.rowCount() == len(view.watchlist)


def test_markets_view_type_filter_includes_all_option() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    asset_filter = view.findChild(QComboBox, "MarketTypeFilter")

    assert app is not None
    assert asset_filter is not None
    assert asset_filter.itemText(0) == "All"
    assert "All" in [asset_filter.itemText(index) for index in range(asset_filter.count())]


def test_markets_view_search_matches_sector() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    table = view.findChild(QTableView)
    search = view.findChild(QLineEdit, "MarketSearchInput")

    assert app is not None
    assert table is not None
    assert search is not None

    search.setText("Automobil")

    assert view.proxy_model.rowCount() > 0
    for row in range(view.proxy_model.rowCount()):
        source = view.proxy_model.mapToSource(view.proxy_model.index(row, 0))
        assert "Automotive" in view.model.rows[source.row()]["values"][5]


def test_markets_view_refresh_preserves_selected_ticker() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    table = view.findChild(QTableView, "MarketTable")

    assert app is not None
    assert table is not None
    ticker = next(iter(state.stocks))

    for row in range(view.proxy_model.rowCount()):
        source = view.proxy_model.mapToSource(view.proxy_model.index(row, 0))
        if view.model.rows[source.row()]["ticker"] == ticker:
            table.selectRow(row)
            break

    view.refresh(snapshot_from_legacy(daten))

    source = view.proxy_model.mapToSource(table.currentIndex())
    assert view.model.rows[source.row()]["ticker"] == ticker


def test_markets_view_draws_initial_selection_without_redundant_refresh() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    table = view.findChild(QTableView, "MarketTable")

    assert app is not None
    assert table is not None
    assert view.chart_panel.chart_draw_count == 1

    view.refresh(snapshot_from_legacy(daten))

    assert view.chart_panel.chart_draw_count == 1

    table.selectRow(1)

    assert view.chart_panel.chart_draw_count == 2


def test_markets_view_live_updates_chart_after_user_selection() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    table = view.findChild(QTableView, "MarketTable")

    assert app is not None
    assert table is not None

    table.selectRow(1)
    draw_count = view.chart_panel.chart_draw_count

    view.refresh(snapshot_from_legacy(daten))

    assert view.live_chart_ticker is not None
    assert view.chart_panel.chart_draw_count == draw_count + 1


def test_markets_view_preserves_market_cap_sort_on_refresh() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    table = view.findChild(QTableView, "MarketTable")

    assert app is not None
    assert table is not None

    table.sortByColumn(8, Qt.SortOrder.DescendingOrder)
    before = _visible_market_caps(view)

    view.refresh(snapshot_from_legacy(daten))
    after = _visible_market_caps(view)

    assert before == sorted(before, reverse=True)
    assert after == sorted(after, reverse=True)
    assert table.horizontalHeader().sortIndicatorSection() == 8
    assert table.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder


def test_markets_view_market_cap_shows_regional_currency() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)

    assert app is not None
    region = next(iter(COUNTRY_SYMBOLS))
    symbol = COUNTRY_SYMBOLS[region]
    assert any(row["values"][8].endswith(f" {symbol}") for row in view.model.rows if row["values"][4] == region)


def test_markets_view_crypto_rows_show_sector_value() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)

    assert app is not None
    crypto_sectors = {row["values"][5] for row in view.model.rows if row["asset_type"] == "Crypto"}
    assert "Digital Store of Value" in crypto_sectors
    assert "Payment Rails" in crypto_sectors
    assert "Decentralized Storage" in crypto_sectors
    assert "Energy Trading Grid" in crypto_sectors


def test_markets_view_stock_rows_hide_rating_and_default_probability_columns() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)

    assert app is not None
    assert "Rating" not in view.model.HEADERS
    assert "Default Prob." not in view.model.HEADERS
    assert all(len(row["values"]) == len(view.model.HEADERS) for row in view.model.rows)


def test_markets_view_double_click_opens_in_app_stock_detail() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)

    assert app is not None

    stock_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Stock")
    view.model.rows[stock_row]["data"]["historie"] = [
        (100.0 + index, (date(2025, 1, 1) + timedelta(days=index)).isoformat(), "")
        for index in range(300)
    ]
    proxy_index = view.proxy_model.mapFromSource(view.model.index(stock_row, 0))
    view._open_stock_detail(proxy_index)

    assert view.pages.currentWidget() is view.stock_detail_view
    assert view.stock_detail_view.ticker == view.model.rows[stock_row]["ticker"]
    kpi_texts = [label.text() for label in view.stock_detail_view.findChildren(QLabel)]
    assert "RATING" in kpi_texts
    assert "DEFAULT PROBABILITY" in kpi_texts
    assert "Price" not in view.stock_detail_view.legend_labels
    assert view.stock_detail_view.legend_labels == []
    view.stock_detail_view.set_indicator(20, True)
    view.stock_detail_view.set_indicator(50, True)
    view.stock_detail_view.set_indicator(200, True)
    assert {"EMA 20", "EMA 50", "EMA 200"}.issubset(set(view.stock_detail_view.legend_labels))
    view.stock_detail_view.set_range(264)
    view.stock_detail_view.set_chart_mode("Candle")
    assert view.stock_detail_view.chart_mode == "Candle"
    assert view.stock_detail_view.last_candle_interval == "Monthly"
    assert view.stock_detail_view.last_candle_count >= 26
    view.stock_detail_view.set_chart_mode("Line")
    assert view.stock_detail_view.chart_mode == "Line"
    assert view.stock_detail_view.chart_view.last_candle_count == 0

    view.stock_detail_view.back_requested.emit()

    assert view.pages.currentWidget() is view.main_page


def test_markets_view_live_quotes_redraw_open_stock_detail_chart(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    assert app is not None

    stock_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Stock")
    row = view.model.rows[stock_row]
    row["data"]["historie"] = [(100.0 + index, "date", "") for index in range(8)]
    proxy_index = view.proxy_model.mapFromSource(view.model.index(stock_row, 0))
    view._open_asset_detail(proxy_index)

    draws: list[str] = []
    monkeypatch.setattr(view.stock_detail_view, "_draw_chart", lambda: draws.append("draw"))
    view.apply_live_quotes(
        [
            {
                "asset_type": row["asset_type"],
                "ticker": row["ticker"],
                "price": 123.45,
                "change": 1.5,
                "market_cap": 1_000_000.0,
                "region": row["region"],
            }
        ]
    )

    assert draws == ["draw"]
    assert view.stock_detail_view.current_price == 123.45


def test_markets_view_live_quotes_load_history_for_open_detail_chart(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    calls: list[tuple[str, str, int]] = []

    def history_provider(asset_type: str, ticker: str, limit: int) -> list[tuple[float, str, str]]:
        calls.append((asset_type, ticker, limit))
        return [(100.0 + index, "", "") for index in range(6)]

    view = MarketsView(state, history_provider=history_provider)
    assert app is not None

    commodity_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Commodity")
    row = view.model.rows[commodity_row]
    proxy_index = view.proxy_model.mapFromSource(view.model.index(commodity_row, 0))
    view._open_asset_detail(proxy_index)
    calls.clear()

    draws: list[str] = []
    monkeypatch.setattr(view.stock_detail_view, "_draw_chart", lambda: draws.append("draw"))
    view.apply_live_quotes(
        [
            {
                "asset_type": row["asset_type"],
                "ticker": row["ticker"],
                "price": 123.45,
                "change": 1.5,
                "market_cap": 1_000_000.0,
                "region": row["region"],
            }
        ]
    )

    assert draws == ["draw"]
    assert calls == []


def test_markets_view_double_click_opens_in_app_commodity_detail() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)

    assert app is not None

    commodity_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Commodity")
    view.model.rows[commodity_row]["data"]["historie"] = [(100.0 + index, "date", "") for index in range(300)]
    proxy_index = view.proxy_model.mapFromSource(view.model.index(commodity_row, 0))
    view._open_asset_detail(proxy_index)

    assert view.pages.currentWidget() is view.stock_detail_view
    assert view.stock_detail_view.asset_type == "Commodity"
    assert view.stock_detail_view.ticker == view.model.rows[commodity_row]["ticker"]
    assert "Price" not in view.stock_detail_view.legend_labels
    assert view.stock_detail_view.legend_labels == []


def test_markets_view_double_click_opens_in_app_crypto_detail() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)

    assert app is not None

    crypto_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Crypto")
    view.model.rows[crypto_row]["data"]["historie"] = [(100.0 + index, "date", "") for index in range(300)]
    proxy_index = view.proxy_model.mapFromSource(view.model.index(crypto_row, 0))
    view._open_asset_detail(proxy_index)

    assert view.pages.currentWidget() is view.stock_detail_view
    assert view.stock_detail_view.asset_type == "Crypto"
    assert view.stock_detail_view.ticker == view.model.rows[crypto_row]["ticker"]
    assert view.stock_detail_view.detail_tabs.isHidden() is False
    assert view.stock_detail_view.kpi_frame.isHidden() is False
    assert view.stock_detail_view.detail_tabs.isTabEnabled(1) is True
    assert view.stock_detail_view.supply_table.model().rowCount() >= 5
    kpi_texts = [label.text() for label in view.stock_detail_view.findChildren(QLabel)]
    assert "DEMAND" in kpi_texts
    assert "MARKET SHARE" in kpi_texts
    assert "UTILIZATION" in kpi_texts
    assert "Price" not in view.stock_detail_view.legend_labels
    assert view.stock_detail_view.legend_labels == []


def test_markets_view_keeps_fund_filter_and_shows_new_indices() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    asset_filter = view.findChild(QComboBox, "MarketTypeFilter")

    assert app is not None
    assert asset_filter is not None
    assert "Funds and ETFs" in [asset_filter.itemText(index) for index in range(asset_filter.count())]
    assert "Index" in [asset_filter.itemText(index) for index in range(asset_filter.count())]
    assert any(row["asset_type"] == "Fund" for row in view.model.rows)
    assert any(row["asset_type"] == "Index" for row in view.model.rows)


def test_markets_view_region_filter_includes_all_countries() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    region_filter = view.findChild(QComboBox, "MarketRegionFilter")

    assert app is not None
    assert region_filter is not None
    options = [region_filter.itemData(index) for index in range(region_filter.count())]
    assert set(state.macro) <= set(options)
    assert options[0] == "All Regions"


def test_markets_view_group_filter_depends_on_asset_type() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    asset_filter = view.findChild(QComboBox, "MarketTypeFilter")
    region_filter = view.findChild(QComboBox, "MarketRegionFilter")
    group_filter = view.findChild(QComboBox, "MarketSectorFilter")

    assert app is not None
    assert asset_filter is not None
    assert region_filter is not None
    assert group_filter is not None

    asset_filter.setCurrentText("Commodity")
    commodity_groups = [group_filter.itemData(index) for index in range(group_filter.count())]

    assert commodity_groups[0] == "All Groups"
    assert {row["filter_group"] for row in view.model.rows if row["asset_type"] == "Commodity"} <= set(commodity_groups)

    asset_filter.setCurrentText("Index")
    index_regions = [region_filter.itemData(index) for index in range(region_filter.count())]

    assert index_regions[0] == "All Regions"
    assert set(state.macro) <= set(index_regions)


def test_index_rows_show_underlying_country_market_cap() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    country = "Ameron"
    expected_market_cap = sum(
        float(asset.get("market_cap", 0.0))
        for asset in state.stocks.values()
        if asset.get("land") == country
    )
    index_row = next(row for row in view.model.rows if row["ticker"] == "AMX")

    assert app is not None
    assert index_row["asset_type"] == "Index"
    assert index_row["sort_values"][8] == pytest.approx(expected_market_cap)


def test_markets_view_index_filter_labels_price_column_as_points() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    asset_filter = view.findChild(QComboBox, "MarketTypeFilter")

    assert app is not None
    assert asset_filter is not None
    asset_filter.setCurrentText("Index")

    assert view.model.headerData(6, Qt.Orientation.Horizontal) == "Points"

    asset_filter.setCurrentText("Stock")

    assert view.model.headerData(6, Qt.Orientation.Horizontal) == "Price"


def test_markets_view_fund_filter_labels_market_cap_column_as_aum() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    asset_filter = view.findChild(QComboBox, "MarketTypeFilter")
    group_filter = view.findChild(QComboBox, "MarketSectorFilter")

    assert app is not None
    assert asset_filter is not None
    assert group_filter is not None
    asset_filter.setCurrentText("Funds and ETFs")

    fund_options = [group_filter.itemData(index) for index in range(group_filter.count())]
    assert fund_options[0] == "All Groups"
    assert fund_options
    assert view.model.headerData(8, Qt.Orientation.Horizontal) == "AUM"
    assert view.proxy_model.rowCount() == min(view.proxy_model._batch_size, len(state.funds))

    asset_filter.setCurrentText("Stock")

    assert view.model.headerData(8, Qt.Orientation.Horizontal) == "Market Cap"


def test_markets_view_derivative_filter_labels_market_cap_column_as_open_interest() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    asset_filter = view.findChild(QComboBox, "MarketTypeFilter")

    assert app is not None
    assert asset_filter is not None

    asset_filter.setCurrentText("Derivatives")

    assert view.model.headerData(8, Qt.Orientation.Horizontal) == "Open Interest"

    asset_filter.setCurrentText("Stock")

    assert view.model.headerData(8, Qt.Orientation.Horizontal) == "Market Cap"


def test_markets_view_derivatives_can_filter_region_and_instrument_separately() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    asset_filter = view.findChild(QComboBox, "MarketTypeFilter")
    region_filter = view.findChild(QComboBox, "MarketRegionFilter")
    group_filter = view.findChild(QComboBox, "MarketSectorFilter")

    assert app is not None
    assert asset_filter is not None
    assert region_filter is not None
    assert group_filter is not None

    asset_filter.setCurrentText("Derivatives")
    derivative_regions = [region_filter.itemData(index) for index in range(region_filter.count())]
    derivative_groups = [group_filter.itemData(index) for index in range(group_filter.count())]

    assert "Ameron" in derivative_regions
    assert "Valoria" in derivative_regions
    assert "Credit Default Swap" in derivative_groups
    assert "FX Forward" in derivative_groups

    region_filter.setCurrentIndex(derivative_regions.index("Valoria"))

    for proxy_row in range(view.proxy_model.rowCount()):
        source = view.proxy_model.mapToSource(view.proxy_model.index(proxy_row, 0))
        row = view.model.rows[source.row()]
        assert row["asset_type"] == "Derivative"
        assert row["region"] == "Valoria"


def test_markets_view_hides_trading_controls_for_indices() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)
    index_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Index")
    proxy_index = view.proxy_model.mapFromSource(view.model.index(index_row, 0))

    assert app is not None
    view._open_asset_detail(proxy_index)

    assert view.stock_detail_view.asset_type == "Index"
    assert view.stock_detail_view.order_quantity.isVisible() is False


def test_markets_view_limits_order_controls_by_asset_type() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    view = MarketsView(state)

    assert app is not None

    option_row = next(
        index
        for index, row in enumerate(view.model.rows)
        if row["asset_type"] == "Derivative" and row["data"].get("instrument_type") == "Option"
    )
    option = view.model.rows[option_row]
    view.chart_panel.update_asset(option["ticker"], option["asset_type"], option["data"])

    assert view.chart_panel.buy_button.isHidden() is False
    assert view.chart_panel.sell_button.isHidden() is False
    assert view.chart_panel.long_button.isHidden() is True
    assert view.chart_panel.short_button.isHidden() is True
    assert view.chart_panel.order_leverage.isHidden() is True

    future_row = next(
        index
        for index, row in enumerate(view.model.rows)
        if row["asset_type"] == "Derivative" and row["data"].get("instrument_type") == "FX Forward"
    )
    future = view.model.rows[future_row]
    view.chart_panel.update_asset(future["ticker"], future["asset_type"], future["data"])

    assert view.chart_panel.buy_button.isHidden() is True
    assert view.chart_panel.sell_button.isHidden() is True
    assert view.chart_panel.long_button.isHidden() is False
    assert view.chart_panel.short_button.isHidden() is False
    assert view.chart_panel.order_leverage.isHidden() is False

    stock_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Stock")
    stock = view.model.rows[stock_row]
    view.chart_panel.update_asset(stock["ticker"], stock["asset_type"], stock["data"])

    assert view.chart_panel.long_button.isHidden() is False
    assert view.chart_panel.short_button.isHidden() is False
    assert view.chart_panel.order_leverage.isHidden() is False


def test_markets_view_enables_stock_buy_when_snapshot_has_cash() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten, profile="markets")
    view = MarketsView(state)

    assert app is not None

    stock_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Stock")
    stock = view.model.rows[stock_row]
    view.chart_panel.update_asset(stock["ticker"], stock["asset_type"], stock["data"])
    view.chart_panel.order_quantity.setText("10")

    assert view.chart_panel.buy_button.isEnabled() is True


def test_market_detail_labels_derivative_notional_metric_as_open_interest() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    view = MarketsView(state)

    assert app is not None

    derivative_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Derivative")
    derivative = view.model.rows[derivative_row]
    view.chart_panel.update_asset(derivative["ticker"], derivative["asset_type"], derivative["data"])

    assert view.chart_panel.market_cap_caption.text() == "OPEN INTEREST"

    stock_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Stock")
    stock = view.model.rows[stock_row]
    view.chart_panel.update_asset(stock["ticker"], stock["asset_type"], stock["data"])

    assert view.chart_panel.market_cap_caption.text() == "MARKET CAP"


def test_derivative_detail_shows_use_case_text() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    future = next(row for row in MarketTableModel(state, set()).rows if row["asset_type"] == "Derivative" and row["data"].get("instrument_type") == "FX Forward")
    detail = StockDetailView(state=state)

    detail.update_asset(future["ticker"], future["data"], "Derivative", state)
    labels = [label.text() for label in detail.findChildren(QLabel)]

    assert app is not None
    assert "USE CASE" in labels
    assert any("exchange-rate" in label for label in labels)


def test_market_detail_shows_stock_open_interest_and_positioning() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    view = MarketsView(state)
    stock_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Stock")
    stock = view.model.rows[stock_row]
    stock["data"]["long_interest"] = 64_000_000.0
    stock["data"]["short_interest"] = 36_000_000.0
    stock["data"]["open_interest"] = 100_000_000.0

    assert app is not None

    view.chart_panel.update_asset(stock["ticker"], stock["asset_type"], stock["data"])

    assert view.chart_panel.open_interest_value.text() != "-"
    assert view.chart_panel.positioning_view.isHidden() is False


def test_market_detail_hides_positioning_chart_without_long_short_quote() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    view = MarketsView(state)
    fund_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Fund")
    fund = view.model.rows[fund_row]

    assert app is not None

    view.chart_panel.update_asset(fund["ticker"], fund["asset_type"], fund["data"])

    assert view.chart_panel.positioning_view.isHidden() is True


def test_stock_detail_view_shows_commodity_open_interest_and_positioning() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    ticker, commodity = next(iter(state.commodities.items()))
    commodity["long_interest"] = 42_000_000.0
    commodity["short_interest"] = 58_000_000.0
    commodity["open_interest"] = 100_000_000.0
    detail = StockDetailView(state=state)

    assert app is not None

    detail.update_asset(ticker, commodity, "Commodity")

    assert detail.positioning_view.isHidden() is False


def test_stock_detail_view_hides_positioning_chart_without_long_short_quote() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    ticker, fund = next(iter(state.funds.items()))
    detail = StockDetailView(state=state)

    assert app is not None

    detail.update_asset(ticker, fund, "Fund")

    assert detail.positioning_view.isHidden() is True


def test_crypto_detail_views_show_open_interest_positioning() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    view = MarketsView(state)
    crypto_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Crypto")
    crypto = view.model.rows[crypto_row]
    crypto["data"]["long_interest"] = 70_000_000.0
    crypto["data"]["short_interest"] = 90_000_000.0
    crypto["data"]["open_interest"] = 160_000_000.0
    detail = StockDetailView(state=state)

    assert app is not None

    view.chart_panel.update_asset(crypto["ticker"], crypto["asset_type"], crypto["data"])
    detail.update_asset(crypto["ticker"], crypto["data"], "Crypto")

    assert view.chart_panel.open_interest_value.text() != "-"
    assert view.chart_panel.positioning_view.isHidden() is False
    assert detail.positioning_view.isHidden() is False


def test_markets_view_emits_future_trade_for_derivative_futures() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)
    view = MarketsView(state)
    future_row = next(
        index
        for index, row in enumerate(view.model.rows)
        if row["asset_type"] == "Derivative" and row["data"].get("instrument_type") == "Yield Future"
    )
    future = view.model.rows[future_row]
    trades: list[tuple[str, str, str, float, int]] = []

    assert app is not None

    view.chart_panel.trade_requested.connect(lambda *args: trades.append(args))
    view.chart_panel.update_asset(future["ticker"], future["asset_type"], future["data"])
    view.chart_panel.order_quantity.setText("10")
    view.chart_panel.order_leverage.setCurrentText("5x")
    view.chart_panel.long_button.click()

    assert trades == [
        (
            future["ticker"],
            "FUTURE",
            "LONG",
            float(future["data"]["kurs"]) * 10.0 / 5.0,
            5,
        )
    ]


def test_markets_chart_preview_aggregates_candles_for_long_ranges() -> None:
    app = QApplication.instance() or QApplication([])
    state = snapshot_from_legacy(daten)

    view = MarketsView(state)

    assert app is not None

    stock_row = next(index for index, row in enumerate(view.model.rows) if row["asset_type"] == "Stock")
    view.model.rows[stock_row]["data"]["historie"] = [(100.0 + index, "date", "") for index in range(300)]
    view.chart_panel.set_range(264)
    view.chart_panel.set_chart_mode("Candle")
    view.chart_panel.update_asset(
        view.model.rows[stock_row]["ticker"],
        view.model.rows[stock_row]["asset_type"],
        view.model.rows[stock_row]["data"],
    )

    assert view.chart_panel.last_candle_interval == "Monthly"
    assert view.chart_panel.last_candle_count >= 26
    view.chart_panel.set_chart_mode("Line")
    assert view.chart_panel.chart_mode == "Line"
    assert view.chart_panel.chart_view.last_candle_count == 0


def _visible_market_caps(view: MarketsView) -> list[float]:
    values = []
    for row in range(view.proxy_model.rowCount()):
        source = view.proxy_model.mapToSource(view.proxy_model.index(row, 0))
        values.append(float(view.model.rows[source.row()]["sort_values"][8]))
    return values
