"""Global macro dashboard with KPI cards, table overview and lazy detail charts."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from kojakstreet.core.global_macro import METRICS
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.formatters import compact_money, percent
from kojakstreet.ui_qt.models.simple_table_model import METADATA_ROLE, SimpleTableModel
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.widgets.stock_detail_dialog import StockDetailView
from kojakstreet.ui_qt.widgets.view_header import ViewHeader


class GlobalMacroView(QFrame):
    def __init__(self, state: GameState) -> None:
        super().__init__()
        self.state = state
        self.setObjectName("Panel")
        self.kpi_values: dict[str, QLabel] = {}
        self.table: QTableView | None = None
        self.table_row_by_key: dict[str, dict] = {}
        self.pages = QStackedWidget()
        self.main_page = QWidget()
        self.detail_view = StockDetailView()
        self.detail_view.back_requested.connect(self._show_macro_list)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        main_layout = QVBoxLayout(self.main_page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        layout.addWidget(
            ViewHeader(
                "Global Macro",
                "Global liquidity, rates, inflation, growth and volatility regime",
                ["Refresh", "Export"],
            )
        )
        main_layout.addWidget(self._build_kpis())
        main_layout.addWidget(self._build_table(), 1)
        self.pages.addWidget(self.main_page)
        self.pages.addWidget(self.detail_view)
        layout.addWidget(self.pages, 1)
        self._refresh_content()

    def refresh(self, state: GameState, *, throttle_charts: bool = False) -> None:
        self.state = state
        self._refresh_content()
        if self.pages.currentWidget() is self.detail_view and self.detail_view.ticker:
            self._update_detail(self.detail_view.ticker)

    def _build_kpis(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("PanelInner")
        grid = QGridLayout(frame)
        grid.setContentsMargins(10, 8, 10, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        kpi_keys = [
            "global_m2",
            "net_liquidity",
            "avg_3y_yield",
            "avg_10y_yield",
            "global_cpi",
            "vix",
        ]
        for index, key in enumerate(kpi_keys):
            card = self._kpi_card(key)
            grid.addWidget(card, index // 3, index % 3)
        return frame

    def _kpi_card(self, key: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("KpiCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        caption = QLabel(METRICS[key].upper())
        caption.setObjectName("Muted")
        value = QLabel("-")
        value.setObjectName("DetailValue")
        self.kpi_values[key] = value
        layout.addWidget(caption)
        layout.addWidget(value)
        return frame

    def _build_table(self) -> QTableView:
        table = QTableView()
        self.table = table
        table.setObjectName("GlobalMacroTable")
        self.table_model = SimpleTableModel(
            ["Indicator", "Current", "Daily Change", "30D Change", "Market Impact"],
            right_aligned_columns={1, 2, 3},
            color_callback=self._table_cell_color,
        )
        table.setModel(self.table_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.setSortingEnabled(True)
        table.doubleClicked.connect(lambda index: self._open_metric_detail(index.row()))
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        optimize_table_view(table, row_height=34)
        self._fill_table()
        return table

    def _refresh_content(self) -> None:
        for key, widget in self.kpi_values.items():
            widget.setText(self._format_value(key, float(self.state.global_macro.get(key, 0.0))))
        self._fill_table()

    def _fill_table(self) -> None:
        if self.table is None:
            return
        selected_key = self._selected_key()
        sort_section = self.table.horizontalHeader().sortIndicatorSection()
        sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        rows = self._rows()
        self.table_row_by_key = {str(row["key"]): row for row in rows}
        self.table.setSortingEnabled(False)
        self.table_model.set_rows(
            [row["values"] for row in rows],
            metadata=[row["key"] for row in rows],
            sort_values=[row["sort_values"] for row in rows],
        )
        self.table.setSortingEnabled(True)
        if sort_section >= 0:
            self.table_model.sort(sort_section, sort_order)
            self.table.horizontalHeader().setSortIndicator(sort_section, sort_order)
        self._select_key(selected_key)

    def _table_cell_color(self, _row: list[str], key: object, column: int) -> QColor | None:
        if not isinstance(key, str):
            return None
        if column in {2, 3}:
            metric = self.table_row_by_key.get(key)
            if metric is not None:
                return QColor("#14b8a6" if metric["sort_values"][column] >= 0 else "#f43f5e")
        return None

    def _selected_key(self) -> str | None:
        if self.table is None:
            return None
        current = self.table.currentIndex().row()
        if current < 0:
            return None
        key = self.table_model.index(current, 0).data(METADATA_ROLE)
        return key if isinstance(key, str) else None

    def _select_key(self, key: str | None) -> None:
        if self.table is None or key is None:
            return
        for row in range(self.table_model.total_row_count()):
            if self.table_model.metadata_at(row) == key:
                self.table_model.ensure_row_loaded(row)
                selection_model = self.table.selectionModel()
                selection_model.blockSignals(True)
                self.table.selectRow(row)
                selection_model.blockSignals(False)
                return

    def _rows(self) -> list[dict]:
        rows = []
        for key, label in METRICS.items():
            history = self._history_values(key)
            current = float(self.state.global_macro.get(key, history[-1] if history else 0.0))
            daily = _change_value(history, 1, key)
            monthly = _change_value(history, 30, key)
            rows.append(
                {
                    "key": key,
                    "values": [
                        label,
                        self._format_value(key, current),
                        self._format_change(key, daily),
                        self._format_change(key, monthly),
                        _impact_text(key),
                    ],
                    "sort_values": [
                        label.lower(),
                        current,
                        daily,
                        monthly,
                        _impact_text(key).lower(),
                    ],
                }
            )
        return rows

    def _open_metric_detail(self, row: int) -> None:
        if self.table is None or row < 0:
            return
        key = self.table_model.index(row, 0).data(METADATA_ROLE)
        if isinstance(key, str):
            self._update_detail(key)
            self.pages.setCurrentWidget(self.detail_view)

    def _update_detail(self, key: str) -> None:
        if key == "yield_curve_3y10y":
            history = [
                (float(self.state.global_macro.get("avg_3y_yield", 0.0)) * 100.0, "", ""),
                (float(self.state.global_macro.get("avg_5y_yield", 0.0)) * 100.0, "", ""),
                (float(self.state.global_macro.get("avg_10y_yield", 0.0)) * 100.0, "", ""),
            ]
            self.detail_view.update_asset(
                key,
                {
                    "name": METRICS.get(key, key),
                    "historie": history,
                    "kurs": float(self.state.global_macro.get(key, 0.0)) * 100.0,
                    "aenderung": _change_value(self._history_values(key), 1, key),
                    "yield_curve_terms": ["3Y", "5Y", "10Y"],
                },
                "GlobalMacro",
            )
            return

        raw_history = list(self.state.global_macro_history.get(key, []))
        history = _display_history(key, raw_history)
        current = float(self.state.global_macro.get(key, 0.0))
        display_current = current * 100.0 if key in _PERCENT_KEYS else current
        if len(history) < 2:
            history = [(display_current, "", ""), (display_current, "", "")]
        self.detail_view.update_asset(
            key,
            {
                "name": METRICS.get(key, key),
                "historie": history,
                "kurs": display_current,
                "aenderung": _change_value(self._history_values(key), 1, key),
            },
            "GlobalMacro",
        )

    def _show_macro_list(self) -> None:
        self.pages.setCurrentWidget(self.main_page)

    def _history_values(self, key: str) -> list[float]:
        values = []
        for entry in self.state.global_macro_history.get(key, [])[-520:]:
            try:
                values.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
            except (TypeError, ValueError):
                continue
        return values

    def _format_value(self, key: str, value: float) -> str:
        if key in _YIELD_KEYS:
            return f"{value * 100.0:+.3f}%"
        if key in _PERCENT_KEYS:
            return percent(value * 100.0)
        if key == "vix":
            return f"{value:.2f}"
        return compact_money(value)

    def _format_change(self, key: str, value: float) -> str:
        if key in _YIELD_KEYS or key == "yield_curve_3y10y":
            return f"{value:+.3f} pp"
        if key in _PERCENT_KEYS:
            return f"{value:+.2f} pp"
        if key == "vix":
            return f"{value:+.2f}"
        return percent(value)


def _change_value(history: list[float], lookback: int, key: str) -> float:
    if len(history) <= lookback:
        return 0.0
    current = history[-1]
    previous = history[-1 - lookback]
    if key in _PERCENT_KEYS or key == "vix":
        return (current - previous) * (100.0 if key in _PERCENT_KEYS else 1.0)
    return ((current - previous) / previous) * 100.0 if previous else 0.0


def _display_history(key: str, history: list) -> list:
    if key not in _PERCENT_KEYS:
        return history
    converted = []
    for entry in history:
        if isinstance(entry, (tuple, list)) and entry:
            converted.append((float(entry[0]) * 100.0, *entry[1:]))
        else:
            converted.append(float(entry) * 100.0)
    return converted


def _impact_text(key: str) -> str:
    impacts = {
        "global_m2": "Net liquidity component",
        "central_bank_balance_sheets": "Net liquidity component",
        "rrp": "Drains net liquidity",
        "tga": "Drains net liquidity",
        "net_liquidity": "Stocks and crypto",
        "yield_curve_3y10y": "Stocks when inverted",
        "avg_3y_yield": "Short-rate expectations",
        "avg_5y_yield": "Curve belly and funding reference",
        "avg_10y_yield": "Bond valuation context",
        "global_cpi": "Macro regime reference",
        "global_gdp_growth": "Macro regime reference",
        "global_unemployment": "Macro regime reference",
        "expected_global_growth": "Market growth expectation",
        "expected_global_cpi": "Inflation expectation",
        "expected_avg_policy_rate": "Policy-rate expectation",
        "macro_surprise_index": "Report surprise impulse",
        "vix": "Stock risk pressure",
        "regime_risk_score": "Risk-on / risk-off regime",
        "regime_inflation_score": "Inflation regime pressure",
        "regime_growth_score": "Growth regime pressure",
        "regime_liquidity_score": "Liquidity regime pressure",
        "regime_credit_stress": "Credit-stress regime pressure",
    }
    return impacts.get(key, "Reference")


_PERCENT_KEYS = {
    "yield_curve_3y10y",
    "avg_3y_yield",
    "avg_5y_yield",
    "avg_10y_yield",
    "global_cpi",
    "global_gdp_growth",
    "global_unemployment",
    "expected_global_growth",
    "expected_global_cpi",
    "expected_avg_policy_rate",
    "macro_surprise_index",
    "regime_risk_score",
    "regime_inflation_score",
    "regime_growth_score",
    "regime_liquidity_score",
    "regime_credit_stress",
}

_YIELD_KEYS = {
    "avg_3y_yield",
    "avg_5y_yield",
    "avg_10y_yield",
    "expected_avg_policy_rate",
}
