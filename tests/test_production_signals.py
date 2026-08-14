from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from kojakstreet.core.companies import ensure_company_universe
from kojakstreet.core.countries import COUNTRY_SYMBOLS
from kojakstreet.core.production_signals import (
    emit_country_economy_news,
    emit_production_chain_news,
    fastest_expanding_sector,
    sector_production_stats,
    strongest_sector,
)


def test_production_signal_helpers_identify_sector_momentum() -> None:
    daten = SimpleNamespace(LAENDER=dict(COUNTRY_SYMBOLS), aktien={}, datum=datetime(1990, 1, 15))
    ensure_company_universe(daten, reset=True)
    for asset in daten.aktien.values():
        asset["capacity_growth"] = 0.035 if asset["branche"] == "Technologie" else 0.0
        asset["capacity_utilization"] = 1.02 if asset["branche"] == "Technologie" else 0.80
        asset["production_score"] = 0.08 if asset["branche"] == "Technologie" else 0.0

    stats = sector_production_stats(daten)

    assert fastest_expanding_sector(stats)[0] == "Technologie"
    assert strongest_sector(stats)[0] == "Technologie"


def test_production_chain_news_uses_explicit_runtime_state() -> None:
    daten = SimpleNamespace(
        LAENDER=dict(COUNTRY_SYMBOLS),
        aktien={},
        makro={},
        NEWS_SPEICHER=[],
        datum=datetime(1990, 1, 15),
    )
    ensure_company_universe(daten, reset=True)
    for asset in daten.aktien.values():
        asset["capacity_growth"] = 0.035 if asset["branche"] == "Technologie" else 0.0
        asset["capacity_utilization"] = 1.02 if asset["branche"] == "Technologie" else 0.80
        asset["production_score"] = 0.08 if asset["branche"] == "Technologie" else 0.0

    emit_production_chain_news(daten, lambda text, category: daten.NEWS_SPEICHER.append(("date", text, category)))

    news_text = "\n".join(item[1] for item in daten.NEWS_SPEICHER)
    assert "CAPACITY TREND: Technologie companies are expanding capacity" in news_text
    assert "SECTOR MOMENTUM: Technologie is running hot" in news_text


def test_country_economy_news_uses_explicit_runtime_state() -> None:
    daten = SimpleNamespace(
        makro={
            f"Country{i}": {
                "import_dependency": 0.10,
                "export_strength": 0.35 + i * 0.01,
                "main_sector": "Technology",
                "main_bottleneck": "",
                "trade_partners": {f"Partner{i}": 100.0 + i},
            }
            for i in range(8)
        },
    )
    news_items = []

    emit_country_economy_news(daten, lambda *item: news_items.append(item))

    bodies = [item[0] for item in news_items]
    assert sum("COUNTRY STRENGTH SUMMARY" in body for body in bodies) == 1
    assert sum("TRADE FLOW SUMMARY" in body for body in bodies) == 1
