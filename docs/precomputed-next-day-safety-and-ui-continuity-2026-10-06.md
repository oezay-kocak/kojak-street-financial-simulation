# Precomputed next day safety audit and UI continuity pass — 6 October 2026

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


**Historical pass:** the subsequently approved retail-investor product rule removes the economic/RNG couplings identified here. See [the retail implementation and renewed precompute assessment](retail-investor-decoupling-and-precompute-2026-10-06.md) for the final current decision: retail decoupling is implemented and validated; full/partial speculation remains disabled after measured sustained copy/readiness costs. The findings below describe the source before that semantic correction.

**Decision: Case C under the document's stop conditions. Full next-day precomputation was not implemented.** Ordinary supported actions feed the integrated next-day world and shared RNG. The independent UI continuity fixes were implemented, with sequential economics, persistence and save compatibility retained.

This is a decision about the current architecture and the requested constraints, not a proof that every possible precomputation architecture is impossible. Invalidating a flag alone is insufficient: the current worker mutates its only authoritative world, portfolio, RNG and analytical store while stepping. Retaining N for nine on-demand views, trade validation, save and histories while that world has become N+1 requires an isolated current world or rollback/reconciliation. Since ordinary spot actions also change integrated portfolio history/settlement results, reconciliation is not a small exceptional path. This pass does not add that machinery or change the economy/RNG design to make independence true.

Evidence: `.cache/precompute-audit/branches.json`, `source-comparison.json`, focused/full test XML, and `.cache/visible-ui-sync/zero-final-*`. Existing dirty work was preserved. Source comparison is against a copy taken at the start of this task: **zero files in `src/kojakstreet/core` changed**.

## Player-action safety gate (items 1–5)

| Player action | Portfolio mutation | Immediate economic-book mutation | Input to next-day core | RNG effect | Would invalidate N+1? | Evidence |
|---|---|---|---|---|---|---|
| Stock BUY/SELL | Positions, FX cash, realized PnL/date | No direct market-book edit | Report dividends, net-worth history and margin-call gate | No draw in command/dividend path | Yes: integrated portfolio step | `trading.execute_spot_trade`, `company_lifecycle.pay_dividend`, `simulation.step_day` |
| LONG/SHORT open, add, close on stock/commodity/crypto | Margin, size, entry, payout | No direct market-book edit | Position size directly contributes to open interest, imbalance/squeeze and subsequent market pricing | No command draw; different dynamics can alter later branches | Yes: world and portfolio | `market_calculations._perpetual_position_interest`, `_update_open_interest`; `portfolio_risk` |
| Dated derivatives/futures | Margin, contract expiry/date, PnL | No direct market-book edit | Settlement eligibility and entry marks; complete portfolio/history step | No direct command draw | Yes | `trading._future_expiry_date`, `update_future_settlements` |
| Option/CDS spot BUY/SELL | Inventory and copied contract terms | No direct market-book edit | Expiry/default settlements, payouts/news/portfolio history | No direct draw in settlement | Yes | `trading._copy_spot_derivative_contract`, `portfolio_risk` |
| Funds BUY/SELL | Inventory/FX cash | No direct market-book edit | Net-worth history and margin-call gate | No direct command draw | Yes: integrated portfolio | `trading.execute_spot_trade`, `accounting.get_net_worth` |
| Commodities spot BUY/SELL | Inventory/FX cash | No direct market-book edit | Net-worth history and margin-call gate | No direct command draw | Yes: integrated portfolio | Same spot path; XAU currency-conversion marks remain current-day inputs |
| Crypto spot BUY/SELL | Holdings, cash | No direct market-book edit | **Monthly fee payout consumes shared RNG only when held**; excess-universe trimming also respects holdings | **Holding-dependent `random.uniform(0.01, 0.03)` on reports** | **Yes: broad economy/RNG** | `monthly_assets.update_monthly_crypto:59–64`; `cryptos._trim_excess_universe` |
| FX exchange | Currency balances | No direct market-book edit | Conversion at N prices, credit charges, net-worth history/game-over gate | None directly | Yes: integrated portfolio | `trading.exchange_currency`, `accounting.update_credit_interest` |
| Owned bonds | Coupon clocks, principal/recovery, cash | No direct market-book edit | Maturity, news, net worth and subsequent world RNG | **Corporate maturity calls shared `random.random()`** | Yes | `bond_calculations.update_laufende_anleihen` |
| Bond purchase/sale | — | — | **No callable Qt purchase/sale route**; Bondmarket is read-only. Existing save holdings are supported | As above for owned holdings | No nonexistent action; holdings still constrain preparation | `BondMarketView`, worker command inventory |
| Loans/credit balances | Debt/FX cash | No direct market-book edit | Daily interest, net worth and margin calls | None directly | Yes | `accounting.update_credit_interest`; no loan command exposed by current Qt shell |
| Other cash mutation | Cash | No direct market-book edit | History and depleted-net-worth early return before policy/date advance | None directly | Yes | `accounting.get_net_worth`, `simulation.step_day` |
| Pause/resume | No portfolio mutation | No direct market-book edit | Scheduling/gating; an already-started sequential day finishes | Does not consume RNG itself | Publication gate, not an economic edit | `app.toggle_simulation`; `IntegratedRuntime.advance_day` explicitly enables a requested manual step |
| Speed/ticks per timeout | No | No direct market-book edit | Scheduling and number of days requested | No direct RNG draw | Scheduling gate | `ticks_per_timeout`, `_timer_interval_ms`; no exposed speed settings control |
| Main navigation, Back, tabs, chart range, filters, sorting, watchlist | No | No direct market-book edit | Read-only scope/history/Qt state; no daily advance | None | No | `visible`/`history` commands, view handlers |
| Display currency | No in normal valid-asset flow | No direct market-book edit | Formatting; missing/retired option asset fallback can choose a settlement currency | None | Conservatively yes for fallback settlement, if such settings are exposed | `portfolio_risk._settle_option_if_expired`; no Qt display-currency settings control |
| Save | No economics edit | No direct market-book edit | Serializes current authoritative checkpoint/history; flushes | No draw | Must discard speculative state in a future design | Existing checkpoint/session path retained |
| Load/world replacement | Replaces state | Replaces whole world | Entire world/date/RNG/history changes | Restores/resets RNG | Always | Existing load/bootstrap paths |
| Runtime seed change | No | No direct market-book edit | Existing books/date remain; future daily draws change | Resets Python/NumPy RNG | Always | `IntegratedRuntime.set_seed`; runtime API, not a current gameplay button |
| Stop/limit orders, standalone short sale, reserved Revalue/Export actions | — | — | **Not implemented/exposed**; shorts use FUTURE tickets | — | No nonexistent action | Worker dispatch and `ViewHeader` source inventory |

