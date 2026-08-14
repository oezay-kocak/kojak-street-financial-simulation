from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from kojakstreet.core.accounting import asset_price, asset_region
from kojakstreet.core.simulation_state import SimulationState


def test_simulation_state_wraps_legacy_data_with_typed_repositories() -> None:
    legacy = SimpleNamespace(
        datum=datetime(1990, 1, 1),
        SPIEL_AKTIV=True,
        spiel_pausiert=False,
        aktien={"AAA": {"kurs": 42.0, "land": "Ameron"}},
        rohstoffe={"XAU": {"kurs": 100.0}},
        kryptos={},
        fonds={},
        indizes={},
        depot={},
        perpetuals={},
        forex_depot={"GD": 1000.0},
        kredite={},
        anleihen=[],
        makro={"Ameron": {"zins": 0.04}},
        LAENDER={"Ameron": "AM"},
        waehrungen_staerke={"Ameron": 1.0},
    )

    state = SimulationState.from_legacy(legacy)

    assert state.assets.price("AAA") == 42.0
    assert state.assets.region("AAA") == "Ameron"
    assert state.portfolio.fx_balances["GD"] == 1000.0
    assert list(state.macro.country_names()) == ["Ameron"]
    assert asset_price(state, "AAA") == 42.0
    assert asset_region(state, "AAA") == "Ameron"

    state.is_paused = True
    state.mark_completed_today()
    state.advance_one_day()

    assert legacy.spiel_pausiert is True
    assert legacy.last_completed_simulation_date == datetime(1990, 1, 1)
    assert legacy.datum == datetime(1990, 1, 2)
