"""Calendar, isolation, persistence and honest selected-country UI contracts."""
import json
import random
import subprocess
import sys
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from kojakstreet.core import politics as p

ROOT = Path(__file__).resolve().parents[1]


def world(seed=1729, heterogeneous=False):
    macro = {"bip_prozent": .015, "arbeitslosigkeit": .052, "inflation": .02}
    state = SimpleNamespace(datum=datetime(1990, 1, 1), simulation_seed=seed,  # noqa: DTZ001 -- simulation calendar is intentionally naive
                            makro={c: dict(macro) for c in ("Ameron", "Ardonia")}, aktives_event=None)
    p.initialize(state, seed=seed, heterogeneous=heterogeneous)
    return state


@pytest.mark.parametrize("seed", range(60))
def test_independent_roots_valid_and_label_not_wealth(seed):
    before = random.getstate()
    numpy_before = np.random.get_state()
    state = world(seed, True)
    other = world(seed, True)
    for country in state.makro:
        p.validate(state.makro[country]["politics"])
        assert state.makro[country]["politics"] == other.makro[country]["politics"]
    assert random.getstate() == before
    assert np.array_equal(np.random.get_state()[1], numpy_before[1])


@pytest.mark.parametrize("system", p.SYSTEMS)
def test_all_systems_calendar_counts_no_fake_votes_and_long_history(system):
    state = world()
    macro = state.makro["Ameron"]
    macro["politics"] = p.create(9, "Ameron", date(1990, 1, 1), macro, heterogeneous=True, system=system)
    p.rebuild_calendar(state)
    before = random.getstate()
    p.advance_coarse(state, date(1990, 1, 1), date(2040, 1, 1), {c: p.macro_snapshot(m) for c, m in state.makro.items()})
    feature = macro["politics"]
    p.validate(feature)
    assert feature["last_monthly"] == "2039-12-15"
    assert random.getstate() == before
    assert len(state._politics_months) == 50*12*2
    if p.SYSTEMS[system][2]:
        assert feature["sequence"] >= 9
        assert feature["last_election"]
        assert feature["latest_result"]
        assert all(a["latest_vote_share"] is not None for a in feature["parties"])
    else:
        assert feature["last_election"] is feature["latest_result"] is None
        assert all(a["latest_vote_share"] is None for a in feature["parties"])
    assert feature["premium"] == 0


def test_genesis_same_mechanics_and_zero_premium():
    state = world()
    a, b = (m["politics"] for m in state.makro.values())
    assert a["political_stability"] == b["political_stability"] == 75
    assert [x["mandate_share"] for x in a["parties"]] == [x["mandate_share"] for x in b["parties"]]
    assert a["next_election"] == b["next_election"] == "1994-01-01"
    assert a["latest_result"] is b["latest_result"] is None


def test_calendar_leap_month_end_coarse_exact_once_and_crisis_coexistence():
    assert p.add_years(date(2020, 2, 29), 5) == date(2025, 2, 28)
    assert p.add_years(date(2020, 1, 31), 4) == date(2024, 1, 31)
    state = world()
    feature = state.makro["Ameron"]["politics"]
    feature["next_election"] = "1990-01-15"
    p.rebuild_calendar(state)
    state.aktives_event = {"laender": ["Ameron"], "bip_makel": -.035}
    economy = {c: {k:v for k,v in m.items() if k != "politics"} for c,m in state.makro.items()}
    p.process_due(state, date(1990, 1, 15))
    assert feature['macro_pressure'] == 6
    result = deepcopy(feature["latest_result"])
    p.process_due(state, date(1990, 1, 15))
    assert feature["sequence"] == 1 and feature["latest_result"] == result
    assert result["inputs"]["macro_available_on"] == "1990-01-01"
    p.monthly(state, date(1990, 1, 15))
    p.monthly(state, date(1990, 1, 15))
    assert len(state._politics_months) == 2
    assert state.aktives_event["bip_makel"] == -.035
    assert {c: {k:v for k,v in m.items() if k != "politics"} for c,m in state.makro.items()} == economy


