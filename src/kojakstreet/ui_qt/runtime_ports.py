"""Small UI-facing runtime contracts."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtWidgets import QWidget

from kojakstreet.core.runtime_context import SimulationDelta
from kojakstreet.core.state import GameState


class RefreshableView(Protocol):
    def refresh(self, state: GameState, *, throttle_charts: bool = False) -> None:
        ...


class RuntimePort(Protocol):
    running: bool

    def set_running(self, running: bool) -> None:
        ...

    def snapshot_for_view(self, view_key: str) -> GameState:
        ...

    def advance_days(self, steps: int, view_key: str = "full") -> GameState:
        ...

    def save_game(self) -> GameState:
        ...

    def load_game(self) -> GameState:
        ...

    def current_version(self) -> int:
        ...

    def current_delta(self) -> SimulationDelta:
        ...


def is_refreshable(view: QWidget) -> bool:
    return callable(getattr(view, "refresh", None))
