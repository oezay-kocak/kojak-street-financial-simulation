"""Build the phase-one report from retained audit records; fail on missing data."""
from __future__ import annotations

import hashlib
import json
import pstats
from pathlib import Path
import statistics
from datetime import date, timedelta
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/ui-state-architecture-audit"
REPORT = ROOT / "docs/ui-state-architecture-audit-2026-10-06.md"


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def med(values):
    return statistics.median(values)


def number(value):
    return f"{value:,.2f}"


def qt_rows(name):
    result = read(name + ".json")
    workers = [json.loads(line) for line in (OUT / (name + "-worker.jsonl")).read_text(encoding="utf-8").splitlines()]
    assert result["finished"] and not result["errors"] and result["worker_exited"]
    assert len(result["rows"]) == len(workers)
    for row, worker in zip(result["rows"], workers):
        assert row["date"] == worker["date"]
        points = [row["t0"], worker["t1"], row["t2"], row["t3"], row["t4"]]
        assert all(a <= b for a, b in zip(points, points[1:]))
        assert all(row[k] for k in ("request_is_qt_main", "slot_is_qt_main", "update_is_qt_main"))
        row["worker"] = worker
    return result


def normal(rows):
    return [r for r in rows if date.fromisoformat(r["date"]).day != 15 and
        (date.fromisoformat(r["date"]) + timedelta(days=1)).month == date.fromisoformat(r["date"]).month and
        not r["worker"]["spans"].get("store.flush", 0)]


def metric(rows, name, where="parent_spans"):
    return med(r[where].get(name, 0) for r in rows)


def group_class(name):
    if name == "global_status":
        return "A", "Date/cash/currency; topbar", "Yes"
    if name.endswith(".quotes_metadata"):
        return "B (+A derived ticker)", "Market table/filter/sort; ticker uses only ranked quotes", "Yes, except products"
    if name.endswith(".simulation_internal"):
        return "G", "Engine only; no direct displayed consumer", "No"
    if name.endswith(".price_history"):
        return "C/D", "Selected preview/chart; portfolio selected holding", "No without selection"
    if name.endswith(".other_history"):
        return "C/D", "Selected supply/positioning/product history", "No"
    if name.endswith(".psychology"):
        return "C/D (+G unused components)", "Selected positioning/long-short charts", "No"
    if name == "stocks.input_output":
        return "C/D/B", "Selected company supply; Supply Chain", "No"
    if name == "macro.history":
        return "C/D", "Selected country/product production/trade charts", "No"
    if name == "macro.current_trade":
        return "B/C/D (+G unused fields)", "Macro/Trade Map/News; selected company related products", "Country names only"
    if name == "funds.allocations_flows_fees":
        return "C/D", "Selected fund allocations/overview", "No"
    if name.endswith(".detail_internal"):
        return "C/D/B (+G unused fields)", "Selected fundamentals/details; related active views", "No"
    consumers = {
        "portfolio": ("B/E", "Portfolio positions; selected sell validation"),
        "perpetuals": ("B/E", "Portfolio/future controls"),
        "fx_balances": ("B/E", "Portfolio/Forex; selected trade validation"),
        "loans": ("B", "Portfolio loan total"),
        "bonds": ("B/C", "Portfolio owned-bond detail"),
        "bond_market": ("B/C/D", "Bond Market table; selected bond chart; held-bond valuation"),
        "news": ("B/C/D", "News feed/calendar; Macro economic context"),
        "macro_history": ("B/C/D", "News calendar historical values; selected country chart"),
        "global_macro": ("B/C", "Global Macro dashboard"),
        "global_macro_history": ("B/C/D", "Global Macro visible indicator charts"),
        "forex_history": ("C/D", "Selected Forex chart"),
        "currency_strength": ("B/C/E", "Forex/Portfolio conversions; selected trade/labels"),
        "portfolio_history": ("B/D", "Portfolio analytics history"),
        "realized_pnl_history": ("B/D", "Portfolio analytics realized return"),
    }
    cls, consumer = consumers[name]
    return cls, consumer, "No (selected trade/conversion may need subset)" if name == "currency_strength" else "No"


