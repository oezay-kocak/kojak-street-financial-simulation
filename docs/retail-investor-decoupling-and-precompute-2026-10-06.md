# Retail-investor decoupling and safe-precompute decision — 6 October 2026

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


**Implemented:** the explicitly approved small-investor boundary and preservation of player accounting. **Not enabled:** full or partial next-day speculation. An optimized isolated-world prototype produces exact world/checkpoint/RNG results, but fails the sustained three-second cadence: 8 prepared hits are followed by 12 consecutive not-ready fallbacks. Including misses, ordinary boundary latency rises to approximately 674 ms median versus 385 ms in the serial cadence control. The cost gate rejects enabling speculation; the verified retail correction remains.

The user approved the product rule in the chat; the attached document supplied the audit scope and conditional implementation criteria. Existing workspace changes from earlier passes were retained. This report closes all 28 requested points.

## 1. Complete coupling matrix

The pre-change inventory was completed and saved before production edits. Categories A/B/C/D/E and source evidence are in [the original audit](retail-investor-coupling-audit-2026-10-06.md).

| Player state/action | World consumer / code path | Effect | Category | Intended under retail rule? | Treatment |
|---|---|---|---|---|---|
| Stock spot BUY/SELL | `trading.execute_spot_trade`, `accounting.get_net_worth` | Cash/inventory/realized PnL; next-day wealth and margin gate | A/B gate | Accounting yes; gating world completion no | Preserve trade execution; move wealth/game-over decision to player completion |
| Stock/crypto/commodity LONG/SHORT size, adding and closing | `market_calculations._perpetual_position_interest` → `_update_open_interest` → squeeze/chance/volatility | Adds retail notional to aggregate market positioning every day | B | No | Remove retail contribution, retain every NPC/base/decay/crowding/squeeze formula |
| Funds spot trades | `trading`, `accounting`, `portfolio` | Holdings and marked wealth; NPC fund portfolios are separate `fund.underlyings` | A | Yes | Preserve; never remove NPC fund-underlying interactions |
| Commodity spot trades | Same spot/accounting paths | Inventory and currency conversion, no direct aggregate demand | A | Yes | Preserve |
| Crypto spot holdings | `monthly_assets.update_monthly_crypto` | Payout of fee × quantity × uniform(0.01, 0.03), with a conditional world draw | A/C | Payout yes; world draw coupling no | Preserve payout distribution/formula with an explicitly seeded, checkpointed player stream |
| Crypto holdings and perpetuals | `cryptos._trim_excess_universe` | Ownership protects an excess chain from removal, affecting future universe/funds and RNG draw count | B/E | No world protection for a small investor | Choose trimming by unchanged world criteria; apply delisting consequences to player separately |
| Weak crypto chain ownership | `shutdown_and_replace_crypto_chains` | World independently shuts chain down; player spot/perpetual positions are written off | A | Yes, world→player | Preserve write-offs and world shutdown/news; record/apply lifecycle effects at player commit |
| Company ownership at bankruptcy | `companies.remove_bankrupt_companies` | World removes issuer, fund references, bond marks and CDS triggers; deletes owned stock/perpetuals and marks owned bonds defaulted | A | Yes, world→player | Preserve NPC/world changes and player losses/recovery; separate the latter from preparation |
| Ticker migration during bootstrap | `companies._rewrite_ticker_references` | Rewrites portfolio references alongside a world rename | A/D | Yes | Keep bootstrap migration; world generation is not an ordinary displayed-day action |
| Stock ownership on report | `company_lifecycle.update_monthly_companies` → `pay_dividend` | Pays quantity × pre-market report price × yield/12, with growth/FCF eligibility | A | Yes | Keep amount, eligibility, currency and phase marks in an ownership-independent accounting event |
| Dated futures | `portfolio_risk.update_future_settlements` | Expiry payout/PnL before derivative roll | A | Yes | Preserve expiry date, pre-roll price/currency and realized history |
| Options and CDS | `update_spot_derivative_settlements` | Expiry/default payout at current world marks, then removal | A | Yes | Preserve before-roll contract availability, underlying marks and world default triggers |
| Leveraged liquidation | `update_perpetual_liquidations` | Removes player margin positions after world prices move | A | Yes | Preserve direction/leverage thresholds, zero residual payout and player notification |
| Owned government bonds | `bond_calculations.update_laufende_anleihen` | Coupon clock and principal repayment in local currency | A | Yes | Preserve clocks, coupon accrual and histories |
| Owned corporate bonds: issuer bankruptcy | Same engine, retired issuer/default flag | World default causes recovery according to `RECOVERY_RATE` | A | Yes | Preserve actual issuer/default event and recovery |
| Owned corporate bonds: residual maturity risk | Same engine, conditional `random.random()` | Rating/horizon-based stochastic principal loss, shifts later world draws; no corresponding NPC issuer default is created | C/E | Ownership-dependent world draw no | Treat as an ownership-independent keyed bond credit event, using issuer/bond/date/seed. Keep probability and contractual payout/loss; do not invent a new issuer-wide bankruptcy or alter NPC pricing |
| Loans/credit | `accounting.update_credit_interest` | Deducts daily debt × (policy rate+0.06)/365 | A | Yes | Preserve pre-policy-decision rates at the original accounting phase |
| FX exchange / other cash mutation | `trading.exchange_currency`, `accounting` | Current-day execution marks and player wealth | A | Yes | Preserve current authoritative marks; exclude balances from world price formation |
| Depleted net worth | `DailySimulation.step_day` early return | Suppresses policy decision, history/date completion and future world schedule | B/E | Player game-over yes; suppressed world event no | Complete the independent world day; keep margin/game-over and pause as player/publication behavior |
| Settlement/coupon/liquidation news | `DailySimulation.add_news`, datastore/adapters | Player messages share/truncate the world news ring | A/B presentation | Player notices yes; displacement of world news no | Keep independent player notices; merge only for visible/persisted publication |
| Pause/play, speed, manual stepping | Qt scheduler and runtime running/paused flags | Determines when an authoritative completed day can publish | D | Yes | Keep scheduling separate; preparation must not publish while paused |
| View/Back/tab/filter/sort/chart/watchlist | Visible projection and history reads | Reads current state; no world step | D | Yes | Preserve on-demand reads and UI continuity; no future scope/history exposure |
| Display currency | Formatting; missing option asset fallback | Primarily presentation; option fallback affects player settlement currency | A/D/E | Presentation yes; contract fallback must remain correct | Retain existing valid-contract behavior and evaluate pre-roll marks explicitly |
| Save | Runtime checkpoint/session | Persists current authoritative world, player and RNG | D | Yes | Serialize published state; speculative world excluded |
| Load/world replacement | Checkpoint/bootstrap | Replaces world/player/date/RNG/history | D | Yes | Discard speculation and restart from loaded authoritative state |
| Runtime reseeding | `IntegratedRuntime.set_seed` | Resets world sequence; no exposed gameplay settings button | D | Explicit world mutation | Discard speculation; initialize player stream deterministically for the new seed |
| Bond BUY/SELL, loan buttons, standing orders, separate short sales, reserved Revalue/Export | Qt/worker action inventory | Bond screen is read-only; other listed controls are absent; SHORT uses a leveraged ticket | D | No nonexistent routes | Test persisted owned bonds/debt through supported engine fixtures; do not claim absent buttons were exercised |

