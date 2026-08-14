from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from kojakstreet.core.data_store import EconomicDataStore
from kojakstreet.core.economy_repository import EconomyRepository


def test_country_macro_history_is_recorded_only_on_report_day(tmp_path) -> None:
    store = EconomicDataStore(tmp_path / "kojakstreet.duckdb")
    if not store.enabled:
        return
    daten = SimpleNamespace(
        datum=datetime(1990, 1, 10),
        aktien={},
        rohstoffe={},
        kryptos={},
        fonds={},
        indizes={},
        processed_products={
            "SDIG": {
                "name": "Digital Services",
                "kategorie": "Technology",
                "supply": 100.0,
                "demand": 88.0,
                "inventories": 30.0,
                "shortage": 0.0,
                "price_pressure": -0.02,
            }
        },
        global_macro={},
        FOREX_PAARE_HISTORIE={},
        DEPOT_VERMOEGEN_HISTORIE=[],
        bargeld=0.0,
        forex_depot={},
        depot={},
        perpetuals={},
        NEWS_SPEICHER=[],
        simulation_phase_timings=[],
        bond_market=[],
        makro={
            "Ameron": {
                "bevoelkerung": 20_000_000.0,
                "bip_abs": 5_000.0,
                "bip_prozent": 0.01,
                "zins": 0.035,
                "inflation": 0.01,
                "arbeitslosigkeit": 0.06,
                "balance_sheet": 1234.0,
                "rating": "BBB",
                "trade_balance": 0.0,
                "import_dependency": 0.0,
                "export_strength": 0.0,
                "main_sector": "Technology",
                "main_bottleneck": "",
            }
        },
    )

    store.record_day(daten)
    daten.datum = datetime(1990, 1, 11)
    daten.makro["Ameron"]["bip_prozent"] = 0.02
    store.record_day(daten)
    daten.datum = datetime(1990, 1, 15)
    daten.makro["Ameron"]["bip_prozent"] = 0.03
    store.record_day(daten)

    assert store.country_current_rows()[0]["growth"] == 0.03
    assert store.country_current_rows()[0]["balance_sheet"] == 1234.0
    assert store.country_history("Ameron", "growth") == [0.03]
    assert store.product_history("SDIG", "produced") == [100.0, 100.0, 100.0]
    store.close()


