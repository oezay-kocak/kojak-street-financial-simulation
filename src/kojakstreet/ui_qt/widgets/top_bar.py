"""Top KPI bar for the Kojak Street Pro shell."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.formatters import gold_dinar, percent


class TopBar(QFrame):
    def __init__(self, state: GameState, asset_count: int) -> None:
        super().__init__()
        self.setObjectName("TopBar")
        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("RunButton")
        self.step_button = QPushButton("Save")
        self.step_button.setObjectName("ActionButton")
        self.load_button = QPushButton("Load")
        self.load_button.setObjectName("ActionButton")
        self.date_value = QLabel(state.date.strftime("%d.%m.%Y"))
        self.date_value.setObjectName("DetailValue")
        self.kpi_values: dict[str, QLabel] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(14)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(4)
        brand = QLabel("KOJAK STREET PRO")
        brand.setObjectName("BrandTitle")
        brand.setAlignment(Qt.AlignmentFlag.AlignLeft)
        subtitle = QLabel("GLOBAL MARKET SIMULATION")
        subtitle.setObjectName("Muted")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
        brand_box.addWidget(brand)
        brand_box.addWidget(subtitle)
        layout.addLayout(brand_box, 0)

        self.ticker_tape = TickerTape()
        self.ticker_tape.set_items(self._build_ticker_items(state))
        layout.addWidget(self.ticker_tape, 1)

        layout.addWidget(self._kpi("Cash", gold_dinar(state.cash)))
        layout.addWidget(self._controls())

    def _kpi(self, label: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("KpiCard")
        frame.setFixedWidth(132)
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(6)
        caption = QLabel(label.upper())
        caption.setObjectName("Muted")
        main = QLabel(value)
        main.setObjectName("KpiValue")
        self.kpi_values[label] = main
        box.addWidget(caption)
        box.addWidget(main)
        return frame

    def _controls(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("ControlCard")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        layout.addWidget(self.date_value)
        layout.addWidget(self.run_button)
        layout.addWidget(self.step_button)
        layout.addWidget(self.load_button)
        return frame

    def update_state(self, state: GameState, asset_count: int) -> None:
        self.kpi_values["Cash"].setText(gold_dinar(state.cash))
        self.date_value.setText(state.date.strftime("%d.%m.%Y"))
        items = self._build_ticker_items(state)
        if items:
            self.ticker_tape.set_items(items)

    def update_status(self, state: GameState) -> None:
        self.kpi_values["Cash"].setText(gold_dinar(state.cash))
        self.date_value.setText(state.date.strftime("%d.%m.%Y"))

    def update_ticker_quotes(self, items: list[dict[str, float | str]]) -> None:
        if items:
            self.ticker_tape.set_items(items)

    def _build_ticker_items(self, state: GameState) -> list[dict[str, float | str]]:
        items = []
        items.extend(self._top_assets(state.commodities, 2))
        items.extend(self._top_assets(state.cryptos, 2))
        items.extend(self._top_assets(state.stocks, 4))
        items.extend(self._top_assets(state.indices, len(state.indices)))
        return items

    def _top_assets(self, assets: dict[str, dict[str, Any]], limit: int) -> list[dict[str, float | str]]:
        ranked = sorted(
            assets.items(),
            key=lambda item: self._weekly_change(item[1]),
            reverse=True,
        )[:limit]
        return [
            {
                "ticker": ticker,
                "price": float(data.get("kurs", 0.0)),
                "change": self._weekly_change(data),
            }
            for ticker, data in ranked
        ]

    def _weekly_change(self, data: dict[str, Any]) -> float:
        history = data.get("historie", [])
        try:
            current = float(data.get("kurs", 0.0))
            if len(history) >= 7:
                previous = float(history[-7][0] if isinstance(history[-7], (tuple, list)) else history[-7])
                return ((current / previous) - 1.0) * 100.0 if previous else 0.0
            return float(data.get("aenderung", 0.0))
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0


class TickerTape(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TickerTape")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(260)
        self.setMinimumHeight(60)
        self.items: list[dict[str, float | str]] = []
        self.pending_items: list[dict[str, float | str]] | None = None
        self._item_signature: tuple[tuple[str, float, float], ...] = ()
        self._pending_signature: tuple[tuple[str, float, float], ...] = ()
        self.content_width = 1
        self.offset = 0
        self.repeat_gap = 80
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scroll)
        self.timer.start(66)

    def sizeHint(self) -> QSize:
        return QSize(640, 60)

    def minimumSizeHint(self) -> QSize:
        return QSize(260, 60)

    def set_items(self, items: list[dict[str, float | str]]) -> None:
        signature = self._signature(items)
        if signature == self._item_signature or signature == self._pending_signature:
            return
        if not self.items:
            self.items = items
            self._item_signature = signature
            self.content_width = self._calculate_content_width(items)
            self.update()
            return
        self.pending_items = items
        self._pending_signature = signature

    def apply_items_now(self, items: list[dict[str, float | str]]) -> None:
        self.items = items
        self.pending_items = None
        self._item_signature = self._signature(items)
        self._pending_signature = ()
        self.content_width = self._calculate_content_width(items)
        self.offset = 0
        self.update()

    def scroll(self) -> None:
        next_offset = self.offset + 2
        if next_offset >= self._tile_width():
            next_offset = 0
            if self.pending_items is not None:
                self.items = self.pending_items
                self.pending_items = None
                self._item_signature = self._pending_signature
                self._pending_signature = ()
                self.content_width = self._calculate_content_width(self.items)
        self.offset = next_offset
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setClipRect(self.rect().adjusted(1, 1, -1, -1))
        font = self._ticker_font()
        painter.setFont(font)

        y = int(self.height() / 2 + painter.fontMetrics().ascent() / 2 - 2)
        tile_width = self._tile_width()
        start_x = -tile_width + self.offset
        while start_x < self.width():
            self._draw_items(painter, start_x, y)
            start_x += tile_width

    def _draw_items(self, painter: QPainter, start_x: int, y: int) -> None:
        metrics = painter.fontMetrics()
        x = start_x
        for item in self.items:
            ticker = str(item["ticker"])
            price = float(item["price"])
            change = float(item["change"])
            prefix = f"{ticker} {price:,.2f} "
            change_text = f"7D {percent(change)}"
            painter.setPen(QColor("#e5eef8"))
            painter.drawText(x, y, prefix)
            x += metrics.horizontalAdvance(prefix)
            painter.setPen(QColor("#14b8a6" if change >= 0 else "#f43f5e"))
            painter.drawText(x, y, change_text)
            x += metrics.horizontalAdvance(change_text)
            separator = "     |     "
            painter.setPen(QColor("#8ea3b8"))
            painter.drawText(x, y, separator)
            x += metrics.horizontalAdvance(separator)

    def _tile_width(self) -> int:
        return self._content_width() + self.repeat_gap

    def _content_width(self) -> int:
        return self.content_width

    def _calculate_content_width(self, items: list[dict[str, float | str]]) -> int:
        metrics = QFontMetrics(self._ticker_font())
        width = 0
        for item in items:
            text = f"{item['ticker']} {float(item['price']):,.2f} 7D {percent(float(item['change']))}     |     "
            width += metrics.horizontalAdvance(text)
        return max(width, 1)

    def _signature(self, items: list[dict[str, float | str]]) -> tuple[tuple[str, float, float], ...]:
        return tuple(
            (
                str(item["ticker"]),
                round(float(item["price"]), 4),
                round(float(item["change"]), 4),
            )
            for item in items
        )

    def _ticker_font(self) -> QFont:
        font = QFont("Cascadia Mono", 10)
        font.setBold(True)
        return font
