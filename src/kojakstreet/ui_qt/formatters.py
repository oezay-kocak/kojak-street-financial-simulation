"""Formatting helpers for the Qt interface."""

from kojakstreet.core.countries import COUNTRY_SYMBOLS, RESERVE_CURRENCY, RESERVE_CURRENCY_SYMBOL


def money(value: float) -> str:
    return f"${value:,.2f}"


def gold_dinar(value: float) -> str:
    return f"{value:,.2f} GD"


def percent(value: float) -> str:
    return f"{value:+.2f}%"


def compact_money(value: float) -> str:
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs_value >= 1_000:
        return f"{value / 1_000:.2f}K"
    return f"{value:.2f}"


def currency_symbol_for_region(region: str) -> str:
    if region == RESERVE_CURRENCY:
        return RESERVE_CURRENCY_SYMBOL
    return COUNTRY_SYMBOLS.get(region, region)


def regional_money(value: float, region: str, *, compact: bool = False) -> str:
    amount = compact_money(value) if compact else f"{value:,.0f}"
    return f"{amount} {currency_symbol_for_region(region)}"


def regional_money_precise(value: float, region: str) -> str:
    return f"{value:,.2f} {currency_symbol_for_region(region)}"
