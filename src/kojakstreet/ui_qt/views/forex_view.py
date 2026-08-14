"""Forex workspace view."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from kojakstreet.core.countries import CURRENCY_CODES, RESERVE_CURRENCY, RESERVE_CURRENCY_CODE
from kojakstreet.core.forex import ForexPair, currency_code
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.formatters import percent
from kojakstreet.ui_qt.models.forex_table_model import (
    ForexFilterProxyModel,
    ForexTableModel,
    build_forex_rows,
)
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.widgets.qt_chart import FastChartView
from kojakstreet.ui_qt.widgets.stock_detail_dialog import StockDetailView
from kojakstreet.ui_qt.widgets.view_header import ViewHeader


class ForexView(QFrame):
    def __init__(
        self,
        state: GameState,
        forex_handler: Callable[[str, str, float], None] | None = None,
        history_provider: Callable[[str, int], list[float]] | None = None,
        current_provider: Callable[[], list[dict[str, object]]] | None = None,
    ) -> None:
        super().__init__()
        self.state = state
        self.forex_handler = forex_handler
        self.history_provider = history_provider
        self.current_provider = current_provider
        self.pair_rows = self._current_pair_rows() or build_forex_rows(state)
        self.pairs = [row["pair"] for row in self.pair_rows]
        self.table: QTableView | None = None
        self.search_input: QLineEdit | None = None
        self.pair_filter: QComboBox | None = None
        self.source_currency: QComboBox | None = None
        self.target_currency: QComboBox | None = None
        self.trade_amount: QLineEdit | None = None
        self.trade_preview: QLabel | None = None
        self.kpi_values: dict[str, QLabel] = {}
        self.model = ForexTableModel(state)
        self.model.refresh_rows(self.pair_rows)
        self.proxy_model = ForexFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.sort_section = -1
        self.sort_order = Qt.SortOrder.AscendingOrder
        self.chart_panel = ForexChartPanel()
        self.pages = QStackedWidget()
        self.main_page = QWidget()
        self.pair_detail_view = StockDetailView()
        self.pair_detail_view.back_requested.connect(self._show_forex_list)
        self.setObjectName("Panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        main_layout = QVBoxLayout(self.main_page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)
        layout.addWidget(
            ViewHeader(
                "Forex",
                "Currency conversion pairs, relative strength and exchange-rate history",
                ["Convert", "Export"],
            )
        )
        main_layout.addLayout(self._build_kpis())
        main_layout.addLayout(self._build_toolbar())
        main_layout.addWidget(self._build_trade_panel())
        main_layout.addWidget(self._build_content(), 1)
        self.pages.addWidget(self.main_page)
        self.pages.addWidget(self.pair_detail_view)
        layout.addWidget(self.pages, 1)

    def _build_kpis(self) -> QGridLayout:
        row = QGridLayout()
        row.setHorizontalSpacing(12)
        row.setVerticalSpacing(10)
        for label, value in self._strength_items():
            index = len(self.kpi_values)
            row.addWidget(self._kpi(label, value), index // 10, index % 10)
        for column in range(10):
            row.setColumnStretch(column, 1)
        return row

    def _kpi(self, label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("KpiCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        caption = QLabel(label.upper())
        caption.setObjectName("Muted")
        main = QLabel(value)
        main.setObjectName("DetailValue")
        self.kpi_values[label] = main
        layout.addWidget(caption)
        layout.addWidget(main)
        return frame

    def _strength_items(self) -> list[tuple[str, str]]:
        strengths = self.state.currency_strength
        reference = _state_currency_strength(self.state, RESERVE_CURRENCY)
        regions = [region for region in strengths if region != RESERVE_CURRENCY]
        items = []
        for region in regions:
            relative = (_state_currency_strength(self.state, region) / reference - 1.0) * 100.0
            items.append((currency_code(region), f"{relative:+.2f}%"))
        return items

    def _refresh_kpis(self) -> None:
        current = dict(self._strength_items())
        for label, value in current.items():
            if label in self.kpi_values:
                self.kpi_values[label].setText(value)
                numeric = float(value.rstrip("%"))
                self.kpi_values[label].setStyleSheet(f"color: {'#14b8a6' if numeric >= 0 else '#f43f5e'};")

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("ForexSearchInput")
        self.search_input.setPlaceholderText("Search pair, base or quote currency")
        self.search_input.textChanged.connect(self.apply_filters)

        self.pair_filter = QComboBox()
        self.pair_filter.setObjectName("ForexPairFilter")
        self.pair_filter.setMinimumWidth(150)
        self.pair_filter.view().setMinimumWidth(180)
        self._populate_pair_filter()
        self.pair_filter.currentTextChanged.connect(self.apply_filters)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.pair_filter)
        return toolbar

    def _build_trade_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PanelInner")
        row = QHBoxLayout(panel)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)

        self.source_currency = QComboBox()
        self.source_currency.setObjectName("ForexSourceCurrency")
        self.source_currency.setMinimumWidth(110)
        self.target_currency = QComboBox()
        self.target_currency.setObjectName("ForexTargetCurrency")
        self.target_currency.setMinimumWidth(110)
        options = self._currency_options()
        self.source_currency.addItems(options)
        self.target_currency.addItems(options)
        self.source_currency.setCurrentText("GLD" if "GLD" in options else options[0])
        target_default = next((option for option in options if option != self.source_currency.currentText()), options[0])
        self.target_currency.setCurrentText(target_default)
        self.trade_amount = QLineEdit()
        self.trade_amount.setObjectName("ForexTradeAmount")
        self.trade_amount.setPlaceholderText("Amount")
        self.trade_preview = QLabel("Receive -")
        self.trade_preview.setObjectName("DetailValue")
        execute_button = QPushButton("Exchange")
        execute_button.setObjectName("ActionButton")
        execute_button.clicked.connect(self._execute_currency_trade)

        self.source_currency.currentTextChanged.connect(self._update_trade_preview)
        self.target_currency.currentTextChanged.connect(self._update_trade_preview)
        self.trade_amount.textChanged.connect(self._update_trade_preview)

        row.addWidget(QLabel("From"))
        row.addWidget(self.source_currency)
        row.addWidget(QLabel("To"))
        row.addWidget(self.target_currency)
        row.addWidget(self.trade_amount)
        row.addWidget(self.trade_preview, 1)
        row.addWidget(execute_button)
        self._update_trade_preview()
        return panel

    def _execute_currency_trade(self) -> None:
        if self.forex_handler is None:
            return
        amount = self._trade_amount_value()
        if amount <= 0 or self.source_currency is None or self.target_currency is None:
            return
        source = _region_from_currency_code(self.source_currency.currentText())
        target = _region_from_currency_code(self.target_currency.currentText())
        self.forex_handler(source, target, amount)

    def _trade_amount_value(self) -> float:
        if self.trade_amount is None:
            return 0.0
        try:
            return float(self.trade_amount.text().replace(",", "."))
        except ValueError:
            return 0.0

    def _update_trade_preview(self) -> None:
        if self.source_currency is None or self.target_currency is None or self.trade_preview is None:
            return
        amount = self._trade_amount_value()
        source = _region_from_currency_code(self.source_currency.currentText())
        target = _region_from_currency_code(self.target_currency.currentText())
        received = amount * (_state_currency_strength(self.state, source) / _state_currency_strength(self.state, target))
        if amount > 0 and source != target:
            self.trade_preview.setText(f"Receive {received:,.2f} {self.target_currency.currentText()}")
        elif source == target:
            self.trade_preview.setText("Receive -")
        else:
            self.trade_preview.setText("Receive -")

    def _currency_options(self) -> list[str]:
        regions = set(self.state.currency_strength) | set(self.state.fx_balances) | {"GD"}
        return sorted({_currency_display_code(region) for region in regions})

    def _build_content(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self.chart_panel)
        splitter.setSizes([760, 430])
        return splitter

    def _build_table(self) -> QTableView:
        table = QTableView()
        self.table = table
        table.setObjectName("ForexTable")
        table.setModel(self.proxy_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSortIndicatorShown(True)
        optimize_table_view(table, row_height=34)
        table.horizontalHeader().sectionClicked.connect(self._sort_by_column)

        table.selectionModel().currentRowChanged.connect(self._show_index)
        table.doubleClicked.connect(self._open_pair_detail)
        self.apply_filters()
        if self.proxy_model.rowCount() > 0:
            self._select_pair(None)
        return table

    def _show_index(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        source_index = self.proxy_model.mapToSource(current)
        if source_index.row() < 0 or source_index.row() >= len(self.model.rows):
            return
        pair = self.model.rows[source_index.row()]["pair"]
        if isinstance(pair, ForexPair):
            self.chart_panel.update_pair(self._pair_with_history(pair))

    def _open_pair_detail(self, current: QModelIndex) -> None:
        pair = self._pair_from_index(current)
        if pair is None:
            return
        self.pair_detail_view.update_asset(
            pair.pair,
            {
                "name": f"{pair.base} / {pair.quote}",
                "historie": [(value, "", "") for value in self._pair_history(pair)],
                "kurs": pair.rate,
                "aenderung": pair.change_percent,
            },
            "Forex",
        )
        self.pages.setCurrentWidget(self.pair_detail_view)

    def _show_forex_list(self) -> None:
        self.pages.setCurrentWidget(self.main_page)

    def refresh(self, state: GameState, *, throttle_charts: bool = False) -> None:
        selected_pair = self._selected_pair()
        self.state = state
        self.pair_rows = self._current_pair_rows() or build_forex_rows(state)
        self.pairs = [row["pair"] for row in self.pair_rows]
        if self.table is None:
            return
        self._refresh_kpis()
        self._populate_pair_filter()
        self.model.refresh_rows(self.pair_rows)
        self.apply_filters()
        self._restore_sort(self.sort_section, self.sort_order)
        self._select_pair(selected_pair, redraw_chart=not throttle_charts)
        self._update_trade_preview()
        if not throttle_charts and self.pages.currentWidget() is self.pair_detail_view and self.pair_detail_view.ticker:
            pair = self._pair_by_name(self.pair_detail_view.ticker)
            if pair is not None:
                self.pair_detail_view.update_asset(
                    pair.pair,
                    {
                        "name": f"{pair.base} / {pair.quote}",
                        "historie": [(value, "", "") for value in self._pair_history(pair)],
                        "kurs": pair.rate,
                        "aenderung": pair.change_percent,
                    },
                    "Forex",
                )

    def apply_live_current_rows(self, rows: list[dict[str, object]]) -> None:
        if not rows or self.table is None:
            return
        selected_pair = self._selected_pair()
        self.pair_rows = self._rows_from_current(rows)
        self.pairs = [row["pair"] for row in self.pair_rows]
        self.model.refresh_rows(self.pair_rows)
        self.apply_filters()
        self._restore_sort(self.sort_section, self.sort_order)
        self._select_pair(selected_pair, redraw_chart=False)
        self._update_trade_preview()
        if self.pages.currentWidget() is self.pair_detail_view and self.pair_detail_view.ticker:
            pair = self._pair_by_name(self.pair_detail_view.ticker)
            if pair is not None:
                self.pair_detail_view.update_asset(
                    pair.pair,
                    {
                        "name": f"{pair.base} / {pair.quote}",
                        "historie": [(value, "", "") for value in self._pair_history(pair)],
                        "kurs": pair.rate,
                        "aenderung": pair.change_percent,
                    },
                    "Forex",
                )

    def _current_pair_rows(self) -> list[dict]:
        if self.current_provider is None:
            return []
        return self._rows_from_current(self.current_provider())

    def _rows_from_current(self, rows: list[dict[str, object]]) -> list[dict]:
        pair_rows = []
        for row in rows:
            raw_pair = str(row.get("pair", ""))
            base = currency_code(str(row.get("base", "")))
            quote = currency_code(str(row.get("quote", "")))
            if not raw_pair or not base or not quote:
                continue
            pair = ForexPair(
                pair=f"{base}/{quote}",
                base=base,
                quote=quote,
                rate=float(row.get("rate", 0.0)),
                change_percent=float(row.get("change", 0.0)),
                history=[],
                source_pair=raw_pair,
            )
            pair_rows.append(
                {
                    "pair": pair,
                    "search": f"{pair.pair} {pair.base} {pair.quote}".lower(),
                    "values": [pair.pair, pair.base, pair.quote, f"{pair.rate:.6f}", percent(pair.change_percent)],
                    "sort_values": [pair.pair, pair.base, pair.quote, pair.rate, pair.change_percent],
                }
            )
        return pair_rows

    def _selected_pair(self) -> str | None:
        if self.table is None:
            return None
        current = self.table.currentIndex()
        pair = self._pair_from_index(current)
        return pair.pair if pair is not None else None

    def _pair_from_index(self, current: QModelIndex) -> ForexPair | None:
        if not current.isValid():
            return None
        source_index = self.proxy_model.mapToSource(current)
        if source_index.row() < 0 or source_index.row() >= len(self.model.rows):
            return None
        pair = self.model.rows[source_index.row()]["pair"]
        return pair if isinstance(pair, ForexPair) else None

    def _pair_by_name(self, pair_name: str) -> ForexPair | None:
        for row in self.model.rows:
            pair = row["pair"]
            if isinstance(pair, ForexPair) and pair.pair == pair_name:
                return pair
        return None

    def _select_pair(self, pair_name: str | None, *, redraw_chart: bool = True) -> None:
        if self.table is None or self.proxy_model.rowCount() == 0:
            return
        target_proxy = self.proxy_model.index(0, 0)
        for source_row, row in enumerate(self.model.rows):
            if row["pair"].pair == pair_name:
                candidate = self.proxy_model.mapFromSource(self.model.index(source_row, 0))
                if candidate.isValid():
                    target_proxy = candidate
                break
        selection_model = self.table.selectionModel()
        selection_model.blockSignals(True)
        self.table.selectRow(target_proxy.row())
        selection_model.blockSignals(False)
        if redraw_chart:
            self._show_index(target_proxy, QModelIndex())

    def _pair_with_history(self, pair: ForexPair) -> ForexPair:
        history = self._pair_history(pair)
        if history == pair.history:
            return pair
        return ForexPair(
            pair=pair.pair,
            base=pair.base,
            quote=pair.quote,
            rate=pair.rate,
            change_percent=pair.change_percent,
            history=history,
            source_pair=pair.source_pair,
        )

    def _pair_history(self, pair: ForexPair) -> list[float]:
        if self.history_provider is not None:
            history = self.history_provider(pair.source_pair or pair.pair, 520)
            if history:
                return history
        return pair.history

    def apply_filters(self, _value: object = None) -> None:
        if self.table is None or self.search_input is None or self.pair_filter is None:
            return
        pair_group = self.pair_filter.currentText()
        self.model.set_pair_group(pair_group)
        changed = self.proxy_model.set_filters(self.search_input.text(), pair_group)
        if changed:
            self.sort_section = -1
            self.proxy_model.sort(-1)
            self._select_pair(None)

    def _populate_pair_filter(self) -> None:
        if self.pair_filter is None:
            return
        current = self.pair_filter.currentText() or "GLD Pairs"
        currencies = sorted({pair.base for pair in self.pairs} | {pair.quote for pair in self.pairs})
        options = ["GLD Pairs", "All Pairs", *[f"{currency} Pairs" for currency in currencies if currency != "GLD"]]
        self.pair_filter.blockSignals(True)
        self.pair_filter.clear()
        self.pair_filter.addItems(options)
        self.pair_filter.setCurrentText(current if current in options else "GLD Pairs")
        self.pair_filter.blockSignals(False)

    def _sort_by_column(self, section: int) -> None:
        if self.sort_section == section and self.sort_order == Qt.SortOrder.AscendingOrder:
            self.sort_order = Qt.SortOrder.DescendingOrder
        else:
            self.sort_section = section
            self.sort_order = Qt.SortOrder.AscendingOrder
        self._restore_sort(self.sort_section, self.sort_order)

    def _restore_sort(self, section: int, order: Qt.SortOrder) -> None:
        if section < 0:
            return
        if self.table is not None:
            self.table.horizontalHeader().setSortIndicator(section, order)
        self.proxy_model.sort(section, order)


class ForexChartPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("PanelInner")
        self.range_points = 132
        self.chart_mode = "Line"
        self.last_candle_count = 0
        self.last_candle_interval = "Daily"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        self.title = QLabel("Select a pair")
        self.title.setObjectName("SectionTitle")
        self.meta = QLabel("Exchange-rate history")
        self.meta.setObjectName("Muted")
        self.chart_view = FastChartView(title="Exchange Rate")
        control_bar = QHBoxLayout()
        control_bar.setSpacing(6)
        self.range_buttons: list[QPushButton] = []
        self.range_button_group = QButtonGroup(self)
        self.range_button_group.setExclusive(True)
        for label, points in [("1M", 22), ("6M", 132), ("1Y", 264), ("ALL", 0)]:
            button = QPushButton(label)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setChecked(label == "6M")
            button.clicked.connect(lambda _checked=False, value=points: self.set_range(value))
            self.range_button_group.addButton(button)
            self.range_buttons.append(button)
            control_bar.addWidget(button)

        self.mode_buttons: list[QPushButton] = []
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        for label in ["Line", "Candle"]:
            button = QPushButton(label)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setChecked(label == "Line")
            button.clicked.connect(lambda _checked=False, mode=label: self.set_chart_mode(mode))
            self.mode_button_group.addButton(button)
            self.mode_buttons.append(button)
            control_bar.addWidget(button)
        control_bar.addStretch(1)
        layout.addWidget(self.title)
        layout.addWidget(self.meta)
        layout.addLayout(control_bar)
        layout.addWidget(self.chart_view, 1)
        self.current_pair: ForexPair | None = None

    def set_range(self, points: int) -> None:
        self.range_points = points
        for button, button_points in zip(self.range_buttons, [22, 132, 264, 0], strict=True):
            button.setChecked(button_points == points)
        if self.current_pair is not None:
            self.update_pair(self.current_pair)

    def set_chart_mode(self, mode: str) -> None:
        self.chart_mode = mode
        for button in self.mode_buttons:
            button.setChecked(button.text() == mode)
        if self.current_pair is not None:
            self.update_pair(self.current_pair)

    def update_pair(self, pair: ForexPair) -> None:
        self.current_pair = pair
        self.last_candle_count = 0
        self.title.setText(pair.pair)
        self.meta.setText(f"{pair.base} into {pair.quote} | {pair.rate:.6f} | {percent(pair.change_percent)}")
        points = pair.history
        if self.range_points and len(points) > self.range_points:
            points = points[-self.range_points :]
        if len(points) >= 2:
            color = "#14b8a6" if points[-1] >= points[0] else "#f43f5e"
            if self.chart_mode == "Candle":
                self.chart_view.plot_candles(points, range_points=self.range_points, title="Exchange Rate")
                self.last_candle_count = self.chart_view.last_candle_count
                self.last_candle_interval = self.chart_view.last_candle_interval
            else:
                self.chart_view.plot_line(points, color=color, title="Exchange Rate", label=pair.pair)
        else:
            self.chart_view.show_message("Forex history builds as the simulation runs")


def _currency_display_code(region: str) -> str:
    return currency_code(region)
    return {
        "USA": "USD",
        "EU": "EUR",
        "Großbritannien": "GBP",
        "GroÃŸbritannien": "GBP",
        "China": "RMB",
        "Japan": "JPY",
        "GD": "GLD",
    }.get(region, region)


def _region_from_currency_code(code: str) -> str:
    if code == RESERVE_CURRENCY_CODE:
        return RESERVE_CURRENCY
    reverse_codes = {value: key for key, value in CURRENCY_CODES.items()}
    return reverse_codes.get(code, code)
    return {
        "USD": "USA",
        "EUR": "EU",
        "GBP": "Großbritannien",
        "RMB": "China",
        "JPY": "Japan",
        "GLD": "GD",
    }.get(code, code)


def _state_currency_strength(state: GameState, region: str) -> float:
    if region == RESERVE_CURRENCY:
        gold = state.commodities.get("XAU", {})
        return max(0.0001, float(gold.get("kurs", 100.0)) / 100.0)
    if region == "GD":
        gold = state.commodities.get("XAU", {})
        return max(0.0001, float(gold.get("kurs", 100.0)) / 100.0)
    return max(0.0001, float(state.currency_strength.get(region, 1.0)))
