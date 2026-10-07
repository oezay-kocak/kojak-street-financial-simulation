# Kojak Street — Case Study

**Özay Kocak · Banking, product thinking and AI-assisted software development**

Kojak Street began as a small stock-market game and became a working desktop simulation of an interconnected fictional economy. This case study describes how I translated a broad idea into requirements, investigated problems, evaluated trade-offs and brought the current portfolio scope to feature freeze.

For the product overview and installation, see the [README](../README.md). The [verification record](portfolio-closeout-2026-10-08.md) links the detailed engineering evidence.

## Context and initial idea

I trained as a banker and worked in customer service and advisory roles involving savings, building-society products, securities, loans and private-client banking. Economics, politics, history, financial markets and monetary systems have been long-standing personal interests.

During a career break and personal learning period, I explored how those interests could become a software product. I did not come from a traditional software-development background. My approach combined self-study, learning by doing, feedback from software-developer friends and practical use of AI-assisted development tools.

The original idea was modest: a broker-terminal game with moving stock prices and a simple macroeconomic background. As the project developed, I wanted the player to have reasons to inspect an asset beyond its latest price. That led to company fundamentals, production inputs, supply and demand, credit, country conditions and portfolio risk. The challenge became keeping these relationships understandable and internally consistent.

## My role and the development workflow

I owned the product idea, economic concepts, scope, priorities and acceptance decisions. That meant deciding what the player should be able to investigate, turning financial intuition into explicit rules, defining expected behavior, identifying problems, forming hypotheses and reviewing whether the results supported those hypotheses.

LLM/Codex tools helped with decomposition, implementation, refactoring, debugging, test design, research and documentation. I do not claim to have manually written every implementation detail. Equally, a generated implementation was not sufficient evidence that a requirement had been met. It needed review, executable checks and a clear explanation of the model's limits.

A recurring workflow was to define the desired behavior, inspect the current implementation, audit dependencies, make a bounded change, compare results and decide whether to retain it. The performance work below is a concrete example: “make it faster” did not identify the right problem. Progress required a more precise question about which data the player actually needed at each moment.

## Challenge 1: modeling an interconnected economy

A market simulation can easily become a collection of unrelated random numbers. I wanted an economic world where the interface could explain connections: a company's inputs and capacity, a country's trade position, a credit rating, or fund-flow pressure on an underlying asset.

The initial world now contains 20 countries, 16 sectors and 1,280 companies, together with resources, products/services and financial instruments. Macro conditions, expectations, production bottlenecks, fundamentals, credit and psychology participate in the model. Multiple drivers can offset one another: a supply shock can raise scarcity pressure without guaranteeing a higher final price.

An important distinction was **root state versus derived state**. Country population, initial GDP and company capitalization belong to world initialization. Shares, revenues, balance-sheet relationships, fund holdings, bond references and indices must then derive consistently from those roots. Randomizing every field independently would create diversity at the expense of coherent relationships.

The country-index audit also exposed the need to distinguish instrument type from ticker text. The repaired broad and sector indices use the actual company membership of each country; the initial world has 340 country/sector index quotes. A symbol is not always enough to identify an instrument safely.

Another product boundary was the player's economic role. I explicitly chose a retail-investor model: ordinary trades and holdings should not alter global price formation or the world's random sequence. The coupling audit found indirect dependencies, including player positions in open interest and holding-dependent random payouts. Those were separated while preserving player accounting, dividends/coupons, PnL, margin, liquidation and settlement. World events still affect the player; small player actions no longer reshape the economy.

The model remains synthetic and simplified. Internal consistency makes it more useful to explore, but does not turn it into a calibrated pricing engine or a forecast of real markets.

## Challenge 2: investigating visible stutter

As the simulation and analytical views grew, advancing a day became visibly uneven. My initial concern was the amount of economic calculation. The audit measured the complete transition instead: core execution, state preparation, history work, serialization, transfer, UI updates, painting and persistence.

That changed the diagnosis. In one original native first-year run, ordinary transitions had a median around 1.33 seconds, while a separate headless/no-flush core measurement was around 224 milliseconds. Those different boundaries were useful for locating costs, not for claiming a matched speedup. A mature-world native path was slower still. Much of the work happened around the economy rather than inside it.

### What improved—and what did not

The first remediation made history synchronization incremental and improved batch transport. It removed repeated merging of unchanged history. However, a broad public world still existed in both worker and UI, and creating a recursive delta still traversed that world. Reducing bytes on the wire did not remove the work needed to prepare them.

That pass had a measurable drawback: a first-year ordinary-day comparison became slower as the published UI state became more complete. It was a useful warning against treating an isolated microbenchmark as the final user experience.

