"""Numerical state survives serialization; live object references do not."""
from datetime import datetime
from types import SimpleNamespace

import pytest

from kojakstreet.core.checkpoints import capture, decode, encode, restore
from kojakstreet.core.funds import _fund_daily_return, _resolved_underlyings
from kojakstreet.core.market_calculations import _asset_ema_diff


def world():
    stock = {
        "kurs": 100.0,
        "aenderung": 1.0,
        "historie": [(100.0 + day % 37, f"day-{day}", "") for day in range(520)],
    }
    fund = {
        "underlyings": [{"asset_type": "Stock", "ticker": "A", "weight": 1.0}],
        "historie": [(100.0 + day / 10, f"day-{day}", "") for day in range(1040)],
    }
    _asset_ema_diff(stock, 180)
    _resolved_underlyings(fund, {("Stock", "A"): stock})
    fund["_fund_pressure_targets"] = [("Stock", "A", stock, 1.0, ())]
    return SimpleNamespace(
        datum=datetime(1990, 1, 1), aktien={"A": stock}, fonds={"F": fund},
        rohstoffe={}, kryptos={}, makro={}, depot={}, forex_depot={"GD": 25000.0},
        bargeld=0.0,
    )


def test_checkpoint_preserves_long_computational_history_and_next_ema():
    original = world()
    payload = decode(encode(capture(original)))
    assert payload["checkpoint"]["aktien"]["A"] == original.aktien["A"]
    assert payload["checkpoint"]["fonds"]["F"]["historie"] == original.fonds["F"]["historie"]
    assert "_resolved_underlyings" not in payload["checkpoint"]["fonds"]["F"]
    assert "_fund_pressure_targets" not in payload["checkpoint"]["fonds"]["F"]
    restored = SimpleNamespace()
    restore(restored, payload)
    for stock in (original.aktien["A"], restored.aktien["A"]):
        stock["historie"].append((150.0, "next-day", ""))
        del stock["historie"][:-520]
    assert _asset_ema_diff(restored.aktien["A"], 180) == _asset_ema_diff(original.aktien["A"], 180)
    assert restored.aktien["A"] == original.aktien["A"]


@pytest.mark.parametrize("version", [4, 5, 6])
def test_restore_rebinds_fund_returns_to_live_assets_even_for_old_cached_saves(version):
    original = world()
    payload = capture(original)
    payload["save_version"] = version
    # Reproduce old writers: JSON expands the live references into asset copies.
    payload["checkpoint"]["fonds"]["F"]["_resolved_underlyings"] = original.fonds["F"]["_resolved_underlyings"]
    payload["checkpoint"]["fonds"]["F"]["_fund_pressure_targets"] = original.fonds["F"]["_fund_pressure_targets"]
    restored = SimpleNamespace()
    restore(restored, decode(encode(payload)))
    fund = restored.fonds["F"]
    assert "_resolved_underlyings" not in fund
    assert "_fund_pressure_targets" not in fund
    restored.aktien["A"]["aenderung"] = 4.0
    cache = {("Stock", "A"): restored.aktien["A"]}
    assert _fund_daily_return(fund, cache) == 0.04
    assert fund["_resolved_underlyings"][0][1] is restored.aktien["A"]


def test_checkpoint_bounds_only_display_topology_history():
    original = world()
    samples = [(float(day), f"day-{day}") for day in range(900)]
    original.aktien["A"]["company_input_history"] = {"steel": samples}
    original.aktien["A"]["company_output_history"] = samples
    original.makro["regional_history"] = {"EU": {"demand": samples}}
    payload = capture(original)["checkpoint"]
    assert payload["aktien"]["A"]["company_input_history"]["steel"] == samples[-2:]
    assert payload["aktien"]["A"]["company_output_history"] == samples[-2:]
    assert payload["makro"]["regional_history"]["EU"]["demand"] == samples[-2:]
    assert len(original.aktien["A"]["company_input_history"]["steel"]) == 900
    assert payload["aktien"]["A"]["historie"] == original.aktien["A"]["historie"]
