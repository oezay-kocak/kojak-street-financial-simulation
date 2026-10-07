"""Small Qt-native, identity-preserving chart for bounded compositions."""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QToolTip, QWidget

COLORS = ("#14b8a6", "#22d3ee", "#8b5cf6", "#f59e0b", "#f43f5e", "#60a5fa", "#a3e635")


class CompositionPie(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(180, 160)
        self.setMouseTracking(True)
        self.slices = []
        self.signature = ()
        self.geometry_updates = 0
        self.paint_count = 0
        self.setAccessibleName("Composition chart; values are also available in the adjacent table")

    def set_data(self, slices):
        # Entries: stable ID, label, fraction, color, tooltip. No animation/timer.
        values = list(slices)
        if values and (len(values) > 7 or any(not math.isfinite(v[2]) or v[2] <= 0 for v in values) or
                       not math.isclose(sum(v[2] for v in values), 1, rel_tol=0, abs_tol=1e-12)):
            values = []
        signature = tuple((v[0], v[2], v[3]) for v in values)
        self.slices = values
        if signature == self.signature:
            return
        self.signature = signature
        self.geometry_updates += 1
        self.update()

    def bounds(self):
        length = min(self.width(), self.height()) - 24
        return QRectF((self.width()-length)/2, (self.height()-length)/2, length, length)

    def paintEvent(self, _event):
        self.paint_count += 1
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        box = self.bounds()
        start = 90*16
        if not self.slices:
            painter.setBrush(QColor("#172033"))
            painter.drawEllipse(box)
        for _, _, share, color, _ in self.slices:
            span = round(share*360*16)
            painter.setBrush(QColor(color))
            painter.drawPie(box, start, -span)
            start -= span
        inset = box.width()*.27
        painter.setBrush(QColor("#0b1017"))
        painter.drawEllipse(box.adjusted(inset, inset, -inset, -inset))

    def mouseMoveEvent(self, event):
        box = self.bounds()
        dx, dy = event.position().x()-box.center().x(), event.position().y()-box.center().y()
        distance = math.hypot(dx, dy)
        if not box.width()*.23 <= distance <= box.width()/2:
            QToolTip.hideText()
            return
        fraction = ((math.degrees(math.atan2(dy, dx))+90) % 360)/360
        cursor = 0
        for _, _, share, _, tooltip in self.slices:
            cursor += share
            if fraction <= cursor:
                QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)
                return

    def leaveEvent(self, _event):
        QToolTip.hideText()
