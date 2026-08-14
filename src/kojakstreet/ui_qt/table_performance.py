"""Shared performance defaults for large Qt tables."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView


def optimize_table_view(table: QTableView, *, row_height: int = 34) -> None:
    """Apply cheap painting and scrolling defaults for data-heavy tables."""
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setShowGrid(False)
    table.setAlternatingRowColors(False)
    table.setMouseTracking(False)
    table.setAutoScroll(False)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    vertical = table.verticalHeader()
    vertical.setVisible(False)
    vertical.setDefaultSectionSize(row_height)
    vertical.setMinimumSectionSize(max(22, row_height - 10))
    vertical.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

    horizontal = table.horizontalHeader()
    horizontal.setHighlightSections(False)
    horizontal.setSectionsMovable(False)
    horizontal.setMinimumSectionSize(48)
