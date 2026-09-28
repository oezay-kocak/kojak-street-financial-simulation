"""Supply chain workspace for commodities and processed products."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.display import display_label
from kojakstreet.ui_qt.formatters import compact_money, percent, regional_money_precise
from kojakstreet.ui_qt.models.simple_table_model import METADATA_ROLE, SimpleTableModel
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.widgets.qt_chart import FastChartView
from kojakstreet.ui_qt.widgets.view_header import ViewHeader


class SupplyChainView(QFrame):
    """Filterable economy-wide list of supply, demand and bottlenecks."""

    def __init__(
        self,
        state: GameState,
        history_provider: Callable[[str, str, int], list[float]] | None = None,
        current_provider: Callable[[], list[dict[str, object]]] | None = None,
        company_current_provider: Callable[[], list[dict[str, object]]] | None = None,
        company_output_provider: Callable[[], list[dict[str, object]]] | None = None,
    ) -> None:
        super().__init__()
        self.state = state
        self.history_provider = history_provider
        self.current_provider = current_provider
        self.company_current_provider = company_current_provider
        self.company_output_provider = company_output_provider
        self.setObjectName("Panel")
        self.rows: list[dict[str, Any]] = []
        self.filtered_rows: list[dict[str, Any]] = []
        self.selected_code: str | None = None
        self._render_signature: tuple[tuple[Any, ...], ...] = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        self.pages = QStackedWidget()
        self.list_page = QWidget()
        list_layout = QVBoxLayout(self.list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(12)
        list_layout.addWidget(
            ViewHeader(
                "Supply Chain",
                "Production, demand and bottlenecks across raw materials, products and services",
                ["Refresh"],
            )
        )
        list_layout.addLayout(self._build_toolbar())
        list_layout.addWidget(self._build_table(), 1)
        self.detail_page = self._build_detail_page()
        self.pages.addWidget(self.list_page)
        self.pages.addWidget(self.detail_page)
        layout.addWidget(self.pages, 1)
        self.refresh(state)

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.setSpacing(12)
        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("ActionButton")
        self.back_button.clicked.connect(self._show_list)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self.detail_title = QLabel("Supply Chain")
        self.detail_title.setObjectName("BrandTitle")
        self.detail_subtitle = QLabel("")
        self.detail_subtitle.setObjectName("Muted")
        title_box.addWidget(self.detail_title)
        title_box.addWidget(self.detail_subtitle)
        header.addWidget(self.back_button, 0)
        header.addLayout(title_box, 1)
        layout.addLayout(header)
        self.metric_row = QHBoxLayout()
        self.metric_row.setSpacing(12)
        self.produced_value = self._metric_card("Produced")
        self.demanded_value = self._metric_card("Demanded")
        self.metric_row.addWidget(self.produced_value[0])
        self.metric_row.addWidget(self.demanded_value[0])
        self.metric_row.addStretch(1)
        layout.addLayout(self.metric_row)
        self.produced_chart = FastChartView(title="Produced")
        self.demanded_chart = FastChartView(title="Demanded")
        self.country_share_chart = FastChartView(title="Country Production Share")
        chart_row = QHBoxLayout()
        chart_row.setSpacing(12)
        trend_column = QVBoxLayout()
        trend_column.setSpacing(12)
        trend_column.addWidget(self.produced_chart, 1)
        trend_column.addWidget(self.demanded_chart, 1)
        chart_row.addLayout(trend_column, 1)
        chart_row.addWidget(self.country_share_chart, 1)
        layout.addLayout(chart_row, 1)
        return page

    def _metric_card(self, title: str) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame()
        card.setObjectName("KpiCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        caption = QLabel(title.upper())
        caption.setObjectName("Muted")
        value = QLabel("-")
        value.setObjectName("DetailValue")
        change = QLabel("-")
        change.setObjectName("DetailValue")
        layout.addWidget(caption)
        layout.addWidget(value)
        layout.addWidget(change)
        return card, value, change

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SupplyChainSearchInput")
        self.search_input.setPlaceholderText("Search code, name or category")
        self.search_input.textChanged.connect(self.apply_filters)

        self.type_filter = QComboBox()
        self.type_filter.setObjectName("SupplyChainTypeFilter")
        self.type_filter.setMinimumWidth(210)
        self.type_filter.view().setMinimumWidth(250)
        self.type_filter.addItems(["Commodity", "Processed Product", "Service", "Imbalance"])
        self.type_filter.currentTextChanged.connect(self.apply_filters)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.type_filter, 0)
        return toolbar

    def _build_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("SupplyChainTable")
        self.table = table
        self.table_model = SimpleTableModel(
            ["Code", "Name", "Type", "Category", "Produced", "Demanded", "Inventories", "Balance", "Pressure"],
            right_aligned_columns={4, 5, 6, 7, 8},
            color_callback=self._table_cell_color,
        )
        table.setModel(self.table_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(38)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True)
        optimize_table_view(table, row_height=38)
        table.clicked.connect(self._open_row_detail)
        return table

    def refresh(self, state: GameState, *, throttle_charts: bool = False) -> None:
        previous_code = self.selected_code or self._selected_code()
        showing_detail = self.pages.currentWidget() is self.detail_page
        self.state = state
        self.rows = self._build_rows()
        if showing_detail and previous_code is not None:
            row = self._row_for_code(previous_code)
            if row is not None:
                if not throttle_charts:
                    self._draw_row_charts(row)
                self.pages.setCurrentWidget(self.detail_page)
            return
        self.apply_filters(selected_code=previous_code)

    def apply_filters(self, _value: object = None, *, selected_code: str | None = None) -> None:
        if selected_code is not None:
            self.selected_code = selected_code
        query = self.search_input.text().strip().lower()
        filter_value = self.type_filter.currentText()
        filtered = []
        for row in self.rows:
            if filter_value == "Commodity" and row["type"] != "Commodity":
                continue
            if filter_value == "Processed Product" and row["type"] != "Processed Product":
                continue
            if filter_value == "Service" and row["type"] != "Service":
                continue
            if filter_value == "Imbalance" and abs(row["imbalance"]) <= 0.03:
                continue
            haystack = f"{row['code']} {row['name']} {row['category']}".lower()
            if query and query not in haystack:
                continue
            filtered.append(row)
        self.filtered_rows = filtered
        self._render_rows(filtered)

    def _build_rows(self) -> list[dict[str, Any]]:
        if self.current_provider is not None:
            current_rows = self.current_provider()
            if current_rows:
                return [self._row_from_current(row) for row in current_rows]
        rows = []
        for code, data in self.state.commodities.items():
            rows.append(self._row(code, data, "Commodity"))
        for code, data in self.state.processed_products.items():
            rows.append(self._row(code, data, self._product_type(data)))
        return rows

    def _row(self, code: str, data: dict[str, Any], item_type: str) -> dict[str, Any]:
        return {
            "code": code,
            "name": display_label(data.get("name", code)),
            "type": item_type,
            "category": display_label(data.get("kategorie", data.get("category", ""))),
            "supply": float(data.get("supply", data.get("production", 0.0))),
            "demand": float(data.get("demand", 0.0)),
            "inventories": float(data.get("inventories", 0.0)),
            "shortage": float(data.get("shortage", 0.0)),
            "surplus": float(data.get("surplus", _row_surplus(data))),
            "imbalance": float(data.get("imbalance", _row_imbalance(data))),
            "pressure": float(data.get("price_pressure", 0.0)),
            "price": float(data.get("kurs", 0.0)),
            "data": data,
        }

    def _row_from_current(self, row: dict[str, object]) -> dict[str, Any]:
        item_type = str(row.get("type", ""))
        category = str(row.get("category", ""))
        if item_type == "Processed Product" and (
            "Dienst" in category or "Service" in category or "Finance" in category or "Finanzen" in category
            or "Real Estate" in category or "Immobilien" in category or "Telecommunication" in category
            or "Telekommunikation" in category or "Crypto Network" in category
        ):
            item_type = "Service"
        data = {
            "name": row.get("name", row.get("code", "")),
            "kategorie": category,
            "supply": float(row.get("produced", 0.0)),
            "demand": float(row.get("demanded", 0.0)),
            "inventories": float(row.get("inventories", 0.0)),
            "shortage": float(row.get("shortage", 0.0)),
            "surplus": max(0.0, (float(row.get("produced", 0.0)) - float(row.get("demanded", 0.0))) / max(1.0, float(row.get("demanded", 0.0)))),
            "imbalance": _balance_from_values(float(row.get("produced", 0.0)), float(row.get("demanded", 0.0))),
            "price_pressure": float(row.get("pressure", 0.0)),
            "kurs": float(row.get("price", 0.0)),
        }
        return self._row(str(row.get("code", "")), data, item_type)

    def _product_type(self, data: dict[str, Any]) -> str:
        category = str(data.get("kategorie", data.get("category", "")))
        if (
            "Dienst" in category
            or "Finanzen" in category
            or "Immobilien" in category
            or "Telekommunikation" in category
            or "Crypto Network" in category
        ):
            return "Service"
        return "Processed Product"

    def _render_rows(self, rows: list[dict[str, Any]]) -> None:
        previous_code = self.selected_code or self._selected_code()
        signature = _rows_signature(rows)
        if signature == self._render_signature:
            self._restore_selection(previous_code, rows)
            return
        self._render_signature = signature
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        try:
            values = []
            sort_values = []
            for row in rows:
                row_values = [
                    row["code"],
                    row["name"],
                    row["type"],
                    row["category"],
                    compact_money(row["supply"]),
                    compact_money(row["demand"]),
                    compact_money(row["inventories"]),
                    percent(row["imbalance"] * 100.0),
                    percent(row["pressure"] * 100.0),
                ]
                if row["type"] == "Commodity" and row["price"] > 0:
                    row_values[8] = f"{row_values[8]} | {regional_money_precise(row['price'], 'GD')}"
                values.append(row_values)
                sort_values.append(
                    [
                        row["code"].lower(),
                        row["name"].lower(),
                        row["type"].lower(),
                        row["category"].lower(),
                        row["supply"],
                        row["demand"],
                        row["inventories"],
                        row["imbalance"],
                        row["pressure"],
                    ]
                )
            self.table_model.set_rows(values, metadata=rows, sort_values=sort_values)
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)
            self.table.blockSignals(False)
        self._restore_selection(previous_code, rows)

    def _table_cell_color(self, _values: list[str], row: Any, column: int) -> QColor | None:
        if not isinstance(row, dict):
            return None
        if column == 7:
            return self._imbalance_color(row["imbalance"])
        if column == 8:
            return self._pressure_color(row["pressure"])
        return None

    def _imbalance_color(self, value: float) -> QColor:
        if value >= 0.10:
            return QColor("#f43f5e")
        if value >= 0.03:
            return QColor("#f59e0b")
        if value <= -0.10:
            return QColor("#14b8a6")
        if value <= -0.03:
            return QColor("#22d3ee")
        return QColor("#14b8a6")

    def _pressure_color(self, value: float) -> QColor:
        if value >= 0.08:
            return QColor("#f43f5e")
        if value >= 0.02:
            return QColor("#f59e0b")
        if value <= -0.02:
            return QColor("#14b8a6")
        return QColor("#c9d7e6")

    def _open_row_detail(self, index) -> None:
        row = index.data(METADATA_ROLE)
        if not isinstance(row, dict):
            return
        self.selected_code = str(row["code"])
        self._draw_row_charts(row)
        self.pages.setCurrentWidget(self.detail_page)

    def _draw_row_charts(self, row: dict[str, Any]) -> None:
        self.selected_code = str(row["code"])
        produced = self._metric_history(row, "produced", "supply_history", row["supply"])
        demanded = self._metric_history(row, "demanded", "demand_history", row["demand"])
        self._update_metric_card(self.produced_value, row["supply"], produced)
        self._update_metric_card(self.demanded_value, row["demand"], demanded)
        self.detail_title.setText(f"{row['code']}  {row['name']}")
        self.detail_subtitle.setText(f"{row['type']} | {row['category']}")
        self.produced_chart.plot_line(produced, color="#14b8a6", title="Produced")
        self.demanded_chart.plot_line(demanded, color="#22d3ee", title="Demanded")
        if self._is_crypto_network_service(row):
            self.country_share_chart.hide()
        else:
            self.country_share_chart.show()
            self.country_share_chart.plot_horizontal_bars(
                self._country_production_shares(str(row["code"])),
                title="Global Production Share by Country",
                color="#22d3ee",
            )

    def _update_metric_card(self, card: tuple[QFrame, QLabel, QLabel], current: float, history: list[float]) -> None:
        _frame, value_label, change_label = card
        value_label.setText(compact_money(float(current)))
        change = self._history_change(history)
        change_label.setText(f"{change:+.2f}% vs prev month")
        change_label.setStyleSheet(f"color: {'#14b8a6' if change >= 0 else '#f43f5e'};")

    def _history_change(self, history: list[float]) -> float:
        if len(history) < 2:
            return 0.0
        previous = history[-31] if len(history) > 30 else history[0]
        current = history[-1]
        return ((current - previous) / abs(previous)) * 100.0 if previous else 0.0

    def _draw_empty_charts(self) -> None:
        self.produced_chart.show_message("No matching supply-chain items")
        self.demanded_chart.show_message("No matching supply-chain items")
        self.country_share_chart.show_message("No matching supply-chain items")
        self.country_share_chart.show()

    def _is_crypto_network_service(self, row: dict[str, Any]) -> bool:
        category = str(row.get("category", ""))
        item_type = str(row.get("type", ""))
        return item_type == "Service" and "Crypto Network" in category

    def _country_production_shares(self, code: str) -> list[tuple[str, float]]:
        countries = list(self.state.macro) or sorted({str(asset.get("land", "")) for asset in self.state.stocks.values() if asset.get("land")})
        produced_by_country = self._country_production_from_current_rows(code, countries)
        if produced_by_country is None:
            produced_by_country = self._country_production_from_state(code, countries)
        total = sum(produced_by_country.values())
        if total <= 0.0:
            return []
        return [
            (display_label(country), value / total * 100.0)
            for country, value in produced_by_country.items()
        ]

    def _country_production_from_current_rows(self, code: str, countries: list[str]) -> dict[str, float] | None:
        if self.company_current_provider is None or self.company_output_provider is None:
            return None
        company_rows = self.company_current_provider()
        output_rows = self.company_output_provider()
        if not company_rows or not output_rows:
            return None
        ticker_region = {
            str(row.get("ticker", "")): str(row.get("region", ""))
            for row in company_rows
        }
        ticker_sector = {
            str(row.get("ticker", "")): str(row.get("sector", ""))
            for row in company_rows
        }
        produced_by_country = {country: 0.0 for country in countries}
        for row in output_rows:
            if str(row.get("role", "")) != "Produces" or str(row.get("code", "")) != code:
                continue
            ticker = str(row.get("ticker", ""))
            country = ticker_region.get(ticker, "")
            if not country:
                continue
            multiplier = self._country_product_multiplier(country, ticker_sector.get(ticker, ""), code)
            produced_by_country[country] = produced_by_country.get(country, 0.0) + max(0.0, float(row.get("quantity", 0.0)) * multiplier)
        return produced_by_country if any(produced_by_country.values()) else None

    def _country_production_from_state(self, code: str, countries: list[str]) -> dict[str, float]:
        produced_by_country = {country: 0.0 for country in countries}
        for asset in self.state.stocks.values():
            country = str(asset.get("land", ""))
            if not country:
                continue
            output_mix = asset.get("output_mix") or {asset.get("specialization", ""): 1.0}
            share = float(output_mix.get(code, 0.0)) if isinstance(output_mix, dict) else 0.0
            if share <= 0.0:
                continue
            capacity = float(asset.get("production_capacity", 0.0))
            multiplier = self._country_product_multiplier(country, str(asset.get("branche", "")), code)
            produced_by_country[country] = produced_by_country.get(country, 0.0) + max(0.0, capacity * share * multiplier)
        if not any(produced_by_country.values()):
            for country in countries:
                produced_by_country[country] = float(self.state.macro.get(country, {}).get("regional_supply", {}).get(code, 0.0))
        return produced_by_country

    def _country_product_multiplier(self, country: str, sector: str, code: str) -> float:
        macro = self.state.macro.get(country, {})
        profile = macro.get("economic_profile", {}) if isinstance(macro, dict) else {}
        sector_focus = float(profile.get("sector_focus", {}).get(sector, 1.0)) if isinstance(profile, dict) else 1.0
        product_focus = float(profile.get("product_focus", {}).get(code, 1.0)) if isinstance(profile, dict) else 1.0
        texture = 0.52 + _stable_unit_interval(f"{country}:{sector}:{code}:country-share") * 1.18
        return max(0.28, min(2.45, sector_focus * product_focus * texture))

    def _history(self, data: dict[str, Any], key: str, fallback: float) -> list[float]:
        return _history_points(data, key)

    def _metric_history(self, row: dict[str, Any], metric: str, legacy_key: str, fallback: float) -> list[float]:
        if self.history_provider is not None:
            points = self.history_provider(str(row["code"]), metric, 1200)
            return _smooth_supply_points(points)
        return _smooth_supply_points(self._history(row["data"], legacy_key, fallback))

    def _selected_code(self) -> str | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        row = index.data(METADATA_ROLE)
        return str(row["code"]) if isinstance(row, dict) else None

    def _restore_selection(self, code: str | None, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        target_code = code if any(row["code"] == code for row in rows) else rows[0]["code"]
        for row_index in range(self.table_model.total_row_count()):
            row = self.table_model.metadata_at(row_index)
            if isinstance(row, dict) and row["code"] == target_code:
                self.table_model.ensure_row_loaded(row_index)
                self.table.blockSignals(True)
                self.table.selectRow(row_index)
                self.table.blockSignals(False)
                self.selected_code = str(target_code)
                return

    def _row_for_code(self, code: str) -> dict[str, Any] | None:
        for row in self.rows:
            if row["code"] == code:
                return row
        return None

    def _show_list(self) -> None:
        self.apply_filters(selected_code=self.selected_code)
        self.pages.setCurrentWidget(self.list_page)

    def apply_live_current_rows(self, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        previous_code = self.selected_code or self._selected_code()
        self.rows = [self._row_from_current(row) for row in rows]
        if self.pages.currentWidget() is self.detail_page and previous_code is not None:
            row = self._row_for_code(previous_code)
            if row is not None:
                self._update_metric_card(
                    self.produced_value,
                    row["supply"],
                    self._metric_history(row, "produced", "supply_history", row["supply"]),
                )
                self._update_metric_card(
                    self.demanded_value,
                    row["demand"],
                    self._metric_history(row, "demanded", "demand_history", row["demand"]),
                )
                self._draw_row_charts(row)
                return
        self.apply_filters(selected_code=previous_code)


def _smooth_supply_points(points: list[float]) -> list[float]:
    if len(points) < 4:
        return points
    cleaned = list(points)
    for index in range(1, len(points) - 1):
        previous_value = cleaned[index - 1]
        current_value = cleaned[index]
        next_value = points[index + 1]
        neighbor_mid = (previous_value + next_value) / 2.0
        scale = max(abs(neighbor_mid), 1.0)
        neighbors_are_stable = abs(previous_value - next_value) / scale < 0.018
        isolated_move = abs(current_value - neighbor_mid) / scale > 0.028
        if neighbors_are_stable and isolated_move:
            cleaned[index] = neighbor_mid

    smoothed = [cleaned[0]]
    for value in cleaned[1:]:
        previous_value = smoothed[-1]
        change = abs(value - previous_value) / max(abs(previous_value), 1.0)
        alpha = 0.68 if change >= 0.08 else 0.24
        smoothed.append(previous_value + ((value - previous_value) * alpha))
    return smoothed


def _history_points(data: dict[str, Any], key: str) -> list[float]:
    points = []
    for entry in data.get(key, []):
        try:
            points.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
        except (TypeError, ValueError):
            continue
    return points


def _row_imbalance(data: dict[str, Any]) -> float:
    return _balance_from_values(
        float(data.get("supply", data.get("production", 0.0))),
        float(data.get("demand", 0.0)),
    )


def _row_surplus(data: dict[str, Any]) -> float:
    supply = float(data.get("supply", data.get("production", 0.0)))
    demand = float(data.get("demand", 0.0))
    return max(0.0, supply - demand) / max(1.0, demand)


def _balance_from_values(supply: float, demand: float) -> float:
    if demand <= 0.0:
        return 0.0
    return (demand - supply) / max(1.0, demand)


def _stable_unit_interval(text: str) -> float:
    value = 0
    for char in text:
        value = (value * 131 + ord(char)) % 10_000
    return value / 10_000.0


def _rows_signature(rows: list[dict[str, Any]]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            row["code"],
            row["type"],
            round(float(row["supply"]), 4),
            round(float(row["demand"]), 4),
            round(float(row["inventories"]), 4),
            round(float(row["imbalance"]), 5),
            round(float(row["pressure"]), 5),
        )
        for row in rows
    )
