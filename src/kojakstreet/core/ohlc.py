"""Backward-compatible OHLC history helpers."""

from __future__ import annotations

from typing import Any


def history_close(entry: Any) -> float:
    """Return the close price from legacy or OHLC history rows."""

    if isinstance(entry, dict):
        return float(entry.get("close", entry.get("kurs", entry.get("price", 0.0))))
    if isinstance(entry, (tuple, list)) and entry:
        return float(entry[0])
    return float(entry)


def history_ohlc(entry: Any) -> tuple[float, float, float, float]:
    """Return open, high, low, close from a history row.

    Legacy rows are shaped as ``(close, date, label)``. New rows keep close at
    index 0 and add ``open, high, low`` at indexes 3..5.
    """

    close = history_close(entry)
    if isinstance(entry, dict):
        open_price = float(entry.get("open", close))
        high = float(entry.get("high", max(open_price, close)))
        low = float(entry.get("low", min(open_price, close)))
        return open_price, max(high, open_price, close), min(low, open_price, close), close
    if isinstance(entry, (tuple, list)) and len(entry) >= 6:
        open_price = float(entry[3])
        high = float(entry[4])
        low = float(entry[5])
        return open_price, max(high, open_price, close), min(low, open_price, close), close
    return close, close, close, close


def make_ohlc_entry(
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    date_text: str,
    label: str = "",
) -> tuple[float, str, str, float, float, float]:
    open_price = max(0.0, float(open_price))
    close = max(0.0, float(close))
    high = max(open_price, close, float(high))
    low = max(0.0, min(open_price, close, float(low)))
    return (close, date_text, label, open_price, high, low)


def make_ohlc_from_move(
    open_price: float,
    close: float,
    date_text: str,
    *,
    volatility: float = 0.0,
    label: str = "",
) -> tuple[float, str, str, float, float, float]:
    open_price = float(open_price)
    close = float(close)
    body = abs(close - open_price)
    base = max(open_price, close, 1.0)
    intraday_range = max(body, base * max(0.0005, abs(float(volatility))))
    upper_wick = intraday_range * 0.30
    lower_wick = intraday_range * 0.24
    high = max(open_price, close) + upper_wick
    low = min(open_price, close) - lower_wick
    return make_ohlc_entry(
        open_price=open_price,
        high=high,
        low=low,
        close=close,
        date_text=date_text,
        label=label,
    )


def append_ohlc_from_move(
    asset: dict[str, Any],
    open_price: float,
    close: float,
    date_text: str,
    *,
    volatility: float = 0.0,
    label: str = "",
    limit: int | None = None,
) -> None:
    history = asset.setdefault("historie", [])
    history.append(
        make_ohlc_from_move(
            open_price,
            close,
            date_text,
            volatility=volatility,
            label=label,
        )
    )
    if limit is not None and len(history) > limit:
        del history[:-limit]


def normalize_commodity_supply_key(asset: dict[str, Any]) -> float:
    """Collapse known legacy mojibake variants into ``foerder_menge``."""

    candidates = (
        "foerder_menge",
        "förder_menge",
        "fÃ¶rder_menge",
        "fÃƒÂ¶rder_menge",
    )
    value = 0.0
    for key in candidates:
        if key in asset:
            try:
                value = float(asset[key])
                break
            except (TypeError, ValueError):
                value = 0.0
    asset["foerder_menge"] = value
    for key in candidates[1:]:
        asset.pop(key, None)
    return value
