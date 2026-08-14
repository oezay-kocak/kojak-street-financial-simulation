"""Forex analytics for currency-pair views."""

from __future__ import annotations

from dataclasses import dataclass, field

from kojakstreet.core.countries import CURRENCY_CODES, RESERVE_CURRENCY, RESERVE_CURRENCY_CODE
from kojakstreet.core.state import GameState


@dataclass(slots=True)
class ForexPair:
    pair: str
    base: str
    quote: str
    rate: float
    change_percent: float
    history: list[float] = field(default_factory=list)
    source_pair: str = ""


@dataclass(slots=True)
class CurrencyStrengthMetric:
    code: str
    average_change: float
    pair_count: int


def build_forex_pairs(state: GameState, include_crypto: bool = False) -> list[ForexPair]:
    pairs = []
    source_pairs = set(state.forex_history)
    for base in state.currency_strength:
        for quote in state.currency_strength:
            if base != quote:
                source_pairs.add(f"{base}/{quote}")
    for pair in sorted(source_pairs):
        if not include_crypto and "BTC" in pair:
            continue
        if "/" not in pair:
            continue
        history = state.forex_history.get(pair, [])
        values = _history_values(history)
        base, quote = pair.split("/", 1)
        display_base = currency_code(base)
        display_quote = currency_code(quote)
        current_rate = _current_rate(state, base, quote)
        first = values[-2] if len(values) >= 2 else current_rate
        last = values[-1] if values else current_rate
        change = ((last - first) / first * 100.0) if first else 0.0
        pairs.append(
            ForexPair(
                pair=f"{display_base}/{display_quote}",
                base=display_base,
                quote=display_quote,
                rate=last,
                change_percent=change,
                history=values,
                source_pair=pair,
            )
        )
    return sorted(pairs, key=lambda item: item.pair)


def build_currency_strength_metrics(state: GameState) -> list[CurrencyStrengthMetric]:
    """Average daily strength from every non-crypto pair containing each currency."""

    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for pair in build_forex_pairs(state):
        totals[pair.base] = totals.get(pair.base, 0.0) + pair.change_percent
        counts[pair.base] = counts.get(pair.base, 0) + 1
        totals[pair.quote] = totals.get(pair.quote, 0.0) - pair.change_percent
        counts[pair.quote] = counts.get(pair.quote, 0) + 1

    return [
        CurrencyStrengthMetric(code=code, average_change=totals[code] / counts[code], pair_count=counts[code])
        for code in sorted(totals)
        if counts.get(code, 0) > 0
    ]


def currency_code(currency: str) -> str:
    if currency == RESERVE_CURRENCY:
        return RESERVE_CURRENCY_CODE
    return CURRENCY_CODES.get(currency, currency)


def _current_rate(state: GameState, base: str, quote: str) -> float:
    base_strength = float(state.currency_strength.get(base, 1.0))
    quote_strength = float(state.currency_strength.get(quote, 1.0))
    return base_strength / quote_strength if quote_strength else 1.0


def _history_values(history: list) -> list[float]:
    values = []
    for entry in history:
        try:
            values.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
        except (TypeError, ValueError):
            continue
    return values
