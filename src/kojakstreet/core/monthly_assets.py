"""Monthly commodity and crypto asset engines."""

from __future__ import annotations

import random
from collections.abc import Callable
from types import ModuleType

from kojakstreet.core.commodities import update_commodity_fundamentals
from kojakstreet.core.cryptos import shutdown_and_replace_crypto_chains, update_crypto_economy, update_crypto_fundamentals
from kojakstreet.core.ohlc import normalize_commodity_supply_key
from kojakstreet.core.psychology import update_asset_expectations

NewsCallback = Callable[[str, str], None]


def update_monthly_commodities(daten: ModuleType, macro_growth: float) -> None:
    for asset in daten.rohstoffe.values():
        result = random.uniform(-0.12, 0.15)
        if daten.aktives_event and daten.aktives_event["typ"] in ["ENERGIE", "BILATERAL"]:
            result -= 0.40
        asset["news_momentum"] = result
        update_commodity_fundamentals(
            asset,
            macro_growth=macro_growth,
            price_change=float(asset.get("aenderung", 0.0)),
            event_result=result,
        )
        update_asset_expectations(asset, "Commodity")
        current_supply = normalize_commodity_supply_key(asset)
        asset["foerder_menge"] = max(
            -3.0,
            min(3.0, current_supply * 0.70 + (result * 15.0) * 0.30),
        )


def update_monthly_crypto(daten: ModuleType, macro_growth: float, world_rate: float) -> None:
    for ticker, asset in list(daten.kryptos.items()):
        result = random.uniform(-0.25, 0.30)
        asset["netzwerk_aktivitaet"] = max(
            -3.0,
            min(3.0, asset.get("netzwerk_aktivitaet", 0.0) * 0.75 + (result * 8.0) * 0.25),
        )
        asset["netzwerk_fees"] = max(
            -3.0,
            min(3.0, asset["netzwerk_aktivitaet"] * 1.1 + random.uniform(-0.4, 0.4)),
        )
        asset["gebuehren"] = max(
            500.0,
            50000.0 * ((asset["netzwerk_aktivitaet"] + 4.0) / 4.0) * (asset["kurs"] / 100.0),
        )
        update_crypto_fundamentals(
            asset,
            macro_growth=macro_growth,
            world_rate=world_rate,
            event_result=result,
        )
        update_asset_expectations(asset, "Crypto")
        if ticker in daten.depot:
            daten.forex_depot["GD"] = daten.forex_depot.get("GD", 0.0) + (
                (asset.get("gebuehren", asset.get("chain_fees", 0.0)) / 1_000_000.0)
                * daten.depot[ticker]["stueck"]
                * random.uniform(0.01, 0.03)
            )


def update_crypto_production_inputs(daten: ModuleType) -> None:
    update_crypto_economy(daten)


def update_crypto_lifecycle(daten: ModuleType, add_news_callback: NewsCallback) -> None:
    removed_chains = shutdown_and_replace_crypto_chains(daten)
    if not removed_chains:
        return
    names = ", ".join(name for _ticker, name in removed_chains[:4])
    add_news_callback(
        f"CRYPTO SHUTDOWN: {names} lost network demand and were switched off. New chains are entering the market.",
        "ROT",
    )