The 32 controlled comparisons restore the same seed-1729 checkpoint and Python/NumPy RNG before each branch. On normal and report dates they compare action→step against step→action, then one additional day. They call the real trading service and real daily economic core. They are dependency experiments, not a proposed reconciliation algorithm; after-step actions intentionally execute against the advanced world, so ordinary execution-price/contract-date differences are reported separately from economic-world/RNG differences. The audit creates only an isolated temporary store, not a live speculative implementation.

No-action controls match economy, RNG, portfolio and dates exactly on both days. LONG/SHORT opening and closing change stock market book hashes through open interest; the small tested ticket need not cross a squeeze threshold to prove the dependency. A crypto purchase before the report produces different stock, index, fund, FX, commodity, crypto and derivative results and different RNG immediately. The exact cause is the holding-dependent random crypto fee payout in `monthly_assets.py`, before subsequent market draws. An owned corporate bond maturity changes RNG on the first day and broad market books on the second day. Stock/fund/commodity spot examples have equal world/RNG in these branches but different portfolio/history, so they cannot be transplanted onto an already-integrated N+1 without preserving those effects.

| Day | Action | N+1 world fields that differ | N+1 RNG | N+1 portfolio fields that differ |
|---|---|---|---|---|
| normal | no action | identical | identical | identical |
| normal | stock buy | identical | identical | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| normal | stock sell | identical | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot, realisierte_guv_historie |
| normal | fund buy | identical | identical | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| normal | commodity buy | identical | identical | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| normal | crypto buy | identical | identical | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| normal | option buy | identical | identical | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| normal | long open | aktien | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot, perpetuals |
| normal | short open | aktien | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot, perpetuals |
| normal | short close | aktien | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot, realisierte_guv_historie |
| normal | dated future open | identical | identical | DEPOT_VERMOEGEN_HISTORIE, perpetuals |
| normal | FX exchange | identical | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot |
| normal | loan balance mutation (not exposed by Qt) | identical | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot |
| normal | corporate bond maturity (owned fixture; no Qt purchase route) | NEWS_SPEICHER | different | DEPOT_VERMOEGEN_HISTORIE, anleihen, forex_depot, realisierte_guv_historie |
| normal | display currency | identical | identical | identical |
| report | no action | identical | identical | identical |
| report | stock buy | identical | identical | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| report | stock sell | identical | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot, realisierte_guv_historie |
| report | fund buy | identical | identical | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| report | commodity buy | identical | identical | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| report | crypto buy | FOREX_PAARE_HISTORIE, GLI_HISTORIE, GLOBAL_MACRO_HISTORIE, aktien, bond_market, derivatives, fonds, gli_index, global_macro, indizes, kryptos, rohstoffe, waehrungen_staerke | different | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| report | option buy | identical | identical | DEPOT_VERMOEGEN_HISTORIE, depot, forex_depot |
| report | long open | aktien | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot, perpetuals |
| report | short open | aktien | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot, perpetuals |
| report | short close | aktien | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot, realisierte_guv_historie |
| report | dated future open | identical | identical | DEPOT_VERMOEGEN_HISTORIE, perpetuals |
| report | FX exchange | identical | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot |
| report | loan balance mutation (not exposed by Qt) | identical | identical | DEPOT_VERMOEGEN_HISTORIE, forex_depot |
| report | corporate bond maturity (owned fixture; no Qt purchase route) | NEWS_SPEICHER | different | DEPOT_VERMOEGEN_HISTORIE, anleihen, forex_depot, realisierte_guv_historie |
| report | display currency | identical | identical | identical |

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

