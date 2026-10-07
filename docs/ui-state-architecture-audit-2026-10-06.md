# Kojak Street — Phase 1 UI-state architecture audit

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Date: 6 October 2026 (Europe/Berlin). Scope: audit only. No production source, economics, RNG, save format, database contract or normal tick contract changed.

**Verdict: the broad-mirror hypothesis is supported. Proceed to a minimal contract design; the performance target is not yet achieved.** The worker compares and encodes public state for the entire economy irrespective of the visible view. A substantial majority of that work has no displayed consumer during an unselected Markets tick. Native ticker rendering also causes reader contention, and the existing T4 boundary does not guarantee current displayed ticker values. The mature Markets switch path is independently slow. These findings prevent treating a smaller delta alone as a solved fluid/correct UI.

## Evidence and measurement boundaries

All measurements used isolated copied checkpoints and DuckDB files under `.cache/ui-state-architecture-audit/`. Seed 1729; mature checkpoint `end` (1 January 1991); young checkpoint 10 January 1990. The current production source hashes match both the start of this audit and the retained performance-remediation baseline. Existing uncommitted production changes predate this audit and were left intact.

Excluded diagnostic: the first minimal-observer attempt observed only the table viewport and never saw a qualifying post-update paint; it timed out with zero completed samples. `qt-native-minimal-observer.*` is retained as a failed measurement, not a gameplay hang or performance evidence. The successful control additionally observes the ticker and central widget.

Fresh runs: 20 mature native-window Markets ticks; 20 matching native ticks with targeted viewport/ticker/central-widget paint observers; 27 mature and 27 young offscreen ticks rotating all nine views; separate section/profile/allocation diagnostics. Normal UI requests call the actual `_on_timer_tick()`. T0 is the request, T1 core completion, T2 parent apply completion, T3 active UI update completion, T4 the next heartbeat after an observed paint and pending UI/chart/history work. Setup, intentional game-day waits and view switches are outside tick latency. Switching is measured separately.

The 10 ms heartbeat gap is an event-loop responsiveness measurement, including GIL/scheduling delay; it is not an exact pure Qt-slot block. Offscreen rows do not establish native desktop feel. Category diff/encode/decode values are isolated replays of the unchanged algorithm on disjoint field groups. The actual wire mixes groups in compressed chunks, so category bytes/times are contribution estimates and must not be added to predict T0→T4. Small category bodies are deliberately measured with the same binary codec. Dictionary visits are counted; sequence lengths are comparison candidates, not claimed exact C-level equality comparisons. Allocation diagnostics are separate and their latencies are excluded.

## Current normal-tick path

`QTimer → _on_timer_tick → Qt SimulationWorker → LiveSimulationProcess.advance_days(status) → worker advance → complete economic simulation → record_day → status snapshot + current_rows + full public snapshot → DayStateEncoder full recursive diff + binary encoding → JSON/pipe → parent reader JSON/decompress/unpickle → apply_day_delta to full canonical GameState → active UI update → paint/heartbeat`.

The worker owns the complete authoritative economy, **and** a detached full public comparison baseline. The parent owns a full canonical public world, current-row tables, UI row copies and bounded chart caches. `_snapshots` view keys converge on the same full canonical object after applying a delta. Hidden main widgets remain idle, but their state is still synchronized. `_runtime_result` ignores the requested active-view profile for daily selection and explicitly calls `snapshot_for_view('full')`; there is no hidden full-snapshot wire fallback on normal ticks.

`snapshot_for_view(view_key)` in the parent is a local lookup. Opening a main view, entity or sub-tab does not currently ask the worker for current detail state. Deep history already has a separate background request path, but current detail fields depend on the broad mirror.

## Measured timer latency and decode attribution

Mature normal days, excluding the reporting day; medians in milliseconds. The retained 1.85 s result is a prior measurement of the identical source, not a new before/after implementation comparison.

| Metric | Fresh native, global event observer | Fresh native, minimal paint observer |
|---|---:|---:|
| T0→T4 | 2,165.31 | 2,271.45 |
| Simulation core | 229.14 | 240.55 |
| Full public snapshot preparation | 104.33 | 108.22 |
| worker.day_delta (diff + encoding + cleanup) | 671.07 | 697.30 |
| Parent decode wall time | 598.73 | 746.11 |
| Reader decode thread CPU | 125.00 | 140.62 |
| Decompression wall time | 521.52 | 669.15 |
| Unpickle | 27.10 | 26.68 |
| Base64 | 3.16 | 3.27 |
| Decode gen-0 collection | 8.44 | 8.16 |
| Decode gen-1 collection | 40.65 | 39.52 |
| Explicit sleep(0) yield | 0.25 | 0.22 |
| Apply delta | 67.30 | 39.37 |
| Active UI update | 24.68 | 27.74 |
| T4−T2 | 177.56 | 207.58 |
| Largest complete heartbeat gap | 399.42 | 381.95 |

