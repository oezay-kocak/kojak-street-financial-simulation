"""Model/view table model for the market universe."""

from __future__ import annotations

from typing import Any, ClassVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from kojakstreet.core.market_data_service import MarketDataService
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.display import display_label, display_text
from kojakstreet.ui_qt.formatters import percent, regional_money

SORT_ROLE = Qt.ItemDataRole.UserRole + 1
POSITIVE_COLOR = QColor("#14b8a6")
NEGATIVE_COLOR = QColor("#f43f5e")


class MarketTableModel(QAbstractTableModel):
    HEADERS: ClassVar[tuple[str, ...]] = (
        "",
        "Ticker",
        "Name",
        "Type",
        "Region",
        "Sector",
        "Price",
        "Change",
        "Market Cap",
    )

    def __init__(self, state: GameState, watchlist: set[str]) -> None:
        super().__init__()
        self.rows = build_market_rows(state, watchlist)
        self._row_lookup = _market_row_lookup(self.rows)
        self.price_header = "Price"
        self.market_cap_header = "Market Cap"

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent and parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent and parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return row["values"][column]
        if role == SORT_ROLE:
            return row["sort_values"][column]
        if role == Qt.ItemDataRole.TextAlignmentRole and column in {6, 7, 8}:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.TextAlignmentRole and column == 0:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.ForegroundRole and column == 7:
            return POSITIVE_COLOR if row["change"] >= 0 else NEGATIVE_COLOR
        if role == Qt.ItemDataRole.UserRole:
            return row
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == 6:
                return self.price_header
            if section == 8:
                return self.market_cap_header
            return self.HEADERS[section]
        return None

    def set_price_header(self, text: str) -> None:
        if self.price_header == text:
            return
        self.price_header = text
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 6, 6)

    def set_market_cap_header(self, text: str) -> None:
        if self.market_cap_header == text:
            return
        self.market_cap_header = text
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 8, 8)

    def refresh(self, state: GameState, watchlist: set[str], *, emit_changes: bool = True) -> bool:
        if _update_existing_market_rows(self.rows, state, watchlist):
            if emit_changes:
                self.emit_price_rows(range(len(self.rows)))
            return False

        next_rows = build_market_rows(state, watchlist)
        self.beginResetModel()
        self.rows = next_rows
        self._row_lookup = _market_row_lookup(self.rows)
        self.endResetModel()
        return True

    def apply_quote_rows(self, quotes: list[dict[str, Any]], watchlist: set[str]) -> list[int]:
        changed_rows: list[int] = []
        for quote in quotes:
            key = (str(quote.get("asset_type", "")), str(quote.get("ticker", "")))
            index = self._row_lookup.get(key)
            if index is None:
                continue
            row = self.rows[index]
            price = float(quote.get("price", 0.0))
            change = float(quote.get("change", 0.0))
            market_cap = float(quote.get("market_cap", 0.0))
            region = str(quote.get("region", row["region"]))
            watched = row["ticker"] in watchlist
            data = row.get("data")
            if isinstance(data, dict):
                data["kurs"] = price
                data["aenderung"] = change
                data["market_cap"] = market_cap
            row["change"] = change
            row["region"] = region
            row["watchlist"] = watched
            row["values"][0] = "*" if watched else ""
            row["values"][6] = f"{price:,.2f}"
            row["values"][7] = percent(change)
            row["values"][8] = regional_money(market_cap, region)
            row["sort_values"][0] = 1 if watched else 0
            row["sort_values"][6] = price
            row["sort_values"][7] = change
            row["sort_values"][8] = market_cap
            changed_rows.append(index)
        return changed_rows

    def emit_price_rows(self, source_rows: range | list[int] | set[int]) -> None:
        if not self.rows:
            return
        roles = [
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ForegroundRole,
            SORT_ROLE,
        ]
        for start, end in _contiguous_ranges(sorted(set(source_rows))):
            if start < 0 or end >= len(self.rows):
                continue
            top_left = self.index(start, 6)
            bottom_right = self.index(end, len(self.HEADERS) - 1)
            self.dataChanged.emit(top_left, bottom_right, roles)

    def row_for_ticker(self, ticker: str | None) -> int:
        return self.row_for_asset(ticker, None)

    def row_for_asset(self, ticker: str | None, asset_type: str | None) -> int:
        if ticker is None:
            return 0
        if asset_type is not None:
            return self._row_lookup.get((asset_type, ticker), 0)
        for row_asset_type in ("Index", "Stock", "Commodity", "Crypto", "Fund", "Derivative"):
            index = self._row_lookup.get((row_asset_type, ticker))
            if index is not None:
                return index
        return 0


class MarketFilterProxyModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self.query = ""
        self.query_is_ticker = False
        self.asset_type = "All"
        self.region_filter = "All Regions"
        self.group_filter = "All Groups"
        self._source_model: MarketTableModel | None = None
        self._accepted_rows: list[int] = []
        self._loaded_rows = 0
        self._batch_size = 160
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder

    def setSourceModel(self, model: MarketTableModel) -> None:
        self.beginResetModel()
        self._source_model = model
        self._accepted_rows = list(range(model.rowCount()))
        self._loaded_rows = min(self._batch_size, len(self._accepted_rows))
        model.dataChanged.connect(self._source_data_changed)
        model.headerDataChanged.connect(self.headerDataChanged.emit)
        self.endResetModel()

    def sourceModel(self) -> MarketTableModel | None:
        return self._source_model

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent and parent.isValid() else self._loaded_rows

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        model = self._source_model
        return 0 if model is None or (parent and parent.isValid()) else model.columnCount()

    def canFetchMore(self, parent: QModelIndex | None = None) -> bool:
        return not (parent and parent.isValid()) and self._loaded_rows < len(self._accepted_rows)

    def fetchMore(self, parent: QModelIndex | None = None) -> None:
        if parent and parent.isValid():
            return
        remaining = len(self._accepted_rows) - self._loaded_rows
        if remaining <= 0:
            return
        amount = min(self._batch_size, remaining)
        first = self._loaded_rows
        last = self._loaded_rows + amount - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self._loaded_rows += amount
        self.endInsertRows()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        source_index = self.mapToSource(index)
        if not source_index.isValid() or self._source_model is None:
            return None
        return self._source_model.data(source_index, role)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if self._source_model is None:
            return None
        return self._source_model.headerData(section, orientation, role)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        self._sort_column = column
        self._sort_order = order
        self._rebuild_indices(keep_loaded=True)

    def mapToSource(self, index: QModelIndex) -> QModelIndex:
        if self._source_model is None or not index.isValid():
            return QModelIndex()
        row = index.row()
        if row < 0 or row >= self._loaded_rows or row >= len(self._accepted_rows):
            return QModelIndex()
        return self._source_model.index(self._accepted_rows[row], index.column())

    def mapFromSource(self, source_index: QModelIndex) -> QModelIndex:
        if self._source_model is None or not source_index.isValid():
            return QModelIndex()
        try:
            proxy_row = self._accepted_rows.index(source_index.row())
        except ValueError:
            return QModelIndex()
        if proxy_row >= self._loaded_rows:
            self._grow_to_row(proxy_row)
        return self.index(proxy_row, source_index.column())

    def set_filters(
        self,
        query: str,
        asset_type: str,
        region_filter: str = "All Regions",
        group_filter: str = "All Groups",
    ) -> bool:
        next_query = query.strip().lower()
        model = self.sourceModel()
        next_query_is_ticker = (
            bool(next_query)
            and isinstance(model, MarketTableModel)
            and any(row["ticker"].lower() == next_query for row in model.rows)
        )
        if (
            self.query == next_query
            and self.query_is_ticker == next_query_is_ticker
            and self.asset_type == asset_type
            and self.region_filter == region_filter
            and self.group_filter == group_filter
        ):
            return False
        self.query = next_query
        self.query_is_ticker = next_query_is_ticker
        self.asset_type = asset_type
        self.region_filter = region_filter
        self.group_filter = group_filter
        self._rebuild_indices(keep_loaded=False)
        return True

    def refilter(self, *, keep_loaded: bool = True) -> None:
        self._rebuild_indices(keep_loaded=keep_loaded)

    def source_rows_for_proxy_range(self, first_proxy_row: int, last_proxy_row: int) -> list[int]:
        first = max(0, first_proxy_row)
        last = min(last_proxy_row, self._loaded_rows - 1, len(self._accepted_rows) - 1)
        if last < first:
            return []
        return self._accepted_rows[first : last + 1]

    def _accepts_row(self, source_row: int) -> bool:
        model = self._source_model
        if model is None or source_row < 0 or source_row >= len(model.rows):
            return False
        row = model.rows[source_row]
        matches_query = (
            not self.query
            or row["ticker"].lower() == self.query
            or (not self.query_is_ticker and self.query in row["search"])
        )
        matches_type = (
            self.asset_type == "All"
            or row["asset_type"] == self.asset_type
            or (self.asset_type == "Watchlist" and row["watchlist"])
        )
        return matches_query and matches_type and self._matches_region(row) and self._matches_group(row)

    def _matches_region(self, row: dict[str, Any]) -> bool:
        return self.region_filter in {"", "All Regions"} or row["region"] == self.region_filter

    def _matches_group(self, row: dict[str, Any]) -> bool:
        return self.group_filter in {"", "All Groups"} or row["filter_group"] == self.group_filter

    def _rebuild_indices(self, *, keep_loaded: bool) -> None:
        model = self._source_model
        if model is None:
            return
        previous_loaded = self._loaded_rows if keep_loaded else self._batch_size
        accepted_rows = [row for row in range(len(model.rows)) if self._accepts_row(row)]
        if 0 <= self._sort_column < model.columnCount():
            reverse = self._sort_order == Qt.SortOrder.DescendingOrder
            accepted_rows.sort(key=lambda row: _sort_key(model.rows[row]["sort_values"][self._sort_column]), reverse=reverse)
        self.beginResetModel()
        self._accepted_rows = accepted_rows
        self._loaded_rows = min(max(self._batch_size, previous_loaded), len(self._accepted_rows))
        self.endResetModel()

    def _grow_to_row(self, proxy_row: int) -> None:
        while proxy_row >= self._loaded_rows and self._loaded_rows < len(self._accepted_rows):
            self.fetchMore()

    def _source_data_changed(self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list[int]) -> None:
        if self._source_model is None or not top_left.isValid() or not bottom_right.isValid():
            return
        first_source = top_left.row()
        last_source = bottom_right.row()
        changed_proxy_rows = [
            proxy_row
            for proxy_row, source_row in enumerate(self._accepted_rows[: self._loaded_rows])
            if first_source <= source_row <= last_source
        ]
        for start, end in _contiguous_ranges(changed_proxy_rows):
            self.dataChanged.emit(
                self.index(start, top_left.column()),
                self.index(end, bottom_right.column()),
                roles,
            )