- `src/kojakstreet/live_process.py`
- `src/kojakstreet/live_worker.py`
- `src/kojakstreet/ui_qt/app.py`
- `src/kojakstreet/ui_qt/combo_options.py`
- `src/kojakstreet/ui_qt/models/simple_table_model.py`
- `src/kojakstreet/ui_qt/views/bondmarket_view.py`
- `src/kojakstreet/ui_qt/views/forex_view.py`
- `src/kojakstreet/ui_qt/views/global_macro_view.py`
- `src/kojakstreet/ui_qt/views/macro_view.py`
- `src/kojakstreet/ui_qt/views/markets_view.py`
- `src/kojakstreet/ui_qt/views/news_view.py`
- `src/kojakstreet/ui_qt/views/supply_chain_view.py`
- `src/kojakstreet/ui_qt/widgets/qt_chart.py`
- `src/kojakstreet/ui_qt/widgets/stock_detail_dialog.py`
- `src/kojakstreet/ui_qt/widgets/top_bar.py`
- `src/kojakstreet/visible_state.py`

New verification/report tools: `precompute_dependency_audit.py`, `zero_flicker_benchmark.py`, `zero_flicker_verify.py`, `precompute_audit_report.py`; tests: `test_zero_flicker_ui.py`, `test_player_day_publication.py`. The existing `test_visible_scope_process.py` assertion now checks exact current quote values by typed identity rather than requiring immediate ranked-list replacement. No economic tolerance changed. The new action test restores the shared legacy module and RNG after execution to keep later tests isolated.

## Measurements (items 20–27)

All triples are **median / p95 / max**. Milliseconds except payload bytes. Native Windows samples use the established 1920×1080 driver. All-view samples are offscreen, three ticks per view; six-detail-day tails and one-off special days are descriptive, not reliable tail estimates. Latency runs are serial and exclude unrelated test/determinism workloads. Every measured day includes core, persistence, response, current visible patch and readiness/paint at T4; no post-boundary work is relabeled as preparation.

| Scenario (samples) | Boundary→visible correct | Visible patch | Per-day longest heartbeat gap | Response bytes |
|---|---|---|---|---|
| native-mature (37) | 394.49 / 481.02 / 525.65 | 51.54 / 73.52 / 76.33 | 68.09 / 98.42 / 121.88 | 523,019.00 / 524,276.00 / 524,495.00 |
| native-young (19) | 365.37 / 448.42 / 519.13 | 48.74 / 71.32 / 80.92 | 67.52 / 88.57 / 104.50 | 524,194.00 / 524,799.70 / 525,355.00 |
| year (2) | 431.43 / 446.76 / 448.47 | 46.66 / 49.24 / 49.52 | 59.47 / 61.78 / 62.04 | 524,102.00 / 524,548.40 / 524,598.00 |
| all-young (27) | 222.27 / 333.82 / 349.55 | 12.19 / 42.72 / 47.81 | 22.98 / 48.52 / 55.08 | 148,161.00 / 1,413,644.50 / 1,417,741.00 |
| all-mature (27) | 245.42 / 386.76 / 439.41 | 13.46 / 46.16 / 57.19 | 24.09 / 48.01 / 58.39 | 149,219.00 / 1,574,282.70 / 1,579,447.00 |
| company-chart (6) | 330.60 / 381.51 / 393.78 | 51.58 / 78.76 / 86.08 | 57.33 / 80.54 / 87.22 | 523,727.00 / 524,506.50 / 524,610.00 |
| company-overview (6) | 368.56 / 429.32 / 444.55 | 57.45 / 87.95 / 96.95 | 66.35 / 93.03 / 101.14 | 525,190.50 / 526,074.50 / 526,208.00 |
| company-supply (6) | 358.30 / 456.22 / 459.25 | 57.24 / 77.07 / 78.40 | 68.38 / 93.17 / 93.42 | 570,828.50 / 571,697.75 / 571,830.00 |

Same prior mature native normal benchmark: **445.48 / 533.75 / 607.28**. New mature normal median: **394.49 ms**. Measurements vary with allocator/OS state; an earlier exploratory run is archived and is not mixed into the final-source samples.

