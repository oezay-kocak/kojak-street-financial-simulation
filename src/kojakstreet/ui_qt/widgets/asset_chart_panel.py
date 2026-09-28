"""Asset detail and chart panel."""

from __future__ import annotations

from typing import Any, ClassVar

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from kojakstreet.core.financial_products import (
    EXPIRING_DERIVATIVE_CONTRACT_TYPES,
    derivative_allows_spot_trade,
)
from kojakstreet.core.market_explanations import driver_summary
from kojakstreet.core.ohlc import history_close
from kojakstreet.core.trade_preview import validate_trade_request
from kojakstreet.ui_qt.chart_series import history_date, merge_history_by_date
from kojakstreet.ui_qt.display import display_label, display_text
from kojakstreet.ui_qt.formatters import percent, regional_money
from kojakstreet.ui_qt.widgets.qt_chart import FastChartView


class AssetChartPanel(QFrame):
    """Right-side quote details and chart panel."""

    trade_requested = Signal(str, str, str, float, int)
    chart_request_changed = Signal()
    SPOT_AND_PERPETUAL_ASSETS: ClassVar[set[str]] = {"Stock", "Commodity", "Crypto"}
    SPOT_ONLY_ASSETS: ClassVar[set[str]] = {"Fund", "Derivative"}

    def __init__(self, state: Any | None = None) -> None:
        super().__init__()
        self.setObjectName("PanelInner")
        self.state = state
        self.current_asset: tuple[str, str, dict[str, Any]] | None = None
        self.range_points = 132
        self.chart_mode = "Line"
        self.chart_draw_count = 0
        self.last_candle_count = 0
        self.last_candle_interval = "Daily"
        self.performance_value = QLabel("-")
        self.performance_value.setObjectName("DetailValue")
        self.current_price = 0.0
        self._chart_points: list[float] = []
        self._chart_history: list[Any] = []
        self._pending_live_points: list[float] | None = None
        self._live_redraw_timer = QTimer(self)
        self._live_redraw_timer.setSingleShot(True)
        self._live_redraw_timer.timeout.connect(self._flush_live_line_redraw)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        self.title = QLabel("Select an asset")
        self.title.setObjectName("SectionTitle")
        self.meta = QLabel("Price history")
        self.meta.setObjectName("Muted")

        self.kpi_grid = QGridLayout()
        self.kpi_grid.setHorizontalSpacing(20)
        self.kpi_grid.setVerticalSpacing(8)
        self.price_value = self._detail_kpi("Price", 0, 0)
        self.change_value = self._detail_kpi("Change", 0, 1)
        self.region_value = self._detail_kpi("Region", 0, 2)
        self.market_cap_caption, self.market_cap_value = self._detail_kpi_pair("Market Cap", 1, 0)
        self.performance_value = self._detail_kpi("Period Perf", 1, 1)
        self.open_interest_value = self._detail_kpi("Open Interest", 1, 2)
        self.driver_value = self._detail_kpi("Drivers", 2, 0, column_span=3)
        self.driver_value.setWordWrap(True)
        for column in range(3):
            self.kpi_grid.setColumnStretch(column, 1)

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

        self.chart_view = FastChartView(title="Price History")
        self.chart_view.setMinimumHeight(280)
        self.positioning_view = FastChartView(title="Long / Short Interest")
        self.positioning_view.setMinimumHeight(104)
        self.positioning_view.setMaximumHeight(130)
        self.order_panel = self._build_order_panel()

        layout.addWidget(self.title)
        layout.addWidget(self.meta)
        layout.addLayout(self.kpi_grid)
        layout.addLayout(control_bar)
        layout.addWidget(self.chart_view, 1)
        layout.addWidget(self.positioning_view)
        layout.addWidget(self.order_panel)

    def set_state(self, state: Any | None) -> None:
        self.state = state
        self._update_order_value()

    def _build_order_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PanelInner")
        layout = QGridLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        self.order_quantity = QLineEdit()
        self.order_quantity.setPlaceholderText("Qty")
        self.order_quantity.setMinimumWidth(110)
        self.order_quantity.setValidator(QDoubleValidator(0.0, 1_000_000_000.0, 4, self))
        self.order_quantity.textChanged.connect(self._update_order_value)
        self.order_total_value = QLabel("Total -")
        self.order_total_value.setObjectName("Muted")
        self.order_total_value.setMinimumWidth(190)
        self.order_total_value.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.order_leverage = QComboBox()
        self.order_leverage.setMinimumWidth(82)
        self.order_leverage.addItems(["1x", "2x", "3x", "4x", "5x"])
        self.order_leverage.currentTextChanged.connect(self._update_order_value)
        self.order_leverage_label = QLabel("Leverage")
        self.order_leverage_label.setObjectName("Muted")
        self.order_leverage_label.setStyleSheet("background: transparent;")

        self.buy_button = QPushButton("Buy")
        self.buy_button.setObjectName("ActionButton")
        self.buy_button.clicked.connect(lambda: self._emit_trade("BUY"))
        self.sell_button = QPushButton("Sell")
        self.sell_button.setObjectName("ActionButton")
        self.sell_button.clicked.connect(lambda: self._emit_trade("SELL"))
        self.long_button = QPushButton("Long")
        self.long_button.setObjectName("ActionButton")
        self.long_button.clicked.connect(lambda: self._emit_trade("LONG"))
        self.short_button = QPushButton("Short")
        self.short_button.setObjectName("ActionButton")
        self.short_button.clicked.connect(lambda: self._emit_trade("SHORT"))

        layout.addWidget(self.order_quantity, 0, 0)
        layout.addWidget(self.order_total_value, 0, 1)
        layout.addWidget(self.order_leverage_label, 0, 2)
        layout.addWidget(self.order_leverage, 0, 3)
        layout.addWidget(self.buy_button, 1, 0)
        layout.addWidget(self.sell_button, 1, 1)
        layout.addWidget(self.long_button, 1, 2)
        layout.addWidget(self.short_button, 1, 3)
        layout.setColumnStretch(0, 1)
        layout.setColumnMinimumWidth(1, 190)
        return panel

    def _emit_trade(self, side: str) -> None:
        if self.current_asset is None:
            return
        ticker, asset_type, _data = self.current_asset
        if asset_type not in self.SPOT_AND_PERPETUAL_ASSETS | self.SPOT_ONLY_ASSETS:
            return
        quantity = self._order_quantity()
        if quantity <= 0:
            return
        leverage = self._selected_leverage()
        if side in {"BUY", "SELL"}:
            if not self._trade_is_valid(side, quantity):
                return
            self.trade_requested.emit(ticker, "SPOT", side, quantity, leverage)
        elif side in {"LONG", "SHORT"} and self._can_trade_perpetual(asset_type, _data):
            margin = (quantity * self.current_price) / max(1, leverage)
            if not self._trade_is_valid(side, margin):
                return
            self.trade_requested.emit(ticker, "FUTURE", side, margin, leverage)

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
            if self.current_asset is not None:
                contract_size = float(self.current_asset[2].get("contract_size", 0.0) or 0.0)
                if contract_size > 0.0:
                    total_text = f"{total_text} | Contract {contract_size:,.2f}"
            self.order_total_value.setText(total_text)
            self.order_total_value.setToolTip(total_text)
        else:
            self.order_total_value.setText("Total -")
            self.order_total_value.setToolTip("")
        self._update_trade_buttons(quantity, margin)

    def _detail_kpi(self, label: str, row: int, column: int, *, column_span: int = 1) -> QLabel:
        box = QVBoxLayout()
        caption = QLabel(label.upper())
        caption.setObjectName("Muted")
        value = QLabel("-")
        value.setObjectName("DetailValue")
        box.addWidget(caption)
        box.addWidget(value)
        self.kpi_grid.addLayout(box, row, column, 1, column_span)
        return value

    def _detail_kpi_pair(self, label: str, row: int, column: int, *, column_span: int = 1) -> tuple[QLabel, QLabel]:
        box = QVBoxLayout()
        caption = QLabel(label.upper())
        caption.setObjectName("Muted")
        value = QLabel("-")
        value.setObjectName("DetailValue")
        box.addWidget(caption)
        box.addWidget(value)
        self.kpi_grid.addLayout(box, row, column, 1, column_span)
        return caption, value

    def set_range(self, points: int) -> None:
        self.range_points = points
        for button, button_points in zip(self.range_buttons, [22, 132, 264, 0], strict=True):
            button.setChecked(button_points == points)
        if self.current_asset is not None:
            self.update_asset(*self.current_asset)
            self.chart_request_changed.emit()

    def set_chart_mode(self, mode: str) -> None:
        self.chart_mode = mode
        for button in self.mode_buttons:
            button.setChecked(button.text() == mode)
        if self.current_asset is not None:
            self.update_asset(*self.current_asset)
            self.chart_request_changed.emit()

    def update_asset(self, ticker: str, asset_type: str, data: dict[str, Any], *, redraw_chart: bool = True) -> None:
        self.current_asset = (ticker, asset_type, data)
        self._update_quote_labels(ticker, asset_type, data)

        history = self._history_entries(data)
        if self.range_points and len(history) > self.range_points:
            history = history[-self.range_points :]
        points = self._history_points(history)
        self._update_performance(points)
        self._draw_positioning(data)
        if not redraw_chart:
            return

        self._draw_chart(points, history)

    def update_live_quote(self, data: dict[str, Any]) -> None:
        if self.current_asset is None:
            return
        ticker, asset_type, _current_data = self.current_asset
        self.current_asset = (ticker, asset_type, data)
        self._update_quote_labels(ticker, asset_type, data)
        history = merge_history_by_date(list(data.get("historie", [])))
        if self.range_points and len(history) > self.range_points:
            history = history[-self.range_points :]
        points = self._history_points(history)
        self._chart_history = history
        self._chart_points = points
        if self.chart_mode != "Line":
            return
        self._update_performance(points)
        self._pending_live_points = points
        self._draw_positioning(data)
        if not self._live_redraw_timer.isActive():
            self._live_redraw_timer.start(48)

    def _flush_live_line_redraw(self) -> None:
        if self._pending_live_points is None:
            return
        points = self._pending_live_points
        self._pending_live_points = None
        self._redraw_live_line(points)

    def _update_quote_labels(self, ticker: str, asset_type: str, data: dict[str, Any]) -> None:
        name = display_text(data.get("name", ticker))
        price = float(data.get("kurs", 0.0))
        self.current_price = price
        change = float(data.get("aenderung", 0.0))
        sector = display_label(data.get("branche", data.get("kategorie", data.get("typ", ""))))
        region = str(data.get("land", data.get("ziel", "GD")))

        self.title.setText(f"{ticker}  {name}")
        self.meta.setText(f"{asset_type} | {sector}")
        self.price_value.setText(f"{price:,.2f}")
        self.change_value.setText(percent(change))
        self.change_value.setStyleSheet(f"color: {'#14b8a6' if change >= 0 else '#f43f5e'};")
        self.market_cap_caption.setText("OPEN INTEREST" if asset_type == "Derivative" else "MARKET CAP")
        self.market_cap_value.setText(regional_money(float(data.get("market_cap", 0.0)), region, compact=True))
        self.open_interest_value.setText(regional_money(float(data.get("open_interest", 0.0)), region, compact=True))
        self.region_value.setText(display_label(region))
        self.driver_value.setText(driver_summary(data, asset_type))
        self.driver_value.setToolTip(driver_summary(data, asset_type))
        self._set_order_mode(asset_type, data)
        self._update_order_value()

    def _update_performance(self, points: list[float]) -> None:
        if len(points) < 2 or points[0] == 0:
            self.performance_value.setText("-")
            self.performance_value.setStyleSheet("")
            return
        value = ((points[-1] / points[0]) - 1.0) * 100.0
        self.performance_value.setText(percent(value))
        self.performance_value.setStyleSheet(f"color: {'#14b8a6' if value >= 0 else '#f43f5e'};")

    def _history_entries(self, data: dict[str, Any]) -> list[Any]:
        return list(data.get("historie", []))

    def _history_points(self, history: list[Any]) -> list[float]:
        points = []
        for entry in history:
            try:
                points.append(history_close(entry))
            except (TypeError, ValueError):
                continue
        return points

    def _draw_chart(self, points: list[float], history: list[Any]) -> None:
        self.chart_draw_count += 1
        self.last_candle_count = 0
        self._chart_points = list(points)
        self._chart_history = list(history)

        if len(points) >= 2:
            color = "#14b8a6" if points[-1] >= points[0] else "#f43f5e"
            if self.chart_mode == "Candle":
                self.chart_view.plot_candles(history, range_points=self.range_points, title="Price History")
                self.last_candle_count = self.chart_view.last_candle_count
                self.last_candle_interval = self.chart_view.last_candle_interval
            else:
                self.chart_view.plot_line(points, dates=[history_date(item) for item in history], color=color, title="Price History", label="Price")
            self.chart_view.set_loading(bool(data_loading(self.current_asset[2])), has_data=True)
        else:
            self.chart_view.set_loading(bool(data_loading(self.current_asset[2])), has_data=False)
            if not data_loading(self.current_asset[2]):
                self.chart_view.show_message("History builds as the simulation runs")

    def _draw_positioning(self, data: dict[str, Any]) -> None:
        long_interest = float(data.get("long_interest", 0.0))
        short_interest = float(data.get("short_interest", 0.0))
        if long_interest <= 0.0 and short_interest <= 0.0:
            self.positioning_view.setVisible(False)
            return
        self.positioning_view.setVisible(True)
        squeeze = float(data.get("squeeze_pressure", 0.0))
        title = "Long / Short Interest"
        if squeeze > 0:
            title = "Long / Short Interest - Short Squeeze"
        elif squeeze < 0:
            title = "Long / Short Interest - Long Squeeze"
        self.positioning_view.plot_long_short_heatmap(long_interest, short_interest, title=title)

    def _redraw_live_line(self, points: list[float]) -> None:
        if len(points) < 2:
            return
        color = "#14b8a6" if points[-1] >= points[0] else "#f43f5e"
        self.chart_view.plot_line(
            points,
            dates=[history_date(item) for item in self._chart_history],
            color=color,
            title="Price History",
            label="Price",
        )

    def _set_order_mode(self, asset_type: str, data: dict[str, Any]) -> None:
        can_trade_spot = asset_type in self.SPOT_AND_PERPETUAL_ASSETS | {"Fund"} or (
            asset_type == "Derivative" and derivative_allows_spot_trade(data)
        )
        can_trade_perpetual = self._can_trade_perpetual(asset_type, data)
        self.order_panel.setVisible(can_trade_spot)
        self.buy_button.setVisible(can_trade_spot)
        self.sell_button.setVisible(can_trade_spot)
        self.order_quantity.setVisible(can_trade_spot)
        self.order_total_value.setVisible(can_trade_spot)
        self.order_leverage_label.setVisible(can_trade_perpetual)
        self.order_leverage.setVisible(can_trade_perpetual)
        self.long_button.setVisible(can_trade_perpetual)
        self.short_button.setVisible(can_trade_perpetual)
        self._update_order_value()

    def _can_trade_perpetual(self, asset_type: str, data: dict[str, Any]) -> bool:
        return asset_type in self.SPOT_AND_PERPETUAL_ASSETS or (
            asset_type == "Derivative" and data.get("instrument_type") in EXPIRING_DERIVATIVE_CONTRACT_TYPES
        )

    def _trade_is_valid(self, side: str, amount: float) -> bool:
        if self.state is None or self.current_asset is None:
            return True
        ticker, _asset_type, _data = self.current_asset
        mode = "SPOT" if side in {"BUY", "SELL"} else "FUTURE"
        return validate_trade_request(self.state, ticker, mode, side, amount, self._selected_leverage()).is_valid

    def _update_trade_buttons(self, quantity: float, margin: float) -> None:
        if self.current_asset is None:
            return
        for side, button, amount in [
            ("BUY", self.buy_button, quantity),
            ("SELL", self.sell_button, quantity),
            ("LONG", self.long_button, margin),
            ("SHORT", self.short_button, margin),
        ]:
            if not button.isVisible():
                continue
            button.setEnabled(amount > 0.0 and self._trade_is_valid(side, amount))


def data_loading(data: dict[str, Any]) -> bool:
    return bool(data.get("_history_loading") or data.get("_history_refreshing"))
