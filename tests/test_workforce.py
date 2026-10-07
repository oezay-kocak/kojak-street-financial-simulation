"""Feature roots, bounded economics, time integration and durable boundaries."""
import math
import random
import subprocess
import sys
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from kojakstreet.core import workforce as wf
from kojakstreet.core.checkpoints import atomic_write, capture, encode, restore
from kojakstreet.core.countries import COUNTRY_SYMBOLS
from kojakstreet.core.fast_history import _rebaseline_handoff_state
from kojakstreet.core.persistence_writer import RowBatch, RowJournal

ROOT = Path(__file__).resolve().parents[1]


def world(capacity=1000, population=20_000_000):
    return SimpleNamespace(datum=datetime(1990, 1, 1), makro={"Ameron": {  # noqa: DTZ001 -- simulation calendar
        "bevoelkerung": population, "population_growth": .001,
        "bip_prozent": .01, "arbeitslosigkeit": .06,
    }}, aktien={"A": {"land": "Ameron", "sector_code": "TECHNOLOGY",
                       "production_capacity": capacity}})


@pytest.mark.parametrize("seed", range(100))
def test_seeded_roots_exact_bounds_and_no_world_rng_consumption(seed):
    before = encode((random.getstate(), np.random.get_state()))
    for country in COUNTRY_SYMBOLS:
        shares, birth, death = wf.country_roots(seed, country, heterogeneous=True)
        assert sum(shares.values()) == 1
        assert .30 <= shares["basic"] <= .50
        assert .32 <= shares["skilled"] <= .48
        assert .12 <= shares["highly_qualified"] <= .30
        assert .008 <= birth <= .016 and .006 <= death <= .011
        assert (shares, birth, death) == wf.country_roots(seed, country, heterogeneous=True)
    assert encode((random.getstate(), np.random.get_state())) == before


def test_mix_inventory_and_seed_variation():
    assert len(wf.SECTOR_MIXES) == 16
    assert all(math.isclose(sum(mix), 1) for mix in wf.SECTOR_MIXES.values())
    assert set(wf.SECTOR_INTENSITIES) == set(wf.SECTOR_MIXES)
    assert min(wf.SECTOR_INTENSITIES.values()) > 0
    assert len({repr(wf.country_roots(s, "Ameron", heterogeneous=True)) for s in range(20)}) == 20
    assert wf.SECTOR_MIXES["TECHNOLOGY"] == (.10, .40, .50)
    assert wf.SECTOR_MIXES["AGRICULTURE"] == (.60, .30, .10)


def test_supply_is_not_reduced_by_unemployment_and_ordinary_days_are_frozen():
    state = world()
    wf.initialize(state)
    macro = state.makro["Ameron"]
    roots = deepcopy(macro["workforce"])
    assert macro["birth_rate"] == .012 and macro["death_rate"] == .0085
    assert roots["shares"] == {"basic": .4, "skilled": .4, "highly_qualified": .2}
    assert sum(roots["supply"].values()) == 13_000_000
    macro["arbeitslosigkeit"] = .80
    state.aktien["A"]["production_capacity"] *= 100
    assert not wf.aggregate(state)
    assert macro["workforce"] == roots
    wf.aggregate(state, when=date(1990, 1, 15))
    assert macro["workforce"]["supply"] == roots["supply"]
    assert wf.company_contribution(state, state.aktien["A"]) < 0
    assert macro["arbeitslosigkeit"] == .8


@pytest.mark.parametrize("shortage,expected", [(0, 0), (.01, -.000001), (.5, -.0025), (1, -.01)])
def test_soft_shortage_curve(shortage, expected):
    for mix in wf.SECTOR_MIXES.values():
        assert wf.shortage_contribution((shortage,) * 3, mix) == pytest.approx(expected, abs=1e-17)