## 2. Intentional and accidental coupling

World → player prices, dividends, coupons, expiry, default, credit charges, PnL and margin remain intentional. Retail size → global positioning, ownership → chain survival, conditional player world-RNG draws, depleted wealth → incomplete world day, and player messages → truncation of NPC news were accidental under the approved rule. NPC fund portfolios, issuer debt, production inventories, macro credit and bond-market liquidity remain world inputs.

## 3. Retail boundary

Ordinary player trades change portfolio/cash/realized results at current authoritative quotes. They do not enter NPC price, production, macro or aggregate-positioning formulas. A completed day uses world evolution, an ordered accounting-event/mark frame, current player accounting, history/date completion, then the existing persistence and compact visible publication. Scheduling/pause remain controls; no speculative world is published.

## 4. Economic files and semantic reasons

`market_calculations.py`: remove only retail notional from global positioning. `cryptos.py`: remove ownership protection and apply delisting losses. `monthly_assets.py`: separate fee payouts and player randomness. `company_lifecycle.py` / `companies.py`: preserve report dividends and issuer losses as ordered player events. `simulation.py`: independent world completion and explicit accounting commit. New `player_accounting.py`: recorded marks, deterministic player stream, keyed bond credit event, lifecycle losses and visible news merge. `bond_calculations.py`: preserve credit probability/payouts with the keyed event. `checkpoints.py`: serialize player RNG/notices with version 7 and validate before mutation. `save_migrations.py`: share that version with the real save loader. `randomness.py`: explicit reseed resets the player stream. `legacy_runtime.py`: a completed margin call remains inactive/paused, including subsequent requested steps. `legacy_state.py`, `visible_state.py`, `data_store.py`: publish/persist player notices without mutating world news. The exact 15-file list is in `.cache/retail-decoupling/final-changed-source.json`.

