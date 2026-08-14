"""Stock fundamentals and EMA helpers for the integrated simulation."""

from __future__ import annotations

from collections.abc import Iterable

SECTOR_PROFILES = {
    "Technologie": {"ps": 5.0, "fcf_margin": 0.20, "dividend_yield": 0.006},
    "Gesundheit": {"ps": 4.0, "fcf_margin": 0.18, "dividend_yield": 0.012},
    "Finanzen": {"ps": 2.2, "fcf_margin": 0.24, "dividend_yield": 0.030},
    "Einzelhandel": {"ps": 0.9, "fcf_margin": 0.055, "dividend_yield": 0.018},
    "Konsumgüter": {"ps": 2.4, "fcf_margin": 0.12, "dividend_yield": 0.025},
    "Automobil": {"ps": 0.8, "fcf_margin": 0.045, "dividend_yield": 0.015},
    "Maschinenbau": {"ps": 1.4, "fcf_margin": 0.09, "dividend_yield": 0.017},
    "Chemie": {"ps": 1.2, "fcf_margin": 0.075, "dividend_yield": 0.022},
    "Öl und Gas": {"ps": 1.1, "fcf_margin": 0.16, "dividend_yield": 0.040},
    "Stromerzeuger": {"ps": 1.5, "fcf_margin": 0.08, "dividend_yield": 0.035},
    "Telekommunikation": {"ps": 1.8, "fcf_margin": 0.10, "dividend_yield": 0.045},
    "Immobilien": {"ps": 6.0, "fcf_margin": 0.28, "dividend_yield": 0.035},
    "Transport und Logistik": {"ps": 0.9, "fcf_margin": 0.06, "dividend_yield": 0.012},
    "Verteidigung": {"ps": 2.0, "fcf_margin": 0.11, "dividend_yield": 0.020},
    "Landwirtschaft": {"ps": 1.0, "fcf_margin": 0.065, "dividend_yield": 0.020},
}
SECTOR_PROFILES["\u00d6l und Gas"] = {"ps": 1.1, "fcf_margin": 0.16, "dividend_yield": 0.040}
SECTOR_PROFILES["Konsumg\u00fcter"] = {"ps": 2.4, "fcf_margin": 0.12, "dividend_yield": 0.025}
SECTOR_PROFILES["Edelmetallf\u00f6rderer"] = {"ps": 1.6, "fcf_margin": 0.14, "dividend_yield": 0.018}
DEFAULT_PROFILE = {"ps": 1.8, "fcf_margin": 0.10, "dividend_yield": 0.018}


def ensure_stock_fundamentals(asset: dict) -> None:
    profile = _profile(asset)
    market_cap = float(asset.get("market_cap", float(asset.get("kurs", 100.0)) * 10_000_000.0))
    revenue = float(asset.get("revenue", market_cap / profile["ps"]))
    asset.setdefault("revenue", revenue)
    asset.setdefault("previous_revenue", revenue)
    asset.setdefault("previous_revenue_growth", 0.0)
    asset.setdefault("revenue_growth", 0.0)
    free_cash_flow = revenue * profile["fcf_margin"]
    asset.setdefault("free_cash_flow", free_cash_flow)
    asset.setdefault("previous_free_cash_flow", free_cash_flow)
    asset.setdefault("fcf_margin", profile["fcf_margin"])
    asset.setdefault("previous_fcf_margin", profile["fcf_margin"])
    asset.setdefault("dividend_yield", profile["dividend_yield"])
    asset.setdefault("previous_dividend_yield", profile["dividend_yield"])
    asset.setdefault("previous_eps", float(asset.get("eps", 5.0)))


def update_stock_fundamentals(asset: dict, macro_growth: float, result: float, sector_factor: float) -> None:
    ensure_stock_fundamentals(asset)
    previous_revenue = max(1.0, float(asset.get("revenue", 1.0)))
    previous_revenue_growth = float(asset.get("revenue_growth", 0.0))
    previous_free_cash_flow = float(asset.get("free_cash_flow", 0.0))
    previous_fcf_margin = float(asset.get("fcf_margin", 0.0))
    previous_dividend_yield = float(asset.get("dividend_yield", 0.0))
    previous_eps = float(asset.get("eps", 0.0))
    monthly_growth = _clamp((macro_growth / 12.0) + (result * 0.18) + ((sector_factor - 1.0) * 0.10), -0.12, 0.12)
    revenue = max(1.0, previous_revenue * (1.0 + monthly_growth))
    profile = _profile(asset)
    fcf_margin = _clamp(profile["fcf_margin"] + (result * 0.08) + ((sector_factor - 1.0) * 0.05), -0.05, 0.35)
    free_cash_flow = revenue * fcf_margin
    dividend_yield = _clamp(profile["dividend_yield"] + (fcf_margin * 0.08) - max(monthly_growth, 0.0) * 0.08, 0.0, 0.08)

    asset["previous_revenue"] = previous_revenue
    asset["previous_revenue_growth"] = previous_revenue_growth
    asset["previous_free_cash_flow"] = previous_free_cash_flow
    asset["previous_fcf_margin"] = previous_fcf_margin
    asset["previous_dividend_yield"] = previous_dividend_yield
    asset["previous_eps"] = previous_eps
    asset["revenue"] = revenue
    asset["revenue_growth"] = monthly_growth
    asset["fcf_margin"] = fcf_margin
    asset["free_cash_flow"] = free_cash_flow
    asset["dividend_yield"] = dividend_yield
    asset["eps"] = max(0.1, free_cash_flow / max(1.0, float(asset.get("aktien_anzahl", 10_000_000.0))))


def fundamental_price_signal(asset: dict) -> float:
    if "revenue" not in asset or "free_cash_flow" not in asset:
        ensure_stock_fundamentals(asset)
    market_cap = max(1.0, float(asset.get("market_cap", 1.0)))
    revenue_growth = float(asset.get("revenue_growth", 0.0))
    fcf_yield = float(asset.get("free_cash_flow", 0.0)) / market_cap
    dividend_yield = float(asset.get("dividend_yield", 0.0))
    return (revenue_growth * 1.5) + ((fcf_yield - 0.04) * 0.8) + (dividend_yield * 0.35)


def ema_values(values: Iterable[float], period: int) -> list[float]:
    series = [float(value) for value in values]
    if not series:
        return []
    alpha = 2.0 / (period + 1.0)
    ema = [series[0]]
    for value in series[1:]:
        ema.append((value * alpha) + (ema[-1] * (1.0 - alpha)))
    return ema


def ema_diff(history: list, period: int) -> float:
    prices = _history_values(history, max(period * 4, period + 1))
    if not prices:
        return 0.0
    ema = ema_values(prices, min(period, len(prices)))[-1]
    return ((prices[-1] - ema) / ema) if ema else 0.0


def _history_values(history: list, limit: int | None = None) -> list[float]:
    values = []
    source = history[-limit:] if limit else history
    for entry in source:
        try:
            values.append(float(entry[0] if isinstance(entry, (tuple, list)) else entry))
        except (TypeError, ValueError):
            continue
    return values


def _profile(asset: dict) -> dict[str, float]:
    return SECTOR_PROFILES.get(str(asset.get("branche", "")), DEFAULT_PROFILE)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
