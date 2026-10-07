# Visible UI and on-demand synchronization — implementation report

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Implemented in the existing application. The complete economy still runs in the worker; daily UI synchronization now follows one active view, selected entity and visible detail tab. Normal native mature transitions improved from 2271.45 ms to 445.48 ms. Database flush and cold navigation remain measurable costs.

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

- `src/kojakstreet/live_process.py`
- `src/kojakstreet/live_worker.py`
- `src/kojakstreet/ui_qt/app.py`
- `src/kojakstreet/ui_qt/views/bondmarket_view.py`
- `src/kojakstreet/ui_qt/views/forex_view.py`
- `src/kojakstreet/ui_qt/views/global_macro_view.py`
- `src/kojakstreet/ui_qt/views/macro_view.py`
- `src/kojakstreet/ui_qt/views/markets_view.py`
- `src/kojakstreet/ui_qt/views/news_view.py`
- `src/kojakstreet/ui_qt/views/portfolio_view.py`
- `src/kojakstreet/ui_qt/views/supply_chain_view.py`
- `src/kojakstreet/ui_qt/widgets/stock_detail_dialog.py`
- `src/kojakstreet/ui_qt/widgets/top_bar.py`
- `src/kojakstreet/visible_state.py`

Tests added: `test_visible_state.py` and `test_visible_scope_process.py`. Existing chart, Markets, shell, process and timer assertions were adapted to visible-tab preparation, immediate ticker replacement and explicit debug reads; economics/RNG assertions and responsiveness thresholds were retained. Added tools: `visible_sync_benchmark.py`, `visible_sync_navigation.py`, `visible_sync_validation.py`, `visible_sync_verify.py`, and `visible_sync_report.py`. Preexisting local work is preserved. **No core economic, persistence, checkpoint or history-service source changed in this implementation**; `source-comparison.json` records all hashes. No economic mutation hooks, extra world mirrors or engine rebuild were required.

## Payload and phase timings (11–14)

Normal mature response bytes before: **2,317,934.00 / 2,344,092.40 / 2,387,125.00**; after: **514,965.00 / 516,303.00 / 516,480.00**. The active Markets response deliberately includes all table metadata and one selected preview, rather than a filtered viewport. Other views carry their own compact dependencies. No compression is used on the normal path.

| Phase | Before | After |
|---|---|---|
| Simulation core | 240.55 / 257.06 / 276.77 | 213.66 / 259.36 / 282.25 |
| Persistence record | 20.12 / 22.67 / 23.40 | 18.48 / 25.51 / 25.70 |
| Full recursive day delta | 697.30 / 760.65 / 852.32 | 0.00 / 0.00 / 0.00 |
| Snapshot preparation | 108.25 / 134.67 / 135.43 | 0.00 / 0.00 / 0.00 |
| Worker response preparation (includes extraction/encode) | 829.94 / 907.34 / 988.38 | 35.22 / 44.94 / 46.55 |
| State encode | 0.14 / 0.16 / 0.17 | 19.27 / 25.14 / 25.48 |
| JSON encode | 30.23 / 35.10 / 36.33 | 10.32 / 14.63 / 15.57 |
| Pipe write | 71.92 / 107.77 / 108.84 | 3.53 / 4.98 / 5.13 |
| Parent JSON decode | 20.80 / 70.24 / 88.71 | 8.62 / 10.91 / 11.54 |
| Parent broad delta decode | 746.11 / 838.25 / 843.46 | 0.00 / 0.00 / 0.00 |
| Parent visible state decode | 0.04 / 0.05 / 0.07 | 6.85 / 9.39 / 10.00 |
| Parent apply result | 41.25 / 104.31 / 124.82 | 7.01 / 9.56 / 10.16 |
| UI model quote apply | 12.21 / 17.17 / 21.26 | 11.78 / 15.55 / 19.92 |
| Active UI update | 27.74 / 291.57 / 333.58 | 53.52 / 71.99 / 78.27 |
| Chart paint | 0.00 / 0.00 / 0.00 | 19.68 / 40.54 / 50.25 |
| Parent GC total per tick | 54.71 / 324.39 / 394.94 | 1.46 / 2.10 / 2.36 |
| Worker GC total per tick | 82.20 / 99.11 / 101.25 | 14.10 / 21.12 / 35.83 |
| IPC round trip (includes worker advance/response) | 2,023.15 / 2,208.23 / 2,234.65 | 305.86 / 369.92 / 398.16 |
| Core completion to parent response | 1,821.28 / 2,002.49 / 2,048.78 | 100.20 / 124.10 / 133.46 |

