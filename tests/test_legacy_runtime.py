from __future__ import annotations

import sys
import importlib
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime


def test_legacy_runtime_uses_integrated_core_without_tkinter_engine() -> None:
    for module_name in ["engine", "layout", "charts", "markt", "makro", "anleihen", "kredite"]:
        sys.modules.pop(module_name, None)

    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        assert runtime.daten.PYSIDE_RUNTIME is True
        assert runtime.snapshot().bond_market
        assert "engine" not in sys.modules
        assert "layout" not in sys.modules
        assert "charts" not in sys.modules
        assert "markt" not in sys.modules
        assert "makro" not in sys.modules
        assert "anleihen" not in sys.modules
        assert "kredite" not in sys.modules
    finally:
        runtime.close()


def test_legacy_runtime_steps_day_without_legacy_engine() -> None:
    for module_name in ["engine", "layout", "charts", "markt", "makro", "anleihen", "kredite"]:
        sys.modules.pop(module_name, None)
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        state = runtime.snapshot()
        ticker = next(iter(state.stocks))

        next_state = runtime.step_day()

        assert next_state.date > state.date
        assert len(next_state.stocks[ticker]["historie"]) >= len(state.stocks[ticker]["historie"])
        assert "production" in next_state.commodities["XAU"]
        assert "engine" not in sys.modules
        assert "layout" not in sys.modules
        assert "charts" not in sys.modules
        assert "markt" not in sys.modules
        assert "makro" not in sys.modules
        assert "anleihen" not in sys.modules
        assert "kredite" not in sys.modules
    finally:
        runtime.close()


def test_legacy_runtime_exposes_duckdb_current_state_tables() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        asset_quotes = runtime.asset_quote_rows()
        product_rows = runtime.product_current_rows()
        country_rows = runtime.country_current_rows()

        assert asset_quotes
        assert product_rows
        assert country_rows
        assert {"ticker", "asset_type", "price", "change", "market_cap", "region"} <= set(asset_quotes[0])
        assert {"code", "type", "produced", "demanded", "shortage", "pressure"} <= set(product_rows[0])
        assert {"region", "population", "growth", "inflation", "trade_balance"} <= set(country_rows[0])

        first_ticker = str(asset_quotes[0]["ticker"])
        runtime.advance_days(1, "status")
        next_quotes = {str(row["ticker"]): row for row in runtime.asset_quote_rows()}

        assert first_ticker in next_quotes
        assert isinstance(next_quotes[first_ticker]["price"], float)
    finally:
        runtime.close()


def test_legacy_runtime_exposes_runtime_context_delta_and_performance_snapshot() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        assert runtime.data_store.auto_flush is True
        assert runtime.context.legacy_data is runtime.daten
        assert runtime.context.repository is runtime.economy
        assert runtime.context.state is not None
        assert runtime.context.services is not None
        assert runtime.context.services.market is runtime.market
        assert runtime.context.services.trading is runtime.trading
        assert runtime.context.services.production is runtime.production
        assert runtime.context.state.assets.stocks is runtime.daten.aktien

        previous_version = runtime.current_version()
        runtime.advance_days(1, "status")
        delta = runtime.current_delta()
        performance = runtime.performance_snapshot()

        assert delta.version > previous_version
        assert delta.changed("asset_current")
        assert delta.changed("phase_metric_current")
        assert performance["current_version"] == delta.version
        assert "asset_market" in performance["phases"]
        assert float(performance["total_phase_ms"]) >= 0.0
    finally:
        runtime.close()


def test_market_engine_uses_explicit_runtime_state(monkeypatch) -> None:
    from kojakstreet.core import market_calculations

    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        monkeypatch.setattr(market_calculations, "daten", object())

        market_calculations.update_markt_kurse(runtime.daten)

        assert hasattr(runtime.daten, "market_runtime_assets")
        assert runtime.daten.market_runtime_assets["assets"]["stocks"]
    finally:
        runtime.close()


def test_runtime_exposes_portfolio_and_news_current_rows() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        assert runtime.portfolio_current_rows()
        assert isinstance(runtime.news_current_rows(), list)
        assert runtime.economy.portfolio()
        assert isinstance(runtime.economy.news(), list)
    finally:
        runtime.close()


