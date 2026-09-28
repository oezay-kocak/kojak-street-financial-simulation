"""Macro workspace view."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from kojakstreet.core.macro import CountryMacroAnalytics, MacroAnalytics, build_macro_analytics
from kojakstreet.core.ratings import default_probability, normalize_rating
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.display import display_label
from kojakstreet.ui_qt.formatters import compact_money, percent
from kojakstreet.ui_qt.models.simple_table_model import METADATA_ROLE, SimpleTableModel
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.widgets.qt_chart import FastChartView
from kojakstreet.ui_qt.widgets.view_header import ViewHeader


class MacroView(QFrame):
    """Read-only macro dashboard for countries and central-bank variables."""

    def __init__(
        self,
        state: GameState,
        history_provider: Callable[[str, str, int], list[float]] | None = None,
        current_provider: Callable[[], list[dict[str, object]]] | None = None,
    ) -> None:
        super().__init__()
        self.state = state
        self.history_provider = history_provider
        self.current_provider = current_provider
        self.current_country_rows: dict[str, dict[str, object]] = {}
        self.analytics = build_macro_analytics(state, include_trends=False)
        self.macro_table: QTableView | None = None
        self.kpi_values: dict[str, QLabel] = {}
        self.pages = QStackedWidget()
        self.main_page = QWidget()
        self.detail_view = CountryDetailView(state, history_provider)
        self.metric_detail = RegionalMetricDetailPanel()
        self.setObjectName("Panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        main_layout = QVBoxLayout(self.main_page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)
        main_layout.addWidget(
            ViewHeader(
                "Macro",
                "Country growth, inflation, unemployment and monetary policy snapshot",
                ["Refresh", "Scenario"],
            )
        )
        main_layout.addLayout(self._build_kpis())

        main_layout.addWidget(self._build_macro_table(), 1)
        self.detail_view.back_requested.connect(self._show_main_page)
        self.detail_view.metric_requested.connect(self._show_metric_detail)
        self.metric_detail.back_requested.connect(self._show_country_detail)
        self.pages.addWidget(self.main_page)
        self.pages.addWidget(self.detail_view)
        self.pages.addWidget(self.metric_detail)
        layout.addWidget(self.pages, 1)

    def _build_kpis(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        for label in ["Avg Growth", "Avg Rate", "Avg Inflation", "Avg Unemp.", "Avg Default", "Regions"]:
            row.addWidget(self._kpi_card(label, self._kpi_value(label)))
        row.addStretch(1)
        return row

    def _kpi_card(self, label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("KpiCard")
        frame.setMinimumWidth(150)
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 8, 10, 8)
        caption = QLabel(label.upper())
        caption.setObjectName("Muted")
        main = QLabel(value)
        main.setObjectName("DetailValue")
        self.kpi_values[label] = main
        box.addWidget(caption)
        box.addWidget(main)
        return frame

    def _kpi_value(self, label: str) -> str:
        values = {
            "Avg Growth": percent(self.analytics.average_growth * 100),
            "Avg Rate": percent(self.analytics.average_rate * 100),
            "Avg Inflation": percent(self.analytics.average_inflation * 100),
            "Avg Unemp.": percent(self.analytics.average_unemployment * 100),
            "Avg Default": percent(self.analytics.average_default_probability * 100),
            "Regions": str(len(self.analytics.countries)),
        }
        return values[label]

    def _build_macro_table(self) -> QTableView:
        table = QTableView()
        self.macro_table = table
        table.setObjectName("MacroTable")
        self.macro_model = SimpleTableModel(
            [
                "Region",
                "GDP",
                "Growth",
                "Rate",
                "Inflation",
                "Unemp. Rate",
                "Balance Sheet",
                "Rating",
            ],
            right_aligned_columns={1, 2, 3, 4, 5, 6},
            color_callback=self._macro_cell_color,
        )
        table.setModel(self.macro_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        optimize_table_view(table, row_height=36)
        table.doubleClicked.connect(lambda index: self._open_country_detail(index.row()))

        self._fill_macro_table(table)
        if self.macro_model.rowCount() > 0:
            table.selectRow(0)
        return table

    def refresh(self, state: GameState, *, throttle_charts: bool = False) -> None:
        selected_region = self._selected_region()
        self.state = state
        if self.current_provider is not None:
            self._apply_current_country_rows(self.current_provider())
        else:
            self.analytics = build_macro_analytics(state, include_trends=False)
        for label, widget in self.kpi_values.items():
            widget.setText(self._kpi_value(label))
        if self.macro_table is not None:
            self._fill_macro_table(self.macro_table)
            self._select_region(selected_region)
        if not throttle_charts and self.pages.currentWidget() is self.detail_view:
            self.detail_view.refresh(state)

    def apply_live_current_rows(self, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        selected_region = self._selected_region()
        self._apply_current_country_rows(rows)
        for label, widget in self.kpi_values.items():
            widget.setText(self._kpi_value(label))
        if self.macro_table is not None:
            self._fill_macro_table(self.macro_table)
            self._select_region(selected_region)
        if self.pages.currentWidget() is self.detail_view and self.detail_view.region:
            self.detail_view.refresh(self.state)

    def _apply_current_country_rows(self, rows: list[dict[str, object]]) -> None:
        self.current_country_rows = {str(row.get("region", "")): row for row in rows}
        countries = []
        for row in rows:
            rating = normalize_rating(str(row.get("rating", "BBB")))
            countries.append(
                CountryMacroAnalytics(
                    region=str(row.get("region", "")),
                    gdp=float(row.get("gdp", 0.0)),
                    growth=float(row.get("growth", 0.0)),
                    rate=float(row.get("rate", 0.0)),
                    inflation=float(row.get("inflation", 0.0)),
                    unemployment=float(row.get("unemployment", 0.0)),
                    balance_sheet=float(row.get("balance_sheet", 0.0)),
                    debt_to_gdp=float(row.get("debt_to_gdp", 0.0)),
                    credit_growth=float(row.get("credit_growth", 0.0)),
                    expected_growth=float(row.get("expected_growth", row.get("growth", 0.0))),
                    expected_inflation=float(row.get("expected_inflation", row.get("inflation", 0.0))),
                    expected_rate=float(row.get("expected_rate", row.get("rate", 0.0))),
                    macro_surprise=float(row.get("macro_surprise", 0.0)),
                    rating=rating,
                    default_probability=default_probability(rating),
                    policy_signal="",
                    risk_signal="",
                )
            )
        count = len(countries) or 1
        self.analytics = MacroAnalytics(
            countries=countries,
            average_growth=sum(country.growth for country in countries) / count,
            average_rate=sum(country.rate for country in countries) / count,
            average_inflation=sum(country.inflation for country in countries) / count,
            average_unemployment=sum(country.unemployment for country in countries) / count,
            average_default_probability=sum(country.default_probability for country in countries) / count,
        )

    def _fill_macro_table(self, table: QTableView) -> None:
        table.blockSignals(True)
        table.setUpdatesEnabled(False)
        rows = self._macro_rows()
        try:
            self.macro_model.set_rows(rows, metadata=list(self.analytics.countries))
        finally:
            table.setUpdatesEnabled(True)
            table.blockSignals(False)

    def _macro_cell_color(self, _row: list[str], country: object, column_index: int) -> QColor | None:
        if isinstance(country, CountryMacroAnalytics) and column_index in {2, 3, 4, 5}:
            return self._metric_color(column_index, country)
        return None

    def _selected_region(self) -> str | None:
        if self.macro_table is None:
            return None
        index = self.macro_table.currentIndex()
        return index.siblingAtColumn(0).data() if index.isValid() else None

    def _select_region(self, region: str | None) -> None:
        if self.macro_table is None or self.macro_model.rowCount() == 0:
            return
        target_row = 0
        for row in range(self.macro_model.total_row_count()):
            country = self.macro_model.metadata_at(row)
            if isinstance(country, CountryMacroAnalytics) and country.region == region:
                target_row = row
                break
        self.macro_model.ensure_row_loaded(target_row)
        self.macro_table.selectRow(target_row)
    def _macro_rows(self) -> list[list[str]]:
        rows = []
        for country in self.analytics.countries:
            rows.append(
                [
                    display_label(country.region),
                    compact_money(country.gdp),
                    percent(country.growth * 100),
                    percent(country.rate * 100),
                    percent(country.inflation * 100),
                    percent(country.unemployment * 100),
                    compact_money(country.balance_sheet),
                    country.rating,
                ]
            )
        return rows

    def _open_country_detail(self, row: int) -> None:
        if self.macro_table is None or row < 0:
            return
        country = self.macro_model.index(row, 0).data(METADATA_ROLE)
        region = country.region if isinstance(country, CountryMacroAnalytics) else str(self.macro_model.index(row, 0).data())
        self.detail_view.update_region(region, self.state)
        self.pages.setCurrentWidget(self.detail_view)

    def _show_main_page(self) -> None:
        self.pages.setCurrentWidget(self.main_page)

    def _show_country_detail(self) -> None:
        self.pages.setCurrentWidget(self.detail_view)

    def _show_metric_detail(self, title: str, subtitle: str, metrics: object) -> None:
        if not isinstance(metrics, list):
            return
        self.metric_detail.update_metric(title, subtitle, metrics)
        self.pages.setCurrentWidget(self.metric_detail)

    def _metric_color(self, column_index: int, country: CountryMacroAnalytics) -> QColor | None:
        if column_index == 2:
            return QColor("#14b8a6" if country.growth >= 0 else "#f43f5e")
        if column_index == 3:
            return QColor("#f59e0b") if country.rate >= 0.05 else None
        if column_index == 4:
            return QColor("#f43f5e" if country.inflation >= 0.035 else "#14b8a6")
        if column_index == 5:
            return QColor("#f43f5e") if country.unemployment >= 0.08 else None
        return None


class MacroTrendPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("PanelInner")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        self.title = QLabel("Select a region")
        self.title.setObjectName("SectionTitle")
        self.meta = QLabel("Rate, inflation and GDP trends")
        self.meta.setObjectName("Muted")
        self.charts: dict[str, FastChartView] = {}
        self.chart_specs = [
            ("GDP", "#14b8a6", "growth_trend", "index"),
            ("Rate", "#22d3ee", "rate_trend", "percent"),
            ("Inflation", "#f59e0b", "inflation_trend", "percent"),
            ("Unemp. Rate", "#f43f5e", "unemployment_trend", "percent"),
            ("Balance Sheet", "#8b5cf6", "balance_sheet_trend", "compact"),
        ]

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        chart_host = QFrame()
        chart_host.setObjectName("PanelInner")
        chart_layout = QVBoxLayout(chart_host)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(10)
        for title, _color, _attr, _mode in self.chart_specs:
            chart_layout.addWidget(self._build_chart(title))
        scroll.setWidget(chart_host)

        layout.addWidget(self.title)
        layout.addWidget(self.meta)
        layout.addWidget(scroll, 1)

    def _build_chart(self, title: str) -> FastChartView:
        chart = FastChartView(title=title)
        chart.setMinimumHeight(150)
        self.charts[title] = chart
        return chart

    def update_country(self, country: CountryMacroAnalytics) -> None:
        self.title.setText(display_label(country.region))
        self.meta.setText("GDP, rates, labor market and central-bank balance sheet")
        for title, color, attr, mode in self.chart_specs:
            values = getattr(country, attr)
            self._draw_chart(self.charts[title], title, values, color, mode)

    def _draw_chart(
        self,
        chart: FastChartView,
        title: str,
        values: list[float],
        color: str,
        mode: str,
    ) -> None:
        if len(values) >= 2:
            series = self._series_values(values, mode)
            chart.plot_line(series, color=color, title=title)
        else:
            chart.show_message("History builds after more simulation updates")

    def _series_values(self, values: list[float], mode: str) -> list[float]:
        if mode == "percent":
            return [value * 100.0 for value in values]
        if mode == "index":
            base = values[0] or 1.0
            return [(value / base - 1.0) * 100.0 for value in values]
        return values


class CountryDetailView(QFrame):
    back_requested = Signal()
    metric_requested = Signal(str, str, object)

    def __init__(self, state: GameState, history_provider: Callable[[str, str, int], list[float]] | None = None) -> None:
        super().__init__()
        self.state = state
        self.history_provider = history_provider
        self.region = ""
        self.production_codes: list[str] = []
        self.trade_codes: list[str] = []
        self._current_macro: dict = {}
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("ActionButton")
        self.back_button.clicked.connect(self.back_requested.emit)
        title_box = QVBoxLayout()
        self.title = QLabel("Country")
        self.title.setObjectName("BrandTitle")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Muted")
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        header.addWidget(self.back_button, 0)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        self.kpi_row = QHBoxLayout()
        self.kpi_values: dict[str, QLabel] = {}
        for label in ["Rating", "Default Prob.", "Trade Balance", "Import Dep.", "Debt/GDP", "Credit Growth"]:
            self.kpi_row.addWidget(self._kpi_card(label))
        layout.addLayout(self.kpi_row)

        self.tabs = QTabWidget()
        self.overview_panel = CountryOverviewPanel(history_provider)
        self.production_table = self._build_table("CountryProductionTable", ["Product", "Produced", "Demanded", "Gap"])
        self.trade_table = self._build_table("CountryTradeTable", ["Product", "Exports", "Imports", "Net", "Partners"])
        self.sector_table = self._build_table("CountrySectorTable", ["Sector", "Focus", "Capacity", "Utilization", "Trend"])
        self.tabs.addTab(self.overview_panel, "Overview")
        self.tabs.addTab(self._table_page(self.production_table), "Production")
        self.tabs.addTab(self._table_page(self.trade_table), "Trade")
        self.tabs.addTab(self._table_page(self.sector_table), "Sectors")
        self.tabs.currentChanged.connect(lambda _index: self._refresh_active_tab())
        layout.addWidget(self.tabs, 1)
        self.production_table.clicked.connect(lambda index: self._open_production_metric(index.row()))
        self.trade_table.clicked.connect(lambda index: self._open_trade_metric(index.row()))

    def _kpi_card(self, label: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("KpiCard")
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 8, 10, 8)
        caption = QLabel(label.upper())
        caption.setObjectName("Muted")
        value = QLabel("-")
        value.setObjectName("DetailValue")
        self.kpi_values[label] = value
        box.addWidget(caption)
        box.addWidget(value)
        return frame

    def _build_table(self, object_name: str, headers: list[str]) -> QTableView:
        table = QTableView()
        table.setObjectName(object_name)
        model = SimpleTableModel(
            headers,
            right_aligned_columns=set(range(1, len(headers))),
            color_callback=self._detail_model_cell_color,
        )
        table.setModel(model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(38)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        optimize_table_view(table, row_height=38)
        return table

    def _table_page(self, table: QTableView) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table)
        return page

    def update_region(self, region: str, state: GameState) -> None:
        self.region = region
        self.refresh(state)

    def refresh(self, state: GameState) -> None:
        self.state = state
        self._current_macro = {}
        if not self.region and state.macro:
            self.region = next(iter(state.macro))
        macro = state.macro.get(self.region, {})
        if not macro:
            return
        self._current_macro = macro
        self.title.setText(display_label(self.region))
        self.subtitle.setText(display_label(macro.get("main_sector", "")))
        rating = normalize_rating(str(macro.get("rating", "-")))
        self.kpi_values["Rating"].setText(str(macro.get("rating", "-")))
        self.kpi_values["Default Prob."].setText(percent(default_probability(rating) * 100))
        self.kpi_values["Trade Balance"].setText(compact_money(float(macro.get("trade_balance", 0.0))))
        self.kpi_values["Import Dep."].setText(percent(float(macro.get("import_dependency", 0.0)) * 100))
        self.kpi_values["Debt/GDP"].setText(percent(float(macro.get("debt_to_gdp", 0.0)) * 100))
        self.kpi_values["Credit Growth"].setText(percent(float(macro.get("credit_growth", 0.0)) * 100))
        self._refresh_active_tab()

    def _refresh_active_tab(self) -> None:
        macro = getattr(self, "_current_macro", {})
        if not macro:
            return
        current_index = self.tabs.currentIndex()
        if current_index == 0:
            self.overview_panel.update_country(self.region, macro, self.state)
        elif current_index == 1:
            self._fill_production(macro)
        elif current_index == 2:
            self._fill_trade(macro)
        elif current_index == 3:
            self._fill_sectors(macro)

    def _fill_production(self, macro: dict) -> None:
        supply = macro.get("regional_supply", {})
        demand = macro.get("regional_demand", {})
        codes = sorted(set(supply) | set(demand), key=lambda code: abs(float(supply.get(code, 0.0)) - float(demand.get(code, 0.0))), reverse=True)[:80]
        self.production_codes = list(codes)
        rows = []
        for code in codes:
            produced = float(supply.get(code, 0.0))
            demanded = float(demand.get(code, 0.0))
            rows.append([self._product_name(code), compact_money(produced), compact_money(demanded), compact_money(produced - demanded)])
        self._fill_table(self.production_table, rows)

    def _fill_trade(self, macro: dict) -> None:
        exports = macro.get("exports", {})
        imports = macro.get("imports", {})
        partner_details = macro.get("trade_partner_details", {})
        codes = sorted(set(exports) | set(imports), key=lambda code: abs(float(exports.get(code, 0.0)) - float(imports.get(code, 0.0))), reverse=True)[:80]
        self.trade_codes = list(codes)
        rows = []
        for code in codes:
            export = float(exports.get(code, 0.0))
            import_value = float(imports.get(code, 0.0))
            partners = ", ".join(list(partner_details.get(code, {}))[:3])
            rows.append([self._product_name(code), compact_money(export), compact_money(import_value), compact_money(export - import_value), partners])
        self._fill_table(self.trade_table, rows)

    def _fill_sectors(self, macro: dict) -> None:
        profile = macro.get("economic_profile", {})
        focus = profile.get("sector_focus", {})
        sector_summary = macro.get("sector_summary", {})
        rows = []
        for sector, strength in sorted(focus.items(), key=lambda item: item[1], reverse=True):
            summary = sector_summary.get(sector, {}) if isinstance(sector_summary, dict) else {}
            if summary:
                capacity = float(summary.get("capacity", 0.0))
                utilization = float(summary.get("utilization", 0.0))
                trend = float(summary.get("trend", 0.0))
            else:
                capacity = sum(float(asset.get("production_capacity", 0.0)) for asset in self.state.stocks.values() if asset.get("land") == self.region and asset.get("branche") == sector)
                utilization_values = [float(asset.get("capacity_utilization", 0.0)) for asset in self.state.stocks.values() if asset.get("land") == self.region and asset.get("branche") == sector]
                utilization = sum(utilization_values) / len(utilization_values) if utilization_values else 0.0
                trend = sum(float(asset.get("capacity_growth", 0.0)) for asset in self.state.stocks.values() if asset.get("land") == self.region and asset.get("branche") == sector)
            rows.append([display_label(sector), f"{float(strength):.2f}x", compact_money(capacity), percent(utilization * 100), percent(trend * 100)])
        self._fill_table(self.sector_table, rows)

    def _fill_table(self, table: QTableView, rows: list[list[str]]) -> None:
        table.blockSignals(True)
        table.setUpdatesEnabled(False)
        try:
            model = table.model()
            if isinstance(model, SimpleTableModel):
                model.set_rows(rows, metadata=[table.objectName() for _ in rows])
        finally:
            table.setUpdatesEnabled(True)
            table.blockSignals(False)

    def _detail_model_cell_color(self, row: list[str], table_name: object, column: int) -> QColor | None:
        value = row[column] if column < len(row) else ""
        return self._detail_cell_color(str(table_name), column, str(value))

    def _detail_cell_color(self, table_name: str, column: int, value: str) -> QColor | None:
        if column == 0:
            return None
        if table_name == "CountryProductionTable" and column == 3:
            return QColor("#14b8a6") if not value.strip().startswith("-") else QColor("#f43f5e")
        if table_name == "CountryTradeTable":
            if column in {1, 3}:
                return QColor("#14b8a6") if not value.strip().startswith("-") else QColor("#f43f5e")
            if column == 2:
                return QColor("#f59e0b")
        if table_name == "CountrySectorTable" and column in {3, 4}:
            return self._percent_status_color(value, warn_positive=False)
        return None

    def _percent_status_color(self, value: str, *, warn_positive: bool) -> QColor | None:
        parsed = self._parse_percent(value)
        if parsed is None:
            return None
        if warn_positive:
            if parsed >= 10:
                return QColor("#f43f5e")
            if parsed >= 3:
                return QColor("#f59e0b")
            return QColor("#14b8a6")
        return QColor("#14b8a6") if parsed >= 0 else QColor("#f43f5e")

    def _pressure_status_color(self, value: str) -> QColor | None:
        parsed = self._parse_percent(value)
        if parsed is None:
            return None
        if parsed >= 8:
            return QColor("#f43f5e")
        if parsed >= 2:
            return QColor("#f59e0b")
        if parsed <= -2:
            return QColor("#14b8a6")
        return None

    def _parse_percent(self, value: str) -> float | None:
        cleaned = value.replace("%", "").replace("+", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _product_name(self, code: str) -> str:
        source = self.state.commodities.get(code) or self.state.processed_products.get(code, {})
        return f"{code} {display_label(source.get('name', code))}"

    def _open_production_metric(self, row: int) -> None:
        if row < 0 or row >= len(self.production_codes):
            return
        code = self.production_codes[row]
        macro = self.state.macro.get(self.region, {})
        history = macro.get("regional_history", {}).get(code, {})
        supply = macro.get("regional_supply", {})
        demand = macro.get("regional_demand", {})
        produced = float(supply.get(code, 0.0))
        demanded = float(demand.get(code, 0.0))
        metrics = [
            ("Produced", produced, self._history(history, "produced", produced), "number", "#14b8a6"),
            ("Demanded", demanded, self._history(history, "demanded", demanded), "number", "#22d3ee"),
            ("Gap", produced - demanded, self._history(history, "gap", produced - demanded), "number", "#8b5cf6"),
        ]
        self.metric_requested.emit(
            f"{self.region} | {self._product_name(code)}",
            "Regional production and demand",
            metrics,
        )

    def _open_trade_metric(self, row: int) -> None:
        if row < 0 or row >= len(self.trade_codes):
            return
        code = self.trade_codes[row]
        macro = self.state.macro.get(self.region, {})
        history = macro.get("regional_history", {}).get(code, {})
        exports = macro.get("exports", {})
        imports = macro.get("imports", {})
        export = float(exports.get(code, 0.0))
        import_value = float(imports.get(code, 0.0))
        metrics = [
            ("Exports", export, self._history(history, "exports", export), "number", "#14b8a6"),
            ("Imports", import_value, self._history(history, "imports", import_value), "number", "#22d3ee"),
            ("Net", export - import_value, self._history(history, "net", export - import_value), "number", "#8b5cf6"),
        ]
        partners = ", ".join(list(macro.get("trade_partner_details", {}).get(code, {}))[:4])
        self.metric_requested.emit(
            f"{self.region} | {self._product_name(code)}",
            f"Trade partners: {partners}",
            metrics,
        )

    def _history(self, history: dict, key: str, fallback: float) -> list[float]:
        values = []
        for entry in history.get(key, [])[-180:]:
            try:
                values.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
            except (TypeError, ValueError):
                continue
        return values if len(values) >= 2 else [fallback, fallback]


class CountryOverviewPanel(QFrame):
    def __init__(self, history_provider: Callable[[str, str, int], list[Any]] | None = None) -> None:
        super().__init__()
        self.history_provider = history_provider
        self.setObjectName("PanelInner")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.range_limit = 365
        self._current_country: tuple[str, dict, GameState] | None = None
        controls = QHBoxLayout()
        controls.addWidget(QLabel("HISTORY"))
        self.range_group = QButtonGroup(self)
        self.range_group.setExclusive(True)
        for label, limit in (("1Y", 365), ("5Y", 1825), ("ALL", 0)):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("RangeButton")
            button.setChecked(limit == self.range_limit)
            button.clicked.connect(lambda _checked=False, value=limit: self._set_range(value))
            self.range_group.addButton(button)
            controls.addWidget(button)
        controls.addStretch(1)
        layout.addLayout(controls)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        self.charts: dict[str, FastChartView] = {}
        for index, title in enumerate(["Inflation", "Growth", "Unemployment", "Rate", "Trade Balance", "Import Dependency", "Debt/GDP", "Credit Growth"]):
            chart = FastChartView(title=title)
            self.charts[title] = chart
            grid.addWidget(chart, index // 2, index % 2)
        layout.addLayout(grid, 1)

    def update_country(self, region: str, macro: dict, state: GameState) -> None:
        self._current_country = (region, macro, state)
        charts = [
            ("Inflation", self._metric_history(region, "inflation", state.macro_history.get(f"{region}_INF", []), float(macro.get("inflation", 0.0)), 100.0), "#f59e0b"),
            ("Growth", self._metric_history(region, "gdp", state.macro_history.get(f"{region}_BIP", []), float(macro.get("bip_abs", 0.0)), 1.0), "#14b8a6"),
            ("Unemployment", self._metric_history(region, "unemployment", state.macro_history.get(f"{region}_ALO", []), float(macro.get("arbeitslosigkeit", 0.0)), 100.0), "#f43f5e"),
            ("Rate", self._metric_history(region, "rate", state.macro_history.get(f"{region}_ZINS", []), float(macro.get("zins", 0.0)), 100.0), "#22d3ee"),
            ("Trade Balance", self._metric_history(region, "trade_balance", macro.get("trade_balance_history", []), float(macro.get("trade_balance", 0.0)), 1.0), "#8b5cf6"),
            ("Import Dependency", self._metric_history(region, "import_dependency", macro.get("import_dependency_history", []), float(macro.get("import_dependency", 0.0)), 100.0), "#eab308"),
            ("Debt/GDP", self._metric_history(region, "debt_gdp", state.macro_history.get(f"{region}_DEBT_GDP", []), float(macro.get("debt_to_gdp", 0.0)), 100.0), "#f97316"),
            ("Credit Growth", self._metric_history(region, "credit", state.macro_history.get(f"{region}_CREDIT", []), float(macro.get("credit_growth", 0.0)), 100.0), "#38bdf8"),
        ]
        for title, series, color in charts:
            values, dates = series
            self.charts[title].plot_line(values, dates=dates, color=color, title=title)

    def _set_range(self, limit: int) -> None:
        self.range_limit = limit
        if self._current_country is not None:
            self.update_country(*self._current_country)

    def _metric_history(self, region: str, metric: str, fallback_history: list, fallback: float, multiplier: float) -> tuple[list[float], list[str]]:
        if self.history_provider is not None:
            points = self.history_provider(region, metric, self.range_limit)
            if len(points) >= 2:
                values, dates = _dated_history_values(points, multiplier)
                if len(values) >= 2:
                    return values, dates
        values, dates = _dated_history_values(fallback_history[-self.range_limit:] if self.range_limit else fallback_history, multiplier)
        if len(values) < 2:
            values = [fallback * multiplier, fallback * multiplier]
            dates = []
        return values, dates


class RegionalMetricDetailPanel(QFrame):
    back_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("PanelInner")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        header = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("ActionButton")
        self.back_button.clicked.connect(self.back_requested.emit)
        title_box = QVBoxLayout()
        self.title = QLabel("Metric")
        self.title.setObjectName("BrandTitle")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Muted")
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        header.addWidget(self.back_button, 0)
        header.addLayout(title_box, 1)
        layout.addLayout(header)
        self.kpi_row = QHBoxLayout()
        self.kpi_row.setSpacing(12)
        self.kpi_cards: list[QFrame] = []
        layout.addLayout(self.kpi_row)
        self.chart_grid = QGridLayout()
        self.chart_grid.setContentsMargins(0, 0, 0, 0)
        self.chart_grid.setSpacing(10)
        self.metric_charts: list[FastChartView] = []
        layout.addLayout(self.chart_grid, 1)

    def update_metric(self, title: str, subtitle: str, metrics: list[tuple[str, float, list[float], str, str]]) -> None:
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self._rebuild_kpis(metrics)
        self._draw_charts(metrics)

    def _rebuild_kpis(self, metrics: list[tuple[str, float, list[float], str, str]]) -> None:
        while self.kpi_row.count():
            item = self.kpi_row.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for label, value, history, mode, _color in metrics:
            card = QFrame()
            card.setObjectName("KpiCard")
            box = QVBoxLayout(card)
            box.setContentsMargins(10, 8, 10, 8)
            caption = QLabel(label.upper())
            caption.setObjectName("Muted")
            current = QLabel(self._format_value(value, mode))
            current.setObjectName("DetailValue")
            change = QLabel(self._change_text(history))
            change.setObjectName("DetailValue")
            change_value = self._change_value(history)
            change.setStyleSheet(f"color: {'#14b8a6' if change_value >= 0 else '#f43f5e'};")
            box.addWidget(caption)
            box.addWidget(current)
            box.addWidget(change)
            self.kpi_row.addWidget(card)
        self.kpi_row.addStretch(1)

    def _draw_charts(self, metrics: list[tuple[str, float, list[float], str, str]]) -> None:
        while self.chart_grid.count():
            item = self.chart_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.metric_charts = []
        columns = 2 if len(metrics) > 3 else 1
        for index, (label, _value, history, _mode, color) in enumerate(metrics):
            chart = FastChartView(title=label)
            chart.plot_line(history, color=color, title=label)
            self.metric_charts.append(chart)
            self.chart_grid.addWidget(chart, index // columns, index % columns)

    def _format_value(self, value: float, mode: str) -> str:
        return percent(value) if mode == "percent" else compact_money(value)

    def _change_value(self, history: list[float]) -> float:
        if len(history) < 2:
            return 0.0
        previous = history[-31] if len(history) > 30 else history[0]
        current = history[-1]
        return ((current - previous) / abs(previous)) * 100.0 if previous else 0.0

    def _change_text(self, history: list[float]) -> str:
        return f"{self._change_value(history):+.2f}% vs prev month"


def _history_values(history: list, fallback: float, multiplier: float) -> list[float]:
    values = []
    for entry in history[-180:]:
        try:
            values.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry) * multiplier)
        except (TypeError, ValueError):
            continue
    if len(values) < 2:
        return [fallback * multiplier, fallback * multiplier]
    return values


def _dated_history_values(history: list, multiplier: float) -> tuple[list[float], list[str]]:
    values: list[float] = []
    dates: list[str] = []
    for entry in history:
        try:
            if isinstance(entry, dict):
                values.append(float(entry.get("value", entry.get("close", 0.0))) * multiplier)
                dates.append(str(entry.get("date", "")))
            elif isinstance(entry, (tuple, list)):
                values.append(float(entry[0]) * multiplier)
                dates.append(str(entry[1]) if len(entry) > 1 else "")
            else:
                values.append(float(entry) * multiplier)
                dates.append("")
        except (TypeError, ValueError):
            continue
    return values, dates