def test_abundance_zero_and_lifecycle_reaggregation():
    state = world()
    wf.initialize(state)
    assert set(state.makro["Ameron"]["workforce"]["contributions"].values()) == {0}
    old = state.makro["Ameron"]["workforce"]["demand"]["basic"]
    state.aktien["B"] = deepcopy(state.aktien["A"])
    wf.aggregate(state, when=date(1990, 2, 15))
    assert state.makro["Ameron"]["workforce"]["demand"]["basic"] == 2 * old
    del state.aktien["A"]
    wf.aggregate(state, when=date(1990, 3, 15))
    assert state.makro["Ameron"]["workforce"]["demand"]["basic"] == old


@pytest.mark.parametrize("growth,unemployment", [(.01, .06), (-.08, .40), (.12, .02)])
def test_demography_monthly_annual_and_century_bounds(growth, unemployment):
    state = world()
    wf.initialize(state)
    macro = state.makro["Ameron"]
    macro.update(bip_prozent=growth, arbeitslosigkeit=unemployment)
    annual, monthly = deepcopy(macro), deepcopy(macro)
    wf.advance_population(annual, 1, floor=100_000, when=date(1991, 1, 1))
    for _ in range(12):
        wf.advance_population(monthly, 1 / 12, floor=100_000, when=date(1991, 1, 1))
    assert monthly["bevoelkerung"] == pytest.approx(annual["bevoelkerung"], rel=2e-15)
    old_monthly = max(-.0025, min(.0035, (growth - .005) * .025 - max(0, unemployment - .08) * .010))
    expected_econ = max(-.006, min(.003, old_monthly * 3))
    assert annual["population_growth"] == pytest.approx(.0035 + expected_econ)
    assert annual["workforce"]["population_interval_years"] == 1
    for year in range(100):
        wf.advance_population(annual, 1, floor=100_000, when=date(1992 + year, 1, 1))
    assert 5_000_000 < annual["bevoelkerung"] < 100_000_000
    assert annual["arbeitslosigkeit"] == unemployment


def test_population_floor_is_realized_growth_and_legacy_no_fake_rate():
    state = world(population=2_000_000)
    wf.initialize(state, legacy=True)
    macro = state.makro["Ameron"]
    assert wf.projection(macro)["population_growth"] is None
    assert macro["population_growth"] == .001
    macro.update(bip_prozent=-.10, arbeitslosigkeit=.80)
    wf.advance_population(macro, 1 / 12, floor=2_000_000, when=date(1990, 1, 15))
    assert macro["bevoelkerung"] == 2_000_000
    assert macro["population_growth"] == 0
    assert macro["workforce"]["population_growth_annualized"] == 0


def test_coarse_monthly_result_recurrence_cash_and_handoff():
    state = world(capacity=100_000_000)
    wf.initialize(state)
    asset = state.aktien["A"]
    asset.update(revenue=1000., fcf_margin=.1, cash_reserves=100., free_cash_flow=100.)
    before = {"A": (1000., asset["production_capacity"], 100.)}
    p = {"Ameron": 20_000_000}
    health, factor = 0., 1.
    for _ in range(12):
        delta = wf.company_contribution(state, asset)
        health = .78 * health + .22 * delta
        factor *= 1 + .18 * (.35 * delta + .65 * health)
        asset["production_capacity"] = before["A"][1] * factor
        wf.aggregate(state, force=True)
    expected = factor
    state = world(capacity=100_000_000)
    wf.initialize(state)
    asset = state.aktien["A"]
    asset.update(revenue=1000., fcf_margin=.1, cash_reserves=100., free_cash_flow=100.)
    wf.integrate_coarse(state, p, before, when=date(1991, 1, 1), years=1)
    assert asset["revenue"] == pytest.approx(1000 * expected, rel=2e-15)
    assert asset["cash_reserves"] == 100 * asset["revenue"] / 1000 + max(0, asset["free_cash_flow"]) * .25
    assert asset["free_cash_flow"] == asset["revenue"] * asset["fcf_margin"]
    assert state.makro["Ameron"]["workforce"]["last_aggregation_date"] == "1991-01-01"
    population = state.makro["Ameron"]["bevoelkerung"]
    state.makro = {}  # handoff's other macro fields are outside this unit fixture
    state.aktien["A"].update(aktien_anzahl=10, kurs=10)
    _rebaseline_handoff_state(state)
    assert asset["operating_health"] == pytest.approx(health, rel=2e-15)
    assert "_workforce_coarse_health" not in asset
    assert population == 20_000_000


