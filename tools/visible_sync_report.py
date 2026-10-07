"""Generate the implementation report from completed evidence, never estimates."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/visible-ui-sync"
BEFORE = ROOT / ".cache/ui-state-architecture-audit"
REPORT = ROOT / "docs/visible-ui-on-demand-sync-2026-10-06.md"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def stats(values):
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.95
    lower = math.floor(position)
    upper = math.ceil(position)
    p95 = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return f"{statistics.median(ordered):,.2f} / {p95:,.2f} / {max(ordered):,.2f}"


def run(directory, label):
    result = read(directory / f"{label}.json")
    workers = [
        json.loads(line) for line in (directory / f"{label}-worker.jsonl").read_text().splitlines()
    ]
    assert result["finished"] and not result["errors"] and result["worker_exited"]
    assert len(result["rows"]) == len(workers)
    for row, worker in zip(result["rows"], workers):
        assert row["date"] == worker["date"]
        assert row["t0"] <= worker["t1"] <= row["t2"] <= row["t3"] <= row["t4"]
        assert all(
            row[key] for key in ("request_is_qt_main", "slot_is_qt_main", "update_is_qt_main")
        )
        if directory == OUT:
            assert row["ticker_current_at_t4"]
        row["worker"] = worker
    return result


def normal(rows):
    return [
        row
        for row in rows
        if date.fromisoformat(row["date"]).day != 15
        and (date.fromisoformat(row["date"]) + timedelta(days=1)).month
        == date.fromisoformat(row["date"]).month
        and not row["worker"]["spans"].get("store.flush", 0)
    ]


def gaps(rows):
    return max(max(row["heartbeat_gaps_ms"]) for row in rows)


def gc_spans(rows, worker=False):
    values = []
    for row in rows:
        events = row["worker"]["gc"] if worker else row["parent_gc"]
        starts, elapsed = {}, 0.0
        for event in events:
            if event["phase"] == "start":
                starts[event["generation"]] = event["time"]
            elif event["generation"] in starts:
                elapsed += (event["time"] - starts.pop(event["generation"])) * 1000
        values.append(elapsed)
    return values


def main():
    before = run(BEFORE, "qt-native-paint-control")
    mature = run(OUT, "final-native-mature")
    young = run(OUT, "final-native-young")
    year = run(OUT, "final-year-boundary")
    all_young = run(OUT, "final-all-young")
    all_mature = run(OUT, "final-all-mature")
    before_young = run(BEFORE, "qt-nine-views-young")
    before_mature = run(BEFORE, "qt-nine-views-mature")
    navigation = read(OUT / "final-navigation-v2.json")
    assert navigation["save_load_exact"]
    suite = ElementTree.parse(OUT / "full-final.xml").getroot().find("testsuite")
    assert suite is not None and int(suite.attrib["failures"]) == int(suite.attrib["errors"]) == 0
    focused = ElementTree.parse(OUT / "final-ui.xml").getroot().find("testsuite")
    assert (
        focused is not None
        and int(focused.attrib["failures"]) == int(focused.attrib["errors"]) == 0
    )
    exact = read(OUT / "determinism-final-source-comparison.json")
    assert all(exact.values())
    old, new = normal(before["rows"]), normal(mature["rows"])
    phase_rows = []

    def phase(label, before_values, after_values):
        phase_rows.append(f"| {label} | {stats(before_values)} | {stats(after_values)} |")

    def worker(rows, key):
        return [row["worker"]["spans"].get(key, 0) for row in rows]

    def parent(rows, key):
        return [row["parent_spans"].get(key, 0) for row in rows]

    for label, key in (
        ("Simulation core", "simulation.core"),
        ("Persistence record", "store.record_day"),
        ("Full recursive day delta", "worker.day_delta"),
        ("Snapshot preparation", "snapshot.prepare"),
        ("Worker response preparation (includes extraction/encode)", "worker.result_prepare"),
        ("State encode", "worker.state_encode"),
        ("JSON encode", "worker.json_encode"),
        ("Pipe write", "worker.pipe_write"),
    ):
        phase(label, worker(old, key), worker(new, key))
    for label, key in (
        ("Parent JSON decode", "parent.json_decode"),
        ("Parent broad delta decode", "parent.decode_day_delta"),
        ("Parent visible state decode", "parent.decode_state"),
        ("Parent apply result", "parent.apply_result"),
        ("UI model quote apply", "ui.model.apply_quote_rows"),
        ("Active UI update", "ui.live_update"),
        ("Chart paint", "chart.paint"),
    ):
        phase(label, parent(old, key), parent(new, key))
    phase("Parent GC total per tick", gc_spans(old), gc_spans(new))
    phase("Worker GC total per tick", gc_spans(old, True), gc_spans(new, True))
    phase(
        "IPC round trip (includes worker advance/response)",
        [r["ipc_roundtrip_ms"] for r in old],
        [r["ipc_roundtrip_ms"] for r in new],
    )
    phase(
        "Core completion to parent response",
        [(r["t2"] - r["worker"]["t1"]) * 1000 for r in old],
        [(r["t2"] - r["worker"]["t1"]) * 1000 for r in new],
    )
    extraction_rows = []
    for key in ("global_ms", "view_ms", "detail_ms"):
        extraction_rows.append(f"| {key} | {stats([r['extraction_ms'][key] for r in new])} |")
    ticker_rows = []
    for key in ("ui.ticker.layout", "ui.ticker.update", "ui.ticker.paint"):
        ticker_rows.append(f"| {key} | {stats(parent(new, key))} |")
    views = []
    for key in (
        "markets",
        "supply_chain",
        "forex",
        "bondmarket",
        "portfolio",
        "macro",
        "trade_map",
        "global_macro",
        "news",
    ):
        ys = [r for r in all_young["rows"] if r["view"] == key]
        ms = [r for r in all_mature["rows"] if r["view"] == key]
        prior = [r for r in before_mature["rows"] if r["view"] == key]
        views.append(
            f"| {key} | {stats([r['total_ms'] for r in ys])} | {stats([r['total_ms'] for r in ms])} | "
            f"{statistics.median(r['switch_sync_ms'] for r in prior):.2f} | {stats([r['switch_ms'] for r in ms])} | "
            f"{all_mature['cold_switches_ms'][key]:.2f} | {gaps(ms):.2f} | {stats([r['switch_ms'] for r in ys])} |"
        )
    details = []
    labels = (
        "Markets return",
        "Stock select",
        "Stock chart detail",
        "Stock overview",
        "Stock supply",
        "Stock chart return",
        "Fund overview",
        "Fund supply",
        "Fund chart detail",
        "Derivative chart detail",
        "Commodity chart detail",
        "Crypto chart detail",
        "Index chart detail",
        "Bond detail",
        "FX detail",
        "Country overview",
        "Country production",
        "Country trade",
        "Country sectors",
        "Product detail",
        "Portfolio holding",
        "Calendar view",
        "Calendar metric",
        "Global macro",
        "Trade map",
    )
    for label in labels:
        rows = [r for r in navigation["rows"] if r["label"] == label]
        details.append(
            f"| {label} | {len(rows)} | {stats([r['ms'] for r in rows])} | {max(r['heartbeat_max_ms'] for r in rows):.2f} |"
        )
    specials = []
    for label, rows in (
        ("Normal", new),
        (
            "Report date (15th)",
            [r for r in mature["rows"] if date.fromisoformat(r["date"]).day == 15],
        ),
        (
            "Month end",
            [
                r
                for r in mature["rows"]
                if (date.fromisoformat(r["date"]) + timedelta(days=1)).month
                != date.fromisoformat(r["date"]).month
            ],
        ),
        ("Flush", [r for r in mature["rows"] if r["worker"]["spans"].get("store.flush", 0)]),
        ("Year boundary (Dec 31 / Jan 1)", year["rows"]),
    ):
        specials.append(
            f"| {label} | {len(rows)} | {stats([r['total_ms'] for r in rows])} | {gaps(rows):.2f} |"
        )
    comparison = []
    baseline_dir = OUT / "baseline-src/kojakstreet"
    for path in sorted((ROOT / "src/kojakstreet").rglob("*.py")):
        baseline = baseline_dir / path.relative_to(ROOT / "src/kojakstreet")
        old_hash = hashlib.sha256(baseline.read_bytes()).hexdigest() if baseline.exists() else None
        new_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        comparison.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "baseline_sha256": old_hash,
                "sha256": new_hash,
                "changed": old_hash != new_hash,
            }
        )
    assert not any(
        r["changed"] for r in comparison if r["path"].startswith("src/kojakstreet/core/")
    )
    (OUT / "source-comparison.json").write_text(json.dumps(comparison, indent=2))
    changed = "\n".join(f"- `{r['path']}`" for r in comparison if r["changed"])
    payload_old = [r["worker"]["response_bytes"] for r in old]
    payload_new = [r["worker"]["response_bytes"] for r in new]
    text = f"""# Visible UI and on-demand synchronization — implementation report

