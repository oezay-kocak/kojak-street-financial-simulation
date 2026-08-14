"""Application status bar."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel


class StatusBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("StatusBar")
        self.message = QLabel("Ready")
        self.message.setObjectName("Muted")
        self.context = QLabel("")
        self.context.setObjectName("Muted")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.addWidget(self.message)
        layout.addStretch(1)
        layout.addWidget(self.context)

    def set_status(self, message: str, context: str = "") -> None:
        self.message.setText(message)
        self.context.setText(context)
