"""Fast PyQtGraph helpers used by interactive workspace charts."""

from __future__ import annotations

import math
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget

from kojakstreet.ui_qt.chart_series import build_candles


class FastChartView(QWidget):
    """Styled PyQtGraph wrapper for fast line and candle charts."""

    def __init__(self, *, title: str = "", legend: bool = False) -> None:
        super().__init__()
        self.last_candle_count = 0
        self.last_candle_interval = "Daily"
        self.legend_labels: list[str] = []
        self._legend_enabled = legend
        self._title = title

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget(background="#0d1118")
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.showGrid(x=True, y=True, alpha=0.22)
        self.plot.getPlotItem().hideButtons()
        self.plot.getAxis("left").setPen(pg.mkPen("#263347"))
        self.plot.getAxis("bottom").setPen(pg.mkPen("#263347"))
        self.plot.getAxis("left").setTextPen(pg.mkPen("#8ea3b8"))
        self.plot.getAxis("bottom").setTextPen(pg.mkPen("#8ea3b8"))
        if title:
            self.plot.setTitle(title, color="#e5eef8", size="10pt")
        self.legend = self.plot.addLegend(offset=(8, 8)) if legend else None
        layout.addWidget(self.plot)

    def plot_line(self, values: list[float], *, color: str = "#14b8a6", title: str = "", label: str = "Value") -> None:
        self.plot_lines([(label, values, color)], title=title, legend=False)

    def plot_lines(self, series_specs: list[tuple[str, list[float], str] | tuple[str, list[float], str, str]], *, title: str = "", legend: bool = False) -> None:
        self._clear(title or self._title or "Chart")
        self.legend_labels = [str(spec[0]) for spec in series_specs if len(spec[1]) >= 2] if legend else []
        if legend and self.legend is None:
            self.legend = self.plot.addLegend(offset=(8, 8))
        elif not legend and self.legend is not None:
            self.plot.removeItem(self.legend)
            self.legend = None

        all_values: list[float] = []
        for spec in series_specs:
            label, values, color = str(spec[0]), spec[1], str(spec[2])
            if len(values) < 2:
                continue
            role = str(spec[3]) if len(spec) >= 4 else self._series_role(label)
            pen = self._series_pen(color, role)
            if role == "primary":
                glow = self.plot.plot(
                    list(range(len(values))),
                    values,
                    pen=pg.mkPen(_alpha_color(color, 48), width=8, cosmetic=True),
                )
                glow.setDownsampling(auto=True, method="peak")
                glow.setClipToView(True)
            item = self.plot.plot(list(range(len(values))), values, pen=pen, name=label if legend else None)
            item.setDownsampling(auto=True, method="peak")
            item.setClipToView(True)
            all_values.extend(values)
        if not all_values:
            self.show_message("History builds as the simulation runs")
            return
        self._fit_range(all_values)

    def _series_role(self, label: str) -> str:
        upper_label = label.upper()
        if upper_label.startswith("EMA"):
            return "average"
        if upper_label in {"PRICE", "VALUE", "YIELD"}:
            return "primary"
        return "secondary"

    def _series_pen(self, color: str, role: str) -> Any:
        if role == "primary":
            return pg.mkPen(_alpha_color(color, 255), width=3.4, cosmetic=True)
        if role == "average":
            return pg.mkPen(_alpha_color(color, 165), width=1.35, style=Qt.PenStyle.DashLine, cosmetic=True)
        return pg.mkPen(_alpha_color(color, 210), width=2.0, cosmetic=True)

    def plot_candles(self, values: list[Any], *, range_points: int, title: str = "Price History") -> None:
        self._clear(title)
        candles, interval = build_candles(values, range_points)
        self.last_candle_count = len(candles)
        self.last_candle_interval = interval
        if not candles:
            self.show_message("History builds as the simulation runs")
            return
        item = CandlestickItem(
            [
                (index, candle.open, candle.close, candle.low, candle.high)
                for index, candle in enumerate(candles)
            ]
        )
        self.plot.addItem(item)
        all_values = [value for candle in candles for value in (candle.low, candle.high)]
        self.plot.setXRange(-1, max(1, len(candles)), padding=0.02)
        self._fit_range(all_values)

    def plot_horizontal_bars(
        self,
        values: list[tuple[str, float]],
        *,
        title: str = "",
        color: str = "#14b8a6",
    ) -> None:
        self._clear(title or self._title or "Chart")
        self.legend_labels = []
        chart_values = [(label, max(0.0, float(value))) for label, value in values]
        if not chart_values or not any(value > 0.0 for _label, value in chart_values):
            self.show_message("No country production data yet")
            return
        ordered = sorted(chart_values, key=lambda item: item[1], reverse=True)
        count = len(ordered)
        positions = list(range(count))
        widths = [value for _label, value in ordered]
        item = pg.BarGraphItem(
            x0=[0.0 for _ in ordered],
            x1=widths,
            y=positions,
            height=0.62,
            brush=pg.mkBrush(_alpha_color(color, 210)),
            pen=pg.mkPen(_alpha_color(color, 245), width=1),
        )
        self.plot.addItem(item)
        max_width = max(widths) or 1.0
        for index, (_label, value) in enumerate(ordered):
            text = pg.TextItem(f"{value:.1f}%", color="#c9d7e6", anchor=(0, 0.5))
            text.setPos(min(value + max_width * 0.015, max_width * 1.03), index)
            self.plot.addItem(text)
        self.plot.getAxis("left").setTicks([[(index, label) for index, (label, _value) in enumerate(ordered)]])
        self.plot.getAxis("bottom").setLabel("% of global production", color="#8ea3b8")
        self.plot.setXRange(0.0, max_width * 1.18, padding=0.0)
        self.plot.setYRange(-0.7, count - 0.3, padding=0.0)
        self.plot.invertY(True)

    def plot_long_short_heatmap(
        self,
        long_value: float,
        short_value: float,
        *,
        title: str = "Long / Short Interest",
    ) -> None:
        self._clear(title)
        self.legend_labels = []
        long_value = max(0.0, float(long_value))
        short_value = max(0.0, float(short_value))
        if long_value <= 0.0 and short_value <= 0.0:
            self.show_message("No positioning data yet")
            return
        values = [("Long", long_value, "#14b8a6"), ("Short", short_value, "#f43f5e")]
        max_width = max(long_value, short_value, 1.0)
        for index, (label, value, color) in enumerate(values):
            bar = pg.BarGraphItem(
                x0=[0.0],
                x1=[value],
                y=[index],
                height=0.58,
                brush=pg.mkBrush(_alpha_color(color, 210)),
                pen=pg.mkPen(_alpha_color(color, 245), width=1),
            )
            self.plot.addItem(bar)
            share = value / max(1.0, long_value + short_value) * 100.0
            text = pg.TextItem(f"{share:.1f}%", color="#c9d7e6", anchor=(0, 0.5))
            text.setPos(min(value + max_width * 0.03, max_width * 1.04), index)
            self.plot.addItem(text)
        self.plot.getAxis("left").setTicks([[(0, "Long"), (1, "Short")]])
        self.plot.getAxis("bottom").setLabel("Open interest", color="#8ea3b8")
        self.plot.getAxis("bottom").setTicks([_compact_value_ticks(max_width)])
        self.plot.setXRange(0.0, max_width * 1.20, padding=0.0)
        self.plot.setYRange(-0.6, 1.6, padding=0.0)
        self.plot.invertY(True)

    def show_message(self, message: str) -> None:
        self._clear(message)
        self.plot.setTitle(message, color="#8ea3b8", size="10pt")

    def _clear(self, title: str) -> None:
        self.plot.clear()
        if self.legend is not None:
            self.legend.clear()
        self.plot.setTitle(title, color="#e5eef8", size="10pt")
        self._reset_axes()
        self.last_candle_count = 0

    def _reset_axes(self) -> None:
        left_axis = self.plot.getAxis("left")
        bottom_axis = self.plot.getAxis("bottom")
        left_axis.setLabel("", color="#8ea3b8")
        bottom_axis.setLabel("", color="#8ea3b8")
        left_axis.setTicks(None)
        bottom_axis.setTicks(None)
        self.plot.invertY(False)
        self.plot.enableAutoRange(x=True, y=True)

    def _fit_range(self, values: list[float]) -> None:
        if not values:
            return
        lower = min(values)
        upper = max(values)
        padding = max((upper - lower) * 0.08, abs(upper) * 0.002, 0.01)
        self.plot.setYRange(lower - padding, upper + padding, padding=0.0)