Median native response: 2.32 MB. No architecture change is represented by these columns. The minimal observer changes measurement coverage only; it preserves the same production worker/UI and produces an exactly equal final economics/RNG signature.

**Cause of the ~635 ms generation span:** recursive dictionary traversal of the complete public world; history equality and prefix/rollover slicing for every series; detached changed-value copies; tens of thousands of path/update/splice objects; per-object persistent-ID checks while pickling; compression and cleanup. Explicit top-level section timers and separate profiles show company state and regional histories dominate. Generation is not simply JSON serialization. The full snapshot preparation cost precedes the day-delta timer and must also disappear from a compact normal-tick path.

**Cause of the ~501 ms decode span:** it is elapsed reader-thread time, not 501 ms of JSON parsing or object reconstruction. Fresh native measurements put most wall time in `zlib.decompress`; isolated decoding spends only a few milliseconds in the same decompression. zlib releases the GIL, so this span includes waiting to resume alongside Qt/Python activity. Unpickling and gen-1 collection add real costs. The native observer control above distinguishes measurement overhead from actual desktop contention; attributing the entire 501 ms to invisible field decoding would be incorrect. The retained baseline's median gen-1 collection is about 37 ms, not 500 ms. Explicit `sleep(0)` is small in the new native run.

Generation profile/raw decoder component timing: `generation-mature-detailed.txt`, `decode-mature-detailed.txt`, corresponding `.pstats`, and per-chunk/CPU spans in native records. Profiler wall times are diagnostic only. Thread CPU on Windows has coarse sampling resolution; do not infer precise sub-millisecond CPU costs from its small-section values.

### Native rendering and visible correctness

The separate native rendering profile observed **29 ticker paints, 58 complete item loops and 60,552 `QPainter.drawText` calls in one diagnostic tick**. `TickerTape.paintEvent` draws two whole long tiles, and `_draw_items` formats/measures/draws every item even when it is outside the clipped viewport. The initial ticker contains 348 items. The profile identifies text drawing and font-width calculation as large costs. Its overlapping Qt/reader/wait spans are not additive or exclusive per-thread CPU attribution; use call counts plus the explicit reader thread CPU/native-offscreen controls as evidence. The minimized observer does not remove this contention.

At the conventional T4 boundary, `ticker_pending_at_t4` is **True** and displayed current items match the worker's current ticker values is **False**. `TickerTape.set_items` buffers replacements; `scroll` applies them only at an entire tile wrap. The measured tile is 99,944 pixels wide. At two pixels per nominal 66 ms timer callback, a complete cycle is approximately 55.0 minutes (remaining time depends on offset; scheduling can extend it). This is existing stale visible ticker behavior, not an optimization introduced by this audit.

Consequently the reported T0→T4 samples mean the existing active-view/paint-ready boundary, **not proven time until every visible global value is current**. Active-view date/receiver state are checked; ticker correctness explicitly fails this stronger boundary. Time until current ticker values appear was not waited out or claimed measured. A later implementation must make current visible ticker values correct promptly and avoid drawing/measuring invisible ticker items, while preserving the ticker product's intended contents/ranking. Narrowing world synchronization cannot by itself fix this native rendering/correctness issue.

### Full encoder section timings

The first mature detached public mirror contains 301,992 dictionary fields, 2,068,212 history points and 8,898,478 scalar values. The profiled unchanged generation visits 29,410 mapping calls and 40,730 sequence calls; it performs 781,002 persistent-ID callbacks during pickling. The first daily body contains 46,430 operations. Those counters explain why an append-only wire delta still incurs broad preparation work.

These are timers inside the actual full encoder, rather than partitioned replays. They measure diff traversal/copy work only; binary encoding and cleanup are separate. Medians from three mature isolated diagnostic updates:

| Actual full encoder component | Median ms |
|---|---:|
| Diff `stocks` | 152.91 |
| Diff `commodities` | 3.71 |
| Diff `processed_products` | 7.20 |
| Diff `cryptos` | 1.92 |
| Diff `funds` | 12.31 |
| Diff `indices` | 8.97 |
| Diff `derivatives` | 12.05 |
| Diff `portfolio` | 0.00 |
| Diff `perpetuals` | 0.00 |
| Diff `fx_balances` | 0.01 |
| Diff `loans` | 0.01 |
| Diff `bonds` | 0.00 |
| Diff `bond_market` | 24.10 |
| Diff `news` | 0.00 |
| Diff `macro` | 76.96 |
| Diff `macro_history` | 0.13 |
| Diff `global_macro` | 0.03 |
| Diff `global_macro_history` | 0.14 |
| Diff `forex_history` | 3.40 |
| Diff `currency_strength` | 0.03 |
| Diff `portfolio_history` | 0.01 |
| Diff `realized_pnl_history` | 0.00 |
| Binary encode of mixed full changes | 184.87 |
| Whole isolated update, including encode/cleanup | 542.04 |

