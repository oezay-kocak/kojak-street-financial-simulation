"""Deep-history contracts, retention limits and semantic aggregation helpers.

The live model keeps only the lookback needed for calculations.  DuckDB owns
the durable timeline and stores semantically aggregated monthly/yearly rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Iterable

HISTORY_SCHEMA_VERSION = 3
ECONOMIC_MODEL_VERSION = "workforce-demographics-v1"
LEGACY_ECONOMIC_MODEL_VERSION = "economic-integrity-v1"
RAW_RETENTION_DAYS = 730
HOT_PRICE_POINTS = 520  # longest calculation is 180 days; ~3x safety margin
HOT_METRIC_POINTS = 900
HOT_FUND_POINTS = 1040
HOT_REALIZED_EVENTS = 2000
DEFAULT_PIXEL_BUDGET = 1200
MAX_PIXEL_BUDGET = 2000


class SemanticType(StrEnum):
    PRICE = "price"
    LEVEL = "level"
    RATE = "rate"
    FLOW = "flow"
    EVENT = "event"


@dataclass(frozen=True, slots=True)
class SemanticAggregate:
    start: date
    end: date
    open: float
    high: float
    low: float
    close: float
    mean: float
    total: float
    count: int

    @property
    def value(self) -> float:
        return self.total if self.count and self.semantic_is_flow else self.close

    @property
    def semantic_is_flow(self) -> bool:
        return False


def aggregate_values(points: Iterable[tuple[date | datetime | str, float]], semantic: SemanticType) -> SemanticAggregate:
    """Aggregate one already-bucketed series with explicit field semantics."""

    ordered = sorted((_as_date(day), float(value)) for day, value in points)
    if not ordered:
        raise ValueError("Cannot aggregate an empty history bucket")
    values = [value for _day, value in ordered]
    total = sum(values) if semantic is SemanticType.FLOW else 0.0
    return SemanticAggregate(
        start=ordered[0][0],
        end=ordered[-1][0],
        open=values[0],
        high=max(values),
        low=min(values),
        close=values[-1],
        mean=sum(values) / len(values),
        total=total,
        count=len(values),
    )


def bounded_extend(history: list, values: Iterable, limit: int) -> None:
    history.extend(values)
    trim_history(history, limit)


def trim_history(history: list, limit: int) -> None:
    if len(history) > limit:
        del history[:-limit]


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    if len(text) == 10 and text[2] == "." and text[5] == ".":
        return datetime.strptime(text, "%d.%m.%Y").date()
    return date.fromisoformat(text[:10])
