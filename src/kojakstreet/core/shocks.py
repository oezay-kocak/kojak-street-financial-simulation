"""Bounded, serializable economic shock state shared by real-economy systems."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

MAX_ACTIVE_AND_RECENT_SHOCKS = 64


def add_shock(
    state: Any,
    *,
    shock_id: str,
    shock_type: str,
    target: str,
    magnitude: float,
    duration_days: int,
    decay: str = "linear",
    source: str = "manual",
    stacking: str = "multiplicative",
) -> dict[str, object]:
    """Create or replace one shock. Negative magnitude reduces availability."""

    today = _as_date(getattr(state, "datum", date.today()))
    shock = {
        "id": str(shock_id),
        "type": str(shock_type),
        "target": str(target),
        "magnitude": max(-0.95, min(3.0, float(magnitude))),
        "start_date": today.isoformat(),
        "duration_days": max(1, int(duration_days)),
        "decay": decay if decay in {"linear", "exponential", "step"} else "linear",
        "source": str(source),
        "stacking": stacking if stacking in {"multiplicative", "strongest"} else "multiplicative",
    }
    shocks = [item for item in getattr(state, "economic_shocks", []) if str(item.get("id")) != shock["id"]]
    shocks.append(shock)
    state.economic_shocks = shocks[-MAX_ACTIVE_AND_RECENT_SHOCKS:]
    return shock


def shock_multiplier(state: Any, shock_type: str, target: str, *, on_date: date | datetime | None = None) -> float:
    today = _as_date(on_date or getattr(state, "datum", date.today()))
    factors: list[tuple[float, str]] = []
    retained = []
    for shock in getattr(state, "economic_shocks", []):
        start = _as_date(shock.get("start_date", today))
        duration = max(1, int(shock.get("duration_days", 1)))
        age = (today - start).days
        if age < duration + 365:
            retained.append(shock)
        if age < 0 or age >= duration:
            continue
        if str(shock.get("type")) != shock_type or str(shock.get("target")) not in {target, "*"}:
            continue
        remaining = _remaining(str(shock.get("decay", "linear")), age, duration)
        factor = max(0.05, 1.0 + float(shock.get("magnitude", 0.0)) * remaining)
        factors.append((factor, str(shock.get("stacking", "multiplicative"))))
    state.economic_shocks = retained[-MAX_ACTIVE_AND_RECENT_SHOCKS:]
    if not factors:
        return 1.0
    strongest = [factor for factor, stacking in factors if stacking == "strongest"]
    product = 1.0
    for factor, stacking in factors:
        if stacking == "multiplicative":
            product *= factor
    if strongest:
        product *= min(strongest, key=lambda factor: abs(factor - 1.0) * -1.0)
    return max(0.05, min(4.0, product))


def _remaining(decay: str, age: int, duration: int) -> float:
    if decay == "step":
        return 1.0
    fraction = max(0.0, min(1.0, age / max(1, duration - 1)))
    if decay == "exponential":
        return (1.0 - fraction) ** 2
    return 1.0 - fraction


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
