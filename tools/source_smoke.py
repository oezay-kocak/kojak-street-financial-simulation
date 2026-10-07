"""Exercise the real Qt entrypoint and post-load continuation in isolated data.

Install the project first. This also runs with an installed wheel interpreter,
from a working directory outside the checkout; no source path is injected.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from kojakstreet.ui_qt.app import KojakStreetWindow, main
from kojakstreet.ui_qt.new_simulation import NewSimulationDialog


def run(output: Path, timeout: float = 180.0) -> int:
    started = time.perf_counter()
    result: dict = {"seed": 1729, "steps": [], "display": "offscreen Qt callbacks"}
    stage = 0
    window = None
    saved = None
    continued = None

    def record(event):
        row = {"event": event, "seconds": round(time.perf_counter() - started, 3)}
        result["steps"].append(row)
        print(json.dumps(row), flush=True)

    def drive():
        nonlocal stage, window, saved, continued
        app = QApplication.instance()
        try:
            if time.perf_counter() - started > timeout:
                raise TimeoutError(f"Source smoke exceeded {timeout}s at stage {stage}")
            if stage == 0:
                chooser = next((w for w in app.topLevelWidgets() if isinstance(w, NewSimulationDialog)), None)
                if chooser is not None:
                    chooser.seed.setValue(1729)
                    chooser.accept()
                    record("Genesis chooser accepted")
                    stage = 1
            elif stage == 1:
                window = next((w for w in app.topLevelWidgets() if isinstance(w, KojakStreetWindow)), None)
                if window is not None:
                    assert window.runtime.is_process_runtime
                    for key in window.VIEW_ORDER:
                        window.set_active_view(key)
                        app.processEvents()
                    record("All nine views navigated with live subprocess")
                    window.set_active_view("markets")
                    window._execute_trade("STONE", "SPOT", "BUY", 10.0, 1)
                    # Portfolio fields are intentionally absent from a Markets
                    # projection. Verify the trade through its actual UI scope.
                    window.set_active_view("portfolio")
                    assert window.runtime.state.portfolio["STONE"]["stueck"] == 10
                    window.set_active_view("markets")
                    window._execute_trade("XAU", "FUTURE", "LONG", 100.0, 2)
                    window.set_active_view("portfolio")
                    assert len(window.state.perpetuals) == 1
                    window._close_future(next(iter(window.state.perpetuals)))
                    assert not window.state.perpetuals
                    record("Spot buy, future portfolio state and close verified")
                    window._request_simulation_steps(13, force_refresh=True)
                    stage = 2
            elif stage == 2 and not window.simulation_busy:
                assert window.state.date.strftime("%Y-%m-%d") == "1990-01-14"
                window.save_game()
                assert (Path(os.environ["KOJAKSTREET_DATA_DIR"]) / "spielstand.dat").exists()
                saved = window.runtime.deterministic_signature()
                record("Saved before monthly report")
                window._request_simulation_steps(4, force_refresh=True)
                stage = 3
            elif stage == 3 and not window.simulation_busy:
                assert window.state.date.strftime("%Y-%m-%d") == "1990-01-18"
                continued = window.runtime.deterministic_signature()
                assert continued != saved
                window.load_game()
                assert window.runtime.deterministic_signature() == saved
                record("Monthly report crossed; immediate restore verified")
                window._request_simulation_steps(4, force_refresh=True)
                stage = 4
            elif stage == 4 and not window.simulation_busy:
                assert window.runtime.deterministic_signature() == continued
                record("Four-day continuation across monthly report matches")
                window.close()
                assert window.runtime._process.poll() is not None
                record("Window closed and worker exited")
                result["passed"] = True
                app.quit()
                return
        except Exception:
            result.update(passed=False, error=traceback.format_exc())
            if window is not None:
                window.close()
            app.exit(1)
            return
        QTimer.singleShot(30, drive)

    previous_data_dir = os.environ.get("KOJAKSTREET_DATA_DIR")
    try:
        with tempfile.TemporaryDirectory(prefix="kojak-source-smoke-") as directory:
            os.environ["KOJAKSTREET_DATA_DIR"] = directory
            QTimer.singleShot(0, drive)
            result["exit"] = main([])
    finally:
        if previous_data_dir is None:
            os.environ.pop("KOJAKSTREET_DATA_DIR", None)
        else:
            os.environ["KOJAKSTREET_DATA_DIR"] = previous_data_dir
        result["seconds"] = round(time.perf_counter() - started, 3)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result.get("passed") and result.get("exit") == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.timeout))