Inclusive spans overlap and must not be summed. Decode thread wall times include scheduling contention; zero broad-delta decode after means the operation was removed. Worker core/source is unchanged; different elapsed core values reflect runtime conditions, not reduced economics. SQL/CSV flush and current/history writes remain in the worker record phase. Pipe write is measured; read/parsing/dispatch also contribute to overall IPC latency.

| Direct extraction after | Median / p95 / max |
|---|---|
| global_ms | 3.84 / 6.30 / 7.15 |
| view_ms | 9.94 / 14.34 / 17.75 |
| detail_ms | 0.15 / 0.22 / 3.29 |

Ticker items now replace immediately, preserve scrolling offset, and exactly equal the authoritative worker ranking at T4. Layout/formatted text is cached for the current tape; paint starts at the visible item and stops at the viewport boundary. The audit observed about 60,000 text draws per second across all repeated entries, plus stale pending items. Final native samples redraw only visible entries; isolated regression checks enforce bounded drawing and seven-day value equivalence.

| Ticker operation after (aggregate per tick) | Median / p95 / max |
|---|---|
| ui.ticker.layout | 8.97 / 12.17 / 12.45 |
| ui.ticker.update | 9.73 / 13.08 / 13.31 |
| ui.ticker.paint | 3.10 / 4.64 / 5.80 |

Allocation/GC evidence: the broad transient copy/encode/decode graph was removed, one compact proxy state replaces the full baseline, and startup release is regression-tested. Native parent RSS before at T0: 1,413.84 / 1,414.95 / 1,417.32 MiB; after: 1,315.80 / 1,316.31 / 1,316.31 MiB. RSS includes Qt and allocator-retained memory; it is not a live Python allocation count. GC is measured in the phase table. No GC disabling/freezing or tracing overhead was used to improve the latency figures.

## End-to-end, navigation and special days (15–19)

T0 is the real Qt timer request; T1 core completion; T2 parent response; T3 UI apply completion; T4 a later actual paint with pending visible chart/history work drained. Game-day waiting and the 30 ms between measurements are excluded. Each sample verifies timestamp order, main-thread request/slot/update, worker exit and ticker freshness; native Markets also verifies selected preview price freshness. No explicit full debug read occurs inside a latency sample.

| Run | Samples | T0→T4 | Longest heartbeat gap |
|---|---:|---|---:|
| Before: mature native normal, minimal paint observer | 19 | 2,271.45 / 2,642.63 / 2,715.00 | 381.95 |
| After: mature native normal | 37 | 445.48 / 533.75 / 607.28 | 183.57 |
| After: young native | 20 | 341.55 / 392.92 / 428.65 | 126.48 |
| Before: young nine-view offscreen | 27 | 1,023.14 / 1,246.52 / 1,485.06 | 183.50 |
| After: young nine-view offscreen | 27 | 211.79 / 327.15 / 348.90 | 54.59 |
| Before: mature nine-view offscreen | 27 | 1,168.52 / 1,431.71 / 1,537.73 | 292.52 |
| After: mature nine-view offscreen | 27 | 246.18 / 365.93 / 421.09 | 57.53 |

Native mature runs start from the same retained Jan 1, 1991 checkpoint and seed 1729; the baseline has 20 days and the final run 40. Normal rows exclude reporting/month-end/flush rows in both. The young offscreen comparison uses the same young checkpoint; the new young native run has no matched fresh old native baseline, so it is not a native young before/after claim. The former ticker could be stale and preview updates were throttled; the new run includes actual correct preview updates. Offscreen rotating-view rows occur on different dates and do not establish causal per-view speedups.

All nine views, three ticks/switches each; warm switch includes authoritative scope fetch, refresh and `processEvents`. Cold timings include widget construction. Separate native readiness navigation below also waits for asynchronous history/chart work.