def test_structured_simulation_current_tables_are_recorded(tmp_path) -> None:
    store = EconomicDataStore(tmp_path / "kojakstreet.duckdb")
    if not store.enabled:
        return
    daten = SimpleNamespace(
        datum=datetime(1990, 1, 15),
        aktien={
            "AAA": {
                "name": "Atlas Works",
                "land": "Ameron",
                "branche": "Technology",
                "rating": "BBB",
                "kurs": 120.0,
                "market_cap": 1_200_000_000.0,
                "revenue": 500_000_000.0,
                "free_cash_flow": 75_000_000.0,
                "production_capacity": 240.0,
                "capacity_utilization": 0.82,
                "production_score": 0.08,
                "input_availability": 0.94,
                "supply_chain_shortage": 0.03,
                "output_mix": {"SDIG": 0.7, "DATA": 0.3},
                "company_input_history": {"ELC": {"history": [(44.0, "15.01.1990", "")]}},
            }
        },
        rohstoffe={},
        kryptos={},
        fonds={
            "FND": {
                "underlyings": [
                    {"ticker": "AAA", "asset_type": "Stock", "weight": 0.75},
                    {"ticker": "GLD", "asset_type": "Commodity", "weight": 0.25},
                ]
            }
        },
        indizes={},
        processed_products={
            "SDIG": {
                "name": "Digital Services",
                "kategorie": "Technology",
                "supply": 100.0,
                "demand": 88.0,
                "inventories": 30.0,
                "shortage": 0.0,
                "price_pressure": -0.02,
            }
        },
        global_macro={},
        FOREX_PAARE_HISTORIE={},
        DEPOT_VERMOEGEN_HISTORIE=[],
        bargeld=0.0,
        forex_depot={},
        depot={},
        perpetuals={},
        NEWS_SPEICHER=[],
        simulation_phase_timings=[
            {"phase": "asset_market", "duration_ms": 12.5},
            {"phase": "production", "duration_ms": 4.25},
        ],
        bond_market=[],
        makro={
            "Ameron": {
                "bevoelkerung": 20_000_000.0,
                "bip_abs": 5_000.0,
                "bip_prozent": 0.01,
                "zins": 0.035,
                "inflation": 0.01,
                "arbeitslosigkeit": 0.06,
                "balance_sheet": 1234.0,
                "rating": "BBB",
                "regional_supply": {"SDIG": 100.0},
                "regional_demand": {"SDIG": 88.0},
                "exports": {"SDIG": 12.0},
                "imports": {"SDIG": 3.0},
                "regional_shortage": {"SDIG": 0.0},
                "regional_pressure": {"SDIG": -0.02},
                "trade_balance": 9.0,
                "import_dependency": 0.03,
                "export_strength": 0.14,
                "main_sector": "Technology",
                "main_bottleneck": "",
            }
        },
    )

    store.record_day(daten, current_scope="full")

    assert store.company_current_rows()[0]["ticker"] == "AAA"
    assert {row["role"] for row in store.company_output_current_rows()} == {"Produces", "Needs"}
    assert store.country_trade_current_rows()[0]["net"] == 9.0
    assert store.fund_allocation_current_rows()[0]["fund_ticker"] == "FND"
    assert store.phase_metric_current_rows()[0]["phase"] == "asset_market"
    health = store.architecture_health()
    assert health["structured_ready"] is True
    assert health["duckdb_truth_ready"] is True
    assert health["companies"] == 1
    repository = EconomyRepository(store)
    assert repository.companies()[0]["ticker"] == "AAA"
    assert repository.country_trade()[0]["code"] == "SDIG"
    store.close()


def test_event_log_classifies_news_rows(tmp_path) -> None:
    store = EconomicDataStore(tmp_path / "kojakstreet.duckdb")
    if not store.enabled:
        return
    daten = SimpleNamespace(
        datum=datetime(1990, 1, 15),
        aktien={},
        rohstoffe={},
        kryptos={},
        fonds={},
        indizes={},
        processed_products={"SDIG": {"name": "Digital Services", "supply": 1.0, "demand": 1.0}},
        global_macro={},
        FOREX_PAARE_HISTORIE={},
        DEPOT_VERMOEGEN_HISTORIE=[],
        bargeld=0.0,
        forex_depot={},
        depot={},
        perpetuals={},
        NEWS_SPEICHER=[
            ("15.01.1990", " IPO: ABC Atlas Works listed in Technology.", "GRUEN"),
            ("15.01.1990", " INSOLVENCY: OldCo defaulted.", "ROT"),
        ],
        simulation_phase_timings=[{"phase": "monthly_report", "duration_ms": 88.0}],
        bond_market=[],
        makro={
            "Ameron": {
                "bevoelkerung": 20_000_000.0,
                "bip_abs": 5_000.0,
                "bip_prozent": 0.01,
                "zins": 0.035,
                "inflation": 0.01,
                "arbeitslosigkeit": 0.06,
                "rating": "BBB",
                "trade_balance": 0.0,
                "import_dependency": 0.0,
                "export_strength": 0.0,
                "main_sector": "Technology",
                "main_bottleneck": "",
            }
        },
    )

    store.record_day(daten, current_scope="full")

    events = store.event_current_rows()
    assert {event["event_type"] for event in events} == {"new_company", "default"}
    assert {event["severity"] for event in events} == {"positive", "negative"}
    assert store.phase_metric_current_rows()[0]["duration_ms"] == 88.0
    store.close()
