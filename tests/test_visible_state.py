"""Visible scopes must be exact and must never require a hidden world diff."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.runtime_context import SimulationDelta
from kojakstreet.live_worker import _runtime_result
from kojakstreet.ui_qt.widgets.top_bar import TickerTape
from kojakstreet.visible_state import project_visible_state, ticker_items


def world():
    date = datetime(1991, 1, 31)  # noqa: DTZ001 -- simulation calendar uses naive dates

    def asset(index):
        return {
            "name": f"Company {index}",
            "kurs": 120.0,
            "aenderung": 1.0,
            "market_cap": 500.0,
            "land": "Ameron",
            "branche": "Industrials",
            "revenue": 4200.0 + index,
            "historie": [
                (100.0 + day, (date - timedelta(days=19 - day)).strftime("%d.%m.%Y"), "")
                for day in range(20)
            ],
            "company_output_history": {"ELC": {"history": [(30.0, "01.01.1991", "")]}},
            "output_mix": {"ELC": 1.0},
            "_resolved_underlyings": {"hidden": "world"},
        }

    daten = SimpleNamespace(
        datum=date,
        bargeld=10.0,
        forex_depot={"GD": 100.0},
        anzeige_waehrung="GD",
        aktien={str(i): asset(i) for i in range(1280)},
        rohstoffe={"XAU": asset(0)},
        fonds={
            "F82": {
                **asset(82),
                "aum": 999.0,
                "underlyings": [{"ticker": "900", "asset_type": "Stock", "weight": 0.5}],
            }
        },
        makro={
            "Ameron": {
                "bip_abs": 99.0,
                "regional_supply": {"ELC": 12.0},
                "regional_demand": {"ELC": 15.0},
                "rating": "AAA",
            }
        },
        waehrungen_staerke={"Ameron": 1.0},
    )
    return SimpleNamespace(daten=daten)


def test_normal_result_never_requests_a_full_world_or_encoder():
    runtime = world()
    health_checks = []
    runtime.data_store = SimpleNamespace(check_persistence_health=lambda: health_checks.append(True))
    runtime.current_delta = lambda: SimulationDelta(
        10, "1991-01-31", frozenset({"asset_current", "bond_current"})
    )
    runtime.phase_metric_current_rows = list
    runtime.snapshot_for_view = lambda *_: (_ for _ in ()).throw(AssertionError("Broad snapshot"))
    result = _runtime_result(runtime, scope={"view": "markets"})
    assert health_checks == [True]
    assert result["visible_state"]
    assert "day_delta" not in result
    assert result["current_rows"] == {}
    assert not hasattr(runtime, "_day_state_encoder")
    assert "revenue" not in result["state"]["stocks"]["900"]
    assert "historie" not in result["state"]["stocks"]["900"]


def test_hidden_company_then_open_fundamentals_and_supply_are_current():
    runtime = world()
    before, _, _ = project_visible_state(runtime, {"view": "markets"})
    runtime.daten.aktien["900"]["revenue"] = 123456.0
    runtime.daten.aktien["900"]["company_output_history"]["ELC"]["history"].append(
        (45.0, "31.01.1991", "")
    )
    assert "revenue" not in before.stocks["900"]
    overview, _, _ = project_visible_state(
        runtime,
        {"view": "markets", "selection": {"kind": "Stock", "ticker": "900", "tab": "overview"}},
    )
    assert overview.stocks["900"]["revenue"] == 123456.0
    assert "company_output_history" not in overview.stocks["900"]
    assert "revenue" not in overview.stocks["901"]
    supply, _, _ = project_visible_state(
        runtime,
        {"view": "markets", "selection": {"kind": "Stock", "ticker": "900", "tab": "supply"}},
    )
    assert supply.stocks["900"]["output_mix"] == runtime.daten.aktien["900"]["output_mix"]
    assert "company_output_history" not in supply.stocks["900"]
    scope = {
        "view": "markets",
        "selection": {
            "kind": "Stock",
            "ticker": "900",
            "tab": "chart",
            "supply_metric": ["Produces", "ELC"],
        },
    }
    chart, _, _ = project_visible_state(runtime, scope)
    assert chart.stocks["900"]["visible_metric_history"] == [30.0, 45.0]
    assert "company_output_history" not in supply.stocks["901"]


def test_fund_overview_count_and_allocations_have_separate_contracts():
    runtime = world()
    scope = {"view": "markets", "selection": {"kind": "Fund", "ticker": "F82", "tab": "overview"}}
    overview, _, _ = project_visible_state(runtime, scope)
    assert overview.funds["F82"]["aum"] == 999.0
    assert overview.funds["F82"]["visible_holding_count"] == 1
    assert "underlyings" not in overview.funds["F82"]
    scope["selection"]["tab"] = "supply"
    allocations, _, _ = project_visible_state(runtime, scope)
    assert allocations.funds["F82"]["visible_allocations"] == [
        {"ticker": "900", "name": "Company 900", "asset_type": "Stock", "weight": 0.5}
    ]


def test_price_tail_uses_calendar_dates_and_preserves_ohlc():
    runtime = world()
    scope = {"view": "markets", "selection": {"kind": "Stock", "ticker": "900", "tab": "chart"}}
    state, _, _ = project_visible_state(runtime, scope, history_since="1991-01-30")
    assert state.stocks["900"]["historie"] == runtime.daten.aktien["900"]["historie"][-2:]
    assert "revenue" not in state.stocks["900"]


def test_country_tab_fetches_current_production_without_other_detail():
    runtime = world()
    main, _, _ = project_visible_state(runtime, {"view": "macro"})
    assert "regional_supply" not in main.macro["Ameron"]
    runtime.daten.makro["Ameron"]["regional_supply"]["ELC"] = 777.0
    detail, _, _ = project_visible_state(
        runtime, {"view": "macro", "selection": {"region": "Ameron", "tab": 1}}
    )
    assert detail.macro["Ameron"]["regional_supply"] == {"ELC": 777.0}
    assert not detail.stocks


def test_country_sectors_match_existing_summary_without_copying_hidden_histories():
    from kojakstreet.adapters.legacy_state import _copy_macro_mapping

    runtime = world()
    for index, asset in enumerate(runtime.daten.aktien.values()):
        asset.update(
            production_capacity=float(index + 1), capacity_utilization=0.75, capacity_growth=0.03
        )
    expected = _copy_macro_mapping(runtime.daten, include_sector_summary=True)["Ameron"][
        "sector_summary"
    ]

    class ForbiddenHistory(dict):
        def items(self):
            raise AssertionError("Sector tab copied hidden country history")

    runtime.daten.makro["Ameron"]["regional_history"] = ForbiddenHistory({"ELC": [1.0, 2.0]})
    runtime.daten.makro["Other"] = {"regional_history": ForbiddenHistory({"ELC": [3.0, 4.0]})}
    state, _, _ = project_visible_state(
        runtime, {"view": "macro", "selection": {"region": "Ameron", "tab": 3}}
    )
    assert state.macro["Ameron"]["sector_summary"] == expected
    assert "regional_history" not in state.macro["Ameron"]


def test_selected_derivative_keeps_contract_size_for_visible_order_summary():
    runtime = world()
    runtime.daten.derivatives = {
        "SWAP": {
            "name": "Rate Swap",
            "kurs": 125.0,
            "contract_size": 250.0,
            "instrument_type": "Inflation Swap",
        }
    }
    state, _, _ = project_visible_state(
        runtime,
        {"view": "markets", "selection": {"kind": "Derivative", "ticker": "SWAP", "tab": "chart"}},
    )
    assert state.derivatives["SWAP"]["contract_size"] == 250.0


def test_ticker_current_immediately_and_layout_cache_bounded():
    app = QApplication.instance() or QApplication([])
    tape = TickerTape()
    try:
        items = ticker_items(world().daten)
        tape.set_items(items)
        tape.offset = 40
        changed = [{**item, "price": item["price"] + 1} for item in items]
        tape.set_items(changed)
        assert tape.items == changed
        assert tape.pending_items is None
        assert tape.offset == 40
        assert len(tape._layout_cache) <= len(changed)
        tape.resize(300, 60)
        tape.show()
        app.processEvents()
    finally:
        tape.close()


def test_ticker_seven_day_values_equal_existing_display_contract():
    from kojakstreet.ui_qt.widgets.top_bar import TopBar

    app = QApplication.instance() or QApplication([])
    assert app is not None
    runtime = world()
    bar = TopBar(snapshot_from_legacy(runtime.daten), 1280)
    try:
        assert ticker_items(runtime.daten) == bar._build_ticker_items(
            snapshot_from_legacy(runtime.daten)
        )
    finally:
        bar.close()


def test_bootstrap_release_detaches_books_and_preserves_retained_references(monkeypatch, tmp_path):
    import kojakstreet.live_process as proxy

    runtime = world()
    original = runtime.daten.aktien
    runtime.project_root = tmp_path
    runtime.data_dir = tmp_path
    runtime.state = SimpleNamespace(aktien=original)
    runtime.state.sync_from_legacy = lambda: setattr(runtime.state, "aktien", runtime.daten.aktien)
    runtime.close = lambda: None
    runtime.data_store = SimpleNamespace(
        record_day=lambda *_args, **_kwargs: None, flush=lambda: None, checkpoint_session=dict
    )
    monkeypatch.setattr(proxy, "capture", lambda daten: {"checkpoint": {"datum": daten.datum}})
    monkeypatch.setattr(proxy, "atomic_write", lambda *_args: None)
    monkeypatch.setattr(proxy.LiveSimulationProcess, "__init__", lambda *_args, **_kwargs: None)
    proxy.LiveSimulationProcess.from_runtime(runtime, release_bootstrap=True)
    assert len(original) == 1280
    assert runtime.daten.aktien == {}
    assert runtime.state.aktien is runtime.daten.aktien
