"""Membership indexing preserves ties while scoring live, replaceable assets."""
from types import SimpleNamespace

from kojakstreet.core.funds import _equity_candidate_groups, _equity_underlyings


def test_fund_groups_match_full_scan_and_keep_live_scores():
    world = SimpleNamespace(aktien={
        "A1": {"land": "A", "branche": "Energy", "market_cap": 100.0},
        "B1": {"land": "B", "branche": "Energy", "market_cap": 100.0},
        "A2": {"land": "A", "branche": "Energy", "market_cap": 100.0},
        "A3": {"land": "A", "branche": "Finance", "market_cap": 50.0},
        "OTHER": {"land": None, "branche": 7, "market_cap": 200.0},
    })
    mandates = [
        {"fund_type": kind, "ziel": country, "branche": branch, "strategy": strategy}
        for kind in ("Country Fund", "Sector Fund", "Global Sector Fund", "World Fund")
        for country in ("A", "missing") for branch in ("Energy", "missing")
        for strategy in ("Small Cap", "Growth", "Dividend", "Value", "Equity")
    ]
    groups = _equity_candidate_groups(world)
    for fund in mandates:
        assert _equity_underlyings(world, fund, groups) == _equity_underlyings(world, fund)
    fund = {"fund_type": "Sector Fund", "ziel": "A", "branche": "Energy"}
    assert [row["ticker"] for row in _equity_underlyings(world, fund, groups)] == ["A1", "A2"]
    world.aktien["A2"]["market_cap"] = 300.0
    assert [row["ticker"] for row in _equity_underlyings(world, fund, groups)] == ["A2", "A1"]
    world.aktien = {"NEW": {"land": "A", "branche": "Energy", "market_cap": 100.0}}
    assert _equity_underlyings(world, fund, _equity_candidate_groups(world)) == [
        {"ticker": "NEW", "asset_type": "Stock", "weight": 1.0},
    ]
