"""Reproducible measurement-only audit of the real live-process/Qt path.

Examples: python tools/day_transition_audit.py headless --days 365
          python tools/day_transition_audit.py qt --days 365 --display windows
          python tools/day_transition_audit.py qt --days 40 --checkpoint end --chart detail
Production code is unchanged. Instrumented and profiler runs are kept separate.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import sys
import time
import threading
import tracemalloc
import shutil
import faulthandler
from collections import Counter
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("KOJAK_AUDIT_PROJECT_ROOT", str(TOOL_ROOT))).resolve()
ORIGINAL_SYS_PATH = list(sys.path)
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(TOOL_ROOT / "tools")]
import day_transition_audit_support as audit

def production_import_paths():
    """Match the production -m worker path after loading audit-only modules."""
    paths = [str(ROOT), *ORIGINAL_SYS_PATH[1:]]
    source = str(ROOT / "src")
    if source not in paths:
        paths.insert(1, source)
    sys.path[:] = paths

production_import_paths()

REFERENCE_OUT = TOOL_ROOT / ".cache" / "day-transition-audit"
OUT = Path(os.environ.get("KOJAK_AUDIT_OUTPUT", str(REFERENCE_OUT))).resolve()
OUT.mkdir(parents=True, exist_ok=True)


def emit(message):
    print(json.dumps(message), flush=True)


def make_runtime(directory, checkpoint=None):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    if checkpoint:
        directory.mkdir(parents=True, exist_ok=True)
        # Clone the matching analytical store, including its history identity.
        # All setup/cleanup runs outside measured transitions.
        shutil.copy2(REFERENCE_OUT / "headless-year" / "kojakstreet.duckdb", directory / "kojakstreet.duckdb")
    runtime = IntegratedRuntime(ROOT, data_dir=directory, seed=1729)
    if checkpoint:
        from kojakstreet.core.checkpoints import decode, restore
        payload = decode(json.loads((REFERENCE_OUT / f"checkpoint-{checkpoint}.json").read_text(encoding="utf-8")))
        restore(runtime.daten, payload)
        runtime.state.sync_from_legacy()
        runtime.market.warm_runtime_indexes()
        runtime.data_store.restore_checkpoint_session(payload.get("analytics_session", {}))
        cutoff = runtime.daten.datum.date().isoformat()
        connection = runtime.data_store._connection
        for (table,) in connection.execute("SHOW TABLES").fetchall():
            columns = {r[1] for r in connection.execute(f'PRAGMA table_info("{table}")').fetchall()}
            if "date" in columns:
                connection.execute(f'DELETE FROM "{table}" WHERE date >= ?', [cutoff])
            if table == "history_aggregate":
                connection.execute('DELETE FROM history_aggregate WHERE bucket_end >= ?', [cutoff])
        runtime.data_store.record_day(runtime.state, current_scope="full")
    return runtime


def checkpoint(runtime, name):
    from kojakstreet.core.checkpoints import capture, atomic_write
    payload = capture(runtime.daten)
    payload["analytics_session"] = runtime.data_store.checkpoint_session()
    atomic_write(OUT / f"checkpoint-{name}.json", payload)


def signature(runtime):
    from kojakstreet.live_process import economic_signature
    return economic_signature(runtime.daten)


def public_numeric_digest(runtime):
    """Compare all public checkpoint numbers, not just the compact signature."""
    from kojakstreet.core.checkpoints import capture
    digest = hashlib.sha256()
    count = 0
    def visit(value, path):
        nonlocal count
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            digest.update(json.dumps((path, value), separators=(",", ":")).encode())
            count += 1
        elif isinstance(value, dict):
            for key in sorted(value, key=str):
                if not str(key).startswith("_"):
                    visit(value[key], (*path, str(key)))
        elif isinstance(value, (tuple, list)):
            for index, item in enumerate(value):
                visit(item, (*path, str(index)))
    visit(capture(runtime.daten)["checkpoint"], ())
    return {"count": count, "sha256": digest.hexdigest()}


def headless(args):
    if not args.uninstrumented:
        audit.install()
    runtime = make_runtime(OUT / args.name, args.checkpoint)
    records = []
    try:
        for i in range(args.days):
            date = runtime.daten.datum.date()
            if args.name == "headless-year" and str(date) in {"1990-01-10", "1990-01-15", "1990-01-31", "1990-12-31"}:
                checkpoint(runtime, str(date))
            audit.begin(date)
            runtime.advance_day()
            row = audit.finish()
            row["total_ms"] = (row["t_end"]-row["t_start"])*1000
            records.append(row)
            if i % 30 == 0:
                emit({"run": args.name, "day": i+1, "date": str(date), "ms": round(row["total_ms"], 2)})
        if args.name == "headless-year":
            checkpoint(runtime, "end")
        result = {"mode": "headless", "name": args.name, "rows": records, "signature": signature(runtime),
                  "duckdb_bytes": runtime.data_store.path.stat().st_size,
                  "database_rows": {row[0]: runtime.data_store._connection.execute(f'SELECT count(*) FROM "{row[0]}"').fetchone()[0]
                                    for row in runtime.data_store._connection.execute("SHOW TABLES").fetchall()}}
        if args.name.startswith("control-"):
            result["public_numeric_checkpoint"] = public_numeric_digest(runtime)
        (OUT / f"{args.name}.json").write_text(json.dumps(result), encoding="utf-8")
        emit({"run": args.name, "finished": len(records)})
    finally:
        runtime.close()


def profile_runs(args):
    audit.install()
    faulthandler.cancel_dump_traceback_later()
    results = []
    for label, point in (("normal", "1990-01-10"), ("report", "1990-01-15"), ("month_end", "1990-01-31"), ("year_end", "1990-12-31"), ("mature_normal", "end")):
        runtime = make_runtime(OUT / f"profile-{label}", point)
        try:
            for repetition in range(3):
                # Restore the same checkpoint/RNG; no economic changes for benchmarking.
                if repetition:
                    runtime.close()
                    runtime = make_runtime(OUT / f"profile-{label}-{repetition}", point)
                audit.begin(runtime.daten.datum.date(), OUT / f"profile-{label}-{repetition}.pstats")
                runtime.advance_day()
                row = audit.finish()
                row["label"] = label
                results.append(row)
            emit({"profile": label, "completed": 3})
        finally:
            runtime.close()
    for repetition in range(3):
        runtime = make_runtime(OUT / f"profile-flush-{repetition}", "end")
        try:
            for _ in range(29):
                runtime.advance_day()
            audit.begin(runtime.daten.datum.date(), OUT / f"profile-flush-{repetition}.pstats")
            runtime.advance_day()
            row = audit.finish()
            row["label"] = "flush"
            results.append(row)
            emit({"profile": "flush", "completed": repetition + 1})
        finally:
            runtime.close()
    # Allocation measurement is explicitly separate from latency measurements.
    for label, point in (("normal", "end"), ("report", "1990-01-15")):
        runtime = make_runtime(OUT / f"allocation-{label}", point)
        try:
            tracemalloc.start(8)
            before = tracemalloc.take_snapshot()
            start = time.perf_counter()
            runtime.advance_day()
            elapsed = (time.perf_counter()-start)*1000
            after = tracemalloc.take_snapshot()
            current, peak = tracemalloc.get_traced_memory()
            differences = after.compare_to(before, "lineno")
            allocations = {"label": label, "instrumented_ms": elapsed, "current_bytes": current, "peak_bytes": peak,
                           "net_bytes": sum(x.size_diff for x in differences), "net_blocks": sum(x.count_diff for x in differences),
                           "top": [{"source": str(x.traceback), "bytes": x.size_diff, "blocks": x.count_diff} for x in differences[:20]]}
            (OUT / f"allocations-{label}.json").write_text(json.dumps(allocations, indent=2), encoding="utf-8")
            tracemalloc.stop()
            emit({"allocation": label, "peak_bytes": peak})
        finally:
            runtime.close()
    (OUT / "profiles.json").write_text(json.dumps(results), encoding="utf-8")


def qt(args):
    if args.display == "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject, QEvent, QTimer, QModelIndex, Slot, Qt, QThread
    from PySide6.QtWidgets import QApplication
    import pyqtgraph as pg
    from kojakstreet.live_process import LiveSimulationProcess
    from kojakstreet.ui_qt.app import KojakStreetWindow
    from kojakstreet.ui_qt.theme import APP_STYLESHEET
    from kojakstreet.ui_qt.widgets.qt_chart import FastChartView
    from kojakstreet.ui_qt.widgets.asset_chart_panel import AssetChartPanel
    from kojakstreet.ui_qt.widgets.stock_detail_dialog import StockDetailView
    from kojakstreet.ui_qt.views.markets_view import MarketsView
    from kojakstreet.ui_qt.models.market_table_model import MarketTableModel
    audit.install()
    worker_log = OUT / f"{args.name}-worker.jsonl"
    if worker_log.exists():
        raise RuntimeError(f"Output already exists: {worker_log}")
    def worker_command(self, bootstrap_path):
        return [sys.executable, str(Path(__file__).resolve()), "worker", "--project-root", str(self.project_root),
                "--data-dir", str(self.data_dir), "--bootstrap", str(bootstrap_path), "--output", str(worker_log)]
    LiveSimulationProcess._worker_command = worker_command
    ctx = {"row": None, "records": [], "finished": False, "errors": [], "heartbeats": [], "last_heartbeat": time.perf_counter()}
    original_apply = LiveSimulationProcess._apply_result
    def apply(self, result):
        with audit.span("parent.apply_result"):
            value = original_apply(self, result)
        if ctx["row"] is not None:
            ctx["row"]["t2"] = time.perf_counter()
        return value
    LiveSimulationProcess._apply_result = apply
    for name in ("_request", "_merge_current_rows"):
        audit.wrap(LiveSimulationProcess, name, "parent." + name.lstrip("_"))
    import kojakstreet.live_process as lp
    audit.wrap(lp, "game_state_from_payload", "parent.decode_state")
    audit.wrap(lp, "apply_day_delta", "parent.apply_day_delta")
    audit.wrap(lp, "prepare_day_delta", "parent.decode_day_delta")
    original_loads = json.loads
    def loads(*values, **kwargs):
        with audit.span("parent.json_decode"):
            return original_loads(*values, **kwargs)
    json.loads = loads
    for name in ("apply_live_quotes", "_append_live_history", "_data_with_history", "refresh", "_emit_visible_market_rows"):
        audit.wrap(MarketsView, name, "ui.markets." + name.lstrip("_"))
    for name in ("apply_quote_rows", "refresh"):
        audit.wrap(MarketTableModel, name, "ui.model." + name)
    for cls in (AssetChartPanel, StockDetailView):
        for name in ("update_live_quote", "_draw_chart", "_redraw_live_line", "_flush_live_line_redraw"):
            audit.wrap(cls, name, "ui." + cls.__name__ + "." + name.lstrip("_"))
    for name in ("plot_line", "plot_lines", "plot_candles", "plot_long_short_heatmap"):
        original = getattr(FastChartView, name)
        def make_draw(original, name):
            def draw(self, *values, **kwargs):
                if ctx["row"] is not None:
                    key = "visible_chart_calls" if self.isVisible() else "hidden_chart_calls"
                    ctx["row"][key] += 1
                with audit.span("chart." + name):
                    return original(self, *values, **kwargs)
            return draw
        setattr(FastChartView, name, make_draw(original, name))
    audit.wrap(pg.GraphicsView, "paintEvent", "chart.paint")

    class Window(KojakStreetWindow):
        def _audit_on_finished(self, state, steps):
            if ctx["row"] is not None:
                ctx["row"]["t_slot"] = time.perf_counter()
                ctx["row"]["slot_thread"] = threading.get_ident()
                ctx["row"]["slot_is_qt_main"] = QThread.currentThread() == app.thread()
                assert ctx["row"]["slot_is_qt_main"], "UI slot is outside the Qt main thread"
            with audit.span("ui.finished_slot"):
                super()._on_simulation_finished(state, steps)
            if ctx["row"] is not None and ctx["row"]["force_refresh"]:
                ctx["row"]["t3"] = time.perf_counter()

        def _ensure_simulation_worker(self):
            super()._ensure_simulation_worker()
            if getattr(self, "_audit_connected_worker", None) is not self.simulation_worker:
                self.simulation_worker.finished.disconnect(self._on_simulation_finished)
                self.simulation_worker.finished.connect(completion_observer.receive, Qt.ConnectionType.QueuedConnection)
                self._audit_connected_worker = self.simulation_worker

        def _apply_live_market_updates(self):
            with audit.span("ui.live_update"):
                super()._apply_live_market_updates()
            if ctx["row"] is not None:
                ctx["row"]["t3"] = time.perf_counter()
                ctx["row"]["ui_update_thread"] = threading.get_ident()
                ctx["row"]["update_is_qt_main"] = QThread.currentThread() == app.thread()
                assert ctx["row"]["update_is_qt_main"], "UI update is outside the Qt main thread"

        def _on_simulation_failed(self, message):
            ctx["errors"].append(message)
            super()._on_simulation_failed(message)
            app.quit()

    class CompletionObserver(QObject):
        @Slot(object, int)
        def receive(self, state, steps):
            window._audit_on_finished(state, steps)

    class Observer(QObject):
        def eventFilter(self, obj, event):
            row = ctx["row"]
            if row is not None:
                kind = event.type()
                if kind == QEvent.Type.Paint:
                    row["paints"] += 1
                    row["last_paint"] = time.perf_counter()
                elif kind == QEvent.Type.MetaCall:
                    row["qt_metacalls"] += 1
                elif kind == QEvent.Type.Timer:
                    row["qt_timer_events"] += 1
            return False

    app = QApplication([])
    ctx["app_thread"] = threading.get_ident()
    app.setStyleSheet(APP_STYLESHEET)
    runtime = make_runtime(OUT / args.name, args.checkpoint)
    initial = runtime.snapshot_for_view("markets")
    emit({"run": args.name, "setup": "runtime ready"})
    process = LiveSimulationProcess.from_runtime(runtime, timeout_seconds=300)
    emit({"run": args.name, "setup": "process ready"})
    window = Window(initial, process)
    completion_observer = CompletionObserver(window)
    assert window.thread() == app.thread() and completion_observer.thread() == app.thread()
    observer = Observer()
    app.installEventFilter(observer)
    window.showMaximized()
    # Load all views once to check that already-created invisible views stay idle.
    for key in window.VIEW_ORDER:
        window.set_active_view(key)
        app.processEvents()
    window.set_active_view(args.view)
    # Track model signals and view refreshes, after initial construction.
    def count_signal(label):
        def count(*values):
            if ctx["row"] is not None:
                ctx["row"]["model_signals"][label] += 1
        return count
    for cls in ("model", "proxy_model"):
        model = getattr(window.markets_view, cls)
        for signal in ("dataChanged", "modelReset", "rowsInserted", "layoutChanged"):
            getattr(model, signal).connect(count_signal(cls + "." + signal))
    for key, view in window.views.items():
        for name in ("refresh", "apply_live_current_rows", "apply_live_quotes"):
            original = getattr(view, name, None)
            if original is None:
                continue
            def bind(original, key, name):
                def update(*values, **kwargs):
                    if ctx["row"] is not None:
                        ctx["row"]["view_calls"][key + "." + name] += 1
                    return original(*values, **kwargs)
                return update
            setattr(view, name, bind(original, key, name))
    if args.chart != "none":
        ticker = next(iter(initial.stocks))
        window.markets_view._select_ticker(ticker, redraw_chart=True)
        if args.chart in {"detail", "candle"}:
            window.markets_view._open_asset_detail(window.markets_view.market_table.currentIndex())
            panel = window.markets_view.stock_detail_view
        else:
            panel = window.markets_view.chart_panel
        panel.set_range(0)
        if args.chart == "candle":
            panel.set_chart_mode("Candle")
        if args.indicators:
            for period in panel.indicator_buttons:
                panel.set_indicator(period, True)
        if args.chart in {"detail", "candle"} and window.markets_view.pages.currentWidget() is not panel:
            raise RuntimeError("Requested detail chart is not visible")
    else:
        window.markets_view.market_table.setCurrentIndex(QModelIndex())
        window.markets_view.market_table.clearSelection()
    window.top_bar.run_button.setChecked(not args.manual_step)
    process.set_running(not args.manual_step)
    window.timer.stop()  # Intentional game-day waiting is excluded, not production work.
    emit({"run": args.name, "setup": "window ready", "model_rows": window.markets_view.model.rowCount(),
          "proxy_rows": window.markets_view.proxy_model.rowCount()})
    if args.repeat_span:
        process.save_game()  # Isolated audit save; outside every measured transition.
    faulthandler.cancel_dump_traceback_later()
    started = time.perf_counter()

    def request():
        if len(ctx["records"]) >= args.days:
            window.grab().save(str(OUT / f"{args.name}.png"))
            ctx["signature"] = process.deterministic_signature()
            ctx["finished"] = True
            app.quit()
            return
        if process._history_pending:
            QTimer.singleShot(10, request)
            return
        if args.repeat_span and ctx["records"] and len(ctx["records"]) % args.repeat_span == 0:
            process.load_game()
            process.set_running(not args.manual_step)
            window.state = process.snapshot_for_view(args.view)
            window._refresh_active_view(preserve_live_history=False)
        date = process._status_state.date.date()
        if args.trace_ui:
            tracemalloc.start(1)
            ctx["allocation_before"] = tracemalloc.take_snapshot()
        row = {"date": str(date), "t0": time.perf_counter(), "t3": None, "paints": 0,
               "visible_chart_calls": 0, "hidden_chart_calls": 0, "qt_metacalls": 0, "qt_timer_events": 0,
               "model_signals": Counter(), "view_calls": Counter(), "heartbeat_gaps_ms": [], "force_refresh": args.force_refresh}
        row["main_thread"] = threading.get_ident()
        row["request_is_qt_main"] = QThread.currentThread() == app.thread()
        assert row["request_is_qt_main"], "Request is outside the Qt main thread"
        row["model_rows"] = window.markets_view.model.rowCount()
        row["proxy_rows"] = window.markets_view.proxy_model.rowCount()
        ctx["row"] = row
        profile_path = OUT / f"ui-profile-{args.name}-{len(ctx['records'])}.pstats" if args.profile_ui else None
        audit.begin(date, profile_path)
        if args.manual_step:
            window.step_simulation()
            row["force_refresh"] = window.force_refresh_after_worker
        else:
            window._request_simulation_steps(1, force_refresh=args.force_refresh)

    def heartbeat():
        now = time.perf_counter()
        gap = (now-ctx["last_heartbeat"])*1000
        ctx["last_heartbeat"] = now
        row = ctx["row"]
        if row is None:
            return
        # The first interval may begin before T0 (for example after chart setup).
        row["heartbeat_gaps_ms"].append(min(gap,(now-row["t0"])*1000))
        if now - row["t0"] > 120:
            ctx["errors"].append("Transition timeout")
            app.quit()
            return
        if row["t3"] is None or window.simulation_busy or window._live_update_pending or process._history_pending:
            return
        for widget in window.findChildren(AssetChartPanel):
            if widget._live_redraw_timer.isActive():
                return
        if row["paints"] == 0 or row.get("last_paint", 0) < row["t3"]:
            return
        row["t4"] = now
        parent = audit.finish()
        if args.trace_ui:
            after = tracemalloc.take_snapshot()
            current, peak = tracemalloc.get_traced_memory()
            changes = after.compare_to(ctx.pop("allocation_before"), "lineno")
            allocation = {"label": args.name, "current_bytes": current, "peak_bytes": peak,
                          "net_bytes": sum(x.size_diff for x in changes), "net_blocks": sum(x.count_diff for x in changes),
                          "instrumented_ms": row["total_ms"] if "total_ms" in row else (now-row["t0"])*1000,
                          "top": [{"source": str(x.traceback), "bytes": x.size_diff, "blocks": x.count_diff} for x in changes[:20]]}
            tracemalloc.stop()
            (OUT / f"allocations-{args.name}-{len(ctx['records'])}.json").write_text(json.dumps(allocation, indent=2), encoding="utf-8")
        row.update(parent_spans=parent["spans"], parent_calls=parent["calls"], parent_gc=parent["gc"],
                   parent_cpu_ms=parent["cpu_ms"], parent_rss_start=parent["rss_start"], parent_rss_end=parent["rss_end"],
                   ipc_roundtrip_ms=process.last_ipc_ms, proxy_apply_ms=process.last_apply_ms,
                   worker_runtime_ms=process.last_simulation_ms, total_ms=(now-row["t0"])*1000)
        ctx["records"].append(row)
        ctx["row"] = None
        if len(ctx["records"]) % 30 == 0:
            emit({"run": args.name, "day": len(ctx["records"]), "date": row["date"], "total_ms": round(row["total_ms"], 2)})
        QTimer.singleShot(30, request)  # Outside measured transitions; allow paints to settle.

    timer = QTimer()
    timer.setTimerType(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.TimerType.PreciseTimer)
    timer.timeout.connect(heartbeat)
    timer.start(10)
    QTimer.singleShot(500, request)
    exit_code = app.exec()
    timer.stop()
    result = {"mode": "qt", "name": args.name, "display": args.display, "chart": args.chart, "view": args.view,
              "finished": ctx["finished"], "errors": ctx["errors"], "rows": ctx["records"], "exit_code": exit_code,
              "signature": ctx.get("signature"), "elapsed_ms": (time.perf_counter()-started)*1000,
              "qt_platform": app.platformName(), "worker_pid": process.worker_pid}
    window.close()
    result["worker_exited"] = process._process.poll() is not None
    (OUT / f"{args.name}.json").write_text(json.dumps(result), encoding="utf-8")
    emit({"run": args.name, "completed": len(ctx["records"]), "errors": ctx["errors"]})
    if ctx["errors"] or not ctx["finished"]:
        raise RuntimeError("Qt audit did not finish")


def worker(args):
    audit.install()
    live_worker = audit.install_worker_logging(args.output)
    raise SystemExit(live_worker.run(args.project_root, args.data_dir, args.bootstrap))


def main():
    faulthandler.enable()
    faulthandler.dump_traceback_later(240, repeat=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("headless", "qt", "profiles", "worker"))
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--name", default="headless-year")
    parser.add_argument("--checkpoint")
    parser.add_argument("--display", choices=("windows", "offscreen"), default="windows")
    parser.add_argument("--chart", choices=("none", "preview", "detail", "candle"), default="none")
    parser.add_argument("--view", default="markets")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--manual-step", action="store_true")
    parser.add_argument("--profile-ui", action="store_true")
    parser.add_argument("--trace-ui", action="store_true")
    parser.add_argument("--indicators", action="store_true")
    parser.add_argument("--uninstrumented", action="store_true")
    parser.add_argument("--repeat-span", type=int, default=0)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--bootstrap", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode == "worker":
        worker(args)
        return
    if (OUT / 'stop-after-current-run').exists():
        emit({'stopped': 'Requested audit stop at a completed-run boundary; production state unchanged'})
        raise SystemExit(75)
    import numpy, duckdb, PySide6, pyqtgraph
    environment = {"timestamp_utc_s": time.time(), "platform": platform.platform(), "python": sys.version, "logical_cpus": os.cpu_count(),
                   "processor": os.environ.get("PROCESSOR_IDENTIFIER"), "numpy": numpy.__version__,
                   "duckdb": duckdb.__version__, "pyside": PySide6.__version__, "pyqtgraph": pyqtgraph.__version__,
                   "seed": 1729, "gc_thresholds": gc.get_threshold(), "mode": args.mode,
                   "sys_path": list(sys.path), "production_import_paths": True,
                   "source_sha256": {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                                     for path in (ROOT / 'src').rglob('*.py')}}
    (OUT / f"environment-{args.name}.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")
    {"headless": headless, "qt": qt, "profiles": profile_runs}[args.mode](args)


if __name__ == "__main__":
    main()