## Consumer matrix

A globally live; B active main view; C selected entity/detail; D visible sub-tab; E explicit action; F Save/Restore/Debug; G simulation-internal. Categories below partition the current public world. C/D rows may contain fields requiring a narrower allowlist; only the consumer's actual displayed dependencies should be extracted. Ticker ranking requires worker-side access to all candidates, not parent synchronization of all candidate histories.

Payload is isolated encoded daily category KiB, not a full snapshot size. Diff/encode/decode are isolated median milliseconds over three mature ticks. Decode here is reconstruction with automatic GC disabled; real full-reader collection/scheduling costs are in the native table above.

| State category | Class | Consumers | Visible on unselected Markets | KiB/day | Diff ms | Encode ms | Decode ms | Proposed ownership |
|---|---|---|---|---:|---:|---:|---:|---|
| bond_market | B/C/D | Bond Market table; selected bond chart; held-bond valuation | No | 14.77 | 26.80 | 1.85 | 0.43 | Worker; explicit active projection / on-open read |
| bonds | B/C | Portfolio owned-bond detail | No | 0.08 | 0.02 | 0.01 | 0.01 | Worker; explicit active projection / on-open read |
| commodities.detail_internal | C/D/B (+G unused fields) | Selected fundamentals/details; related active views | No | 6.92 | 0.89 | 0.47 | 0.17 | Worker; explicit active projection / on-open read |
| commodities.other_history | C/D | Selected supply/positioning/product history | No | 4.94 | 2.28 | 0.85 | 0.17 | Worker; explicit active projection / on-open read |
| commodities.price_history | C/D | Selected preview/chart; portfolio selected holding | No without selection | 1.97 | 0.34 | 0.23 | 0.08 | Worker; explicit active projection / on-open read |
| commodities.psychology | C/D (+G unused components) | Selected positioning/long-short charts | No | 3.67 | 0.31 | 0.26 | 0.12 | Worker; explicit active projection / on-open read |
| commodities.quotes_metadata | B (+A derived ticker) | Market table/filter/sort; ticker uses only ranked quotes | Yes, except products | 1.64 | 0.15 | 0.15 | 0.04 | Worker; explicit active projection / on-open read |
| cryptos.detail_internal | C/D/B (+G unused fields) | Selected fundamentals/details; related active views | No | 4.39 | 0.91 | 0.26 | 0.08 | Worker; explicit active projection / on-open read |
| cryptos.other_history | C/D | Selected supply/positioning/product history | No | 1.23 | 0.25 | 0.17 | 0.05 | Worker; explicit active projection / on-open read |
| cryptos.price_history | C/D | Selected preview/chart; portfolio selected holding | No without selection | 1.95 | 0.23 | 0.20 | 0.06 | Worker; explicit active projection / on-open read |
| cryptos.psychology | C/D (+G unused components) | Selected positioning/long-short charts | No | 3.63 | 0.27 | 0.23 | 0.08 | Worker; explicit active projection / on-open read |
| cryptos.quotes_metadata | B (+A derived ticker) | Market table/filter/sort; ticker uses only ranked quotes | Yes, except products | 1.63 | 0.16 | 0.13 | 0.04 | Worker; explicit active projection / on-open read |
| currency_strength | B/C/E | Forex/Portfolio conversions; selected trade/labels | No (selected trade/conversion may need subset) | 0.57 | 0.02 | 0.05 | 0.02 | Worker; explicit active projection / on-open read |
| derivatives.detail_internal | C/D/B (+G unused fields) | Selected fundamentals/details; related active views | No | 5.19 | 3.54 | 0.67 | 0.17 | Worker; explicit active projection / on-open read |
| derivatives.price_history | C/D | Selected preview/chart; portfolio selected holding | No without selection | 24.54 | 5.17 | 2.37 | 0.50 | Worker; explicit active projection / on-open read |
| derivatives.psychology | C/D (+G unused components) | Selected positioning/long-short charts | No | 0.08 | 1.02 | 0.00 | 0.01 | Worker; explicit active projection / on-open read |
| derivatives.quotes_metadata | B (+A derived ticker) | Market table/filter/sort; ticker uses only ranked quotes | Yes, except products | 9.55 | 3.04 | 1.01 | 0.26 | Worker; explicit active projection / on-open read |
| forex_history | C/D | Selected Forex chart | No | 7.31 | 3.43 | 1.21 | 0.27 | Worker; explicit active projection / on-open read |
| funds.allocations_flows_fees | C/D | Selected fund allocations/overview | No | 3.47 | 2.67 | 0.47 | 0.15 | Worker; explicit active projection / on-open read |
| funds.detail_internal | C/D/B (+G unused fields) | Selected fundamentals/details; related active views | No | 19.05 | 5.03 | 1.48 | 0.37 | Worker; explicit active projection / on-open read |
| funds.other_history | C/D | Selected supply/positioning/product history | No | 4.77 | 2.45 | 0.82 | 0.18 | Worker; explicit active projection / on-open read |
| funds.price_history | C/D | Selected preview/chart; portfolio selected holding | No without selection | 13.61 | 2.32 | 1.16 | 0.35 | Worker; explicit active projection / on-open read |
| funds.quotes_metadata | B (+A derived ticker) | Market table/filter/sort; ticker uses only ranked quotes | Yes, except products | 11.79 | 2.37 | 0.91 | 0.28 | Worker; explicit active projection / on-open read |
| fx_balances | B/E | Portfolio/Forex; selected trade validation | No | 0.08 | 0.02 | 0.00 | 0.00 | Worker; explicit active projection / on-open read |
| global_macro | B/C | Global Macro dashboard | No | 0.55 | 0.02 | 0.06 | 0.03 | Worker; explicit active projection / on-open read |
| global_macro_history | B/C/D | Global Macro visible indicator charts | No | 0.84 | 0.18 | 0.14 | 0.05 | Worker; explicit active projection / on-open read |
| global_status | A | Date/cash/currency; topbar | Yes | 0.22 | 0.01 | 0.06 | 0.03 | Worker; send status |
| indices.detail_internal | C/D/B (+G unused fields) | Selected fundamentals/details; related active views | No | 40.60 | 4.05 | 2.29 | 0.68 | Worker; explicit active projection / on-open read |
| indices.price_history | C/D | Selected preview/chart; portfolio selected holding | No without selection | 16.95 | 2.79 | 1.39 | 0.32 | Worker; explicit active projection / on-open read |
| indices.quotes_metadata | B (+A derived ticker) | Market table/filter/sort; ticker uses only ranked quotes | Yes, except products | 13.47 | 2.80 | 1.35 | 0.35 | Worker; explicit active projection / on-open read |
| loans | B | Portfolio loan total | No | 0.08 | 0.02 | 0.00 | 0.00 | Worker; explicit active projection / on-open read |
| macro.current_trade | B/C/D (+G unused fields) | Macro/Trade Map/News; selected company related products | Country names only | 165.55 | 21.30 | 14.50 | 3.47 | Worker; explicit active projection / on-open read |
| macro.history | C/D | Selected country/product production/trade charts | No | 253.24 | 56.14 | 58.24 | 9.92 | Worker; explicit active projection / on-open read |
| macro_history | B/C/D | News calendar historical values; selected country chart | No | 0.08 | 0.18 | 0.00 | 0.01 | Worker; explicit active projection / on-open read |
| news | B/C/D | News feed/calendar; Macro economic context | No | 0.08 | 0.01 | 0.00 | 0.00 | Worker; explicit active projection / on-open read |
| perpetuals | B/E | Portfolio/future controls | No | 0.08 | 0.00 | 0.00 | 0.00 | Worker; explicit active projection / on-open read |
| portfolio | B/E | Portfolio positions; selected sell validation | No | 0.08 | 0.00 | 0.00 | 0.00 | Worker; explicit active projection / on-open read |
| portfolio_history | B/D | Portfolio analytics history | No | 0.19 | 0.01 | 0.04 | 0.02 | Worker; explicit active projection / on-open read |
| processed_products.detail_internal | C/D/B (+G unused fields) | Selected fundamentals/details; related active views | No | 15.58 | 1.66 | 0.82 | 0.29 | Worker; explicit active projection / on-open read |
| processed_products.other_history | C/D | Selected supply/positioning/product history | No | 9.68 | 5.28 | 2.02 | 0.39 | Worker; explicit active projection / on-open read |
| processed_products.price_history | C/D | Selected preview/chart; portfolio selected holding | No without selection | 0.08 | 0.26 | 0.01 | 0.01 | Worker; explicit active projection / on-open read |
| processed_products.quotes_metadata | B (+A derived ticker) | Market table/filter/sort; ticker uses only ranked quotes | Yes, except products | 0.08 | 0.20 | 0.00 | 0.00 | Worker; explicit active projection / on-open read |
| realized_pnl_history | B/D | Portfolio analytics realized return | No | 0.08 | 0.00 | 0.00 | 0.00 | Worker; explicit active projection / on-open read |
| stocks.detail_internal | C/D/B (+G unused fields) | Selected fundamentals/details; related active views | No | 39.88 | 33.90 | 3.65 | 0.88 | Worker; explicit active projection / on-open read |
| stocks.input_output | C/D/B | Selected company supply; Supply Chain | No | 32.82 | 9.90 | 3.20 | 0.80 | Worker; explicit active projection / on-open read |
| stocks.other_history | C/D | Selected supply/positioning/product history | No | 207.99 | 75.47 | 69.45 | 9.13 | Worker; explicit active projection / on-open read |
| stocks.price_history | C/D | Selected preview/chart; portfolio selected holding | No without selection | 65.59 | 13.17 | 6.80 | 1.24 | Worker; explicit active projection / on-open read |
| stocks.psychology | C/D (+G unused components) | Selected positioning/long-short charts | No | 133.81 | 13.58 | 9.03 | 1.97 | Worker; explicit active projection / on-open read |
| stocks.quotes_metadata | B (+A derived ticker) | Market table/filter/sort; ticker uses only ranked quotes | Yes, except products | 52.48 | 8.22 | 4.58 | 1.09 | Worker; explicit active projection / on-open read |
| stocks.simulation_internal | G | Engine only; no direct displayed consumer | No | 49.15 | 25.20 | 6.22 | 1.52 | Worker only |
| Deep history | C/D/E/F | Requested ALL/chart history; persistence | No | Not in normal delta | — | — | — | Worker/store; request selected series |
| Private caches / RNG / save-only checkpoint fields | G/F | Engine / checkpoint / deterministic debug | No | 0 | Private keys skipped | 0 | 0 | Worker/checkpoint only |
| Event / phase rows | B/E/F | News economic context / debug telemetry | No | See current-row appendix | — | JSON | JSON | Worker; explicit consumer only |