def test_reordered_countries_and_parties_elect_identically():
    a, b = world(41, True), world(41, True)
    b.makro = dict(reversed(list(b.makro.items())))
    for m in b.makro.values():
        m["politics"]["parties"].reverse()
    for state in (a,b):
        for country,m in state.makro.items():
            if p.SYSTEMS[m["politics"]["system"]][2]:
                p.election(state, country, m["politics"], date(1994, 1, 1))
    for country in a.makro:
        assert a.makro[country]["politics"]["latest_result"] == b.makro[country]["politics"]["latest_result"]


def test_majority_coalition_supported_minority_caretaker_and_cohabitation():
    feature = world().makro["Ameron"]["politics"]
    for a, share in zip(feature["parties"], (.6,.2,.1,.1), strict=True):
        a["mandate_share"] = share
    assert p.form_government(feature)[2] == "single_party_majority"
    for a, share, axis in zip(feature["parties"], (.4,.3,.2,.1), (-1,1,1,1), strict=True):
        a.update(mandate_share=share,economic_axis=axis)
    # p1/p2/p3 are a coherent majority even though plurality belongs to p0.
    feature["system"] = "semi_presidential_democracy"
    ids, _, status, executive = p.form_government(feature)
    assert executive == "Ameron:p0" and executive not in ids and status == "majority_coalition"
    feature["parties"] = feature["parties"][:2]
    for a, share, axis in zip(feature["parties"], (.5,.5), (-.6,.6), strict=True):
        a.update(mandate_share=share,economic_axis=axis)
    assert p.form_government(feature)[2] == "supported_minority"
    feature["parties"][0]["economic_axis"] = -1
    feature["parties"][1]["economic_axis"] = 1
    assert p.form_government(feature)[2] == "caretaker"


def test_same_inputs_same_score_and_macro_pressure_never_enters_hook():
    state = world()
    feature = state.makro["Ameron"]["politics"]
    before = feature["political_stability"]
    premium = p.candidate_premium(before)
    for macro in ({"bip_prozent": -.06, "arbeitslosigkeit": .25, "inflation": .12}, {"bip_prozent": .03, "arbeitslosigkeit": .03, "inflation": .02}):
        for label in p.SYSTEMS:
            # Identical stored mechanics; label isn't an input to the score.
            copy = deepcopy(feature)
            copy["system"] = label
            p.refresh_components(copy,date(1990,1,15),macro,True,monthly=True)
            assert copy["political_stability"] == before
            assert p.candidate_premium(copy["political_stability"]) == premium
            assert copy["premium"] == 0
            assert 0 <= copy["stability"] <= 100
    assert p.candidate_premium(75) == 0
    assert p.candidate_premium(25) == .0025


@pytest.mark.parametrize("field,value", [("premium",.001),("premium_enabled",True),("next_election","1989-01-01"),("base",float('nan')),("government_ids",['missing']),("leadership_axes",[float('inf'),0]),("formation_date","2050-01-01"),("transition",[]),("government_ids","")])
def test_corrupt_politics_rejected_before_restore_mutates_runtime(tmp_path,field,value):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, restore
    rt = IntegratedRuntime(ROOT,data_dir=tmp_path,seed=41)
    try:
        payload = capture(rt.daten)
        original = rt.daten.makro
        payload['checkpoint']['makro']['Ameron']['politics'][field]=value
        with pytest.raises(ValueError):
            restore(rt.daten,payload)
        assert rt.daten.makro is original
    finally:
        rt.close()