| View | Young tick | Mature tick | Prior mature warm switch median | New mature warm switch | New mature cold load | Mature tick max gap | New young warm switch |
|---|---|---|---:|---|---:|---:|---|
| markets | 332.24 / 347.24 / 348.90 | 358.81 / 414.86 / 421.09 | 4224.55 | 154.12 / 162.09 / 162.97 | 21.06 | 55.24 | 157.57 / 230.69 / 238.81 |
| supply_chain | 197.09 / 200.01 / 200.34 | 224.01 / 240.26 / 242.07 | 32.22 | 47.66 / 51.22 / 51.62 | 127.73 | 31.94 | 47.85 / 48.93 / 49.05 |
| forex | 197.98 / 198.79 / 198.88 | 223.98 / 235.71 / 237.01 | 32.52 | 65.98 / 69.97 / 70.41 | 863.36 | 27.59 | 58.72 / 60.79 / 61.02 |
| bondmarket | 275.14 / 283.06 / 283.94 | 332.01 / 365.29 / 368.98 | 22.82 | 118.88 / 160.73 / 165.38 | 212.96 | 56.14 | 106.46 / 112.92 / 113.63 |
| portfolio | 183.96 / 189.24 / 189.82 | 210.24 / 247.67 / 251.83 | 10.13 | 20.55 / 20.73 / 20.75 | 125.93 | 11.10 | 14.82 / 15.04 / 15.06 |
| macro | 211.61 / 284.69 / 292.81 | 246.18 / 299.45 / 305.37 | 20.91 | 32.52 / 35.25 / 35.55 | 271.21 | 45.70 | 31.80 / 33.12 / 33.26 |
| trade_map | 256.97 / 303.73 / 308.93 | 273.00 / 285.80 / 287.22 | 33.48 | 86.64 / 87.35 / 87.43 | 91.03 | 19.48 | 81.67 / 82.84 / 82.97 |
| global_macro | 203.28 / 228.90 / 231.75 | 225.02 / 233.30 / 234.22 | 54.10 | 49.02 / 51.13 / 51.36 | 187.10 | 33.75 | 51.12 / 74.70 / 77.32 |
| news | 218.39 / 225.51 / 226.30 | 249.70 / 261.84 / 263.19 | 161.53 | 189.89 / 196.75 / 197.51 | 757.41 | 57.53 | 164.02 / 185.85 / 188.27 |

Repeated native entity/sub-tab navigation after 35 hidden days, five repetitions including runs after Save/Load; 235 total samples. Chart/detail rows include rendering/history readiness. Portfolio contains a real purchased holding. Entity selection switches between stock #900, fund #82, derivative, commodity, crypto and index. Cold first visits are included in maxima; unavailable detail tabs remain unavailable.

| Action | Samples | Ready time | Longest heartbeat gap |
|---|---:|---|---:|
| Markets return | 5 | 349.29 / 430.07 / 448.21 | 243.35 |
| Stock select | 5 | 238.09 / 287.07 / 292.36 | 195.57 |
| Stock chart detail | 5 | 208.10 / 261.66 / 272.41 | 156.68 |
| Stock overview | 5 | 264.54 / 522.54 / 564.73 | 372.19 |
| Stock supply | 5 | 125.71 / 134.80 / 136.71 | 103.18 |
| Stock chart return | 5 | 225.33 / 256.38 / 263.77 | 176.31 |
| Fund overview | 5 | 478.60 / 722.35 / 764.29 | 330.62 |
| Fund supply | 5 | 118.07 / 143.41 / 149.22 | 93.68 |
| Fund chart detail | 5 | 112.43 / 165.50 / 176.24 | 84.41 |
| Derivative chart detail | 5 | 103.16 / 104.43 / 104.54 | 49.30 |
| Commodity chart detail | 5 | 146.37 / 154.93 / 156.85 | 82.48 |
| Crypto chart detail | 5 | 129.33 / 149.96 / 151.48 | 78.94 |
| Index chart detail | 5 | 136.63 / 141.23 / 142.29 | 66.74 |
| Bond detail | 5 | 100.09 / 223.13 / 251.77 | 149.94 |
| FX detail | 5 | 86.04 / 117.60 / 124.86 | 80.29 |
| Country overview | 5 | 340.99 / 371.85 / 374.62 | 215.32 |
| Country production | 5 | 62.33 / 82.12 / 84.19 | 62.43 |
| Country trade | 5 | 44.79 / 51.94 / 53.05 | 29.13 |
| Country sectors | 5 | 32.81 / 34.63 / 34.80 | 20.13 |
| Product detail | 5 | 228.40 / 1,840.30 / 2,214.75 | 174.25 |
| Portfolio holding | 5 | 146.36 / 315.29 / 357.41 | 263.63 |
| Calendar view | 5 | 157.70 / 1,177.88 / 1,401.36 | 1250.89 |
| Calendar metric | 5 | 78.54 / 102.95 / 107.79 | 57.82 |
| Global macro | 5 | 104.65 / 144.21 / 152.05 | 58.23 |
| Trade map | 5 | 131.95 / 165.71 / 171.42 | 122.09 |

