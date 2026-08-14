"""Human-readable price-driver summaries for assets and product tickets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PriceDriver:
    label: str
    score: float
    detail: str


def explain_asset_move(asset: dict[str, Any], asset_type: str, *, limit: int = 4) -> list[PriceDriver]:
    drivers: list[PriceDriver] = []
    if asset_type == "Stock":
        drivers.extend(
            [
                PriceDriver("Fundamentals", float(asset.get("revenue_growth", 0.0)) + float(asset.get("fcf_margin", 0.0)) * 0.25, _growth_detail(asset, "revenue_growth")),
                PriceDriver("Valuation", _valuation_score(asset), _valuation_detail(asset)),
                PriceDriver("Fund/ETF Flows", float(asset.get("fund_flow_pressure", 0.0)), _pressure_detail(asset, "fund_flow_pressure")),
            ]
        )
    elif asset_type == "Commodity":
        drivers.extend(
            [
                PriceDriver("Supply/Demand", float(asset.get("demand_change", 0.0)) - float(asset.get("production_change", 0.0)), _supply_detail(asset)),
                PriceDriver("Inventories", -float(asset.get("inventories_change", 0.0)), _growth_detail(asset, "inventories_change")),
                PriceDriver("Costs", float(asset.get("extraction_cost_change", 0.0)), _growth_detail(asset, "extraction_cost_change")),
            ]
        )
    elif asset_type == "Crypto":
        drivers.extend(
            [
                PriceDriver("Network Demand", float(asset.get("demand_change", 0.0)) + float(asset.get("transaction_change", 0.0)), _growth_detail(asset, "demand_change")),
                PriceDriver("Fees", float(asset.get("fee_change", 0.0)), _growth_detail(asset, "fee_change")),
                PriceDriver("Supply", -float(asset.get("inflation_rate", 0.0)), _growth_detail(asset, "inflation_rate")),
            ]
        )
    elif asset_type == "Derivative":
        drivers.extend(
            [
                PriceDriver("Contract", 0.0, str(asset.get("instrument_type", "Derivative"))),
                PriceDriver("Underlying", 0.0, str(asset.get("underlying", ""))),
                PriceDriver("Rate/Spread", float(asset.get("yield_rate", asset.get("spread", 0.0))), _rate_or_spread_detail(asset)),
            ]
        )
    ranked = sorted(drivers, key=lambda driver: abs(driver.score), reverse=True)
    return ranked[: max(1, limit)]


def driver_summary(asset: dict[str, Any], asset_type: str) -> str:
    drivers = explain_asset_move(asset, asset_type, limit=4)
    return " | ".join(f"{driver.label}: {driver.detail}" for driver in drivers)


def _growth_detail(asset: dict[str, Any], key: str) -> str:
    return f"{float(asset.get(key, 0.0)) * 100:+.2f}%"


def _signed_detail(asset: dict[str, Any], key: str) -> str:
    return f"{float(asset.get(key, 0.0)):+.4f}"


def _pressure_detail(asset: dict[str, Any], key: str) -> str:
    return f"{float(asset.get(key, 0.0)) * 100:+.2f}% pressure"


def _supply_detail(asset: dict[str, Any]) -> str:
    demand = float(asset.get("demand_change", 0.0)) * 100.0
    production = float(asset.get("production_change", 0.0)) * 100.0
    return f"demand {demand:+.2f}% / supply {production:+.2f}%"


def _valuation_score(asset: dict[str, Any]) -> float:
    price = max(0.01, float(asset.get("kurs", 0.0)))
    eps = max(0.01, float(asset.get("eps", 0.01)))
    return (20.0 - price / eps) / 100.0


def _valuation_detail(asset: dict[str, Any]) -> str:
    price = max(0.01, float(asset.get("kurs", 0.0)))
    eps = max(0.01, float(asset.get("eps", 0.01)))
    return f"P/E {price / eps:.1f}"


def _rate_or_spread_detail(asset: dict[str, Any]) -> str:
    if "spread" in asset:
        return f"spread {float(asset.get('spread', 0.0)) * 100:.2f}%"
    if "yield_rate" in asset:
        return f"yield {float(asset.get('yield_rate', 0.0)) * 100:.2f}%"
    return str(asset.get("instrument_type", ""))