@pytest.mark.parametrize("day", [14, 15, 16])
def test_exact_save_load_report_boundaries_sparse_history_and_projection(tmp_path, day):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.adapters.legacy_state import snapshot_from_legacy
    from kojakstreet.visible_state import project_visible_state

    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path, seed=1729)
    try:
        runtime.data_store.enable_background_flush()
        runtime.advance_days(day - 1)
        runtime.set_running(False)
        saved = encode(capture(runtime.daten))
        runtime.save_game()
        runtime.advance_day()
        expected = encode(capture(runtime.daten))
        runtime.load_game()
        assert encode(capture(runtime.daten)) == saved
        runtime.advance_day()
        assert encode(capture(runtime.daten)) == expected
        current = runtime.daten.makro["Ameron"]["workforce"]
        assert current["last_aggregation_date"] == ("1990-01-15" if day >= 15 else "1990-01-01")
        runtime.data_store.flush()
        count = runtime.data_store._connection.execute("SELECT count(*) FROM country_workforce_monthly").fetchone()[0]
        assert count == (20 if day >= 15 else 0)
        state, _, _ = project_visible_state(runtime, {"view": "macro", "selection": {"region": "Ameron", "area": "population_society"}})
        assert state.macro["Ameron"]["population_society"]["pools"]
        assert not state.macro_history
        assert all("birth_rate" not in m and "workforce" not in m for m in state.macro.values())
        assert all("population_society" not in m for c, m in state.macro.items() if c != "Ameron")
        broad = snapshot_from_legacy(runtime.daten)
        assert all(not {"workforce", "birth_rate", "death_rate"}.intersection(m) for m in broad.macro.values())
    finally:
        runtime.close()


def test_invalid_feature_checkpoint_is_rejected_before_any_mutation(tmp_path):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path, seed=9)
    try:
        original = capture(runtime.daten)
        invalid = deepcopy(original)
        invalid["checkpoint"]["makro"]["Ameron"]["workforce"]["shortage"]["basic"] = 2
        with pytest.raises(ValueError, match="shortage"):
            restore(runtime.daten, invalid)
        assert encode(capture(runtime.daten)) == encode(original)
        invalid = deepcopy(original)
        invalid["checkpoint"]["makro"]["Ameron"]["workforce"]["shares"]["highly_qualified"] += 1e-10
        with pytest.raises(ValueError, match="sum to one"):
            restore(runtime.daten, invalid)
        assert encode(capture(runtime.daten)) == encode(original)
    finally:
        runtime.close()


def test_nullable_current_rows_and_journal_replay_are_exact(tmp_path):
    from kojakstreet.core.data_store import EconomicDataStore
    state = world()
    wf.initialize(state)
    path = tmp_path / "rows.duckdb"
    store = EconomicDataStore(path)
    rows = store._workforce_rows(state)
    assert rows[0][7] is None
    history = store._history_id
    store.close()
    batch = RowBatch.freeze(1, history, {}, {"country_workforce_current": rows}, {"1990-01-01"})
    RowJournal(path, history).stage(0, batch)
    rows[0] = ("changed",)
    recovered = EconomicDataStore(path)
    try:
        row = recovered._connection.execute("SELECT * FROM country_workforce_current").fetchone()
        assert row[7] is None and row[8] == 0 and row[9] is None and row[10] is None
        assert row[4] == 20_000_000
        assert not RowJournal(path, history, create=False).pending
    finally:
        recovered.close()