Global portfolio summary: the actual topbar shows **cash**, not NAV/gross exposure/positions. Cash is already a precomputed status scalar. Portfolio full positions/loans/FX/owned bonds are B/C/E, not automatically A. Selected trade controls need only relevant position/balance/rate/contract rules; authoritative validation already has a worker command. A currency conversion may require the selected region and GD/XAU strength, not every FX history.

Company quantity histories and market product supply/demand are used when a company Supply Chain tab is open. Fund allocation detail currently resolves constituent names/weights across stocks, indices and bonds; a worker-side selected-fund projection can resolve these references once. This does not require synchronizing their equivalent full details in the parent. Some existing detail constructors call `ensure_*_fundamentals` on UI copies; replacing those initializers with authoritative selected display values belongs in shell/consumer adaptation, not economic formula changes.

## Traversal, emitted data and allocations by category

This appendix records actual dictionary visit counts, available sequence slots, emitted scalar leaves, emitted history tail points, and separate traced net allocations. Net retained blocks/bytes are not total lifetime allocation counts; transient peak bytes are also retained in JSON. Exact C-level list/tuple comparator counts are not available without changing equality semantics.

| Category | Entities | Dict fields visited | Sequence comparison slots | Scalars emitted | History tail points | Traced net KiB | Net blocks |
|---|---:|---:|---:|---:|---:|---:|---:|
| bond_market | 0 | 36,287 | 93,436 | 2,279 | 140 | 432.94 | 7,173 |
| bonds | 0 | 1 | 0 | 0 | 0 | 1.09 | 18 |
| commodities.detail_internal | 34 | 1,091 | 0 | 651 | 0 | 67.07 | 1,082 |
| commodities.other_history | 34 | 341 | 217,600 | 1,496 | 306 | 236.28 | 4,938 |
| commodities.price_history | 34 | 69 | 24,854 | 272 | 34 | 29.95 | 638 |
| commodities.psychology | 34 | 409 | 0 | 278 | 0 | 35.10 | 583 |
| commodities.quotes_metadata | 34 | 205 | 0 | 102 | 0 | 21.31 | 377 |
| cryptos.detail_internal | 32 | 1,473 | 0 | 347 | 0 | 44.27 | 606 |
| cryptos.other_history | 32 | 65 | 16,640 | 128 | 32 | 25.74 | 547 |
| cryptos.price_history | 32 | 65 | 23,392 | 256 | 32 | 27.82 | 595 |
| cryptos.psychology | 32 | 385 | 0 | 264 | 0 | 33.40 | 553 |
| cryptos.quotes_metadata | 32 | 257 | 0 | 96 | 0 | 20.11 | 356 |
| currency_strength | 0 | 22 | 0 | 20 | 0 | 4.02 | 69 |
| derivatives.detail_internal | 566 | 6,268 | 0 | 509 | 0 | 222.60 | 3,790 |
| derivatives.price_history | 566 | 1,133 | 413,746 | 4,528 | 566 | 528.64 | 11,277 |
| derivatives.psychology | 566 | 1,133 | 0 | 0 | 0 | 1.04 | 19 |
| derivatives.quotes_metadata | 566 | 5,095 | 0 | 840 | 0 | 307.43 | 5,338 |
| forex_history | 0 | 421 | 307,020 | 2,100 | 420 | 320.95 | 7,087 |
| funds.allocations_flows_fees | 271 | 8,624 | 4,757 | 4,427 | 5 | 1,767.00 | 27,528 |
| funds.detail_internal | 271 | 5,421 | 0 | 1,890 | 0 | 283.86 | 4,482 |
| funds.other_history | 271 | 543 | 198,643 | 1,355 | 271 | 218.87 | 4,561 |
| funds.price_history | 271 | 543 | 198,101 | 2,168 | 271 | 253.03 | 5,375 |
| funds.quotes_metadata | 271 | 2,982 | 0 | 1,084 | 0 | 206.53 | 3,864 |
| fx_balances | 0 | 22 | 0 | 0 | 0 | 0.91 | 18 |
| global_macro | 0 | 23 | 0 | 16 | 0 | 4.70 | 75 |
| global_macro_history | 0 | 23 | 16,082 | 110 | 22 | 18.95 | 405 |
| global_status | 0 | 3 | 0 | 1 | 0 | 2.21 | 38 |
| indices.detail_internal | 340 | 4,941 | 0 | 2,560 | 0 | 466.52 | 7,613 |
| indices.price_history | 340 | 681 | 248,540 | 2,720 | 340 | 318.49 | 6,756 |
| indices.quotes_metadata | 340 | 2,721 | 0 | 1,020 | 0 | 254.44 | 4,558 |
| loans | 0 | 22 | 0 | 0 | 0 | 0.87 | 18 |
| macro.current_trade | 20 | 17,531 | 0 | 13,763 | 0 | 2,518.21 | 36,688 |
| macro.history | 20 | 22,421 | 143,300 | 99,500 | 19,900 | 14,497.09 | 280,102 |
| macro_history | 0 | 161 | 4,160 | 0 | 0 | 0.87 | 18 |
| news | 0 | 1 | 100 | 0 | 0 | 1.23 | 22 |
| perpetuals | 0 | 1 | 0 | 0 | 0 | 1.46 | 26 |
| portfolio | 0 | 1 | 0 | 0 | 0 | 1.39 | 25 |
| portfolio_history | 0 | 1 | 733 | 4 | 1 | 2.47 | 48 |
| processed_products.detail_internal | 90 | 2,298 | 1,072 | 1,571 | 0 | 165.86 | 2,614 |
| processed_products.other_history | 90 | 811 | 529,200 | 3,600 | 720 | 554.55 | 11,574 |
| processed_products.price_history | 90 | 181 | 0 | 0 | 0 | 1.26 | 23 |
| processed_products.quotes_metadata | 90 | 271 | 0 | 0 | 0 | 0.87 | 18 |
| realized_pnl_history | 0 | 1 | 0 | 0 | 0 | 0.98 | 20 |
| stocks.detail_internal | 1,280 | 48,521 | 0 | 2,875 | 0 | 987.66 | 16,996 |
| stocks.input_output | 1,280 | 11,471 | 0 | 2,324 | 0 | 948.94 | 16,209 |
| stocks.other_history | 1,280 | 31,253 | 730,930 | 70,450 | 14,346 | 10,602.24 | 206,832 |
| stocks.price_history | 1,280 | 2,561 | 935,680 | 10,240 | 1,280 | 1,205.49 | 25,548 |
| stocks.psychology | 1,280 | 15,361 | 0 | 10,908 | 0 | 1,482.15 | 24,856 |
| stocks.quotes_metadata | 1,280 | 8,961 | 0 | 3,840 | 0 | 1,013.02 | 17,799 |
| stocks.simulation_internal | 1,280 | 24,321 | 0 | 5,128 | 0 | 1,001.18 | 17,735 |

