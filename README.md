# Kojak Street

A desktop economic and financial-market simulation built with Python, PySide6,
pyqtgraph and DuckDB. Explore how macro conditions, production bottlenecks,
company fundamentals, credit and market psychology affect fictional markets
and a trading portfolio.

This is a portfolio project at the intersection of banking, business analysis,
product development and AI-assisted software engineering. It is a synthetic
learning environment, not an investment tool or a professionally calibrated
forecasting or pricing model.

## Start here

Use **Python 3.11 or 3.12**. Python 3.12 is the locally verified environment;
the CI workflow also targets 3.11. From a checkout, on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe kojakstreet_qt_launcher.py
```

The installed entry point is `.\.venv\Scripts\kojakstreet-qt.exe`.
On Linux, use `.venv/bin/python` and `.venv/bin/kojakstreet-qt` instead.
A working graphical desktop and Qt system libraries are required for the UI.
For a first tour, choose **Genesis World**, seed **1729**. Open Markets,
Supply Chain, Macro and Portfolio. Run through the first monthly report on
the 15th, pause, inspect a company, and place a small spot trade.
Use a larger desktop window for dense portfolio/detail tables; some views
require scrolling at 1366×768.

The supported delivery path for this revision is **source / Python wheel**.
The experimental Windows executable is **not release-approved**: its previous
frozen smoke test did not finish. Building an EXE is not evidence that it starts.

## Two starting worlds

- **Genesis World** starts a young fictional economy immediately. The baseline
  contains 20 countries, 16 sectors and 1,280 companies, alongside commodities,
  processed products, crypto assets, funds/ETFs, indices, bonds and derivatives.
- **Established World** offers 50, 75 or 100 years of prehistory in a separate
  generator process. Its default is **Fast History V2**: correlated yearly and
  monthly steps, a rebaseline of the live state, then 365 days of the normal
  daily simulation as burn-in. The entire prehistory is **not** calculated with
  the same daily production economy. Generation can be cancelled and restarted;
  resuming a partial generation is not supported.

World bundles contain a checkpoint, DuckDB history and integrity metadata.
The optional production-equivalent generator path is separate from the UI's
Fast History default. Short generation tests do not establish economic
stability over a century.

## Four views of one model

| Markets and company drivers | Production and supply chains |
| --- | --- |
| ![Markets](screenshots/01_markets_overview.png) | ![Supply chain](screenshots/03_supply_chain.png) |

| Country macro conditions | Portfolio and exposure |
| --- | --- |
| ![Macro](screenshots/05_macro_dashboard.png) | ![Portfolio](screenshots/07_portfolio_overview.png) |

These overview images illustrate the interface; they are not evidence of a
particular shock outcome or the latest test result.

The executable model includes production recipes and trade flows, revenue/FCF
and company distress, monetary/fiscal conditions, expectations, fixed income,
FX, options, futures, swaps and CDS. Portfolio mechanics include spot and
leveraged positions, FX balances, credit, liquidation and settlement. Aggregate
portfolio values use GD; instrument rows retain their labelled currencies.

## Saves and history

New **V6 checkpoints** retain the bounded computational histories and numerical
caches required for continuation, together with Python and NumPy RNG state.
Live-reference fund caches are reconstructed from the loaded instruments rather
than serialized as disconnected copies. Save replacement is atomic, and a
history manifest prevents attaching the save to an unrelated analytical store.
Display-only regional and company input/output histories keep their last two
samples in the checkpoint; older analytical history stays in the matching store.

V4/V5 checkpoints and older legacy saves remain readable through their migration
paths. Histories omitted by old writers cannot be reconstructed, so identical
continuation of those old saves is not guaranteed. Keep a backup before moving
an old save into a new version. Reproducibility assumes the same model and
compatible dependency versions, not arbitrary future versions.

The UI uses the application's local data directory. Set `KOJAKSTREET_DATA_DIR`
to a separate directory for a demo or test; a direct source runtime otherwise
uses `.cache`. Checkpoint and matching DuckDB history belong together. The live
world keeps bounded lookbacks; DuckDB retains recent daily data and semantic
monthly/yearly summaries. Adaptive ALL charts limit the displayed payload.
Synthetic long-history query tests are not thousand-year economic simulations.

## Verification and wheel installation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src tests tools
.\.venv\Scripts\python.exe tools/wheel_smoke.py
.\.venv\Scripts\python.exe tools/source_smoke.py --output .cache/source-smoke.json
```

The source smoke drives the real New Simulation / live-worker path offscreen,
including trading, monthly processing and continuation after Save/Load.
The wheel smoke checks installed project imports outside the checkout. See the
[release-readiness report](docs/release-readiness-2026-09-28.md) for actual test
counts, environment, results and remaining limitations; historical pass counts
are not current guarantees. The [CI workflow](.github/workflows/ci.yml) defines
Windows/Linux checks; its presence alone does not mean remote CI has passed.

To build a wheel and install it into a fresh environment:

```powershell
.\.venv\Scripts\python.exe -m pip wheel . --no-deps --wheel-dir dist
python -m venv .venv-wheel
.\.venv-wheel\Scripts\python.exe -m pip install dist/kojakstreet-0.2.0-py3-none-any.whl
.\.venv-wheel\Scripts\kojakstreet-qt.exe
```

`requirements-tested-py312.txt` records tested direct dependencies; it is not a
complete cross-platform lockfile. A future unpinned dependency upgrade is not
covered by the current verification.

## Design, background and limits

Özay Kocak supplied the product idea, financial concepts, priorities and
acceptance decisions, drawing on banking practice and self-directed learning.
LLM/Codex assisted planning, implementation, refactoring, tests and debugging.
This describes the development workflow; the application does not contain a
claimed AI market-prediction engine, and no hand-written share of the code is
asserted.

Prices and economic outcomes are fictional and rule-based with seeded random
components. Internal consistency and scenario tests do not establish empirical
forecasting, risk or pricing accuracy. An oil supply shock can increase shortage
and price pressure without a reliably higher final oil price when other model
channels dominate. Not for real trading, investment advice or regulatory use.

- [Architecture and modern versus legacy entry points](docs/architecture.md)
- [Model assumptions and units](docs/model_assumptions.md)
- [Demo themes](docs/demo_scenarios.md)
- [Project background](docs/project_background.md)
- [Release-readiness and remaining risks](docs/release-readiness-2026-09-28.md)

The modern application lives under `src/kojakstreet`; `daten.py` and
`speicher.py` remain active compatibility modules. The older root-level
Tkinter application is not the supported entry point for this revision.

Released under the [MIT License](LICENSE).
