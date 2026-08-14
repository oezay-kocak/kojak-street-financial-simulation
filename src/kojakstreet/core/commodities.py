"""Commodity fundamentals for supply, demand, costs and inventories."""

from __future__ import annotations

import random


def ensure_commodity_fundamentals(asset: dict) -> None:
    price = float(asset.get("kurs", 100.0))
    production = float(asset.get("production", 100.0))
    demand = float(asset.get("demand", 100.0))
    extraction_cost = float(asset.get("extraction_cost", max(20.0, price * 0.42)))
    inventories = float(asset.get("inventories", 100.0))
    asset.setdefault("production", production)
    asset.setdefault("previous_production", production)
    asset.setdefault("production_change", 0.0)
    asset.setdefault("demand", demand)
    asset.setdefault("previous_demand", demand)
    asset.setdefault("demand_change", 0.0)
    asset.setdefault("extraction_cost", extraction_cost)
    asset.setdefault("previous_extraction_cost", extraction_cost)
    asset.setdefault("extraction_cost_change", 0.0)
    asset.setdefault("inventories", inventories)
    asset.setdefault("previous_inventories", inventories)
    asset.setdefault("inventories_change", 0.0)


def update_commodity_fundamentals(
    asset: dict,
    *,
    macro_growth: float,
    price_change: float,
    event_result: float,
) -> None:
    ensure_commodity_fundamentals(asset)
    previous_production = max(1.0, float(asset.get("production", 100.0)))
    previous_demand = max(1.0, float(asset.get("demand", 100.0)))
    previous_extraction_cost = max(1.0, float(asset.get("extraction_cost", 40.0)))
    previous_inventories = max(1.0, float(asset.get("inventories", 100.0)))
    price_level = (float(asset.get("kurs", 100.0)) - 100.0) / 100.0
    price_momentum = price_change / 100.0

    production_change = _clamp((price_level * 0.018) + (price_momentum * 0.16) + (event_result * 0.035), -0.08, 0.08)
    demand_change = _clamp((macro_growth * 1.8) - (price_level * 0.006) + (event_result * 0.020), -0.07, 0.07)
    extraction_cost_change = _clamp(_cost_noise(asset) + (abs(price_momentum) * 0.015), -0.025, 0.025)
    inventory_change = _clamp(
        (production_change - demand_change) - (price_level * 0.018) - (price_momentum * 0.10),
        -0.10,
        0.10,
    )

    asset["previous_production"] = previous_production
    asset["previous_demand"] = previous_demand
    asset["previous_extraction_cost"] = previous_extraction_cost
    asset["previous_inventories"] = previous_inventories
    asset["production"] = max(10.0, previous_production * (1.0 + production_change))
    asset["demand"] = max(10.0, previous_demand * (1.0 + demand_change))
    asset["extraction_cost"] = max(1.0, previous_extraction_cost * (1.0 + extraction_cost_change))
    asset["inventories"] = max(1.0, previous_inventories * (1.0 + inventory_change))
    asset["production_change"] = production_change
    asset["demand_change"] = demand_change
    asset["extraction_cost_change"] = extraction_cost_change
    asset["inventories_change"] = inventory_change


def commodity_price_signal(asset: dict) -> float:
    ensure_commodity_fundamentals(asset)
    production_change = float(asset.get("production_change", 0.0))
    demand_change = float(asset.get("demand_change", 0.0))
    cost_change = float(asset.get("extraction_cost_change", 0.0))
    inventory_change = float(asset.get("inventories_change", 0.0))
    inventories = max(1.0, float(asset.get("inventories", 100.0)))
    demand = max(1.0, float(asset.get("demand", 100.0)))
    stock_to_use_gap = (demand - inventories) / demand
    low_inventory_pressure = _clamp(stock_to_use_gap, -0.35, 0.65)
    supply_response = max(0.0, production_change) * max(0.25, 1.0 - low_inventory_pressure)
    scarcity_signal = max(0.0, -inventory_change) * 2.4 + max(0.0, demand_change - production_change) * 1.8
    mean_reversion = _clamp((float(asset.get("kurs", 100.0)) - 100.0) / 100.0, -1.0, 2.5) * 0.16
    raw_signal = (
        (demand_change * 1.5)
        - (supply_response * 0.9)
        + (cost_change * 1.0)
        - (inventory_change * 1.7)
        + (low_inventory_pressure * 0.16)
        + scarcity_signal
        - mean_reversion
    )
    return _clamp(raw_signal, -0.08, 0.08)


def _cost_noise(asset: dict) -> float:
    momentum = float(asset.get("news_momentum", 0.0))
    category = str(asset.get("kategorie", ""))
    base = random.uniform(-0.006, 0.006)
    if category in {"Energietraeger", "Energieträger"}:
        base += 0.0015
    return _clamp(base + (momentum * 0.006), -0.018, 0.018)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
