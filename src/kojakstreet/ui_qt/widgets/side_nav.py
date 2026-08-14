"""Side navigation for the Kojak Street Pro shell."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout


class SideNav(QFrame):
    view_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SideNav")
        self.setFixedWidth(220)
        self.buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(2)

        for index, (key, text) in enumerate(
            [
                ("markets", "Markets"),
                ("forex", "Forex"),
                ("bondmarket", "Bondmarket"),
                ("portfolio", "Portfolio"),
                ("macro", "Macro"),
                ("supply_chain", "Supply Chain"),
                ("trade_map", "Trade Map"),
                ("global_macro", "Global Macro"),
                ("news", "News"),
            ]
        ):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setMinimumHeight(42)
            button.clicked.connect(lambda _checked=False, view_key=key: self.set_active_view(view_key))
            self.buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)

    def set_active_view(self, view_key: str) -> None:
        for key, button in self.buttons.items():
            button.setChecked(key == view_key)
        self.view_changed.emit(view_key)
