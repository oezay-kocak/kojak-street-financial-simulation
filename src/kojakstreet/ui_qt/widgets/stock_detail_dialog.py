"""Expanded in-app stock detail view opened from the Markets table."""

from __future__ import annotations

from typing import Any, ClassVar

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableView,
    QTabWidget,
    QVBoxLayout,
)

from kojakstreet.core.commodities import ensure_commodity_fundamentals
from kojakstreet.core.cryptos import ensure_crypto_fundamentals
from kojakstreet.core.financial_products import (
    derivative_allows_future_trade,
    derivative_allows_spot_trade,
    derivative_pricing_note,
    derivative_use_case,
)
from kojakstreet.core.fundamentals import ema_values, ensure_stock_fundamentals
from kojakstreet.core.market_explanations import driver_summary
from kojakstreet.core.ohlc import history_close
from kojakstreet.core.production_chains import (
    PROCESSED_PRODUCTS,
    PRODUCT_NAME_TO_CODE,
    _input_requirements,
    commodity_definitions,
)
from kojakstreet.core.ratings import DEFAULT_RATING, default_probability, normalize_rating
from kojakstreet.core.state import GameState
from kojakstreet.core.trade_preview import validate_trade_request
from kojakstreet.ui_qt.chart_series import build_candles, history_date, merge_history_by_date
from kojakstreet.ui_qt.display import display_label, display_text
from kojakstreet.ui_qt.formatters import (
    compact_money,
    percent,
    regional_money,
    regional_money_precise,
)
from kojakstreet.ui_qt.models.simple_table_model import METADATA_ROLE, SimpleTableModel
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.widgets.qt_chart import FastChartView


