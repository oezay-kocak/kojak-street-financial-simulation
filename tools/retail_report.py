"""Close out the retail audit only from completed, checked evidence."""

from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree

from visible_sync_report import gaps, normal, run, stats

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / ".cache/retail-decoupling"
UI = ROOT / ".cache/visible-ui-sync"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    comparison = read(EVIDENCE / "no-player-final-comparison.json")
    assert all(comparison.values()), comparison
    suite = ElementTree.parse(EVIDENCE / "full-final.xml").getroot().find("testsuite")
    assert int(suite.attrib["failures"]) == int(suite.attrib["errors"]) == 0
    native = run(UI, "retail-final-native-mature-repeat")
    before = run(UI, "retail-reference-native-mature")
    early = run(UI, "retail-final-native-mature")
    archived = run(UI, "zero-final-native-mature")
    labels = ("native-young", "year", "all-young", "all-mature", "company-chart", "company-overview", "company-supply")
    results = {label: run(UI, "retail-final-" + label) for label in labels}
    for result in [native, early, *results.values()]:
        assert result["ticker_continuity_checks"]
        assert all(row["hidden_chart_calls"] == 0 for row in result["rows"])
    for label in ("all-young", "all-mature"):
        counts = Counter(row["view"] for row in results[label]["rows"])
        assert len(counts) == 9 and set(counts.values()) == {3}
    navigation = read(UI / "retail-final-navigation.json")
    assert navigation["save_load_exact"] and navigation["repeats"] == 2
    for row in navigation["rows"]:
        if row["label"].endswith(" select"):
            assert row["scope"]["selection"]["kind"] == row["label"].split()[0], row
    copies = read(EVIDENCE / "clone-probe.json")
    optimized = read(EVIDENCE / "alternate-copy.json")
    prepared = read(EVIDENCE / "prepared-gate.json")
    experiment = run(UI, "retail-prepared-cadence-mature")
    cadence_control = run(UI, "retail-prepared-cadence-control")
    assert experiment["signature"] == cadence_control["signature"]
    assert all(r["exact_checkpoint_and_rng"] and r["authoritative_unchanged_until_publish"] for r in prepared)
    hits = [r for r in experiment["rows"] if r["precomputation"].get("hit")]
    misses = [r for r in experiment["rows"] if not r["precomputation"].get("hit")]
    assert len(hits) == 8 and len(misses) == 12
    assert all(r["precomputation"]["ready_perf"] <= r["t0"] for r in hits)
    assert all(r["precomputation"]["source_date"] == r["date"] for r in hits)
    assert all(r["precomputation"]["reason"] == "not_ready" for r in misses)
    assert not (ROOT / "src/kojakstreet/core/precomputation.py").exists()
    accounting = read(EVIDENCE / "accounting-probe.json")
    rows = normal(native["rows"])
    phases = {}
    for row in rows:
        for phase in row["worker"]["phases"]:
            phases.setdefault(phase["phase"], []).append(phase["duration_ms"])
    medians = {name: statistics.median(values) for name, values in phases.items()}
    source = read(EVIDENCE / "final-source-hashes.json")["files"]
    assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == value for path, value in source.items())
    changed = []
    for path in (ROOT / "src").rglob("*.py"):
        relative = path.relative_to(ROOT)
        old = EVIDENCE / "baseline" / relative
        if not old.exists() or old.read_text(encoding="utf-8") != path.read_text(encoding="utf-8"):
            changed.append(str(relative).replace("\\", "/"))
    (EVIDENCE / "final-changed-source.json").write_text(json.dumps(changed, indent=2), encoding="utf-8")
    audit = (ROOT / "docs/retail-investor-coupling-audit-2026-10-06.md").read_text(encoding="utf-8")
    matrix = audit[audit.index("| Player state/action"):audit.index("The complete core reference search")].strip()

    def total(result):
        return stats([row["total_ms"] for row in normal(result["rows"])])

    def core(result):
        return stats([row["worker"]["spans"]["simulation.core"] for row in normal(result["rows"])])

    phase_table = "| Phase | Median ms | Player reads? | World RNG? | Feeds later phases? | Class / partial verdict |\n|---|---:|---|---|---|---|\n"
    descriptions = {
        "monthly_report": ("No after event separation", "Yes on reports", "All world phases", "YELLOW: report closure includes company, crypto, production, macro and lifecycle books"),
        "events": ("No", "Yes", "Macro/production/prices", "GREEN only as a prefix on non-report days; negligible gain"),
        "global_macro": ("No", "Yes", "Production/prices/bonds", "YELLOW: expectations and histories also change; only about 4 ms"),
        "daily_crypto_inputs": ("No", "No", "Production and crypto prices", "YELLOW: shared quantities and production state"),
        "daily_production_chain_core": ("No", "No daily draw", "Asset market/report quantities", "YELLOW: inventories, regional flows, company plans and histories form a large ownership closure"),
        "daily_production": ("No", "Indirect", "Asset market", "YELLOW: aggregate contains the preceding two rows; do not double count"),
        "bond_market": ("No; NPC issuers only", "Conditional issuance", "Derivatives and future reports", "YELLOW: macro/issuer/rolling bond-state dependencies"),
        "asset_market": ("No; retail interest removed", "Yes", "Funds, indices, derivatives, accounting", "YELLOW: sequential FX/commodity/stock/crypto/fund/index effects; expensive world closure"),
        "derivatives": ("No", "No", "Rolls and player expiry", "YELLOW: requires completed underlying prices and bond/macro marks"),
        "derivative_rolls": ("No", "No", "Next-day contracts", "YELLOW: pre-roll marks must survive for player expiry; too little isolated benefit"),
        "credit_interest": ("Yes", "No", "Player cash/margin", "RED: current debt and captured pre-policy rates"),
        "spot_derivative_settlements": ("Yes", "No", "Player cash/PnL", "RED: current options/CDS and full issuer/default marks"),
        "future_settlements": ("Yes", "No", "Player cash/PnL", "RED: current margin positions and pre-roll prices"),
        "perpetuals": ("Yes", "No", "Player liquidation/margin", "RED: current positions, actual final world prices"),
        "bond_portfolio": ("Yes", "Keyed credit event", "Player cash/coupons/PnL", "RED: current owned lots and coupon clocks"),
    }
    for name, values in descriptions.items():
        phase_table += f"| {name} | {medians[name]:.4f} | " + " | ".join(values) + " |\n"
    conditional_table = "| Conditional phase | Actual samples | Median ms | RNG/dependency and partial verdict |\n|---|---:|---:|---|\n"
    conditions = {
        "monthly_macro": "World RNG, macro/expectations/history prefix; too little gain alone",
        "monthly_companies": "World RNG, stock fundamentals and histories; large mutable closure",
        "monthly_company_lifecycle": "World RNG, issuers/funds/bonds/retirement; follows company report",
        "monthly_commodities": "World RNG and preceding macro/growth; too little gain alone",
        "monthly_crypto_inputs": "Production inputs and chain state; feeds monthly production",
        "monthly_production_chain_core": "Company/country/commodity/crypto quantities and inventories; large shared closure",
        "monthly_production_news": "World news after production; not an independent calculation",
        "monthly_crypto": "World RNG, fee marks and chain state after production; not independently reusable",
        "monthly_crypto_lifecycle": "World RNG for replacements, funds/universe and loss events; follows crypto report",
    }
    for name, why in conditions.items():
        values = [p["duration_ms"] for r in native["rows"] for p in r["worker"]["phases"] if p["phase"] == name]
        assert values, name
        conditional_table += f"| {name} | {len(values)} | {statistics.median(values):.4f} | YELLOW: {why} |\n"
    values = [r["worker"]["spans"]["simulation.policy_decision"] for r in native["rows"] if "simulation.policy_decision" in r["worker"]["spans"]]
    assert values
    conditional_table += f"| policy_decision | {len(values)} | {statistics.median(values):.4f} | YELLOW: policy/news/history commit follows world phases; negligible isolated gain |\n"

    critical = "| Non-overlapping boundary segment | Median / p95 / max ms |\n|---|---:|\n"
    for title, values in (
        ("Request T0 → core/accounting complete T1", [(r["worker"]["t1"]-r["t0"])*1000 for r in rows]),
        ("T1 → parent receives T2: persistence, projection, encoding, IPC and decode", [(r["t2"]-r["worker"]["t1"])*1000 for r in rows]),
        ("T2 → visible patch complete T3", [(r["t3"]-r["t2"])*1000 for r in rows]),
        ("T3 → correct visible paint T4", [(r["t4"]-r["t3"])*1000 for r in rows]),
    ):
        critical += f"| {title} | {stats(values)} |\n"
    special = "| Day type | Samples | T0 → T4 median / p95 / max ms |\n|---|---:|---:|\n"
    selected = {
        "Report day (15th, mature)": [r for r in native["rows"] if date.fromisoformat(r["date"]).day == 15],
        "Month-end (mature)": [r for r in native["rows"] if (date.fromisoformat(r["date"])+timedelta(days=1)).month != date.fromisoformat(r["date"]).month],
        "Year-end": [r for r in results["year"]["rows"] if date.fromisoformat(r["date"]).month == 12],
        "Durable flush (mature)": [r for r in native["rows"] if r["worker"]["spans"].get("store.flush", 0)],
    }
    for title, values in selected.items():
        assert values, title
        special += f"| {title} | {len(values)} | {stats([r['total_ms'] for r in values])} |\n"
    copy_table = "| World | Copies | Copy median / p95 / max ms | RSS before range MiB | RSS after range MiB |\n|---|---:|---:|---:|---:|\n"
    for label, values in copies.items():
        rss_before = [v["rss_before"]/1048576 for v in values]
        rss_after = [v["rss_after"]/1048576 for v in values]
        copy_table += f"| {label} | {len(values)} | {stats([v['clone_ms'] for v in values])} | {min(rss_before):.2f}–{max(rss_before):.2f} | {min(rss_after):.2f}–{max(rss_after):.2f} |\n"
    optimized_table = "| Fixture | Optimized isolated copy median / p95 / max ms (3 samples) | Full preparation with GC enabled (3 samples) | Publication | Player commit |\n|---|---:|---:|---:|---:|\n"
    for label, values in optimized.items():
        actual = [r for r in prepared if r["checkpoint"] == label]
        assert len(actual) == 3
        optimized_table += f"| {label} | {stats([r['copy_ms'] for r in values])} | {stats([r['preparation_ms'] for r in actual])} | {stats([r['publication_ms'] for r in actual])} | {stats([r['accounting_ms'] for r in actual])} |\n"
    cadence_table = "| Real 3-second cadence, mature world | All ordinary samples | Boundary → correct visible paint median / p95 / max ms |\n|---|---:|---:|\n"
    for label, group in (
        ("Sequential control", normal(cadence_control["rows"])),
        ("Optimized preparation, including misses", normal(experiment["rows"])),
        ("Prepared hits only (diagnostic subset)", normal(hits)),
        ("Not-ready fallbacks only (diagnostic subset)", normal(misses)),
    ):
        cadence_table += f"| {label} | {len(group)} | {stats([r['total_ms'] for r in group])} |\n"
    cadence_critical = "| Non-overlapping segment at real cadence | Sequential control median / p95 / max ms | Experimental preparation, including misses |\n|---|---:|---:|\n"
    for label, values in (
        ("T0 → T1: boundary world/player completion", lambda r: (r["worker"]["t1"] - r["t0"]) * 1000),
        ("T1 → T2: persistence/projection/encoding/IPC/decode", lambda r: (r["t2"] - r["worker"]["t1"]) * 1000),
        ("T2 → T3: visible patch", lambda r: (r["t3"] - r["t2"]) * 1000),
        ("T3 → T4: correct paint", lambda r: (r["t4"] - r["t3"]) * 1000),
    ):
        cadence_critical += f"| {label} | {stats([values(r) for r in normal(cadence_control['rows'])])} | {stats([values(r) for r in normal(experiment['rows'])])} |\n"
    accounting_table = "| World / portfolio | Samples | Complete player commit median / p95 / max ms |\n|---|---:|---:|\n"
    for label in copies:
        for case in ("no player", "mixed expiry"):
            values = [r["player_commit_ms"] for r in accounting if r["checkpoint"] == label and r["case"] == case]
            assert len(values) == 2
            accounting_table += f"| {label} / {case} | {len(values)} | {stats(values)} |\n"
    report = f"""# Retail-investor decoupling and safe-precompute decision — 6 October 2026

**Implemented:** the explicitly approved small-investor boundary and preservation of player accounting. **Not enabled:** full or partial next-day speculation. An optimized isolated-world prototype produces exact world/checkpoint/RNG results, but fails the sustained three-second cadence: 8 prepared hits are followed by 12 consecutive not-ready fallbacks. Including misses, ordinary boundary latency rises to approximately 674 ms median versus 385 ms in the serial cadence control. The cost gate rejects enabling speculation; the verified retail correction remains.

The user approved the product rule in the chat; the attached document supplied the audit scope and conditional implementation criteria. Existing workspace changes from earlier passes were retained. This report closes all 28 requested points.

## 1. Complete coupling matrix

The pre-change inventory was completed and saved before production edits. Categories A/B/C/D/E and source evidence are in [the original audit](retail-investor-coupling-audit-2026-10-06.md).

{matrix}

## 2. Intentional and accidental coupling

World → player prices, dividends, coupons, expiry, default, credit charges, PnL and margin remain intentional. Retail size → global positioning, ownership → chain survival, conditional player world-RNG draws, depleted wealth → incomplete world day, and player messages → truncation of NPC news were accidental under the approved rule. NPC fund portfolios, issuer debt, production inventories, macro credit and bond-market liquidity remain world inputs.

## 3. Retail boundary

Ordinary player trades change portfolio/cash/realized results at current authoritative quotes. They do not enter NPC price, production, macro or aggregate-positioning formulas. A completed day uses world evolution, an ordered accounting-event/mark frame, current player accounting, history/date completion, then the existing persistence and compact visible publication. Scheduling/pause remain controls; no speculative world is published.

## 4. Economic files and semantic reasons

`market_calculations.py`: remove only retail notional from global positioning. `cryptos.py`: remove ownership protection and apply delisting losses. `monthly_assets.py`: separate fee payouts and player randomness. `company_lifecycle.py` / `companies.py`: preserve report dividends and issuer losses as ordered player events. `simulation.py`: independent world completion and explicit accounting commit. New `player_accounting.py`: recorded marks, deterministic player stream, keyed bond credit event, lifecycle losses and visible news merge. `bond_calculations.py`: preserve credit probability/payouts with the keyed event. `checkpoints.py`: serialize player RNG/notices with version 7 and validate before mutation. `save_migrations.py`: share that version with the real save loader. `randomness.py`: explicit reseed resets the player stream. `legacy_runtime.py`: a completed margin call remains inactive/paused, including subsequent requested steps. `legacy_state.py`, `visible_state.py`, `data_store.py`: publish/persist player notices without mutating world news. The exact {len(changed)}-file list is in `.cache/retail-decoupling/final-changed-source.json`.

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

{phase_table}

{conditional_table}

Funds and indices are sequential subphases of `asset_market`; their NPC underlying references and pressure effects are preserved, not treated as the player portfolio. Report/company/crypto/monthly-production and policy phases are conditional closures, measured in the special-day runs. Persistence/projection/IPC/UI paint remain RED publication work. Tiny event/macro/roll prefixes cannot materially reduce the observed hundreds of milliseconds; no dependency graph or reconciliation system was added.

## 16. Architecture actually implemented

Retained the explicit in-process world/accounting split with an ephemeral `PlayerDay` frame. It is completed synchronously by the existing live worker before current-state publication. Immutable marks bridge original economic timing, while portfolio mutations use current holdings. No speculative ownership or future-state exposure exists in the final architecture.

## 17. Memory and copy cost

One graph `deepcopy` of checkpoint-owned world fields preserves nested NPC reference identity and isolates mutable state; player/control fields are excluded and only empty player placeholders are added for engine construction. Each sample includes facade/engine construction and index warming. Five copies per fixture, collected and measured separately from tests/UI workloads:

{copy_table}

RSS measures resident memory, not the exclusive logical size of the second world: decoded checkpoints and the allocator's reusable arena reserve are already present before copying. The modest RSS increment must not be mistaken for complete allocation cost. The standard-copy experiment already uses about 1.35 GiB in the mature fixture. A second graph-copy experiment proves exact graph equality and no shared mutable dict/list/set/array identities; only immutable values may be shared.

{optimized_table}

The optimized copy-only observer sees at most {max(r['heartbeat_max_ms'] for values in optimized.values() for r in values):.2f} ms between pulses in a second thread; this is not the native GUI heartbeat. In the real cadence experiment, mature worker RSS starts as low as {min(r['worker']['rss_start'] for r in experiment['rows'])/1048576:.2f} MiB and reaches {max(r['worker']['rss_end'] for r in experiment['rows'])/1048576:.2f} MiB, versus a control maximum of {max(r['worker']['rss_end'] for r in cadence_control['rows'])/1048576:.2f} MiB. Isolated full-checkpoint comparisons also retain encoded checkpoint graphs and are deliberately not used as an application memory estimate.

## 18. Preparation and player-commit timing

Preparation and publication timings above belong to the isolated prototype. The final program has no background preparation/publication/swap feature because it was rejected after real cadence measurement. Its world core remains in the boundary. Separate real-engine commit timings on isolated fixtures include payouts, expiry, risk, coupons, wealth/history and date completion, without persistence:

{accounting_table}

Two samples per case are diagnostic, not a high-percentile guarantee. The mixed case has stock/crypto/fund/commodity holdings, expiring option/CDS/future, an open short, debt and a maturing government bond.

## 19. Boundary critical path

{critical}

The preceding table is the existing rapid-loop final-source driver. The additional native three-second control and experimental run expose the actual speculative tradeoff:

{cadence_critical}

Segments are non-overlapping; their individual medians need not add to the median total. Sequential-core measurements include synchronous world evolution and player commit. On experimental hits, the boundary core measures world publication and player commit; the earlier background preparation is reported separately and is never counted as boundary work. On misses it measures the normal world day. Projection/encoding/IPC continue using the existing visible-only protocol.

## 20. Boundary → visible-correct before/after

| Comparable sample | Ordinary days | Core median / p95 / max ms | T0 → T4 median / p95 / max ms |
|---|---:|---:|---:|
| Archived preceding pass | {len(normal(archived['rows']))} | {core(archived)} | {total(archived)} |
| Frozen pre-edit source, measured in this pass | {len(normal(before['rows']))} | {core(before)} | {total(before)} |
| First current-source run | {len(normal(early['rows']))} | {core(early)} | {total(early)} |
| Current-source repeat | {len(rows)} | {core(native)} | {total(native)} |
| Current young world | {len(normal(results['native-young']['rows']))} | {core(results['native-young'])} | {total(results['native-young'])} |

These native runs are serial and use the same preserved fixture and real request/worker/paint driver. Timing varied materially between runs; the archived ~394 ms should not be presented as a contemporaneous control. The rapid-loop decoupling measurements do not show a speed improvement. Cadence affects the measurement conditions; do not infer a source-level optimization from the faster three-second control.

{cadence_table}

The experiment and control each cover 20 consecutive transitions, including one report day. Ordinary statistics exclude the report and include every readiness miss. Even its hit-only subset remains above 100 ms. The final program uses the sequential path; no claimed precomputation gain exists.

## 21. Heartbeat

Ordinary mature maximum heartbeat gap: pre-edit control {gaps(normal(before['rows'])):.2f} ms; final repeat {gaps(rows):.2f} ms. All visible updates execute on the Qt main thread; T0 ≤ T1 ≤ T2 ≤ T3 ≤ T4 and worker exit are asserted. Long worker flushes are separate from GUI-thread stalls. Native navigation maximum observed gap: {max(r['heartbeat_max_ms'] for r in navigation['rows']):.2f} ms.

At the measured three-second cadence, ordinary native GUI heartbeat maximum is {gaps(normal(cadence_control['rows'])):.2f} ms for the sequential control and {gaps(normal(experiment['rows'])):.2f} ms for the experiment including misses. Background phase timers are filtered by worker-thread identity so they cannot be mistaken for boundary work.

## 22. Special days and durable flush

{special}

Ordinary statistics exclude reports, month ends and flushes. Small special-day sample counts are stated rather than marketed as stable percentiles. DuckDB's existing durable batching/flush remains unchanged, including its separate seconds-scale cost.

## 23. Tests

Final complete suite: **{suite.attrib['tests']} tests, zero failures/errors**, {float(suite.attrib['time']):.2f} seconds. Targeted runs found and corrected an initial Gold-Dinar test assumption and the real save-version mismatch before full-suite verification. Exact retail comparisons, accounting tests, existing NPC squeeze tests, checkpoint/migration tests, actual process tests and UI continuity tests are included. New files pass Ruff; old tolerances were not widened.

## 24. 365-day evidence

`.cache/retail-decoupling/no-player-before.json` is the immutable source-reference result. `no-player-final.json` is the final source result. `no-player-final-comparison.json` has all four checks true: daily state/RNG, checkpoints at days 15/31/181/365, complete final checkpoint, database. Earlier `no-player-after.json` also passed independently. Reference source, source hashes and the per-pass diff are retained for review.

## 25. Save/Load and pause

Version 7 is shared by checkpoint writer and loader; versions 4/5/6 remain supported. Player RNG/notices survive save/load, and invalid random state is rejected before live mutation. Actual disk save → report continuation → load → replay returns identical world/RNG and player signatures. Paused simulation does not advance on direct world stepping; explicitly requested manual steps preserve existing behavior. In-flight sequential requests finish as before. Margin-call completion leaves the runtime inactive/paused and further steps do not advance it. No speculative state is serialized.

## 26. Nine views and continuity

All nine views have three transition samples in both young and mature worlds. Native company chart, overview and supply each have six transition samples with real Stock selection. Ticker identity/offset/geometry/current quote checks, hidden-chart exclusion, correct visible paint, selection/tab/model/card/chart reuse regressions and on-demand synchronization remain verified. Native navigation exercises all asset categories, country/product/FX/bond/calendar details, portfolio and Save/Load: {len(navigation['rows'])} samples over two repetitions.

## 27. Remaining bottlenecks

Daily production and price formation dominate synchronous core computation; visible-state persistence/projection/serialization/IPC and Qt patch/paint remain on the publication path. Optimized whole-world graph copying still misses readiness in a sustained mature run and then adds contention to normal progression. Flush is a separate durability cost. A smaller world/history ownership design would be a distinct architecture project; a complex rollback, invalidation or reconciliation mechanism was not added to this pass.

## 28. Gameplay-fluidity verdict

**The approved retail semantics are implemented and exactly regression-tested.** Player accounting and current-day UI publication are preserved. **Precomputation is not justified by the measured implementation cost, and the sub-100-ms boundary goal was not achieved.** The audit-supported correction remains useful independently: ordinary retail positions no longer steer global prices or global randomness, while the world still determines portfolio outcomes.
"""
    path = ROOT / "docs/retail-investor-decoupling-and-precompute-2026-10-06.md"
    path.write_text(report, encoding="utf-8")
    print(path)
    print("Tests", suite.attrib["tests"], "365-day comparison", comparison)


if __name__ == "__main__":
    main()
