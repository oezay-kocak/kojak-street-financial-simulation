"""News workspace view."""

from __future__ import annotations

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
    QSplitter,
    QStackedWidget,
    QTableView,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
)

from kojakstreet.core.economic_calendar import EconomicCalendarItem, build_economic_calendar
from kojakstreet.core.news import (
    NewsItem,
    build_news_items,
    classify_impact,
    classify_priority,
    classify_topic,
    normalize_category,
    translate_news_text,
)
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.display import display_label, display_text
from kojakstreet.ui_qt.formatters import percent
from kojakstreet.ui_qt.models.simple_table_model import METADATA_ROLE, SimpleTableModel
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.widgets.empty_state import EmptyState
from kojakstreet.ui_qt.widgets.qt_chart import FastChartView
from kojakstreet.ui_qt.widgets.view_header import ViewHeader


class NewsView(QFrame):
    """Read-only news and event feed."""

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self.state = state
        self.news_items = build_news_items(state)
        self.calendar_items = build_economic_calendar(state)
        self._news_signature = self._state_news_signature(state)
        self._calendar_signature = self._state_calendar_signature(state)
        self.news_table: QTableView | None = None
        self.calendar_table: QTableView | None = None
        self.search_input: QLineEdit | None = None
        self.category_filter: QComboBox | None = None
        self.priority_filter: QComboBox | None = None
        self.detail_stack: QStackedWidget | None = None
        self.empty_state: EmptyState | None = None
        self.kpi_values: dict[str, QLabel] = {}
        self.detail_title = QLabel("No news selected")
        self.detail_title.setObjectName("SectionTitle")
        self.detail_title.setWordWrap(True)
        self.detail_meta = QLabel("Select an event to inspect impact and full text")
        self.detail_meta.setObjectName("Muted")
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setObjectName("DetailText")
        self.calendar_detail_title = QLabel("No event selected")
        self.calendar_detail_title.setObjectName("SectionTitle")
        self.calendar_detail_title.setWordWrap(True)
        self.calendar_detail_meta = QLabel("Select an economic calendar row")
        self.calendar_detail_meta.setObjectName("Muted")
        self.calendar_chart = FastChartView(title="Indicator History")
        self.setObjectName("Panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(
            ViewHeader(
                "News",
                "Market events, central-bank updates and risk alerts",
                ["Archive", "Export"],
            )
        )
        layout.addLayout(self._build_kpis())
        layout.addLayout(self._build_toolbar())
        layout.addWidget(self._build_content(), 1)

    def _build_kpis(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self._add_kpi(grid, "Items", self._kpi_value("Items"), 0, 0)
        self._add_kpi(grid, "Critical", self._kpi_value("Critical"), 0, 1)
        self._add_kpi(grid, "High Priority", self._kpi_value("High Priority"), 0, 2)
        self._add_kpi(grid, "Central Bank", self._kpi_value("Central Bank"), 0, 3)
        self._add_kpi(grid, "Bearish", self._kpi_value("Bearish"), 0, 4)
        self._add_kpi(grid, "Bullish", self._kpi_value("Bullish"), 0, 5)
        return grid

    def _add_kpi(self, grid: QGridLayout, label: str, value: str, row: int, column: int) -> None:
        box = QVBoxLayout()
        caption = QLabel(label.upper())
        caption.setObjectName("Muted")
        main = QLabel(value)
        main.setObjectName("DetailValue")
        self.kpi_values[label] = main
        box.addWidget(caption)
        box.addWidget(main)
        grid.addLayout(box, row, column)

    def _kpi_value(self, label: str) -> str:
        values = {
            "Items": str(len(self.news_items)),
            "Critical": str(self._count_priority("Critical")),
            "High Priority": str(self._count_priority("High")),
            "Central Bank": str(self._count_category("Central Bank")),
            "Bearish": str(self._count_impact("Bearish")),
            "Bullish": str(self._count_impact("Bullish")),
        }
        return values[label]

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("NewsSearchInput")
        self.search_input.setPlaceholderText("Search news, category, impact or date")
        self.search_input.textChanged.connect(self.apply_filters)

        self.category_filter = QComboBox()
        self.category_filter.setObjectName("NewsCategoryFilter")
        self.category_filter.setMinimumWidth(220)
        self.category_filter.view().setMinimumWidth(300)
        self.category_filter.addItems(["All Categories", *self._unique_categories()])
        self.category_filter.currentTextChanged.connect(self.apply_filters)

        self.priority_filter = QComboBox()
        self.priority_filter.setObjectName("NewsPriorityFilter")
        self.priority_filter.setMinimumWidth(160)
        self.priority_filter.view().setMinimumWidth(190)
        self.priority_filter.addItems(["All Priorities", "Critical", "High", "Medium", "Normal"])
        self.priority_filter.currentTextChanged.connect(self.apply_filters)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.category_filter)
        toolbar.addWidget(self.priority_filter)
        return toolbar

    def _build_content(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        tabs = QTabWidget()
        tabs.setObjectName("NewsTabs")
        tabs.addTab(self._build_calendar_table(), "Economic Calendar")
        tabs.addTab(self._build_news_table(), "Market News")
        detail = self._build_detail_stack()
        detail.setMinimumWidth(360)
        splitter.addWidget(tabs)
        splitter.addWidget(detail)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([760, 860])
        return splitter

    def _build_detail_stack(self) -> QStackedWidget:
        self.detail_stack = QStackedWidget()
        self.empty_state = EmptyState(
            "No news yet",
            "Simulation events and central-bank updates will appear here.",
        )
        self.detail_stack.addWidget(self.empty_state)
        self.detail_stack.addWidget(self._build_detail_panel())
        self.detail_stack.addWidget(self._build_calendar_detail_panel())
        self._sync_detail_stack()
        return self.detail_stack

    def _build_news_table(self) -> QTableView:
        table = QTableView()
        self.news_table = table
        table.setObjectName("NewsTable")
        self.news_model = SimpleTableModel(
            ["Date", "Topic", "Priority", "Category", "Impact", "Headline", "Tag"],
            color_callback=self._table_cell_color,
        )
        table.setModel(self.news_model)
        self.news_model.rowsInserted.connect(lambda *_: self.apply_filters())
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        optimize_table_view(table, row_height=40)

        self._fill_news_table(table)

        table.selectionModel().currentRowChanged.connect(lambda index, _previous: self._show_detail(index.row()))
        if self.news_items:
            table.selectRow(0)
            self._set_detail(self.news_items[0])
        else:
            self.detail.setText("No news yet.")
        return table

    def _build_calendar_table(self) -> QTableView:
        table = QTableView()
        self.calendar_table = table
        table.setObjectName("EconomicCalendarTable")
        self.calendar_model = SimpleTableModel(
            ["Date", "Time", "Country", "Indicator", "Actual", "Previous", "Expected", "Surprise"],
            right_aligned_columns={4, 5, 6, 7},
            color_callback=self._calendar_cell_color,
        )
        table.setModel(self.calendar_model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(38)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for column in (0, 1, 2, 4, 5, 6, 7):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        optimize_table_view(table, row_height=38)
        self._fill_calendar_table(table)
        table.selectionModel().currentRowChanged.connect(lambda index, _previous: self._show_calendar_detail(index.row()))
        if self.calendar_items:
            table.selectRow(0)
            self._set_calendar_detail(self.calendar_items[0])
        return table

    def refresh(self, state: GameState) -> None:
        signature = self._state_news_signature(state)
        calendar_signature = self._state_calendar_signature(state)
        if signature == self._news_signature and calendar_signature == self._calendar_signature:
            self.state = state
            return
        selected_key = self._selected_news_key()
        selected_calendar_key = self._selected_calendar_key()
        self.state = state
        self._news_signature = signature
        self._calendar_signature = calendar_signature
        self.news_items = build_news_items(state)
        self.calendar_items = build_economic_calendar(state)
        for label, widget in self.kpi_values.items():
            widget.setText(self._kpi_value(label))
        self._sync_category_filter()
        if self.news_table is not None:
            self._fill_news_table(self.news_table)
            self.apply_filters()
            self._select_news(selected_key)
        if self.calendar_table is not None:
            self._fill_calendar_table(self.calendar_table)
            self._select_calendar(selected_calendar_key)
        self._sync_detail_stack()

    def apply_live_current_rows(self, rows: list[dict[str, object]]) -> None:
        signature = tuple((str(row.get("date", "")), str(row.get("body", "")), str(row.get("category", ""))) for row in rows)
        if signature == self._news_signature:
            return
        selected_key = self._selected_news_key()
        self._news_signature = signature
        self.news_items = [_news_item_from_current_row(row) for row in rows]
        for label, widget in self.kpi_values.items():
            widget.setText(self._kpi_value(label))
        self._sync_category_filter()
        if self.news_table is not None:
            self._fill_news_table(self.news_table)
            self.apply_filters()
            self._select_news(selected_key)
        self._sync_detail_stack()

    def _fill_news_table(self, table: QTableView) -> None:
        table.blockSignals(True)
        table.setUpdatesEnabled(False)
        try:
            rows = []
            for row_index, item in enumerate(self.news_items):
                rows.append([
                    item.date,
                    item.topic,
                    item.priority,
                    item.category,
                    item.impact,
                    display_text(item.headline),
                    self._tag(item),
                ])
            self.news_model.set_rows(rows, metadata=list(self.news_items))
        finally:
            table.setUpdatesEnabled(True)
            table.blockSignals(False)

    def _fill_calendar_table(self, table: QTableView) -> None:
        table.blockSignals(True)
        table.setUpdatesEnabled(False)
        try:
            rows = []
            for item in self.calendar_items:
                rows.append([
                    item.date,
                    item.time,
                    item.country,
                    f"{item.indicator} {item.period}",
                    _calendar_value(item.actual),
                    _calendar_value(item.previous),
                    _calendar_value(item.expected),
                    _calendar_value(item.surprise),
                ])
            self.calendar_model.set_rows(rows, metadata=list(self.calendar_items))
        finally:
            table.setUpdatesEnabled(True)
            table.blockSignals(False)

    def _calendar_cell_color(self, _row: list[str], item: object, column: int) -> QColor | None:
        if not isinstance(item, EconomicCalendarItem):
            return None
        if column in {4, 7} and item.surprise is not None:
            return QColor("#14b8a6") if item.surprise >= 0 else QColor("#f43f5e")
        if column == 6:
            return QColor("#22d3ee")
        return None

    def _table_cell_color(self, _row: list[str], item: object, column: int) -> QColor | None:
        if isinstance(item, NewsItem) and column in {1, 2, 3, 4, 6}:
            return self._item_color(item, column)
        return None

    def _build_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PanelInner")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.detail_title)
        layout.addWidget(self.detail_meta)
        layout.addWidget(self.detail, 1)
        return panel

    def _build_calendar_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PanelInner")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.calendar_detail_title)
        layout.addWidget(self.calendar_detail_meta)
        layout.addWidget(self.calendar_chart, 1)
        return panel

    def _show_detail(self, row: int) -> None:
        if self.news_table is None or row < 0:
            return
        index = self.news_table.model().index(row, 0)
        if not index.isValid():
            return
        news_item = index.data(METADATA_ROLE)
        if isinstance(news_item, NewsItem):
            self._set_detail(news_item)

    def _set_detail(self, item: NewsItem) -> None:
        self.detail_title.setText(display_text(item.headline))
        self.detail_meta.setText(
            f"{item.date} | {display_label(item.topic)} | {item.priority} | {item.category} | {item.impact}"
        )
        self.detail.setText(
            f"Topic: {display_label(item.topic)}\nPriority: {item.priority}\nImpact: {item.impact}\n\n{display_text(item.body)}"
        )
        self._sync_detail_stack()

    def _show_calendar_detail(self, row: int) -> None:
        if self.calendar_table is None or row < 0:
            return
        index = self.calendar_table.model().index(row, 0)
        item = index.data(METADATA_ROLE) if index.isValid() else None
        if isinstance(item, EconomicCalendarItem):
            self._set_calendar_detail(item)

    def _set_calendar_detail(self, item: EconomicCalendarItem) -> None:
        self.calendar_detail_title.setText(f"{item.country}  {item.indicator}")
        surprise = "-" if item.surprise is None else _calendar_value(item.surprise)
        self.calendar_detail_meta.setText(
            f"{item.date} | {item.time} | Actual {_calendar_value(item.actual)} | "
            f"Expected {_calendar_value(item.expected)} | Surprise {surprise}"
        )
        if len(item.history) >= 2:
            self.calendar_chart.plot_line(item.history, color="#22d3ee", title=item.indicator, label=item.country)
        else:
            self.calendar_chart.show_message("History builds as economic reports are published")
        if self.detail_stack is not None:
            self.detail_stack.setCurrentIndex(2)

    def _sync_detail_stack(self) -> None:
        if self.detail_stack is None:
            return
        self.detail_stack.setCurrentIndex(1 if self.news_items else 0)

    def _selected_news_key(self) -> tuple[str, str] | None:
        if self.news_table is None:
            return None
        index = self.news_table.currentIndex()
        news_item = index.data(METADATA_ROLE) if index.isValid() else None
        if isinstance(news_item, NewsItem):
            return (news_item.date, news_item.headline)
        return None

    def _selected_calendar_key(self) -> tuple[str, str, str] | None:
        if self.calendar_table is None:
            return None
        index = self.calendar_table.currentIndex()
        item = index.data(METADATA_ROLE) if index.isValid() else None
        if isinstance(item, EconomicCalendarItem):
            return (item.date, item.country, item.indicator)
        return None

    def _select_news(self, key: tuple[str, str] | None) -> None:
        if self.news_table is None:
            return
        if not self.news_items:
            self.detail_title.setText("No news selected")
            self.detail_meta.setText("Select an event to inspect impact and full text")
            self.detail.setText("No news yet.")
            return
        target_row = 0
        for row in range(self.news_model.total_row_count()):
            news_item = self.news_model.metadata_at(row)
            if isinstance(news_item, NewsItem) and (news_item.date, news_item.headline) == key:
                target_row = row
                break
        self.news_model.ensure_row_loaded(target_row)
        self.news_table.selectRow(target_row)
        news_item = self.news_model.index(target_row, 0).data(METADATA_ROLE)
        if isinstance(news_item, NewsItem):
            self._set_detail(news_item)

    def _select_calendar(self, key: tuple[str, str, str] | None) -> None:
        if self.calendar_table is None or not self.calendar_items:
            return
        target_row = 0
        for row in range(self.calendar_model.total_row_count()):
            item = self.calendar_model.metadata_at(row)
            if isinstance(item, EconomicCalendarItem) and (item.date, item.country, item.indicator) == key:
                target_row = row
                break
        self.calendar_model.ensure_row_loaded(target_row)
        self.calendar_table.selectRow(target_row)

    def _sync_category_filter(self) -> None:
        if self.category_filter is None:
            return
        current = self.category_filter.currentText()
        categories = ["All Categories", *self._unique_categories()]
        existing = [self.category_filter.itemText(index) for index in range(self.category_filter.count())]
        if existing == categories:
            return
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItems(categories)
        self.category_filter.setCurrentText(current if current in categories else "All Categories")
        self.category_filter.blockSignals(False)

    def apply_filters(self) -> None:
        if self.news_table is None or self.search_input is None:
            return
        if self.category_filter is None or self.priority_filter is None:
            return

        query = self.search_input.text().strip().lower()
        category = self.category_filter.currentText()
        priority = self.priority_filter.currentText()
        for row in range(self.news_model.rowCount()):
            index = self.news_model.index(row, 0)
            news_item = index.data(METADATA_ROLE)
            if not isinstance(news_item, NewsItem):
                self.news_table.setRowHidden(row, True)
                continue

            matches_query = not query or query in news_item.search_text
            matches_category = category == "All Categories" or news_item.category == category
            matches_priority = priority == "All Priorities" or news_item.priority == priority
            self.news_table.setRowHidden(row, not (matches_query and matches_category and matches_priority))

    def _unique_categories(self) -> list[str]:
        return sorted({item.category for item in self.news_items})

    def _state_news_signature(self, state: GameState) -> tuple[tuple[str, str, str], ...]:
        signature = []
        for raw_item in state.news:
            if len(raw_item) < 3:
                continue
            date, body, category = raw_item[:3]
            signature.append((str(date), str(body), str(category)))
        return tuple(signature)

    def _state_calendar_signature(self, state: GameState) -> tuple[object, ...]:
        macro_signature = tuple(
            (
                country,
                data.get("expected_growth"),
                data.get("expected_inflation"),
                data.get("expected_rate"),
                data.get("bip_prozent"),
                data.get("inflation"),
                data.get("arbeitslosigkeit"),
                data.get("zins"),
            )
            for country, data in sorted(state.macro.items())
        )
        history_signature = tuple((key, len(value), value[-1] if value else None) for key, value in sorted(state.macro_history.items()))
        return (state.date.strftime("%Y-%m-%d"), macro_signature, history_signature)

    def _count_priority(self, priority: str) -> int:
        return sum(1 for item in self.news_items if item.priority == priority)

    def _count_category(self, category: str) -> int:
        return sum(1 for item in self.news_items if item.category == category)

    def _count_impact(self, impact: str) -> int:
        return sum(1 for item in self.news_items if item.impact == impact)

    def _item_color(self, item: NewsItem, column: int) -> QColor | None:
        if column == 1:
            topic_colors = {
                "Solvency": "#f43f5e",
                "IPO": "#14b8a6",
                "Policy": "#22d3ee",
                "Trade": "#60a5fa",
                "Country": "#a78bfa",
                "Capacity": "#f59e0b",
                "Sector": "#c084fc",
                "Market": "#e5eef8",
            }
            return QColor(topic_colors.get(item.topic, "#8ea3b8"))
        if item.priority == "Critical":
            return QColor("#fb7185")
        if item.priority == "High":
            return QColor("#f59e0b")
        if item.impact in {"Bearish", "Tightening"}:
            return QColor("#f43f5e")
        if item.impact in {"Bullish", "Easing", "Stabilizing"}:
            return QColor("#14b8a6")
        if item.category in {"Central Bank", "Macro"}:
            return QColor("#22d3ee")
        return None

    def _tag(self, item: NewsItem) -> str:
        if item.priority == "Critical":
            return "CRITICAL"
        if item.priority == "High":
            return "ALERT"
        if item.topic != "General":
            return item.topic.upper()
        if item.impact in {"Bullish", "Bearish"}:
            return "MARKET"
        return "INFO"


def _news_item_from_current_row(row: dict[str, object]) -> NewsItem:
    date = str(row.get("date", ""))
    body = translate_news_text(str(row.get("body", "")).strip())
    category = normalize_category(str(row.get("category", "")))
    headline = body.splitlines()[0].strip() if body else "News"
    topic = classify_topic(body, category)
    priority = classify_priority(body, category)
    impact = classify_impact(body, category)
    search_text = f"{date} {topic} {category} {headline} {body} {priority} {impact}".lower()
    return NewsItem(date, topic, category, headline, body, priority, impact, search_text)


def _calendar_value(value: float | None) -> str:
    if value is None:
        return "-"
    return percent(float(value) * 100.0)