Final mature native sweep includes reporting, month end and periodic flush; the year boundary uses the retained Dec 31 checkpoint. Single-event p95 equals max and cannot estimate future tails.

| Day type | Samples | T0→T4 | Longest heartbeat gap |
|---|---:|---|---:|
| Normal | 37 | 445.48 / 533.75 / 607.28 | 183.57 |
| Report date (15th) | 1 | 609.59 / 609.59 / 609.59 | 115.19 |
| Month end | 1 | 372.07 / 372.07 / 372.07 | 96.28 |
| Flush | 1 | 4,047.25 / 4,047.25 / 4,047.25 | 102.45 |
| Year boundary (Dec 31 / Jan 1) | 2 | 569.48 / 578.35 / 579.34 | 122.91 |

## Correctness (20–24)

Full suite: **339 passed**, zero failures/errors, 791.94 seconds; evidence `full-final.xml`. It covers existing simulation/persistence/history/chart functionality and new scoped-state cases. After the selected-sector read narrowing and derivative contract-size field correction, **100 UI/process/history regression tests passed**, zero failures/errors; evidence `final-ui.xml`. The sector test asserts exact summary equivalence while rejecting any hidden history copy. The derivative fixture and actual worker control assert that contract size is preserved in the selected chart/order context. Chart regression checks retain Deep History, EMA/Candle behavior, date-aware incremental histories, viewport persistence and no redraw of a hidden detail chart. All final benchmark sweeps completed without errors and recorded zero hidden chart calls in normal ticks.

The **365-day comparison through the compact worker path** uses seed 1729, all nine worker scopes and rotating selected company and country tabs. Every daily non-history public checkpoint field and Python/NumPy RNG state matches exactly. Full checkpoint hashes at days 15, 31, 181 and 365, including histories, match; final full capture matches. Every database table's economic content and row count matches after flush. As in the established comparator, only nondeterministic `phase_metric_* .duration_ms` values and the independently created `history_metadata.history_id` are excluded. No numerical tolerances were introduced or widened. Evidence: `determinism-final-source.json` and `determinism-final-source-comparison.json`.

Save/Load is checked by exact signatures, continued days crossing the next report and reopened company fundamentals. Hidden company #900, its supply rows, fund allocations, country production/product detail, bond, FX and calendar values are compared with explicit authoritative worker debug controls after 35 hidden days. The calendar preserves exact report-date previous/actual values instead of reconstructing them from a two-point transport tail. Only its selected chart history is sent. The proxy holds one active compact state and never retains the full debug result.

## Remaining costs and verdict (25–27)

**Simulation core is now the largest ordinary worker component**, rather than broad state comparison/reconstruction. The UI still sends full active table quote metadata, renders visible charts, calculates ticker text widths when values change and performs synchronous on-demand reads between ticks. Cold News construction and the first product/deep-history request remain slower than warm navigation; the native action table exposes their maxima. A navigation request made during a running day waits for that day's completion while the event loop remains active.

Periodic database flush remains a multi-second completion cost; narrowing UI state does not remove it. It happens in the worker, so its T0→T4 duration is distinct from the much shorter measured UI heartbeat gaps. The startup checkpoint is still a large explicit handoff outside ordinary ticks. Controls using synchronous worker calls can also wait if invoked while it is busy; these measurements cover uninterrupted timer ticks. These are candidates for later work, not hidden by the normal-day median.

**Verdict:** the broad synchronization bottleneck is removed and normal gameplay is substantially more responsive, with current visible values and no equivalent state-building bottleneck replacing the old delta. Warm Markets return is no longer a multi-second full-history rebuild. This is a normal-gameplay improvement, not a claim that flushes, cold starts or every first navigation are pause-free. Economic computation, randomness, persistence and Save/Load are preserved exactly.