def main():
    detailed = read("sections-mature-detailed.json")
    rows = detailed["rows"]
    young_sections = read("sections-young.json")["rows"]
    allocation = read("sections-mature-allocations.json")["rows"][0]
    native = qt_rows("qt-native-markets")
    control = qt_rows("qt-native-paint-control")
    mature_ui = qt_rows("qt-nine-views-mature")
    young_ui = qt_rows("qt-nine-views-young")
    render_profile = qt_rows("qt-native-render-profile")
    rendered = render_profile["rows"][0]
    test_suite = ElementTree.parse(OUT / "focused-tests.xml").getroot().find("testsuite")
    assert test_suite is not None
    assert int(test_suite.attrib["failures"]) == 0 and int(test_suite.attrib["errors"]) == 0
    test_count = int(test_suite.attrib["tests"])
    test_seconds = float(test_suite.attrib["time"])
    profile_stats = pstats.Stats(str(OUT / "ui-profile-qt-native-render-profile-0.pstats"))
    draw_calls = sum(v[1] for (filename, line, name), v in profile_stats.stats.items() if "drawText" in name)
    item_loops = sum(v[1] for (filename, line, name), v in profile_stats.stats.items() if name == "_draw_items")
    ticker_paints = sum(v[1] for (filename, line, name), v in profile_stats.stats.items() if name == "paintEvent" and "top_bar.py" in filename)
    assert native["signature"] == control["signature"]
    expected = read("environment-qt-mature-markets.json")["source_sha256"]
    current = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "src").rglob("*.py")}
    assert expected == current
    previous_path = ROOT / ".cache/performance-remediation/reaudit"
    previous = json.loads((previous_path / "environment-qt-mature-none-valid.json").read_text())
    assert expected == previous["source_sha256"]
    group_names = sorted(rows[0]["groups"])
    required = [k for k in group_names if k == "global_status" or k.endswith(".quotes_metadata") and not k.startswith("processed_products")]
    shares = []
    for row in rows:
        groups = row["groups"]
        cost = lambda g: g["diff"]["ms"] + g["encode"]["ms"]
        shares.append({"invisible_processing_pct": 100 * (1 - sum(cost(groups[k]) for k in required) / sum(cost(g) for g in groups.values())),
            "required_dictionary_visits_pct": 100 * sum(groups[k]["traversal"].get("dictionary_fields_visited", 0) for k in required) / sum(g["traversal"].get("dictionary_fields_visited", 0) for g in groups.values()),
            "required_emitted_scalars_pct": 100 * sum(groups[k]["output"].get("scalar_values", 0) for k in required) / sum(g["output"].get("scalar_values", 0) for g in groups.values()),
            "required_isolated_wire_pct": 100 * sum(groups[k]["wire_bytes_isolated"] for k in required) / sum(g["wire_bytes_isolated"] for g in groups.values()),
            "required_decode_reconstruction_pct": 100 * sum(groups[k]["decode"]["ms"] for k in required) / sum(g["decode"]["ms"] for g in groups.values())})
    summary = {"production_source_unchanged": True, "previous_baseline_source_identical": True,
        "exact_native_control_signature_match": True, "consumer_shares": {k: med(s[k] for s in shares) for k in shares[0]},
        "focused_tests_passed": test_count,
        "native_render_profile": {"ticker_paints": ticker_paints, "item_loops": item_loops, "draw_text_calls": draw_calls, "ticker_pending_at_t4": rendered["ticker_pending_at_t4"], "ticker_current_matches_worker_at_t4": rendered["ticker_current_matches_worker_at_t4"], "ticker_tile_width": rendered["ticker_tile_width"]},
        "qt_samples_checked": sum(len(r["rows"]) for r in (native, control, mature_ui, young_ui)),
        "native": {}, "minimal_observer_control": {}}
    for result, label in ((native, "native"), (control, "minimal_observer_control")):
        rs = normal(result["rows"])
        summary[label] = {"n": len(rs), "T0_T4_ms": med(r["total_ms"] for r in rs), "decode_ms": metric(rs, "parent.decode_day_delta"),
            "decode_cpu_ms": metric(rs, "decode.thread_cpu"), "decompress_ms": metric(rs, "decode.decompress"),
            "max_heartbeat_gap_ms": max(max(r["heartbeat_gaps_ms"][1:], default=0) for r in rs)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    text = ["# Kojak Street — Phase 1 UI-state architecture audit", "", "Date: 6 October 2026 (Europe/Berlin). Scope: audit only. No production source, economics, RNG, save format, database contract or normal tick contract changed.", "",
        "**Verdict: the broad-mirror hypothesis is supported. Proceed to a minimal contract design; the performance target is not yet achieved.** The worker compares and encodes public state for the entire economy irrespective of the visible view. A substantial majority of that work has no displayed consumer during an unselected Markets tick. Native ticker rendering also causes reader contention, and the existing T4 boundary does not guarantee current displayed ticker values. The mature Markets switch path is independently slow. These findings prevent treating a smaller delta alone as a solved fluid/correct UI.", "",
        "## Evidence and measurement boundaries", "",
        "All measurements used isolated copied checkpoints and DuckDB files under `.cache/ui-state-architecture-audit/`. Seed 1729; mature checkpoint `end` (1 January 1991); young checkpoint 10 January 1990. The current production source hashes match both the start of this audit and the retained performance-remediation baseline. Existing uncommitted production changes predate this audit and were left intact.", "",
        "Excluded diagnostic: the first minimal-observer attempt observed only the table viewport and never saw a qualifying post-update paint; it timed out with zero completed samples. `qt-native-minimal-observer.*` is retained as a failed measurement, not a gameplay hang or performance evidence. The successful control additionally observes the ticker and central widget.", "",
        "Fresh runs: 20 mature native-window Markets ticks; 20 matching native ticks with targeted viewport/ticker/central-widget paint observers; 27 mature and 27 young offscreen ticks rotating all nine views; separate section/profile/allocation diagnostics. Normal UI requests call the actual `_on_timer_tick()`. T0 is the request, T1 core completion, T2 parent apply completion, T3 active UI update completion, T4 the next heartbeat after an observed paint and pending UI/chart/history work. Setup, intentional game-day waits and view switches are outside tick latency. Switching is measured separately.", "",
        "The 10 ms heartbeat gap is an event-loop responsiveness measurement, including GIL/scheduling delay; it is not an exact pure Qt-slot block. Offscreen rows do not establish native desktop feel. Category diff/encode/decode values are isolated replays of the unchanged algorithm on disjoint field groups. The actual wire mixes groups in compressed chunks, so category bytes/times are contribution estimates and must not be added to predict T0→T4. Small category bodies are deliberately measured with the same binary codec. Dictionary visits are counted; sequence lengths are comparison candidates, not claimed exact C-level equality comparisons. Allocation diagnostics are separate and their latencies are excluded.", "",
        "## Current normal-tick path", "",
        "`QTimer → _on_timer_tick → Qt SimulationWorker → LiveSimulationProcess.advance_days(status) → worker advance → complete economic simulation → record_day → status snapshot + current_rows + full public snapshot → DayStateEncoder full recursive diff + binary encoding → JSON/pipe → parent reader JSON/decompress/unpickle → apply_day_delta to full canonical GameState → active UI update → paint/heartbeat`.", "",
        "The worker owns the complete authoritative economy, **and** a detached full public comparison baseline. The parent owns a full canonical public world, current-row tables, UI row copies and bounded chart caches. `_snapshots` view keys converge on the same full canonical object after applying a delta. Hidden main widgets remain idle, but their state is still synchronized. `_runtime_result` ignores the requested active-view profile for daily selection and explicitly calls `snapshot_for_view('full')`; there is no hidden full-snapshot wire fallback on normal ticks.", "",
        "`snapshot_for_view(view_key)` in the parent is a local lookup. Opening a main view, entity or sub-tab does not currently ask the worker for current detail state. Deep history already has a separate background request path, but current detail fields depend on the broad mirror.", "",
        "## Measured timer latency and decode attribution", "",
        "Mature normal days, excluding the reporting day; medians in milliseconds. The retained 1.85 s result is a prior measurement of the identical source, not a new before/after implementation comparison.", "",
        "| Metric | Fresh native, global event observer | Fresh native, minimal paint observer |", "|---|---:|---:|"]
    nrs, crs = normal(native["rows"]), normal(control["rows"])
    for title, fn in (
        ("T0→T4", lambda r: r["total_ms"]),
        ("Simulation core", lambda r: r["worker"]["spans"]["simulation.core"]),
        ("Full public snapshot preparation", lambda r: r["worker"]["spans"]["snapshot.copy"]),
        ("worker.day_delta (diff + encoding + cleanup)", lambda r: r["worker"]["spans"]["worker.day_delta"]),
        ("Parent decode wall time", lambda r: r["parent_spans"]["parent.decode_day_delta"]),
        ("Reader decode thread CPU", lambda r: r["parent_spans"]["decode.thread_cpu"]),
        ("Decompression wall time", lambda r: r["parent_spans"]["decode.decompress"]),
        ("Unpickle", lambda r: r["parent_spans"]["decode.unpickle"]),
        ("Base64", lambda r: r["parent_spans"]["decode.base64"]),
        ("Decode gen-0 collection", lambda r: r["parent_spans"]["decode.gc0"]),
        ("Decode gen-1 collection", lambda r: r["parent_spans"]["decode.gc1"]),
        ("Explicit sleep(0) yield", lambda r: r["parent_spans"]["decode.yield"]),
        ("Apply delta", lambda r: r["parent_spans"]["parent.apply_day_delta"]),
        ("Active UI update", lambda r: r["parent_spans"]["ui.live_update"]),
        ("T4−T2", lambda r: (r["t4"]-r["t2"])*1000)):
        text.append(f"| {title} | {number(med(fn(r) for r in nrs))} | {number(med(fn(r) for r in crs))} |")
    text += [f"| Largest complete heartbeat gap | {number(summary['native']['max_heartbeat_gap_ms'])} | {number(summary['minimal_observer_control']['max_heartbeat_gap_ms'])} |", "",
        f"Median native response: {number(med(r['worker']['response_bytes'] for r in nrs)/1_000_000)} MB. No architecture change is represented by these columns. The minimal observer changes measurement coverage only; it preserves the same production worker/UI and produces an exactly equal final economics/RNG signature.", "",
        "**Cause of the ~635 ms generation span:** recursive dictionary traversal of the complete public world; history equality and prefix/rollover slicing for every series; detached changed-value copies; tens of thousands of path/update/splice objects; per-object persistent-ID checks while pickling; compression and cleanup. Explicit top-level section timers and separate profiles show company state and regional histories dominate. Generation is not simply JSON serialization. The full snapshot preparation cost precedes the day-delta timer and must also disappear from a compact normal-tick path.", "",
        "**Cause of the ~501 ms decode span:** it is elapsed reader-thread time, not 501 ms of JSON parsing or object reconstruction. Fresh native measurements put most wall time in `zlib.decompress`; isolated decoding spends only a few milliseconds in the same decompression. zlib releases the GIL, so this span includes waiting to resume alongside Qt/Python activity. Unpickling and gen-1 collection add real costs. The native observer control above distinguishes measurement overhead from actual desktop contention; attributing the entire 501 ms to invisible field decoding would be incorrect. The retained baseline's median gen-1 collection is about 37 ms, not 500 ms. Explicit `sleep(0)` is small in the new native run.", "",
        "Generation profile/raw decoder component timing: `generation-mature-detailed.txt`, `decode-mature-detailed.txt`, corresponding `.pstats`, and per-chunk/CPU spans in native records. Profiler wall times are diagnostic only. Thread CPU on Windows has coarse sampling resolution; do not infer precise sub-millisecond CPU costs from its small-section values.", "",
        "### Native rendering and visible correctness", "",
        f"The separate native rendering profile observed **{ticker_paints} ticker paints, {item_loops} complete item loops and {draw_calls:,} `QPainter.drawText` calls in one diagnostic tick**. `TickerTape.paintEvent` draws two whole long tiles, and `_draw_items` formats/measures/draws every item even when it is outside the clipped viewport. The initial ticker contains {rendered['ticker_count']} items. The profile identifies text drawing and font-width calculation as large costs. Its overlapping Qt/reader/wait spans are not additive or exclusive per-thread CPU attribution; use call counts plus the explicit reader thread CPU/native-offscreen controls as evidence. The minimized observer does not remove this contention.", "",
        f"At the conventional T4 boundary, `ticker_pending_at_t4` is **{rendered['ticker_pending_at_t4']}** and displayed current items match the worker's current ticker values is **{rendered['ticker_current_matches_worker_at_t4']}**. `TickerTape.set_items` buffers replacements; `scroll` applies them only at an entire tile wrap. The measured tile is {rendered['ticker_tile_width']:,} pixels wide. At two pixels per nominal 66 ms timer callback, a complete cycle is approximately {rendered['ticker_tile_width']/2*.066/60:.1f} minutes (remaining time depends on offset; scheduling can extend it). This is existing stale visible ticker behavior, not an optimization introduced by this audit.", "",
        "Consequently the reported T0→T4 samples mean the existing active-view/paint-ready boundary, **not proven time until every visible global value is current**. Active-view date/receiver state are checked; ticker correctness explicitly fails this stronger boundary. Time until current ticker values appear was not waited out or claimed measured. A later implementation must make current visible ticker values correct promptly and avoid drawing/measuring invisible ticker items, while preserving the ticker product's intended contents/ranking. Narrowing world synchronization cannot by itself fix this native rendering/correctness issue.", "",
        "### Full encoder section timings", "",
        f"The first mature detached public mirror contains {rows[0]['public_mirror']['dict_fields']:,} dictionary fields, {rows[0]['public_mirror']['history_points']:,} history points and {rows[0]['public_mirror']['scalar_values']:,} scalar values. The profiled unchanged generation visits 29,410 mapping calls and 40,730 sequence calls; it performs 781,002 persistent-ID callbacks during pickling. The first daily body contains {rows[0]['encode']['operations']:,} operations. Those counters explain why an append-only wire delta still incurs broad preparation work.", "",
        "These are timers inside the actual full encoder, rather than partitioned replays. They measure diff traversal/copy work only; binary encoding and cleanup are separate. Medians from three mature isolated diagnostic updates:", "",
        "| Actual full encoder component | Median ms |", "|---|---:|"]
    for section in rows[0]["sections"]:
        text.append(f"| Diff `{section}` | {number(med(r['sections'][section]['diff_ms'] for r in rows))} |")
    text += [f"| Binary encode of mixed full changes | {number(med(r['encode']['ms'] for r in rows))} |",
        f"| Whole isolated update, including encode/cleanup | {number(med(r['day_delta']['ms'] for r in rows))} |", "",
        "## Consumer matrix", "",
        "A globally live; B active main view; C selected entity/detail; D visible sub-tab; E explicit action; F Save/Restore/Debug; G simulation-internal. Categories below partition the current public world. C/D rows may contain fields requiring a narrower allowlist; only the consumer's actual displayed dependencies should be extracted. Ticker ranking requires worker-side access to all candidates, not parent synchronization of all candidate histories.", "",
        "Payload is isolated encoded daily category KiB, not a full snapshot size. Diff/encode/decode are isolated median milliseconds over three mature ticks. Decode here is reconstruction with automatic GC disabled; real full-reader collection/scheduling costs are in the native table above.", "",
        "| State category | Class | Consumers | Visible on unselected Markets | KiB/day | Diff ms | Encode ms | Decode ms | Proposed ownership |", "|---|---|---|---|---:|---:|---:|---:|---|"]
    for name in group_names:
        values = [r["groups"][name] for r in rows]
        cls, consumer, visible = group_class(name)
        ownership = "Worker; send status" if cls == "A" else "Worker only" if cls == "G" else "Worker; explicit active projection / on-open read"
        text.append(f"| {name} | {cls} | {consumer} | {visible} | {number(med(v['wire_bytes_isolated'] for v in values)/1024)} | {number(med(v['diff']['ms'] for v in values))} | {number(med(v['encode']['ms'] for v in values))} | {number(med(v['decode']['ms'] for v in values))} | {ownership} |")
    text += ["| Deep history | C/D/E/F | Requested ALL/chart history; persistence | No | Not in normal delta | — | — | — | Worker/store; request selected series |",
        "| Private caches / RNG / save-only checkpoint fields | G/F | Engine / checkpoint / deterministic debug | No | 0 | Private keys skipped | 0 | 0 | Worker/checkpoint only |",
        "| Event / phase rows | B/E/F | News economic context / debug telemetry | No | See current-row appendix | — | JSON | JSON | Worker; explicit consumer only |", "",
        "Global portfolio summary: the actual topbar shows **cash**, not NAV/gross exposure/positions. Cash is already a precomputed status scalar. Portfolio full positions/loans/FX/owned bonds are B/C/E, not automatically A. Selected trade controls need only relevant position/balance/rate/contract rules; authoritative validation already has a worker command. A currency conversion may require the selected region and GD/XAU strength, not every FX history.", "",
        "Company quantity histories and market product supply/demand are used when a company Supply Chain tab is open. Fund allocation detail currently resolves constituent names/weights across stocks, indices and bonds; a worker-side selected-fund projection can resolve these references once. This does not require synchronizing their equivalent full details in the parent. Some existing detail constructors call `ensure_*_fundamentals` on UI copies; replacing those initializers with authoritative selected display values belongs in shell/consumer adaptation, not economic formula changes.", "",
        "## Traversal, emitted data and allocations by category", "",
        "This appendix records actual dictionary visit counts, available sequence slots, emitted scalar leaves, emitted history tail points, and separate traced net allocations. Net retained blocks/bytes are not total lifetime allocation counts; transient peak bytes are also retained in JSON. Exact C-level list/tuple comparator counts are not available without changing equality semantics.", "",
        "| Category | Entities | Dict fields visited | Sequence comparison slots | Scalars emitted | History tail points | Traced net KiB | Net blocks |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name in group_names:
        g = rows[0]["groups"][name]
        a = allocation["groups"][name]["allocations"]
        text.append(f"| {name} | {g['entities']:,} | {g['traversal'].get('dictionary_fields_visited',0):,} | {g['traversal'].get('sequence_slots_available_for_comparison',0):,} | {g['output'].get('scalar_values',0):,} | {g['history_tail_points']:,} | {number(a['net_bytes']/1024)} | {a['net_blocks']:,} |")
    text += ["", "## Actual daily current-row transport", "",
        "Besides the delta, ordinary mature ticks transmit `asset_current`, `product_current`, `forex_current`, `bond_current` and `phase_metric_current`. Bond/FX rows travel even when Markets is visible. Other tables below exist as worker materializations and are sent when their changed-table flags require it, not necessarily every day. On-open selection should reuse authoritative worker data or explicit read extraction, without adding a second mirror.", "",
        "| Table | Rows available | JSON KiB | Ordinary diagnostic day emitted? | Extract ms | Markets consumer |", "|---|---:|---:|---|---:|---|"]
    for name, info in rows[0]["current_rows"].items():
        consumer = "Quotes/ticker (contains more than the displayed fields)" if name == "asset_current" else "None without selected detail"
        text.append(f"| {name} | {info['rows']:,} | {number(info['json_bytes']/1024)} | {info['emitted_today']} | {number(info['ms'])} | {consumer} |")
    shares = summary["consumer_shares"]
    text += ["", "## Share needed by the active UI", "",
        f"For Markets with no selected instrument/chart, a conservative upper bound includes quote/metadata fields for **every** market-table instrument, even hidden asset types, plus status. It excludes product rows and country details. This subset accounts for {number(shares['required_dictionary_visits_pct'])}% of category dictionary visits, {number(shares['required_emitted_scalars_pct'])}% of emitted scalar values, {number(shares['required_isolated_wire_pct'])}% of isolated delta bytes, and {number(shares['required_decode_reconstruction_pct'])}% of isolated reconstruction cost. **{number(shares['invisible_processing_pct'])}% of isolated diff+encode cost is outside that subset.** These are diagnostic shares, not a promised equivalent fraction of total native latency.", "",
        "The visible filtered table does need fresh quotes for correct sorting/filtering and for rows revealed by scrolling. Sending only the viewport's displayed rows without maintaining correct sort/filter results would be wrong. The all-instruments upper bound avoids claiming gains from dropping those dependencies. Static metadata need not be retransmitted daily except for relevant topology/metadata changes.", "",
        "An audit-only read extraction from authoritative engine objects, with no full snapshot or recursive diff, measured:", "",
        "| Read-only projection | Median ms / bytes |", "|---|---:|"]
    probes = [r["read_projection"] for r in rows]
    for label, fn in (("All market-table rows + pre-ranked ticker + status extraction", lambda p:p["extract"]["ms"]),
        ("JSON encode",lambda p:p["json_encode"]["ms"]),("JSON decode",lambda p:p["json_decode"]["ms"]),
        ("JSON bytes (including static metadata)",lambda p:p["json_bytes"]),
        ("Full public copy of one selected stock",lambda p:p["full_selected_stock_public_copy"]["ms"]),
        ("One selected stock JSON bytes (includes histories)",lambda p:p["selected_stock_json_bytes"])):
        text.append(f"| {label} | {number(med(fn(p) for p in probes))} |")
    text += ["", "All 2,523 quote rows exactly match the existing full snapshot's quote values, identity, region and metadata. The probe is evidence that explicit reads are possible without mutation hooks. It is not a replacement contract, does not measure UI apply/render or on-demand switch IPC, and does not establish low-hundreds-of-milliseconds T0→T4.", "",
        "## All nine views and existing switch costs", "",
        "Three ticks per view in each rotating offscreen run; different simulation dates, not paired performance comparisons. Warm switch includes refresh and `processEvents`; asynchronous history completion can extend beyond this synchronous number. Mature cold construction measurements precede the run. Selected details and hidden sub-tabs are source-audited; exhaustive future on-demand behavior is not implemented/tested.", "",
        "| View | Young T0→T4 ms | Mature T0→T4 ms | Mature max heartbeat gap ms | Young warm switch ms | Mature warm switch ms | Mature initial load ms |", "|---|---:|---:|---:|---:|---:|---:|"]
    for view in mature_ui["cold_view_switch_including_process_events_ms"]:
        yrs=[r for r in young_ui["rows"] if r["view"]==view]; mrs=[r for r in mature_ui["rows"] if r["view"]==view]
        text.append(f"| {view} | {number(med(r['total_ms'] for r in yrs))} | {number(med(r['total_ms'] for r in mrs))} | {number(max(max(r['heartbeat_gaps_ms'][1:],default=0) for r in mrs))} | {number(med(r['switch_sync_ms'] for r in yrs))} | {number(med(r['switch_sync_ms'] for r in mrs))} | {number(mature_ui['cold_view_switch_including_process_events_ms'][view])} |")
    text += ["", "Returning to Markets calls `MarketsView.refresh`, rebuilding all table row histories through `_prepare_local_histories`/`IncrementalHistory`, even though only a table or one detail is visible. It is already slow in a mature world. A later contract must avoid using the existing full refresh as its generic on-demand population mechanism. Do not shift normal-tick work into this path.", "",
        "View dependencies: Markets quotes/filter metadata + selected preview/detail; Supply Chain product/service rows + selected product/country/company breakdown; Forex rates/balances/conversion scalars + selected pair chart; Bond Market offers/filter metadata + selected bond detail; Portfolio precomputed totals and owned positions/bonds/currencies + selected holding chart; Macro country aggregate rows + selected country charts/supply/trade/sectors; Trade Map country/map totals and selected product flows; Global Macro visible indicator values/charts; News feed and calendar rows + selected news/calendar context. Portfolio and News currently refresh hidden tabs too; these are consumer-level opportunities, not globally live requirements.", "",
        "## Seven audit decisions", "",
        "1. **Broader parent mirror? Yes.** It contains all public asset/company/country detail and histories regardless of active view, plus current-row copies. Main-widget laziness does not narrow the protocol.",
        "2. **Invisible/unneeded share?** The measured diagnostic proportions above support a large majority of state-processing work being unneeded on an unselected Markets tick. Native decode includes scheduling and GC, so do not equate its full wall time with the section reconstruction sum.",
        "3. **Truly globally live?** Date, cash, display currency/control status and the already-ranked ticker items. A compact revision/date context is needed for consistency. Full portfolio, countries, FX/bonds and asset histories are not globally live display dependencies.",
        "4. **Active/on-demand?** Table/dashboard projections for the active main view, the selected entity's header/trade context, the visible sub-tab's fields and visible/live history endpoints. Related product/constituent information should be resolved in one worker-side selected-detail response.",
        "5. **Can broad day_delta disappear? Yes from normal ticks, in principle.** Existing full state/checkpoint operations remain explicit for restore/debug/save as needed. A small explicit active contract can replace broad comparison; whether limited active deltas or full compact active rows are best belongs to Phase 2.",
        "6. **Can compact explicit extraction replace comparison? Yes, supported by the quote/read probe and existing current-table materializations.** It must include dynamic topology, sort/filter correctness and selected dependencies; transmitting a stale filtered viewport is not sufficient.",
        "7. **Without thousands of mutation hooks? Yes for extraction.** Read finished authoritative objects/tables at a completed simulation revision. Required changes are worker/proxy IPC and shell/view consumers. No evidence requires economic assignment instrumentation. Stop if detailed contract design instead needs economic formula rewrites, new broad mirrors or fragile revision coupling.", "",
        "## Validation and boundaries", "",
        "Section runs assert exact prepared-delta/receiver equality for every public field. Category replays assert exact diff outputs and resulting values. Economics/RNG signatures before and after diagnostic reads match. All UI samples pass timestamp ordering, completion, request/slot/update main-thread checks and worker shutdown. Matching native control runs end with exactly equal economics/RNG signatures. Source SHA-256 checks prove production files unchanged.", "",
        f"**{test_count} focused tests passed in {test_seconds:.2f} seconds**: `test_day_delta.py`, `test_day_delta_views.py`, `test_day_delta_process.py`, and `test_workspace_views.py`. These include exact actual process timer/Step state and RNG comparison, Save/Load, explicit authoritative snapshot comparison and all nine views. Results: `focused-tests.txt` and `focused-tests.xml`. The prior identical-source release run recorded 330 passing tests and an exact 365-day economics/RNG/checkpoint/database comparison, including Save/Load/history coverage. That full suite and 365-day comparison were **not rerun in this audit**; no implementation was changed. Future on-demand A→B→A, hidden-sub-tab refresh after many days, Save/Load repetition and exact chart/EMA/Candle behavior remain Phase 6 requirements, not claimed completed here.", "",
        "Young/report/month-end evidence: fresh rotating young run covers a report date and month end; native mature run covers a report date. No fresh flush/day-type sweep was performed. The identical-source retained native first-year run has normal-no-flush median 1,413.41 ms, report 1,893.74 ms, month-end 1,369.29 ms and flush 4,439.52 ms. Those are retained baseline data, not new post-change results. Current persistence/flush remains an independent worker cost and is not removed by narrowing UI state.", "",
        "## Deliverables and final verdict", "",
        "Added files: `tools/ui_state_architecture_audit.py`, `tools/ui_state_architecture_report.py`, and this report. Raw JSON, source-consumer index, profiles, decoder CPU/component spans, per-section counters and allocation records are under `.cache/ui-state-architecture-audit/` (ignored local audit artifacts). No production files were changed during this pass.", "",
        "Broad synchronization removed/reduced: **none in production**. New tick contract/on-demand behavior: **not implemented**. Before/after payload, extraction, decode, apply, native block and T0→T4 improvements: **not claimed**. Simulation core is **not** the dominant elapsed component in the current native path. Remaining bottlenecks include broad public snapshot/diff/encoding, unnecessary bond/FX current-row transport, ticker text rendering and stale pending ticker items, native reader/Qt contention, GC and mature Markets full refresh; flush remains separate.", "",
        "**Final verdict: more targeted architecture work is justified.** The evidence supports Phase 2 minimal global/active-view/selected-detail/visible-history contract design. It does not support a generic full-profile on-demand fetch, another broad cache or a declaration of fluid gameplay. A later candidate must remeasure native T0→T4 and view-switch readiness with a minimally perturbing observer, then pass exact economics/history/Save/Load regression checks.", ""]
    REPORT.write_text("\n".join(text), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(str(REPORT))


if __name__ == "__main__":
    main()