def _sort_key(value: object) -> tuple[int, object]:
    if isinstance(value, (int, float)):
        return (0, value)
    return (1, str(value).lower())


def _market_row_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    return {
        (str(row["asset_type"]), str(row["ticker"])): index
        for index, row in enumerate(rows)
    }


def build_market_rows(state: GameState, watchlist: set[str]) -> list[dict[str, Any]]:
    order = {"Index": 0, "Stock": 1, "Commodity": 2, "Crypto": 3, "Fund": 4, "Derivative": 5}
    quotes = sorted(MarketDataService(state).quotes(), key=lambda quote: (order.get(quote.asset_type, 99), quote.ticker))
    return [_asset_row(quote.ticker, quote.data, quote.asset_type, watchlist, region=quote.region) for quote in quotes]


def _same_market_shape(current_rows: list[dict[str, Any]], next_rows: list[dict[str, Any]]) -> bool:
    if len(current_rows) != len(next_rows):
        return False
    return all(
        current["ticker"] == next_row["ticker"] and current["asset_type"] == next_row["asset_type"]
        for current, next_row in zip(current_rows, next_rows)
    )


def _update_existing_market_rows(rows: list[dict[str, Any]], state: GameState, watchlist: set[str]) -> bool:
    service = MarketDataService(state)
    if not rows:
        return False
    for row in rows:
        quote = service.quote(row["ticker"])
        if quote is None or quote.asset_type != row["asset_type"]:
            return False
        data = quote.data
        price = quote.price
        change = quote.change
        market_cap = quote.market_cap
        region = quote.region
        watched = row["ticker"] in watchlist
        row["data"] = data
        row["change"] = change
        row["region"] = region
        row["watchlist"] = watched
        row["values"][0] = "*" if watched else ""
        row["values"][6] = f"{price:,.2f}"
        row["values"][7] = percent(change)
        row["values"][8] = regional_money(market_cap, region)
        row["sort_values"][0] = 1 if watched else 0
        row["sort_values"][6] = price
        row["sort_values"][7] = change
        row["sort_values"][8] = market_cap
    return True


