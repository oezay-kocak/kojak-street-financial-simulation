"""Real timer/paint/heartbeat measurements, reusing the audit's T0--T4 driver.

Unlike an explicit debug read, T4 checks the compact scope and displayed tape.
The driver measures navigation outside ticks. Production economics are intact.
"""

from __future__ import annotations

import argparse
import inspect
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/visible-ui-sync"
os.environ["KOJAK_AUDIT_OUTPUT"] = str(OUT)
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]
import day_transition_audit as prior


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--checkpoint", default="end")
    parser.add_argument("--days", type=int, default=27)
    parser.add_argument("--view")
    parser.add_argument("--display", choices=("windows", "offscreen"), default="offscreen")
    parser.add_argument("--chart", choices=("none", "detail", "preview", "candle"), default="none")
    parser.add_argument("--trace-ui", action="store_true")
    args = parser.parse_args()
    from kojakstreet.ui_qt.widgets.top_bar import TickerTape

    prior.audit.wrap(TickerTape, "paintEvent", "ui.ticker.paint")
    prior.audit.wrap(TickerTape, "set_items", "ui.ticker.update")
    prior.audit.wrap(TickerTape, "_calculate_content_width", "ui.ticker.layout")
    source = inspect.getsource(prior.qt)
    source = source.replace(
        "LiveSimulationProcess.from_runtime(runtime, timeout_seconds=300)",
        "LiveSimulationProcess.from_runtime(runtime, timeout_seconds=300, release_bootstrap=True)",
    )
    source = source.replace(
        'emit({"run": args.name, "setup": "process ready"})',
        'initial = process.snapshot_for_view("markets")\n    emit({"run": args.name, "setup": "process ready"})',
    )
    source = source.replace('ctx = {"row": None', 'cold_switches = {}\n    ctx = {"row": None')
    source = source.replace(
        "window.set_active_view(key)\n        app.processEvents()",
        "switch_start = time.perf_counter()\n        window.set_active_view(key)\n        app.processEvents()\n        cold_switches[key] = (time.perf_counter() - switch_start) * 1000",
    )
    source = source.replace(
        "date = process._status_state.date.date()",
        """next_view = measured_view or window.VIEW_ORDER[len(ctx["records"]) % len(window.VIEW_ORDER)]
        switch_start = time.perf_counter()
        window.set_active_view(next_view)
        app.processEvents()
        switch_ms = (time.perf_counter() - switch_start) * 1000
        date = process._status_state.date.date()""",
    )
    source = source.replace(
        'row["main_thread"] = threading.get_ident()',
        'row["view"] = next_view\n        row["switch_ms"] = switch_ms\n        row["main_thread"] = threading.get_ident()',
    )
    source = source.replace(
        "window._request_simulation_steps(1, force_refresh=args.force_refresh)",
        "window._on_timer_tick()",
    )
    source = source.replace(
        'row["t4"] = now',
        """assert window.state.date == process.state.date
        tape = window.top_bar.ticker_tape
        assert tape.pending_items is None
        assert tape._signature(tape.items) == tape._signature(process.ticker_tape_quotes())
        row["ticker_current_at_t4"] = True
        if row["view"] == "markets" and window.markets_view.pages.currentWidget() is window.markets_view.main_page:
            selected = window.markets_view.chart_panel.current_asset
            if selected:
                from kojakstreet.visible_state import BOOKS
                assert selected[2]["kurs"] == getattr(process.state, BOOKS[selected[1]][1])[selected[0]]["kurs"]
                row["preview_current_at_t4"] = True
        row["extraction_ms"] = dict(process.last_extraction_ms)
        row["visible_scope"] = dict(process.visible_scope)
        row["t4"] = now""",
    )
    source = source.replace(
        '"qt_platform": app.platformName()',
        '"cold_switches_ms": cold_switches, "qt_platform": app.platformName()',
    )
    # Observe actual visible paints without an application-wide Python filter.
    source = source.replace(
        "app.installEventFilter(observer)",
        "window.top_bar.ticker_tape.installEventFilter(observer)\n    window.centralWidget().installEventFilter(observer)",
    )
    prior.__dict__["measured_view"] = args.view
    namespace = {}
    exec(compile(source, str(Path(__file__).resolve()), "exec"), prior.__dict__, namespace)  # noqa: S102 -- trusted local measurement driver
    namespace["qt"](
        argparse.Namespace(
            days=args.days,
            name=args.label,
            checkpoint=args.checkpoint,
            display=args.display,
            chart=args.chart,
            view=args.view or "markets",
            force_refresh=False,
            manual_step=False,
            profile_ui=False,
            trace_ui=args.trace_ui,
            indicators=False,
            repeat_span=0,
        )
    )


if __name__ == "__main__":
    main()