## Actual daily current-row transport

Besides the delta, ordinary mature ticks transmit `asset_current`, `product_current`, `forex_current`, `bond_current` and `phase_metric_current`. Bond/FX rows travel even when Markets is visible. Other tables below exist as worker materializations and are sent when their changed-table flags require it, not necessarily every day. On-open selection should reuse authoritative worker data or explicit read extraction, without adding a second mirror.

| Table | Rows available | JSON KiB | Ordinary diagnostic day emitted? | Extract ms | Markets consumer |
|---|---:|---:|---|---:|---|
| asset_current | 2,523 | 354.30 | True | 4.16 | Quotes/ticker (contains more than the displayed fields) |
| product_current | 124 | 32.59 | True | 0.20 | None without selected detail |
| company_current | 1,280 | 504.27 | False | 3.02 | None without selected detail |
| company_output_current | 13,066 | 1,187.14 | False | 8.00 | None without selected detail |
| country_trade_current | 2,480 | 500.41 | False | 2.11 | None without selected detail |
| fund_allocation_current | 2,376 | 218.00 | False | 0.99 | None without selected detail |
| country_current | 20 | 12.43 | False | 0.08 | None without selected detail |
| forex_current | 420 | 41.03 | True | 0.47 | None without selected detail |
| bond_current | 1,504 | 627.69 | True | 3.00 | None without selected detail |
| portfolio_current | 1 | 0.06 | False | 0.01 | None without selected detail |
| news_current | 0 | 0.00 | False | 0.89 | None without selected detail |
| event_current | 0 | 0.00 | False | 0.85 | None without selected detail |
| phase_metric_current | 15 | 0.91 | True | 0.02 | None without selected detail |