def test_runtime_election_save_load_sparse_tables_and_zero_economic_input(tmp_path):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, restore
    from kojakstreet.visible_state import project_visible_state
    rt = IntegratedRuntime(ROOT,data_dir=tmp_path,seed=41)
    try:
        feature = rt.daten.makro['Ameron']['politics']
        feature['next_election']='1990-01-02'
        p.rebuild_calendar(rt.state)
        rt.save_game()
        rt.advance_days(3)
        result = deepcopy(rt.daten.makro['Ameron']['politics'])
        rt.load_game()
        rt.advance_days(3)
        assert rt.daten.makro['Ameron']['politics']==result
        rt.data_store.flush()
        assert rt.data_store._connection.execute("select count(*) from politics_events where event_type='election_result'").fetchone()[0] == 1
        assert rt.data_store._connection.execute('select count(*) from country_politics_monthly').fetchone()[0] == 0
        state,_,_ = project_visible_state(rt,{'view':'macro','selection':{'region':'Ameron','area':'society_politics'}})
        assert list(state.macro)==['Ameron']
        assert not state.stocks and not state.commodities and not state.processed_products and not state.macro_history
        assert len(json.dumps(state.macro,separators=(',',':')).encode()) < 5000
        assert all('politics' not in m and 'society_politics' not in m for m in rt.snapshot().macro.values())
        saved = capture(rt.daten)
        for m in saved['checkpoint']['makro'].values():
            m.pop('politics')
        saved['checkpoint'].pop('politics_calendar')
        restore(rt.daten,saved)
        rt.state.sync_from_legacy()
        before = capture(rt.daten)
        rt._activate_loaded_politics()
        after = capture(rt.daten)
        for m in after['checkpoint']['makro'].values():
            assert m['politics']['premium']==0 and m['politics']['last_election'] is None
            m.pop('politics')
        after['checkpoint'].pop('politics_calendar')
        from kojakstreet.core.checkpoints import encode
        assert encode(before) == encode(after)
    finally:
        rt.close()


def test_society_pies_identity_hidden_tabs_and_honest_distribution(tmp_path):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.ui_qt.views.macro_view import CountryDetailView
    from kojakstreet.visible_state import project_visible_state
    app = QApplication.instance() or QApplication([])
    rt=IntegratedRuntime(ROOT,data_dir=tmp_path,seed=1729)
    try:
        v=CountryDetailView(rt.snapshot_for_view('macro'))
        calls=[]
        def fetch(scope):
            calls.append(scope)
            return project_visible_state(rt,scope)[0]
        v.scope_provider=fetch
        v.scope_changed=lambda state: None
        v.update_region('Ameron',rt.snapshot_for_view('macro'))
        assert v.tabs.count()==5
        assert v.tabs.tabText(4).replace('&&', '&') == 'Society & Politics'
        assert v.society_panel.update_count==0
        v.tabs.setCurrentIndex(4)
        panel=v.society_panel
        assert len(panel.workforce_pie.slices)==3
        assert not panel.political_pie.slices
        assert panel.values['Population Growth · annualized'].text()=='Not yet observed'
        ids=(id(panel),id(panel.workforce_pie),id(panel.political_pie))
        p.election(rt.state,'Ameron',rt.daten.makro['Ameron']['politics'],date(1994,1,1))
        v.refresh(project_visible_state(rt,calls[-1])[0])
        assert len(panel.political_pie.slices)==4
        assert '1994-01-01' in panel.political_note.text()
        geometry=panel.political_pie.geometry_updates
        v.refresh(project_visible_state(rt,calls[-1])[0])
        assert panel.political_pie.geometry_updates==geometry
        assert ids==(id(v.society_panel),id(panel.workforce_pie),id(panel.political_pie))
        updates=panel.update_count
        v.tabs.setCurrentIndex(0)
        v.refresh(project_visible_state(rt,{'view':'macro','selection':{'region':'Ameron','tab':0}})[0])
        assert panel.update_count==updates
        for system in ('absolute_monarchy','one_party_state','authoritarian_republic'):
            rt.daten.makro['Ameron']['politics']=p.create(3,'Ameron',date(1990,1,1),rt.daten.makro['Ameron'],system=system)
            v.tabs.setCurrentIndex(4)
            v.refresh(project_visible_state(rt,{'view':'macro','selection':{'region':'Ameron','area':'society_politics'}})[0])
            assert not panel.political_pie.slices
            assert panel.political_note.text()=='No competitive party election'
        v.close()
        app.processEvents()
    finally:
        rt.close()


@pytest.mark.parametrize('stage', ['before_transaction','before_commit','after_commit','after_ack'])
def test_new_sparse_tables_crash_recovery_atomic_idempotent(tmp_path,stage):
    from kojakstreet.core.data_store import EconomicDataStore
    path=tmp_path/'crash.duckdb'
    store=EconomicDataStore(path)
    store.close()
    child=subprocess.run([sys.executable,str(ROOT/'tools/politics_writer_crash.py'),'--database',str(path),'--stage',stage],capture_output=True,text=True,timeout=60,check=False)
    assert child.returncode==91,child.stderr
    for _ in range(2):
        store=EconomicDataStore(path)
        try:
            assert store._connection.execute('select count(*) from politics_events').fetchone()[0]==1
            assert store._connection.execute('select count(*) from country_politics_monthly').fetchone()[0]==1
            assert store._connection.execute('select count(*) from country_politics_current').fetchone()[0]==1
        finally:
            store.close()


