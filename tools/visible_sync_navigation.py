"""Native on-demand navigation readiness and heartbeat measurements."""

from __future__ import annotations

# ruff: noqa: B023 -- measure invokes each callback synchronously in this iteration
import argparse
import gc
import json
import os
import sys
import time
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/visible-ui-sync"
os.environ["KOJAK_AUDIT_OUTPUT"] = str(OUT)
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]
from day_transition_audit import make_runtime
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from kojakstreet.live_process import LiveSimulationProcess
from kojakstreet.ui_qt.app import KojakStreetWindow
from kojakstreet.ui_qt.theme import APP_STYLESHEET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--checkpoint", default="end")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    app = QApplication([])
    app.setStyleSheet(APP_STYLESHEET)
    runtime = make_runtime(OUT / args.label, args.checkpoint)
    process = LiveSimulationProcess.from_runtime(
        runtime, timeout_seconds=300, release_bootstrap=True
    )
    window = KojakStreetWindow(process.state, process)
    window.showMaximized()
    records, pulses = [], []
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: pulses.append(time.perf_counter()))
    timer.start()

    def settle():
        deadline = time.perf_counter() + 30
        while time.perf_counter() < deadline:
            app.processEvents()
            pending = (
                process._history_pending or window.simulation_busy or window._live_update_pending
            )
            pending = pending or any(
                panel._live_redraw_timer.isActive()
                for panel in window.findChildren(
                    __import__(
                        "kojakstreet.ui_qt.widgets.asset_chart_panel", fromlist=["AssetChartPanel"]
                    ).AssetChartPanel
                )
            )
            if not pending:
                break
            time.sleep(0.002)
        assert not pending, "Navigation readiness timeout"
        app.processEvents()

    def measure(label, action):
        app.processEvents()
        pulses.clear()
        pulses.append(time.perf_counter())
        start = time.perf_counter()
        action()
        settle()
        end = time.perf_counter()
        gaps = [(b - a) * 1000 for a, b in pairwise(pulses)]
        gaps.append((end - pulses[-1]) * 1000)
        records.append(
            {
                "label": label,
                "ms": (end - start) * 1000,
                "heartbeat_max_ms": max(gaps),
                "scope": process.visible_scope,
                "date": str(process.state.date),
            }
        )

    try:
        window.set_active_view("global_macro")
        process.advance_days(35, "global_macro")
        # No graph from bootstrap or explicit full debug state is retained.
        gc.collect()
        process.trade_spot("HARBO", 1.0, "BUY")
        for repeat in range(args.repeats):
            measure("Markets return", lambda: window.set_active_view("markets"))
            markets = window.markets_view
            for kind, book, index in (
                ("Stock", "stocks", 900),
                ("Fund", "funds", 82),
                ("Derivative", "derivatives", 0),
                ("Commodity", "commodities", 0),
                ("Crypto", "cryptos", 0),
                ("Index", "indices", 0),
            ):
                markets._show_market_list()
                ticker = list(getattr(process.state, book))[index]
                measure(kind + " select", lambda ticker=ticker: markets._select_ticker(ticker))
                measure(
                    kind + " chart detail",
                    lambda: markets._open_asset_detail(markets.market_table.currentIndex()),
                )
                detail = markets.stock_detail_view
                measure(
                    kind + " overview",
                    lambda: detail.detail_tabs.setCurrentWidget(detail.overview_tab),
                )
                measure(
                    kind + " supply", lambda: detail.detail_tabs.setCurrentWidget(detail.supply_tab)
                )
                measure(
                    kind + " chart return",
                    lambda: detail.detail_tabs.setCurrentWidget(detail.chart_tab),
                )
            measure("Macro view", lambda: window.set_active_view("macro"))
            macro = window.views["macro"]
            measure("Country overview", lambda: macro._open_country_detail(0))
            measure("Country production", lambda: macro.detail_view.tabs.setCurrentIndex(1))
            measure("Country trade", lambda: macro.detail_view.tabs.setCurrentIndex(2))
            measure("Country sectors", lambda: macro.detail_view.tabs.setCurrentIndex(3))
            macro.detail_view.tabs.setCurrentIndex(0)
            measure("Supply view", lambda: window.set_active_view("supply_chain"))
            supply = window.views["supply_chain"]
            measure(
                "Product detail", lambda: supply._open_row_detail(supply.table.model().index(0, 0))
            )
            measure("FX view", lambda: window.set_active_view("forex"))
            fx = window.views["forex"]
            measure("FX detail", lambda: fx._open_pair_detail(fx.table.model().index(0, 0)))
            measure("Bond view", lambda: window.set_active_view("bondmarket"))
            bonds = window.views["bondmarket"]
            measure("Bond detail", lambda: bonds._open_bond_detail(0))
            measure("Portfolio holding", lambda: window.set_active_view("portfolio"))
            assert window.views["portfolio"].row_metadata
            measure("Trade map", lambda: window.set_active_view("trade_map"))
            measure("Calendar view", lambda: window.set_active_view("news"))
            news = window.views["news"]
            measure("Calendar metric", lambda: news._show_calendar_detail(repeat % 4))
            measure("Global macro", lambda: window.set_active_view("global_macro"))
            if repeat == 1:
                process.save_game()
                saved = process.deterministic_signature()
                process.advance_days(5, "global_macro")
                process.load_game()
                assert process.deterministic_signature() == saved
        window.grab().save(str(OUT / f"{args.label}.png"))
        (OUT / f"{args.label}.json").write_text(
            json.dumps(
                {
                    "rows": records,
                    "repeats": args.repeats,
                    "qt_platform": app.platformName(),
                    "hidden_days": 35,
                    "save_load_exact": True,
                },
                indent=2,
            )
        )
        print("Navigation samples", len(records), flush=True)
    finally:
        timer.stop()
        window.close()
        app.processEvents()
        process.close()


if __name__ == "__main__":
    main()