## 5. Open interest and squeezes

Removed `_perpetual_position_interest` and its two additions. NPC/base positioning, decay, momentum/crowding, caps, imbalance, squeeze probabilities and volatility formulas are preserved. Direct tests compare huge LONG and SHORT retail positions against no positions for Stock, Commodity and Crypto; entire results and asset state are equal. Existing NPC squeeze tests remain.

## 6. Crypto randomness

The same fee/1,000,000 × quantity × uniform(0.01, 0.03) formula now draws from a separately seeded `Random` stream. Its lazy state is checkpointed and replayed. The seed is SHA-256 of the explicit versioned domain and simulation seed, with deterministic seed 0 fallback for older saves without seed metadata. Historical player payout samples can change; the distribution, formula and accounting order remain. World randomness is untouched by holdings.

## 7. Corporate bond randomness

Residual maturity risk uses a deterministic versioned event keyed by simulation seed, issuer, bond symbol, currency, date and original term. Nominal size, lot count and ownership are excluded. It does not advance the world stream or invent an NPC issuer bankruptcy. Rating/horizon default probability, coupon accrual, full principal loss on the existing residual-risk outcome, successful repayment and actual issuer-default recovery are preserved. Same-issue lots see the same event. This intentionally changes old ownership-conditioned stochastic samples.

## 8. Portfolio/accounting separation

Report events preserve price/yield/currency before market movement and preserve payout-before-retirement order. Credit captures pre-policy rates. Settlement uses copied pre-roll derivative prices/currencies, current underlying prices, copied player contract terms and the full current default/issuer state. A facade restores full macro state after credit calculation so CDS default checks do not see a rates-only projection. Current portfolio dictionaries remain authoritative; world accounting events never replace them.

## 9. World/RNG comparisons

64 exact comparisons cover 16 actions × ordinary/report/month/year dates, with two days of continuation except the game-over branch, whose completed first world day is compared before play stops. Every captured world field/history and Python/NumPy RNG is compared. Portfolio results must differ. No tolerance was widened.

## 10. Player correctness

Exact tests cover pre-policy debt interest, pre-roll LONG/SHORT expiry including returned margin and realized PnL, option currency/strike/payout, sovereign CDS default after credit, dividend/fee-before-delisting, issuer bond recovery, government/corporate coupon and maturity success/loss, liquidation, margin/game-over, player news retention and actual crypto-report save replay. Existing trading, financial-product, monthly/lifecycle and bond tests also pass.

## 11. No-player equivalence

Final source is exactly equivalent to the preserved pre-edit source over 365 days: daily field signatures and world RNG, checkpoints at days 15/31/181/365, the complete final checkpoint including numerical histories, and economic database content. Only the deliberately changed outer format marker (save version 6 → 7), existing nondeterministic phase durations and per-run history identity are excluded. Economic numbers, dates, histories, row content and random states use exact comparisons.

## 12. Intentional gameplay changes

Retail leveraged size no longer drives market squeezes; owned weak excess chains can be removed under world criteria and the player bears their loss; crypto/bond player stochastic samples follow explicit independent rules; a margin call completes the already evolving world day before stopping player progression. Player messages no longer displace NPC news. Trade execution, quantities, leverage, PnL, expiry contracts, loan/coupon clocks, repayment/default formulas and durable flush behavior remain.

## 13. Post-decoupling dependencies

