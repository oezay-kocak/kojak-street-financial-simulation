# Portfolio closeout — 8 October 2026

**Status: Feature Complete / Feature Freeze for the current portfolio scope.**

This documentation/repository pass publishes the previously implemented runtime,
starting worlds, workforce/demography and Politics V1 together with an updated
English [README](../README.md) and [case study](project_background.md). No new
product feature or architecture change was introduced in this closeout. A
pre-existing Python 3.11 syntax incompatibility found by publication checks was
repaired without changing the portfolio display's behavior.

## Fact check

An internal claim/source/current/publication sheet was created before drafting.
The following public summary records the claims retained in the final texts.

| Claim | Source and verification | Publication boundary |
| --- | --- | --- |
| 20 countries, 16 sectors, 1,280 companies | Current Heterogeneous runtime capture; [initialization report](heterogeneous-start-world-implementation-2026-10-07.md) | Initial universe, not a fixed count forever |
| 34 resources, 90 products/services, 340 country/sector indices | Same runtime capture; initialization/index tests | No fixed total instrument count claimed |
| Three world modes | `ui_qt/new_simulation.py` mode cards and config | UI labels: GENESIS WORLD, HETEROGENEOUS WORLD, ESTABLISHED WORLD |
| Established 50/75/100 years; 365 daily burn-in | Chooser and `world_generator.py` | Coarse historical development plus daily burn-in, not decades of full daily economics |
| Three workforce pools and bounded monthly company effect | `core/workforce.py`; [implementation report](workforce-birth-rate-implementation-2026-10-07.md) | Aggregate equivalents; macro unemployment is separate |
| Seven government systems; elections/formation and sparse history | `core/politics.py`; [Politics implementation](politics-v1-society-politics-implementation-2026-10-07.md) | Descriptive ideology; sovereign-bond premium disabled |
| Ordinary player trades do not drive global prices | [Retail boundary audit and implementation](retail-investor-decoupling-and-precompute-2026-10-06.md) and regression tests | Player accounting remains fully active; world institutional flows remain |
| No speculative next-day precomputation | Same retail/precompute report | Copied-world prototype rejected after sustained cost/readiness experiment |
| Single ordered, journaled DuckDB writer | `core/persistence_writer.py`; [flush remediation](final-duckdb-flush-remediation-2026-10-06.md) | Durable publication, barriers, replay and backpressure; no RAM-only durability |
| Current V9 checkpoints | `core/checkpoints.py` and save migration readers | Supported V4–V9; old omitted data cannot be recreated |
| 732 verified cases | Final Politics JUnit and case-identity comparison | 731 full-run passes plus corrected module; no invented clean second full run |
| ~161 ms ordinary day / 0.263 ms monthly politics / 0.403 ms election | Final 90-day Politics matched headless controls | Runtime with writer active, not native desktop latency; one election sample |
| Python >=3.11, package 0.2.0, source/wheel supported | `pyproject.toml`, installed checks below | Local Windows/Python 3.12; frozen EXE unapproved |

The earlier count of changed numeric fields is not used as a product-scale or
performance claim. It does not mean that each field was an expensive calculation.

## Final test and installation checks

The existing final implementation run collected **732 cases**, with **731 passed
and one failed** in 2,087.724 seconds. The failure was a stale four-tab expectation.
After updating it to the intended five-tab contract, all **12 module tests passed**.
The unique case-identity union verifies all 732. At the start of this task, all
203 source/test file hashes matched the tested implementation state. Publication
hygiene removed one surplus blank line at EOF in a persistence test. Subsequently,
the proven Python 3.11 compatibility repair changed only string quoting in one
portfolio display expression. Its entire Python 3.12 AST remains identical to
the tested module. All other production/test files are unchanged. One report
generator also received an EOF cleanup.

Additional closeout checks:

- **37 tests passed** across the country-workspace and Qt-shell modules. A pytest
  cache-directory permission warning affected diagnostic cache creation only.
- Source compilation passed for `src`, `tests` and `tools`.
- Current test collection confirmed 732 cases; new documentation/capture tools
  passed their scoped Ruff check. Repository diff whitespace checks passed.
- The current wheel built and its installed-import/Qt smoke passed outside the
  checkout. That small smoke uses the invoking environment's dependencies.
