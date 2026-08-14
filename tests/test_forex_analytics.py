from __future__ import annotations

import daten
from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.countries import CURRENCY_CODES, RESERVE_CURRENCY_CODE
from kojakstreet.core.forex import build_forex_pairs


def test_forex_pairs_build_rates_without_btc_pairs_by_default() -> None:
    state = snapshot_from_legacy(daten)

    pairs = build_forex_pairs(state)

    assert pairs
    assert all("BTC" not in pair.pair for pair in pairs)
    first_code, second_code = list(CURRENCY_CODES.values())[:2]
    assert any(pair.pair == f"{first_code}/{second_code}" for pair in pairs)
    assert any(pair.pair == f"{first_code}/{RESERVE_CURRENCY_CODE}" for pair in pairs)


def test_fresh_forex_pairs_have_spot_rates_without_startup_history() -> None:
    state = snapshot_from_legacy(daten)

    pairs = build_forex_pairs(state)

    assert all(not history for history in state.forex_history.values())
    assert pairs
    assert all(pair.history == [] for pair in pairs)
    assert {pair.rate for pair in pairs} == {1.0}
    assert all(pair.change_percent == 0.0 for pair in pairs)
