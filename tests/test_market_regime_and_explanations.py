from __future__ import annotations

from types import SimpleNamespace

import pytest

from kojakstreet.core.accounting import _owned_bond_market_value
from kojakstreet.core.label_codes import attach_stable_label_codes, stable_label_code
from kojakstreet.core.market_explanations import driver_summary, explain_asset_move
from kojakstreet.core.market_regime import classify_market_regime, update_market_regime
from kojakstreet.core.trade_preview import build_trade_preview


def test_stable_label_codes_normalize_mojibake_variants() -> None:
    assert stable_label_code("Öl und Gas", category="sector") == "OIL_GAS"
    assert stable_label_code("Ã–l und Gas", category="sector") == "OIL_GAS"

    state = SimpleNamespace(
        aktien={"AAA": {"branche": "Öl und Gas"}},
        rohstoffe={"CL": {"kategorie": "EnergietrÃ¤ger"}},
        fonds={},
        indizes={},
    )
    attach_stable_label_codes(state)
    assert state.aktien["AAA"]["sector_code"] == "OIL_GAS"
    assert state.rohstoffe["CL"]["group_code"] == "ENERGY_COMMODITIES"


def test_market_regime_writes_global_macro_snapshot() -> None:
    state = SimpleNamespace(
        makro={
            "A": {"bip_prozent": -0.02, "inflation": 0.08, "zins": 0.07, "arbeitslosigkeit": 0.09, "debt_to_gdp": 0.95},
            "B": {"bip_prozent": -0.01, "inflation": 0.07, "zins": 0.06, "arbeitslosigkeit": 0.08, "debt_to_gdp": 0.90},
        },
        global_macro={"yield_curve_3y10y": -0.01, "vix": 30.0, "net_liquidity": 82000.0},
    )
    regime = update_market_regime(state)
    assert regime.name in {"Credit Stress", "Stagflation"}
    assert state.market_regime == regime.name
    assert "market_regime" not in state.global_macro
    assert classify_market_regime(state).credit_stress > 0.0


def test_asset_explanation_surfaces_driver_text() -> None:
    asset = {
        "aenderung": 1.2,
        "revenue_growth": 0.04,
        "fcf_margin": 0.12,
        "kurs": 100.0,
        "eps": 5.0,
        "fund_flow_pressure": 0.002,
    }
    drivers = explain_asset_move(asset, "Stock")
    assert drivers
    assert "Last move" not in {driver.label for driver in drivers}
    assert "Positioning" not in {driver.label for driver in drivers}
    assert "Fund/ETF Flows" in {driver.label for driver in drivers}
    assert "P/E" in driver_summary(asset, "Stock")
    assert "pressure" in driver_summary(asset, "Stock")


def test_trade_preview_exposes_cds_contract_size() -> None:
    state = SimpleNamespace(
        assets=None,
        aktien={},
        rohstoffe={},
        kryptos={},
        fonds={},
        derivatives={
            "CDS": {
                "kurs": 25.0,
                "land": "GD",
                "instrument_type": "Credit Default Swap",
                "notional": 10_000_000.0,
                "recovery_rate": 0.40,
            }
        },
        waehrungen_staerke={"GD": 1.0},
    )
    preview = build_trade_preview(state, "CDS", "BUY", 2.0)
    assert preview.contract_size == 1000.0
    assert preview.payout_hint == pytest.approx(1200.0)


def test_owned_bond_market_value_prefers_market_price() -> None:
    state = SimpleNamespace(bond_market_by_symbol={"BOND": {"price": 92.5}})
    assert _owned_bond_market_value(state, {"nominal": 1000.0, "symbol": "BOND"}) == 925.0
    assert _owned_bond_market_value(state, {"nominal": 1000.0}) == 1000.0