@pytest.mark.parametrize("stage", ["before_transaction", "during_copy", "before_commit", "during_commit", "after_commit", "after_ack"])
def test_workforce_writer_crash_recovery_is_atomic_and_idempotent(tmp_path, stage):
    import duckdb

    from kojakstreet.core.data_store import EconomicDataStore
    from tools.workforce_writer_crash import row
    path = tmp_path / "crash.duckdb"
    store = EconomicDataStore(path)
    store.close()
    child = subprocess.run([sys.executable, str(ROOT / "tools/workforce_writer_crash.py"),
                            "--database", str(path), "--stage", stage],
                           capture_output=True, text=True, check=False, timeout=45)
    assert child.returncode == 91, child.stderr
    with duckdb.connect(str(path)) as raw:
        monthly = raw.execute("SELECT * FROM country_workforce_monthly").fetchall()
        current = raw.execute("SELECT * FROM country_workforce_current").fetchall()
        assert len(monthly) == len(current) and len(current) in (0, 1)
    for _ in range(2):
        recovered = EconomicDataStore(path)
        try:
            monthly = recovered._connection.execute("SELECT * FROM country_workforce_monthly").fetchall()
            current = recovered._connection.execute("SELECT * FROM country_workforce_current").fetchall()
            assert len(monthly) == len(current) == 1
            assert monthly[0][1:] == current[0][1:] == row()[1:]
        finally:
            recovered.close()


def test_monthly_hook_once_frozen_does_not_mutate_macro(monkeypatch):
    import kojakstreet.core.company_lifecycle as lifecycle
    state = world(capacity=100_000_000)
    wf.initialize(state)
    asset = state.aktien["A"]
    asset.update(branche="Technology", kurs=1.)
    state.rohstoffe = {code: {"kurs": 100} for code in ("CL", "TTF", "HG", "LIT")}
    state.aktives_event = None
    state.depot = {}
    macro = deepcopy(state.makro)
    delta = wf.company_contribution(state, asset)
    calls = []
    monkeypatch.setattr(lifecycle.random, "uniform", lambda *_: .05)
    monkeypatch.setattr(lifecycle, "company_hedge_profile", lambda *_: {"input_cost": 0, "event": 0, "sector": 0})
    monkeypatch.setattr(lifecycle, "company_regional_factor", lambda *_: 1)
    monkeypatch.setattr(lifecycle, "sector_energy_factor", lambda *_: 1)
    monkeypatch.setattr(lifecycle, "update_stock_fundamentals", lambda a, g, r, s: calls.append((g, r, s)))
    for key in ("update_company_finances_for_asset", "stage_fundamental_repricing", "update_asset_expectations", "update_company_rating"):
        monkeypatch.setattr(lifecycle, key, lambda *_: None)
    lifecycle.update_monthly_companies(state)
    assert calls == [(.01, .05 + delta, 1.)]
    assert state.makro == macro
    assert asset["news_momentum"] == .05


def test_ordinary_day_has_no_workforce_aggregation(tmp_path, monkeypatch):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core import simulation
    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path, seed=7)
    try:
        def unexpected(*_, **__):
            raise AssertionError("ordinary-day workforce scan")
        monkeypatch.setattr(simulation, "aggregate_workforce", unexpected)
        runtime.advance_days(3)
        assert runtime.daten.makro["Ameron"]["workforce"]["last_aggregation_date"] == "1990-01-01"
    finally:
        runtime.close()


