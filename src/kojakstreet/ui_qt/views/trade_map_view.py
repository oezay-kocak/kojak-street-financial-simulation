"""Fictional world trade map view."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from kojakstreet.core.countries import COUNTRIES
from kojakstreet.core.state import GameState
from kojakstreet.ui_qt.display import display_text
from kojakstreet.ui_qt.formatters import compact_money
from kojakstreet.ui_qt.widgets.view_header import ViewHeader

CountryTradeProvider = Callable[[], list[dict[str, object]]]


def _oval_position(degrees: float) -> tuple[float, float]:
    angle = math.radians(degrees)
    return (0.5 + 0.45 * math.cos(angle), 0.5 + 0.45 * math.sin(angle))


COUNTRY_ORBIT_ORDER = (
    "Nordmark",
    "Albionia",
    "Ardonia",
    "Valoria",
    "Romara",
    "Soleria",
    "Azaria",
    "Indara",
    "Hanxia",
    "Pacifica",
    "Koryo",
    "Auroria",
    "Sarmatia",
    "Danubria",
    "Carpathia",
    "Anatria",
    "Savanna",
    "Amazonia",
    "Ameron",
    "Canadia",
)

COUNTRY_POSITIONS = {
    country: _oval_position(-96 + index * (360 / len(COUNTRY_ORBIT_ORDER)))
    for index, country in enumerate(COUNTRY_ORBIT_ORDER)
}


class TradeMapView(QFrame):
    """Terminal-styled fictional map of global country trade routes."""

    def __init__(self, state: GameState, current_provider: CountryTradeProvider | None = None) -> None:
        super().__init__()
        self.state = state
        self.current_provider = current_provider
        self.setObjectName("Panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(
            ViewHeader(
                "Trade Map",
                "Fictional world routes, partner intensity and country balances",
                ["Export"],
            )
        )
        layout.addLayout(self._build_toolbar())
        self.canvas = TradeMapCanvas()
        layout.addWidget(self.canvas, 1)
        self.refresh(state)

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        caption = QLabel("Flow")
        caption.setObjectName("Muted")
        self.product_filter = QComboBox()
        self.product_filter.setObjectName("TradeMapProductFilter")
        self.product_filter.setMinimumWidth(420)
        self.product_filter.view().setMinimumWidth(520)
        self.product_filter.currentIndexChanged.connect(lambda _index: self._draw_map())
        toolbar.addWidget(caption)
        toolbar.addWidget(self.product_filter)
        toolbar.addStretch(1)
        return toolbar

    def refresh(self, state: GameState) -> None:
        self.state = state
        current_code = self.product_filter.currentData()
        options = self._product_options()
        existing = [self.product_filter.itemData(index) for index in range(self.product_filter.count())]
        if existing != [code for code, _label in options]:
            self.product_filter.blockSignals(True)
            self.product_filter.clear()
            for code, label in options:
                self.product_filter.addItem(label, code)
            if current_code in existing:
                self.product_filter.setCurrentIndex(max(0, [code for code, _label in options].index(current_code)))
            self.product_filter.blockSignals(False)
        self._draw_map()

    def _draw_map(self) -> None:
        code = self.product_filter.currentData()
        flows = self._flows(str(code)) if code and code != "ALL" else self._partner_flows()
        self.canvas.set_data(
            countries=self._countries(),
            flows=flows,
            selected_label=self.product_filter.currentText(),
        )

    def _countries(self) -> list[dict[str, object]]:
        countries = []
        for definition in COUNTRIES:
            macro = self.state.macro.get(definition.name, {})
            exports = sum(_safe_float(value) for value in dict(macro.get("exports", {})).values())
            imports = sum(_safe_float(value) for value in dict(macro.get("imports", {})).values())
            countries.append(
                {
                    "name": definition.name,
                    "balance": exports - imports,
                    "volume": exports + imports,
                    "position": COUNTRY_POSITIONS.get(definition.name, (0.5, 0.5)),
                }
            )
        return countries

    def _product_options(self) -> list[tuple[str, str]]:
        codes = set()
        names = self._product_names()
        for macro in self.state.macro.values():
            codes.update(str(code) for code in dict(macro.get("exports", {})))
            codes.update(str(code) for code in dict(macro.get("imports", {})))
        options = [("ALL", "All Trade")]
        options.extend((code, f"{code} {names.get(code, code)}") for code in sorted(codes))
        return options

    def _product_names(self) -> dict[str, str]:
        names = {}
        for universe in (self.state.commodities, self.state.processed_products):
            for code, item in universe.items():
                names[str(code)] = display_text(str(item.get("name", code)))
        return names

    def _partner_flows(self) -> list[dict[str, object]]:
        pair_totals: dict[tuple[str, str], float] = defaultdict(float)
        for country, macro in self.state.macro.items():
            for partner, value in dict(macro.get("trade_partners", {})).items():
                if partner == country:
                    continue
                pair = tuple(sorted((str(country), str(partner))))
                pair_totals[pair] += _safe_float(value)
        return [
            {"source": source, "target": target, "value": value / 2.0, "direction": "total"}
            for (source, target), value in sorted(pair_totals.items(), key=lambda item: item[1], reverse=True)[:32]
            if value > 0.0
        ]

    def _flows(self, code: str) -> list[dict[str, object]]:
        flows = []
        for exporter, macro in self.state.macro.items():
            if _safe_float(dict(macro.get("exports", {})).get(code, 0.0)) <= 0.0:
                continue
            partners = dict(macro.get("trade_partner_details", {})).get(code, {})
            for importer, value in dict(partners).items():
                amount = _safe_float(value)
                if amount > 0.0 and importer != exporter:
                    flows.append({"source": exporter, "target": str(importer), "value": amount, "direction": "export"})
        flows.sort(key=lambda item: float(item["value"]), reverse=True)
        return flows[:32]


class TradeMapCanvas(QFrame):
    """Paint a stylized fictional world and trade flows."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TradeMapCanvas")
        self.setMinimumHeight(400)
        self.countries: list[dict[str, object]] = []
        self.flows: list[dict[str, object]] = []
        self.selected_label = "All Trade"

    def set_data(self, *, countries: list[dict[str, object]], flows: list[dict[str, object]], selected_label: str) -> None:
        self.countries = countries
        self.flows = flows
        self.selected_label = selected_label
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = self.rect().adjusted(18, 18, -18, -18)
        painter.fillRect(self.rect(), QColor("#0b1017"))
        self._draw_grid(painter, bounds)
        self._draw_orbit(painter, bounds)
        positions = {str(country["name"]): self._point(bounds, country["position"]) for country in self.countries}
        self._draw_hub(painter, bounds)
        self._draw_flows(painter, positions)
        self._draw_countries(painter, positions)

    def _draw_grid(self, painter: QPainter, bounds: QRectF) -> None:
        painter.setPen(QPen(QColor(35, 50, 70, 80), 1))
        for index in range(1, 12):
            x = bounds.left() + bounds.width() * index / 12
            painter.drawLine(QPointF(x, bounds.top()), QPointF(x, bounds.bottom()))
        for index in range(1, 7):
            y = bounds.top() + bounds.height() * index / 7
            painter.drawLine(QPointF(bounds.left(), y), QPointF(bounds.right(), y))

    def _draw_orbit(self, painter: QPainter, bounds: QRectF) -> None:
        orbit = bounds.adjusted(bounds.width() * 0.05, bounds.height() * 0.05, -bounds.width() * 0.05, -bounds.height() * 0.05)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(38, 58, 78, 190), 1.4))
        painter.drawEllipse(orbit)

    def _draw_hub(self, painter: QPainter, bounds: QRectF) -> None:
        center = QPointF(bounds.center().x(), bounds.center().y())
        painter.setPen(QPen(QColor("#22d3ee"), 1.2))
        painter.setBrush(QColor(10, 18, 27, 230))
        painter.drawEllipse(center, 42, 42)
        painter.setPen(QColor("#e5eef8"))
        painter.drawText(QRectF(center.x() - 70, center.y() - 9, 140, 18), Qt.AlignmentFlag.AlignCenter, "Global Market")

    def _draw_flows(self, painter: QPainter, positions: dict[str, QPointF]) -> None:
        if not self.flows:
            painter.setPen(QColor("#8fb6d8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No trade flows available yet")
            return
        max_value = max(float(flow["value"]) for flow in self.flows) or 1.0
        for index, flow in enumerate(reversed(self.flows)):
            source = positions.get(str(flow["source"]))
            target = positions.get(str(flow["target"]))
            if source is None or target is None:
                continue
            intensity = max(0.18, min(1.0, float(flow["value"]) / max_value))
            color = QColor("#22d3ee") if flow.get("direction") == "total" else QColor("#14b8a6")
            color.setAlphaF(0.26 + intensity * 0.58)
            pen = QPen(color, 1.4 + intensity * 4.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            path, label_point = self._route_path(source, target, index)
            painter.drawPath(path)
            self._draw_arrow(painter, source, target, color, 7.0 + intensity * 6.0)
            self._draw_flow_label(painter, label_point, float(flow["value"]))

    def _draw_countries(self, painter: QPainter, positions: dict[str, QPointF]) -> None:
        max_volume = max((_safe_float(country.get("volume", 0.0)) for country in self.countries), default=1.0) or 1.0
        for country in self.countries:
            name = str(country["name"])
            point = positions[name]
            balance = _safe_float(country.get("balance", 0.0))
            volume = _safe_float(country.get("volume", 0.0))
            radius = 7.0 + 16.0 * math.sqrt(max(0.0, volume) / max_volume)
            fill = QColor("#14b8a6") if balance >= 0 else QColor("#f43f5e")
            fill.setAlphaF(0.82)
            painter.setPen(QPen(QColor("#d7f7ff"), 1.2))
            painter.setBrush(fill)
            painter.drawEllipse(point, radius, radius)
            painter.setPen(QColor("#b9d9f4"))
            painter.drawText(QRectF(point.x() - 58, point.y() + radius + 4, 116, 18), Qt.AlignmentFlag.AlignCenter, name)

    def _route_path(self, source: QPointF, target: QPointF, index: int) -> tuple[QPainterPath, QPointF]:
        midpoint = QPointF((source.x() + target.x()) / 2.0, (source.y() + target.y()) / 2.0)
        dx = target.x() - source.x()
        dy = target.y() - source.y()
        distance = max(1.0, math.hypot(dx, dy))
        curve = ((index % 5) - 2) * 16.0
        control = QPointF(midpoint.x() - dy / distance * curve, midpoint.y() + dx / distance * curve)
        path = QPainterPath(source)
        path.quadTo(control, target)
        label_point = QPointF(
            0.25 * source.x() + 0.5 * control.x() + 0.25 * target.x(),
            0.25 * source.y() + 0.5 * control.y() + 0.25 * target.y(),
        )
        return path, label_point

    def _draw_flow_label(self, painter: QPainter, point: QPointF, value: float) -> None:
        text = compact_money(value)
        rect = QRectF(point.x() - 24, point.y() - 10, 48, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(8, 14, 22, 210))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(QColor("#d7f7ff"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_arrow(self, painter: QPainter, source: QPointF, target: QPointF, color: QColor, size: float) -> None:
        angle = math.atan2(target.y() - source.y(), target.x() - source.x())
        tip = QPointF(target.x(), target.y())
        left = QPointF(tip.x() - math.cos(angle - 0.46) * size, tip.y() - math.sin(angle - 0.46) * size)
        right = QPointF(tip.x() - math.cos(angle + 0.46) * size, tip.y() - math.sin(angle + 0.46) * size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([tip, left, right]))

    def _point(self, bounds: QRectF, normalized: object) -> QPointF:
        x, y = normalized if isinstance(normalized, tuple) else (0.5, 0.5)
        return QPointF(bounds.left() + bounds.width() * float(x), bounds.top() + bounds.height() * float(y))


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
