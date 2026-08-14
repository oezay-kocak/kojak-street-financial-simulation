from __future__ import annotations

from types import SimpleNamespace

from kojakstreet.core.bond_portfolio_details import owned_bond_details
from kojakstreet.core.funds import _credit_issuer_fees, _expense_ratio, _fund_daily_return


def test_owned_bond_details_uses_market_price_rating_and_duration() -> None:
    state = SimpleNamespace(
        bonds=[{"symbol": "B1", "nominal": 1_000.0, "resttage": 365.0}],
        bond_market=[
            {
                "symbol": "B1",
                "issuer": "Issuer",
                "region": "USA",
                "price": 95.0,
                "coupon": 0.04,
                "duration": 0.9,
                "yield_to_maturity": 0.055,
                "rating": "BBB",
            }
        ],
    )

    [detail] = owned_bond_details(state)

    assert detail.market_value == 950.0
    assert detail.duration == 0.9
    assert detail.yield_to_maturity == 0.055
    assert detail.default_risk > 0.0


def test_fund_returns_and_issuer_income_have_no_asset_fee_effect() -> None:
    fund = {
        "expense_ratio": 0.50,
        "cash_allocation": 0.0,
        "underlyings": [{"asset_type": "Stock", "ticker": "AAA", "weight": 1.0}],
    }
    asset_cache = {("Stock", "AAA"): {"aenderung": 1.0}}
    state = SimpleNamespace(aktien={"BANK": {"revenue": 100.0, "free_cash_flow": 10.0}})

    assert _expense_ratio("ETF") == 0.0
    assert _fund_daily_return(fund, asset_cache) == 0.01
    _credit_issuer_fees(state, {"issuer": "BANK", "aum": 1_000_000.0, "expense_ratio": 0.50})
    assert state.aktien["BANK"] == {"revenue": 100.0, "free_cash_flow": 10.0}
