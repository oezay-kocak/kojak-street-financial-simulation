from __future__ import annotations

from types import SimpleNamespace

import daten
from kojakstreet.core.company_lifecycle import company_hedge_profile
from kojakstreet.core.production_chains import COMMODITY_GROUPS, INPUT_RECIPES, PROCESSED_PRODUCTS


def test_all_processed_product_inputs_and_recipes_resolve_to_markets() -> None:
    commodities = {code for group in COMMODITY_GROUPS.values() for code in group.values()}
    markets = commodities | set(PROCESSED_PRODUCTS)
    aliases = {"Chemische Grundstoffe": "CHEM", "Fahrzeuge": "VEH", "Reifen": "TIRE"}

    for code, product in PROCESSED_PRODUCTS.items():
        for item in product.get("inputs", []):
            assert aliases.get(item, item) in markets, (code, item)

    for output_code, recipe in INPUT_RECIPES.items():
        assert output_code in PROCESSED_PRODUCTS
        assert all(input_code in markets for input_code in recipe)


def test_palladium_and_rhodium_are_used_in_weighted_recipes() -> None:
    recipe_inputs = {input_code for recipe in INPUT_RECIPES.values() for input_code in recipe}

    assert "XPD" in recipe_inputs
    assert "RHD" in recipe_inputs


def test_company_hedge_profile_is_visible_and_reduces_exposed_sectors() -> None:
    state = SimpleNamespace(
        makro={"USA": {"zins": 0.065, "inflation": 0.055, "default_probability": 0.03}},
    )
    asset = {
        "land": "USA",
        "branche": "Transport und Logistik",
        "output_mix": {"AIRF": 0.6, "FREIGHT": 0.4},
    }

    hedge = company_hedge_profile(state, asset)

    assert hedge["input_cost"] > 0.30
    assert hedge["overall"] > 0.0
    assert asset["hedge_summary"]