No ordinary portfolio input remains in world price/production/macro evolution. World phases still form a strict shared-state and random-stream sequence. Reusing a partially prepared later phase requires its earlier world inputs and exact RNG position. Monthly reports additionally span company lifecycle, crypto lifecycle, production and macro. Logical player independence does not make individual mutable world phases independently swappable.

## 14. Full-precompute verdict

**Rejected on sustained measured net performance.** The initial standard copy takes 8.81 seconds. A second implementation shares only proven immutable scalar/tuple/history points while copying every mutable container, retaining internal graph references. This reduces isolated mature copy time to about 2.15 seconds. Six complete preparation/publication comparisons (three young, three mature) match every captured field/history and Python/NumPy random state exactly; preparation leaves the current authoritative checkpoint unchanged. With real GC enabled, mature preparation takes 2.49–2.71 seconds in that isolated gate.

The real native Qt/worker experiment uses the three-second request cadence and never waits at the boundary. A prepared result is taken only when already ready; otherwise the original world day runs. All eight hits were completed before T0 and match the source date. Nevertheless the next twelve transitions miss readiness consecutively. The discarded running copy cannot be canceled immediately and competes with the fallback/new work. Hit-only timing is therefore an invalid basis for activation. The complete experiment has a worse median/tail than its serial cadence control and ends at an identical economic/RNG signature.

This meets the document's stop condition that cloning/architecture defeats the gain. No production background scheduler, N+1 cache, detached world RNG or world-swap feature remains. Only the audited world/accounting separation is retained. The production files were restored from the verified decoupled snapshot and every recorded source hash matches the 436-test/365-day version.

## 15. Partial-phase matrix

GREEN = a simple safely preparable prefix with negligible gain. YELLOW = world-only but requires an ownership/dependency/RNG closure; it is not an independently reusable result. RED = current-player accounting or publication. All world-only phases could run inside a fully isolated world, which failed the copy-cost gate. The measured mature ordinary-day phases are:

| Phase | Median ms | Player reads? | World RNG? | Feeds later phases? | Class / partial verdict |
|---|---:|---|---|---|---|
| monthly_report | 0.0059 | No after event separation | Yes on reports | All world phases | YELLOW: report closure includes company, crypto, production, macro and lifecycle books |
| events | 0.0095 | No | Yes | Macro/production/prices | GREEN only as a prefix on non-report days; negligible gain |
| global_macro | 4.3456 | No | Yes | Production/prices/bonds | YELLOW: expectations and histories also change; only about 4 ms |
| daily_crypto_inputs | 1.9789 | No | No | Production and crypto prices | YELLOW: shared quantities and production state |
| daily_production_chain_core | 124.0695 | No | No daily draw | Asset market/report quantities | YELLOW: inventories, regional flows, company plans and histories form a large ownership closure |
| daily_production | 126.4121 | No | Indirect | Asset market | YELLOW: aggregate contains the preceding two rows; do not double count |
| bond_market | 6.3264 | No; NPC issuers only | Conditional issuance | Derivatives and future reports | YELLOW: macro/issuer/rolling bond-state dependencies |
| asset_market | 118.1943 | No; retail interest removed | Yes | Funds, indices, derivatives, accounting | YELLOW: sequential FX/commodity/stock/crypto/fund/index effects; expensive world closure |
| derivatives | 32.1198 | No | No | Rolls and player expiry | YELLOW: requires completed underlying prices and bond/macro marks |
| derivative_rolls | 1.1667 | No | No | Next-day contracts | YELLOW: pre-roll marks must survive for player expiry; too little isolated benefit |
| credit_interest | 0.0173 | Yes | No | Player cash/margin | RED: current debt and captured pre-policy rates |
| spot_derivative_settlements | 0.0058 | Yes | No | Player cash/PnL | RED: current options/CDS and full issuer/default marks |
| future_settlements | 0.0036 | Yes | No | Player cash/PnL | RED: current margin positions and pre-roll prices |
| perpetuals | 0.0022 | Yes | No | Player liquidation/margin | RED: current positions, actual final world prices |
| bond_portfolio | 0.0070 | Yes | Keyed credit event | Player cash/coupons/PnL | RED: current owned lots and coupon clocks |


