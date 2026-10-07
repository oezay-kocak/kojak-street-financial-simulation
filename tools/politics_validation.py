"""Isolated production probes and readable offscreen UI evidence for Politics V1."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from collections import Counter
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/politics-implementation"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def describe(values):
    values = sorted(values)
    return {"count": len(values), "median": statistics.median(values),
            "p95": values[int((len(values)-1)*.95)], "max": max(values)} if values else None


def economic_digest(state):
    from kojakstreet.core.checkpoints import capture, encode
    saved = capture(state)
    saved.pop("save_version")
    saved["checkpoint"].pop("politics_calendar", None)
    saved["checkpoint"].pop("world_generation", None)
    # Politics news is an intentional presentation output; all economic/player
    # books, histories, prior news and both global RNG states remain compared.
    for macro in saved["checkpoint"]["makro"].values():
        macro.pop("politics", None)
    for key in ("NEWS_SPEICHER", "PLAYER_NEWS_SPEICHER"):
        if key in saved["checkpoint"]:
            saved["checkpoint"][key] = [n for n in saved["checkpoint"][key] if "POLITICS:" not in str(n)]
    payload = json.dumps(encode(saved), ensure_ascii=False, sort_keys=True, allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def run(args, source, directory):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.world_generator import _peak_rss_bytes
    rt = IntegratedRuntime(source, data_dir=directory / "data", seed=1729)
    result = {"reference": args.reference, "years": args.years}
    try:
        rt.data_store.enable_background_flush()
        if args.years:
            from kojakstreet.core.fast_history import generate_coarse_history
            wall, cpu = time.perf_counter(), time.process_time()
            plan = generate_coarse_history(rt, 1729, args.years, burn_in_days=365)
            result["coarse_seconds"] = time.perf_counter()-wall
            result["coarse_cpu_seconds"] = time.process_time()-cpu
            result["coarse_economic_digest"] = economic_digest(rt.daten)
            days = plan.daily_days
            print(f"{args.label}: coarse completed, burn-in {days}", flush=True)
        else:
            days = 90
            if not args.reference:
                from kojakstreet.core import politics
                rt.daten.makro["Ameron"]["politics"]["next_election"] = "1990-01-10"
                politics.rebuild_calendar(rt.state)
        rows = []
        wall, cpu = time.perf_counter(), time.process_time()
        for i in range(days):
            when = rt.daten.datum
            t, c = time.perf_counter(), time.process_time()
            rt.advance_day()
            phases = {item["phase"]: item["duration_ms"] for item in rt.daten.simulation_phase_timings}
            rows.append({"date": when.isoformat(), "report": when.day == 15,
                         "election": "political_events" in phases,
                         "wall_ms": (time.perf_counter()-t)*1000,
                         "cpu_ms": (time.process_time()-c)*1000,
                         "monthly_politics_ms": phases.get("monthly_politics"),
                         "political_events_ms": phases.get("political_events")})
            if (i+1) % 90 == 0:
                print(f"{args.label}: {i+1}/{days}", flush=True)
        result["daily_seconds"] = time.perf_counter()-wall
        result["daily_cpu_seconds"] = time.process_time()-cpu
        result["days"] = rows
        result["ordinary"] = {kind: describe([r[kind] for r in rows if not r["report"] and not r["election"]]) for kind in ("wall_ms", "cpu_ms")}
        result["reports"] = describe([r["wall_ms"] for r in rows if r["report"]])
        result["elections"] = describe([r["wall_ms"] for r in rows if r["election"]])
        result["monthly_politics_ms"] = describe([r["monthly_politics_ms"] for r in rows if r["monthly_politics_ms"] is not None])
        result["event_phase_ms"] = describe([r["political_events_ms"] for r in rows if r["political_events_ms"] is not None])
        result["economic_digest"] = economic_digest(rt.daten)
        result["peak_rss_bytes"] = _peak_rss_bytes()
        writer = rt.data_store._writer
        result["writer_queue_depth"] = writer.jobs.qsize()
        result["writer_capacity"] = writer.jobs.maxsize
        rt.data_store.flush()
        rt.data_store.wait_for_persistence()
        metrics = list(writer.metrics)
        result['writer_metrics'] = {key: describe([m[key] for m in metrics if key in m])
                                    for key in ('writer_ms', 'backpressure_ms', 'queue_wait_ms', 'queue_depth')}
        if not args.reference:
            from kojakstreet.core import politics
            from kojakstreet.live_process import game_state_payload
            from kojakstreet.visible_state import project_visible_state
            p = rt.daten.makro["Ameron"]["politics"]
            result['politics_current_json_bytes'] = sum(len(politics.json_text(m['politics']).encode()) for m in rt.daten.makro.values())
            samples, formation = [], []
            for _ in range(100):
                t = time.perf_counter()
                selected, _, _ = project_visible_state(rt, {"view": "macro", "selection": {"region": "Ameron", "area": "society_politics"}})
                samples.append((time.perf_counter()-t)*1000)
                t = time.perf_counter()
                politics.form_government(p)
                formation.append((time.perf_counter()-t)*1000)
            result["selected_projection_ms"] = describe(samples)
            result["coalition_ms"] = describe(formation)
            result["selected_macro_bytes"] = len(json.dumps(selected.macro, separators=(",", ":")).encode())
            result["selected_payload_bytes"] = len(json.dumps(game_state_payload(selected), separators=(",", ":")).encode())
            result["politics"] = {c: {k: m["politics"][k] for k in ("system", "sequence", "last_election", "last_review", "next_election", "political_stability", "stability", "government_status", "premium")} for c, m in rt.daten.makro.items()}
            for table in ("country_politics_current", "country_politics_monthly", "politics_events"):
                result[table+"_rows"] = rt.data_store._connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            if args.years == 5:
                before = {c: json.dumps(m["politics"], sort_keys=True) for c, m in rt.daten.makro.items()}
                rt.save_game()
                rt.load_game()
                assert before == {c: json.dumps(m["politics"], sort_keys=True) for c, m in rt.daten.makro.items()}
                result["established_save_load_politics_exact"] = True
        write(directory / "result.json", result)
        print(json.dumps({k: v for k, v in result.items() if k not in ("days", "politics")}), flush=True)
    finally:
        rt.close()


def visuals(args, source, directory):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.ui_qt.app import KojakStreetWindow
    from kojakstreet.ui_qt.theme import APP_STYLESHEET
    from kojakstreet.visible_state import project_visible_state
    app = QApplication([])
    for font in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf"):
        assert QFontDatabase.addApplicationFont("C:/Windows/Fonts/"+font) >= 0
    app.setStyleSheet(APP_STYLESHEET)
    rt = IntegratedRuntime(source, data_dir=directory / "data", seed=1729)
    try:
        state, _, _ = project_visible_state(rt, {"view": "macro"})
        shell = KojakStreetWindow(rt.snapshot(), rt)
        shell.set_active_view("macro")
        macro_view = shell.views["macro"]
        view = macro_view.detail_view
        view.scope_provider = lambda scope: project_visible_state(rt, scope)[0]
        view.scope_changed = lambda state: None
        view.update_region("Ameron", state)
        macro_view.pages.setCurrentWidget(view)
        shell.resize(1400, 1200)
        shell.show()
        rows = []

        def shot(name, tab, width=1400, height=1200):
            shell.resize(width, height)
            shell.workspace_scroll.horizontalScrollBar().setValue(0)
            view.tabs.setCurrentIndex(tab)
            selection = {"region": "Ameron", "area": "society_politics"} if tab == 4 else {"region": "Ameron", "tab": tab}
            view.refresh(project_visible_state(rt, {"view": "macro", "selection": selection})[0])
            app.processEvents()
            shell.repaint()
            app.processEvents()
            assert shell.grab().save(str(directory / (name+".png")))
            if tab == 4 and view.society_panel.verticalScrollBar().maximum():
                view.society_panel.verticalScrollBar().setValue(view.society_panel.verticalScrollBar().maximum())
                app.processEvents()
                shell.grab().save(str(directory / (name+"-lower.png")))
                view.society_panel.verticalScrollBar().setValue(0)
            rows.append({"name": name, "width": shell.width(), "height": shell.height()})

        for tab, name in enumerate(("overview", "production", "trade", "sectors")):
            shot(name, tab)
        if not args.reference:
            from kojakstreet.core import politics as p
            shot("01-genesis-initial", 4)
            macro = rt.daten.makro["Ameron"]
            cases = [("02-heterogeneous-coalition", "parliamentary_democracy"),
                     ("03-presidential", "presidential_democracy"),
                     ("04-semi-presidential-cohabitation", "semi_presidential_democracy"),
                     ("05-absolute-monarchy", "absolute_monarchy"),
                     ("06-one-party", "one_party_state"),
                     ("07-authoritarian", "authoritarian_republic")]
            for name, system in cases:
                feature = p.create(11, "Ameron", date(1990, 1, 1), macro, heterogeneous=True, system=system)
                macro["politics"] = feature
                if p.SYSTEMS[system][2] and system != "parliamentary_democracy":
                    # Authentic simulator result, with a controlled formation fixture.
                    shares = [.4, .3, .2, .1]
                    feature = p.create(11, "Ameron", date(1990, 1, 1), macro, system=system)
                    macro["politics"] = feature
                    axes = [.95, -.4, -.3, -.2] if "semi" in system else [-.6, -.2, .2, .6]
                    for party, share, axis in zip(feature["parties"], shares, axes, strict=True):
                        party["mandate_share"] = share
                        party["economic_axis"] = axis
                    p.election(rt.state, "Ameron", feature, date(1994, 1, 1))
                    if "semi" in system:
                        assert feature["executive_id"] not in feature["government_ids"]
                elif system == "parliamentary_democracy":
                    for seed in range(100):
                        feature = p.create(seed, "Ameron", date(1990, 1, 1), macro, heterogeneous=True, system=system)
                        macro["politics"] = feature
                        p.election(rt.state, "Ameron", feature, date(1994, 1, 1))
                        if feature["government_status"] == "majority_coalition":
                            break
                    assert feature["government_status"] == "majority_coalition"
                p.refresh_components(feature, date(1994, 1, 1), macro)
                shot(name, 4)
            shot("08-narrow", 4, 1080, 720)
            shot("09-large", 4, 1920, 1400)
            panel = view.society_panel
            samples = []
            for _ in range(100):
                t = time.perf_counter()
                panel.apply_data("Ameron", view._current_macro["population_society"], view._current_macro["society_politics"])
                samples.append((time.perf_counter()-t)*1000)
            write(directory / "patch-cost.json", {"set_data_ms": describe(samples), "stable_widget_id": id(panel), "captures": rows})
        shell.close()
        write(directory / "captures.json", rows)
    finally:
        rt.close()


def distributions(args, source, directory):
    from kojakstreet.core import politics, workforce
    from kojakstreet.core.companies import BRANCHEN
    from kojakstreet.core.countries import COUNTRY_SYMBOLS
    from kojakstreet.core.heterogeneous_start import _correlation, generate_roots
    countries = list(COUNTRY_SYMBOLS)
    rows = []
    for seed in range(200):
        roots = generate_roots(seed, countries, BRANCHEN)
        for country in countries:
            feature = politics.create(seed, country, date(1990, 1, 1), {}, heterogeneous=True)
            politics.validate(feature)
            shares, births, deaths = workforce.country_roots(seed, country, heterogeneous=True)
            rows.append({"system": feature["system"], "party_count": len(feature["parties"]),
                         "base": feature["base"], "political_stability": feature["political_stability"],
                         "economic_axis": feature["leadership_axes"][0], "social_axis": feature["leadership_axes"][1],
                         "population": roots.population[country], "gdp_per_capita": roots.gdp[country]/roots.population[country],
                         "birth_rate": births, "death_rate": deaths, "qualified_share": shares["highly_qualified"]})
    correlations = {}
    for political in ("party_count", "base", "political_stability", "economic_axis", "social_axis", *politics.SYSTEMS):
        left = [int(r["system"] == political) if political in politics.SYSTEMS else r[political] for r in rows]
        correlations[political] = {economic: _correlation(left, [r[economic] for r in rows])
                                  for economic in ("population", "gdp_per_capita", "birth_rate", "death_rate", "qualified_share")}
    write(directory / "result.json", {"seeds": 200, "countries": len(countries), "sample_count": len(rows),
          "systems": dict(Counter(r["system"] for r in rows)), "party_counts": dict(Counter(r["party_count"] for r in rows)),
          "correlations": correlations, "maximum_absolute_correlation": max(abs(v) for row in correlations.values() for v in row.values())})


def sealed_reference(args, source, directory):
    assert args.reference
    from kojakstreet.world_generator import generate
    with (directory / "generation.log").open("w", encoding="utf-8") as log, redirect_stdout(log):
        bundle = generate(source, directory / "bundle", 1729, 50, burn_in_days=1)
    print(str(bundle), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--label", required=True)
    parser.add_argument("--years", type=int, default=0)
    parser.add_argument("--visuals", action="store_true")
    parser.add_argument("--distributions", action="store_true")
    parser.add_argument("--sealed-reference", action="store_true")
    args = parser.parse_args()
    source = OUT / "baseline" if args.reference else ROOT
    sys.path[:0] = [str(source / "src"), str(source)]
    directory = OUT / args.label
    directory.mkdir(parents=True, exist_ok=False)
    action = sealed_reference if args.sealed_reference else visuals if args.visuals else distributions if args.distributions else run
    action(args, source, directory)


if __name__ == "__main__":
    main()
