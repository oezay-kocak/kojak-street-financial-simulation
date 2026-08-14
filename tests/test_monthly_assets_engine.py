from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.monthly_assets import (
    update_crypto_lifecycle,
    update_crypto_production_inputs,
    update_monthly_commodities,
    update_monthly_crypto,
)


def test_monthly_commodity_engine_updates_explicit_runtime_state() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        asset = runtime.daten.rohstoffe["XAU"]

        update_monthly_commodities(runtime.daten, 0.02)

        assert "production_change" in asset
        assert "demand_change" in asset
        assert asset.get("_psychology_ready") is True
    finally:
        runtime.close()


def test_monthly_crypto_engine_updates_explicit_runtime_state() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        ticker, asset = next(iter(runtime.daten.kryptos.items()))
        runtime.daten.depot[ticker] = {"stueck": 2.0, "kaufkurs": float(asset["kurs"])}

        update_monthly_crypto(runtime.daten, 0.02, 0.035)

        assert "transaction_change" in asset
        assert "netzwerk_aktivitaet" in asset
        assert runtime.daten.forex_depot["GD"] >= 0.0
    finally:
        runtime.close()


def test_crypto_production_and_lifecycle_engines_use_runtime_state() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    old_cryptos = deepcopy(runtime.daten.kryptos)
    news_items = []
    try:
        ticker = next(iter(runtime.daten.kryptos))
        runtime.daten.kryptos[ticker]["kurs"] = 0.5
        runtime.daten.kryptos[ticker]["market_share"] = 0.0001
        runtime.daten.kryptos[ticker]["demand_change"] = -0.5
        runtime.daten.kryptos[ticker]["historie"] = [(1.0, "date", "") for _ in range(100)]

        update_crypto_production_inputs(runtime.daten)
        update_crypto_lifecycle(runtime.daten, lambda *item: news_items.append(item))

        assert ticker not in runtime.daten.kryptos
        assert news_items
    finally:
        runtime.daten.kryptos = old_cryptos
        runtime.close()
