from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime


def test_seeded_30_day_simulation_preserves_core_mechanics() -> None:
    signature = _seeded_30_day_signature()

    assert signature["date"] == "1990-01-31"
    assert signature["cash"] == pytest.approx(25_000.0)
    assert signature["history_count"] == 31
    assert int(signature["news_count"]) >= 1
    assert all(price > 0.0 for price in signature["stocks"])
    assert all(price > 0.0 for price in signature["commodities"])
    assert all(price > 0.0 for price in signature["cryptos"])
    assert any(abs(balance) > 1.0 for balance in signature["trade_balances"])
    assert all(value > 0.0 for value in signature["product_demand"])
    assert all(value > 0.0 for value in signature["product_supply"])


def _seeded_30_day_signature() -> dict[str, object]:
    random_state = random.getstate()
    numpy_state = np.random.get_state()
    random.seed(1729)
    np.random.seed(1729)
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        for _ in range(30):
            runtime.advance_day()

        daten = runtime.daten

        signature = {
            "date": daten.datum.strftime("%Y-%m-%d"),
            "cash": round(daten.forex_depot.get("GD", 0.0) + daten.bargeld, 4),
            "history_count": len(daten.DEPOT_VERMOEGEN_HISTORIE),
            "news_count": len(daten.NEWS_SPEICHER),
            "stocks": _sample_asset_prices(daten.aktien, 5),
            "commodities": _asset_prices(daten.rohstoffe, ["XAU", "CL", "TTF"]),
            "cryptos": _sample_asset_prices(daten.kryptos, 3),
            "trade_balances": [round(daten.makro[country]["trade_balance"], 4) for country in ("Ameron", "Albionia", "Ardonia")],
            "product_demand": [round(daten.processed_products[code]["demand"], 4) for code in ("ELC", "FUEL", "HEAT", "STL", "ALU")],
            "product_supply": [round(daten.processed_products[code]["supply"], 4) for code in ("ELC", "FUEL", "HEAT", "STL", "ALU")],
        }
        return signature
    finally:
        runtime.close()
        random.setstate(random_state)
        np.random.set_state(numpy_state)


def _asset_prices(assets: dict[str, dict], tickers: list[str]) -> list[float]:
    return [round(float(assets[ticker]["kurs"]), 4) for ticker in tickers]


def _sample_asset_prices(assets: dict[str, dict], count: int) -> list[float]:
    return _asset_prices(assets, sorted(assets)[:count])
