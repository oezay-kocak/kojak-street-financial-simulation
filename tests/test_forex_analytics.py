from __future__ import annotations

from pathlib import Path

import pytest

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.countries import CURRENCY_CODES, RESERVE_CURRENCY_CODE
from kojakstreet.core.forex import build_forex_pairs


@pytest.fixture
def fresh_state(tmp_path):
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1], data_dir=tmp_path, seed=1729)
    try:
        yield runtime.snapshot()
    finally:
        runtime.close()


def test_forex_pairs_build_rates_without_btc_pairs_by_default(fresh_state) -> None:
    state = fresh_state

    pairs = build_forex_pairs(state)

    assert pairs
    assert all("BTC" not in pair.pair for pair in pairs)
    first_code, second_code = list(CURRENCY_CODES.values())[:2]
    assert any(pair.pair == f"{first_code}/{second_code}" for pair in pairs)
    assert any(pair.pair == f"{first_code}/{RESERVE_CURRENCY_CODE}" for pair in pairs)


def test_fresh_forex_pairs_have_spot_rates_without_startup_history(fresh_state) -> None:
    state = fresh_state

    pairs = build_forex_pairs(state)

    assert all(not history for history in state.forex_history.values())
    assert pairs
    assert all(pair.history == [] for pair in pairs)
    assert {pair.rate for pair in pairs} == {1.0}
    assert all(pair.change_percent == 0.0 for pair in pairs)