class StockDetailView(QFrame):
    """Large broker-style stock detail sheet with fundamentals and EMA chart."""

    back_requested = Signal()
    trade_requested = Signal(str, str, str, float, int)
    chart_request_changed = Signal()
    SPOT_AND_PERPETUAL_ASSETS: ClassVar[set[str]] = {"Stock", "Commodity", "Crypto"}
    SPOT_ONLY_ASSETS: ClassVar[set[str]] = {"Fund", "Derivative"}

    def __init__(self, parent=None, state: GameState | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.ticker = ""
        self.asset_type = "Stock"
        self.data: dict[str, Any] = {}
        self.state = state
        self.legend_labels: list[str] = []
        self.selected_metric_history: list[float] | None = None
        self.selected_metric_label = ""
        self.range_points = 132
        self.chart_mode = "Line"
        self.enabled_indicators: set[int] = set()
        self.last_candle_count = 0
        self.last_candle_interval = "Daily"
        self.performance_label = QLabel("-")
        self.performance_label.setObjectName("DetailValue")
        self.current_price = 0.0
        self.yield_curve_terms: list[str] = []
        self.order_control_widgets = []
        self._suppress_supply_selection = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("ActionButton")
        self.back_button.clicked.connect(self.back_requested.emit)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self.title = QLabel("Select a stock")
        self.title.setObjectName("BrandTitle")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Muted")
        self.subtitle.setMinimumWidth(0)
        self.subtitle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        header.addWidget(self.back_button, 0)
        header.addLayout(title_box, 1)
        price_box = QVBoxLayout()
        price_box.setSpacing(2)
        self.header_price = QLabel("-")
        self.header_price.setObjectName("BrandTitle")
        self.header_price.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.header_change = QLabel("-")
        self.header_change.setObjectName("DetailValue")
        self.header_change.setAlignment(Qt.AlignmentFlag.AlignRight)
        price_box.addWidget(self.header_price)
        price_box.addWidget(self.header_change)
        header.addLayout(price_box)

        self.kpi_frame = QFrame()
        self.kpi_frame.setObjectName("PanelInner")
        self.kpi_grid = QGridLayout(self.kpi_frame)
        self.kpi_grid.setContentsMargins(12, 10, 12, 10)
        self.kpi_grid.setHorizontalSpacing(18)
        self.kpi_grid.setVerticalSpacing(10)
        self.kpi_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._fundamental_cards: list[QFrame] = []
        self._fundamental_card_columns = 0

        self.chart_view = FastChartView(title="Price History", legend=True)
        self.chart_view.setMinimumHeight(390)
        self.positioning_view = FastChartView(title="Long / Short Interest")
        self.positioning_view.setMinimumHeight(104)
        self.positioning_view.setMaximumHeight(132)
        self.detail_tabs = QTabWidget()
        self.detail_tabs.setObjectName("DetailTabs")
        self.detail_tabs.setMinimumWidth(0)
        self.detail_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.chart_tab = QFrame()
        self.chart_tab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        chart_layout = QVBoxLayout(self.chart_tab)
        chart_layout.setContentsMargins(0, 6, 0, 0)
        chart_layout.setSpacing(8)
        chart_layout.addLayout(self._build_chart_controls())
        chart_layout.addWidget(self.chart_view, 1)
        chart_layout.addWidget(self.positioning_view, 0)
        self.overview_tab = QFrame()
        self.overview_tab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        overview_layout = QVBoxLayout(self.overview_tab)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.addWidget(self.kpi_frame, 0, Qt.AlignmentFlag.AlignTop)
        overview_layout.addStretch(1)
        self.supply_table = QTableView()
        self.supply_table.setObjectName("CompanySupplyChainTable")
        self.supply_model = SimpleTableModel(
            ["Role", "Code", "Name", "Share", "Company Qty", "Supply", "Demand", "Inventories", "Shortage", "Pressure"],
            right_aligned_columns={3, 4, 5, 6, 7, 8, 9},
        )
        self.supply_table.setModel(self.supply_model)
        self.supply_table.verticalHeader().setVisible(False)
        self.supply_table.setAlternatingRowColors(True)
        self.supply_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.supply_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.supply_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.supply_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        optimize_table_view(self.supply_table, row_height=34)
        self.supply_table.selectionModel().selectionChanged.connect(lambda *_: self._draw_selected_supply_metric())
        self.supply_tab = QFrame()
        self.supply_tab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        supply_layout = QVBoxLayout(self.supply_tab)
        supply_layout.setContentsMargins(0, 0, 0, 0)
        supply_layout.addWidget(self.supply_table)
        self.detail_tabs.addTab(self.chart_tab, "Chart")
        self.detail_tabs.addTab(self.overview_tab, "Fundamentals")
        self.detail_tabs.addTab(self.supply_tab, "Supply Chain")
        self.detail_tabs.currentChanged.connect(self._detail_tab_changed)

        layout.addLayout(header)
        layout.addLayout(self._build_order_controls())
        layout.addWidget(self.detail_tabs, 1)

    def _build_chart_controls(self) -> QHBoxLayout:
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
        self.indicator_buttons: dict[int, QPushButton] = {}
        for period in (20, 50, 200):
            button = QPushButton(f"EMA {period}")
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setChecked(False)
            button.clicked.connect(
                lambda checked=False, value=period: self.set_indicator(value, bool(checked))
            )
            self.indicator_buttons[period] = button
            control_bar.addWidget(button)
        control_bar.addStretch(1)
        return control_bar

    def _build_order_controls(self) -> QHBoxLayout:
        control_bar = QHBoxLayout()
        control_bar.setSpacing(8)
        caption = QLabel("PERIOD")
        caption.setObjectName("Muted")
        self.order_control_widgets.append(caption)
        self.order_quantity = QLineEdit()
        self.order_quantity.setPlaceholderText("Qty")
        self.order_quantity.setMinimumWidth(110)
        self.order_quantity.setValidator(QDoubleValidator(0.0, 1_000_000_000.0, 4, self))
        self.order_quantity.textChanged.connect(self._update_order_value)
        self.order_total_value = QLabel("Total -")
        self.order_total_value.setObjectName("Muted")
        self.order_total_value.setMinimumWidth(210)
        self.order_total_value.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.order_leverage = QComboBox()
        self.order_leverage.setMinimumWidth(82)
        self.order_leverage.addItems(["1x", "2x", "3x", "4x", "5x"])
        self.order_leverage.currentTextChanged.connect(self._update_order_value)
        self.order_buttons: dict[str, QPushButton] = {}
        for label, side in [("Buy", "BUY"), ("Sell", "SELL"), ("Long", "LONG"), ("Short", "SHORT")]:
            button = QPushButton(label)
            button.setObjectName("ActionButton")
            button.clicked.connect(lambda _checked=False, value=side: self._emit_trade(value))
            self.order_buttons[side] = button
            self.order_control_widgets.append(button)
            control_bar.addWidget(button)
        control_bar.addStretch(1)
        control_bar.addWidget(caption)
        control_bar.addWidget(self.performance_label)
        control_bar.addWidget(self.order_quantity)
        control_bar.addWidget(self.order_total_value)
        control_bar.addWidget(self.order_leverage)
        self.order_control_widgets.extend(
            [self.performance_label, self.order_quantity, self.order_total_value, self.order_leverage]
        )
        return control_bar

    def _emit_trade(self, side: str) -> None:
        if not self.ticker or self.asset_type not in self.SPOT_AND_PERPETUAL_ASSETS | self.SPOT_ONLY_ASSETS:
            return
        quantity = self._order_quantity()
        if quantity <= 0:
            return
        leverage = self._selected_leverage()
        if side in {"BUY", "SELL"}:
            if not self._trade_is_valid(side, quantity):
                return
            self.trade_requested.emit(self.ticker, "SPOT", side, quantity, leverage)
        elif side in {"LONG", "SHORT"} and self.asset_type in self.SPOT_AND_PERPETUAL_ASSETS:
            margin = (quantity * self.current_price) / max(1, leverage)
            if not self._trade_is_valid(side, margin):
                return
            self.trade_requested.emit(self.ticker, "FUTURE", side, margin, leverage)

    def _order_quantity(self) -> float:
        try:
            return float(self.order_quantity.text().replace(",", "."))
        except ValueError:
            return 0.0

    def _selected_leverage(self) -> int:
        return int(self.order_leverage.currentText().replace("x", ""))

    def _update_order_value(self) -> None:
        quantity = self._order_quantity()
        notional = quantity * self.current_price
        margin = notional / max(1, self._selected_leverage())
        if notional > 0:
            total_text = f"Total {notional:,.2f}"
            if self.order_leverage.isVisible():
                leverage = max(1, self._selected_leverage())
                liq = self.current_price * (1.0 - 1.0 / leverage)
                total_text = f"{total_text} | Margin {margin:,.2f} | Liq {liq:,.2f}"
            contract_size = float(self.data.get("contract_size", 0.0) or 0.0)
            if contract_size > 0.0:
                total_text = f"{total_text} | Contract {contract_size:,.2f}"
            self.order_total_value.setText(total_text)
            self.order_total_value.setToolTip(total_text)
        else:
            self.order_total_value.setText("Total -")
            self.order_total_value.setToolTip("")
        self._update_trade_buttons(quantity, margin)

    def set_range(self, points: int) -> None:
        self.range_points = points
        for button, button_points in zip(self.range_buttons, [22, 132, 264, 0], strict=True):
            button.setChecked(button_points == points)
        if self.data:
            self._draw_chart()
            self.chart_request_changed.emit()

    def set_chart_mode(self, mode: str) -> None:
        self.chart_mode = mode
        for button in self.mode_buttons:
            button.setChecked(button.text() == mode)
        if self.data:
            self._draw_chart()
            self.chart_request_changed.emit()

    def set_indicator(self, period: int, enabled: bool) -> None:
        if enabled:
            self.enabled_indicators.add(int(period))
        else:
            self.enabled_indicators.discard(int(period))
        button = self.indicator_buttons.get(int(period))
        if button is not None:
            button.setChecked(bool(enabled))
        if self.data and self.detail_tabs.currentWidget() is self.chart_tab:
            self._draw_chart()

    def update_stock(self, ticker: str, data: dict[str, Any]) -> None:
        self.update_asset(ticker, data, "Stock")

    def update_commodity(self, ticker: str, data: dict[str, Any]) -> None:
        self.update_asset(ticker, data, "Commodity")

    def update_crypto(self, ticker: str, data: dict[str, Any]) -> None:
        self.update_asset(ticker, data, "Crypto")

    def update_asset(
        self,
        ticker: str,
        data: dict[str, Any],
        asset_type: str,
        state: GameState | None = None,
        *,
        redraw_chart: bool = True,
    ) -> None:
        previous_supply_identity = self._selected_supply_identity()
        previous_tab = self.detail_tabs.currentWidget()
        same_asset = ticker == self.ticker and asset_type == self.asset_type
        if state is not None:
            self.state = state
        self.asset_type = asset_type
        if asset_type == "Commodity":
            ensure_commodity_fundamentals(data)
        elif asset_type == "Crypto":
            ensure_crypto_fundamentals(data)
        elif asset_type == "Stock":
            ensure_stock_fundamentals(data)
        self.ticker = ticker
        self.data = data
        self.legend_labels = []
        self.yield_curve_terms = list(data.get("yield_curve_terms", []))
        if asset_type == "GlobalMacro":
            self.title.setText(display_text(data.get("name", ticker)))
        else:
            self.title.setText(f"{ticker}  {display_text(data.get('name', ticker))}")
        self.current_price = float(data.get("kurs", 0.0))
        change = float(data.get("aenderung", 0.0))
        region = str(data.get("land", data.get("ziel", "GD")))
        self.header_price.setText(regional_money_precise(self.current_price, region))
        self.header_change.setText(percent(change))
        self.header_change.setStyleSheet(f"color: {'#14b8a6' if change >= 0 else '#f43f5e'};")
        self._set_trade_controls(asset_type)
        self._update_order_value()
        self.selected_metric_history = None
        self.selected_metric_label = ""
        if asset_type == "Commodity":
            self.subtitle.setText(f"Commodity | {display_label(data.get('kategorie', ''))} | Priced in GLD")
        elif asset_type == "Crypto":
            self.subtitle.setText(f"Crypto | {display_label(data.get('branche', ''))} | Demand-driven chain economics")
        elif asset_type == "Fund":
            self.subtitle.setText(
                f"Funds and ETFs | {display_label(data.get('fund_type', 'Fund'))} | Issuer {display_text(data.get('issuer_bank', ''))}"
            )
        elif asset_type == "Index":
            self.subtitle.setText(f"Index | {display_label(data.get('land', ''))} | Market-cap weighted equity benchmark")
        elif asset_type == "Forex":
            self.subtitle.setText("Forex | Exchange-rate history | Macro-driven currency strength")
        elif asset_type == "Bond":
            self.subtitle.setText("Bond | Secondary-market price history | Rate and credit-risk driven")
        elif asset_type == "GlobalMacro":
            self.subtitle.setText("Global macro indicator | Daily simulation history")
        else:
            self.subtitle.setText(
                f"{display_label(data.get('land', ''))} | {display_label(data.get('branche', ''))} | Rating {data.get('rating', 'BB')}"
            )
        self._rebuild_kpis()
        self._rebuild_supply_chain(previous_supply_identity)
        self._draw_positioning()
        self._configure_detail_tabs(asset_type)
        if same_asset and previous_tab in {self.chart_tab, self.overview_tab, self.supply_tab}:
            self.detail_tabs.setCurrentWidget(previous_tab)
        else:
            self.detail_tabs.setCurrentWidget(self.chart_tab)
        if redraw_chart:
            self._draw_chart()

    def update_live_quote(self, data: dict[str, Any], state: GameState | None = None) -> None:
        if state is not None:
            self.state = state
        existing_history = self.data.get("historie", [])
        self.data = dict(data)
        if not self.data.get("historie") and existing_history:
            self.data["historie"] = existing_history
        self.current_price = float(self.data.get("kurs", self.current_price))
        history = merge_history_by_date(list(self.data.get("historie", [])))
        if self.range_points > 0 and len(history) > self.range_points:
            history = history[-self.range_points :]
        self.data["historie"] = history
        change = float(self.data.get("aenderung", 0.0))
        region = str(self.data.get("land", self.data.get("ziel", "GD")))
        self.header_price.setText(regional_money_precise(self.current_price, region))
        self.header_change.setText(percent(change))
        self.header_change.setStyleSheet(f"color: {'#14b8a6' if change >= 0 else '#f43f5e'};")
        self._update_order_value()
        self._draw_chart()

    def _configure_detail_tabs(self, asset_type: str) -> None:
        has_fundamentals = asset_type in {"Stock", "Commodity", "Crypto", "Fund", "Derivative"}
        has_supply = asset_type in {"Stock", "Crypto", "Fund"}
        self.detail_tabs.setTabVisible(self.detail_tabs.indexOf(self.overview_tab), has_fundamentals)
        self.detail_tabs.setTabVisible(self.detail_tabs.indexOf(self.supply_tab), has_supply)
        self.detail_tabs.setTabText(
            self.detail_tabs.indexOf(self.overview_tab),
            "Overview" if asset_type == "Fund" else "Fundamentals",
        )
        self.detail_tabs.setTabText(
            self.detail_tabs.indexOf(self.supply_tab),
            "Allocations" if asset_type == "Fund" else "Supply Chain",
        )

    def _detail_tab_changed(self, _index: int) -> None:
        if self.detail_tabs.currentWidget() is self.overview_tab:
            self._layout_fundamental_cards()

    def _set_trade_controls(self, asset_type: str) -> None:
        can_trade_spot = asset_type in self.SPOT_AND_PERPETUAL_ASSETS | {"Fund"} or (
            asset_type == "Derivative" and derivative_allows_spot_trade(self.data)
        )
        can_trade_perpetual = asset_type in self.SPOT_AND_PERPETUAL_ASSETS or (
            asset_type == "Derivative" and derivative_allows_future_trade(self.data)
        )
        for widget in self.order_control_widgets:
            widget.setVisible(can_trade_spot or can_trade_perpetual)
        self.order_leverage.setVisible(can_trade_perpetual)
        for side in ("LONG", "SHORT"):
            self.order_buttons[side].setVisible(can_trade_perpetual)
        for side in ("BUY", "SELL"):
            self.order_buttons[side].setVisible(can_trade_spot)
        self._update_order_value()

    def _trade_is_valid(self, side: str, amount: float) -> bool:
        if self.state is None or not self.ticker:
            return True
        mode = "SPOT" if side in {"BUY", "SELL"} else "FUTURE"
        return validate_trade_request(self.state, self.ticker, mode, side, amount, self._selected_leverage()).is_valid

    def _update_trade_buttons(self, quantity: float, margin: float) -> None:
        for side, amount in [("BUY", quantity), ("SELL", quantity), ("LONG", margin), ("SHORT", margin)]:
            button = self.order_buttons.get(side)
            if button is None or not button.isVisible():
                continue
            button.setEnabled(amount > 0.0 and self._trade_is_valid(side, amount))

    def _rebuild_kpis(self) -> None:
        self._clear_fundamental_cards()
        if self.asset_type in {"Index", "Forex", "Bond", "GlobalMacro"}:
            self.kpi_frame.setVisible(False)
            return

        self.kpi_frame.setVisible(True)
        region = "GD" if self.asset_type in {"Commodity", "Crypto"} else str(self.data.get("land", "GD"))
        if self.asset_type == "Commodity":
            values = [
                ("Price", regional_money_precise(float(self.data.get("kurs", 0.0)), region)),
                ("Change", percent(float(self.data.get("aenderung", 0.0)))),
                ("Market Cap", regional_money(float(self.data.get("market_cap", 0.0)), region, compact=True)),
                ("Open Interest", regional_money(float(self.data.get("open_interest", 0.0)), region, compact=True)),
                ("Production", compact_money(float(self.data.get("production", 0.0)))),
                ("Production Growth", percent(float(self.data.get("production_change", 0.0)) * 100)),
                ("Demand", compact_money(float(self.data.get("demand", 0.0)))),
                ("Demand Growth", percent(float(self.data.get("demand_change", 0.0)) * 100)),
                ("Extraction Cost", regional_money_precise(float(self.data.get("extraction_cost", 0.0)), region)),
                ("Cost Growth", percent(float(self.data.get("extraction_cost_change", 0.0)) * 100)),
                ("Inventories", compact_money(float(self.data.get("inventories", 0.0)))),
                ("Inventory Growth", percent(float(self.data.get("inventories_change", 0.0)) * 100)),
            ]
        elif self.asset_type == "Crypto":
            values = [
                ("Price", regional_money_precise(float(self.data.get("kurs", 0.0)), region), float(self.data.get("aenderung", 0.0))),
                ("Change", percent(float(self.data.get("aenderung", 0.0)))),
                self._crypto_metric("Market Cap", "market_cap", "money_compact"),
                self._crypto_metric("Open Interest", "open_interest", "money_compact"),
                self._crypto_metric("Demand", "demand", "compact"),
                self._crypto_metric("Market Share", "market_share", "percent"),
                self._crypto_metric("Utilization", "network_utilization", "percent", color_mode="utilization"),
                self._crypto_metric("Transactions", "transactions", "compact", change_key="transaction_change"),
                self._crypto_metric("Network Revenue", "chain_fees", "money", change_key="fee_change"),
                self._crypto_metric("Average Fee", "average_fee", "money", invert_color=True),
                self._crypto_metric("Circulating Supply", "circulating_supply", "compact", invert_color=True),
                self._crypto_metric("Active Wallets", "active_wallets", "compact", change_key="wallet_change"),
            ]
            values.extend(self._crypto_task_kpis())
        elif self.asset_type == "Fund":
            region = str(self.data.get("land", self.data.get("ziel", "GD")))
            values = [
                ("Price", regional_money_precise(float(self.data.get("kurs", 0.0)), region), float(self.data.get("aenderung", 0.0))),
                ("Change", percent(float(self.data.get("aenderung", 0.0)))),
                ("AUM", regional_money(float(self.data.get("aum", self.data.get("market_cap", 0.0))), region, compact=True), float(self.data.get("aum_change", 0.0))),
                self._fund_performance_metric("Performance 1M", "performance_1m"),
                self._fund_performance_metric("Performance 6M", "performance_6m"),
                self._fund_performance_metric("Performance 1Y", "performance_1y"),
                self._fund_performance_metric("Performance ALL", "performance_all"),
                self._fund_neutral_metric("Fund Age", self._fund_age_text()),
                self._fund_performance_metric("Cash Allocation", "cash_allocation", multiplier=100.0),
                self._fund_neutral_metric("Equity Allocation", percent(float(self.data.get("equity_allocation", 0.0)) * 100.0)),
                self._fund_neutral_metric("Bond Allocation", percent(float(self.data.get("bond_allocation", 0.0)) * 100.0)),
                self._fund_neutral_metric("Commodity Allocation", percent(float(self.data.get("commodity_allocation", 0.0)) * 100.0)),
                self._fund_neutral_metric("Crypto Allocation", percent(float(self.data.get("crypto_allocation", 0.0)) * 100.0)),
                self._fund_performance_metric("Distribution Yield", "distribution_yield", multiplier=100.0),
                self._fund_neutral_metric("Tracked Index", str(self.data.get("tracked_index") or "-")),
                self._fund_neutral_metric("Leverage", f"{float(self.data.get('leverage', 1.0)):g}x"),
                self._fund_neutral_metric("Holdings", str(len(self._fund_allocation_rows()))),
            ]
        else:
            rating = normalize_rating(str(self.data.get("rating", DEFAULT_RATING)))
            values = [
                ("Price", f"{float(self.data.get('kurs', 0.0)):,.2f}"),
                ("Change", percent(float(self.data.get("aenderung", 0.0)))),
                ("Market Cap", regional_money(float(self.data.get("market_cap", 0.0)), region, compact=True)),
                ("Open Interest", regional_money(float(self.data.get("open_interest", 0.0)), region, compact=True)),
                ("Rating", rating),
                ("Default Probability", percent(default_probability(rating) * 100)),
                ("Shares", compact_money(float(self.data.get("aktien_anzahl", 0.0)))),
                ("Revenue", regional_money(float(self.data.get("revenue", 0.0)), region, compact=True)),
                ("Revenue Growth", percent(float(self.data.get("revenue_growth", 0.0)) * 100)),
                ("Free Cash Flow", regional_money(float(self.data.get("free_cash_flow", 0.0)), region, compact=True)),
                ("FCF Margin", percent(float(self.data.get("fcf_margin", 0.0)) * 100)),
                ("Dividend Yield", percent(float(self.data.get("dividend_yield", 0.0)) * 100)),
                ("EPS", f"{float(self.data.get('eps', 0.0)):,.2f}"),
            ]
            if "total_debt" in self.data or "debt" in self.data:
                debt = float(self.data.get("total_debt", self.data.get("debt", 0.0)))
                values.append(("Debt", regional_money(debt, region, compact=True)))
            if "interest_coverage" in self.data:
                values.append(("Interest Coverage", f"{float(self.data['interest_coverage']):,.2f}x"))
            if "debt_to_equity" in self.data:
                values.append(("Debt / Equity", f"{float(self.data['debt_to_equity']):,.2f}x"))
        if self.asset_type in {"Stock", "Commodity", "Crypto", "Derivative"}:
            values.append(("Drivers", driver_summary(self.data, self.asset_type)))
        if self.asset_type == "Derivative":
            values.append(("Use Case", derivative_use_case(self.data)))
            values.append(("Pricing Note", str(self.data.get("pricing_note") or derivative_pricing_note(self.data))))
        self._build_fundamental_cards(values)

    def _build_fundamental_cards(self, values: list[tuple]) -> None:
        market_labels = {"Price", "Change", "Market Cap", "Shares", "Open Interest", "AUM"}
        fundamental_labels = {
            "Revenue", "Revenue Growth", "Free Cash Flow", "FCF Margin", "EPS", "Dividend Yield",
            "Production", "Production Growth", "Demand", "Demand Growth", "Transactions", "Transaction Growth",
            "Network Revenue", "Average Fee", "Active Wallets", "Wallet Growth",
        }
        credit_labels = {
            "Rating", "Default Probability", "Debt", "Interest Coverage", "Debt / Equity",
            "Circulating Supply", "Inflation", "Extraction Cost", "Cost Growth",
        }
        driver_labels = {"Drivers", "Use Case", "Pricing Note"}
        grouped: dict[str, list[tuple]] = {
            "Market": [],
            "Fundamentals": [],
            "Credit & Capital": [],
            "Drivers": [],
        }
        for item in values:
            label = str(item[0])
            if label in market_labels:
                grouped["Market"].append(item)
            elif label in fundamental_labels:
                grouped["Fundamentals"].append(item)
            elif label in credit_labels:
                grouped["Credit & Capital"].append(item)
            elif label in driver_labels:
                grouped["Drivers"].append(item)
            else:
                grouped["Fundamentals"].append(item)
        for title, items in grouped.items():
            if not items:
                continue
            card = QFrame()
            card.setObjectName("PanelInner")
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 12)
            card_layout.setSpacing(8)
            heading = QLabel(title.upper())
            heading.setObjectName("SectionTitle")
            card_layout.addWidget(heading)
            metrics = QGridLayout()
            metrics.setHorizontalSpacing(18)
            metrics.setVerticalSpacing(8)
            for index, item in enumerate(items):
                if len(item) == 4:
                    label, value, change, color = item
                    metric = self._kpi(label, value, change, color)
                elif len(item) == 3:
                    label, value, change = item
                    metric = self._kpi(label, value, change)
                else:
                    label, value = item
                    metric = self._kpi(label, value)
                metrics.addLayout(metric, index // 2, index % 2)
            card_layout.addLayout(metrics)
            card_layout.addStretch(1)
            self._fundamental_cards.append(card)
        self._layout_fundamental_cards(force=True)

    def _clear_fundamental_cards(self) -> None:
        while self.kpi_grid.count():
            item = self.kpi_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._fundamental_cards = []
        self._fundamental_card_columns = 0

    def _layout_fundamental_cards(self, *, force: bool = False) -> None:
        if not self._fundamental_cards:
            return
        width = max(self.width(), self.detail_tabs.width())
        columns = 2 if width < 1100 else 3 if width < 1550 else 4
        columns = min(columns, len(self._fundamental_cards))
        if not force and columns == self._fundamental_card_columns:
            return
        while self.kpi_grid.count():
            self.kpi_grid.takeAt(0)
        for index, card in enumerate(self._fundamental_cards):
            self.kpi_grid.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            self.kpi_grid.setColumnStretch(column, 1)
        self._fundamental_card_columns = columns

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._layout_fundamental_cards()

    def _crypto_task_kpis(self) -> list[tuple[str, str, float]]:
        task_type = str(self.data.get("task_type", ""))
        if task_type == "STORE":
            return [self._crypto_metric("Hashrate", "hashrate", "compact")]
        if task_type == "PAY":
            return [
                self._crypto_metric("Transactions per Second", "tps", "compact"),
                self._crypto_metric("Confirmation Time", "confirmation_time", "seconds", invert_color=True),
                self._crypto_metric("Merchant Adoption", "merchant_adoption", "percent"),
            ]
        if task_type == "DATA":
            return [
                self._crypto_metric("Storage Capacity", "storage_capacity", "compact"),
                self._crypto_metric("Used Storage", "used_storage", "compact"),
                self._crypto_metric("Price per TB", "price_per_tb", "money"),
            ]
        if task_type == "GRID":
            return [
                self._crypto_metric("Energy Volume", "energy_volume", "compact"),
                self._crypto_metric("Smart Meter Nodes", "smart_meter_nodes", "compact"),
                self._crypto_metric("Grid Capacity", "grid_capacity", "compact"),
                self._crypto_metric("Energy Transactions", "energy_transactions", "compact"),
                self._crypto_metric("Settlement Speed", "settlement_speed", "seconds"),
            ]
        return []

    def _fund_age_text(self) -> str:
        months = max(0, int(self.data.get("fund_age_months", 0)))
        years, remaining_months = divmod(months, 12)
        return f"{years}Y {remaining_months}M"

    def _fund_performance_metric(self, label: str, key: str, *, multiplier: float = 1.0) -> tuple[str, str, float, str]:
        value = float(self.data.get(key, 0.0)) * multiplier
        return label, percent(value), None, "#14b8a6" if value >= 0 else "#f43f5e"

    def _fund_neutral_metric(self, label: str, value: str) -> tuple[str, str, float, str]:
        return label, value, None, "#e5eef8"

    def _crypto_metric(
        self,
        label: str,
        key: str,
        value_type: str,
        *,
        change_key: str | None = None,
        invert_color: bool = False,
        color_mode: str = "change",
    ) -> tuple[str, str, float, str | None]:
        value = float(self.data.get(key, 0.0))
        change = float(self.data.get(change_key or f"{key}_change", 0.0)) * 100.0
        display_change = -change if invert_color else change
        if value_type == "compact":
            text = compact_money(value)
        elif value_type == "money":
            text = regional_money_precise(value, "GD")
        elif value_type == "money_compact":
            text = regional_money(value, "GD", compact=True)
        elif value_type == "percent":
            text = percent(value * 100.0)
        elif value_type == "seconds":
            text = f"{value:,.2f}s"
        else:
            text = f"{value:,.2f}"
        color = self._crypto_metric_color(value, display_change, color_mode)
        return label, text, display_change, color

    def _crypto_metric_color(self, value: float, change: float, color_mode: str) -> str | None:
        if color_mode == "utilization":
            if value >= 0.70:
                return "#14b8a6"
            if value >= 0.40:
                return "#f59e0b"
            return "#f43f5e"
        return "#14b8a6" if change >= 0 else "#f43f5e"

    def _rebuild_supply_chain(self, selected_identity: tuple[str, str] | None = None) -> None:
        if self.asset_type == "Fund":
            supply_index = self.detail_tabs.indexOf(self.supply_tab)
            self.detail_tabs.setTabText(supply_index, "Allocations")
            self.detail_tabs.setTabEnabled(supply_index, True)
            self.supply_model.set_headers(["Ticker", "Name", "Asset Type", "Weight"])
            self.supply_model.right_aligned_columns = {3}
            self._populate_allocation_rows(self._fund_allocation_rows())
            return
        supply_index = self.detail_tabs.indexOf(self.supply_tab)
        self.detail_tabs.setTabText(supply_index, "Supply Chain")
        self.supply_model.set_headers(["Role", "Code", "Name", "Share", "Company Qty", "Supply", "Demand", "Inventories", "Shortage", "Pressure"])
        self.supply_model.right_aligned_columns = {3, 4, 5, 6, 7, 8, 9}
        self.detail_tabs.setTabEnabled(supply_index, self.asset_type in {"Stock", "Crypto"})
        if self.asset_type == "Crypto":
            rows = self._crypto_supply_rows()
            self._populate_supply_rows(rows, selected_identity)
            return
        if self.asset_type != "Stock":
            return
        rows = self._company_supply_rows()
        self._populate_supply_rows(rows, selected_identity)

    def _populate_supply_rows(self, rows: list[dict[str, Any]], selected_identity: tuple[str, str] | None = None) -> None:
        table_rows = []
        for row in rows:
            values = []
            for column, key in enumerate(
                ["role", "code", "name", "share", "company_qty", "supply", "demand", "inventories", "shortage", "pressure"]
            ):
                value = row[key]
                if key in {"share", "shortage", "pressure"}:
                    text = percent(float(value) * 100.0)
                elif key in {"company_qty", "supply", "demand", "inventories"}:
                    text = compact_money(float(value))
                else:
                    text = str(value)
                values.append(text)
            table_rows.append(values)
        self.supply_model.set_rows(table_rows, metadata=rows)
        if rows:
            target_row = self._supply_row_index(rows, selected_identity)
            self._suppress_supply_selection = True
            selection_model = self.supply_table.selectionModel()
            selection_model.blockSignals(True)
            self.supply_table.selectRow(target_row)
            selection_model.blockSignals(False)
            self._suppress_supply_selection = False
            if selected_identity is not None:
                row = rows[target_row]
                self.selected_metric_history = list(row.get("company_qty_history", []))
                self.selected_metric_label = f"{display_label(row.get('name', row.get('code')))} | Company Qty"

    def _populate_allocation_rows(self, rows: list[dict[str, Any]]) -> None:
        table_rows = []
        for row in rows:
            values = []
            for key in ["ticker", "name", "asset_type", "weight"]:
                value = row[key]
                text = percent(float(value) * 100.0) if key == "weight" else str(value)
                values.append(text)
            table_rows.append(values)
        self.supply_model.set_rows(table_rows, metadata=rows)

    def _fund_allocation_rows(self) -> list[dict[str, Any]]:
        rows = []
        for holding in self.data.get("underlyings", []):
            ticker = str(holding.get("ticker", ""))
            weight = float(holding.get("weight", 0.0))
            asset_type = str(holding.get("asset_type", ""))
            if asset_type == "Index":
                index = (self.state.indices if self.state is not None else {}).get(ticker, {})
                for stock_ticker, index_weight in index.get("constituents", {}).items():
                    asset = (self.state.stocks if self.state is not None else {}).get(stock_ticker, {})
                    rows.append(
                        {
                            "ticker": stock_ticker,
                            "name": display_text(asset.get("name", stock_ticker)),
                            "asset_type": "Stock",
                            "weight": weight * float(index_weight),
                        }
                    )
                continue
            asset = self._allocation_asset(asset_type, ticker)
            rows.append(
                {
                    "ticker": ticker,
                    "name": display_text(asset.get("name", asset.get("issuer", ticker))),
                    "asset_type": asset_type,
                    "weight": weight,
                }
            )
        return sorted(rows, key=lambda row: row["weight"], reverse=True)

    def _allocation_asset(self, asset_type: str, ticker: str) -> dict[str, Any]:
        if self.state is None:
            return {}
        if asset_type == "Stock":
            return self.state.stocks.get(ticker, {})
        if asset_type == "Commodity":
            return self.state.commodities.get(ticker, {})
        if asset_type == "Crypto":
            return self.state.cryptos.get(ticker, {})
        if asset_type == "Index":
            return self.state.indices.get(ticker, {})
        if asset_type == "Bond":
            for bond in self.state.bond_market:
                if str(bond.get("symbol", "")) == ticker:
                    return bond
        return {}

    def _crypto_supply_rows(self) -> list[dict[str, Any]]:
        service_code = str(self.data.get("service_code", "CRPAY"))
        service_market = self._market_item(service_code)
        service_qty = max(1.0, float(self.data.get("demand", self.data.get("network_capacity", 1.0))))
        rows = [
            self._supply_row("Provides", service_code, float(self.data.get("market_share", 0.0)), service_qty, service_market, self._metric_history(service_market, "supply_history")),
        ]
        input_weights = {"ELC": 0.36, "ECOMP": 0.22, "SDIG": 0.24, "CHW": 0.18}
        for code, weight in input_weights.items():
            required = service_qty * weight
            rows.append(self._supply_row("Needs", code, 0.0, required, self._market_item(code), self._metric_history(self._market_item(code), "demand_history")))
        return rows

    def _company_supply_rows(self) -> list[dict[str, Any]]:
        output_mix = self.data.get("output_mix") or {self.data.get("specialization", ""): 1.0}
        capacity = max(1.0, float(self.data.get("production_capacity", 0.0)))
        rows = []
        required_inputs: dict[str, float] = {}
        for code, share in self._normalized_mix(output_mix).items():
            market = self._market_item(code)
            company_qty = capacity * share
            rows.append(self._supply_row("Produces", code, share, company_qty, market, self._company_quantity_history("output", code, company_qty)))
            definition = PROCESSED_PRODUCTS.get(code)
            if definition:
                for input_code, required in _input_requirements(code, tuple(definition["inputs"]), company_qty).items():
                    required_inputs[input_code] = required_inputs.get(input_code, 0.0) + required
        for code, required in sorted(required_inputs.items(), key=lambda item: item[1], reverse=True):
            rows.append(self._supply_row("Needs", code, 0.0, required, self._market_item(code), self._company_quantity_history("input", code, required)))
        return rows

    def _supply_row(self, role: str, code: str, share: float, company_qty: float, market: dict[str, Any], quantity_history: list[float]) -> dict[str, Any]:
        return {
            "role": role,
            "code": code,
            "name": display_text(self._item_name(code, market)),
            "share": share,
            "company_qty": company_qty,
            "supply": float(market.get("supply", market.get("production", 0.0))),
            "demand": float(market.get("demand", 0.0)),
            "inventories": float(market.get("inventories", 0.0)),
            "shortage": float(market.get("shortage", 0.0)),
            "pressure": float(market.get("price_pressure", 0.0)),
            "market": market,
            "company_qty_history": quantity_history,
        }

    def _draw_selected_supply_metric(self) -> None:
        if self._suppress_supply_selection:
            return
        if self.asset_type == "Fund":
            return
        index = self.supply_table.currentIndex()
        if not index.isValid():
            return
        row = index.data(METADATA_ROLE)
        if not isinstance(row, dict):
            return
        self.selected_metric_history = list(row.get("company_qty_history", []))
        self.selected_metric_label = f"{display_label(row.get('name', row.get('code')))} | Company Qty"
        self._draw_chart()

    def _selected_supply_identity(self) -> tuple[str, str] | None:
        index = self.supply_table.currentIndex()
        if not index.isValid() or self.selected_metric_history is None:
            return None
        row = index.data(METADATA_ROLE)
        if not isinstance(row, dict):
            return None
        return str(row.get("role", "")), str(row.get("code", ""))

    def _supply_row_index(self, rows: list[dict[str, Any]], selected_identity: tuple[str, str] | None) -> int:
        if selected_identity is None:
            return 0
        selected_role, selected_code = selected_identity
        for index, row in enumerate(rows):
            if row.get("role") == selected_role and row.get("code") == selected_code:
                return index
        return 0

    def _company_quantity_history(self, role: str, code: str, fallback: float) -> list[float]:
        history_book = self.data.get("company_output_history" if role == "output" else "company_input_history", {})
        points = []
        for entry in history_book.get(code, {}).get("history", []):
            try:
                points.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
            except (TypeError, ValueError):
                continue
        return points if len(points) >= 2 else [fallback, fallback]

    def _metric_history(self, market: dict[str, Any], key: str) -> list[float]:
        points = []
        for entry in market.get(key, []):
            try:
                points.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
            except (TypeError, ValueError):
                continue
        fallback_key = {
            "supply_history": "supply",
            "demand_history": "demand",
            "inventory_history": "inventories",
            "shortage_history": "shortage",
            "price_pressure_history": "price_pressure",
        }.get(key, "supply")
        fallback = float(market.get(fallback_key, 0.0))
        if key in {"shortage_history", "price_pressure_history"} and len(points) == 0:
            fallback *= 100.0
        return points or [fallback]

    def _market_item(self, code: str) -> dict[str, Any]:
        if self.state is not None:
            return self.state.commodities.get(code) or self.state.processed_products.get(code) or {}
        return {}

    def _item_name(self, code: str, market: dict[str, Any]) -> str:
        if market.get("name"):
            return display_text(market["name"])
        if code in commodity_definitions():
            return display_text(commodity_definitions()[code]["name"])
        if code in PROCESSED_PRODUCTS:
            return display_text(PROCESSED_PRODUCTS[code]["name"])
        return code

    def _normalized_mix(self, output_mix: dict[str, Any]) -> dict[str, float]:
        cleaned = {str(code): max(0.0, float(share)) for code, share in dict(output_mix).items() if code}
        total = sum(cleaned.values()) or 1.0
        return {code: share / total for code, share in cleaned.items() if share > 0.0}

    def _normalize_input(self, item: str) -> str:
        return PRODUCT_NAME_TO_CODE.get(item, item)

    def _kpi(self, label: str, value: str, change: float | None = None, color: str | None = None) -> QVBoxLayout:
        box = QVBoxLayout()
        caption = QLabel(label.upper())
        caption.setObjectName("Muted")
        main = QLabel(value if change is None else f"{value}  {percent(change)}")
        main.setObjectName("DetailValue")
        if label in {"Drivers", "Use Case", "Pricing Note"}:
            main.setWordWrap(True)
        direction = change if change is not None else self._metric_direction(label)
        if color is not None:
            main.setStyleSheet(f"color: {color};")
        elif direction is not None:
            main.setStyleSheet(f"color: {'#14b8a6' if direction >= 0 else '#f43f5e'};")
        box.addWidget(caption)
        box.addWidget(main)
        return box

    def _metric_direction(self, label: str) -> float | None:
        if label == "Price":
            prices = self._history_points()
            return prices[-1] - prices[-2] if len(prices) >= 2 else 0.0
        if label == "Change":
            return float(self.data.get("aenderung", 0.0))
        if label == "Market Cap":
            current = float(self.data.get("market_cap", 0.0))
            prices = self._history_points()
            shares = float(self.data.get("aktien_anzahl", 10_000_000.0 if self.asset_type == "Commodity" else 0.0))
            previous = prices[-2] * shares if len(prices) >= 2 and shares else current
            return current - previous
        if label == "Production":
            return float(self.data.get("production", 0.0)) - float(self.data.get("previous_production", 0.0))
        if label == "Production Growth":
            return float(self.data.get("production_change", 0.0))
        if label == "Demand":
            return float(self.data.get("demand", 0.0)) - float(self.data.get("previous_demand", 0.0))
        if label == "Demand Growth":
            return float(self.data.get("demand_change", 0.0))
        if label == "Extraction Cost":
            return float(self.data.get("extraction_cost", 0.0)) - float(self.data.get("previous_extraction_cost", 0.0))
        if label == "Cost Growth":
            return float(self.data.get("extraction_cost_change", 0.0))
        if label == "Inventories":
            return float(self.data.get("inventories", 0.0)) - float(self.data.get("previous_inventories", 0.0))
        if label == "Inventory Growth":
            return float(self.data.get("inventories_change", 0.0))
        if label == "Transactions":
            return float(self.data.get("transactions", 0.0)) - float(self.data.get("previous_transactions", 0.0))
        if label == "Transaction Growth":
            return float(self.data.get("transaction_change", 0.0))
        if label == "Fees":
            return float(self.data.get("chain_fees", 0.0)) - float(self.data.get("previous_chain_fees", 0.0))
        if label == "Fee Growth":
            return float(self.data.get("fee_change", 0.0))
        if label == "Circulating Supply":
            return -(
                float(self.data.get("circulating_supply", 0.0))
                - float(self.data.get("previous_circulating_supply", 0.0))
            )
        if label == "Inflation":
            return -float(self.data.get("inflation_rate", 0.0))
        if label == "Active Wallets":
            return float(self.data.get("active_wallets", 0.0)) - float(self.data.get("previous_active_wallets", 0.0))
        if label == "Wallet Growth":
            return float(self.data.get("wallet_change", 0.0))
        if label == "Revenue":
            return float(self.data.get("revenue", 0.0)) - float(self.data.get("previous_revenue", 0.0))
        if label == "Revenue Growth":
            return float(self.data.get("revenue_growth", 0.0)) - float(self.data.get("previous_revenue_growth", 0.0))
        if label == "Free Cash Flow":
            return float(self.data.get("free_cash_flow", 0.0)) - float(self.data.get("previous_free_cash_flow", 0.0))
        if label == "FCF Margin":
            return float(self.data.get("fcf_margin", 0.0)) - float(self.data.get("previous_fcf_margin", 0.0))
        if label == "Dividend Yield":
            return float(self.data.get("dividend_yield", 0.0)) - float(self.data.get("previous_dividend_yield", 0.0))
        if label == "EPS":
            return float(self.data.get("eps", 0.0)) - float(self.data.get("previous_eps", 0.0))
        return None

    def _draw_chart(self) -> None:
        self.last_candle_count = 0
        history = self._history_entries()
        prices = self._history_points(history)
        if self.asset_type == "GlobalMacro" and self.yield_curve_terms:
            self._draw_yield_curve(prices)
            return
        if self.range_points and len(history) > self.range_points:
            history = history[-self.range_points :]
            prices = prices[-self.range_points :]
        self._update_performance(prices)
        if len(prices) >= 2:
            color = "#14b8a6" if prices[-1] >= prices[0] else "#f43f5e"
            supports_indicators = (
                self.asset_type in {"Stock", "Commodity", "Crypto", "Fund", "Index"}
                and self.selected_metric_history is None
            )
            if self.chart_mode == "Candle" and self.selected_metric_history is None:
                candle_prices = [candle.close for candle in build_candles(history, self.range_points)[0]] or prices
                overlays = self._enabled_ema_series(candle_prices) if supports_indicators else []
                self.chart_view.plot_candles(
                    history,
                    range_points=self.range_points,
                    title=self._chart_title(),
                    overlays=overlays,
                )
                self.last_candle_count = self.chart_view.last_candle_count
                self.last_candle_interval = self.chart_view.last_candle_interval
                self.legend_labels = [label for label, values, _color in overlays if len(values) >= 2]
            elif not supports_indicators:
                self.legend_labels = []
                self.chart_view.plot_line(
                    prices,
                    dates=[history_date(item) for item in history],
                    color=color,
                    title=self._chart_title(),
                    label="Value",
                )
            else:
                series_specs = [("Price", prices, color)]
                series_specs.extend(self._enabled_ema_series(prices))
                if self.enabled_indicators:
                    self.chart_view.plot_lines(
                        series_specs,
                        title=self._chart_title(),
                        legend=True,
                        dates=[history_date(item) for item in history],
                    )
                else:
                    self.chart_view.plot_line(
                        prices,
                        dates=[history_date(item) for item in history],
                        color=color,
                        title=self._chart_title(),
                        label="Price",
                    )
                self.legend_labels = [label for label, values, _color in series_specs if label != "Price" and len(values) >= 2]
            self.chart_view.set_loading(self._history_is_loading(), has_data=True)
        else:
            self.chart_view.set_loading(self._history_is_loading(), has_data=False)
            if not self._history_is_loading():
                self.chart_view.show_message("History builds as the simulation runs")

    def _draw_positioning(self) -> None:
        if self.asset_type not in {"Stock", "Commodity", "Crypto"}:
            self.positioning_view.setVisible(False)
            return
        self.positioning_view.setVisible(True)
        long_value = float(self.data.get("long_interest", 0.0))
        short_value = float(self.data.get("short_interest", 0.0))
        if long_value <= 0.0 and short_value <= 0.0:
            self.positioning_view.setVisible(False)
            return
        pressure = float(self.data.get("squeeze_pressure", 0.0))
        title = "Long / Short Interest"
        if pressure > 0.0:
            title = "Long / Short Interest - Short Squeeze"
        elif pressure < 0.0:
            title = "Long / Short Interest - Long Squeeze"
        self.positioning_view.plot_long_short_heatmap(long_value, short_value, title=title)

    def _update_performance(self, prices: list[float]) -> None:
        if len(prices) < 2 or prices[0] == 0:
            self.performance_label.setText("-")
            self.performance_label.setStyleSheet("")
            return
        value = ((prices[-1] / prices[0]) - 1.0) * 100.0
        self.performance_label.setText(percent(value))
        self.performance_label.setStyleSheet(f"color: {'#14b8a6' if value >= 0 else '#f43f5e'};")

    def _chart_title(self) -> str:
        if self.asset_type == "Bond":
            return "Bond Price History"
        if self.asset_type == "GlobalMacro":
            return "Global Macro History"
        return self.selected_metric_label or "Price History"

    def _draw_yield_curve(self, yields: list[float]) -> None:
        if len(yields) < 2:
            self.chart_view.show_message("Yield curve builds as the simulation runs")
            return
        color = "#14b8a6" if yields[-1] >= yields[0] else "#f43f5e"
        self.chart_view.plot_line(yields, color=color, title="Government Yield Curve", label="Yield")
        self.legend_labels = []

    def _ema_series(self, prices: list[float], period: int, color: str) -> list[tuple[str, list[float], str]]:
        ema = ema_values(prices, min(period, len(prices)))
        if len(ema) >= 2:
            return [(f"EMA {period}", ema, color)]
        return []

    def _enabled_ema_series(self, prices: list[float]) -> list[tuple[str, list[float], str]]:
        colors = {20: "#22d3ee", 50: "#f59e0b", 200: "#8b5cf6"}
        series: list[tuple[str, list[float], str]] = []
        for period in sorted(self.enabled_indicators):
            series.extend(self._ema_series(prices, period, colors[period]))
        return series

    def _history_is_loading(self) -> bool:
        return bool(self.data.get("_history_loading") or self.data.get("_history_refreshing"))

    def _history_entries(self) -> list[Any]:
        return list(self.data.get("historie", []))

    def _history_points(self, history: list[Any] | None = None) -> list[float]:
        if self.selected_metric_history is not None:
            return list(self.selected_metric_history)
        history = self._history_entries() if history is None else history
        points = []
        for entry in history:
            try:
                points.append(history_close(entry))
            except (TypeError, ValueError):
                continue
        return points

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                self._clear_layout(item.layout())


StockDetailDialog = StockDetailView