def _alpha_color(color: str, alpha: int) -> QColor:
    qcolor = QColor(color)
    qcolor.setAlpha(max(0, min(255, alpha)))
    return qcolor


def _compact_value_ticks(max_value: float) -> list[tuple[float, str]]:
    max_value = max(1.0, float(max_value))
    step = _nice_tick_step(max_value / 4.0)
    ticks = []
    value = step
    while value <= max_value * 1.05:
        ticks.append((value, _compact_value_label(value)))
        value += step
    return ticks


def _nice_tick_step(raw_step: float) -> float:
    if raw_step <= 0:
        return 1.0
    magnitude = 10 ** int(math.floor(math.log10(raw_step)))
    normalized = raw_step / magnitude
    if normalized <= 1:
        nice = 1
    elif normalized <= 2:
        nice = 2
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10
    return nice * magnitude


def _compact_value_label(value: float) -> str:
    abs_value = abs(float(value))
    for divisor, suffix in ((1_000_000_000_000, "T"), (1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs_value >= divisor:
            scaled = value / divisor
            return f"{scaled:g}{suffix}"
    return f"{value:g}"


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, data: list[tuple[int, float, float, float, float]]) -> None:
        super().__init__()
        self.data = data
        self.picture = None
        self.generate_picture()

    def generate_picture(self) -> None:
        picture = pg.QtGui.QPicture()
        painter = pg.QtGui.QPainter(picture)
        width = 0.56
        for index, open_price, close_price, low, high in self.data:
            color = QColor("#14b8a6" if close_price >= open_price else "#f43f5e")
            painter.setPen(pg.mkPen(color, width=1))
            painter.drawLine(pg.QtCore.QPointF(index, low), pg.QtCore.QPointF(index, high))
            body_low = min(open_price, close_price)
            body_high = max(open_price, close_price)
            if abs(body_high - body_low) < 1e-9:
                body_high = body_low + max(abs(close_price) * 0.0005, 0.01)
            painter.setBrush(pg.mkBrush(color))
            painter.drawRect(pg.QtCore.QRectF(index - width / 2, body_low, width, body_high - body_low))
        painter.end()
        self.picture = picture

    def paint(self, painter, _option, _widget=None) -> None:
        if self.picture is not None:
            self.picture.play(painter)

    def boundingRect(self):
        if not self.data:
            return pg.QtCore.QRectF()
        lows = [item[3] for item in self.data]
        highs = [item[4] for item in self.data]
        return pg.QtCore.QRectF(-1, min(lows), len(self.data) + 2, max(highs) - min(lows))
