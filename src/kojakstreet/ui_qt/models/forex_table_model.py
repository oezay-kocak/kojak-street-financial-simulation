"""Model/view table model for forex pairs."""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor

from kojakstreet.core.forex import ForexPair, build_forex_pairs
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.formatters import percent

SORT_ROLE = Qt.ItemDataRole.UserRole + 1
POSITIVE_COLOR = QColor("#14b8a6")
NEGATIVE_COLOR = QColor("#f43f5e")


class ForexTableModel(QAbstractTableModel):
    HEADERS: ClassVar[tuple[str, ...]] = ("Pair", "Base", "Quote", "Rate", "Daily Change")

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self.pair_group = "GLD Pairs"
        self.base_rows = build_forex_rows(state)
        self.rows = prioritized_pair_rows(self.base_rows, self.pair_group)
        self.loaded_rows = min(420, len(self.rows))
        self.batch_size = 420

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent and parent.isValid() else self.loaded_rows

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent and parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if index.row() < 0 or index.row() >= self.loaded_rows:
            return None
        row = self.rows[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return row["values"][column]
        if role == SORT_ROLE:
            return row["sort_values"][column]
        if role == Qt.ItemDataRole.TextAlignmentRole and column in {3, 4}:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and column == 4:
            return POSITIVE_COLOR if row["pair"].change_percent >= 0 else NEGATIVE_COLOR
        if role == Qt.ItemDataRole.UserRole:
            return row["pair"]
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
        return not (parent and parent.isValid()) and self.loaded_rows < len(self.rows)

    def fetchMore(self, parent: QModelIndex | None = None) -> None:
        if parent and parent.isValid():
            return
        remaining = len(self.rows) - self.loaded_rows
        if remaining <= 0:
            return
        amount = min(self.batch_size, remaining)
        first = self.loaded_rows
        last = self.loaded_rows + amount - 1
        self.beginInsertRows(QModelIndex(), first, last)
        self.loaded_rows += amount
        self.endInsertRows()

    def refresh(self, state: GameState) -> None:
        self.refresh_rows(build_forex_rows(state))

    def refresh_rows(self, rows: list[dict]) -> None:
        next_rows = prioritized_pair_rows(rows, self.pair_group)
        self.base_rows = rows
        if _same_pair_shape(self.rows, next_rows):
            self.rows = next_rows
            if self.rows:
                top_left = self.index(0, 3)
                bottom_right = self.index(self.loaded_rows - 1, 4)
                self.dataChanged.emit(
                    top_left,
                    bottom_right,
                    [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole, SORT_ROLE],
                )
            return
        self.beginResetModel()
        self.rows = next_rows
        self.loaded_rows = min(self.batch_size, len(self.rows))
        self.endResetModel()

    def set_pair_group(self, pair_group: str) -> None:
        if self.pair_group == pair_group:
            return
        self.pair_group = pair_group
        self.beginResetModel()
        self.rows = prioritized_pair_rows(self.base_rows, pair_group)
        self.loaded_rows = min(self.batch_size, len(self.rows))
        self.endResetModel()

    def row_for_pair(self, pair_name: str | None) -> int:
        if pair_name is None:
            return 0
        for index, row in enumerate(self.rows):
            if row["pair"].pair == pair_name:
                if index >= self.loaded_rows:
                    self._grow_to_row(index)
                return index
        return 0

    def _grow_to_row(self, row: int) -> None:
        while row >= self.loaded_rows and self.loaded_rows < len(self.rows):
            self.fetchMore()


class ForexFilterProxyModel(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self.query = ""
        self.pair_group = "GLD Pairs"
        self.setDynamicSortFilter(False)

    def set_filters(self, query: str, pair_group: str) -> bool:
        next_query = query.strip().lower()
        if self.query == next_query and self.pair_group == pair_group:
            return False
        self.beginFilterChange()
        self.query = next_query
        self.pair_group = pair_group
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        return True

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not isinstance(model, ForexTableModel):
            return True
        row = model.rows[source_row]
        pair: ForexPair = row["pair"]
        matches_query = not self.query or self.query in row["search"]
        matches_pair_group = self.pair_group == "All Pairs" or _group_currency(self.pair_group) in {
            pair.base,
            pair.quote,
        }
        return matches_query and matches_pair_group

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        left_value = left.data(SORT_ROLE)
        right_value = right.data(SORT_ROLE)
        if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            return left_value < right_value
        return str(left_value).lower() < str(right_value).lower()


def build_forex_rows(state: GameState) -> list[dict]:
    rows = []
    for pair in build_forex_pairs(state):
        rows.append(
            {
                "pair": pair,
                "search": f"{pair.pair} {pair.base} {pair.quote}".lower(),
                "values": [
                    pair.pair,
                    pair.base,
                    pair.quote,
                    f"{pair.rate:.6f}",
                    percent(pair.change_percent),
                ],
                "sort_values": [
                    pair.pair,
                    pair.base,
                    pair.quote,
                    pair.rate,
                    pair.change_percent,
                ],
            }
        )
    return rows


def prioritized_pair_rows(rows: list[dict], pair_group: str) -> list[dict]:
    currency = _group_currency(pair_group)
    if pair_group == "All Pairs" or not currency:
        return sorted(rows, key=lambda row: row["pair"].pair)
    return sorted(
        rows,
        key=lambda row: (
            0 if row["pair"].base == currency else 1,
            row["pair"].quote,
            row["pair"].pair,
        ),
    )


def _same_pair_shape(current_rows: list[dict], next_rows: list[dict]) -> bool:
    if len(current_rows) != len(next_rows):
        return False
    return all(current["pair"].pair == next_row["pair"].pair for current, next_row in zip(current_rows, next_rows))


def _group_currency(pair_group: str) -> str:
    return pair_group.removesuffix(" Pairs")
