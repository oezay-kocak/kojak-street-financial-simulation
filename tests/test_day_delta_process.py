import time
from copy import deepcopy
from pathlib import Path

from PySide6.QtWidgets import QApplication

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.day_delta import public_copy, state_values
from kojakstreet.live_process import LiveSimulationProcess, game_state_from_payload
from kojakstreet.ui_qt.app import KojakStreetWindow


def wait_for_day(app, window):
    deadline = time.perf_counter() + 60
    while (
        window.simulation_busy or window._live_update_pending
    ) and time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.002)
    app.processEvents()
    assert not window.simulation_busy
    assert not window._live_update_pending


def test_actual_manual_step_and_timer_share_complete_current_state_history_and_rng(
    tmp_path, monkeypatch
):
    app = QApplication.instance() or QApplication([])
    root = Path(__file__).resolve().parents[1]
    bootstrap = IntegratedRuntime(root, data_dir=tmp_path, seed=1729, flush_interval_days=1000)
    bootstrap.advance_days(16)
    initial = bootstrap.snapshot_for_view("markets")
    process = LiveSimulationProcess.from_runtime(bootstrap, timeout_seconds=90)
    window = KojakStreetWindow(initial, process)
    requests = []
    original = process._request

    def request(command, *args, **kwargs):
        requests.append((command, dict(kwargs)))
        return original(command, *args, **kwargs)

    monkeypatch.setattr(process, "_request", request)
    try:
        process.save_game()
        window.step_simulation()
        wait_for_day(app, window)
        manual = public_copy(state_values(process.snapshot()))
        signature = deepcopy(process.deterministic_signature())
        assert window.state.date == process.snapshot().date

        process.load_game()
        window.state = process.snapshot_for_view("markets")
        window._refresh_active_view(preserve_live_history=False)
        window.ticks_per_timeout = 1
        window._on_timer_tick()
        wait_for_day(app, window)
        assert public_copy(state_values(process.snapshot())) == manual
        assert process.deterministic_signature() == signature
        advances = [args for command, args in requests if command == "advance" and args["steps"] > 0]
        assert len(advances) == 2
        assert all(args["force_snapshot"] is False for args in advances)

        # Explicit debug control verifies every UI field, including all history
        # series, against the authoritative worker. It is not a normal Step.
        control = original("advance", steps=0, profile="full", force_snapshot=True)
        authoritative = game_state_from_payload(control["state"])
        assert public_copy(state_values(authoritative)) == manual
        process._apply_result(control)
        for key in window.VIEW_ORDER:
            window.set_active_view(key)
            app.processEvents()
            assert window.state.date == authoritative.date
            view = window.views[key]
            if hasattr(view, "state"):
                assert view.state.date == authoritative.date
    finally:
        window.close()
        app.processEvents()
        process.close()
