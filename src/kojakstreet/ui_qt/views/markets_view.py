"""Markets workspace view."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from kojakstreet.adapters.legacy_state import UI_HISTORY_LIMIT
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.chart_series import merge_history_by_date
from kojakstreet.ui_qt.chart_history_cache import (
    ChartHistoryCache,
    ChartHistoryKey,
    history_key,
    point_budget,
)
from kojakstreet.ui_qt.display import display_label
from kojakstreet.ui_qt.models.market_table_model import MarketFilterProxyModel, MarketTableModel
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.widgets.asset_chart_panel import AssetChartPanel
from kojakstreet.ui_qt.widgets.stock_detail_dialog import StockDetailView
from kojakstreet.ui_qt.widgets.view_header import ViewHeader


class MarketsView(QFrame):
    """Searchable market table plus read-only quote detail panel."""

    def __init__(
        self,
        state: GameState,
        trade_handler: Callable[[str, str, str, float, int], None] | None = None,
        history_provider: Callable[[str, str, int], list] | None = None,
    ) -> None:
        super().__init__()
        self.state = state
        self.trade_handler = trade_handler
        self.history_provider = history_provider
        self.history_cache = ChartHistoryCache(max_entries=32)
        self._active_history_key: ChartHistoryKey | None = None
        self.chart_panel: AssetChartPanel | None = None
        self.market_table: QTableView | None = None
        self.search_input: QLineEdit | None = None
        self.type_filter: QComboBox | None = None
        self.region_filter: QComboBox | None = None
        self.group_filter: QComboBox | None = None
        self._stock_detail_view: StockDetailView | None = None
        self.watchlist = self._build_watchlist()
        self.model = MarketTableModel(state, self.watchlist)
        self.proxy_model = MarketFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.live_chart_ticker: str | None = None
        self.pages = QStackedWidget()
        self.main_page = QWidget()

        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        main_layout = QVBoxLayout(self.main_page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)
        layout.addWidget(
            ViewHeader(
                "Markets",
                "Search, filter and inspect the legacy market universe in the new terminal shell",
                ["Refresh", "Export"],
            )
        )
        main_layout.addLayout(self._build_toolbar())
        main_layout.addWidget(self._build_content_splitter(), 1)
        self.pages.addWidget(self.main_page)
        layout.addWidget(self.pages, 1)

    @property
    def asset_count(self) -> int:
        return self.model.rowCount()

    @property
    def stock_detail_view(self) -> StockDetailView:
        if self._stock_detail_view is None:
            self._stock_detail_view = StockDetailView(state=self.state)
            self._stock_detail_view.back_requested.connect(self._show_market_list)
            self._stock_detail_view.chart_request_changed.connect(self._refresh_detail_history)
            if self.trade_handler is not None:
                self._stock_detail_view.trade_requested.connect(self.trade_handler)
            self.pages.addWidget(self._stock_detail_view)
        return self._stock_detail_view

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("MarketSearchInput")
        self.search_input.setPlaceholderText("Search ticker, name, region or sector")
        self.search_input.textChanged.connect(self.apply_filters)

        self.type_filter = QComboBox()
        self.type_filter.setObjectName("MarketTypeFilter")
        self.type_filter.setMinimumWidth(180)
        self.type_filter.view().setMinimumWidth(220)
        self.type_filter.addItems(["All", "Stock", "Commodity", "Crypto", "Funds and ETFs", "Derivatives", "Index", "Watchlist"])
        self.type_filter.currentTextChanged.connect(self._asset_type_changed)

        self.region_filter = QComboBox()
        self.region_filter.setObjectName("MarketRegionFilter")
        self.region_filter.setMinimumWidth(180)
        self.region_filter.view().setMinimumWidth(340)
        self.region_filter.currentTextChanged.connect(self.apply_filters)
        self.group_filter = QComboBox()
        self.group_filter.setObjectName("MarketSectorFilter")
        self.group_filter.setMinimumWidth(180)
        self.group_filter.view().setMinimumWidth(320)
        self.group_filter.currentTextChanged.connect(self.apply_filters)
        self._populate_filter_options()

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.type_filter, 0)
        toolbar.addWidget(self.region_filter, 0)
        toolbar.addWidget(self.group_filter, 0)
        return toolbar

    def _build_content_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        table = self._build_market_table()
        self.chart_panel = AssetChartPanel(self.state)
        self.chart_panel.setMinimumWidth(360)
        self.chart_panel.setMaximumWidth(720)
        self.chart_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        if self.trade_handler is not None:
            self.chart_panel.trade_requested.connect(self.trade_handler)
        self.chart_panel.chart_request_changed.connect(self._refresh_preview_history)
        splitter.addWidget(table)
        splitter.addWidget(self.chart_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([1040, 560])
        if self.proxy_model.rowCount() > 0:
            self._select_ticker(None, redraw_chart=True)
        return splitter

    def _build_market_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("MarketTable")
        self.market_table = table
        table.setModel(self.proxy_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.setMinimumWidth(500)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._apply_market_table_column_widths(table)
        table.horizontalHeader().setSortIndicatorShown(True)
        optimize_table_view(table, row_height=34)
        table.selectionModel().currentRowChanged.connect(self._show_index)
        table.doubleClicked.connect(self._open_asset_detail)
        return table

    def _apply_market_table_column_widths(self, table: QTableView) -> None:
        widths = {
            0: 34,
            1: 88,
            2: 210,
            3: 92,
            4: 84,
            5: 170,
            6: 104,
            7: 92,
            8: 132,
        }
        header = table.horizontalHeader()
        for column, width in widths.items():
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(column, width)

    def _show_index(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if current.isValid():
            source_index = self.proxy_model.mapToSource(current)
            self.live_chart_ticker = self.model.rows[source_index.row()]["ticker"]
        self._show_index_with_chart_mode(current, redraw_chart=True)

    def _show_index_with_chart_mode(self, current: QModelIndex, *, redraw_chart: bool) -> None:
        if not current.isValid():
            return
        source_index = self.proxy_model.mapToSource(current)
        if source_index.row() < 0 or source_index.row() >= len(self.model.rows):
            return
        row = self.model.rows[source_index.row()]
        if self.chart_panel is None:
            return
        self.chart_panel.update_asset(
            row["ticker"],
            row["asset_type"],
            self._data_with_history(row, redraw_chart=redraw_chart, panel=self.chart_panel),
            redraw_chart=redraw_chart,
        )

    def _open_stock_detail(self, current: QModelIndex) -> None:
        self._open_asset_detail(current)

    def _open_asset_detail(self, current: QModelIndex) -> None:
        if not current.isValid():
            return
        source_index = self.proxy_model.mapToSource(current)
        if source_index.row() < 0 or source_index.row() >= len(self.model.rows):
            return
        row = self.model.rows[source_index.row()]
        if row["asset_type"] not in {"Stock", "Commodity", "Crypto", "Fund", "Index", "Derivative"}:
            return
        detail_view = self.stock_detail_view
        detail_view.update_asset(
            row["ticker"],
            self._data_with_history(row, redraw_chart=True, panel=detail_view),
            row["asset_type"],
            self.state,
        )
        self.pages.setCurrentWidget(detail_view)

    def _show_market_list(self) -> None:
        self.pages.setCurrentWidget(self.main_page)

    def refresh(
        self,
        state: GameState,
        *,
        throttle_charts: bool = False,
        preserve_live_history: bool = True,
    ) -> None:
        selected_ticker = self._selected_ticker()
        if preserve_live_history:
            self._merge_local_history_into_state(state)
        self.state = state
        if self.chart_panel is not None:
            self.chart_panel.set_state(state)
        self.watchlist = self._build_watchlist()
        if self.market_table is not None:
            self.market_table.setUpdatesEnabled(False)
        try:
            shape_changed = self.model.refresh(state, self.watchlist, emit_changes=False)
            self._populate_filter_options(preserve_current=True)
            if shape_changed:
                self.proxy_model.refilter(keep_loaded=True)
                self.apply_filters()
            else:
                self._emit_visible_market_rows()
            should_redraw_chart = (
                selected_ticker is not None
                and selected_ticker == self.live_chart_ticker
                and not throttle_charts
                and (self.type_filter is None or self.type_filter.currentText() != "Funds and ETFs")
            )
            self._select_ticker(selected_ticker, redraw_chart=should_redraw_chart)
            if (
                self._stock_detail_view is not None
                and self.pages.currentWidget() is self._stock_detail_view
                and self._stock_detail_view.ticker
            ):
                source_row = self.model.row_for_ticker(self._stock_detail_view.ticker)
                row = self.model.rows[source_row]
                if row["asset_type"] in {"Stock", "Commodity", "Crypto", "Fund", "Index", "Derivative"}:
                    self._stock_detail_view.update_asset(
                        row["ticker"],
                        self._data_with_history(
                            row,
                            redraw_chart=not throttle_charts,
                            panel=self._stock_detail_view,
                        ),
                        row["asset_type"],
                        self.state,
                        redraw_chart=not throttle_charts,
                    )
        finally:
            if self.market_table is not None:
                self.market_table.setUpdatesEnabled(True)

    def apply_live_quotes(self, quotes: list[dict], *, date_text: str | None = None) -> None:
        selected_ticker = self._selected_ticker()
        live_date = date_text or self.state.date.isoformat()
        self._append_live_history(quotes, live_date)
        for quote in quotes:
            self.history_cache.update_live(
                str(quote.get("asset_type", "")),
                str(quote.get("ticker", "")),
                (float(quote.get("price", 0.0)), live_date, "Live"),
            )
        changed_rows = self.model.apply_quote_rows(quotes, self.watchlist)
        if changed_rows:
            self._emit_visible_market_rows()
        if selected_ticker and self.pages.currentWidget() is self.main_page:
            source_row = self.model.row_for_ticker(selected_ticker)
            row = self.model.rows[source_row]
            if self.chart_panel is not None:
                self.chart_panel.update_live_quote(
                    self._data_with_history(row, redraw_chart=False, panel=self.chart_panel)
                )
        if (
            self._stock_detail_view is not None
            and self.pages.currentWidget() is self._stock_detail_view
            and self._stock_detail_view.ticker
        ):
            source_row = self.model.row_for_ticker(self._stock_detail_view.ticker)
            row = self.model.rows[source_row]
            self._stock_detail_view.update_live_quote(
                self._data_with_history(row, redraw_chart=False, panel=self._stock_detail_view),
                self.state,
            )

    def _append_live_history(self, quotes: list[dict], date_text: str) -> None:
        for quote in quotes:
            asset_type = str(quote.get("asset_type", ""))
            ticker = str(quote.get("ticker", ""))
            source_row = self.model.row_for_asset(ticker, asset_type)
            if source_row < 0 or source_row >= len(self.model.rows):
                continue
            row = self.model.rows[source_row]
            if row["ticker"] != ticker or row["asset_type"] != asset_type:
                continue
            point = (float(quote.get("price", 0.0)), date_text, "Live")
            history = row["data"].setdefault("historie", [])
            history[:] = merge_history_by_date(history, [point])[-UI_HISTORY_LIMIT:]

    def _merge_local_history_into_state(self, state: GameState) -> None:
        books = {
            "Stock": state.stocks,
            "Commodity": state.commodities,
            "Crypto": state.cryptos,
            "Fund": state.funds,
            "Index": state.indices,
            "Derivative": state.derivatives,
        }
        for row in self.model.rows:
            target = books.get(row["asset_type"], {}).get(row["ticker"])
            if target is None:
                continue
            snapshot_history = list(target.get("historie", []))
            local_history = list(row["data"].get("historie", []))
            target["historie"] = merge_history_by_date(
                snapshot_history, local_history
            )[-UI_HISTORY_LIMIT:]

    def _selected_ticker(self) -> str | None:
        if self.market_table is None:
            return None
        current = self.market_table.currentIndex()
        if not current.isValid():
            return None
        source = self.proxy_model.mapToSource(current)
        return self.model.rows[source.row()]["ticker"]

    def _select_ticker(self, ticker: str | None, *, redraw_chart: bool = True) -> None:
        if self.market_table is None or self.proxy_model.rowCount() == 0:
            return
        current = self.market_table.currentIndex()
        if current.isValid() and self._selected_ticker() == ticker:
            self._show_index_with_chart_mode(current, redraw_chart=redraw_chart)
            return
        source_row = self.model.row_for_ticker(ticker)
        proxy_index = self.proxy_model.mapFromSource(self.model.index(source_row, 0))
        if not proxy_index.isValid():
            proxy_index = self.proxy_model.index(0, 0)
        selection_model = self.market_table.selectionModel()
        selection_model.blockSignals(True)
        self.market_table.selectRow(proxy_index.row())
        selection_model.blockSignals(False)
        self._show_index_with_chart_mode(proxy_index, redraw_chart=redraw_chart)

    def _data_with_history(self, row: dict, *, redraw_chart: bool, panel=None) -> dict:
        data = row["data"]
        range_points = int(getattr(panel, "range_points", 132))
        local_history = merge_history_by_date(list(data.get("historie", [])))
        if range_points > 0:
            # Recent ranges are part of the bounded world snapshot. They must not
            # depend on the optional UI cache or a Deep-History roundtrip.
            self._active_history_key = None
            history = local_history[-range_points:]
            cached = None
            requested = False
        else:
            # ALL paints local history first. The worker may then supply older
            # Deep History without clearing the already-visible series.
            key = history_key(row["asset_type"], row["ticker"], range_points)
            self._active_history_key = key
            cached = self.history_cache.get(key)
            history = merge_history_by_date(list(cached or []), local_history)
            requested = self.history_provider is not None and redraw_chart
            if requested:
                fresh = self.history_provider(
                    row["asset_type"], row["ticker"], point_budget(range_points)
                )
                if fresh:
                    history = merge_history_by_date(list(fresh), history, local_history)
                    self.history_cache.put(key, history)
        enriched = dict(data)
        if history:
            enriched["historie"] = history
        enriched["_history_loading"] = (
            range_points <= 0 and not bool(history) and self.history_provider is not None
        )
        enriched["_history_refreshing"] = bool(history) and requested
        enriched["_history_cache_hit"] = cached is not None
        return enriched

    def apply_history_response(self, key: ChartHistoryKey, history: list) -> bool:
        """Accept a background result without letting an obsolete selection replace the chart."""

        source_row = self.model.row_for_asset(key.ticker, key.asset_type)
        row = self.model.rows[source_row]
        local_history = list(row["data"].get("historie", []))
        self.history_cache.put(key, merge_history_by_date(history, local_history))
        if key != self._active_history_key:
            return False
        if self.pages.currentWidget() is self._stock_detail_view and self._stock_detail_view is not None:
            self._refresh_detail_history()
        else:
            self._refresh_preview_history()
        return True

    def _refresh_preview_history(self) -> None:
        if self.market_table is None:
            return
        current = self.market_table.currentIndex()
        if current.isValid():
            self._show_index_with_chart_mode(current, redraw_chart=True)

    def _refresh_detail_history(self) -> None:
        if self._stock_detail_view is None or not self._stock_detail_view.ticker:
            return
        source_row = self.model.row_for_ticker(self._stock_detail_view.ticker)
        row = self.model.rows[source_row]
        self._stock_detail_view.update_asset(
            row["ticker"],
            self._data_with_history(row, redraw_chart=True, panel=self._stock_detail_view),
            row["asset_type"],
            self.state,
        )

    def apply_filters(self, _value: object = None, *, restore_sort: bool = True) -> None:
        if self.search_input is None or self.type_filter is None or self.region_filter is None or self.group_filter is None:
            return
        changed = self.proxy_model.set_filters(
            self.search_input.text(),
            self._selected_asset_type(),
            str(self.region_filter.currentData()),
            str(self.group_filter.currentData()),
        )
        self.model.set_price_header("Points" if self.type_filter.currentText() == "Index" else "Price")
        self.model.set_market_cap_header(_market_cap_header_for_asset_filter(self.type_filter.currentText()))
        if not restore_sort or not changed:
            return
        sort_section, sort_order = self._current_sort()
        self._restore_sort(sort_section, sort_order)

    def _current_sort(self) -> tuple[int, Qt.SortOrder]:
        if self.market_table is None:
            return -1, Qt.SortOrder.AscendingOrder
        header = self.market_table.horizontalHeader()
        return header.sortIndicatorSection(), header.sortIndicatorOrder()

    def _restore_sort(self, section: int, order: Qt.SortOrder) -> None:
        if section < 0:
            return
        self.proxy_model.sort(section, order)

    def _emit_visible_market_rows(self) -> None:
        if self.market_table is None:
            self.model.emit_price_rows(range(len(self.model.rows)))
            return
        viewport = self.market_table.viewport()
        first_proxy_row = self.market_table.rowAt(0)
        last_proxy_row = self.market_table.rowAt(max(0, viewport.height() - 1))
        first_proxy_row = max(first_proxy_row, 0)
        if last_proxy_row < 0:
            visible_rows = max(1, viewport.height() // self.market_table.verticalHeader().defaultSectionSize())
            last_proxy_row = min(self.proxy_model.rowCount() - 1, first_proxy_row + visible_rows)
        source_rows = self.proxy_model.source_rows_for_proxy_range(first_proxy_row, last_proxy_row)
        self.model.emit_price_rows(source_rows)

    def _build_watchlist(self) -> set[str]:
        preferred = ["XAU", "CL"]
        preferred.extend(list(self.state.cryptos)[:2])
        preferred.extend(list(self.state.stocks)[:3])
        asset_books = [self.state.stocks, self.state.commodities, self.state.cryptos, self.state.funds, self.state.indices, self.state.derivatives]
        ticker_counts = {
            ticker: sum(1 for assets in asset_books if ticker in assets)
            for ticker in preferred
        }
        return {ticker for ticker in preferred if ticker_counts[ticker] == 1}

    def _selected_asset_type(self) -> str:
        if self.type_filter is None:
            return "All"
        label = self.type_filter.currentText()
        if label == "Funds and ETFs":
            return "Fund"
        if label == "Derivatives":
            return "Derivative"
        return label

    def _asset_type_changed(self) -> None:
        self._populate_filter_options()
        self.apply_filters()

    def _populate_filter_options(self, *, preserve_current: bool = False) -> None:
        if self.type_filter is None or self.region_filter is None or self.group_filter is None:
            return
        current_region = self.region_filter.currentData() if preserve_current else None
        current_group = self.group_filter.currentData() if preserve_current else None
        asset_type = self._selected_asset_type()
        region_options = [("All Regions", "All Regions")]
        region_options.extend((display_label(region), region) for region in self._region_values(asset_type))
        group_options = [("All Groups", "All Groups")]
        group_options.extend(self._group_options(asset_type))
        self._replace_combo_options(self.region_filter, region_options, current_region)
        self._replace_combo_options(self.group_filter, group_options, current_group)

    def _replace_combo_options(self, combo: QComboBox, options: list[tuple[str, str]], current: object) -> None:
        combo.blockSignals(True)
        combo.clear()
        for text, value in options:
            combo.addItem(text, value)
        values = [value for _text, value in options]
        combo.setCurrentIndex(values.index(current) if current in values else 0)
        combo.blockSignals(False)

    def _region_values(self, asset_type: str) -> list[str]:
        if asset_type in {"All", "Watchlist"}:
            values = {row["region"] for row in self.model.rows if row["region"]}
        else:
            values = {row["region"] for row in self.model.rows if row["asset_type"] == asset_type and row["region"]}
        ordered = [region for region in self.state.macro if region in values]
        extras = sorted(values - set(ordered))
        return ordered + extras

    def _group_options(self, asset_type: str) -> list[tuple[str, str]]:
        rows = self.model.rows if asset_type in {"All", "Watchlist"} else [
            row for row in self.model.rows if row["asset_type"] == asset_type
        ]
        groups = sorted({row["filter_group"] for row in rows if row["filter_group"]})
        return [(display_label(group), group) for group in groups]


def _market_cap_header_for_asset_filter(label: str) -> str:
    if label == "Funds and ETFs":
        return "AUM"
    if label == "Derivatives":
        return "Open Interest"
    return "Market Cap"