Implemented in the existing application. The complete economy still runs in the worker; daily UI synchronization now follows one active view, selected entity and visible detail tab. Normal native mature transitions improved from {statistics.median(r["total_ms"] for r in old):.2f} ms to {statistics.median(r["total_ms"] for r in new):.2f} ms. Database flush and cold navigation remain measurable costs.

Evidence is in `.cache/visible-ui-sync/`; prior audit evidence is in `.cache/ui-state-architecture-audit/`. This report covers the 27 requested items below. All timings are milliseconds; triples are **median / p95 / max**, using linear interpolation. Three samples per view and five per navigation action are descriptive, not statistically strong tail estimates. Native tests used the Windows Qt platform at 1920×1080. Offscreen results are identified separately. Runs were serial, without profiler/allocation tracing in latency samples.

## Consumer matrix (1, 4–8)

| Scope | Required live state | On demand | Worker-only state |
|---|---|---|---|
| Global | Date, cash, display currency, revision/date context, pre-ranked seven-day ticker | — | World, RNG, economic caches |
| Markets | All 2,523 instruments' quote/filter/sort metadata | Selected chart seed and live price tail; selected overview scalars; supply rows; fund allocation resolution; selected supply metric | Unselected company fundamentals, output/input history, fund holdings and all other instrument histories |
| Supply Chain | 124 current products/services and country scalars | Selected product supply/demand series, producing-company subset and country profile | Other company details and product histories |
| Forex | Rates, balances, strengths and last two pair values | Selected pair chart / existing deep history | Other pair histories |
| Bond Market | Current offers and filter metadata | Selected bond history | Other bond histories |
| Portfolio | Held positions, balances, valuations, loans, held bonds and portfolio history | Selected holding chart | Unowned instrument details |
| Macro | Country table scalars and product names/current metadata | Selected country; overview histories, production, trade, sectors; one selected regional product series | Other country detail/history |
| Trade Map | Current country trade/product flows | Existing selected flow/filter presentation | Company histories and fundamentals |
| Global Macro | Current indicators and 31 points needed for 1D/30D table changes | Selected indicator history | Other deep histories |
| News | Feed/KPI counts, current calendar row values from authoritative dated history | Selected calendar metric history; selected news text | Unselected calendar histories |

