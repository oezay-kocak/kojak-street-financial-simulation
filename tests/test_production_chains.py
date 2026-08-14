from __future__ import annotations

from types import SimpleNamespace

from kojakstreet.core.companies import ensure_company_universe
from kojakstreet.core.countries import COUNTRY_SYMBOLS
from kojakstreet.core.production_chains import (
    COMMODITY_GROUPS,
    CONSUMER_BASKET,
    INPUT_RECIPES,
    PROCESSED_PRODUCTS,
    PRODUCT_NAME_TO_CODE,
    SECTOR_INPUT_WEIGHTS,
    commodity_definitions,
    ensure_country_economies,
    ensure_processed_products,
    opportunity_sector,
    update_population,
    update_production_chain,
)


def test_new_commodity_document_list_has_split_primary_goods() -> None:
    tickers = {ticker for group in COMMODITY_GROUPS.values() for ticker in group.values()}

    assert len(tickers) == 34
    assert {"COF", "COC", "SUG", "MEAT", "FISH", "IRO", "BAU", "NIK", "SIL"} <= tickers
    assert "KCSO" not in tickers
    assert "LFSH" not in tickers


def test_processed_products_include_supply_chain_inputs() -> None:
    ensure_processed_products(daten := _minimal_daten())

    assert len(daten.processed_products) == len(PROCESSED_PRODUCTS)
    assert daten.processed_products["SEMI"]["inputs"]
    assert "Stahl" in [product["name"] for product in daten.processed_products.values()]
    assert {"CRSTORE", "CRPAY", "CRDATA", "CRGRID"} <= set(daten.processed_products)
    assert daten.processed_products["CRPAY"]["inputs"] == ["ELC", "ECOMP", "SDIG", "CHW"]


def test_population_grows_with_good_economy() -> None:
    daten = _minimal_daten()

    update_population(daten)

    country = next(iter(daten.makro))
    assert daten.makro[country]["bevoelkerung"] > 20_000_000.0


def test_production_chain_links_companies_to_real_supply_and_demand() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten)

    assert daten.processed_products["ELC"]["supply"] > 0
    assert daten.processed_products["ELC"]["demand"] > 0
    assert daten.rohstoffe["CL"]["demand"] > 0
    assert all(asset.get("specialization") for asset in daten.aktien.values())


def test_sector_need_matrix_and_consumer_basket_drive_demand() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten)

    assert SECTOR_INPUT_WEIGHTS["Automobil"]["STL"] > 0
    assert CONSUMER_BASKET["FOOD"] > CONSUMER_BASKET["LUX"]
    assert daten.processed_products["STL"]["demand"] > 10.0
    assert daten.processed_products["FOOD"]["demand"] > daten.processed_products["LUX"]["demand"]


def test_inventory_buffer_smooths_shortages_and_company_score_tracks_chain() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {
                "name": name,
                "kategorie": group,
                "kurs": 100.0,
                "historie": [],
                "inventories": 300.0,
            }

    update_production_chain(daten)
    first_food_inventory = daten.processed_products["FOOD"]["inventories"]
    daten.processed_products["FOOD"]["inventories"] = 300.0
    daten.processed_products["FOOD"]["demand"] = 900.0
    update_production_chain(daten)

    assert daten.processed_products["FOOD"]["inventories"] > 1.0
    assert first_food_inventory > 1.0
    assert all("production_score" in asset for asset in daten.aktien.values())


def test_companies_can_run_output_portfolios_inside_their_sector() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten)

    mixed = [asset for asset in daten.aktien.values() if len(asset.get("output_mix", {})) > 1]
    assert mixed
    assert all(abs(sum(asset["output_mix"].values()) - 1.0) < 0.0001 for asset in daten.aktien.values())
    assert all(asset["specialization"] in asset["output_mix"] for asset in daten.aktien.values())


def test_processed_products_have_internal_price_pressure_and_opportunity_sector() -> None:
    daten = _minimal_daten()
    ensure_processed_products(daten)
    daten.processed_products["CLOUD"]["shortage"] = 0.95
    daten.processed_products["CLOUD"]["price_pressure"] = 0.80
    daten.processed_products["CLOUD"]["demand"] = 1000.0
    daten.processed_products["CLOUD"]["supply"] = 50.0

    assert opportunity_sector(daten) == "Technologie"


def test_company_mix_rebalances_toward_shortage_without_leaving_sector() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}
    tech = next(asset for asset in daten.aktien.values() if asset["branche"] == "Technologie")
    tech["output_mix"] = {"SEMI": 0.85, "ECOMP": 0.15}
    daten.processed_products["CLOUD"]["shortage"] = 0.95
    daten.processed_products["CLOUD"]["price_pressure"] = 0.80
    before = tech["output_mix"].get("CLOUD", 0.0)

    update_production_chain(daten)

    assert tech["output_mix"].get("CLOUD", 0.0) >= before
    assert set(tech["output_mix"]) <= {
        "SEMI", "ECOMP", "CHW", "SDIG", "CELEC", "BHW", "SOFT", "CLOUD", "PLAT", "BESS", "RND", "IP", "CYBR"
    }


