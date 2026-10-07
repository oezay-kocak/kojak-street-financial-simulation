"""The retained sequential publication path must preserve actions and saves exactly."""

import random
from pathlib import Path

import numpy as np
import pytest

import daten
from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import capture, encode
from kojakstreet.live_process import economic_signature
from kojakstreet.live_worker import _execute


@pytest.fixture
def preserve_legacy_world():
    # Runtime construction replaces the shared module's world. Keep the prior
    # objects intact so this action regression cannot contaminate later tests.
    namespace = dict(vars(daten))
    python_rng = random.getstate()
    numpy_rng = np.random.get_state()
    try:
        yield
    finally:
        for key in set(vars(daten)) - set(namespace):
            delattr(daten, key)
        vars(daten).update(namespace)
        random.setstate(python_rng)
        np.random.set_state(numpy_rng)


def test_actions_immediately_before_day_pause_resume_and_save_replay_match_sequential(
    tmp_path, preserve_legacy_world
):
    import hashlib
    import json

    def checkpoint_digest(runtime):
        return hashlib.sha256(
            json.dumps(encode(capture(runtime.daten)), sort_keys=True).encode()
        ).hexdigest()

    outputs = []
    root = Path(__file__).resolve().parents[1]
    for worker in (False, True):
        runtime = IntegratedRuntime(
            root, data_dir=tmp_path / ("worker" if worker else "sequential"), seed=1729
        )
        try:
            stock = next(
                ticker for ticker in runtime.daten.aktien if ticker not in runtime.daten.indizes
            )
            crypto = next(iter(runtime.daten.kryptos))
            option = next(
                ticker
                for ticker, asset in runtime.daten.derivatives.items()
                if asset.get("instrument_type") == "Option"
            )
            schedule = {
                1: ("trade_spot", {"ticker": stock, "quantity": 2, "side": "BUY"}),
                3: (
                    "trade_future",
                    {"ticker": stock, "direction": "LONG", "leverage": 2, "margin": 100},
                ),
                5: (
                    "trade_future",
                    {"ticker": crypto, "direction": "SHORT", "leverage": 2, "margin": 100},
                ),
                7: (
                    "exchange_currency",
                    {"source_region": "GD", "target_region": "Ameron", "amount": 10},
                ),
                8: ("close_future", {"position_id": f"{crypto}_SHORT"}),
                10: ("trade_spot", {"ticker": option, "quantity": 1, "side": "BUY"}),
                12: ("trade_spot", {"ticker": stock, "quantity": 1, "side": "SELL"}),
                14: ("trade_spot", {"ticker": crypto, "quantity": 1, "side": "BUY"}),
                15: ("trade_spot", {"ticker": crypto, "quantity": 1, "side": "SELL"}),
            }
            signatures = []
            for day in range(1, 21):
                scope = {
                    "view": "markets",
                    "selection": {
                        "kind": "Stock",
                        "ticker": stock,
                        "tab": ("chart", "overview", "supply")[day % 3],
                    },
                }
                _execute(runtime, "set_running", {"running": False})
                date = runtime.daten.datum
                _execute(runtime, "visible", {"scope": scope})
                assert runtime.daten.datum == date
                if day in schedule:
                    command, arguments = schedule[day]
                    _execute(runtime, command, arguments)
                    assert runtime.daten.datum == date
                _execute(runtime, "set_running", {"running": True})
                if worker:
                    _execute(runtime, "advance", {"steps": 1, "scope": scope})
                else:
                    runtime.advance_day()
                _execute(runtime, "set_running", {"running": False})
                signatures.append(economic_signature(runtime.daten))
                if day == 9:
                    _execute(runtime, "save", {})
                    saved = checkpoint_digest(runtime)
                    _execute(runtime, "advance", {"steps": 1, "scope": scope})
                    future = economic_signature(runtime.daten)
                    _execute(runtime, "load", {})
                    assert checkpoint_digest(runtime) == saved
                    _execute(runtime, "advance", {"steps": 1, "scope": scope})
                    assert economic_signature(runtime.daten) == future
                    _execute(runtime, "load", {})
            outputs.append((signatures, checkpoint_digest(runtime)))
        finally:
            runtime.close()
    assert outputs[0] == outputs[1]
