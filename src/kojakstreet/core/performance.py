"""Lightweight runtime profiling helpers for simulation phases."""

from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any, Iterator


def record_phase_duration(daten: Any, name: str, started: float) -> None:
    duration_ms = (perf_counter() - started) * 1000.0
    timings = getattr(daten, "simulation_phase_timings", None)
    if timings is None:
        daten.simulation_phase_timings = []
        timings = daten.simulation_phase_timings
    timings.append({"phase": name, "duration_ms": duration_ms})


@contextmanager
def timed_phase(daten: Any, name: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        record_phase_duration(daten, name, started)
