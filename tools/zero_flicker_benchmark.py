"""Use the established boundary driver with visible-quote/continuity assertions."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]
import visible_sync_benchmark as driver

from kojakstreet.ui_qt.widgets.top_bar import TickerTape


def main():
    detail_tab = None
    if "--detail-tab" in sys.argv:
        index = sys.argv.index("--detail-tab")
        detail_tab = sys.argv[index + 1]
        if detail_tab not in {"overview", "supply"}:
            raise ValueError("Use overview or supply")
        del sys.argv[index : index + 2]
    checks = []
    original_set = TickerTape.set_items

    def observed(tape, items):
        visible = tape._visible_cells()
        before = {i: tape._identity(tape.items[i]) for i in visible}
        geometry = (tape.offset, list(tape._item_starts), tape.content_width)
        ranked = [item for item in items if item.get("ranked", True)]
        quotes = {tape._identity(item): item for item in items}
        ordinary = len(tape.items) == len(ranked) and bool(tape.items)
        original_set(tape, items)
        if ordinary:
            assert (tape.offset, tape._item_starts, tape.content_width) == geometry
            assert all(
                tape._identity(tape.items[i]) == ticker
                for i, ticker in before.items()
                if ticker in quotes
            )
            assert all(
                float(item["price"]) == float(quotes[tape._identity(item)]["price"])
                and float(item["change"]) == float(quotes[tape._identity(item)]["change"])
                for item in tape.items
            )
            checks.append(
                {"visible_cells": len(visible), "geometry_preserved": True, "quotes_current": True}
            )

    TickerTape.set_items = observed
    source = inspect.getsource(driver)
    driver_patch = """source = inspect.getsource(prior.qt)
    source = source.replace('window.markets_view._select_ticker(ticker, redraw_chart=True)',
        'source_row = window.markets_view.model.row_for_asset(ticker, "Stock")\\n        target = window.markets_view.proxy_model.mapFromSource(window.markets_view.model.index(source_row, 0))\\n        window.markets_view.market_table.setCurrentIndex(target)\\n        window.markets_view._show_index_with_chart_mode(target, redraw_chart=True)')"""
    if detail_tab:
        driver_patch += (
            '\n    source = source.replace("panel.set_range(0)", '
            + repr(
                "panel.set_range(0)\n        panel.detail_tabs.setCurrentWidget(panel."
                + detail_tab
                + "_tab)"
            )
            + ")"
        )
    source = source.replace("source = inspect.getsource(prior.qt)", driver_patch)
    source = source.replace(
        "assert tape._signature(tape.items) == tape._signature(process.ticker_tape_quotes())",
        "quotes = {tape._identity(item): item for item in process.ticker_tape_quotes()}\n        assert all(tape._signature([item]) == tape._signature([quotes[tape._identity(item)]]) for item in tape.items)",
    )
    # This executes the existing trusted driver with the corrected ticker contract.
    namespace = {
        "__file__": str(ROOT / "tools/visible_sync_benchmark.py"),
        "__name__": "zero_flicker_driver",
    }
    exec(compile(source, __file__, "exec"), namespace)  # noqa: S102
    namespace["main"]()
    label = sys.argv[sys.argv.index("--label") + 1]
    result = ROOT / f".cache/visible-ui-sync/{label}.json"
    payload = json.loads(result.read_text(encoding="utf-8"))
    payload["ticker_continuity_checks"] = checks
    payload["detail_tab"] = detail_tab
    result.write_text(json.dumps(payload), encoding="utf-8")
    if label == "zero-final-company-chart":
        for tab in ("overview", "supply"):
            subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--label",
                    f"zero-final-company-{tab}",
                    "--checkpoint",
                    "end",
                    "--days",
                    "6",
                    "--display",
                    "windows",
                    "--view",
                    "markets",
                    "--chart",
                    "detail",
                    "--detail-tab",
                    tab,
                ],
                cwd=ROOT,
                check=True,
            )


if __name__ == "__main__":
    main()