def test_sector_balance_profiles_keep_essential_goods_near_start_equilibrium() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten, advance_population=False)

    electricity = daten.processed_products["ELC"]
    luxury = daten.processed_products["LUX"]

    assert electricity["supply"] >= electricity["demand"] * 0.96
    assert electricity["shortage"] <= 0.05
    assert luxury["demand"] >= 25.0
    assert luxury["price_pressure"] > -0.05


def test_supply_chain_values_are_textured_and_shortage_matches_visible_gap() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten, advance_population=False)

    products = list(daten.processed_products.values())
    identical_pairs = [
        product
        for product in products
        if abs(float(product["supply"]) - float(product["demand"])) < 0.005
    ]
    bad_shortage = [
        product
        for product in products
        if float(product["supply"]) >= float(product["demand"]) and float(product["shortage"]) > 0.0001
    ]

    assert len(identical_pairs) <= 1
    assert bad_shortage == []
    assert len({round(float(product["supply"]), 2) for product in products}) > 40


def test_first_supply_chain_point_starts_from_balanced_market_level() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten, advance_population=False)

    for asset in list(daten.processed_products.values()) + list(daten.rohstoffe.values()):
        assert asset["supply_history"][-1][0] == asset["supply"]
        assert asset["demand_history"][-1][0] == asset["demand"]
        assert abs(float(asset["supply_change"])) < 0.0001
        assert abs(float(asset["demand_change"])) < 0.0001


def test_overproduction_is_recorded_as_negative_imbalance_not_shortage() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten, advance_population=False)

    surplus_products = [
        product
        for product in daten.processed_products.values()
        if float(product["supply"]) > float(product["demand"]) * 1.03
    ]

    assert surplus_products
    assert all(float(product["shortage"]) == 0.0 for product in surplus_products)
    assert all(float(product["surplus"]) > 0.0 for product in surplus_products)
    assert all(float(product["imbalance"]) < 0.0 for product in surplus_products)


def test_recipe_inputs_resolve_to_real_markets_and_weight_stahl_materials() -> None:
    known = set(commodity_definitions()) | set(PROCESSED_PRODUCTS)
    unresolved = []
    for code, data in PROCESSED_PRODUCTS.items():
        for item in data.get("inputs", []):
            normalized = PRODUCT_NAME_TO_CODE.get(item, item)
            if normalized not in known:
                unresolved.append((code, item))

    assert unresolved == []
    assert INPUT_RECIPES["STL"]["IRO"] > INPUT_RECIPES["STL"]["NEWC"] > INPUT_RECIPES["STL"]["ELC"]


def test_country_profiles_create_regional_supply_demand_and_trade_data() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    ensure_country_economies(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten, advance_population=False)

    countries = list(daten.makro.values())
    first = countries[0]
    second = countries[1]

    assert first["economic_profile"]["sector_focus"]
    assert set(first["economic_profile"]["sector_focus"]) != set(second["economic_profile"]["sector_focus"])
    assert first["regional_supply"]
    assert first["regional_demand"]
    assert "trade_balance" in first
    assert "import_dependency" in first
    assert "trade_partners" in first
    assert len(first["trade_partners"]) > 1
    assert any(len(partners) > 1 for partners in first["trade_partner_details"].values())
    assert max(first["regional_shortage"].values()) < 1.0


def test_country_trade_matches_exports_to_real_import_gaps() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    ensure_country_economies(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten, advance_population=False)

    for code in list(daten.rohstoffe) + list(daten.processed_products):
        exporters = [
            country
            for country, macro in daten.makro.items()
            if float(macro.get("exports", {}).get(code, 0.0)) > 0.0
        ]
        importers = [
            country
            for country, macro in daten.makro.items()
            if float(macro.get("imports", {}).get(code, 0.0)) > 0.0
        ]
        if exporters:
            assert importers
        if importers:
            assert exporters


def test_regional_supply_and_demand_sum_to_global_markets() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ensure_processed_products(daten)
    ensure_country_economies(daten)
    for group, items in COMMODITY_GROUPS.items():
        for name, ticker in items.items():
            daten.rohstoffe[ticker] = {"name": name, "kategorie": group, "kurs": 100.0, "historie": []}

    update_production_chain(daten, advance_population=False)

    for code, market in {**daten.rohstoffe, **daten.processed_products}.items():
        regional_supply = sum(float(macro.get("regional_supply", {}).get(code, 0.0)) for macro in daten.makro.values())
        regional_demand = sum(float(macro.get("regional_demand", {}).get(code, 0.0)) for macro in daten.makro.values())
        global_supply = float(market.get("supply", market.get("production", 0.0)))
        global_demand = float(market.get("demand", 0.0))

        assert abs(regional_supply - global_supply) < 0.01
        assert abs(regional_demand - global_demand) < 0.01


def _minimal_daten() -> SimpleNamespace:
    return SimpleNamespace(
        LAENDER=dict(COUNTRY_SYMBOLS),
        makro={
            country: {"bip_prozent": 0.03, "arbeitslosigkeit": 0.05, "bevoelkerung": 20_000_000.0}
            for country in COUNTRY_SYMBOLS
        },
        aktien={},
        rohstoffe={},
        processed_products={},
        depot={},
        perpetuals={},
        anleihen=[],
    )
