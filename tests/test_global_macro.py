from __future__ import annotations

import math
from datetime import date
from types import SimpleNamespace

import daten
from kojakstreet.core.global_macro import ensure_global_macro, update_global_macro


def test_global_macro_tracks_3y_5y_10y_and_curve_spread() -> None:
    ensure_global_macro(daten)
    update_global_macro(daten)

    macro = daten.global_macro

    assert "avg_3y_yield" in macro
    assert "avg_5y_yield" in macro
    assert "avg_10y_yield" in macro
    assert macro["avg_5y_yield"] > macro["avg_3y_yield"]
    assert macro["avg_10y_yield"] > macro["avg_5y_yield"]
    assert math.isclose(
        macro["yield_curve_3y10y"],
        macro["avg_10y_yield"] - macro["avg_3y_yield"],
        abs_tol=1e-12,
    )


def test_global_macro_uses_observed_government_bond_yields() -> None:
    state = SimpleNamespace(
        datum=date(2026, 1, 1),
        LAENDER=["Ameron"],
        makro={
            "Ameron": {
                "zins": 0.03,
                "bip_prozent": 0.012,
                "inflation": 0.021,
                "arbeitslosigkeit": 0.055,
                "bip_abs": 1_000.0,
                "balance_sheet": 200.0,
            }
        },
        bond_market=[
            {"issuer_type": "Government", "maturity_years": 3.0, "yield_to_maturity": 0.031},
            {"issuer_type": "Government", "maturity_years": 5.0, "yield_to_maturity": 0.041},
            {"issuer_type": "Government", "maturity_years": 10.0, "yield_to_maturity": 0.054},
            {"issuer_type": "Corporate", "maturity_years": 10.0, "yield_to_maturity": 0.09},
        ],
        aktien={},
        kryptos={},
        fonds={},
        indizes={},
    )

    ensure_global_macro(state)
    update_global_macro(state)

    assert state.global_macro["avg_3y_yield"] < state.global_macro["avg_5y_yield"]
    assert state.global_macro["avg_10y_yield"] > state.global_macro["avg_5y_yield"]
    assert state.global_macro["avg_10y_yield"] < 0.06
