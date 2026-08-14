"""Bond market workspace view."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, ClassVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from kojakstreet.core.bonds import BondOffer, build_bond_offers
from kojakstreet.core.ratings import RATINGS
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.display import display_label, display_text
from kojakstreet.ui_qt.formatters import percent
from kojakstreet.ui_qt.table_performance import optimize_table_view
from kojakstreet.ui_qt.widgets.stock_detail_dialog import StockDetailView
from kojakstreet.ui_qt.widgets.view_header import ViewHeader

BOND_HIGH_YIELD_COLOR = QColor("#f59e0b")
BOND_DEFAULT_COLOR = QColor("#e5eef8")
MATURITY_BUCKETS = ("0-3Y", "3-7Y", "7-15Y", "15Y+")


class BondMarketView(QFrame):
    """Read-only bond market offer sheet using the legacy yield concept."""

    def __init__(
        self,
        state: GameState,
        history_provider: Callable[[str, int], list] | None = None,
        current_provider: Callable[[], list[dict[str, object]]] | None = None,
    ) -> None:
        super().__init__()
        self.state = state
        self.history_provider = history_provider
        self.current_provider = current_provider
        self.all_offers = self._current_offers() or build_bond_offers(state, "All")
        self.offers = []
        self.table: QTableView | None = None
        self.model = BondOfferTableModel(self.offers)
        self.category_filter: QComboBox | None = None
        self.region_filter: QComboBox | None = None
        self.rating_filter: QComboBox | None = None
        self.maturity_filter: QComboBox | None = None
        self.kpi_values: dict[str, QLabel] = {}
        self.market_signature = _bond_market_signature(state.bond_market)
        self.offer_signature = _offers_signature(self.offers)
        self.pages = QStackedWidget()
        self.main_page = QWidget()
        self.bond_detail_view = StockDetailView()
        self.bond_detail_view.back_requested.connect(self._show_bond_list)
        self.setObjectName("Panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        main_layout = QVBoxLayout(self.main_page)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)
        layout.addWidget(
            ViewHeader(
                "Bondmarket",
                "Government and corporate bond yields based on local rates and issuer rating",
                ["Refresh", "Export"],
            )
        )
        main_layout.addLayout(self._build_kpis())
        main_layout.addLayout(self._build_toolbar())
        self._reload_offers()
        self.offer_signature = _offers_signature(self.offers)
        self.model.set_offers(self.offers)
        self._refresh_kpis()
        main_layout.addWidget(self._build_table(), 1)
        self.pages.addWidget(self.main_page)
        self.pages.addWidget(self.bond_detail_view)
        layout.addWidget(self.pages, 1)

    def refresh(self, state: GameState, *, throttle_charts: bool = False) -> None:
        self.state = state
        current_offers = self._current_offers()
        if current_offers:
            next_market_signature = _offers_signature(current_offers)
            market_changed = next_market_signature != self.market_signature
            if market_changed:
                self.market_signature = next_market_signature
                self.all_offers = current_offers
                self._populate_filter()
                self._populate_secondary_filters()
            self._reload_offers()
            self._apply_offer_changes(throttle_charts=throttle_charts)
            return

        next_market_signature = _bond_market_signature(state.bond_market)
        market_changed = next_market_signature != self.market_signature
        if market_changed:
            self.market_signature = next_market_signature
            self.all_offers = build_bond_offers(state, "All")
            self._populate_filter()
            self._populate_secondary_filters()
        self._reload_offers()
        next_signature = _offers_signature(self.offers)
        signature_changed = next_signature != self.offer_signature
        if signature_changed:
            self.offer_signature = next_signature
            self._refresh_kpis()
            if self.table is not None:
                self._fill_table()
        if not throttle_charts and self.pages.currentWidget() is self.bond_detail_view and self.bond_detail_view.ticker:
            offer = self._offer_by_symbol(self.bond_detail_view.ticker)
            if offer is not None:
                self._update_bond_detail(offer)

    def apply_live_current_rows(self, rows: list[dict[str, object]]) -> None:
        if not rows:
            return
        selected_symbol = self._selected_symbol()
        if len(rows) != len(self.all_offers):
            self.all_offers = _offers_from_current_rows(rows, self.state.date)
            self.market_signature = _offers_signature(self.all_offers)
            self._populate_filter()
            self._populate_secondary_filters()
            self._reload_offers()
        else:
            current_by_symbol = {str(row.get("symbol", "")): row for row in rows}
            for offer in self.offers:
                if row := current_by_symbol.get(offer.symbol):
                    _update_offer_from_current_row(offer, row, self.state.date)
        self._apply_offer_changes(throttle_charts=False)
        self._select_symbol(selected_symbol)

    def _build_kpis(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        for label, value in self._kpi_items():
            row.addWidget(self._kpi_card(label, value))
        row.addStretch(1)
        return row

    def _kpi_card(self, label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("KpiCard")
        frame.setMinimumWidth(145)
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

    def _kpi_items(self) -> list[tuple[str, str]]:
        government = [offer for offer in self.offers if offer.category == "Government"]
        corporate = [offer for offer in self.offers if offer.category != "Government"]
        return [
            ("Offers", str(len(self.offers))),
            ("Government", str(len(government))),
            ("Corporate", str(len(corporate))),
            ("Avg Yield", percent(_average([offer.yield_to_maturity for offer in self.offers]) * 100)),
            ("Avg Price", f"{_average([offer.price for offer in self.offers]):.2f}"),
        ]

    def _refresh_kpis(self) -> None:
        for label, value in self._kpi_items():
            self.kpi_values[label].setText(value)

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.category_filter = QComboBox()
        self.category_filter.setObjectName("BondCategoryFilter")
        self.category_filter.setMinimumWidth(180)
        self.category_filter.view().setMinimumWidth(230)
        self._populate_filter()
        self.category_filter.currentTextChanged.connect(self._category_changed)
        self.region_filter = QComboBox()
        self.region_filter.setObjectName("BondRegionFilter")
        self.region_filter.setMinimumWidth(180)
        self.region_filter.view().setMinimumWidth(240)
        self.region_filter.currentTextChanged.connect(self._region_changed)
        self.rating_filter = QComboBox()
        self.rating_filter.setObjectName("BondRatingFilter")
        self.rating_filter.setMinimumWidth(120)
        self.rating_filter.currentTextChanged.connect(self._rating_changed)
        self.maturity_filter = QComboBox()
        self.maturity_filter.setObjectName("BondMaturityFilter")
        self.maturity_filter.setMinimumWidth(130)
        self.maturity_filter.currentTextChanged.connect(self.apply_filter)
        self._populate_secondary_filters()
        toolbar.addStretch(1)
        toolbar.addWidget(self.category_filter)
        toolbar.addWidget(self.region_filter)
        toolbar.addWidget(self.rating_filter)
        toolbar.addWidget(self.maturity_filter)
        return toolbar

    def _build_table(self) -> QTableView:
        table = QTableView()
        self.table = table
        table.setObjectName("BondMarketTable")
        table.setModel(self.model)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        table.setSortingEnabled(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSortIndicatorShown(True)
        optimize_table_view(table, row_height=34)
        table.doubleClicked.connect(self._open_bond_detail)
        return table

    def _fill_table(self) -> None:
        if self.table is None:
            return
        self.model.set_offers(self.offers)

    def _row_values(self, offer: BondOffer) -> list[str]:
        return [
            offer.symbol,
            display_text(offer.issuer),
            display_label(offer.issuer_type),
            display_label(offer.category),
            display_label(offer.region),
            offer.rating,
            f"{offer.price:.2f}",
            percent(offer.coupon * 100),
            percent(offer.yield_to_maturity * 100),
            f"{offer.maturity_years:.1f}Y",
            f"{offer.duration:.1f}",
            percent(offer.default_risk * 100),
            percent(offer.liquidity * 100),
        ]

    def _populate_filter(self) -> None:
        if self.category_filter is None:
            return
        current = self.category_filter.currentData() or "Government"
        categories = sorted({offer.category for offer in self.all_offers if offer.category and offer.category != "Government"})
        options = ["Government", *categories]
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        for option in options:
            self.category_filter.addItem(display_label(option), option)
        self.category_filter.setCurrentIndex(options.index(current) if current in options else 0)
        self.category_filter.blockSignals(False)
        self._populate_secondary_filters()

    def _populate_secondary_filters(self) -> None:
        if self.region_filter is None or self.rating_filter is None or self.maturity_filter is None:
            return
        category = self.category_filter.currentData() if self.category_filter is not None else "Government"
        region_current = self.region_filter.currentData()
        rating_current = self.rating_filter.currentText()
        maturity_current = self.maturity_filter.currentText()
        category_offers = [offer for offer in self.all_offers if _matches_category(offer, str(category))]
        regions = sorted({offer.region for offer in category_offers if offer.region})
        selected_region = region_current if region_current in regions else (regions[0] if regions else "")
        available_ratings = {
            offer.rating
            for offer in category_offers
            if offer.region == selected_region and offer.rating
        }
        ratings = [rating for rating in RATINGS if rating in available_ratings]
        selected_rating = _preferred_rating(rating_current, available_ratings)
        maturities = _available_maturities(category_offers, selected_region, selected_rating)
        selected_maturity = _preferred_maturity(maturity_current, maturities)
        self.region_filter.blockSignals(True)
        self.rating_filter.blockSignals(True)
        self.maturity_filter.blockSignals(True)
        self.region_filter.clear()
        self.rating_filter.clear()
        self.maturity_filter.clear()
        for region in regions:
            self.region_filter.addItem(display_label(region), region)
        self.rating_filter.addItems(ratings)
        self.maturity_filter.addItems(maturities)
        self.region_filter.setCurrentIndex(regions.index(selected_region) if selected_region in regions else 0)
        self.rating_filter.setCurrentText(selected_rating)
        self.maturity_filter.setCurrentText(selected_maturity)
        self.region_filter.blockSignals(False)
        self.rating_filter.blockSignals(False)
        self.maturity_filter.blockSignals(False)

    def apply_filter(self) -> None:
        self._reload_offers()
        self.offer_signature = _offers_signature(self.offers)
        self._refresh_kpis()
        if self.table is not None:
            self._fill_table()

    def _category_changed(self) -> None:
        self._populate_secondary_filters()
        self.apply_filter()

    def _region_changed(self) -> None:
        self._populate_secondary_filters()
        self.apply_filter()

    def _rating_changed(self) -> None:
        self._populate_maturity_filter()
        self.apply_filter()

    def _populate_maturity_filter(self) -> None:
        if (
            self.category_filter is None
            or self.region_filter is None
            or self.rating_filter is None
            or self.maturity_filter is None
        ):
            return
        category = str(self.category_filter.currentData() or "Government")
        region = str(self.region_filter.currentData() or "")
        rating = self.rating_filter.currentText()
        category_offers = [offer for offer in self.all_offers if _matches_category(offer, category)]
        maturities = _available_maturities(category_offers, region, rating)
        selected_maturity = _preferred_maturity(self.maturity_filter.currentText(), maturities)
        self.maturity_filter.blockSignals(True)
        self.maturity_filter.clear()
        self.maturity_filter.addItems(maturities)
        self.maturity_filter.setCurrentText(selected_maturity)
        self.maturity_filter.blockSignals(False)

    def _reload_offers(self) -> None:
        category = self.category_filter.currentData() if self.category_filter is not None else "Government"
        region = self.region_filter.currentData() if self.region_filter is not None else ""
        rating = self.rating_filter.currentText() if self.rating_filter is not None else ""
        maturity = self.maturity_filter.currentText() if self.maturity_filter is not None else MATURITY_BUCKETS[0]
        self.offers = self._filtered_offers(str(category), str(region), str(rating), str(maturity))

    def _apply_offer_changes(self, *, throttle_charts: bool) -> None:
        next_signature = _offers_signature(self.offers)
        signature_changed = next_signature != self.offer_signature
        if signature_changed:
            self.offer_signature = next_signature
            self._refresh_kpis()
            if self.table is not None:
                self._fill_table()
        if not throttle_charts and self.pages.currentWidget() is self.bond_detail_view and self.bond_detail_view.ticker:
            offer = self._offer_by_symbol(self.bond_detail_view.ticker)
            if offer is not None:
                self._update_bond_detail(offer)

    def _filtered_offers(self, category: str, region: str, rating: str, maturity: str) -> list[BondOffer]:
        return [
            offer
            for offer in self.all_offers
            if _matches_category(offer, category)
            and offer.region == region
            and offer.rating == rating
            and _matches_maturity(offer, maturity)
        ]

    def _open_bond_detail(self, index: QModelIndex | int) -> None:
        if self.table is None:
            return
        row = index if isinstance(index, int) else index.row()
        if row < 0:
            return
        offer = self.model.offer_at(row)
        if offer is None:
            return
        self._update_bond_detail(offer)
        self.pages.setCurrentWidget(self.bond_detail_view)

    def _update_bond_detail(self, offer: BondOffer) -> None:
        history = self._bond_history(offer.symbol)
        if len(history) < 2:
            history = [(offer.price, "", ""), (offer.price, "", "")]
        self.bond_detail_view.update_asset(
            offer.symbol,
            {
                "name": offer.issuer,
                "historie": history,
                "kurs": offer.price,
                "aenderung": 0.0,
            },
            "Bond",
        )

    def _show_bond_list(self) -> None:
        self.pages.setCurrentWidget(self.main_page)

    def _offer_by_symbol(self, symbol: str) -> BondOffer | None:
        for offer in self.offers:
            if offer.symbol == symbol:
                return offer
        return None

    def _bond_history(self, symbol: str) -> list:
        if self.history_provider is not None:
            history = self.history_provider(symbol, 520)
            if history:
                return history
        for bond in self.state.bond_market:
            if str(bond.get("symbol", "")) == symbol:
                return list(bond.get("historie", []))
        return []

    def _current_offers(self) -> list[BondOffer]:
        if self.current_provider is None:
            return []
        return _offers_from_current_rows(self.current_provider(), self.state.date)

    def _selected_symbol(self) -> str | None:
        if self.table is None:
            return None
        offer = self.model.offer_at(self.table.currentIndex().row())
        return offer.symbol if offer is not None else None

    def _select_symbol(self, symbol: str | None) -> None:
        if not symbol or self.table is None:
            return
        row = self.model.row_for_symbol(symbol)
        self.table.selectRow(row)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _offers_signature(offers: list[BondOffer]) -> tuple[tuple[str, float, float, float], ...]:
    return tuple(
        (offer.symbol, round(offer.price, 6), round(offer.yield_to_maturity, 6), round(offer.maturity_years, 4))
        for offer in offers
    )


def _bond_market_signature(bonds: list[dict[str, Any]]) -> tuple[int, float, float]:
    return (
        len(bonds),
        round(sum(float(bond.get("price", 0.0)) for bond in bonds), 4),
        round(sum(float(bond.get("yield_to_maturity", 0.0)) for bond in bonds), 6),
    )


def _matches_category(offer: BondOffer, category: str) -> bool:
    return category == "All" or offer.category == category


def _matches_maturity(offer: BondOffer, maturity: str) -> bool:
    years = offer.maturity_years
    if maturity == "0-3Y":
        return years <= 3.25
    if maturity == "3-7Y":
        return 3.25 < years <= 7.25
    if maturity == "7-15Y":
        return 7.25 < years <= 15.25
    if maturity == "15Y+":
        return years > 15
    return False


def _maturity_bucket(offer: BondOffer) -> str:
    for maturity in MATURITY_BUCKETS:
        if _matches_maturity(offer, maturity):
            return maturity
    return MATURITY_BUCKETS[-1]


def _available_maturities(category_offers: list[BondOffer], region: str, rating: str) -> list[str]:
    available = {
        _maturity_bucket(offer)
        for offer in category_offers
        if offer.region == region and offer.rating == rating
    }
    return [maturity for maturity in MATURITY_BUCKETS if maturity in available]


def _preferred_rating(current: str | None, available: set[str]) -> str:
    if current in available:
        return str(current)
    for rating in RATINGS:
        if rating in available:
            return rating
    return ""


def _preferred_maturity(current: str | None, available: list[str]) -> str:
    if current in available:
        return str(current)
    return available[0] if available else ""


def _offers_from_current_rows(rows: list[dict[str, object]], fallback_date: datetime) -> list[BondOffer]:
    offers = []
    for row in rows:
        symbol = str(row.get("symbol", ""))
        if not symbol:
            continue
        maturity_years = float(row.get("maturity_years", 0.0) or 0.0)
        maturity_date = _parse_current_date(str(row.get("maturity_date", "")), fallback_date, maturity_years)
        issuer_type = str(row.get("issuer_type", row.get("bond_type", "Corporate")) or "Corporate")
        offers.append(
            BondOffer(
                symbol=symbol,
                issuer=str(row.get("issuer", symbol)),
                issuer_type=issuer_type,
                category=str(row.get("category", issuer_type) or issuer_type),
                region=str(row.get("region", "")),
                rating=str(row.get("rating", "")),
                coupon=float(row.get("coupon", 0.0) or 0.0),
                yield_to_maturity=float(row.get("yield", 0.0) or 0.0),
                price=float(row.get("price", 0.0) or 0.0),
                maturity_years=maturity_years,
                duration=float(row.get("duration", maturity_years) or 0.0),
                default_risk=float(row.get("default_risk", 0.0) or 0.0),
                liquidity=float(row.get("liquidity", 0.0) or 0.0),
                maturity_date=maturity_date,
            )
        )
    return offers


def _update_offer_from_current_row(offer: BondOffer, row: dict[str, object], fallback_date: datetime) -> None:
    maturity_years = float(row.get("maturity_years", offer.maturity_years) or offer.maturity_years)
    offer.issuer = str(row.get("issuer", offer.issuer))
    offer.issuer_type = str(row.get("issuer_type", offer.issuer_type) or offer.issuer_type)
    offer.category = str(row.get("category", offer.category) or offer.category)
    offer.region = str(row.get("region", offer.region))
    offer.rating = str(row.get("rating", offer.rating))
    offer.coupon = float(row.get("coupon", offer.coupon) or 0.0)
    offer.yield_to_maturity = float(row.get("yield", offer.yield_to_maturity) or 0.0)
    offer.price = float(row.get("price", offer.price) or 0.0)
    offer.maturity_years = maturity_years
    offer.duration = float(row.get("duration", offer.duration) or 0.0)
    offer.default_risk = float(row.get("default_risk", offer.default_risk) or 0.0)
    offer.liquidity = float(row.get("liquidity", offer.liquidity) or 0.0)
    offer.maturity_date = _parse_current_date(str(row.get("maturity_date", "")), fallback_date, maturity_years)


def _parse_current_date(value: str, fallback_date: datetime, maturity_years: float) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return fallback_date + timedelta(days=max(1, round(maturity_years * 365)))


BOND_SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class BondOfferTableModel(QAbstractTableModel):
    HEADERS: ClassVar[tuple[str, ...]] = (
        "Symbol",
        "Issuer",
        "Type",
        "Category",
        "Region",
        "Rating",
        "Price",
        "Coupon",
        "Yield",
        "Maturity",
        "Duration",
        "Default Risk",
        "Liquidity",
    )

    def __init__(self, offers: list[BondOffer]) -> None:
        super().__init__()
        self.offers = offers
        self.loaded_rows = min(320, len(offers))
        self.batch_size = 320

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent and parent.isValid() else self.loaded_rows

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent and parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if index.row() < 0 or index.row() >= self.loaded_rows:
            return None
        offer = self.offers[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return _bond_cell_value(offer, column)
        if role == BOND_SORT_ROLE:
            return _bond_sort_value(offer, column)
        if role == Qt.ItemDataRole.TextAlignmentRole and column in {6, 7, 8, 9, 10, 11, 12}:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and column in {6, 7, 8, 9, 10, 11, 12}:
            return BOND_HIGH_YIELD_COLOR if offer.yield_to_maturity >= 0.06 else BOND_DEFAULT_COLOR
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def canFetchMore(self, parent: QModelIndex | None = None) -> bool:
        return not (parent and parent.isValid()) and self.loaded_rows < len(self.offers)

    def fetchMore(self, parent: QModelIndex | None = None) -> None:
        if parent and parent.isValid():
            return
        remaining = len(self.offers) - self.loaded_rows
        if remaining <= 0:
            return
        amount = min(self.batch_size, remaining)
        first = self.loaded_rows
        last = self.loaded_rows + amount - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self.loaded_rows += amount
        self.endInsertRows()

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if column < 0 or column >= len(self.HEADERS):
            return
        self.layoutAboutToBeChanged.emit()
        reverse = order == Qt.SortOrder.DescendingOrder
        self.offers.sort(key=lambda offer: _bond_sort_value(offer, column), reverse=reverse)
        self.loaded_rows = min(max(self.batch_size, self.loaded_rows), len(self.offers))
        self.layoutChanged.emit()

    def set_offers(self, offers: list[BondOffer]) -> None:
        if _offers_signature(self.offers) == _offers_signature(offers):
            self.offers = offers
            if self.offers:
                self.dataChanged.emit(
                    self.index(0, 0),
                    self.index(self.loaded_rows - 1, len(self.HEADERS) - 1),
                    [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole, BOND_SORT_ROLE],
                )
            return
        self.beginResetModel()
        self.offers = offers
        self.loaded_rows = min(self.batch_size, len(self.offers))
        self.endResetModel()

    def offer_at(self, row: int) -> BondOffer | None:
        if 0 <= row < self.loaded_rows and row < len(self.offers):
            return self.offers[row]
        return None

    def row_for_symbol(self, symbol: str | None) -> int:
        if not symbol:
            return 0
        for row, offer in enumerate(self.offers):
            if offer.symbol == symbol:
                if row >= self.loaded_rows:
                    self._grow_to_row(row)
                return row
        return 0

    def _grow_to_row(self, row: int) -> None:
        while row >= self.loaded_rows and self.loaded_rows < len(self.offers):
            self.fetchMore()


def _bond_cell_value(offer: BondOffer, column: int) -> str:
    values = (
        offer.symbol,
        display_text(offer.issuer),
        display_label(offer.issuer_type),
        display_label(offer.category),
        display_label(offer.region),
        offer.rating,
        f"{offer.price:.2f}",
        percent(offer.coupon * 100),
        percent(offer.yield_to_maturity * 100),
        f"{offer.maturity_years:.1f}Y",
        f"{offer.duration:.1f}",
        percent(offer.default_risk * 100),
        percent(offer.liquidity * 100),
    )
    return values[column]


def _bond_sort_value(offer: BondOffer, column: int) -> Any:
    values: tuple[Any, ...] = (
        offer.symbol,
        offer.issuer,
        offer.issuer_type,
        offer.category,
        offer.region,
        offer.rating,
        offer.price,
        offer.coupon,
        offer.yield_to_maturity,
        offer.maturity_years,
        offer.duration,
        offer.default_risk,
        offer.liquidity,
    )
    return values[column]