## Share needed by the active UI

For Markets with no selected instrument/chart, a conservative upper bound includes quote/metadata fields for **every** market-table instrument, even hidden asset types, plus status. It excludes product rows and country details. This subset accounts for 7.74% of category dictionary visits, 2.75% of emitted scalar values, 7.26% of isolated delta bytes, and 5.87% of isolated reconstruction cost. **95.43% of isolated diff+encode cost is outside that subset.** These are diagnostic shares, not a promised equivalent fraction of total native latency.

The visible filtered table does need fresh quotes for correct sorting/filtering and for rows revealed by scrolling. Sending only the viewport's displayed rows without maintaining correct sort/filter results would be wrong. The all-instruments upper bound avoids claiming gains from dropping those dependencies. Static metadata need not be retransmitted daily except for relevant topology/metadata changes.

An audit-only read extraction from authoritative engine objects, with no full snapshot or recursive diff, measured:

| Read-only projection | Median ms / bytes |
|---|---:|
| All market-table rows + pre-ranked ticker + status extraction | 27.63 |
| JSON encode | 6.92 |
| JSON decode | 5.12 |
| JSON bytes (including static metadata) | 349,247.00 |
| Full public copy of one selected stock | 0.66 |
| One selected stock JSON bytes (includes histories) | 49,328.00 |