The stronger hypothesis was that **hidden views did not need a continuously mirrored world**. The resulting architecture publishes global status and the current active view, then requests selected entity/tab details on demand. Deep history has its own request path. Markets still receives its complete current quote table; this is not merely a shortcut that updates the rows currently visible on screen.

Chart continuity and ticker rendering required separate work. Existing series remain visible while newer history is requested, obsolete responses cannot replace a newer selection, and ticker updates no longer wait for an entire long scrolling cycle. Correct visible values and stable presentation are part of performance, not just a lower worker time.

### A measured timeline

The rows below are separate experiments against their own frozen references. They must not be multiplied into a single end-to-end speedup.

| Investigation | Matched or diagnostic result | Boundary and qualification |
| --- | --- | --- |
| Initial measurement, 5 October | Native first-year ordinary median ~1,331 ms; separate headless/no-flush core ~224 ms | Diagnostic attribution with different boundaries, not a before/after optimization |
| First remediation, 5 October | Mature native path ~3.50 → 1.85 s; first-year no-flush ordinary path ~1.26 → 1.41 s | The mature improvement did not remove the broad-state architecture; the first-year regression is retained |
| Visible/on-demand synchronization, 6 October | Ordinary median 2,271 → 445 ms | Native Windows mature checkpoint; 37 ordinary days after, report/flush days separated |
| Final targeted pass, 6 October | Ordinary median 398 → 291 ms | A new matched native series, 37 ordinary days per side; visible values, history, chart commit and paint included |
| Synchronous flush remediation, 6 October | Raw flush median 4,250 → 3,641 ms | Identical isolated copies; three raw flushes per side, with commit and compaction retained |
| Ordered writer, 6 October | Visible warm flush transition 4,117 → 1,155 ms in a one-flush pair | Native UI boundary after durable journal handoff; a separate ten-flush after series had median 490 ms and maximum 1,163 ms. DB work still completes in the writer. |
| Politics V1 control, 7 October | Ordinary median 158 → 161 ms; monthly politics phase 0.263 ms | Headless 90-day runtime controls with writer active; CPU median unchanged. One election phase measured 0.403 ms |

