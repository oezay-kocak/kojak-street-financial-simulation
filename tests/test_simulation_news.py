from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from kojakstreet.core.countries import COUNTRY_SYMBOLS
from kojakstreet.core.companies import ensure_company_universe
from kojakstreet.core.production_signals import emit_country_economy_news, emit_production_chain_news
from kojakstreet.core.simulation import DailySimulation


def test_production_chain_capacity_and_sector_momentum_emit_news() -> None:
    daten = SimpleNamespace(
        LAENDER=dict(COUNTRY_SYMBOLS),
        aktien={},
        NEWS_SPEICHER=[],
        datum=datetime(1990, 1, 15),
        spiel_pausiert=False,
    )
    ensure_company_universe(daten, reset=True)
    for asset in daten.aktien.values():
        if asset["branche"] == "Technologie":
            asset["capacity_growth"] = 0.035
            asset["capacity_utilization"] = 1.02
            asset["production_score"] = 0.08
        else:
            asset["capacity_growth"] = 0.0
            asset["capacity_utilization"] = 0.80
            asset["production_score"] = 0.0

    emit_production_chain_news(daten, lambda text, category: daten.NEWS_SPEICHER.insert(0, (daten.datum.strftime("%d.%m.%Y"), text, category)))

    news_text = "\n".join(item[1] for item in daten.NEWS_SPEICHER)
    assert "CAPACITY TREND: Technologie companies are expanding capacity" in news_text
    assert "SECTOR MOMENTUM: Technologie is running hot" in news_text


def test_news_feed_does_not_pause_simulation() -> None:
    daten = SimpleNamespace(
        NEWS_SPEICHER=[],
        datum=datetime(1990, 1, 15),
        spiel_pausiert=False,
    )
    simulation = DailySimulation(daten, SimpleNamespace(), SimpleNamespace(), SimpleNamespace())

    simulation.add_news("TEST NEWS", "WEISS")

    assert daten.NEWS_SPEICHER
    assert daten.spiel_pausiert is False


def test_daily_simulation_updates_production_chain_every_day() -> None:
    class ProductionStub:
        def __init__(self) -> None:
            self.daily_calls = 0

        def update_daily_production_chain(self) -> None:
            self.daily_calls += 1

    daten = SimpleNamespace(
        SPIEL_AKTIV=True,
        NEWS_SPEICHER=[],
        DEPOT_VERMOEGEN_HISTORIE=[],
        LAENDER={},
        aktives_event=None,
        datum=datetime(1990, 1, 2),
        spiel_pausiert=False,
        bargeld=1_000.0,
        forex_depot={},
        depot={},
        anleihen=[],
        perpetuals={},
        kredite={},
        aktien={},
        rohstoffe={},
        kryptos={},
        fonds={},
        makro={},
        bond_market=[],
    )
    production = ProductionStub()
    simulation = DailySimulation(
        daten,
        SimpleNamespace(update_global_liquidity=lambda: None),
        SimpleNamespace(update_daily_prices=lambda: None),
        SimpleNamespace(update_owned_bonds=lambda _add_news: None),
        production,
    )

    simulation.step_day()

    assert production.daily_calls == 1
    assert any(item["phase"] == "daily_production" for item in daten.simulation_phase_timings)


def test_country_trade_and_strength_news_are_summarized() -> None:
    daten = SimpleNamespace(
        NEWS_SPEICHER=[],
        datum=datetime(1990, 1, 15),
        spiel_pausiert=False,
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
    emit_country_economy_news(daten, lambda text, category: daten.NEWS_SPEICHER.insert(0, (daten.datum.strftime("%d.%m.%Y"), text, category)))

    bodies = [item[1] for item in daten.NEWS_SPEICHER]
    assert sum("COUNTRY STRENGTH SUMMARY" in body for body in bodies) == 1
    assert sum("TRADE FLOW SUMMARY" in body for body in bodies) == 1
    assert not any("COUNTRY STRENGTH:" in body for body in bodies)
    assert not any("TRADE FLOW:" in body for body in bodies)


def test_monthly_economic_report_is_due_on_15th_for_each_year() -> None:
    daten = SimpleNamespace(
        datum=datetime(1991, 1, 15),
        LETZTER_REPORT_MONAT=1,
    )
    simulation = DailySimulation(daten, SimpleNamespace(), SimpleNamespace(), SimpleNamespace())

    assert simulation._monthly_economic_report_due() is True

    daten.LETZTER_REPORT_MONAT = 199101

    assert simulation._monthly_economic_report_due() is False


def test_policy_decision_is_due_only_on_month_end() -> None:
    daten = SimpleNamespace(
        datum=datetime(1990, 2, 27),
        LETZTER_ZINS_TAG=None,
    )
    simulation = DailySimulation(daten, SimpleNamespace(), SimpleNamespace(), SimpleNamespace())

    assert simulation._policy_decision_due() is False

    daten.datum = datetime(1990, 2, 28)

    assert simulation._policy_decision_due() is True

    daten.LETZTER_ZINS_TAG = datetime(1990, 2, 28)

    assert simulation._policy_decision_due() is False
