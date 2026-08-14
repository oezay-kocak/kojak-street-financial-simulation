from __future__ import annotations

from pathlib import Path
from statistics import mean

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime

DAILY_PRODUCTION_BUDGET_MS = 120.0
DAILY_ASSET_MARKET_BUDGET_MS = 90.0
DAILY_BOND_MARKET_BUDGET_MS = 35.0
MONTHLY_PRODUCTION_BUDGET_MS = 140.0
MONTHLY_COMPANIES_BUDGET_MS = 70.0
MONTHLY_ASSET_MARKET_BUDGET_MS = 115.0


def test_daily_runtime_stays_inside_interactive_budget() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    phase_totals: dict[str, list[float]] = {}
    try:
        for _ in range(12):
            runtime.advance_day()
            for item in getattr(runtime.daten, "simulation_phase_timings", []):
                phase_totals.setdefault(str(item["phase"]), []).append(float(item["duration_ms"]))
    finally:
        runtime.close()

    assert mean(phase_totals["daily_production"]) < DAILY_PRODUCTION_BUDGET_MS
    assert mean(phase_totals["asset_market"]) < DAILY_ASSET_MARKET_BUDGET_MS
    assert mean(phase_totals["bond_market"]) < DAILY_BOND_MARKET_BUDGET_MS


def test_monthly_runtime_phases_stay_inside_interactive_budget() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    phase_totals: dict[str, list[float]] = {}
    try:
        for _ in range(40):
            runtime.advance_day()
            for item in getattr(runtime.daten, "simulation_phase_timings", []):
                phase_totals.setdefault(str(item["phase"]), []).append(float(item["duration_ms"]))
    finally:
        runtime.close()

    if "monthly_production" in phase_totals:
        assert mean(phase_totals["monthly_production"]) < MONTHLY_PRODUCTION_BUDGET_MS
    if "monthly_companies" in phase_totals:
        assert mean(phase_totals["monthly_companies"]) < MONTHLY_COMPANIES_BUDGET_MS
    if "monthly_asset_market" in phase_totals:
        assert mean(phase_totals["monthly_asset_market"]) < MONTHLY_ASSET_MARKET_BUDGET_MS


def test_current_rows_are_cached_between_simulation_days() -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1])
    try:
        version = runtime.current_version()
        first_quotes = runtime.asset_quote_rows()
        second_quotes = runtime.asset_quote_rows()
        first_tape = runtime.ticker_tape_quotes()
        second_tape = runtime.ticker_tape_quotes()

        assert first_quotes is second_quotes
        assert first_tape is second_tape
        assert runtime.current_version() == version

        runtime.advance_day()

        assert runtime.current_version() > version
        assert runtime.asset_quote_rows() is not first_quotes
    finally:
        runtime.close()
