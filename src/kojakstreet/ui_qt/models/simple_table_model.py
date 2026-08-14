"""Small reusable table model for read-only workspace tables."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor


SORT_ROLE = Qt.ItemDataRole.UserRole + 1
METADATA_ROLE = Qt.ItemDataRole.UserRole + 2

ColorCallback = Callable[[list[str], Any, int], QColor | str | None]
_UNSET = object()


class SimpleTableModel(QAbstractTableModel):
    """Read-only list-backed model with metadata, sorting and cell colors."""

    def __init__(
        self,
        headers: list[str],
        *,
        right_aligned_columns: set[int] | None = None,
        color_callback: ColorCallback | None = None,
    ) -> None:
        super().__init__()
        self.headers = list(headers)
        self.rows: list[list[str]] = []
        self.sort_values: list[list[Any]] = []
        self.metadata: list[Any] = []
        self.foreground_colors: list[list[QColor | None | object]] = []
        self.loaded_rows = 0
        self.batch_size = 160
        self.right_aligned_columns = right_aligned_columns or set()
        self.color_callback = color_callback

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else self.loaded_rows

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row_index = index.row()
        column = index.column()
        if row_index < 0 or row_index >= self.loaded_rows or column < 0 or column >= len(self.headers):
            return None
        row = self.rows[row_index]
        if role == Qt.ItemDataRole.DisplayRole:
            return row[column] if column < len(row) else ""
        if role == SORT_ROLE:
            if row_index < len(self.sort_values) and column < len(self.sort_values[row_index]):
                return self.sort_values[row_index][column]
            return row[column] if column < len(row) else ""
        if role == METADATA_ROLE:
            return self.metadata[row_index] if row_index < len(self.metadata) else None
        if role == Qt.ItemDataRole.TextAlignmentRole and column in self.right_aligned_columns:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and row_index < len(self.foreground_colors):
            colors = self.foreground_colors[row_index]
            if column < len(colors):
                color = colors[column]
                if color is _UNSET:
                    color = self._foreground_for_cell(row_index, column)
                    colors[column] = color
                return color
        return None

    def canFetchMore(self, parent: QModelIndex = QModelIndex()) -> bool:
        return not parent.isValid() and self.loaded_rows < len(self.rows)

    def fetchMore(self, parent: QModelIndex = QModelIndex()) -> None:
        if parent.isValid():
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

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.headers):
            return self.headers[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_headers(self, headers: list[str]) -> None:
        self.beginResetModel()
        self.headers = list(headers)
        self.rows = []
        self.sort_values = []
        self.metadata = []
        self.foreground_colors = []
        self.loaded_rows = 0
        self.endResetModel()

    def set_rows(
        self,
        rows: list[list[Any]],
        *,
        metadata: list[Any] | None = None,
        sort_values: list[list[Any]] | None = None,
    ) -> None:
        normalized_rows = [[str(value) for value in row] for row in rows]
        normalized_sort = sort_values if sort_values is not None else [list(row) for row in normalized_rows]
        normalized_meta = metadata if metadata is not None else [None for _ in normalized_rows]
        normalized_colors = self._empty_foreground_cache(normalized_rows)
        same_shape = (
            len(normalized_rows) == len(self.rows)
            and len(normalized_sort) == len(self.sort_values)
            and len(normalized_meta) == len(self.metadata)
            and len(normalized_colors) == len(self.foreground_colors)
            and all(len(row) == len(old_row) for row, old_row in zip(normalized_rows, self.rows, strict=True))
        )
        if same_shape:
            changed_rows = [
                index
                for index, (
                    new_row,
                    old_row,
                    new_sort,
                    old_sort,
                    new_meta,
                    old_meta,
                    new_colors,
                    old_colors,
                ) in enumerate(
                    zip(
                        normalized_rows,
                        self.rows,
                        normalized_sort,
                        self.sort_values,
                        normalized_meta,
                        self.metadata,
                        normalized_colors,
                        self.foreground_colors,
                        strict=True,
                    )
                )
                if new_row != old_row or new_sort != old_sort or new_meta != old_meta or new_colors != old_colors
            ]
            self.rows = normalized_rows
            self.sort_values = normalized_sort
            self.metadata = normalized_meta
            self.foreground_colors = normalized_colors
            if changed_rows and self.rows and self.headers:
                visible_changed_rows = [row for row in changed_rows if row < self.loaded_rows]
                if not visible_changed_rows:
                    return
                roles = [
                    Qt.ItemDataRole.DisplayRole,
                    Qt.ItemDataRole.ForegroundRole,
                    Qt.ItemDataRole.TextAlignmentRole,
                    SORT_ROLE,
                    METADATA_ROLE,
                ]
                for start, end in _contiguous_ranges(visible_changed_rows):
                    self.dataChanged.emit(
                        self.index(start, 0),
                        self.index(end, len(self.headers) - 1),
                        roles,
                    )
            return
        self.beginResetModel()
        self.rows = normalized_rows
        self.sort_values = normalized_sort
        self.metadata = normalized_meta
        self.foreground_colors = normalized_colors
        self.loaded_rows = min(self.batch_size, len(self.rows))
        self.endResetModel()

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if column < 0 or column >= len(self.headers):
            return
        combined = list(zip(self.rows, self.sort_values, self.metadata, strict=True))
        reverse = order == Qt.SortOrder.DescendingOrder

        def sort_key(item: tuple[list[str], list[Any], Any]) -> tuple[int, Any]:
            values = item[1]
            value = values[column] if column < len(values) else ""
            try:
                return (0, float(value))
            except (TypeError, ValueError):
                return (1, str(value).lower())

        self.layoutAboutToBeChanged.emit()
        combined.sort(key=sort_key, reverse=reverse)
        self.rows = [item[0] for item in combined]
        self.sort_values = [item[1] for item in combined]
        self.metadata = [item[2] for item in combined]
        self.foreground_colors = self._empty_foreground_cache(self.rows)
        self.loaded_rows = min(max(self.batch_size, self.loaded_rows), len(self.rows))
        self.layoutChanged.emit()

    def metadata_at(self, row: int) -> Any:
        if 0 <= row < len(self.metadata):
            return self.metadata[row]
        return None

    def ensure_row_loaded(self, row: int) -> None:
        while row >= self.loaded_rows and self.loaded_rows < len(self.rows):
            self.fetchMore()

    def total_row_count(self) -> int:
        return len(self.rows)

    def _empty_foreground_cache(self, rows: list[list[str]]) -> list[list[QColor | None | object]]:
        if self.color_callback is None:
            return [[None for _ in self.headers] for _ in rows]
        return [[_UNSET for _ in self.headers] for _ in rows]

    def _foreground_for_cell(self, row_index: int, column: int) -> QColor | None:
        if self.color_callback is None:
            return None
        row = self.rows[row_index]
        meta = self.metadata[row_index] if row_index < len(self.metadata) else None
        color = self.color_callback(row, meta, column)
        if isinstance(color, QColor):
            return color
        if isinstance(color, str):
            return QColor(color)
        return None


def _contiguous_ranges(rows: list[int]) -> list[tuple[int, int]]:
    if not rows:
        return []
    ordered = sorted(set(rows))
    ranges = []
    start = previous = ordered[0]
    for row in ordered[1:]:
        if row == previous + 1:
            previous = row
            continue
        ranges.append((start, previous))
        start = previous = row
    ranges.append((start, previous))
    return ranges