Native measurements used Windows, a Ryzen 9 3900 system and roughly 16 GiB RAM. The locally tested runtime was Python 3.12.14, NumPy 2.5.1, DuckDB 1.5.5, PySide6 6.11.1 and pyqtgraph 0.14.0. Sample definitions and exclusions are in the [dated reports](portfolio-closeout-2026-10-08.md#evidence-and-historical-reports).

The latest 161 ms value describes a headless runtime day, not a freshly measured desktop paint latency. Report days, history compaction, cold navigation, Save/Load and backpressure remain more expensive. The intentional display duration of an in-game day is separate from transition computation.

### Persistence without weaker guarantees

Periodic DuckDB flushes remained expensive after the synchronous improvements. Moving writes off the day path was justified only after examining recovery, ownership, ordering and backpressure.

The implemented writer has one DuckDB owner. The simulation materializes immutable rows, writes a durable journal before publication, and submits ordered batches. Transactions commit before acknowledgements are made durable. Save, Load, history reads and shutdown wait at barriers. A bounded number of outstanding batches prevents an unlimited queue; sustained overload causes waiting rather than silently dropping data.

Validation terminated actual child processes at six crash boundaries around copy, commit and acknowledgement. Recovery accepted atomic old/new states and idempotent journal replay. Large-row fixtures and continued simulations checked logical data integrity. This is substantially different from putting writes into a RAM queue and calling the UI faster.

An existing limitation also remained explicit: multi-threaded native SQL aggregation can change the least significant bits of yearly averages. Controlled single-thread comparisons established exact aggregates; the audit did not hide native aggregation differences by loosening tolerances.

### A rejected optimization

After retail decoupling, next-day precomputation was reassessed rather than assumed safe and worthwhile. An isolated copied-world prototype could preserve exact state, but a mature copy cost about 2.15 seconds. In a real three-second cadence experiment it produced eight ready hits followed by twelve fallback days. The ordinary-day control median was about 385 ms; the experiment including misses was about 674 ms.

The faster hit-only subset was not a valid reason to ship it. Full and partial speculative next-day computation remain disabled. The retained UI continuity improvements work with sequential authoritative simulation.

## Challenge 3: adding depth without restoring broad daily work

The final additions had to respect the architecture established by the performance investigations.

**Heterogeneous World** adds controlled country and company diversity once at initialization. Population, GDP and initial equity-capitalization budgets remain exact. Seed-derived initialization streams avoid consuming the daily economic RNG. Derived values follow the existing bootstrap path, and the world starts on Day 1 without fictional price history. Genesis provides the common baseline; Established provides genuine generated prehistory followed by daily burn-in.

**Workforce and demography** separate population development, labor availability and company requirements. The three pools are Basic, Skilled and Highly Qualified. Birth/death rates and a bounded macro adjustment contribute to population growth. Supply, demand and coverage use aggregate workforce equivalents; company shortages have a bounded monthly effect. Macro headline unemployment remains a separate measure. This avoids pretending that a coverage ratio is an observed unemployment statistic or that the model contains individual age and education cohorts.

**Politics V1** adds seven systems: parliamentary, presidential and semi-presidential democracy, constitutional and absolute monarchy, one-party state and authoritarian republic. Competitive systems have elections and government formation; other systems use appropriate leadership/review rules. Economic and social ideology axes describe governments rather than providing a complete policy simulator.

Politics uses country-specific deterministic streams, monthly updates, events and sparse history. A multi-seed audit covered 200 seeds across 20 countries. The Society & Politics tab requests the selected country, rather than broadcasting all countries' political histories every day.

![Current Society and Politics country view](assets/society-politics.png)

The screenshot is an actual Heterogeneous World after 75 daily steps. It distinguishes initial mandates from recorded election results—a small but important example of honest UI semantics.

## Quality and validation

Testing combined small behavioral checks with broader comparison runs. Exact comparisons covered economic state and random-number-generator state, not just whether an application stayed open. Where a feature intentionally changes economics, the checks distinguish that intended change from unrelated regressions.

Evidence includes 365-day runs, 5/20/50-year Established coarse-history comparisons with 365 daily burn-in steps, multi-seed initialization, genuine older-save compatibility, player-action isolation, Save/Load continuation, journal replay, crash recovery and real live-process UI navigation.

The final full run collected 732 cases: 731 passed and one failed because an older UI test expected four country tabs. The delivered product intentionally has five. That expectation was updated, including the exact tab titles, and all 12 cases in its module then passed. Hashes confirmed unchanged production and other test files. The verified aggregate is 732 cases; it is not presented as a second clean full run.

Long-run checks validate the tested configurations, not every imaginable seed or a century of full daily economics. Reproducibility also depends on model/dependency versions. A save checkpoint and its analytical history store have separate responsibilities and must remain paired.

## Decisions about scope

Several decisions define the delivered product:

- The political government-bond premium stays **off**. Coarse-history bond quotes, curves, bond-fund NAV and yield derivatives did not all satisfy the same consistency gate.
- Politics remains a compact descriptive and event-based system, without a political grand-strategy or full policy model.
- A separate housing/real-estate market is outside this portfolio scope. Real-estate equities already exist; the absence of a housing simulator is not an unfinished required feature.
- Ordinary UI updates retain visible/on-demand projection. New features do not justify returning to broad daily state mirroring.
- Speculative precomputation is not shipped on the strength of favorable ready-hit timings.
- Source and Python wheel are supported. The experimental frozen executable is not release-approved.

These choices make the scope reviewable and achievable. Feature freeze is a delivery boundary, not a declaration that the project can never evolve.

## What I learned and why it relates to business analysis

The project developed my practical understanding of Python, object-oriented code, tooling, tests, debugging and application structure. More fundamentally, it taught me to turn a vague idea into explicit behavior and acceptance criteria, separate causes from symptoms, and use evidence to change an initial assumption.

UI work made the user perspective concrete: a technically correct state is insufficient if a chart clears unnecessarily, a visible ticker stays stale or a label suggests an election that never happened. Architecture and data ownership became product concerns because they determined responsiveness, consistency and what a save could promise.

AI assistance accelerated implementation, but its usefulness depended on the clarity of the task and the strength of verification. I learned to question plausible answers, define precise comparisons, preserve failure evidence and reject changes that did not meet the measured goal.

Those habits connect naturally to business analysis: translating domain knowledge into requirements, breaking an interconnected system into understandable responsibilities, testing hypotheses, prioritizing improvements and explaining trade-offs to different audiences. Kojak Street gives me a concrete working product through which to demonstrate that process.

## Final result

Kojak Street is **Feature Complete / Feature Freeze for the current portfolio scope**. It provides an evolving fictional economy, an interactive financial terminal, portfolio accounting, three starting-world modes, society/politics views and persistent history.

The result is a personal learning and portfolio project with working software and documented limits. Its value is the connection between banking knowledge, product ownership, AI-assisted implementation, measurement and validation.

[Run or explore the application](../README.md#installation-and-first-run) · [Architecture](architecture.md) · [Model assumptions](model_assumptions.md) · [Verification and evidence](portfolio-closeout-2026-10-08.md)
