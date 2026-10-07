"""Real navigation after hidden days, with authoritative full debug controls."""

import json
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.live_process import LiveSimulationProcess
from kojakstreet.ui_qt.app import KojakStreetWindow
from kojakstreet.visible_state import _allocations


def wait(app, window):
    deadline = time.perf_counter() + 90
    while (
        window.simulation_busy or window._live_update_pending
    ) and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.002)
    assert not window.simulation_busy and not window._live_update_pending
    app.processEvents()


def test_hidden_entities_open_current_and_visible_tabs_survive_ticks_and_load(tmp_path):
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    bootstrap = IntegratedRuntime(root, data_dir=tmp_path, seed=1729)
    process = LiveSimulationProcess.from_runtime(bootstrap, timeout_seconds=90)
    window = KojakStreetWindow(process.state, process)
    timings = []
    try:
        company = list(process.state.stocks)[900]
        window.set_active_view("global_macro")
        window._request_simulation_steps(35, force_refresh=False)
        wait(app, window)
        assert not process.state.stocks and len(process._snapshots) == 1
        authoritative = process.snapshot()  # explicit full debug read; never retained
        assert not process.state.stocks

        def timed(label, action):
            start = time.perf_counter()
            action()
            app.processEvents()
            timings.append({"label": label, "ms": (time.perf_counter() - start) * 1000})

        timed("Markets return after 35 hidden days", lambda: window.set_active_view("markets"))
        markets = window.markets_view
        assert "revenue" not in process.state.stocks[company]
        timed("company 900 chart", lambda: markets._select_ticker(company))
        timed(
            "company 900 detail",
            lambda: markets._open_asset_detail(markets.market_table.currentIndex()),
        )
        detail = markets.stock_detail_view
        timed(
            "company 900 Fundamentals",
            lambda: detail.detail_tabs.setCurrentWidget(detail.overview_tab),
        )
        assert detail.data["revenue"] == authoritative.stocks[company]["revenue"]
        assert detail.data["free_cash_flow"] == authoritative.stocks[company]["free_cash_flow"]
        assert "company_output_history" not in detail.data
        timed("company 900 Supply", lambda: detail.detail_tabs.setCurrentWidget(detail.supply_tab))
        assert detail.data["output_mix"] == authoritative.stocks[company]["output_mix"]
        assert detail.supply_model.rowCount() > 0
        for row in range(detail.supply_model.rowCount()):
            meta = detail.supply_model.metadata_at(row)
            product = authoritative.commodities.get(
                meta["code"]
            ) or authoritative.processed_products.get(meta["code"], {})
            assert meta["supply"] == float(product.get("supply", product.get("production", 0.0)))
        window._on_timer_tick()
        wait(app, window)
        current = process.snapshot()
        assert detail.data["production_capacity"] == current.stocks[company]["production_capacity"]
        # Ranking changes enter offscreen; every retained identity must still
        # show the exact current quote, including assets leaving the ranking.
        quotes = {
            (item["asset_type"], item["ticker"]): item for item in process.ticker_tape_quotes()
        }
        tape_items = window.top_bar.ticker_tape.items
        assert len(tape_items) == sum(
            item.get("ranked", True) for item in process.ticker_tape_quotes()
        )
        for item in tape_items:
            quote = quotes[(item["asset_type"], item["ticker"])]
            assert item["price"] == quote["price"]
            assert item["change"] == quote["change"]

        for kind, book in (
            ("Fund", "funds"),
            ("Derivative", "derivatives"),
            ("Commodity", "commodities"),
            ("Crypto", "cryptos"),
            ("Index", "indices"),
        ):
            markets._show_market_list()
            ticker = list(getattr(current, book))[min(82, len(getattr(current, book)) - 1)]
            timed(kind + " select", lambda ticker=ticker: markets._select_ticker(ticker))
            timed(
                kind + " detail",
                lambda: markets._open_asset_detail(markets.market_table.currentIndex()),
            )
            assert detail.header_price.text() != "-"
            assert detail.data["kurs"] == getattr(current, book)[ticker]["kurs"]
            if kind == "Derivative":
                assert detail.data.get("contract_size") == current.derivatives[ticker].get(
                    "contract_size"
                )
            if kind == "Fund":
                timed(
                    "Fund overview",
                    lambda: detail.detail_tabs.setCurrentWidget(detail.overview_tab),
                )
                assert detail.data["aum"] == current.funds[ticker]["aum"]
                assert "underlyings" not in detail.data
                timed(
                    "Fund allocations",
                    lambda: detail.detail_tabs.setCurrentWidget(detail.supply_tab),
                )
                from types import SimpleNamespace

                daten = SimpleNamespace(
                    aktien=current.stocks,
                    indizes=current.indices,
                    rohstoffe=current.commodities,
                    kryptos=current.cryptos,
                    bond_market=current.bond_market,
                )
                assert detail._fund_allocation_rows() == _allocations(daten, current.funds[ticker])

        timed("Country view", lambda: window.set_active_view("macro"))
        macro = window.views["macro"]
        timed("Country overview", lambda: macro._open_country_detail(0))
        region = macro.detail_view.region
        timed("Country production tab", lambda: macro.detail_view.tabs.setCurrentIndex(1))
        assert (
            macro.detail_view.state.macro[region]["regional_supply"]
            == current.macro[region]["regional_supply"]
        )
        if macro.detail_view.production_codes:
            timed("Country production metric", lambda: macro.detail_view._open_production_metric(0))
            code = macro.detail_view._metric_selection[1]
            assert macro.detail_view.state.macro[region]["regional_history"][code] == current.macro[
                region
            ]["regional_history"].get(code, {})

        timed("Supply view", lambda: window.set_active_view("supply_chain"))
        supply = window.views["supply_chain"]
        timed("Product detail", lambda: supply._open_row_detail(supply.table.model().index(0, 0)))
        code = supply.selected_code
        actual = process.state.processed_products.get(code) or process.state.commodities.get(code)
        expected = current.processed_products.get(code) or current.commodities.get(code)
        assert actual["supply"] == expected.get("supply", expected.get("production", 0.0))

        for key in ("forex", "bondmarket", "portfolio", "trade_map", "news"):
            timed(key + " activate", lambda key=key: window.set_active_view(key))
            assert window.state.date == current.date
            if key == "forex":
                view = window.views[key]
                timed(
                    "FX detail",
                    lambda view=view: view._open_pair_detail(view.table.model().index(0, 0)),
                )
                assert process.visible_scope["selection"].get("pair")
                assert view.pages.currentWidget() is view.pair_detail_view
            elif key == "bondmarket":
                view = window.views[key]
                timed("Bond detail", lambda view=view: view._open_bond_detail(0))
                symbol = process.visible_scope["selection"]["ticker"]
                expected = next(row for row in current.bond_market if row["symbol"] == symbol)
                actual = next(row for row in process.state.bond_market if row["symbol"] == symbol)
                assert actual["price"] == expected["price"]
            elif key == "news":
                from dataclasses import asdict

                from kojakstreet.core.economic_calendar import build_economic_calendar

                expected = build_economic_calendar(current)
                actual = process.economic_calendar_rows()
                without_history = lambda row: {
                    name: value for name, value in asdict(row).items() if name != "history"
                }
                assert [without_history(row) for row in actual] == [
                    without_history(row) for row in expected
                ]
                news = window.views[key]
                timed("Calendar metric", lambda news=news: news._show_calendar_detail(3))
                history_key = process.visible_scope["selection"]["history_key"]
                selected = next(
                    row
                    for row in process.economic_calendar_rows()
                    if row.history_key == history_key
                )
                assert (
                    selected.history
                    == next(row for row in expected if row.history_key == history_key).history[
                        -520:
                    ]
                )
                assert news.detail_stack.currentIndex() == 2
        process.save_game()
        saved = process.deterministic_signature()
        process.advance_days(5, "status")
        process.load_game()
        assert process.deterministic_signature() == saved
        timed("Markets after Load", lambda: window.set_active_view("markets"))
        markets._show_market_list()
        markets._select_ticker(company)
        markets._open_asset_detail(markets.market_table.currentIndex())
        detail.detail_tabs.setCurrentWidget(detail.overview_tab)
        assert detail.data["revenue"] == current.stocks[company]["revenue"]
        assert len(process._snapshots) == 1 and "full" not in process._snapshots
        (tmp_path / "navigation-timings.json").write_text(json.dumps(timings, indent=2))
    finally:
        window.close()
        app.processEvents()
        process.close()