All 2,523 quote rows exactly match the existing full snapshot's quote values, identity, region and metadata. The probe is evidence that explicit reads are possible without mutation hooks. It is not a replacement contract, does not measure UI apply/render or on-demand switch IPC, and does not establish low-hundreds-of-milliseconds T0→T4.

## All nine views and existing switch costs

Three ticks per view in each rotating offscreen run; different simulation dates, not paired performance comparisons. Warm switch includes refresh and `processEvents`; asynchronous history completion can extend beyond this synchronous number. Mature cold construction measurements precede the run. Selected details and hidden sub-tabs are source-audited; exhaustive future on-demand behavior is not implemented/tested.

| View | Young T0→T4 ms | Mature T0→T4 ms | Mature max heartbeat gap ms | Young warm switch ms | Mature warm switch ms | Mature initial load ms |
|---|---:|---:|---:|---:|---:|---:|
| markets | 1,047.58 | 1,156.22 | 73.26 | 339.77 | 4,224.55 | 72.80 |
| supply_chain | 910.32 | 1,175.13 | 62.38 | 37.05 | 32.22 | 199.52 |
| forex | 934.03 | 1,170.68 | 71.05 | 36.71 | 32.52 | 447.56 |
| bondmarket | 1,023.14 | 1,121.04 | 126.57 | 17.02 | 22.82 | 235.15 |
| portfolio | 966.99 | 1,191.38 | 60.61 | 10.78 | 10.13 | 247.02 |
| macro | 1,225.97 | 1,263.88 | 87.18 | 23.65 | 20.91 | 441.53 |
| trade_map | 1,038.53 | 1,195.07 | 268.62 | 33.42 | 33.48 | 73.34 |
| global_macro | 1,108.13 | 1,138.47 | 292.52 | 34.91 | 54.10 | 277.29 |
| news | 1,081.40 | 1,108.39 | 74.80 | 173.25 | 161.53 | 799.71 |

Returning to Markets calls `MarketsView.refresh`, rebuilding all table row histories through `_prepare_local_histories`/`IncrementalHistory`, even though only a table or one detail is visible. It is already slow in a mature world. A later contract must avoid using the existing full refresh as its generic on-demand population mechanism. Do not shift normal-tick work into this path.

View dependencies: Markets quotes/filter metadata + selected preview/detail; Supply Chain product/service rows + selected product/country/company breakdown; Forex rates/balances/conversion scalars + selected pair chart; Bond Market offers/filter metadata + selected bond detail; Portfolio precomputed totals and owned positions/bonds/currencies + selected holding chart; Macro country aggregate rows + selected country charts/supply/trade/sectors; Trade Map country/map totals and selected product flows; Global Macro visible indicator values/charts; News feed and calendar rows + selected news/calendar context. Portfolio and News currently refresh hidden tabs too; these are consumer-level opportunities, not globally live requirements.