| Conditional phase | Actual samples | Median ms | RNG/dependency and partial verdict |
|---|---:|---:|---|
| monthly_macro | 1 | 3.5563 | YELLOW: World RNG, macro/expectations/history prefix; too little gain alone |
| monthly_companies | 1 | 82.7864 | YELLOW: World RNG, stock fundamentals and histories; large mutable closure |
| monthly_company_lifecycle | 1 | 8.8808 | YELLOW: World RNG, issuers/funds/bonds/retirement; follows company report |
| monthly_commodities | 1 | 0.9341 | YELLOW: World RNG and preceding macro/growth; too little gain alone |
| monthly_crypto_inputs | 1 | 2.3190 | YELLOW: Production inputs and chain state; feeds monthly production |
| monthly_production_chain_core | 1 | 134.4109 | YELLOW: Company/country/commodity/crypto quantities and inventories; large shared closure |
| monthly_production_news | 1 | 4.9412 | YELLOW: World news after production; not an independent calculation |
| monthly_crypto | 1 | 1.5787 | YELLOW: World RNG, fee marks and chain state after production; not independently reusable |
| monthly_crypto_lifecycle | 1 | 0.0952 | YELLOW: World RNG for replacements, funds/universe and loss events; follows crypto report |
| policy_decision | 1 | 0.5423 | YELLOW: policy/news/history commit follows world phases; negligible isolated gain |


Funds and indices are sequential subphases of `asset_market`; their NPC underlying references and pressure effects are preserved, not treated as the player portfolio. Report/company/crypto/monthly-production and policy phases are conditional closures, measured in the special-day runs. Persistence/projection/IPC/UI paint remain RED publication work. Tiny event/macro/roll prefixes cannot materially reduce the observed hundreds of milliseconds; no dependency graph or reconciliation system was added.

## 16. Architecture actually implemented

Retained the explicit in-process world/accounting split with an ephemeral `PlayerDay` frame. It is completed synchronously by the existing live worker before current-state publication. Immutable marks bridge original economic timing, while portfolio mutations use current holdings. No speculative ownership or future-state exposure exists in the final architecture.

## 17. Memory and copy cost

One graph `deepcopy` of checkpoint-owned world fields preserves nested NPC reference identity and isolates mutable state; player/control fields are excluded and only empty player placeholders are added for engine construction. Each sample includes facade/engine construction and index warming. Five copies per fixture, collected and measured separately from tests/UI workloads:

| World | Copies | Copy median / p95 / max ms | RSS before range MiB | RSS after range MiB |
|---|---:|---:|---:|---:|
| 1990-01-10 | 5 | 870.64 / 908.92 / 913.36 | 240.04–242.23 | 243.24–243.89 |
| end | 5 | 8,808.86 / 8,930.25 / 8,933.30 | 1343.99–1348.88 | 1364.24–1365.72 |


RSS measures resident memory, not the exclusive logical size of the second world: decoded checkpoints and the allocator's reusable arena reserve are already present before copying. The modest RSS increment must not be mistaken for complete allocation cost. The standard-copy experiment already uses about 1.35 GiB in the mature fixture. A second graph-copy experiment proves exact graph equality and no shared mutable dict/list/set/array identities; only immutable values may be shared.

| Fixture | Optimized isolated copy median / p95 / max ms (3 samples) | Full preparation with GC enabled (3 samples) | Publication | Player commit |
|---|---:|---:|---:|---:|
| 1990-01-10 | 298.21 / 303.30 / 303.86 | 492.33 / 520.08 / 523.16 | 19.24 / 20.35 / 20.47 | 0.39 / 0.42 / 0.43 |
| end | 2,146.02 / 2,176.79 / 2,180.21 | 2,560.09 / 2,694.00 / 2,708.88 | 48.95 / 49.00 / 49.00 | 0.32 / 0.46 / 0.48 |


The optimized copy-only observer sees at most 32.05 ms between pulses in a second thread; this is not the native GUI heartbeat. In the real cadence experiment, mature worker RSS starts as low as 1237.43 MiB and reaches 1388.32 MiB, versus a control maximum of 1248.22 MiB. Isolated full-checkpoint comparisons also retain encoded checkpoint graphs and are deliberately not used as an application memory estimate.