- The complete source start-path smoke passed in **34.244 seconds**: chooser,
  all nine views with real live subprocess, spot purchase, futures open/close,
  Save/Load across a monthly report, identical four-day continuation and shutdown.
- The same complete smoke passed from the installed wheel with `python -I`,
  outside the checkout, in **35.119 seconds**. This reused a separately created
  virtual environment with `include-system-site-packages = false`, replacing
  the old project wheel. It is a representative installed environment, not a
  newly resolved dependency installation during this pass.
- Six complete-window screenshots were generated and visually reviewed. The
  complete world/player/RNG digest was unchanged by capture/navigation.

The old source smoke read player holdings from a Markets projection. On-demand
state deliberately omits those fields. The tool now selects Portfolio before
checking its position; the successful run exercised the actual GUI command.
No production code was changed to satisfy that obsolete assumption. An initial
sandbox attempt also failed to create child-process temporary data; release
checks were rerun with isolated workspace temporary storage and normal process
permissions. Failed attempts are not reported as passes.

| Environment | Versions |
| --- | --- |
| Source/local checks | Windows, Python 3.12.14; NumPy 2.5.1; DuckDB 1.5.5; PySide6 6.11.1; pyqtgraph 0.14.0 |
| Representative installed wheel | Python 3.12.14; NumPy 2.5.3; DuckDB 1.5.5; PySide6 6.11.2; pyqtgraph 0.14.0 |

Local checks do not establish a passing remote CI matrix. The repository's
[workflow](../.github/workflows/ci.yml) targets Windows/Linux on Python 3.11/3.12.
Remote publication/check status is reported separately at completion.

### GitHub readback and Linux CI setup correction

The runtime and documentation were published as normal fast-forward commits
`44a102e` and `182a30b`. GitHub returned the current README and Case Study with
HTTP 200 and rendered HTML, including all six README images and the case-study
image. The branch head was independently checked against the published commit.

