"""Country ALL completeness through generation, persistence and colliding UI symbols."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.companies import BRANCHEN
from kojakstreet.core.countries import COUNTRIES
from kojakstreet.core.indices import COMPOSITE_TICKERS, ensure_index_universe
from kojakstreet.core.market_calculations import _update_indices_from_runtime_cache
from kojakstreet.core.market_data_service import MarketDataService
from kojakstreet.core.state import GameState
from kojakstreet.live_process import LiveSimulationProcess
from kojakstreet.ui_qt.views.markets_view import MarketsView

ROOT = Path(__file__).resolve().parents[1]


def assert_complete(data):
    assert len(data.indizes) == 20 * (len(BRANCHEN) + 1)
    for country in COUNTRIES:
        indices = {t: a for t, a in data.indizes.items() if a["land"] == country.name}
        broad = {t: a for t, a in indices.items() if a["branche"] == "All Sectors"}
        assert list(broad) == [COMPOSITE_TICKERS[country.name]]
        stocks = {t: a for t, a in data.aktien.items() if a["land"] == country.name}
        index = next(iter(broad.values()))
        assert set(index["constituents"]) == set(stocks)
        assert index["constituent_count"] == len(stocks)
        assert index["market_cap"] == pytest.approx(sum(a["market_cap"] for a in stocks.values()))
        assert sum(index["constituents"].values()) == pytest.approx(1.0)
        assert {a["branche"] for a in indices.values() if a["index_type"] == "Sector"} == set(BRANCHEN)


@pytest.mark.parametrize("seed", [7, 42, 2307])
def test_fresh_genesis_all_indices_exist_and_reach_market_table(tmp_path, seed):
    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path / "data", seed=seed)
    try:
        assert_complete(runtime.daten)
        view = MarketsView(runtime.snapshot_for_view("markets"))
        for country in COUNTRIES:
            view.proxy_model.set_filters("", "Index", country.name, "All Groups")
            assert view.proxy_model.rowCount() == 17
            rows = [view.model.rows[view.proxy_model.mapToSource(view.proxy_model.index(i, 0)).row()]
                    for i in range(17)]
            assert len({r["ticker"] for r in rows}) == 17
            assert sum(r["data"]["branche"] == "All Sectors" for r in rows) == 1
            assert all(r["data"]["land"] == country.name for r in rows)
    finally:
        runtime.close()


def test_indices_save_load_and_daily_formula_preserved(tmp_path):
    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path / "data", seed=2307)
    try:
        initial = deepcopy(runtime.daten.indizes)
        expected_levels = {}
        runtime.advance_day()
        for ticker, index in initial.items():
            components = [a for a in runtime.daten.aktien.values()
                          if a["land"] == index["land"]
                          and (index["branche"] == "All Sectors" or a["branche"] == index["branche"])]
            current = sum(a["kurs"] * a["aktien_anzahl"] for a in components)
            previous = sum(a["kurs"] / (1 + a["aenderung"] / 100) * a["aktien_anzahl"] for a in components)
            expected_levels[ticker] = max(1.0, index["kurs"] * current / previous)
        assert_complete(runtime.daten)
        assert {t: a["kurs"] for t, a in runtime.daten.indizes.items()} == pytest.approx(expected_levels)
        expected = deepcopy(runtime.daten.indizes)
        runtime.save_game()
        runtime.advance_day()
        runtime.load_game()
        assert runtime.daten.indizes == expected
        assert_complete(runtime.daten)
        persisted = runtime.data_store.asset_quote_rows()
        assert {r["ticker"] for r in persisted if r["asset_type"] == "Index"} == set(expected)
    finally:
        runtime.close()


def test_sparse_universe_keeps_exact_all_semantics_and_sector_rules():
    stock = {"land": "Ameron", "branche": "Technologie", "kurs": 11.,
             "aenderung": 10., "aktien_anzahl": 10., "market_cap": 110.}
    data = SimpleNamespace(aktien={"AMX": stock}, indizes={})
    ensure_index_universe(data)
    assert data.indizes["AMX"]["constituents"] == {"AMX": 1.0}
    assert data.indizes["AMX-TECH"]["constituents"] == {"AMX": 1.0}
    assert data.indizes["AMX-AUTO"]["constituent_count"] == 0
    assert data.indizes["ABX"]["constituent_count"] == 0
    _update_indices_from_runtime_cache(data, "02.01.1990")
    assert data.indizes["AMX"]["kurs"] == 1100.
    assert data.indizes["AMX-TECH"]["kurs"] == 1100.
    assert data.indizes["AMX-AUTO"]["kurs"] == 1000.
    assert data.indizes["ABX"]["kurs"] == 1000.


def test_live_worker_keeps_colliding_indices_after_hidden_days(tmp_path):
    bootstrap = IntegratedRuntime(ROOT, data_dir=tmp_path, seed=2307)
    process = LiveSimulationProcess.from_runtime(bootstrap, timeout_seconds=90)
    try:
        for country in COUNTRIES:
            ticker = COMPOSITE_TICKERS[country.name]
            assert sum(r["ticker"] == ticker and r["asset_type"] == "Index"
                       for r in process.asset_quote_rows()) == 1
        process.snapshot_for_view("global_macro")
        process.advance_days(2)
        assert not process.state.indices
        process.snapshot_for_view("markets")
        authoritative = process.snapshot()
        for row in process.asset_quote_rows():
            if row["asset_type"] == "Index":
                assert row["price"] == authoritative.indices[row["ticker"]]["kurs"]
        assert sum(r["asset_type"] == "Index" for r in process.asset_quote_rows()) == 340
        for ticker in ("RMX", "SLX", "NMX", "HNX", "KRX"):
            assert any(r["ticker"] == ticker and r["asset_type"] == "Stock"
                       for r in process.asset_quote_rows())
    finally:
        process.close()


@pytest.mark.parametrize("kind", ["Index", "Stock"])
def test_colliding_symbol_selection_live_refresh_and_detail_keep_identity(kind):
    # Production simulation dates intentionally have no timezone.
    state = GameState(datetime(1990, 1, 1), 25_000., "GD",  # noqa: DTZ001
                      stocks={"AMX": {"name": "Same ticker stock", "kurs": 10., "land": "Ameron"}},
                      indices={"AMX": {"name": "Ameron Composite", "kurs": 1000., "land": "Ameron",
                                       "branche": "All Sectors", "historie": [(1000., "01.01.1990", "")]}})
    view = MarketsView(state)
    source = view.model.index(view.model.row_for_asset("AMX", kind), 0)
    view.market_table.setCurrentIndex(view.proxy_model.mapFromSource(source))
    assert view.chart_panel.current_asset[:2] == ("AMX", kind)
    updated = deepcopy(state)
    updated.date += timedelta(days=1)
    updated.indices["AMX"]["kurs"] = 1015.
    updated.stocks["AMX"]["kurs"] = 11.
    view.refresh(updated)
    assert view._selected_row_asset_type() == kind
    assert view.chart_panel.current_asset[:2] == ("AMX", kind)
    quotes = [{"ticker": q.ticker, "asset_type": q.asset_type, "price": q.price,
               "change": q.change, "market_cap": q.market_cap, "region": q.region}
              for q in MarketDataService(updated).quotes()]
    view.apply_live_quotes(quotes, current_state=updated)
    assert view.chart_panel.current_price == (1015. if kind == "Index" else 11.)
    view._open_asset_detail(view.market_table.currentIndex())
    assert view.stock_detail_view.asset_type == kind
    view._refresh_detail_history()
    assert view.stock_detail_view.asset_type == kind
    view.apply_live_quotes(quotes, current_state=updated)
    assert view.stock_detail_view.asset_type == kind