def test_legacy_activation_preserves_world_player_rng_and_has_no_backfilled_history(tmp_path):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path, seed=1729)
    try:
        runtime.advance_days(13)
        runtime.set_running(False)
        legacy = capture(runtime.daten)
        legacy["save_version"] = 7
        for macro in legacy["checkpoint"]["makro"].values():
            for field in ("workforce", "birth_rate", "death_rate"):
                del macro[field]
        atomic_write(runtime.save_path, legacy)
        runtime.advance_day()
        runtime.load_game()
        actual = capture(runtime.daten)
        for macro in actual["checkpoint"]["makro"].values():
            assert macro["workforce"]["provenance"] == "legacy_activation"
            assert macro["workforce"]["activated_on"] == "1990-01-14"
            assert wf.projection(macro)["population_growth"] is None
            for field in ("workforce", "birth_rate", "death_rate"):
                del macro[field]
        actual["save_version"] = 7
        assert encode(actual) == encode(legacy)
        runtime.data_store.flush()
        assert runtime.data_store._connection.execute("SELECT count(*) FROM country_workforce_monthly").fetchone()[0] == 0
        runtime.advance_days(2)
        runtime.data_store.flush()
        assert runtime.data_store._connection.execute("SELECT count(*) FROM country_workforce_monthly").fetchone()[0] == 20
        assert runtime.daten.makro["Ameron"]["workforce"]["population_interval_end"] == "1990-01-15"
    finally:
        runtime.close()


def test_real_default_replacement_joins_next_workforce_aggregate(tmp_path):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.company_lifecycle import update_company_lifecycle
    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path, seed=42)
    try:
        state = runtime.daten
        ticker, asset = next(iter(state.aktien.items()))
        country = asset["land"]
        frozen = deepcopy(state.makro[country]["workforce"])
        asset.update(distress_months=9, cash_reserves=0, debt_to_market_cap=1.,
                     free_cash_flow=-1, interest_expense=1, rating="D")
        count = len(state.aktien)
        messages = []
        update_company_lifecycle(state, lambda *text: messages.append(text))
        assert ticker not in state.aktien and ticker in state.retired_company_tickers
        assert len(state.aktien) == count and messages
        assert state.makro[country]["workforce"] == frozen
        wf.aggregate(state, when=date(1990, 1, 15))
        expected = [0., 0., 0.]
        for company in state.aktien.values():
            if company["land"] == country:
                code = wf.sector_code(company)
                for i, mix in enumerate(wf.SECTOR_MIXES[code]):
                    expected[i] += company["production_capacity"] * wf.DEMAND_SCALE * wf.SECTOR_INTENSITIES[code] * mix
        assert list(state.makro[country]["workforce"]["demand"].values()) == expected
    finally:
        runtime.close()


def test_coarse_margin_level_is_never_added_again_to_baseline(tmp_path, monkeypatch):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.fast_history import _advance_correlated_state, _normal
    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path, seed=1729)
    try:
        ticker, asset = next(iter(runtime.daten.aktien.items()))
        baseline_margin = asset.get("free_cash_flow_margin", .08)
        monkeypatch.setattr(wf, "aggregate", lambda *_, **__: False)
        delta = -.005
        for macro in runtime.daten.makro.values():
            macro["workforce"]["contributions"] = dict.fromkeys(wf.SECTOR_MIXES, delta)
        health = 0.
        for month in range(1, 25):
            when = date(1990 + (month - 1) // 12, (month - 1) % 12 + 1, 28)
            company = _normal(1729, when, f"company:{ticker}", 0., .025 * math.sqrt(1 / 12))
            baseline_margin = max(-.08, min(.30, baseline_margin + company * .08))
            health = .78 * health + .22 * delta
            _advance_correlated_state(runtime.daten, 1729, when, 1 / 12)
            assert asset["_workforce_coarse_base_margin"] == baseline_margin
            expected = max(-.08, min(.30, baseline_margin + .06 * delta + .16 * health))
            assert asset["fcf_margin"] == pytest.approx(expected, abs=1e-16)
        population = {c: m["bevoelkerung"] for c, m in runtime.daten.makro.items()}
        _rebaseline_handoff_state(runtime.daten)
        assert population == {c: m["bevoelkerung"] for c, m in runtime.daten.makro.items()}
        assert "_workforce_coarse_base_margin" not in asset
    finally:
        runtime.close()
