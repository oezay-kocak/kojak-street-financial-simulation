from __future__ import annotations

from pathlib import Path

import daten
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
from kojakstreet.ui_qt.new_simulation import GenerationProgressDialog, NewSimulationDialog
from kojakstreet.ui_qt.views.global_macro_view import GlobalMacroView


def test_new_simulation_keeps_genesis_default_and_exposes_established_options() -> None:
    dialog = NewSimulationDialog()
    assert dialog.genesis.isChecked()
    assert not dialog.established.isChecked()
    assert not dialog.years.isEnabled()
    assert dialog.config().mode is WorldMode.GENESIS

    dialog.established.click()
    assert dialog.established.isChecked()
    assert not dialog.genesis.isChecked()
    assert dialog.years.isEnabled()
    assert dialog.config().prehistory_years == 50


def test_cancel_removes_only_matching_incomplete_generation(tmp_path) -> None:
    config = WorldGenerationConfig(mode=WorldMode.ESTABLISHED, seed=7, prehistory_years=50).normalized()
    dialog = GenerationProgressDialog(config, Path.cwd(), tmp_path)
    partial = dialog.bundle_path.parent / f".{dialog.bundle_path.name}.test.partial"
    partial.mkdir(parents=True)
    unrelated = dialog.bundle_path.parent / ".unrelated.partial"
    unrelated.mkdir()

    dialog.cancel()

    assert not partial.exists()
    assert unrelated.exists()


def test_global_macro_all_requests_adaptive_history_provider() -> None:
    calls: list[tuple[str, int]] = []

    def provider(metric: str, limit: int):
        calls.append((metric, limit))
        return [
            {"date": "1990-01-01", "value": 12.0, "open": 12.0, "high": 12.0, "low": 12.0, "close": 12.0, "resolution": "yearly"},
            {"date": "2026-01-01", "value": 18.0, "open": 18.0, "high": 18.0, "low": 18.0, "close": 18.0, "resolution": "raw"},
        ]

    view = GlobalMacroView(snapshot_from_legacy(daten), provider)
    view._update_detail("vix")
    view.detail_view.set_range(0)

    assert calls[-1] == ("vix", 0)
    assert view.detail_view.chart_view.date_axis.date_mode