## 18. Preparation and player-commit timing

Preparation and publication timings above belong to the isolated prototype. The final program has no background preparation/publication/swap feature because it was rejected after real cadence measurement. Its world core remains in the boundary. Separate real-engine commit timings on isolated fixtures include payouts, expiry, risk, coupons, wealth/history and date completion, without persistence:

| World / portfolio | Samples | Complete player commit median / p95 / max ms |
|---|---:|---:|
| 1990-01-10 / no player | 2 | 0.33 / 0.36 / 0.36 |
| 1990-01-10 / mixed expiry | 2 | 0.45 / 0.46 / 0.46 |
| end / no player | 2 | 0.32 / 0.34 / 0.34 |
| end / mixed expiry | 2 | 0.46 / 0.49 / 0.50 |


Two samples per case are diagnostic, not a high-percentile guarantee. The mixed case has stock/crypto/fund/commodity holdings, expiring option/CDS/future, an open short, debt and a maturing government bond.

## 19. Boundary critical path

| Non-overlapping boundary segment | Median / p95 / max ms |
|---|---:|
| Request T0 → core/accounting complete T1 | 292.90 / 316.04 / 424.43 |
| T1 → parent receives T2: persistence, projection, encoding, IPC and decode | 153.73 / 169.97 / 203.86 |
| T2 → visible patch complete T3 | 88.92 / 97.56 / 106.42 |
| T3 → correct visible paint T4 | 85.47 / 100.49 / 112.44 |


The preceding table is the existing rapid-loop final-source driver. The additional native three-second control and experimental run expose the actual speculative tradeoff:

| Non-overlapping segment at real cadence | Sequential control median / p95 / max ms | Experimental preparation, including misses |
|---|---:|---:|
| T0 → T1: boundary world/player completion | 175.21 / 222.86 / 250.48 | 341.91 / 544.12 / 650.34 |
| T1 → T2: persistence/projection/encoding/IPC/decode | 81.64 / 118.85 / 123.92 | 182.47 / 260.58 / 438.50 |
| T2 → T3: visible patch | 49.08 / 67.53 / 67.97 | 69.51 / 85.91 / 86.29 |
| T3 → T4: correct paint | 80.74 / 88.83 / 91.08 | 80.76 / 88.31 / 92.28 |


Segments are non-overlapping; their individual medians need not add to the median total. Sequential-core measurements include synchronous world evolution and player commit. On experimental hits, the boundary core measures world publication and player commit; the earlier background preparation is reported separately and is never counted as boundary work. On misses it measures the normal world day. Projection/encoding/IPC continue using the existing visible-only protocol.

## 20. Boundary → visible-correct before/after

| Comparable sample | Ordinary days | Core median / p95 / max ms | T0 → T4 median / p95 / max ms |
|---|---:|---:|---:|
| Archived preceding pass | 37 | 173.23 / 230.02 / 233.49 | 394.49 / 481.02 / 525.65 |
| Frozen pre-edit source, measured in this pass | 37 | 276.95 / 302.68 / 444.77 | 584.98 / 640.18 / 816.05 |
| First current-source run | 37 | 345.38 / 396.19 / 492.59 | 714.06 / 793.15 / 930.33 |
| Current-source repeat | 37 | 291.06 / 313.94 / 412.58 | 618.25 / 661.91 / 799.84 |
| Current young world | 19 | 305.39 / 325.38 / 330.05 | 653.25 / 858.09 / 981.16 |

These native runs are serial and use the same preserved fixture and real request/worker/paint driver. Timing varied materially between runs; the archived ~394 ms should not be presented as a contemporaneous control. The rapid-loop decoupling measurements do not show a speed improvement. Cadence affects the measurement conditions; do not infer a source-level optimization from the faster three-second control.

| Real 3-second cadence, mature world | All ordinary samples | Boundary → correct visible paint median / p95 / max ms |
|---|---:|---:|
| Sequential control | 19 | 384.77 / 481.62 / 516.53 |
| Optimized preparation, including misses | 19 | 674.40 / 949.45 / 977.46 |
| Prepared hits only (diagnostic subset) | 8 | 260.65 / 312.43 / 324.79 |
| Not-ready fallbacks only (diagnostic subset) | 11 | 741.24 / 961.90 / 977.46 |


