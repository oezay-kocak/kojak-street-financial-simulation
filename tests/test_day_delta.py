import json
from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from kojakstreet.core.state import GameState
from kojakstreet.day_delta import (
    DayStateEncoder,
    apply_day_delta,
    prepare_day_delta,
    public_copy,
    state_values,
)


def initial_state():
    return GameState(
        date=datetime(1990, 1, 1),  # noqa: DTZ001 - legacy game calendar is timezone-free
        cash=100.0,
        display_currency="GD",
        stocks={
            "A": {
                "kurs": 10.0,
                "revenue": 1000.0,
                "historie": [
                    (float(i), f"1990-01-{i + 1:02}", "", 1.0, 20.0, 0.0) for i in range(20)
                ],
                "company_input_history": {"ELC": {"history": [(1.0, "1990-01-01", "")]}},
                "_ema_cache": {"value": 123.0},
            }
        },
        macro={"Ameron": {"regional_history": {"ELC": {"produced": [(1.0, "1990-01-01")]}}}},
        bond_market=[{"symbol": "B1", "price": 99.0, "historie": [(99.0, "1990-01-01", "")]}],
        forex_history={"A/GD": [(1.0, "1990-01-01", "")]},
    )


def test_delta_roundtrip_is_exact_for_all_public_fields_and_preserves_live_references():
    source = initial_state()
    receiver = GameState(**public_copy(state_values(source)))
    encoder = DayStateEncoder(source)
    revision = 0
    reference = receiver.stocks["A"]
    for day in range(30):
        source.date += timedelta(days=1)
        source.stocks["A"]["historie"].append(
            (day + 0.5, source.date.isoformat(), "", day, day + 1.0, day - 1.0)
        )
        source.stocks["A"]["historie"] = source.stocks["A"]["historie"][-20:]
        source.stocks["A"]["revenue"] += 0.25
        source.stocks["A"]["company_input_history"]["ELC"]["history"].append((day, str(day), ""))
        source.macro["Ameron"]["regional_history"]["ELC"]["produced"].append((day, str(day)))
        source.forex_history["A/GD"].append((day, str(day), ""))
        source.bond_market[0]["price"] += 0.01
        source.bond_market[0]["historie"].append((day, str(day), ""))
        # The transport is real JSON, including checkpoint tuple/datetime tags.
        payload = json.loads(json.dumps(encoder.update(source)))
        revision = apply_day_delta(receiver, payload, revision)
        assert state_values(receiver) == public_copy(state_values(source))
        assert receiver.stocks["A"] is reference
        assert "_ema_cache" not in receiver.stocks["A"]


def test_delta_handles_backdated_mutable_points_deletions_and_entity_topology():
    source = initial_state()
    encoder = DayStateEncoder(source)
    receiver = GameState(**public_copy(state_values(source)))
    source.stocks["A"]["historie"][1] = {"date": "1989-01-01", "close": 5.0}
    source.stocks["A"]["historie"].reverse()
    source.stocks["B"] = {"kurs": 20.0, "historie": [(20.0, "1990-01-01", "")]}
    del source.stocks["A"]["revenue"]
    source.bond_market.append(
        {"symbol": "B2", "price": 80.0, "historie": [(80.0, "1990-01-01", "")]}
    )
    source.portfolio["B"] = {"quantity": 2.0}
    revision = apply_day_delta(receiver, json.loads(json.dumps(encoder.update(source))), 0)
    assert state_values(receiver) == public_copy(state_values(source))
    source.stocks["A"]["historie"][-2]["close"] = 7.0
    source.bond_market.pop(0)
    del source.stocks["B"]
    source.portfolio.clear()
    apply_day_delta(receiver, json.loads(json.dumps(encoder.update(source))), revision)
    assert state_values(receiver) == public_copy(state_values(source))


def test_unchanged_history_is_not_transmitted_and_new_day_contains_only_new_points():
    source = initial_state()
    source.stocks["A"]["historie"] = [(float(i), str(i), "") for i in range(5000)]
    encoder = DayStateEncoder(source)
    assert encoder.update(source)["changes"] == []
    source.stocks["A"]["historie"].append((5001.0, "new", ""))
    text = json.dumps(encoder.update(source))
    assert len(text) < 350
    assert "4999" not in text


def test_wrong_revision_and_unknown_contract_fail_without_a_full_snapshot_fallback():
    source = initial_state()
    receiver = deepcopy(source)
    payload = DayStateEncoder(source).update(source)
    with pytest.raises(ValueError, match="revision"):
        apply_day_delta(receiver, payload, 10)
    payload["version"] = 999
    with pytest.raises(ValueError, match="version"):
        apply_day_delta(receiver, payload, 0)


def test_large_delta_retains_tuples_datetimes_and_all_history_points():
    source = initial_state()
    source.stocks = {
        str(i): {"kurs": float(i), "historie": [(float(i), source.date, "")]} for i in range(600)
    }
    receiver = GameState(**public_copy(state_values(source)))
    encoder = DayStateEncoder(source)
    source.date += timedelta(days=5)
    for asset in source.stocks.values():
        asset["kurs"] += 0.25
        asset["historie"].extend(
            [(asset["kurs"], source.date - timedelta(days=i), "") for i in range(5)]
        )
    payload = json.loads(json.dumps(encoder.update(source)))
    assert payload["codec"] == "data-pickle5-zlib1"
    apply_day_delta(receiver, prepare_day_delta(payload), 0)
    assert state_values(receiver) == public_copy(state_values(source))


def test_binary_transport_cannot_load_python_classes_or_functions():
    import base64
    import pickle
    import zlib

    payload = {
        "codec": "data-pickle5-zlib1",
        "changes": base64.b64encode(zlib.compress(pickle.dumps(eval, protocol=5))).decode("ascii"),
    }
    with pytest.raises(pickle.UnpicklingError, match="cannot instantiate"):
        prepare_day_delta(payload)


@pytest.mark.parametrize("enabled", [True, False])
def test_encoder_restores_gc_policy_after_success_and_failure(enabled, monkeypatch):
    import gc

    original = gc.isenabled()
    source = initial_state()
    encoder = DayStateEncoder(source)
    try:
        (gc.enable if enabled else gc.disable)()
        source.stocks["A"]["kurs"] += 1
        assert encoder.update(source)["revision"] == 1
        assert gc.isenabled() is enabled

        def fail(*args):
            raise RuntimeError("injected comparison failure")
        monkeypatch.setattr(encoder, "_mapping", fail)
        with pytest.raises(RuntimeError, match="comparison failure"):
            encoder.update(source)
        assert gc.isenabled() is enabled
    finally:
        (gc.enable if original else gc.disable)()
