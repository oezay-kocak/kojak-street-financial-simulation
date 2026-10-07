"""Read-only current-state probes; synthetic payloads are estimates, not politics code."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".cache" / "politics-ui-audit-2026-10-07"


def hashes():
    files = list((ROOT / "src" / "kojakstreet").rglob("*.py"))
    files += list((ROOT / "tests").rglob("*.py"))
    files += list(ROOT.glob("*.py"))
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}


def size(value):
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":"), default=str).encode("utf-8"))


def main():
    if (OUT / "evidence.json").exists():
        raise FileExistsError("Keep completed audit evidence; choose a fresh output directory")
    OUT.mkdir(parents=True, exist_ok=True)
    before = hashes()
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, encode
    from kojakstreet.core.economic_calendar import build_economic_calendar
    from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
    from kojakstreet.core.macro_calculations import sovereign_rating_target
    from kojakstreet.core.ratings import rating_spread
    from kojakstreet.ui_qt.views.macro_view import MacroView
    from kojakstreet.visible_state import project_visible_state
    app = QApplication.instance() or QApplication([])
    evidence = {"source_hashes_before": before, "modes": {}, "synthetic_note":
                "Politics objects below are byte-size fixtures only; no economic/UI implementation."}
    for mode in (WorldMode.GENESIS, WorldMode.HETEROGENEOUS):
        directory = OUT / mode.value.lower()
        if directory.exists():
            raise FileExistsError(directory)
        rt = IntegratedRuntime(ROOT, data_dir=directory,
                               world_config=WorldGenerationConfig(mode=mode, seed=1729))
        try:
            world_before = hashlib.sha256(json.dumps(encode(capture(rt.daten)),
                                                    sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()
            projections = {}
            for name, scope in {
                "markets": {"view": "markets"},
                "macro_overview": {"view": "macro", "selection": {"region": "Ameron", "tab": 0}},
                "population_society": {"view": "macro", "selection": {"region": "Ameron", "area": "population_society"}},
            }.items():
                state, _, timings = project_visible_state(rt, scope)
                detail = state.macro.get("Ameron", {}).get("population_society", {})
                projections[name] = {"macro_bytes": size(state.macro), "workforce_detail_bytes": size(detail),
                                     "country_count": len(state.macro), "stock_count": len(state.stocks),
                                     "product_count": len(state.processed_products),
                                     "commodity_count": len(state.commodities),
                                     "countries_with_workforce": [c for c, m in state.macro.items() if "population_society" in m or "workforce" in m],
                                     "history_count": len(state.macro_history), "timings_ms": timings}
            world_after = hashlib.sha256(json.dumps(encode(capture(rt.daten)),
                                                   sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()
            assert world_before == world_after, "Read-only projection altered checkpoint or RNG"
            state, _, _ = project_visible_state(rt, {"view": "macro"})
            widget = MacroView(state)
            tabs = [widget.detail_view.tabs.tabText(i) for i in range(widget.detail_view.tabs.count())]
            assert tabs == ["Overview", "Production", "Trade", "Sectors"]
            widget.close()
            widget.deleteLater()
            app.processEvents()
            row = {"country_count": len(rt.daten.makro), "companies": len(rt.daten.aktien),
                   "macro_fields": sorted(rt.daten.makro["Ameron"]), "projections": projections,
                   "projection_checkpoint_rng_unchanged": world_before == world_after,
                   "actual_qt_tabs": tabs, "calendar_items": len(build_economic_calendar(state)),
                   "initial_sovereign_rating": rt.daten.makro["Ameron"]["rating"],
                   "initial_sovereign_target": sovereign_rating_target(rt.daten.makro["Ameron"])}
            durations = []
            for _ in range(16):
                started = perf_counter()
                rt.advance_day()
                durations.append((perf_counter() - started) * 1000)
            row["16_day_probe"] = {"end_date": rt.daten.datum.isoformat(), "wall_ms": durations,
                                    "ordinary_day_politics_phases": [p for p, _ in rt.daten.simulation_phase_timings if "politic" in p],
                                    "population_interval_years": rt.daten.makro["Ameron"]["workforce"]["population_interval_years"]}
            evidence["modes"][mode.value] = row
        finally:
            rt.close()
    shares = [0.30, 0.20, 0.15, 0.12, 0.10, 0.08, 0.05]
    parties = [{"id": f"ameron:p{i}", "name": f"Civic Reform Alliance {i}", "vote_share": s,
                "economic_axis": -0.8 + i * 0.25, "social_axis": 0.4 - i * 0.1,
                "in_government": i < 3} for i, s in enumerate(shares)]
    synthetic = {"model_version": 1, "region": "Ameron", "activated_on": "1990-01-01",
                 "distribution_kind": "latest_election_vote_share", "distribution_date": "1990-01-01",
                 "distribution_provenance": "initial_allocation_not_election", "system": "parliamentary_democracy",
                 "stability": 75.0, "political_stability": 75.0, "government_status": "majority_coalition",
                 "government_party_ids": [p["id"] for p in parties[:3]], "next_election": "1994-01-01",
                 "government_ideology": {"economic_axis": -0.3, "social_axis": 0.1},
                 "parties": parties}
    evidence["payload_estimate"] = {"seven_party_politics_bytes": size(synthetic),
                                    "sparse_60_stability_points_bytes": size([[f"{1990+i//12}-{i%12+1:02}-15", 75.0] for i in range(60)]),
                                    "two_party_politics_bytes": size({**synthetic, "parties": parties[:2]})}
    evidence["rating_fanout_probe"] = {rating: rating_spread(rating) for rating in ("BBB+", "BBB", "BBB-")}
    anchors = {}
    for relative in before:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                anchors[f"{relative}:{node.name}"] = node.lineno
    evidence["source_anchors"] = anchors
    after = hashes()
    evidence["source_files_changed_by_audit"] = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
    assert evidence["source_files_changed_by_audit"] == []
    (OUT / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"evidence": str(OUT / "evidence.json"), "modes": list(evidence["modes"]),
                      "source_changes": evidence["source_files_changed_by_audit"],
                      "payload": evidence["payload_estimate"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