Quotes for all Markets rows are intentional: sorting, filtering and scrolling require them. Company #900's fundamentals are absent while hidden; its table quote is still a Markets dependency. Headers and selected trading controls retain small current scalar context across detail tabs. Inactive widgets may retain their last bounded presentation data; they receive no daily updates and are refreshed when reopened.

## Architecture and ownership (2, 3, 9, 10)

Previously, each ordinary day built a broad detached public snapshot, recursively compared it, serialized a day delta and reconstructed a broad parent mirror. Current tables also crossed the pipe for hidden views. Mature Markets return rebuilt every instrument's history. Ticker replacement waited for a full scroll cycle, and paint traversed the entire repeated tape.

Now `visible_state.py` reads completed worker state directly through one explicit scope. Global, active-view and selected-detail extraction have separate measured spans. Navigation sends a `visible` request without advancing economics. Live requests send the same scope and date endpoint; selected Markets price history is merged incrementally, bounded to 520 local points. Full state is an explicit debug read and is never retained as the UI baseline. Save/checkpoint/history persistence remain authoritative in the worker. Missing compact responses fail rather than falling back to a full mirror.

There is no normal `DayStateEncoder`, broad recursive diff, compressed pickle/unpickle receiver, full-world canonical baseline or hidden-view current-table transport. The legacy delta utility remains for compatibility/diagnostic tests. Application startup explicitly releases closed bootstrap books, including facade aliases, by replacing references; a caller's retained dictionaries are not cleared. Navigation during a tick is deferred until completion, avoiding waiting on the worker lock in the Qt thread.

Production files changed relative to the **start-of-task source copy**, including new `visible_state.py`:

{changed}

