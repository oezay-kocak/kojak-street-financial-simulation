from __future__ import annotations

from types import SimpleNamespace

import pytest

from kojakstreet.core.expectations import record_macro_report, update_daily_expectations


def test_crisis_event_is_priced_into_expectations_before_macro_report() -> None:
    daten = SimpleNamespace(
        aktives_event={
            "name": "GENERAL STRIKE & CIVIL UNREST",
            "typ": "NATIONAL",
            "laender": ["ALB"],
            "bip_makel": -0.035,
        },
        makro={
            "ALB": {
                "bip_prozent": 0.015,
                "inflation": 0.02,
                "arbeitslosigkeit": 0.06,
                "zins": 0.035,
                "expected_growth": 0.015,
                "expected_inflation": 0.02,
                "expected_unemployment": 0.06,
                "expected_rate": 0.035,
            }
        },
    )

    for _day in range(30):
        update_daily_expectations(daten)

    macro = daten.makro["ALB"]
    assert macro["expected_growth"] < -0.002
    assert macro["expected_inflation"] > 0.026
    assert macro["expected_unemployment"] > 0.070


def test_macro_report_surprise_is_small_when_crisis_was_expected() -> None:
    daten = SimpleNamespace(
        aktives_event=None,
        makro={
            "ALB": {
                "bip_prozent": -0.020,
                "inflation": 0.035,
                "arbeitslosigkeit": 0.085,
                "zins": 0.035,
                "expected_growth": -0.018,
                "expected_inflation": 0.034,
                "expected_unemployment": 0.083,
                "expected_rate": 0.035,
            }
        },
    )

    record_macro_report(daten, ["ALB"])

    macro = daten.makro["ALB"]
    assert macro["growth_surprise"] == pytest.approx(-0.002)
    assert abs(macro["macro_surprise_momentum"]) < 0.015
