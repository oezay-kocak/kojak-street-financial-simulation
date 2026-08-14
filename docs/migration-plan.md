# Kojak Street Migration Plan

## Goal

Move Kojak Street from a first-generation Tkinter prototype into a stable,
professional PySide6 desktop application without losing the existing game.

The guiding rule is: keep the old app runnable while the new app grows beside
it. Replace one vertical slice at a time only after it behaves correctly.

## Phase 1: Foundation

- Fix project hygiene: metadata, dependency list, README, development notes.
- Introduce a `src/kojakstreet` package for the new architecture.
- Keep legacy modules in place until migrated.
- Create adapters that can read legacy global state without forcing a big-bang
  rewrite.
- Add smoke tests for core operations once Python is available in the local
  environment.

## Phase 2: Core Separation

Target modules:

- `kojakstreet.core.state`: game state containers and domain models
- `kojakstreet.core.market`: market update rules
- `kojakstreet.core.trading`: buy/sell, bonds, loans, FX, derivatives
- `kojakstreet.core.persistence`: save/load with schema versions
- `kojakstreet.core.news`: event and news stream

The first step is to wrap the current global data from `daten.py` into an
explicit state object. After that, the update logic can be moved piece by
piece.

## Phase 3: PySide6 UI

Target user experience:

- main shell with top KPI bar, left navigation, and workspace panels
- market grid with sorting, filtering, watchlists, and asset details
- portfolio view with exposure, PnL, cash, loans, bonds, and derivatives
- chart workspace with instrument comparison, time ranges, and indicators
- macro dashboard with central-bank decisions and country metrics
- news/event feed with detail pane and impact tags

Qt Widgets should be used first for reliability and speed. Qt Charts or
Matplotlib-in-Qt can be evaluated for charts. If the charting requirements grow
heavy, pyqtgraph is a strong candidate for fast interactive plots.

## Phase 4: Save Games

Replace raw pickle saves with a versioned format:

- `save_version`
- timestamp
- game date
- cash, FX balances, positions, loans, bonds
- asset universe and histories
- macro histories
- news stream

JSON is easier to inspect and migrate. SQLite is better if histories become
large.

## Phase 5: Feature Expansion

After the base is clean:

- order types: market, limit, stop, take profit
- watchlists and saved filters
- transaction ledger
- dividends, fees, taxes
- improved rating model
- richer macro cycles
- scenario editor
- risk analytics and exposure views
- backtesting/simulation controls
- configurable asset universe from files

## Immediate Next Slice

Build a minimal PySide6 shell that starts independently of Tkinter:

1. load legacy data through an adapter
2. render top KPIs
3. show a read-only market table
4. show one chart panel
5. keep the old `terminal.py` as the known-good app

