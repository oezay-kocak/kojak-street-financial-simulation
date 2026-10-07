"""Build the safety decision and UI report from completed evidence."""

from __future__ import annotations

import json
import statistics
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

from visible_sync_report import normal, run, stats

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / ".cache/precompute-audit"
OUT = ROOT / ".cache/visible-ui-sync"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    branches = read(EVIDENCE / "branches.json")
    assert len(branches) == 32
    for row in branches:
        if row["action"] == "no action":
            assert all(
                not row[day]["world"] and not row[day]["portfolio"] and row[day]["rng_equal"]
                for day in ("day1", "day2")
            )
    crypto = next(
        row for row in branches if row["action"] == "crypto buy" and row["day_kind"] == "report"
    )
    assert not crypto["day1"]["rng_equal"] and "aktien" in crypto["day1"]["world"]
    labels = (
        "native-mature",
        "native-young",
        "year",
        "all-young",
        "all-mature",
        "company-chart",
        "company-overview",
        "company-supply",
    )
    results = {label: run(OUT, f"zero-final-{label}") for label in labels}
    for result in results.values():
        assert result["ticker_continuity_checks"]
        assert all(row["hidden_chart_calls"] == 0 for row in result["rows"])
    old = run(OUT, "final-native-mature")
    suite = ElementTree.parse(EVIDENCE / "full-final.xml").getroot().find("testsuite")
    assert int(suite.attrib["failures"]) == int(suite.attrib["errors"]) == 0
    determinism = read(OUT / "zero-final-determinism-comparison.json")
    assert all(determinism.values())
    source = read(EVIDENCE / "source-comparison.json")
    assert not source["core_changed"]
    matrix = """| Player action | Portfolio mutation | World mutation/input to next day | RNG effect | Would invalidate N+1? | Evidence |
|---|---|---|---|---|---|
| Stock BUY/SELL | Positions, FX cash, realized PnL/date | Report dividends, net-worth history and margin-call gate | No draw in command/dividend path | Yes: integrated portfolio step | `trading.execute_spot_trade`, `company_lifecycle.pay_dividend`, `simulation.step_day` |
| LONG/SHORT open, add, close on stock/commodity/crypto | Margin, size, entry, payout | Position size directly contributes to open interest, imbalance/squeeze and subsequent market pricing | No command draw; different dynamics can alter later branches | Yes: world and portfolio | `market_calculations._perpetual_position_interest`, `_update_open_interest`; `portfolio_risk` |
| Dated derivatives/futures | Margin, contract expiry/date, PnL | Settlement eligibility and entry marks; complete portfolio/history step | No direct command draw | Yes | `trading._future_expiry_date`, `update_future_settlements` |
| Option/CDS spot BUY/SELL | Inventory and copied contract terms | Expiry/default settlements, payouts/news/portfolio history | No direct draw in settlement | Yes | `trading._copy_spot_derivative_contract`, `portfolio_risk` |
| Funds BUY/SELL | Inventory/FX cash | Net-worth history and margin-call gate | No direct command draw | Yes: integrated portfolio | `trading.execute_spot_trade`, `accounting.get_net_worth` |
| Commodities spot BUY/SELL | Inventory/FX cash | Net-worth history and margin-call gate | No direct command draw | Yes: integrated portfolio | Same spot path; XAU currency-conversion marks remain current-day inputs |
| Crypto spot BUY/SELL | Holdings, cash | **Monthly fee payout consumes shared RNG only when held**; excess-universe trimming also respects holdings | **Holding-dependent `random.uniform(0.01, 0.03)` on reports** | **Yes: broad economy/RNG** | `monthly_assets.update_monthly_crypto:59–64`; `cryptos._trim_excess_universe` |
| FX exchange | Currency balances | Conversion at N prices, credit charges, net-worth history/game-over gate | None directly | Yes: integrated portfolio | `trading.exchange_currency`, `accounting.update_credit_interest` |
| Owned bonds | Coupon clocks, principal/recovery, cash | Maturity, news, net worth and subsequent world RNG | **Corporate maturity calls shared `random.random()`** | Yes | `bond_calculations.update_laufende_anleihen` |
| Bond purchase/sale | — | **No callable Qt purchase/sale route**; Bondmarket is read-only. Existing save holdings are supported | As above for owned holdings | No nonexistent action; holdings still constrain preparation | `BondMarketView`, worker command inventory |
| Loans/credit balances | Debt/FX cash | Daily interest, net worth and margin calls | None directly | Yes | `accounting.update_credit_interest`; no loan command exposed by current Qt shell |
| Other cash mutation | Cash | History and depleted-net-worth early return before policy/date advance | None directly | Yes | `accounting.get_net_worth`, `simulation.step_day` |
| Pause/resume | No portfolio mutation | Scheduling/gating; an already-started sequential day finishes | Does not consume RNG itself | Publication gate, not an economic edit | `app.toggle_simulation`; `IntegratedRuntime.advance_day` explicitly enables a requested manual step |
| Speed/ticks per timeout | No | Scheduling and number of days requested | No direct RNG draw | Scheduling gate | `ticks_per_timeout`, `_timer_interval_ms`; no exposed speed settings control |
| Main navigation, Back, tabs, chart range, filters, sorting, watchlist | No | Read-only scope/history/Qt state; no daily advance | None | No | `visible`/`history` commands, view handlers |
| Display currency | No in normal valid-asset flow | Formatting; missing/retired option asset fallback can choose a settlement currency | None | Conservatively yes for fallback settlement, if such settings are exposed | `portfolio_risk._settle_option_if_expired`; no Qt display-currency settings control |
| Save | No economics edit | Serializes current authoritative checkpoint/history; flushes | No draw | Must discard speculative state in a future design | Existing checkpoint/session path retained |
| Load/world replacement | Replaces state | Entire world/date/RNG/history changes | Restores/resets RNG | Always | Existing load/bootstrap paths |
| Runtime seed change | No | Existing books/date remain; future daily draws change | Resets Python/NumPy RNG | Always | `IntegratedRuntime.set_seed`; runtime API, not a current gameplay button |
| Stop/limit orders, standalone short sale, reserved Revalue/Export actions | — | **Not implemented/exposed**; shorts use FUTURE tickets | — | No nonexistent action | Worker dispatch and `ViewHeader` source inventory |"""
    # Separate immediate book mutation from next-day dependencies explicitly.
    matrix_lines = matrix.splitlines()
    matrix_lines[0] = matrix_lines[0].replace(
        "World mutation/input to next day",
        "Immediate economic-book mutation | Input to next-day core",
    )
    matrix_lines[1] = "|---|---|---|---|---|---|---|"
    absent = {
        "Bond purchase/sale",
        "Stop/limit orders, standalone short sale, reserved Revalue/Export actions",
    }
    for index in range(2, len(matrix_lines)):
        cells = matrix_lines[index].split("|")
        action = cells[1].strip()
        mutation = (
            "Replaces whole world"
            if action == "Load/world replacement"
            else "No direct market-book edit"
        )
        if action in absent:
            mutation = "—"
        cells.insert(3, f" {mutation} ")
        matrix_lines[index] = "|".join(cells)
    matrix = "\n".join(matrix_lines)
    branch_table = "\n".join(
        f"| {row['day_kind']} | {row['action']} | {', '.join(row['day1']['world']) or 'identical'} | {'identical' if row['day1']['rng_equal'] else 'different'} | {', '.join(row['day1']['portfolio']) or 'identical'} |"
        for row in branches
        if row["action"] != "pause"
    )
    timing_rows = []
    for label, result in results.items():
        rows = (
            normal(result["rows"]) if label in {"native-mature", "native-young"} else result["rows"]
        )
        timing_rows.append(
            f"| {label} ({len(rows)}) | {stats([row['total_ms'] for row in rows])} | {stats([row['parent_spans'].get('ui.live_update', 0) for row in rows])} | {stats([max(row['heartbeat_gaps_ms']) for row in rows])} | {stats([row['worker']['response_bytes'] for row in rows])} |"
        )
    mature = normal(results["native-mature"]["rows"])
    special = []
    for label, rows in (
        (
            "Report (15th)",
            [
                row
                for row in results["native-mature"]["rows"]
                if date.fromisoformat(row["date"]).day == 15
            ],
        ),
        (
            "Month end",
            [row for row in results["native-mature"]["rows"] if row["date"] == "1991-01-31"],
        ),
        (
            "Durable flush",
            [
                row
                for row in results["native-mature"]["rows"]
                if row["worker"]["spans"].get("store.flush")
            ],
        ),
        ("Year boundary", results["year"]["rows"]),
    ):
        special.append(
            f"| {label} ({len(rows)}) | {stats([row['total_ms'] for row in rows])} | {stats([max(row['heartbeat_gaps_ms']) for row in rows])} |"
        )
    phases = []
    for label, values in (
        (
            "Economic core, after requested boundary",
            [row["worker"]["spans"]["simulation.core"] for row in mature],
        ),
        ("Persistence record", [row["worker"]["spans"]["store.record_day"] for row in mature]),
        (
            "Response preparation, includes projection/encode",
            [row["worker"]["spans"]["worker.result_prepare"] for row in mature],
        ),
        (
            "Core finish to parent receipt",
            [(row["t2"] - row["worker"]["t1"]) * 1000 for row in mature],
        ),
        ("Visible UI patch", [row["parent_spans"]["ui.live_update"] for row in mature]),
        ("Chart paint spans", [row["parent_spans"].get("chart.paint", 0) for row in mature]),
    ):
        phases.append(f"| {label} | {stats(values)} |")
    navigation = []
    young_cold = results["native-young"]["cold_switches_ms"]
    mature_cold = results["native-mature"]["cold_switches_ms"]
    for view in young_cold:
        navigation.append(f"| {view} | {young_cold[view]:.2f} | {mature_cold[view]:.2f} |")
    changed = "\n".join(f"- `{path.replace(chr(92), '/')}`" for path in source["changed"])
    report = f"""# Precomputed next day safety audit and UI continuity pass — 6 October 2026

**Decision: Case C under the document's stop conditions. Full next-day precomputation was not implemented.** Ordinary supported actions feed the integrated next-day world and shared RNG. The independent UI continuity fixes were implemented, with sequential economics, persistence and save compatibility retained.

This is a decision about the current architecture and the requested constraints, not a proof that every possible precomputation architecture is impossible. Invalidating a flag alone is insufficient: the current worker mutates its only authoritative world, portfolio, RNG and analytical store while stepping. Retaining N for nine on-demand views, trade validation, save and histories while that world has become N+1 requires an isolated current world or rollback/reconciliation. Since ordinary spot actions also change integrated portfolio history/settlement results, reconciliation is not a small exceptional path. This pass does not add that machinery or change the economy/RNG design to make independence true.

Evidence: `.cache/precompute-audit/branches.json`, `source-comparison.json`, focused/full test XML, and `.cache/visible-ui-sync/zero-final-*`. Existing dirty work was preserved. Source comparison is against a copy taken at the start of this task: **zero files in `src/kojakstreet/core` changed**.

## Player-action safety gate (items 1–5)

{matrix}

The 32 controlled comparisons restore the same seed-1729 checkpoint and Python/NumPy RNG before each branch. On normal and report dates they compare action→step against step→action, then one additional day. They call the real trading service and real daily economic core. They are dependency experiments, not a proposed reconciliation algorithm; after-step actions intentionally execute against the advanced world, so ordinary execution-price/contract-date differences are reported separately from economic-world/RNG differences. The audit creates only an isolated temporary store, not a live speculative implementation.

No-action controls match economy, RNG, portfolio and dates exactly on both days. LONG/SHORT opening and closing change stock market book hashes through open interest; the small tested ticket need not cross a squeeze threshold to prove the dependency. A crypto purchase before the report produces different stock, index, fund, FX, commodity, crypto and derivative results and different RNG immediately. The exact cause is the holding-dependent random crypto fee payout in `monthly_assets.py`, before subsequent market draws. An owned corporate bond maturity changes RNG on the first day and broad market books on the second day. Stock/fund/commodity spot examples have equal world/RNG in these branches but different portfolio/history, so they cannot be transplanted onto an already-integrated N+1 without preserving those effects.

| Day | Action | N+1 world fields that differ | N+1 RNG | N+1 portfolio fields that differ |
|---|---|---|---|---|
{branch_table}

Pause comparisons intentionally show the low-level `DailySimulation` gate skipping a day when paused. The production `advance_day` wrapper temporarily enables an explicitly requested step; normal pause correctness depends on the Qt scheduler not requesting another day. Navigation, sorting and chart inspection are reads, not steps. Dormant APIs and nonexistent controls are distinguished in the matrix rather than claiming every documented action is currently a button.

## Lifecycle, publication and durability (items 6–11, 26)

Previous path: Qt timer boundary → QThread command → authoritative worker `advance_day` → record/occasional durable flush → compact selected scope → IPC → visible patch/paint. The retained path has the same sequence; the UI work patches existing controls and chart graphics more selectively.

There is **no prepared-state lifecycle, invalidation cache, speculative commit or pre-boundary background economic computation**. Preparation/commit/invalidation timings are therefore **not applicable**, rather than reported as zero-cost successes. Dates and future reports/news/history become visible only through the completed authoritative day response. No future data is cached for inspection. No world mirrors or rollback machinery were introduced.

Save serializes the existing authoritative checkpoint and analytics session; Load restores them through the existing compatibility path. Neither includes a speculative day. During an in-flight sequential advance, Save/Load/trade handlers retain their existing busy guard. Their visual appearance no longer toggles each tick. Main navigation/detail requests during that interval are deferred; scrolling and Back remain enabled. Pause stops scheduling immediately, clears queued steps and sends the worker's pause flag after the in-flight day returns, avoiding a Qt-thread wait on its core lock. An already-started day completes; this is not speculative publication while paused.

DuckDB flushing stays in the authoritative worker before the response. Moving publication ahead of the durable operation would require changing ordering/error guarantees, so no such change was made. Normal-day improvements do not conceal the flush cost.

## UI artifact audit and fixes (items 12–19)

| Artifact | Root cause / call | Necessary on ordinary tick? | Implemented fix |
|---|---|---|---|
| Back/navigation/control appearance flash | `app._request_simulation_steps` disabled the whole active view, Save and Load; completion enabled them | No | Remove temporary enabled-state toggles; retain mutation guards; defer scope/pause requests instead of waiting on active core |
| Overview partly reloads | `_rebuild_kpis` deleted cards/labels and rebuilt layouts | No for same metric schema | Reuse cards and metric labels; patch text/color; rebuild only changed schemas |
| Supply scroll/selection reset | `_rebuild_supply_chain` called `set_headers` even for identical headers | No | `set_headers` returns for identical schema; values/metadata update in existing model; avoid reselecting the same row |
| Bond table scroll/control changes | `set_offers` compared price/yield signatures to decide model reset | No for same symbols | Patch by symbol; preserve loaded rows and persistent indices; sort/layout changes only when order really changes |
| Sorted rows lose logical selection | Simple model replaced sorted rows with canonical order; sort did not remap persistent indices | No | Match stable row identities before value patch; remap persistent indices on sort; do not emit layout changes for unchanged order |
| Dropdown popup/selection flicker | Markets/FX/bond filter options cleared/reinserted every refresh | No for unchanged options | Compare labels/data; rebuild only genuine option changes; preserve selection with signal blockers |
| Scroll jumps back to selected item | Refresh handlers unconditionally called `selectRow` | No for unchanged selection | Skip reselection in FX, country, product, global macro, news/calendar and supply tables |
| Chart/legend reconstruction | Multi-line/EMA and candle paths cleared plot items and recreated legends | No for same series schema | Update existing curve/candle/overlay items; keep legend widgets; clear only when chart structure changes |
| Ticker identities/geometry jump | Replaced complete ranked tape; variable text widths changed cell origins despite same offset | No | Reserve stable cell geometry, patch current numeric values, replace identities only offscreen as cells pass natural boundaries |

Ticker ranking is staged per offscreen cell, not held until an entire multi-hour tape wrap. Quotes for still-visible items that leave the top ranking are fetched from the current authoritative world until they leave the screen; no yesterday's values are retained. Identity includes asset type and symbol, so a stock and index with the same symbol cannot overwrite one another. Scroll keeps its pixel origin/remainder; drawing remains bounded to visible cells. A real asset-universe size change or retirement may require structural adjustment; ordinary price/rank changes do not. The 7D value definition remains the prior seven-point contract.

Tab/range/indicator choices, focused order text, selected identities, loaded rows and scroll positions are exercised by focused checks. Real universe/schema/filter changes still update structure. Repaint of changed numbers, colors and auto-fitted chart axes is necessary; retaining widget/graphics identity is not a promise of zero pixel repaint. The current FastChartView disables mouse pan/zoom; this pass retains range/indicator selections and does not add a new viewport interaction model.

Production files changed relative to this task's starting copy:

{changed}

New verification/report tools: `precompute_dependency_audit.py`, `zero_flicker_benchmark.py`, `zero_flicker_verify.py`, `precompute_audit_report.py`; tests: `test_zero_flicker_ui.py`, `test_player_day_publication.py`. The existing `test_visible_scope_process.py` assertion now checks exact current quote values by typed identity rather than requiring immediate ranked-list replacement. No economic tolerance changed. The new action test restores the shared legacy module and RNG after execution to keep later tests isolated.

## Measurements (items 20–27)

All triples are **median / p95 / max**. Milliseconds except payload bytes. Native Windows samples use the established 1920×1080 driver. All-view samples are offscreen, three ticks per view; six-detail-day tails and one-off special days are descriptive, not reliable tail estimates. Latency runs are serial and exclude unrelated test/determinism workloads. Every measured day includes core, persistence, response, current visible patch and readiness/paint at T4; no post-boundary work is relabeled as preparation.

| Scenario (samples) | Boundary→visible correct | Visible patch | Per-day longest heartbeat gap | Response bytes |
|---|---|---|---|---|
{chr(10).join(timing_rows)}

Same prior mature native normal benchmark: **{stats([row["total_ms"] for row in normal(old["rows"])])}**. New mature normal median: **{statistics.median(row["total_ms"] for row in mature):.2f} ms**. Measurements vary with allocator/OS state; an earlier exploratory run is archived and is not mixed into the final-source samples.

The phase spans below overlap (for example, core-finish-to-receipt includes persistence and response work), and their medians are not additive. Boundary-to-visible latency is measured directly from T0 to T4.

| Mature ordinary phase | Median / p95 / max |
|---|---|
{chr(10).join(phases)}

| Special day | Boundary→visible correct | Per-day longest heartbeat gap |
|---|---|---|
{chr(10).join(special)}

All nine views are exercised by both young and mature runs; actual company chart, fundamentals and supply tabs have separate native runs. Every final run asserts current tape quotes at T4, same visible identities/cell origins on ordinary publication, no hidden-chart daily draws, correct thread/phase ordering, successful completion and worker exit. The chart driver selects Stock by asset type, avoiding a same-symbol index match. These are measured correctness assertions, not screenshot-only impressions.

The final native drivers also measure initial navigation into each view, including scope retrieval, construction/update and processing pending Qt events. These are one sample per view/world, measured outside an in-flight day; they are separate from boundary latency and are not preparation timings.

| Initial navigation | Young (ms) | Mature (ms) |
|---|---|---|
{chr(10).join(navigation)}

The all-view runs measure repeated switches before their requested boundaries: young **{stats([row["switch_ms"] for row in results["all-young"]["rows"]])} ms**, mature **{stats([row["switch_ms"] for row in results["all-mature"]["rows"]])} ms** (median / p95 / max). Navigation requested during an in-flight day retains the deferred behavior described above; these measurements do not claim immediate completion in that interval.

Player actions are assessed with the dependency branches and a 20-day exact sequential/action/SaveLoad/pause regression. There is no precomputed path against which to benchmark trading invalidation; preparation/commit/recompute and speculative trade latency entries are not applicable. The branch experiment's elapsed times include checkpoint restoration and signatures and are not presented as trade latency. No new standalone trade/pause latency benchmark was run; their behavioral correctness is covered by the action and UI regressions.

## Correctness and limits (items 28–33)

Full suite: **{suite.attrib["tests"]} tests passed**, errors/failures zero; XML duration **{float(suite.attrib["time"]):.2f} s**. Focused checks cover card/label identity, unchanged headers/dropdowns, sorted persistent selection, scroll, fresh departing ticker quotes, same-symbol ticker isolation, visible sequence/origin continuity, bounded layout cache, reused chart items, and deferred busy-day pause/detail requests. The player-action regression executes purchases/sales, LONG/SHORT, closing, FX and an option immediately before requested boundaries, repeated pause/read/action/resume, save/load and replay; final full checkpoint and daily economic/RNG signatures match traditional sequential stepping exactly.

365-day worker-scope comparison: **{json.dumps(determinism, sort_keys=True)}**. All daily world/RNG signatures, report-visible fields, histories in checkpoints at days 15/31/181/365, final checkpoint and final economic database contents match the prior exact sequential reference. The comparator excludes only nondeterministic phase durations and session history identity, as before; no economic tolerances were widened. This is a regression of the retained sequential path, **not a prepared-vs-sequential claim**. There is no prepared path to test or leak future data. Save/Load and nine-view real process checks also run in the full suite.

**Final verdict: ordinary transitions have steadier UI structure, but are not effectively immediate.** The economic core still starts at the requested boundary and remains a substantial component; publication/IPC/patch/paint add further work. Results remain above the ~100 ms target, and durable flushes take seconds. Cold scoped reads, deep-history requests, on-completion deferred navigation, and genuine new/schema-changing rows can still produce stalls or structural updates. The audit rejected speculative precomputation under the current constraints rather than hiding those costs or changing economics/RNG.
"""
    path = ROOT / "docs/precomputed-next-day-safety-and-ui-continuity-2026-10-06.md"
    path.write_text(report, encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
