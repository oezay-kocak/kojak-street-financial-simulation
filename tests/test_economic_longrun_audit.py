from __future__ import annotations

import math
from types import SimpleNamespace

from tools.economic_longrun_audit import pearson, summarize
from tools.economic_shock_probe import oil_supply_shock, policy_rate_shock


def test_summarize_reports_distribution_and_ignores_nonfinite_values() -> None:
    result = summarize([1.0, 2.0, 3.0, float("nan"), float("inf")])

    assert result["n"] == 3
    assert result["min"] == 1.0
    assert result["median"] == 2.0
    assert result["max"] == 3.0
    assert result["mean"] == 2.0


def test_pearson_handles_direction_and_constant_series() -> None:
    assert math.isclose(pearson([1, 2, 3], [2, 4, 6]) or 0.0, 1.0)
    assert math.isclose(pearson([1, 2, 3], [6, 4, 2]) or 0.0, -1.0)
    assert pearson([1, 1, 1], [2, 3, 4]) is None


def test_diagnostic_shocks_mutate_only_the_requested_state() -> None:
    state = SimpleNamespace(
        rohstoffe={"CL": {"supply": 100.0, "production": 80.0, "inventories": 40.0}},
        makro={"A": {"zins": 0.02}, "B": {"zins": 0.08}},
    )

    oil_supply_shock(state)
    policy_rate_shock(state)

    assert state.rohstoffe["CL"] == {"supply": 50.0, "production": 40.0, "inventories": 20.0}
    assert state.makro["A"]["zins"] == 0.05
    assert state.makro["B"]["zins"] == 0.095
