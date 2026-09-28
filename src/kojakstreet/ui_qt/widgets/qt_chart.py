"""Fast PyQtGraph helpers used by interactive workspace charts."""

from __future__ import annotations

import math
from bisect import bisect_left
from datetime import date
from itertools import pairwise
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QGradient, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from kojakstreet.ui_qt.chart_series import build_candles, history_date, history_ordinal


class SimulationDateAxis(pg.AxisItem):
    """Format ordinal simulation dates without assuming evenly spaced samples."""

    def __init__(self) -> None:
        super().__init__(orientation="bottom")
        self.date_mode = False

    def tickStrings(self, values, scale, spacing):
        if not self.date_mode:
            return super().tickStrings(values, scale, spacing)
        labels = []
        for value in values:
            try:
                day = date.fromordinal(round(value))
                labels.append(day.strftime("%Y") if spacing >= 300 else day.strftime("%b %Y") if spacing >= 25 else day.strftime("%d %b"))
            except (OverflowError, ValueError):
                labels.append("")
        return labels


class CompactValueAxis(pg.AxisItem):
    """Financial value axis that avoids scientific notation for normal prices."""

    def tickStrings(self, values, scale, spacing):
        return [_compact_value_label(float(value) * float(scale)) for value in values]


class LegendSwatch(QWidget):
    """Line-only legend sample, independent from plot fill brushes."""

    def __init__(self, color: str, *, dashed: bool = False) -> None:
        super().__init__()
        self.color = color
        self.dashed = dashed
        self.setFixedSize(24, 12)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        pen = pg.mkPen(
            self.color,
            width=2,
            style=Qt.PenStyle.DashLine if self.dashed else Qt.PenStyle.SolidLine,
            cosmetic=True,
        )
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(pen)
        painter.drawLine(1, self.height() // 2, self.width() - 1, self.height() // 2)


class FastChartView(QWidget):
    """Styled PyQtGraph wrapper for fast line and candle charts."""

    def __init__(self, *, title: str = "", legend: bool = False) -> None:
        super().__init__()
        self.last_candle_count = 0
        self.last_candle_interval = "Daily"
        self.last_x_values: list[float] = []
        self.legend_labels: list[str] = []
        self._legend_enabled = legend
        self._title = title
        self._current_title = title
        self._hover_points: list[tuple[float, float, str, str]] = []
        self._hover_label: Any = None
        self._hover_line: Any = None
        self._hover_horizontal: Any = None
        self._chart_kind = ""
        self._series_items: list[Any] = []
        self._primary_glow: Any = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.legend_bar = QWidget()
        self.legend_layout = QHBoxLayout(self.legend_bar)
        self.legend_layout.setContentsMargins(12, 2, 12, 0)
        self.legend_layout.setSpacing(6)
        self.legend_bar.setVisible(False)
        layout.addWidget(self.legend_bar, 0)
        self.date_axis = SimulationDateAxis()
        self.value_axis = CompactValueAxis(orientation="right")
        self.plot = pg.PlotWidget(
            background="#0b1017",
            axisItems={"bottom": self.date_axis, "right": self.value_axis},
        )
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.showGrid(x=True, y=True, alpha=0.14)
        self.plot.getPlotItem().hideButtons()
        self.plot.showAxis("right")
        self.plot.hideAxis("left")
        self.plot.scene().sigMouseMoved.connect(self._mouse_moved)
        self.plot.getAxis("right").setPen(pg.mkPen("#263347"))
        self.plot.getAxis("bottom").setPen(pg.mkPen("#263347"))
        self.plot.getAxis("right").setTextPen(pg.mkPen("#8ea3b8"))
        self.plot.getAxis("bottom").setTextPen(pg.mkPen("#8ea3b8"))
        self.plot.getAxis("bottom").setHeight(32)
        if title:
            self.plot.setTitle(title, color="#e5eef8", size="10pt")
        self.legend = None
        layout.addWidget(self.plot)

    def plot_line(self, values: list[float], *, dates: list[Any] | None = None, color: str = "#14b8a6", title: str = "", label: str = "Value") -> None:
        if self._chart_kind == "line" and len(self._series_items) == 1 and len(values) >= 2:
            x_values = self._x_values(dates, len(values))
            lower = min(values)
            self._series_items[0].setData(
                x_values,
                values,
                pen=self._series_pen(color, "primary"),
                fillLevel=lower,
                brush=self._area_brush(color),
            )
            if self._primary_glow is not None:
                self._primary_glow.setData(x_values, values, pen=pg.mkPen(_alpha_color(color, 42), width=8, cosmetic=True))
            self._current_title = title or self._title or "Chart"
            self.plot.setTitle(self._current_title, color="#e5eef8", size="10pt")
            self._fit_range(values)
            self._set_hover_points(x_values, values, dates or [])
            self._set_legend([(label, color, False)])
            return
        self.plot_lines([(label, values, color)], title=title, legend=True, dates=dates)

    def plot_lines(self, series_specs: list[tuple[str, list[float], str] | tuple[str, list[float], str, str]], *, title: str = "", legend: bool = False, dates: list[Any] | None = None) -> None:
        self._clear(title or self._title or "Chart")
        self._chart_kind = "line"
        self.legend_labels = [str(spec[0]) for spec in series_specs if len(spec[1]) >= 2] if legend else []
        if legend:
            self._set_legend(
                [
                    (str(spec[0]), str(spec[2]), self._series_role(str(spec[0])) == "average")
                    for spec in series_specs
                    if len(spec[1]) >= 2
                ]
            )

        all_values: list[float] = []
        x_values = self._x_values(dates, max((len(spec[1]) for spec in series_specs), default=0))
        for spec in series_specs:
            label, values, color = str(spec[0]), spec[1], str(spec[2])
            if len(values) < 2:
                continue
            role = str(spec[3]) if len(spec) >= 4 else self._series_role(label)
            pen = self._series_pen(color, role)
            if role == "primary":
                self._primary_glow = self.plot.plot(
                    x_values[-len(values):],
                    values,
                    pen=pg.mkPen(_alpha_color(color, 48), width=8, cosmetic=True),
                )
                self._primary_glow.setDownsampling(auto=True, method="peak")
                self._primary_glow.setClipToView(True)
            item = self.plot.plot(
                x_values[-len(values):],
                values,
                pen=pen,
                fillLevel=min(values) if role == "primary" else None,
                brush=self._area_brush(color) if role == "primary" else None,
            )
            item.setDownsampling(auto=True, method="peak")
            item.setClipToView(True)
            self._series_items.append(item)
            all_values.extend(values)
        if not all_values:
            self.show_message("History builds as the simulation runs")
            return
        self._fit_range(all_values)
        if dates and series_specs:
            primary_values = series_specs[0][1]
            self._set_hover_points(x_values[-len(primary_values):], primary_values, dates[-len(primary_values):])

    def _x_values(self, dates: list[Any] | None, count: int) -> list[float]:
        ordinals = [history_ordinal(item) for item in (dates or [])]
        if count and len(ordinals) == count and all(value is not None for value in ordinals):
            values = [float(value) for value in ordinals if value is not None]
            if len(set(values)) > 1 and all(right > left for left, right in pairwise(values)):
                self.date_axis.date_mode = True
                self.last_x_values = values
                return values
        self.date_axis.date_mode = False
        self.last_x_values = [float(index) for index in range(count)]
        return self.last_x_values

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

    def _area_brush(self, color: str) -> QBrush:
        gradient = QLinearGradient(0.0, 0.0, 0.0, 1.0)
        gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
        gradient.setColorAt(0.0, _alpha_color(color, 72))
        gradient.setColorAt(0.55, _alpha_color(color, 24))
        gradient.setColorAt(1.0, _alpha_color(color, 0))
        return QBrush(gradient)

    def plot_candles(
        self,
        values: list[Any],
        *,
        range_points: int,
        title: str = "Price History",
        overlays: list[tuple[str, list[float], str]] | None = None,
    ) -> None:
        self._clear(title)
        self._chart_kind = "candle"
        candles, interval = build_candles(values, range_points)
        self.last_candle_count = len(candles)
        self.last_candle_interval = interval
        if not candles:
            self.show_message("History builds as the simulation runs")
            return
        x_values = self._x_values([candle.date for candle in candles], len(candles))
        item = CandlestickItem([(x_values[index], candle.open, candle.close, candle.low, candle.high) for index, candle in enumerate(candles)])
        self.plot.addItem(item)
        self.legend_labels = []
        self._set_legend(
            [("Price", "#14b8a6", False)]
            + [(label, color, True) for label, _overlay_values, color in (overlays or [])]
        )
        if overlays:
            for label, overlay_values, color in overlays:
                if len(overlay_values) < 2:
                    continue
                overlay = self.plot.plot(
                    x_values[-len(overlay_values) :],
                    overlay_values,
                    pen=self._series_pen(color, "average"),
                )
                overlay.setDownsampling(auto=True, method="peak")
                overlay.setClipToView(True)
                self.legend_labels.append(label)
        all_values = [value for candle in candles for value in (candle.low, candle.high)]
        self.plot.setXRange(min(x_values), max(x_values) if len(x_values) > 1 else x_values[0] + 1, padding=0.02)
        self._fit_range(all_values)
        details = [
            f"O {_compact_value_label(candle.open)}  H {_compact_value_label(candle.high)}  "
            f"L {_compact_value_label(candle.low)}  C {_compact_value_label(candle.close)}"
            for candle in candles
        ]
        self._set_hover_points(
            x_values,
            [candle.close for candle in candles],
            [candle.date for candle in candles],
            details=details,
        )

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
        self.plot.hideAxis("right")
        self.plot.showAxis("left")

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
        self.plot.hideAxis("right")
        self.plot.showAxis("left")

    def show_message(self, message: str) -> None:
        self._clear(message)
        self.plot.getAxis("right").setTicks([[]])
        self.plot.getAxis("bottom").setTicks([[]])
        self.plot.setXRange(0.0, 1.0, padding=0.0)
        self.plot.setYRange(0.0, 1.0, padding=0.0)
        self.plot.setTitle(message, color="#8ea3b8", size="10pt")

    def set_loading(self, loading: bool, *, has_data: bool) -> None:
        if loading and not has_data:
            self.show_message("Loading price history…")
            return
        suffix = "  ·  Refreshing…" if loading else ""
        self.plot.setTitle(f"{self._current_title}{suffix}", color="#e5eef8", size="10pt")

    def _clear(self, title: str) -> None:
        self.plot.clear()
        self._current_title = title
        self._chart_kind = ""
        self._series_items = []
        self._primary_glow = None
        self._hover_points = []
        self._hover_label = None
        self._hover_line = None
        self._hover_horizontal = None
        self._set_legend([])
        self.plot.setTitle(title, color="#e5eef8", size="10pt")
        self._reset_axes()
        self.last_candle_count = 0

    def _set_hover_points(
        self,
        x_values: list[float],
        values: list[float],
        dates: list[Any],
        *,
        details: list[str] | None = None,
    ) -> None:
        labels = [history_date(item) for item in dates]
        if not labels or not all(labels) or len(labels) != len(values):
            return
        detail_labels = details or [f"Price {_compact_value_label(value)}" for value in values]
        self._hover_points = list(
            zip(x_values, (float(value) for value in values), labels, detail_labels, strict=True)
        )
        if self._hover_line is None:
            self._hover_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#52667d", width=1))
            self._hover_horizontal = pg.InfiniteLine(
                angle=0,
                movable=False,
                pen=pg.mkPen(_alpha_color("#52667d", 115), width=1, style=Qt.PenStyle.DotLine),
            )
            self._hover_label = pg.TextItem(
                color="#e5eef8",
                fill=pg.mkBrush(13, 17, 24, 232),
                border=pg.mkPen("#2a3a4f"),
                anchor=(0, 1),
            )
            self.plot.addItem(self._hover_line, ignoreBounds=True)
            self.plot.addItem(self._hover_horizontal, ignoreBounds=True)
            self.plot.addItem(self._hover_label, ignoreBounds=True)
        self._hover_line.hide()
        self._hover_horizontal.hide()
        self._hover_label.hide()

    def _mouse_moved(self, scene_position: Any) -> None:
        if not self._hover_points or not self.plot.sceneBoundingRect().contains(scene_position):
            return
        position = self.plot.getPlotItem().vb.mapSceneToView(scene_position)
        x_values = [point[0] for point in self._hover_points]
        index = bisect_left(x_values, position.x())
        if index >= len(x_values):
            index = len(x_values) - 1
        elif index > 0 and abs(x_values[index - 1] - position.x()) <= abs(x_values[index] - position.x()):
            index -= 1
        x_value, value, label, details = self._hover_points[index]
        self._hover_line.setPos(x_value)
        self._hover_horizontal.setPos(value)
        self._hover_label.setText(f"{label}\n{details}")
        view_range = self.plot.getPlotItem().vb.viewRange()[0]
        self._hover_label.setAnchor((1, 1) if x_value > sum(view_range) / 2 else (0, 1))
        self._hover_label.setPos(x_value, value)
        self._hover_line.show()
        self._hover_horizontal.show()
        self._hover_label.show()

    def _reset_axes(self) -> None:
        value_axis = self.plot.getAxis("right")
        bottom_axis = self.plot.getAxis("bottom")
        value_axis.setLabel("", color="#8ea3b8")
        bottom_axis.setLabel("", color="#8ea3b8")
        value_axis.setTicks(None)
        bottom_axis.setTicks(None)
        self.date_axis.date_mode = False
        self.plot.showAxis("right")
        self.plot.hideAxis("left")
        self.plot.invertY(False)
        self.plot.enableAutoRange(x=True, y=True)

    def _fit_range(self, values: list[float]) -> None:
        if not values:
            return
        lower = min(values)
        upper = max(values)
        padding = max((upper - lower) * 0.08, abs(upper) * 0.002, 0.01)
        self.plot.setYRange(lower - padding, upper + padding, padding=0.0)

    def _set_legend(self, entries: list[tuple[str, str, bool]]) -> None:
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for label, color, dashed in entries:
            self.legend_layout.addWidget(LegendSwatch(color, dashed=dashed))
            text = QLabel(label)
            text.setObjectName("Muted")
            text.setStyleSheet("background: transparent;")
            self.legend_layout.addWidget(text)
            self.legend_layout.addSpacing(8)
        self.legend_layout.addStretch(1)
        self.legend_bar.setVisible(bool(entries))


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
    magnitude = 10 ** math.floor(math.log10(raw_step))
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
    def __init__(self, data: list[tuple[float, float, float, float, float]]) -> None:
        super().__init__()
        self.data = data
        self.picture = None
        self.generate_picture()

    def generate_picture(self) -> None:
        picture = pg.QtGui.QPicture()
        painter = pg.QtGui.QPainter(picture)
        gaps = [right[0] - left[0] for left, right in zip(self.data, self.data[1:]) if right[0] > left[0]]
        width = max(0.56, min(gaps) * 0.56) if gaps else 0.56
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
        x_values = [item[0] for item in self.data]
        return pg.QtCore.QRectF(min(x_values) - 1, min(lows), max(x_values) - min(x_values) + 2, max(highs) - min(lows))