The experiment and control each cover 20 consecutive transitions, including one report day. Ordinary statistics exclude the report and include every readiness miss. Even its hit-only subset remains above 100 ms. The final program uses the sequential path; no claimed precomputation gain exists.

## 21. Heartbeat

Ordinary mature maximum heartbeat gap: pre-edit control 124.10 ms; final repeat 135.59 ms. All visible updates execute on the Qt main thread; T0 ≤ T1 ≤ T2 ≤ T3 ≤ T4 and worker exit are asserted. Long worker flushes are separate from GUI-thread stalls. Native navigation maximum observed gap: 892.82 ms.

At the measured three-second cadence, ordinary native GUI heartbeat maximum is 87.99 ms for the sequential control and 109.64 ms for the experiment including misses. Background phase timers are filtered by worker-thread identity so they cannot be mistaken for boundary work.

## 22. Special days and durable flush

| Day type | Samples | T0 → T4 median / p95 / max ms |
|---|---:|---:|
| Report day (15th, mature) | 1 | 797.74 / 797.74 / 797.74 |
| Month-end (mature) | 1 | 623.53 / 623.53 / 623.53 |
| Year-end | 1 | 642.53 / 642.53 / 642.53 |
| Durable flush (mature) | 1 | 5,191.05 / 5,191.05 / 5,191.05 |


Ordinary statistics exclude reports, month ends and flushes. Small special-day sample counts are stated rather than marketed as stable percentiles. DuckDB's existing durable batching/flush remains unchanged, including its separate seconds-scale cost.

## 23. Tests

Final complete suite: **436 tests, zero failures/errors**, 1669.33 seconds. Targeted runs found and corrected an initial Gold-Dinar test assumption and the real save-version mismatch before full-suite verification. Exact retail comparisons, accounting tests, existing NPC squeeze tests, checkpoint/migration tests, actual process tests and UI continuity tests are included. New files pass Ruff; old tolerances were not widened.

## 24. 365-day evidence

`.cache/retail-decoupling/no-player-before.json` is the immutable source-reference result. `no-player-final.json` is the final source result. `no-player-final-comparison.json` has all four checks true: daily state/RNG, checkpoints at days 15/31/181/365, complete final checkpoint, database. Earlier `no-player-after.json` also passed independently. Reference source, source hashes and the per-pass diff are retained for review.

## 25. Save/Load and pause

Version 7 is shared by checkpoint writer and loader; versions 4/5/6 remain supported. Player RNG/notices survive save/load, and invalid random state is rejected before live mutation. Actual disk save → report continuation → load → replay returns identical world/RNG and player signatures. Paused simulation does not advance on direct world stepping; explicitly requested manual steps preserve existing behavior. In-flight sequential requests finish as before. Margin-call completion leaves the runtime inactive/paused and further steps do not advance it. No speculative state is serialized.

## 26. Nine views and continuity

All nine views have three transition samples in both young and mature worlds. Native company chart, overview and supply each have six transition samples with real Stock selection. Ticker identity/offset/geometry/current quote checks, hidden-chart exclusion, correct visible paint, selection/tab/model/card/chart reuse regressions and on-demand synchronization remain verified. Native navigation exercises all asset categories, country/product/FX/bond/calendar details, portfolio and Save/Load: 94 samples over two repetitions.

## 27. Remaining bottlenecks

Daily production and price formation dominate synchronous core computation; visible-state persistence/projection/serialization/IPC and Qt patch/paint remain on the publication path. Optimized whole-world graph copying still misses readiness in a sustained mature run and then adds contention to normal progression. Flush is a separate durability cost. A smaller world/history ownership design would be a distinct architecture project; a complex rollback, invalidation or reconciliation mechanism was not added to this pass.

## 28. Gameplay-fluidity verdict

**The approved retail semantics are implemented and exactly regression-tested.** Player accounting and current-day UI publication are preserved. **Precomputation is not justified by the measured implementation cost, and the sub-100-ms boundary goal was not achieved.** The audit-supported correction remains useful independently: ordinary retail positions no longer steer global prices or global randomness, while the world still determines portfolio outcomes.
