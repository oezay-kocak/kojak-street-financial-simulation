"""Portfolio workspace view."""

from __future__ import annotations

from kojakstreet.core.accounting import convert_amount
from kojakstreet.ui_qt.formatters import gold_dinar, regional_money

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from kojakstreet.core.bond_portfolio_details import owned_bond_details
from kojakstreet.core.portfolio import PortfolioAnalytics, build_portfolio_analytics
from kojakstreet.core.state import GameState
from kojakstreet.core.trading import liquidation_price
from kojakstreet.ui_qt.display import display_label, display_text
from kojakstreet.ui_qt.formatters import compact_money, money, percent
from kojakstreet.ui_qt.models.simple_table_model import SimpleTableModel
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.views.forex_view import (
    _currency_display_code,
    _region_from_currency_code,
    _state_currency_strength,
)
from kojakstreet.ui_qt.widgets.asset_chart_panel import AssetChartPanel
from kojakstreet.ui_qt.widgets.empty_state import EmptyState
from kojakstreet.ui_qt.widgets.qt_chart import FastChartView
from kojakstreet.ui_qt.widgets.view_header import ViewHeader


class PortfolioView(QFrame):
    """Portfolio overview backed by the current legacy snapshot."""

    def __init__(
        self,
        state: GameState,
        trade_handler: Callable[[str, str, str, float, int], None] | None = None,
        close_future_handler: Callable[[str], None] | None = None,
        forex_handler: Callable[[str, str, float], None] | None = None,
    ) -> None:
        super().__init__()
        self.state = state
        self.trade_handler = trade_handler
        self.close_future_handler = close_future_handler
        self.forex_handler = forex_handler
        self.analytics = build_portfolio_analytics(state)
        self.row_metadata: list[dict[str, str]] = []
        self.kpi_values: dict[str, QLabel] = {}
        self.setObjectName("Panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(
            ViewHeader(
                "Portfolio",
                "Positions, PnL, cash balances, loans and bonds from the current simulation state",
                ["Revalue", "Export"],
            )
        )
        self.kpi_grid = self._build_kpis()
        layout.addLayout(self.kpi_grid)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_tabs())
        splitter.addWidget(self._build_management_panel())
        splitter.setSizes([780, 430])
        layout.addWidget(splitter, 1)
        if self.positions_model.rowCount():
            self.positions_table.selectRow(0)

    def refresh(self, state: GameState, *, throttle_charts: bool = False) -> None:
        self.state = state
        if hasattr(self, "chart_panel"):
            self.chart_panel.set_state(state)
        self.analytics = build_portfolio_analytics(state)
        self._update_kpis()
        self._populate_positions_table()
        self._populate_bonds_table()
        self._populate_currency_table()
        self._update_currency_preview()
        self._update_empty_state()
        if not throttle_charts:
            self._show_selected_position()

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setObjectName("PortfolioTabs")

        assets_tab = QWidget()
        assets_layout = QVBoxLayout(assets_tab)
        assets_layout.setContentsMargins(0, 0, 0, 0)
        self.positions_table = self._build_positions_table()
        assets_layout.addWidget(self.positions_table)

        bonds_tab = QWidget()
        bonds_layout = QVBoxLayout(bonds_tab)
        bonds_layout.setContentsMargins(0, 0, 0, 0)
        self.bonds_table = self._build_bonds_table()
        bonds_layout.addWidget(self.bonds_table)

        currencies_tab = QWidget()
        currencies_layout = QVBoxLayout(currencies_tab)
        currencies_layout.setContentsMargins(0, 0, 0, 0)
        currencies_layout.setSpacing(10)
        self.currency_table = self._build_currency_table()
        currencies_layout.addWidget(self.currency_table, 1)
        currencies_layout.addWidget(self._build_currency_trade_panel())

        tabs.addTab(assets_tab, "Assets")
        tabs.addTab(bonds_tab, "Bonds")
        tabs.addTab(currencies_tab, "Currencies")
        return tabs

    def _build_kpis(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self._add_kpi(grid, "Cash", gold_dinar(self.state.cash), 0, 0)
        self._add_kpi(grid, "Invested", gold_dinar(self.analytics.total_value_gd), 0, 1)
        self._add_kpi(
            grid,
            "Unrealized PnL",
            f"{gold_dinar(self.analytics.unrealized_pnl_gd)} ({percent(self.analytics.unrealized_pnl_percent)})",
            0,
            2,
            self.analytics.unrealized_pnl_gd,
        )
        self._add_kpi(grid, "Positions", str(len(self.analytics.positions)), 0, 3)
        self._add_kpi(grid, "Loans", gold_dinar(sum(convert_amount(self.state, amount, region, "GD") for region, amount in self.state.loans.items())), 0, 4)
        self._add_kpi(grid, "Gross Exposure", gold_dinar(self.analytics.gross_exposure_gd), 1, 0)
        self._add_kpi(grid, "Leveraged", gold_dinar(self.analytics.leveraged_exposure_gd), 1, 1)
        return grid

    def apply_live_current_rows(self, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        row = rows[0]
        self._set_kpi("Cash", gold_dinar(float(row.get("cash", self.state.cash))))
        self._set_kpi("Positions", str(int(row.get("positions", len(self.analytics.positions)))))
        futures = int(row.get("futures", len(self.state.perpetuals)))
        if futures:
            self._set_kpi("Positions", f"{int(row.get('positions', 0))} + {futures}F")

    def _add_kpi(
        self,
        grid: QGridLayout,
        label: str,
        value: str,
        row: int,
        column: int,
        signed_value: float | None = None,
    ) -> None:
        box = QVBoxLayout()
        caption = QLabel(label.upper())
        caption.setObjectName("Muted")
        main = QLabel(value)
        main.setObjectName("DetailValue")
        if signed_value is not None:
            main.setStyleSheet(f"color: {'#14b8a6' if signed_value >= 0 else '#f43f5e'};")
        self.kpi_values[label] = main
        box.addWidget(caption)
        box.addWidget(main)
        grid.addLayout(box, row, column)

    def _update_kpis(self) -> None:
        self._set_kpi("Cash", gold_dinar(self.state.cash))
        self._set_kpi("Invested", gold_dinar(self.analytics.total_value_gd))
        self._set_kpi(
            "Unrealized PnL",
            f"{gold_dinar(self.analytics.unrealized_pnl_gd)} ({percent(self.analytics.unrealized_pnl_percent)})",
            self.analytics.unrealized_pnl_gd,
        )
        self._set_kpi("Positions", str(len(self.analytics.positions)))
        self._set_kpi("Loans", gold_dinar(sum(convert_amount(self.state, amount, region, "GD") for region, amount in self.state.loans.items())))
        self._set_kpi("Gross Exposure", gold_dinar(self.analytics.gross_exposure_gd))
        self._set_kpi("Leveraged", gold_dinar(self.analytics.leveraged_exposure_gd))

    def _set_kpi(self, label: str, value: str, signed_value: float | None = None) -> None:
        widget = self.kpi_values.get(label)
        if widget is None:
            return
        widget.setText(value)
        if signed_value is not None:
            widget.setStyleSheet(f"color: {'#14b8a6' if signed_value >= 0 else '#f43f5e'};")

    def _build_positions_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("PositionsTable")
        self.positions_model = SimpleTableModel(
            [
                "Mode",
                "Ticker",
                "Name",
                "Type",
                "Region",
                "Sector",
                "Qty",
                "Avg",
                "Last",
                "Value",
                "Expiry",
                "PnL / Liq",
            ],
            right_aligned_columns={6, 7, 8, 9, 10, 11},
            color_callback=self._position_cell_color,
        )
        table.setModel(self.positions_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        optimize_table_view(table, row_height=34)

        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate((90, 90, 180, 90, 90, 130, 80, 90, 90, 120, 100, 170)):
            table.setColumnWidth(column, width)
        table.selectionModel().selectionChanged.connect(lambda *_: self._show_selected_position())
        self.positions_table = table
        self._populate_positions_table()
        return table

    def _populate_positions_table(self) -> None:
        table = self.positions_table
        rows = self._position_rows()
        self.row_metadata = [row["_meta"] for row in rows]
        if not rows:
            table.setMinimumHeight(180)
        self.positions_model.set_rows([row["values"] for row in rows], metadata=rows)

    def _position_cell_color(self, _values: list[str], row: object, column: int) -> QColor | None:
        if isinstance(row, dict) and column == 11:
            signed = float(row.get("signed", 0.0))
            return QColor("#14b8a6" if signed >= 0 else "#f43f5e")
        return None

    def _build_bonds_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("PortfolioBondsTable")
        self.bonds_model = SimpleTableModel(
            ["Type", "Issuer", "Region", "Nominal", "Market Value", "Coupon", "Remaining", "Duration", "YTM", "Rating", "Default Risk", "Meta"],
            right_aligned_columns={3, 4, 5, 6, 7, 8, 10},
        )
        table.setModel(self.bonds_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        optimize_table_view(table, row_height=34)
        self._populate_bonds_table()
        return table

    def _populate_bonds_table(self) -> None:
        if not hasattr(self, "bonds_table"):
            return
        rows = self._bond_rows()
        self.bonds_model.set_rows(rows)

    def _build_currency_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("PortfolioCurrenciesTable")
        self.currency_model = SimpleTableModel(
            ["Currency", "Region", "Amount", "Strength"],
            right_aligned_columns={2, 3},
        )
        table.setModel(self.currency_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        optimize_table_view(table, row_height=34)
        self._populate_currency_table()
        return table

    def _populate_currency_table(self) -> None:
        if not hasattr(self, "currency_table"):
            return
        rows = []
        for region, amount in sorted(self.state.fx_balances.items()):
            if amount:
                rows.append([
                    _currency_display_code(region),
                    display_label(region),
                    f"{amount:,.2f}",
                    f"{_state_currency_strength(self.state, region):.4f}",
                ])
        self.currency_model.set_rows(rows)

    def _build_currency_trade_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PanelInner")
        row = QHBoxLayout(panel)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(8)
        options = sorted({_currency_display_code(region) for region in set(self.state.fx_balances) | set(self.state.currency_strength) | {"GD"}})
        self.currency_source = QComboBox()
        self.currency_source.setMinimumWidth(110)
        self.currency_source.addItems(options)
        self.currency_target = QComboBox()
        self.currency_target.setMinimumWidth(110)
        self.currency_target.addItems(options)
        if "GLD" in options:
            self.currency_source.setCurrentText("GLD")
        target_default = next((option for option in options if option != self.currency_source.currentText()), options[0])
        self.currency_target.setCurrentText(target_default)
        self.currency_amount = QLineEdit()
        self.currency_amount.setPlaceholderText("Amount")
        self.currency_preview = QLabel("Receive -")
        self.currency_preview.setObjectName("DetailValue")
        exchange_button = QPushButton("Exchange")
        exchange_button.setObjectName("ActionButton")
        exchange_button.clicked.connect(self._execute_currency_trade)
        self.currency_source.currentTextChanged.connect(self._update_currency_preview)
        self.currency_target.currentTextChanged.connect(self._update_currency_preview)
        self.currency_amount.textChanged.connect(self._update_currency_preview)
        row.addWidget(QLabel("From"))
        row.addWidget(self.currency_source)
        row.addWidget(QLabel("To"))
        row.addWidget(self.currency_target)
        row.addWidget(self.currency_amount)
        row.addWidget(self.currency_preview, 1)
        row.addWidget(exchange_button)
        return panel

    def _execute_currency_trade(self) -> None:
        if self.forex_handler is None:
            return
        amount = self._currency_amount_value()
        if amount <= 0:
            return
        self.forex_handler(
            _region_from_currency_code(self.currency_source.currentText()),
            _region_from_currency_code(self.currency_target.currentText()),
            amount,
        )

    def _currency_amount_value(self) -> float:
        try:
            return float(self.currency_amount.text().replace(",", "."))
        except (AttributeError, ValueError):
            return 0.0

    def _update_currency_preview(self) -> None:
        if not hasattr(self, "currency_preview"):
            return
        amount = self._currency_amount_value()
        source = _region_from_currency_code(self.currency_source.currentText())
        target = _region_from_currency_code(self.currency_target.currentText())
        if amount > 0 and source != target:
            received = amount * (_state_currency_strength(self.state, source) / _state_currency_strength(self.state, target))
            self.currency_preview.setText(f"Receive {received:,.2f} {self.currency_target.currentText()}")
        else:
            self.currency_preview.setText("Receive -")

    def _position_rows(self) -> list[dict[str, object]]:
        rows = []
        for position in self.analytics.positions:
            asset = self._all_assets().get(position.ticker, {})
            raw_position = self.state.portfolio.get(position.ticker, {})
            mode = _spot_position_mode(asset)
            rows.append(
                {
                    "_meta": {"ticker": position.ticker, "asset_type": position.asset_type, "position_id": "", "mode": "SPOT"},
                    "signed": position.pnl_local,
                    "values": [
                        mode,
                        position.ticker,
                        display_text(position.name),
                        position.asset_type,
                        display_label(position.region),
                        display_label(position.sector),
                        f"{position.quantity:,.2f}",
                        f"{position.average_price:,.2f}",
                        f"{position.last_price:,.2f}",
                        regional_money(position.value_local, position.region),
                        _expiry_label(raw_position.get("expires_at") or asset.get("expires_at")),
                        f"{regional_money(position.pnl_local, position.region)} ({percent(position.pnl_percent)})",
                    ],
                }
            )
        assets = self._all_assets()
        for position_id, position in self.state.perpetuals.items():
            ticker = str(position.get("ticker", ""))
            asset = assets.get(ticker, {})
            last = float(asset.get("kurs", 0.0))
            entry = float(position.get("einstiegskurs", 0.0))
            quantity = float(position.get("groesse", 0.0))
            margin = float(position.get("margin", 0.0))
            direction = str(position.get("typ", "LONG"))
            pnl = (last - entry) * quantity if direction == "LONG" else (entry - last) * quantity
            value = max(0.0, margin + pnl)
            rows.append(
                {
                    "_meta": {
                        "ticker": ticker,
                        "asset_type": self._asset_type_for_ticker(ticker),
                        "position_id": position_id,
                        "mode": "FUTURE",
                    },
                    "signed": pnl,
                    "values": [
                        f"{direction} {int(position.get('hebel', 1))}x",
                        ticker,
                        display_text(asset.get("name", ticker)),
                        self._asset_type_for_ticker(ticker),
                        display_label(position.get("land", "GD")),
                        display_label(asset.get("branche", asset.get("kategorie", asset.get("typ", "")))),
                        f"{quantity:,.2f}",
                        f"{entry:,.2f}",
                        f"{last:,.2f}",
                        regional_money(value, str(position.get("land", "GD"))),
                        _expiry_label(position.get("expires_at")),
                        f"{regional_money(pnl, str(position.get("land", "GD")))} | Liq {liquidation_price(position):,.2f}",
                    ],
                }
            )
        return rows

    def _build_management_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PanelInner")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self.chart_panel = AssetChartPanel(self.state)
        self.chart_panel.chart_view.setMinimumHeight(190)
        self.chart_panel.positioning_view.setMaximumHeight(112)
        if self.trade_handler is not None:
            self.chart_panel.trade_requested.connect(self.trade_handler)
        self.empty_state = EmptyState(
            "No open positions",
            "Use the market chart ticket to build a portfolio.",
        )
        self.empty_state.setObjectName("PortfolioEmptyState")
        self.close_future_button = QPushButton("Close Future")
        self.close_future_button.setObjectName("ActionButton")
        self.close_future_button.clicked.connect(self._close_selected_future)
        self.close_future_button.setVisible(False)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.chart_panel, 1)
        layout.addWidget(self.close_future_button)
        self._update_empty_state()
        return panel

    def _show_selected_position(self) -> None:
        current = self.positions_table.currentIndex().row()
        if current < 0 or current >= len(self.row_metadata):
            self.close_future_button.setEnabled(False)
            self.close_future_button.setVisible(False)
            return
        meta = self.row_metadata[current]
        provider = getattr(self, "scope_provider", None)
        identity = (meta["asset_type"], meta["ticker"])
        if provider is not None and getattr(self, "_scope_position", None) != identity:
            self.state = provider({"view": "portfolio", "selection": {"kind": identity[0], "ticker": identity[1]}})
            self._scope_position = identity
        data = self._all_assets().get(meta["ticker"])
        if not data:
            return
        self.chart_panel.update_asset(meta["ticker"], meta["asset_type"], data)
        is_future = meta["mode"] == "FUTURE"
        self.close_future_button.setEnabled(is_future)
        self.close_future_button.setVisible(is_future)

    def _update_empty_state(self) -> None:
        if not hasattr(self, "empty_state") or not hasattr(self, "chart_panel"):
            return
        has_positions = bool(self.analytics.positions or self.state.perpetuals)
        self.empty_state.setVisible(not has_positions)
        self.chart_panel.setVisible(has_positions)
        if not has_positions and hasattr(self, "close_future_button"):
            self.close_future_button.setVisible(False)

    def _close_selected_future(self) -> None:
        current = self.positions_table.currentIndex().row()
        if current < 0 or current >= len(self.row_metadata) or self.close_future_handler is None:
            return
        position_id = self.row_metadata[current].get("position_id", "")
        if position_id:
            self.close_future_handler(position_id)

    def _all_assets(self) -> dict[str, dict]:
        assets = {}
        assets.update(self.state.stocks)
        assets.update(self.state.commodities)
        assets.update(self.state.cryptos)
        assets.update(self.state.funds)
        assets.update(self.state.indices)
        assets.update(self.state.derivatives)
        return assets

    def _asset_type_for_ticker(self, ticker: str) -> str:
        if ticker in self.state.stocks:
            return "Stock"
        if ticker in self.state.commodities:
            return "Commodity"
        if ticker in self.state.cryptos:
            return "Crypto"
        if ticker in self.state.funds:
            return "Fund"
        if ticker in self.state.indices:
            return "Index"
        if ticker in self.state.derivatives:
            return "Derivative"
        return "Other"

    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PanelInner")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._build_exposure_chart(), 1)
        layout.addWidget(self._build_exposure_table(), 1)
        layout.addWidget(self._build_balances_table(), 1)
        if not self.analytics.positions:
            layout.insertWidget(
                0,
                EmptyState(
                    "No open positions",
                    "Use the legacy app or future trading controls to build a portfolio.",
                ),
            )
        return panel

    def _build_exposure_chart(self) -> FastChartView:
        view = FastChartView(title="Region Exposure")
        exposure = self._top_items(self.analytics.region_exposure, 6)
        values = [item[1] for item in exposure]
        if values:
            view.plot_line(values, color="#22d3ee", title="Region Exposure", label="Exposure")
        else:
            view.show_message("No portfolio exposure")
        return view

    def _build_exposure_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("ExposureTable")
        model = SimpleTableModel(["Bucket", "Name", "Value", "Share"], right_aligned_columns={2, 3})
        table.setModel(model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        optimize_table_view(table, row_height=32)

        rows = self._exposure_rows(self.analytics)
        model.set_rows(rows)
        return table

    def _exposure_rows(self, analytics: PortfolioAnalytics) -> list[list[str]]:
        rows: list[list[str]] = []
        rows.extend(self._bucket_rows("Region", analytics.region_exposure))
        rows.extend(self._bucket_rows("Sector", self._top_dict(analytics.sector_exposure, 5)))
        rows.extend(self._bucket_rows("Type", analytics.asset_type_exposure))
        return rows

    def _bucket_rows(self, bucket: str, exposure: dict[str, float]) -> list[list[str]]:
        rows = []
        total = sum(exposure.values())
        for name, value in self._top_items(exposure, 8):
            share = (value / total * 100.0) if total else 0.0
            rows.append([bucket, display_label(name), gold_dinar(value), percent(share)])
        return rows

    def _top_dict(self, values: dict[str, float], limit: int) -> dict[str, float]:
        return dict(self._top_items(values, limit))

    def _top_items(self, values: dict[str, float], limit: int) -> list[tuple[str, float]]:
        return sorted(values.items(), key=lambda item: item[1], reverse=True)[:limit]

    def _build_balances_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("BalancesTable")
        model = SimpleTableModel(["Type", "Region", "Amount", "Meta"], right_aligned_columns={2})
        table.setModel(model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        optimize_table_view(table, row_height=32)

        rows = self._balance_rows()
        model.set_rows(rows)
        return table

    def _balance_rows(self) -> list[list[str]]:
        rows = [["Cash", "GD", gold_dinar(self.state.cash), "Reserve currency"]]
        rows.extend(
            ["FX", display_label(region), f"{amount:,.2f}", "Foreign balance"]
            for region, amount in self.state.fx_balances.items()
            if amount
        )
        rows.extend(
            ["Loan", display_label(region), f"{amount:,.2f}", "Outstanding"]
            for region, amount in self.state.loans.items()
            if amount
        )
        for bond in self.state.bonds:
            rows.append([
                "Bond",
                display_label(str(bond.get("land", ""))),
                f"{float(bond.get('nominal', 0.0)):,.2f}",
                str(bond.get("typ", "Held")),
            ])
        return rows

    def _bond_rows(self) -> list[list[str]]:
        rows = []
        for bond in owned_bond_details(self.state):
            rows.append([
                display_label(bond.bond_type),
                display_text(bond.issuer),
                display_label(bond.region),
                f"{bond.nominal:,.2f}",
                f"{bond.market_value:,.2f}",
                percent(bond.coupon * 100),
                f"{bond.remaining_years:.1f}Y",
                f"{bond.duration:.1f}Y",
                percent(bond.yield_to_maturity * 100),
                bond.rating,
                percent(bond.default_risk * 100),
                bond.meta,
            ])
        return rows


def _spot_position_mode(asset: dict) -> str:
    instrument_type = str(asset.get("instrument_type", ""))
    if instrument_type == "Credit Default Swap":
        return "CDS"
    if instrument_type:
        return instrument_type
    return "Spot"


def _expiry_label(value: object) -> str:
    if not value:
        return "-"
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return f"{text[8:10]}.{text[5:7]}.{text[0:4]}"
    return text
