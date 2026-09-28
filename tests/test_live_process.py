from __future__ import annotations

import json
import os
import time
from itertools import pairwise
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.live_process import LiveSimulationProcess, economic_signature
from kojakstreet.ui_qt.app import KojakStreetWindow


def test_live_process_is_deterministic_responsive_and_save_load_safe(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    direct = IntegratedRuntime(root, data_dir=tmp_path / "direct", seed=20260922, flush_interval_days=1000)
    direct_started = time.perf_counter()
    try:
        direct.advance_days(30)
        direct_ms_day = (time.perf_counter() - direct_started) * 1000.0 / 30.0
        expected = json.loads(json.dumps(economic_signature(direct.daten), sort_keys=True))
    finally:
        direct.close()

    bootstrap = IntegratedRuntime(root, data_dir=tmp_path / "worker", seed=20260922, flush_interval_days=1000)
    initial_state = bootstrap.snapshot_for_view("markets")
    process = LiveSimulationProcess.from_runtime(bootstrap, timeout_seconds=30.0)
    window = KojakStreetWindow(initial_state, process)
    app = QApplication.instance()
    event_times: list[float] = []
    heartbeat = QTimer()
    heartbeat.setInterval(5)
    heartbeat.timeout.connect(lambda: event_times.append(time.perf_counter()))
    try:
        assert app is not None
        assert process.worker_pid != os.getpid()
        heartbeat.start()
        started = time.perf_counter()
        window._request_simulation_steps(30, force_refresh=False)
        while window.simulation_busy and time.perf_counter() - started < 20.0:
            app.processEvents()
            time.sleep(0.002)
        app.processEvents()
        heartbeat.stop()

        assert not window.simulation_busy
        assert len(event_times) >= 20
        gaps = [later - earlier for earlier, later in pairwise(event_times)]
        assert not gaps or max(gaps) < 0.150
        assert economic_signature_result(process) == expected
        assert process.last_simulation_ms / 30.0 < max(1000.0, direct_ms_day * 2.5)
        assert process.last_apply_ms < 50.0

        process.save_game()
        saved = process.deterministic_signature()
        saved_date = process.state.date
        # Cross the next monthly report, not just the immediate restore boundary.
        process.advance_days(17, "status")
        continued = process.deterministic_signature()
        assert continued != saved
        process.load_game()
        assert process.deterministic_signature() == saved
        assert process.state.date == saved_date
        process.advance_days(17, "status")
        assert process.deterministic_signature() == continued
        process.load_game()

        ticker = next(iter(process.state.stocks))
        validation = process.validate_trade(ticker, "SPOT", "BUY", 1.0, 1)
        assert validation.is_valid
        process.trade_spot(ticker, 1.0, "BUY")
        assert ticker in process.state.portfolio
        process.exchange_currency("GD", "Ameron", 10.0)
        assert process.state.fx_balances["Ameron"] > 0.0

        history_version = process.history_cache_version
        history_started = time.perf_counter()
        process.asset_history("Stock", ticker, 1200)
        assert time.perf_counter() - history_started < 0.100
        history_deadline = time.perf_counter() + 10.0
        while process.history_cache_version == history_version and time.perf_counter() < history_deadline:
            app.processEvents()
            time.sleep(0.01)
        assert process.history_cache_version > history_version

        window._request_simulation_steps(5, force_refresh=False)
        close_started = time.perf_counter()
        window.close()
        app.processEvents()
        assert time.perf_counter() - close_started < 5.0
        assert process._process.poll() is not None
    finally:
        heartbeat.stop()
        window.close()
        app.processEvents()
        process.close()


def economic_signature_result(process: LiveSimulationProcess):
    return process.deterministic_signature()
