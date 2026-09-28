from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.company_lifecycle import (
    company_regional_factor,
    sector_energy_factor,
    update_company_lifecycle,
    update_monthly_companies,
)


def test_monthly_company_engine_updates_explicit_runtime_state() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        ticker, asset = next(iter(runtime.daten.aktien.items()))
        previous_eps = float(asset.get("eps", 0.0))

        update_monthly_companies(runtime.daten)

        assert runtime.daten.aktien[ticker] is asset
        assert "news_momentum" in asset
        assert float(asset.get("eps", 0.0)) != previous_eps or "free_cash_flow" in asset
        assert asset.get("_psychology_ready") is True
    finally:
        runtime.close()


def test_company_lifecycle_replaces_bankrupt_companies() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    old_stocks = deepcopy(runtime.daten.aktien)
    news_items = []
    try:
        ticker = next(iter(runtime.daten.aktien))
        runtime.daten.aktien[ticker]["cash_reserves"] = 0.0
        runtime.daten.aktien[ticker]["debt_to_market_cap"] = 1.5
        runtime.daten.aktien[ticker]["rating"] = "CC"
        runtime.daten.aktien[ticker]["free_cash_flow"] = -10_000_000.0
        runtime.daten.aktien[ticker]["distress_months"] = 9

        update_company_lifecycle(runtime.daten, lambda *item: news_items.append(item))

        assert ticker not in runtime.daten.aktien
        assert len(runtime.daten.aktien) >= len(old_stocks)
        assert news_items
    finally:
        runtime.daten.aktien = old_stocks
        runtime.close()


def test_company_factor_helpers_are_state_based() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        asset = next(iter(runtime.daten.aktien.values()))
        assert 0.78 <= company_regional_factor(runtime.daten, asset) <= 1.18
        assert sector_energy_factor(str(asset.get("branche", "")), 1.0, 1.0) > 0.0
    finally:
        runtime.close()