def test_save_load_report_transition_and_late_scope_rejection(tmp_path):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.live_process import LiveSimulationProcess, game_state_payload
    from kojakstreet.visible_state import project_visible_state
    rt = IntegratedRuntime(ROOT, data_dir=tmp_path, seed=41)
    try:
        feature = rt.daten.makro['Ameron']['politics']
        feature['government_ids'] = ['Ameron:p0']
        feature['next_election'] = '1990-01-15'
        p.rebuild_calendar(rt.state)
        rt.advance_days(15)
        assert feature['last_election'] == '1990-01-15'
        assert feature['last_monthly'] == '1990-01-15'
        assert feature['transition'] is not None
        rt.save_game()
        rt.advance_days(31)
        expected = deepcopy(rt.daten.makro['Ameron']['politics'])
        rt.load_game()
        rt.advance_days(31)
        assert rt.daten.makro['Ameron']['politics'] == expected
        rt.data_store.flush()
        current_json = rt.data_store._connection.execute("SELECT payload_json FROM country_politics_current WHERE region='Ameron'").fetchone()[0]
        assert json.loads(current_json) == expected
        report_row = rt.data_store._connection.execute("SELECT political_stability, macro_pressure, stability, premium, revision FROM country_politics_monthly WHERE region='Ameron' AND date=?", [expected['last_monthly']]).fetchone()
        assert report_row == tuple(expected[k] for k in ('political_stability', 'macro_pressure', 'stability', 'premium', 'revision'))
        selected, _, _ = project_visible_state(rt, {'view': 'macro', 'selection': {'region': 'Ameron', 'area': 'society_politics'}})
        process = object.__new__(LiveSimulationProcess)
        process._requested_scope = {'view': 'macro', 'selection': {'region': 'Ardonia', 'area': 'society_politics'}}
        process._snapshots = {}
        process._status_state = rt.snapshot()
        original = process.state
        process._apply_result({'visible_state': True, 'state': game_state_payload(selected),
                               'visible_scope': {'view': 'macro', 'selection': {'region': 'Ameron', 'area': 'society_politics'}}})
        assert process.state is original
    finally:
        rt.close()


def test_local_visible_society_refreshes_on_monthly_and_election_delta(tmp_path):
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.ui_qt.app import KojakStreetWindow
    app = QApplication.instance() or QApplication([])
    rt = IntegratedRuntime(ROOT, data_dir=tmp_path, seed=1729)
    window = KojakStreetWindow(rt.snapshot(), rt)
    try:
        window.set_active_view('macro')
        macro = window.views['macro']
        detail = macro.detail_view
        detail.update_region('Ameron', macro.state)
        macro.pages.setCurrentWidget(detail)
        detail.tabs.setCurrentIndex(4)
        feature = rt.daten.makro['Ameron']['politics']
        feature['next_election'] = '1990-01-02'
        p.rebuild_calendar(rt.state)
        rt.advance_day()
        window._apply_live_market_updates()
        rt.advance_day()
        window._apply_live_market_updates()
        app.processEvents()
        assert '1990-01-02' in detail.society_panel.political_note.text()
        assert len(detail.society_panel.political_pie.slices) == 4
        rt.advance_days(13)
        window._apply_live_market_updates()
        app.processEvents()
        assert detail.society_panel.values['Population Growth · annualized'].text() != 'Not yet observed'
    finally:
        window.close()
        rt.close()