The [initial CI run](https://github.com/oezay-kocak/kojak-street-financial-simulation/actions/runs/37695754976)
then exposed a runner setup defect: Linux collection failed with
`ImportError: libEGL.so.1: cannot open shared object file`. This happened before
the tests executed. The workflow now installs Ubuntu's
[EGL](https://packages.ubuntu.com/noble/libegl1),
[GL](https://packages.ubuntu.com/noble/libgl1) and
[OpenGL](https://packages.ubuntu.com/noble/libopengl0) system libraries before
importing Qt. Matrix fail-fast is disabled so one environment does not cancel
the other independent checks. No product behavior, test expectation or timing
threshold was changed for this correction. The new CI run is a separate
verification; passing local results do not establish its final outcome.

After Linux setup succeeded, the Python 3.11 job in
[the next run](https://github.com/oezay-kocak/kojak-street-financial-simulation/actions/runs/37696298709)
exposed a pre-existing f-string in `ui_qt/views/portfolio_view.py` that reused
the outer quotation mark inside an expression. Python 3.12 accepts that spelling;
Python 3.11 does not. Switching the inner dictionary-key/default strings to
single quotes restores the declared compatibility without changing their values.
The complete module AST is identical to the tested version on Python 3.12.

All **297 publishable Python files** passed the native Python **3.11.9** AST
parser. The official portable interpreter was used only for syntax checks in
the ignored evidence directory; it was not installed system-wide or used to
claim a full Python 3.11 application test. After the quoting repair, the same
**37 UI tests passed** again, compilation passed, and the complete source smoke
passed again in **31.728 seconds**. The wheel was rebuilt and its full installed
smoke repeated successfully. Remote matrix execution remains a separate result.

## Screenshots and repository hygiene

The six PNGs under `docs/assets/` show Heterogeneous World, seed 1729, after **75
real daily steps**, on **17 March 1990**. The player bought ten STONE shares.
Ardonia is the country shown; its seven-party allocation is explicitly an
initial mandate, not a fabricated election. Captures use the actual Qt shell
offscreen, with Windows application fonts, at 1680×1050 or 1920×1400.

| Asset | View |
| --- | --- |
| [markets.png](assets/markets.png) | Main market terminal and current price chart |
| [company-detail.png](assets/company-detail.png) | Fundamentals and credit |
| [country.png](assets/country.png) | Observed macro history |
| [society-politics.png](assets/society-politics.png) | Workforce, society and government |
| [supply-chain.png](assets/supply-chain.png) | Production and resource imbalance |
| [portfolio.png](assets/portfolio.png) | Real spot holding, valuation and PnL |

The original larger fixture galleries and raw benchmark data remain local.
Dated engineering reports are preserved, with relative module links and a
historical-context notice. The old test-terminal image was removed from public
assets because it exposed a personal local path and an obsolete count. Earlier
interface screenshots are historical assets rather than the current tour.

Caches, save/history stores, build products, raw captures and logs are excluded.
The ignore rules now also cover local logs and `.env` files. Publication candidates
were checked for cache/save artifacts, oversized files, personal paths and
recognizable secret patterns. No matching secret or accidental data-store file
was found; this is a repository hygiene check, not an exhaustive security audit.

README/Case Study and public documentation links are checked against publishable
files, including images and local heading targets. The small Mermaid diagram uses
standard GitHub flowchart syntax. The images were inspected at their actual sizes;
they are captures of software, not redesigned mockups.

The final local documentation check passed across **27 Markdown documents and
272 local link/heading targets**, including the six selected assets (about
0.76 MiB combined). No personal absolute path, broken publishable link or
recognized credential pattern remained in publication candidates.

## Evidence and historical reports

These reports describe their dated source revisions. Their full-run counts,
schema versions and timings should not be substituted for the current summary.
Detailed raw cache references are local evidence names, not downloadable artifacts.

| Topic | Dated evidence |
| --- | --- |
| Original latency attribution | [Day-transition audit, 5 October](day-transition-performance-audit-2026-10-05.md) |
| First history/state/batch changes | [Performance remediation, 5 October](performance-remediation-2026-10-05.md) |
| Broad-state dependency investigation | [UI-state architecture audit, 6 October](ui-state-architecture-audit-2026-10-06.md) |
| Visible/on-demand synchronization | [Implementation, 6 October](visible-ui-on-demand-sync-2026-10-06.md) |
| UI continuity and initial speculation gate | [Safety/continuity audit, 6 October](precomputed-next-day-safety-and-ui-continuity-2026-10-06.md) |
| Retail coupling and renewed speculation gate | [Coupling audit](retail-investor-coupling-audit-2026-10-06.md), [implementation and decision](retail-investor-decoupling-and-precompute-2026-10-06.md) |
| Targeted native performance | [Final performance pass, 6 October](final-maximum-performance-squeeze-2026-10-06.md) |
| Persistence ownership and recovery | [Flush remediation, 6 October](final-duckdb-flush-remediation-2026-10-06.md) |
| Initial roots and index repair | [Genesis audit, 7 October](genesis-initialization-and-country-index-audit-2026-10-07.md), [field inventory](genesis-initialization-field-inventory-2026-10-07.md) |
| Diverse Day-1 world | [Heterogeneous implementation, 7 October](heterogeneous-start-world-implementation-2026-10-07.md) |
| Population and labor model | [Audit](workforce-population-audit-2026-10-07.md), [sector inventory](workforce-sector-inventory-2026-10-07.md), [implementation](workforce-birth-rate-implementation-2026-10-07.md) |
| Politics and selected country UI | [Audit](politics-stability-society-ui-audit-2026-10-07.md), [implementation](politics-v1-society-politics-implementation-2026-10-07.md), [capture record](politics-v1-ui-captures-2026-10-07.md) |
| Earlier packaging/checkpoint baseline | [Release report, 28 September](release-readiness-2026-09-28.md) |

## Deliberate limits

Synthetic uncalibrated economics; simplified financial products; no fees/taxes/
slippage; aggregate workforce without cohorts/wages/migration; compact descriptive
politics; disabled political bond premium and speculation; no separate housing
market; no release-approved frozen executable. Established is coarse history plus
daily burn-in. Native parallel yearly averages retain a floating-point ordering
limit. Version-dependent continuation and paired checkpoint/history remain required.

These limits define the completed portfolio scope. Future development can resume
without describing an optional idea as an unfinished release requirement.
