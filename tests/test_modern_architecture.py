from __future__ import annotations

from pathlib import Path

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.data_store_schema import CURRENT_TABLE_SOURCES, MIGRATION_COLUMNS
from kojakstreet.core.production_indexes import company_runtimes


def test_runtime_uses_reusable_production_company_indexes() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        first = company_runtimes(runtime.daten)
        second = company_runtimes(runtime.daten)

        assert first is second
        assert len(first) == len(runtime.daten.aktien)
        assert first[0].asset is next(iter(runtime.daten.aktien.values()))
    finally:
        runtime.close()


def test_store_schema_declares_current_tables_and_migrations() -> None:
    assert CURRENT_TABLE_SOURCES["asset_current"] == "asset_daily"
    assert CURRENT_TABLE_SOURCES["country_trade_current"] == "country_trade_daily"
    assert ("duration", "DOUBLE") in MIGRATION_COLUMNS["bond_daily"]
    assert ("balance_sheet", "DOUBLE") in MIGRATION_COLUMNS["country_current"]


def test_repository_exposes_lookup_helpers() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        repository = runtime.economy_repository()

        assets = repository.asset_by_ticker()
        products = repository.product_by_code()
        countries = repository.country_by_region()

        assert assets
        assert products
        assert countries
        assert next(iter(runtime.daten.aktien)) in assets
        assert "ELC" in products
        assert "Ameron" in countries
        assert repository.portfolio_summary()
    finally:
        runtime.close()
