from __future__ import annotations

import math
from pathlib import Path

import pytest

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.fast_history import generate_coarse_history


def test_coarse_history_handoff_is_consistent_and_survives_first_report(tmp_path) -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1], data_dir=tmp_path / "runtime", seed=20260922)
    try:
        generate_coarse_history(runtime, 20260922, 25, burn_in_days=30)

        current = {str(row["region"]): row for row in runtime.country_current_rows()}
        for region, macro in runtime.daten.makro.items():
            row = current[region]
            assert row["gdp"] == pytest.approx(float(macro["bip_abs"]))
            assert row["growth"] == pytest.approx(float(macro["bip_prozent"]))
            assert row["inflation"] == pytest.approx(float(macro["inflation"]))
            assert row["rate"] == pytest.approx(float(macro["zins"]))
            assert row["unemployment"] == pytest.approx(float(macro["arbeitslosigkeit"]))
            assert row["debt_to_gdp"] == pytest.approx(float(macro["debt_to_gdp"]))
            assert row["balance_sheet"] == pytest.approx(float(macro["balance_sheet"]))
            assert row["credit_growth"] == pytest.approx(float(macro["credit_growth"]))
            assert row["rating"] == macro["rating"]

        fund_ticker, fund = next(iter(runtime.daten.fonds.items()))
        fund_points = runtime.data_store.history_series(
            "asset_daily",
            "ticker",
            f"Fund:{fund_ticker}",
            "price",
            pixel_budget=1200,
            semantic_type="price",
        )
        assert len({round(float(point["value"]), 6) for point in fund_points}) > 3
        assert float(fund_points[-1]["value"]) == pytest.approx(float(fund["kurs"]))
        assert all(math.isfinite(float(point["value"])) and float(point["value"]) > 0.0 for point in fund_points)

        index_caps = [round(float(index["market_cap"]), 2) for index in runtime.daten.indizes.values()]
        assert len(set(index_caps)) > 10
        for ticker, index in list(runtime.daten.indizes.items())[:20]:
            points = runtime.data_store.history_series(
                "asset_daily",
                "ticker",
                f"Index:{ticker}",
                "price",
                pixel_budget=1200,
                semantic_type="price",
            )
            assert float(points[-1]["value"]) == pytest.approx(float(index["kurs"]))
            if len(points) > 1:
                assert float(points[1]["value"]) / max(0.01, float(points[0]["value"])) < 5.0

        first_day_max = None
        first_report_max = None
        maximum_transition_return = 0.0
        for _ in range(30):
            report_day = runtime.daten.datum.day == 15
            runtime.advance_day()
            daily_max = max(abs(float(asset.get("aenderung", 0.0))) for asset in runtime.daten.aktien.values())
            maximum_transition_return = max(maximum_transition_return, daily_max)
            if first_day_max is None:
                first_day_max = daily_max
            if report_day and first_report_max is None:
                first_report_max = daily_max

        assert first_day_max is not None and first_day_max < 25.0
        assert first_report_max is not None and first_report_max < 100.0
        assert maximum_transition_return < 100.0
        assert all(
            math.isfinite(float(asset["kurs"]))
            and float(asset["kurs"]) > 0.0
            and math.isfinite(float(asset.get("expectation", 0.0)))
            and math.isfinite(float(asset.get("surprise", 0.0)))
            for asset in runtime.daten.aktien.values()
        )
        assert all(math.isfinite(float(index["kurs"])) and float(index["kurs"]) > 0.0 for index in runtime.daten.indizes.values())
    finally:
        runtime.close()