Tests added: `test_visible_state.py` and `test_visible_scope_process.py`. Existing chart, Markets, shell, process and timer assertions were adapted to visible-tab preparation, immediate ticker replacement and explicit debug reads; economics/RNG assertions and responsiveness thresholds were retained. Added tools: `visible_sync_benchmark.py`, `visible_sync_navigation.py`, `visible_sync_validation.py`, `visible_sync_verify.py`, and `visible_sync_report.py`. Preexisting local work is preserved. **No core economic, persistence, checkpoint or history-service source changed in this implementation**; `source-comparison.json` records all hashes. No economic mutation hooks, extra world mirrors or engine rebuild were required.

## Payload and phase timings (11–14)

Normal mature response bytes before: **{stats(payload_old)}**; after: **{stats(payload_new)}**. The active Markets response deliberately includes all table metadata and one selected preview, rather than a filtered viewport. Other views carry their own compact dependencies. No compression is used on the normal path.

| Phase | Before | After |
|---|---|---|
{chr(10).join(phase_rows)}

Inclusive spans overlap and must not be summed. Decode thread wall times include scheduling contention; zero broad-delta decode after means the operation was removed. Worker core/source is unchanged; different elapsed core values reflect runtime conditions, not reduced economics. SQL/CSV flush and current/history writes remain in the worker record phase. Pipe write is measured; read/parsing/dispatch also contribute to overall IPC latency.

| Direct extraction after | Median / p95 / max |
|---|---|
{chr(10).join(extraction_rows)}

Ticker items now replace immediately, preserve scrolling offset, and exactly equal the authoritative worker ranking at T4. Layout/formatted text is cached for the current tape; paint starts at the visible item and stops at the viewport boundary. The audit observed about 60,000 text draws per second across all repeated entries, plus stale pending items. Final native samples redraw only visible entries; isolated regression checks enforce bounded drawing and seven-day value equivalence.

| Ticker operation after (aggregate per tick) | Median / p95 / max |
|---|---|
{chr(10).join(ticker_rows)}

Allocation/GC evidence: the broad transient copy/encode/decode graph was removed, one compact proxy state replaces the full baseline, and startup release is regression-tested. Native parent RSS before at T0: {stats([r["parent_rss_start"] / 1048576 for r in old])} MiB; after: {stats([r["parent_rss_start"] / 1048576 for r in new])} MiB. RSS includes Qt and allocator-retained memory; it is not a live Python allocation count. GC is measured in the phase table. No GC disabling/freezing or tracing overhead was used to improve the latency figures.

## End-to-end, navigation and special days (15–19)

T0 is the real Qt timer request; T1 core completion; T2 parent response; T3 UI apply completion; T4 a later actual paint with pending visible chart/history work drained. Game-day waiting and the 30 ms between measurements are excluded. Each sample verifies timestamp order, main-thread request/slot/update, worker exit and ticker freshness; native Markets also verifies selected preview price freshness. No explicit full debug read occurs inside a latency sample.

| Run | Samples | T0→T4 | Longest heartbeat gap |
|---|---:|---|---:|
| Before: mature native normal, minimal paint observer | {len(old)} | {stats([r["total_ms"] for r in old])} | {gaps(old):.2f} |
| After: mature native normal | {len(new)} | {stats([r["total_ms"] for r in new])} | {gaps(new):.2f} |
| After: young native | {len(young["rows"])} | {stats([r["total_ms"] for r in young["rows"]])} | {gaps(young["rows"]):.2f} |
| Before: young nine-view offscreen | 27 | {stats([r["total_ms"] for r in before_young["rows"]])} | {gaps(before_young["rows"]):.2f} |
| After: young nine-view offscreen | 27 | {stats([r["total_ms"] for r in all_young["rows"]])} | {gaps(all_young["rows"]):.2f} |
| Before: mature nine-view offscreen | 27 | {stats([r["total_ms"] for r in before_mature["rows"]])} | {gaps(before_mature["rows"]):.2f} |
| After: mature nine-view offscreen | 27 | {stats([r["total_ms"] for r in all_mature["rows"]])} | {gaps(all_mature["rows"]):.2f} |

Native mature runs start from the same retained Jan 1, 1991 checkpoint and seed 1729; the baseline has 20 days and the final run 40. Normal rows exclude reporting/month-end/flush rows in both. The young offscreen comparison uses the same young checkpoint; the new young native run has no matched fresh old native baseline, so it is not a native young before/after claim. The former ticker could be stale and preview updates were throttled; the new run includes actual correct preview updates. Offscreen rotating-view rows occur on different dates and do not establish causal per-view speedups.

