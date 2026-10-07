# Retail-investor coupling audit — 6 October 2026

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


The user explicitly approved the small-investor product rule. This inventory was completed before changing production code. Source evidence is preserved in `.cache/retail-decoupling/baseline`; existing workspace changes belong to the preceding passes and are retained.

Categories: **A** player accounting; **B** accidental feedback into the world; **C** ownership-dependent consumption of world randomness; **D** display/publication; **E** a design distinction requiring an explicit treatment.

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

The complete core reference search found no ordinary player-input price/production/macro consumer beyond the positioning contribution, crypto ownership retention, conditional random draws and game-over gate above. Fund `underlyings`, issuer finances, macro credit and NPC bond liquidity are world state, not the player's portfolio.

The supported boundary is world evolution → accounting events/marks → current player accounting → persistence/publication. Phase order and marks matter: dividends precede company retirement; crypto fees precede shutdown; credit uses pre-policy rates; option/future settlement precedes contract rolls. A naive move of all accounting to the end without those marks would change payouts and is rejected.

No-player world formulas and the original world random sequence must match the preserved reference. Intentional changes are removal of retail market influence, ownership protection, ownership-dependent world draws and the game-over world gate. A changed player RNG sequence is explicit and replayable, not described as an unchanged historical stochastic payout sample.

This pre-edit audit is now closed by [the implementation and measurement report](retail-investor-decoupling-and-precompute-2026-10-06.md). The supported retail corrections were implemented, all 436 tests passed, and the 365-day no-player reference is exactly equivalent. Full preparation is economically possible after the correction, but both standard and optimized isolated-world copies were measured. The optimized real-cadence experiment misses readiness on 12 of 20 consecutive transitions and worsens overall latency. Full speculation is therefore disabled under the cost stop condition; partial phase preparation provides no simple material net gain. The verified synchronous world/accounting split remains in production.