## Seven audit decisions

1. **Broader parent mirror? Yes.** It contains all public asset/company/country detail and histories regardless of active view, plus current-row copies. Main-widget laziness does not narrow the protocol.
2. **Invisible/unneeded share?** The measured diagnostic proportions above support a large majority of state-processing work being unneeded on an unselected Markets tick. Native decode includes scheduling and GC, so do not equate its full wall time with the section reconstruction sum.
3. **Truly globally live?** Date, cash, display currency/control status and the already-ranked ticker items. A compact revision/date context is needed for consistency. Full portfolio, countries, FX/bonds and asset histories are not globally live display dependencies.
4. **Active/on-demand?** Table/dashboard projections for the active main view, the selected entity's header/trade context, the visible sub-tab's fields and visible/live history endpoints. Related product/constituent information should be resolved in one worker-side selected-detail response.
5. **Can broad day_delta disappear? Yes from normal ticks, in principle.** Existing full state/checkpoint operations remain explicit for restore/debug/save as needed. A small explicit active contract can replace broad comparison; whether limited active deltas or full compact active rows are best belongs to Phase 2.
6. **Can compact explicit extraction replace comparison? Yes, supported by the quote/read probe and existing current-table materializations.** It must include dynamic topology, sort/filter correctness and selected dependencies; transmitting a stale filtered viewport is not sufficient.
7. **Without thousands of mutation hooks? Yes for extraction.** Read finished authoritative objects/tables at a completed simulation revision. Required changes are worker/proxy IPC and shell/view consumers. No evidence requires economic assignment instrumentation. Stop if detailed contract design instead needs economic formula rewrites, new broad mirrors or fragile revision coupling.

## Validation and boundaries

Section runs assert exact prepared-delta/receiver equality for every public field. Category replays assert exact diff outputs and resulting values. Economics/RNG signatures before and after diagnostic reads match. All UI samples pass timestamp ordering, completion, request/slot/update main-thread checks and worker shutdown. Matching native control runs end with exactly equal economics/RNG signatures. Source SHA-256 checks prove production files unchanged.

**25 focused tests passed in 54.21 seconds**: `test_day_delta.py`, `test_day_delta_views.py`, `test_day_delta_process.py`, and `test_workspace_views.py`. These include exact actual process timer/Step state and RNG comparison, Save/Load, explicit authoritative snapshot comparison and all nine views. Results: `focused-tests.txt` and `focused-tests.xml`. The prior identical-source release run recorded 330 passing tests and an exact 365-day economics/RNG/checkpoint/database comparison, including Save/Load/history coverage. That full suite and 365-day comparison were **not rerun in this audit**; no implementation was changed. Future on-demand A→B→A, hidden-sub-tab refresh after many days, Save/Load repetition and exact chart/EMA/Candle behavior remain Phase 6 requirements, not claimed completed here.

Young/report/month-end evidence: fresh rotating young run covers a report date and month end; native mature run covers a report date. No fresh flush/day-type sweep was performed. The identical-source retained native first-year run has normal-no-flush median 1,413.41 ms, report 1,893.74 ms, month-end 1,369.29 ms and flush 4,439.52 ms. Those are retained baseline data, not new post-change results. Current persistence/flush remains an independent worker cost and is not removed by narrowing UI state.

## Deliverables and final verdict

Added files: `tools/ui_state_architecture_audit.py`, `tools/ui_state_architecture_report.py`, and this report. Raw JSON, source-consumer index, profiles, decoder CPU/component spans, per-section counters and allocation records are under `.cache/ui-state-architecture-audit/` (ignored local audit artifacts). No production files were changed during this pass.

Broad synchronization removed/reduced: **none in production**. New tick contract/on-demand behavior: **not implemented**. Before/after payload, extraction, decode, apply, native block and T0→T4 improvements: **not claimed**. Simulation core is **not** the dominant elapsed component in the current native path. Remaining bottlenecks include broad public snapshot/diff/encoding, unnecessary bond/FX current-row transport, ticker text rendering and stale pending ticker items, native reader/Qt contention, GC and mature Markets full refresh; flush remains separate.

**Final verdict: more targeted architecture work is justified.** The evidence supports Phase 2 minimal global/active-view/selected-detail/visible-history contract design. It does not support a generic full-profile on-demand fetch, another broad cache or a declaration of fluid gameplay. A later candidate must remeasure native T0→T4 and view-switch readiness with a minimally perturbing observer, then pass exact economics/history/Save/Load regression checks.
