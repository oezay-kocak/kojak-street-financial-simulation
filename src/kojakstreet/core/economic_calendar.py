"""Economic calendar rows derived from the simulation expectation layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass(slots=True)
class EconomicCalendarItem:
    date: str
    time: str
    country: str
    indicator: str
    period: str
    actual: float | None
    previous: float | None
    expected: float
    unit: str
    history_key: str
    history: list[float]
    surprise: float | None

    @property
    def search_text(self) -> str:
        return f"{self.date} {self.country} {self.indicator} {self.period}".lower()


def build_economic_calendar(state: Any) -> list[EconomicCalendarItem]:
    items: list[EconomicCalendarItem] = []
    current_date = getattr(state, "date", datetime.now())
    countries = getattr(state, "macro", {})
    for country in sorted(countries):
        macro = countries[country]
        items.extend(_country_macro_items(state, current_date, country, macro))
        items.append(_policy_item(state, current_date, country, macro))
    return sorted(items, key=lambda item: (_sort_date(item.date), item.time, item.country, item.indicator))


def _country_macro_items(state: Any, current_date: datetime, country: str, macro: dict[str, Any]) -> list[EconomicCalendarItem]:
    event_date = _monthly_report_date(current_date)
    period = event_date.strftime("%b").upper()
    return [
        _item(state, event_date, "08:30 AM", country, "GDP Growth YoY", period, f"{country}_BIP", "growth", float(macro.get("expected_growth", macro.get("bip_prozent", 0.0))), "%"),
        _item(state, event_date, "08:30 AM", country, "Inflation Rate YoY", period, f"{country}_INF", "inflation", float(macro.get("expected_inflation", macro.get("inflation", 0.0))), "%"),
        _item(state, event_date, "08:30 AM", country, "Unemployment Rate", period, f"{country}_ALO", "unemployment", float(macro.get("arbeitslosigkeit", 0.0)), "%"),
    ]


def _policy_item(state: Any, current_date: datetime, country: str, macro: dict[str, Any]) -> EconomicCalendarItem:
    event_date = _month_end_date(current_date)
    return _item(
        state,
        event_date,
        "02:00 PM",
        country,
        "Policy Rate Decision",
        event_date.strftime("%b").upper(),
        f"{country}_ZINS",
        "rate",
        float(macro.get("expected_rate", macro.get("zins", 0.0))),
        "%",
    )


def _item(
    state: Any,
    event_date: datetime,
    time_text: str,
    country: str,
    indicator: str,
    period: str,
    history_key: str,
    current_key: str,
    expected: float,
    unit: str,
) -> EconomicCalendarItem:
    history = _numeric_history(getattr(state, "macro_history", {}).get(history_key, []))
    actual = _actual_for_date(getattr(state, "macro_history", {}).get(history_key, []), event_date)
    previous = history[-1] if history else None
    if actual is not None and len(history) >= 2:
        previous = history[-2]
    if current_key == "growth":
        actual = _gdp_to_growth(actual, previous) if actual is not None else None
        previous_growth = _gdp_to_growth(previous, history[-2]) if previous is not None and len(history) >= 2 else None
        previous = previous_growth
        history = _growth_history(history)
    surprise = actual - expected if actual is not None else None
    return EconomicCalendarItem(
        date=event_date.strftime("%d.%m.%Y"),
        time=time_text,
        country=country,
        indicator=indicator,
        period=period,
        actual=actual,
        previous=previous,
        expected=expected,
        unit=unit,
        history_key=history_key,
        history=history,
        surprise=surprise,
    )


def _monthly_report_date(current_date: datetime) -> datetime:
    return current_date.replace(day=15)


def _month_end_date(current_date: datetime) -> datetime:
    next_month = current_date.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)


def _numeric_history(raw_history: list[Any]) -> list[float]:
    values = []
    for entry in raw_history:
        try:
            values.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
        except (TypeError, ValueError):
            continue
    return values


def _actual_for_date(raw_history: list[Any], event_date: datetime) -> float | None:
    target = event_date.strftime("%d.%m.%Y")
    for entry in reversed(raw_history):
        if isinstance(entry, (tuple, list)) and len(entry) > 1 and str(entry[1]) == target:
            try:
                return float(entry[0])
            except (TypeError, ValueError):
                return None
    return None


def _gdp_to_growth(current: float | None, previous: float | None) -> float | None:
    if current is None:
        return None
    if previous is None or previous == 0:
        return current
    return (current - previous) / abs(previous)


def _growth_history(history: list[float]) -> list[float]:
    if len(history) < 2:
        return history
    return [_gdp_to_growth(history[index], history[index - 1]) or 0.0 for index in range(1, len(history))]


def _sort_date(date_text: str) -> str:
    day, month, year = date_text.split(".")
    return f"{year}-{month}-{day}"
