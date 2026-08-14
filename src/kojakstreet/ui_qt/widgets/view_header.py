"""Reusable view header with contextual action buttons."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class ViewHeader(QFrame):
    def __init__(self, title: str, subtitle: str, actions: list[str] | None = None) -> None:
        super().__init__()
        self.setObjectName("ViewHeader")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        text_box = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("Muted")
        text_box.addWidget(title_label)
        text_box.addWidget(subtitle_label)
        layout.addLayout(text_box, 1)

        for action in actions or []:
            button = QPushButton(action)
            button.setObjectName("ActionButton")
            button.setEnabled(False)
            layout.addWidget(button)