def test_macro_engine_uses_explicit_runtime_state(monkeypatch) -> None:
    from kojakstreet.core import macro_calculations

    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    news_items = []
    add_news = lambda *item: news_items.append(item)
    try:
        monkeypatch.setattr(macro_calculations, "daten", object())

        macro_calculations.update_global_liquidity_index(runtime.daten)
        macro_calculations.fuehre_monatlichen_zinsentscheid_durch(add_news, runtime.daten)
        macro_calculations.update_makro_oekonomie(add_news, runtime.daten)
        macro_calculations.update_sovereign_ratings(runtime.daten)

        assert runtime.daten.GLI_HISTORIE
        assert runtime.daten.global_macro
        assert news_items
    finally:
        runtime.close()


def test_macro_report_histories_are_recorded_only_when_news_is_emitted() -> None:
    from kojakstreet.core import macro_calculations

    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    country = next(iter(runtime.daten.LAENDER))
    runtime.daten.datum = runtime.daten.datum + timedelta(days=40)
    gdp_key = f"{country}_BIP"
    inflation_key = f"{country}_INF"
    unemployment_key = f"{country}_ALO"
    rate_key = f"{country}_ZINS"
    before = {
        key: len(runtime.daten.MAKRO_HISTORIE[key])
        for key in (gdp_key, inflation_key, unemployment_key, rate_key)
    }
    try:
        macro_calculations.update_makro_oekonomie(None, runtime.daten)
        macro_calculations.fuehre_monatlichen_zinsentscheid_durch(None, runtime.daten)

        assert {key: len(runtime.daten.MAKRO_HISTORIE[key]) for key in before} == before

        macro_calculations.update_makro_oekonomie(lambda *_item: None, runtime.daten)
        macro_calculations.fuehre_monatlichen_zinsentscheid_durch(lambda *_item: None, runtime.daten)

        assert len(runtime.daten.MAKRO_HISTORIE[gdp_key]) == before[gdp_key] + 1
        assert len(runtime.daten.MAKRO_HISTORIE[inflation_key]) == before[inflation_key] + 1
        assert len(runtime.daten.MAKRO_HISTORIE[unemployment_key]) == before[unemployment_key] + 1
        assert len(runtime.daten.MAKRO_HISTORIE[rate_key]) == before[rate_key] + 1
    finally:
        runtime.close()


def test_runtime_country_history_uses_published_macro_history_not_daily_store() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    region = next(iter(runtime.daten.LAENDER))
    try:
        runtime.daten.datum = runtime.daten.datum.replace(day=20)
        runtime.daten.MAKRO_HISTORIE[f"{region}_INF"] = [(0.011, "01.01.1990", "")]
        for _ in range(5):
            runtime.advance_day()

        assert runtime.country_history(region, "inflation") == [0.011]
    finally:
        runtime.close()


def test_fresh_runtime_asset_charts_start_without_history_points() -> None:
    import daten

    importlib.reload(daten)
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        stock_ticker = next(iter(runtime.daten.aktien))
        commodity_ticker = next(iter(runtime.daten.rohstoffe))
        crypto_ticker = next(iter(runtime.daten.kryptos))
        fund_ticker = next(iter(runtime.daten.fonds))
        index_ticker = next(iter(runtime.daten.indizes))

        assert runtime.asset_history("Stock", stock_ticker) == []
        assert runtime.asset_history("Commodity", commodity_ticker) == []
        assert runtime.asset_history("Crypto", crypto_ticker) == []
        assert runtime.asset_history("Fund", fund_ticker) == []
        assert runtime.asset_history("Index", index_ticker) == []
    finally:
        runtime.close()


def test_bond_portfolio_engine_uses_explicit_runtime_state(monkeypatch) -> None:
    from kojakstreet.core import bond_calculations

    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    old_bonds = deepcopy(runtime.daten.anleihen)
    old_forex = deepcopy(runtime.daten.forex_depot)
    old_realized = deepcopy(runtime.daten.realisierte_guv_historie)
    old_bond_count = len(old_bonds)
    try:
        runtime.daten.anleihen.append(
            {
                "typ": "STAAT",
                "land": "GD",
                "nominal": 1000.0,
                "zins": 0.04,
                "resttage": 1,
                "zinstage_zaehler": 0,
            }
        )
        monkeypatch.setattr(bond_calculations, "daten", object())

        bond_calculations.update_laufende_anleihen(lambda *_args: None, runtime.daten)

        assert len(runtime.daten.anleihen) == old_bond_count
        assert runtime.daten.forex_depot["GD"] >= 1000.0
    finally:
        runtime.daten.anleihen = old_bonds
        runtime.daten.forex_depot = old_forex
        runtime.daten.realisierte_guv_historie = old_realized
        runtime.close()
