# Source / wheel release readiness — 28 September 2026

This report covers the repaired working tree, including the previously unpublished
modern runtime, history, generation and UI modules. It supersedes the earlier
diagnostic conclusion for this revision only. The historical local portfolio
audit and its measurements were preserved unchanged; raw logs, machine paths,
savegames and large audit/build outputs are deliberately excluded from Git.

## Cause and repair

The two checkpoint continuation failures were reproduced before editing:
**2 failed**, pytest 115.67 seconds, command exit 1. Immediate numerical state and
RNG equality did not imply equivalent future behavior. A phase-by-phase trace
located the first divergence in `asset_market`, after matching monthly, event,
macro, production, credit and bond phases.

Fund caches `_resolved_underlyings` and `_fund_pressure_targets` contained live
asset references. JSON expanded those references into separate asset copies;
after restore, fund returns and flow pressure used stale, disconnected objects.
The trace found all 2,349 resolved references detached after loading.

`core/checkpoints.py` now writes V6 and excludes exactly these reference caches,
rebuilding them against live instruments. Restore also removes them from V4/V5
files. Numerical caches, Python/NumPy RNG state and computational price/FX
histories are preserved. Save-only price-history truncation could invalidate EMA
cache lengths and lookbacks, so it was removed. Only regional and company
input/output **display** histories retain two samples; their current values are
also sufficient for analytical row recording. Older summaries belong to the
matching DuckDB session. This avoids a 90 MB checkpoint and repeated-load timeout
observed during development without discarding computational lookbacks.

`adapters/legacy_state.py` also omits the two reference caches from UI snapshots:
serializing their object graph into IPC caused an actual source-start timeout.
The adapter test verifies that snapshotting does not mutate the live caches.

Regression coverage compares the full canonical checkpoint after **each of four
continued days**, for both original start dates, including monthly processing.
Additional tests cover long computational history/EMA rollover, old cached
V4/V5 saves, live object identity and display-only retention. The real subprocess
test now repeats a 17-day continuation across the next report and loads twice.
The chart test requires all saved computational history while retaining its
separate UI-window assertions. Assertions were not relaxed to tolerate drift.

The FX tests now construct and close their own seeded runtime instead of reading
state left in the global `daten` module by another test. The Qt portfolio-delta
test uses the actual `SimulationDelta` contract, including `date_text`.

## Verification

Local platform: Windows 11, Python 3.12.14. Development dependencies are recorded
in `requirements-tested-py312.txt` (NumPy 2.5.1, DuckDB 1.5.5, PySide6 6.11.1,
pyqtgraph 0.14.0, pytest 9.1.1). Commands used isolated data directories.

| Check | Result |
| --- | --- |
| Historical full diagnostic suite, before this task | 292 passed, 4 failed, 0 skipped; historical evidence only |
| Initial focused checkpoint, FX, Qt and migration regressions | 18 passed in 202.87 s; exit 0 |
| Final full suite | **302 passed, 0 failed, 0 errors, 0 skipped** in 823.47 s; exit 0 (command wall time 828.28 s) |
| `compileall -q src tests tools` | Passed in 0.359 s; exit 0 |
| Wheel build | Passed; exit 0 |
| Installed-wheel smoke outside checkout | Passed in 12.718 s; exit 0; build, install, Qt runtime and shutdown |
| Normal source chooser/live-process smoke | Passed in 61.840 s; exit 0 |
| Fresh-venv installed-wheel chooser/live-process smoke | Passed in 60.849 s; exit 0 |
| Fresh environment `pip check` and import origin | Passed; exit 0; project modules came from installed wheel |
| Git whitespace and publication-file review | Passed; no staged secrets, private user paths, emails or generated outputs found; README links exist |

The fresh wheel environment resolves NumPy 2.5.3 and PySide6 6.11.2, with DuckDB
1.5.5 and pyqtgraph 0.14.0. It has no access to development site-packages. This
checks a real installation, not merely an editable checkout or a target directory
borrowing all development dependencies.

`tools/source_smoke.py` invokes the normal Qt `main([])`, accepts Genesis seed
1729, verifies a separate live worker, navigates all nine views, buys spot,
opens/closes a leveraged future and checks portfolio state. It saves on January
14, crosses the January 15 monthly report, restores, compares the four-day
continuation, closes the window and verifies worker exit. The same probe runs
against the freshly installed wheel outside the checkout. Qt is offscreen:
these are functional UI checks, not a new visual/DPI or manual usability audit.

Intermediate failures remain in local artifacts: an early full run was stopped
after the old chart-history expectation failed; the first source probe exposed
the IPC cache issue; an expanded load test exposed oversized display histories.
One intermediate retention unit test caught a list-versus-dict dispatch mistake,
which was corrected before the final suite. None is counted as a passing run.

## Publication and remaining limits

README now documents a venv, launcher/installed entry point and wheel install;
Genesis and Fast History V2 with yearly/monthly generation, rebaseline and 365
daily burn-in days; four existing screenshots; AI-assisted authorship and the
synthetic model's limits. This does not claim an AI prediction engine.

The publication includes required source, tests, diagnostic tools, CI and an
explicitly experimental PyInstaller spec. It excludes virtual environments,
databases, saves, raw audit results, local drafts, builds and executable binaries.
The unused source-to-text export helper is removed. Existing public screenshots
are retained; the old test screenshot is not used as current verification.

- **Source / wheel:** accepted on the locally verified Windows/Python 3.12 path.
- **Windows EXE:** not approved. The historical frozen smoke hung; no repaired
  EXE startup is claimed. The checked-in spec is experimental build configuration.
- **Old saves:** V4/V5 and legacy migration paths remain readable. History absent
  from an old file cannot be recovered; identical continuation of old saves is
  not promised. Checkpoint and matching analytical store belong together.
- **Model:** synthetic rules, no empirical pricing/forecast validation, no newly
  repeated century-long economic run. Fast History is not daily simulation of
  the entire prehistory. Historical oil-shock evidence did not show a reliably
  higher terminal oil price.
- **Engineering:** lint debt remains; Ruff is not claimed green. One mutable
  world per process is supported. Dense views may need scrolling on small screens.
  Local verification is Windows/Python 3.12; remote matrix results are separate.

Repository: [kojak-street-financial-simulation](https://github.com/oezay-kocak/kojak-street-financial-simulation).
Baseline commit: `4173a20fb4c9716d1bddf8a8598b7f6b5fb8d9cf` on `main`.
Release code commit: `786c71e` (`Publish verified source and wheel runtime with
deterministic checkpoint continuation`). This report is the following
documentation-only commit; both are intended for a normal fast-forward push to
the existing `origin/main`. No history rewrite or force-push is needed.

Remote CI is separate from the completed local checks. At report creation the
new workflow has not yet run remotely; no green CI result is claimed. The
delivery message records the post-push readback and observed status. Current
results are visible in [GitHub Actions](https://github.com/oezay-kocak/kojak-street-financial-simulation/actions).

**Application-link assessment:** suitable as a self-guided source/wheel portfolio
link, with a Python installation required and the limits above visible. It is
not an approved one-click Windows executable. A reviewer can inspect the model,
screenshots and tests, follow the installation instructions and explore Genesis.