The phase spans below overlap (for example, core-finish-to-receipt includes persistence and response work), and their medians are not additive. Boundary-to-visible latency is measured directly from T0 to T4.

| Mature ordinary phase | Median / p95 / max |
|---|---|
| Economic core, after requested boundary | 173.23 / 230.02 / 233.49 |
| Persistence record | 16.57 / 21.33 / 23.98 |
| Response preparation, includes projection/encode | 29.94 / 42.06 / 45.99 |
| Core finish to parent receipt | 87.04 / 115.23 / 127.34 |
| Visible UI patch | 51.54 / 73.52 / 76.33 |
| Chart paint spans | 15.70 / 22.98 / 27.35 |

| Special day | Boundary→visible correct | Per-day longest heartbeat gap |
|---|---|---|
| Report (15th) (1) | 507.12 / 507.12 / 507.12 | 46.48 / 46.48 / 46.48 |
| Month end (1) | 369.18 / 369.18 / 369.18 | 61.37 / 61.37 / 61.37 |
| Durable flush (1) | 3,442.10 / 3,442.10 / 3,442.10 | 68.01 / 68.01 / 68.01 |
| Year boundary (2) | 431.43 / 446.76 / 448.47 | 59.47 / 61.78 / 62.04 |

All nine views are exercised by both young and mature runs; actual company chart, fundamentals and supply tabs have separate native runs. Every final run asserts current tape quotes at T4, same visible identities/cell origins on ordinary publication, no hidden-chart daily draws, correct thread/phase ordering, successful completion and worker exit. The chart driver selects Stock by asset type, avoiding a same-symbol index match. These are measured correctness assertions, not screenshot-only impressions.

The final native drivers also measure initial navigation into each view, including scope retrieval, construction/update and processing pending Qt events. These are one sample per view/world, measured outside an in-flight day; they are separate from boundary latency and are not preparation timings.

| Initial navigation | Young (ms) | Mature (ms) |
|---|---|---|
| markets | 113.96 | 112.45 |
| supply_chain | 221.02 | 177.55 |
| forex | 1011.71 | 1100.48 |
| bondmarket | 252.05 | 261.39 |
| portfolio | 176.80 | 152.23 |
| macro | 407.35 | 331.92 |
| trade_map | 106.17 | 97.54 |
| global_macro | 265.76 | 241.49 |
| news | 613.91 | 943.49 |

The all-view runs measure repeated switches before their requested boundaries: young **66.30 / 172.65 / 248.89 ms**, mature **74.16 / 186.58 / 191.11 ms** (median / p95 / max). Navigation requested during an in-flight day retains the deferred behavior described above; these measurements do not claim immediate completion in that interval.

Player actions are assessed with the dependency branches and a 20-day exact sequential/action/SaveLoad/pause regression. There is no precomputed path against which to benchmark trading invalidation; preparation/commit/recompute and speculative trade latency entries are not applicable. The branch experiment's elapsed times include checkpoint restoration and signatures and are not presented as trade latency. No new standalone trade/pause latency benchmark was run; their behavioral correctness is covered by the action and UI regressions.

## Correctness and limits (items 28–33)

Full suite: **352 tests passed**, errors/failures zero; XML duration **864.56 s**. Focused checks cover card/label identity, unchanged headers/dropdowns, sorted persistent selection, scroll, fresh departing ticker quotes, same-symbol ticker isolation, visible sequence/origin continuity, bounded layout cache, reused chart items, and deferred busy-day pause/detail requests. The player-action regression executes purchases/sales, LONG/SHORT, closing, FX and an option immediately before requested boundaries, repeated pause/read/action/resume, save/load and replay; final full checkpoint and daily economic/RNG signatures match traditional sequential stepping exactly.

365-day worker-scope comparison: **{"checkpoints": true, "database": true, "days": true, "final_checkpoint": true}**. All daily world/RNG signatures, report-visible fields, histories in checkpoints at days 15/31/181/365, final checkpoint and final economic database contents match the prior exact sequential reference. The comparator excludes only nondeterministic phase durations and session history identity, as before; no economic tolerances were widened. This is a regression of the retained sequential path, **not a prepared-vs-sequential claim**. There is no prepared path to test or leak future data. Save/Load and nine-view real process checks also run in the full suite.

**Final verdict: ordinary transitions have steadier UI structure, but are not effectively immediate.** The economic core still starts at the requested boundary and remains a substantial component; publication/IPC/patch/paint add further work. Results remain above the ~100 ms target, and durable flushes take seconds. Cold scoped reads, deep-history requests, on-completion deferred navigation, and genuine new/schema-changing rows can still produce stalls or structural updates. The audit rejected speculative precomputation under the current constraints rather than hiding those costs or changing economics/RNG.