def test_sparse_bulk_identity_replay_preserves_other_country_and_exact_values(tmp_path):
    from kojakstreet.core.data_store import EconomicDataStore
    store = EconomicDataStore(tmp_path/'sparse.duckdb')
    try:
        months = [(f'{1990+i//12}-{1+i%12:02d}-15', f'Country{country}', 74.12345678901234, 5.23456789012345, 68.88888889888889, 0., i)
                  for i in range(120) for country in range(20)]
        store._replace_buffered_rows('country_politics_monthly', months)
        store._replace_buffered_rows('country_politics_monthly', months)
        assert store._connection.execute('SELECT count(*) FROM country_politics_monthly').fetchone()[0] == 2400
        replacement = (*months[0][:2], 73.12345678901234, *months[0][3:])
        store._replace_buffered_rows('country_politics_monthly', [replacement])
        actual = store._connection.execute("SELECT political_stability, macro_pressure, stability, premium, revision FROM country_politics_monthly WHERE date='1990-01-15' AND region='Country0'").fetchone()
        assert actual == replacement[2:]
        assert store._connection.execute("SELECT count(*) FROM country_politics_monthly WHERE date='1990-01-15'").fetchone()[0] == 20
        events = [('1990-01-15', 'a'*24, 'Country0', 'election_result', '{"value":0.12345678901234567}'),
                  ('1990-01-15', 'b'*24, 'Country1', 'election_result', '{"value":0.9876543210987654}')]
        store._replace_buffered_rows('politics_events', events)
        store._replace_buffered_rows('politics_events', [events[0], events[0]])
        assert store._connection.execute('SELECT count(*) FROM politics_events').fetchone()[0] == 2
        assert store._connection.execute("SELECT metadata_json FROM politics_events WHERE event_id=?", ['a'*24]).fetchone()[0] == events[0][4]
        quoted = ('1990-01-15', "Country's capital", *replacement[2:])
        store._replace_buffered_rows('country_politics_monthly', [quoted])
        store._replace_buffered_rows('country_politics_monthly', [quoted])
        assert store._connection.execute("SELECT count(*) FROM country_politics_monthly WHERE region=?", [quoted[1]]).fetchone()[0] == 1
    finally:
        store.close()


def test_crisis_start_end_display_only_and_no_daily_pressure_work():
    state = world()
    feature = state.makro['Ameron']['politics']
    baseline = feature['political_stability']
    published = deepcopy(feature['published_macro'])
    state.aktives_event = {'laender': ['Ameron']}
    p.refresh_crisis_pressure(state, None)
    assert feature['macro_pressure'] == 6
    assert feature['political_stability'] == baseline
    assert feature['published_macro'] == published and feature['last_monthly'] is None
    seq = feature['event_sequence']
    p.refresh_crisis_pressure(state, state.aktives_event)
    assert feature['event_sequence'] == seq
    previous, state.aktives_event = state.aktives_event, None
    p.refresh_crisis_pressure(state, previous)
    assert feature['macro_pressure'] == 0
    assert feature['political_stability'] == baseline and feature['premium'] == 0
    for macro in state.makro.values():
        macro.pop('politics')
    state.aktives_event = {'laender': ['Ameron']}
    p.initialize(state, seed=1729, legacy=True)
    activated = state.makro['Ameron']['politics']
    assert activated['political_stability'] == 75 and activated['macro_pressure'] == 6
    assert activated['last_election'] is None and activated['premium'] == 0


@pytest.mark.parametrize('corruption', ['input_date', 'sequence', 'identity', 'mandate'])
def test_immutable_result_provenance_and_mandate_rejected(corruption):
    state = world()
    feature = state.makro['Ameron']['politics']
    p.election(state, 'Ameron', feature, date(1990, 1, 2))
    if corruption == 'input_date':
        feature['latest_result']['inputs']['macro_available_on'] = '1990-01-03'
    elif corruption == 'sequence':
        feature['latest_result']['sequence'] += 1
    elif corruption == 'identity':
        feature['latest_result']['id'] = 'bad'
    else:
        feature['parties'][0]['mandate_share'] += .01
        feature['parties'][1]['mandate_share'] -= .01
    with pytest.raises(ValueError):
        p.validate(feature, as_of=date(1990, 1, 3))


def test_saved_calendar_allows_today_but_rejects_missing_past_term():
    feature = world().makro['Ameron']['politics']
    p.validate(feature, as_of=date(1994, 1, 1))
    with pytest.raises(ValueError):
        p.validate(feature, as_of=date(1994, 1, 2))
