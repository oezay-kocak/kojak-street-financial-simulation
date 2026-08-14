from __future__ import annotations

from kojakstreet.core.commodities import (
    commodity_price_signal,
    ensure_commodity_fundamentals,
    update_commodity_fundamentals,
)
from kojakstreet.core.ohlc import normalize_commodity_supply_key


def test_commodity_fundamentals_initialize_supply_metrics() -> None:
    asset = {"kurs": 100.0, "kategorie": "Energieträger"}

    ensure_commodity_fundamentals(asset)

    assert asset["production"] == 100.0
    assert asset["demand"] == 100.0
    assert asset["extraction_cost"] > 0
    assert asset["inventories"] == 100.0


def test_commodity_fundamentals_keep_previous_month_comparisons() -> None:
    asset = {"kurs": 115.0, "aenderung": 2.0, "kategorie": "Energieträger"}
    ensure_commodity_fundamentals(asset)

    update_commodity_fundamentals(asset, macro_growth=0.03, price_change=2.0, event_result=0.05)

    assert asset["previous_production"] == 100.0
    assert asset["previous_demand"] == 100.0
    assert asset["production"] != 100.0
    assert asset["demand"] != 100.0


def test_commodity_price_signal_rewards_demand_and_low_inventory() -> None:
    asset = {
        "production_change": 0.00,
        "demand_change": 0.04,
        "extraction_cost_change": 0.01,
        "inventories_change": -0.03,
    }

    assert commodity_price_signal(asset) > 0


def test_commodity_price_signal_is_capped_to_prevent_runaway_prices() -> None:
    asset = {
        "production_change": -0.20,
        "demand_change": 0.25,
        "extraction_cost_change": 0.10,
        "inventories_change": -0.30,
    }

    assert commodity_price_signal(asset) == 0.08


def test_commodity_supply_key_normalizes_legacy_variants() -> None:
    asset = {"förder_menge": 1.75, "fÃ¶rder_menge": -2.0}

    value = normalize_commodity_supply_key(asset)

    assert value == 1.75
    assert asset == {"foerder_menge": 1.75}
