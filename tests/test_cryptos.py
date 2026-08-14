from __future__ import annotations

from types import SimpleNamespace

from kojakstreet.core.cryptos import (
    CRYPTO_TASK_TYPES,
    TARGET_CRYPTO_COUNT,
    crypto_price_signal,
    ensure_crypto_fundamentals,
    ensure_crypto_universe,
    shutdown_and_replace_crypto_chains,
    update_crypto_economy,
    update_crypto_fundamentals,
)


def test_crypto_fundamentals_initialize_chain_metrics() -> None:
    asset = {"kurs": 100.0, "gebühren": 50_000.0}

    ensure_crypto_fundamentals(asset)

    assert asset["transactions"] > 0
    assert asset["chain_fees"] > 0
    assert asset["circulating_supply"] > 0
    assert asset["active_wallets"] > 0
    assert asset["open_interest"] > 0
    assert asset["open_interest"] == asset["long_interest"] + asset["short_interest"]


def test_crypto_fundamentals_keep_previous_month_comparisons() -> None:
    asset = {"kurs": 100.0, "gebühren": 50_000.0, "netzwerk_aktivitaet": 1.0, "netzwerk_fees": 1.0}
    ensure_crypto_fundamentals(asset)

    update_crypto_fundamentals(asset, macro_growth=0.03, world_rate=0.02, event_result=0.10)

    assert asset["previous_transactions"] == 100_000.0
    assert asset["previous_active_wallets"] == 50_000.0
    assert asset["transactions"] != 100_000.0
    assert asset["active_wallets"] != 50_000.0


def test_crypto_task_fundamentals_track_previous_values_and_changes() -> None:
    asset = {
        "kurs": 100.0,
        "task_type": "PAY",
        "tps": 900.0,
        "confirmation_time": 3.0,
        "merchant_adoption": 0.20,
        "network_capacity": 600.0,
        "network_utilization": 0.9,
        "demand_change": 0.05,
    }
    ensure_crypto_fundamentals(asset)

    update_crypto_fundamentals(asset, macro_growth=0.03, world_rate=0.02, event_result=0.10)

    assert asset["previous_tps"] == 900.0
    assert asset["previous_confirmation_time"] == 3.0
    assert asset["previous_merchant_adoption"] == 0.20
    assert "circulating_supply_change" in asset
    assert asset["tps_change"] != 0.0
    assert asset["confirmation_time_change"] != 0.0
    assert "merchant_adoption_change" in asset


def test_store_of_value_supply_is_fixed() -> None:
    asset = {"kurs": 100.0, "task_type": "STORE", "circulating_supply": 17_500_000.0}
    ensure_crypto_fundamentals(asset)

    update_crypto_fundamentals(asset, macro_growth=0.03, world_rate=0.02, event_result=0.10)

    assert asset["circulating_supply"] == 17_500_000.0
    assert asset["circulating_supply_change"] == 0.0


def test_crypto_price_signal_rewards_usage_and_deflation() -> None:
    asset = {
        "transaction_change": 0.05,
        "fee_change": 0.04,
        "inflation_rate": -0.01,
        "wallet_change": 0.03,
    }

    assert crypto_price_signal(asset) > 0


def test_crypto_price_signal_is_not_capped() -> None:
    asset = {
        "transaction_change": 0.25,
        "fee_change": 0.20,
        "inflation_rate": -0.05,
        "wallet_change": 0.18,
    }

    assert crypto_price_signal(asset) > 0.14


def test_crypto_universe_generates_task_based_chains() -> None:
    daten = _minimal_daten()

    ensure_crypto_universe(daten, reset=True)

    assert len(daten.kryptos) == TARGET_CRYPTO_COUNT
    assert {asset["task_type"] for asset in daten.kryptos.values()} == set(CRYPTO_TASK_TYPES)
    assert all(ticker.isupper() and 3 <= len(ticker) <= 5 for ticker in daten.kryptos)
    assert all("Bitcoin" not in asset["name"] and "Ethereum" not in asset["name"] for asset in daten.kryptos.values())


def test_crypto_economy_assigns_demand_and_market_share() -> None:
    daten = _minimal_daten()
    ensure_crypto_universe(daten, reset=True)

    update_crypto_economy(daten)

    assert all(asset["demand"] > 0 for asset in daten.kryptos.values())
    assert all(0 < asset["market_share"] < 1 for asset in daten.kryptos.values())
    assert all("network_utilization" in asset for asset in daten.kryptos.values())
    assert all("market_share_change" in asset for asset in daten.kryptos.values())
    assert all("network_utilization_change" in asset for asset in daten.kryptos.values())


def test_weak_crypto_chain_shuts_down_and_is_replaced() -> None:
    daten = _minimal_daten()
    ensure_crypto_universe(daten, reset=True)
    ticker = next(iter(daten.kryptos))
    name = daten.kryptos[ticker]["name"]
    daten.kryptos[ticker]["kurs"] = 0.5
    daten.kryptos[ticker]["market_share"] = 0.0001
    daten.kryptos[ticker]["demand_change"] = -0.5
    daten.kryptos[ticker]["historie"] = [(1.0, "date", "") for _ in range(100)]
    daten.depot[ticker] = {"stueck": 1.0, "kaufkurs": 10.0}
    daten.perpetuals[f"{ticker}_LONG"] = {"ticker": ticker}

    removed = shutdown_and_replace_crypto_chains(daten)

    assert removed == [(ticker, name)]
    assert ticker not in daten.kryptos
    assert ticker not in daten.depot
    assert f"{ticker}_LONG" not in daten.perpetuals
    assert len(daten.kryptos) == TARGET_CRYPTO_COUNT


def _minimal_daten() -> SimpleNamespace:
    return SimpleNamespace(
        kryptos={},
        aktien={
            "AAA": {"branche": "Technologie", "market_cap": 1000.0},
            "BBB": {"branche": "Finanzen", "market_cap": 800.0},
            "CCC": {"branche": "Stromerzeuger", "market_cap": 600.0},
            "DDD": {"branche": "Einzelhandel", "market_cap": 400.0},
        },
        makro={"Ameron": {"inflation": 0.02, "bip_prozent": 0.03}},
        gli_index=15420.0,
        depot={},
        perpetuals={},
    )