def _contiguous_ranges(rows: list[int]) -> list[tuple[int, int]]:
    if not rows:
        return []
    ranges = []
    start = previous = rows[0]
    for row in rows[1:]:
        if row == previous + 1:
            previous = row
            continue
        ranges.append((start, previous))
        start = previous = row
    ranges.append((start, previous))
    return ranges


def _asset_rows(assets: dict, asset_type: str, watchlist: set[str]) -> list[dict[str, Any]]:
    return [_asset_row(str(ticker), data, asset_type, watchlist) for ticker, data in assets.items()]


def _asset_row(
    ticker: str,
    data: dict[str, Any],
    asset_type: str,
    watchlist: set[str],
    *,
    region: str | None = None,
) -> dict[str, Any]:
    price = float(data.get("kurs", 0.0))
    change = float(data.get("aenderung", 0.0))
    market_cap = float(data.get("market_cap", data.get("aum", 0.0)))
    region = str(region or data.get("land", data.get("ziel", "GD")))
    sector = _asset_sector(data, asset_type)
    filter_group = _asset_filter_group(data, asset_type, sector)
    display_name = display_text(data.get("name", ticker))
    display_region = display_label(region)
    display_sector = display_label(sector)
    type_label = "Funds and ETFs" if asset_type == "Fund" else "Derivatives" if asset_type == "Derivative" else asset_type
    return {
        "ticker": ticker,
        "asset_type": asset_type,
        "data": data,
        "change": change,
        "region": region,
        "sector": sector,
        "filter_group": filter_group,
        "search": " ".join(
            [
                ticker,
                str(data.get("name", ticker)),
                display_name,
                asset_type,
                type_label,
                region,
                display_region,
                sector,
                display_sector,
                filter_group,
                display_label(filter_group),
            ]
        ).lower(),
        "watchlist": ticker in watchlist,
        "values": [
            "*" if ticker in watchlist else "",
            ticker,
            display_name,
            type_label,
            display_region,
            display_sector,
            f"{price:,.2f}",
            percent(change),
            regional_money(market_cap, region),
        ],
        "sort_values": [
            1 if ticker in watchlist else 0,
            ticker,
            display_name,
            type_label,
            display_region,
            display_sector,
            price,
            change,
            market_cap,
        ],
    }


def _asset_sector(data: dict, asset_type: str) -> str:
    return str(data.get("branche", data.get("kategorie", data.get("typ", ""))))


def _asset_filter_group(data: dict, asset_type: str, sector: str) -> str:
    if asset_type == "Derivative":
        return str(data.get("instrument_type", sector))
    if asset_type == "Fund":
        return str(data.get("fund_type", sector))
    return sector