All nine views, three ticks/switches each; warm switch includes authoritative scope fetch, refresh and `processEvents`. Cold timings include widget construction. Separate native readiness navigation below also waits for asynchronous history/chart work.

| View | Young tick | Mature tick | Prior mature warm switch median | New mature warm switch | New mature cold load | Mature tick max gap | New young warm switch |
|---|---|---|---:|---|---:|---:|---|
{chr(10).join(views)}

Repeated native entity/sub-tab navigation after 35 hidden days, five repetitions including runs after Save/Load; 235 total samples. Chart/detail rows include rendering/history readiness. Portfolio contains a real purchased holding. Entity selection switches between stock #900, fund #82, derivative, commodity, crypto and index. Cold first visits are included in maxima; unavailable detail tabs remain unavailable.

| Action | Samples | Ready time | Longest heartbeat gap |
|---|---:|---|---:|
{chr(10).join(details)}

Final mature native sweep includes reporting, month end and periodic flush; the year boundary uses the retained Dec 31 checkpoint. Single-event p95 equals max and cannot estimate future tails.

| Day type | Samples | T0→T4 | Longest heartbeat gap |
|---|---:|---|---:|
{chr(10).join(specials)}

## Correctness (20–24)

Full suite: **{suite.attrib["tests"]} passed**, zero failures/errors, {float(suite.attrib["time"]):.2f} seconds; evidence `full-final.xml`. It covers existing simulation/persistence/history/chart functionality and new scoped-state cases. After the selected-sector read narrowing and derivative contract-size field correction, **{focused.attrib["tests"]} UI/process/history regression tests passed**, zero failures/errors; evidence `final-ui.xml`. The sector test asserts exact summary equivalence while rejecting any hidden history copy. The derivative fixture and actual worker control assert that contract size is preserved in the selected chart/order context. Chart regression checks retain Deep History, EMA/Candle behavior, date-aware incremental histories, viewport persistence and no redraw of a hidden detail chart. All final benchmark sweeps completed without errors and recorded zero hidden chart calls in normal ticks.

The **365-day comparison through the compact worker path** uses seed 1729, all nine worker scopes and rotating selected company and country tabs. Every daily non-history public checkpoint field and Python/NumPy RNG state matches exactly. Full checkpoint hashes at days 15, 31, 181 and 365, including histories, match; final full capture matches. Every database table's economic content and row count matches after flush. As in the established comparator, only nondeterministic `phase_metric_* .duration_ms` values and the independently created `history_metadata.history_id` are excluded. No numerical tolerances were introduced or widened. Evidence: `determinism-final-source.json` and `determinism-final-source-comparison.json`.

Save/Load is checked by exact signatures, continued days crossing the next report and reopened company fundamentals. Hidden company #900, its supply rows, fund allocations, country production/product detail, bond, FX and calendar values are compared with explicit authoritative worker debug controls after 35 hidden days. The calendar preserves exact report-date previous/actual values instead of reconstructing them from a two-point transport tail. Only its selected chart history is sent. The proxy holds one active compact state and never retains the full debug result.

## Remaining costs and verdict (25–27)

**Simulation core is now the largest ordinary worker component**, rather than broad state comparison/reconstruction. The UI still sends full active table quote metadata, renders visible charts, calculates ticker text widths when values change and performs synchronous on-demand reads between ticks. Cold News construction and the first product/deep-history request remain slower than warm navigation; the native action table exposes their maxima. A navigation request made during a running day waits for that day's completion while the event loop remains active.

Periodic database flush remains a multi-second completion cost; narrowing UI state does not remove it. It happens in the worker, so its T0→T4 duration is distinct from the much shorter measured UI heartbeat gaps. The startup checkpoint is still a large explicit handoff outside ordinary ticks. Controls using synchronous worker calls can also wait if invoked while it is busy; these measurements cover uninterrupted timer ticks. These are candidates for later work, not hidden by the normal-day median.

**Verdict:** the broad synchronization bottleneck is removed and normal gameplay is substantially more responsive, with current visible values and no equivalent state-building bottleneck replacing the old delta. Warm Markets return is no longer a multi-second full-history rebuild. This is a normal-gameplay improvement, not a claim that flushes, cold starts or every first navigation are pause-free. Economic computation, randomness, persistence and Save/Load are preserved exactly.
"""
    REPORT.write_text(text, encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
