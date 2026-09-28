from datetime import datetime
import pickle
import random
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import atomic_write, capture, decode, encode, restore
from kojakstreet.core.financial_products import _cds_price, _fx_forward_price
from kojakstreet.core.portfolio import build_portfolio_analytics
from kojakstreet.core.state import GameState


def test_forward_keeps_spot_sensitivity_and_quote_convention():
    state = SimpleNamespace(waehrungen_staerke={"Ameron": 1., "Albionia": 1.}, makro={"Ameron": {"zins": .05}, "Albionia": {"zins": .02}})
    product = {"base_currency": "Ameron", "quote_currency": "Albionia", "tenor_months": 12}
    price = _fx_forward_price(state, product)
    assert price == pytest.approx(100 * 1.02 / 1.05)
    state.waehrungen_staerke["Ameron"] = 2.
    assert _fx_forward_price(state, product) == pytest.approx(price * 2)


def test_cds_uses_deficit_ratio_and_does_not_penalize_surplus():
    macro = {"bip_abs": 5000., "fiscal_deficit": 100., "default_probability": .02}
    state = SimpleNamespace(makro={"A": macro})
    product = {"underlying": "A"}
    first = _cds_price(state, product)
    macro.update(bip_abs=10000., fiscal_deficit=200.)
    assert _cds_price(state, product) == pytest.approx(first)
    macro["fiscal_deficit"] = -200.
    assert _cds_price(state, product) < first
    assert product["fiscal_deficit_ratio"] == 0


def test_portfolio_converts_values_exposures_and_costs_to_gd():
    state = GameState(date=datetime(1990, 1, 1), cash=0., display_currency="GD")
    state.commodities = {"XAU": {"kurs": 200.}}
    state.currency_strength = {"A": 4., "B": 2.}
    state.stocks = {k: {"kurs": 100., "land": k} for k in ("A", "B")}
    state.portfolio = {k: {"stueck": 1., "kaufkurs": 80.} for k in ("A", "B")}
    a = build_portfolio_analytics(state)
    assert a.total_value_gd == 300.
    assert a.total_cost_gd == 240.
    assert a.unrealized_pnl_gd == 60.
    assert a.region_exposure == {"A": 200., "B": 100.}


def test_atomic_failure_keeps_previous_save(tmp_path, monkeypatch):
    path = tmp_path / "save.json"
    path.write_text("original")
    def fail(*args):
        raise OSError("disk failure")
    monkeypatch.setattr("kojakstreet.core.checkpoints.os.replace", fail)
    with pytest.raises(OSError):
        atomic_write(path, {"valid": True})
    assert path.read_text() == "original"
    assert list(tmp_path.iterdir()) == [path]


def test_legacy_pickle_rejects_executable_global(tmp_path):
    import speicher
    class Exploit:
        def __reduce__(self):
            return (eval, ("40+2",))
    path = tmp_path / "unsafe.dat"
    path.write_bytes(pickle.dumps(Exploit()))
    with pytest.raises(pickle.UnpicklingError):
        speicher._load_payload(path)


def test_monthly_day_runs_daily_phases_and_books_once(tmp_path, monkeypatch):
    runtime = IntegratedRuntime(Path.cwd(), data_dir=tmp_path)
    try:
        runtime.daten.datum = datetime(1990, 1, 15)
        daily_calls = []
        monkeypatch.setattr(runtime.production, "update_daily_production_chain", lambda: daily_calls.append(True))
        before = len(runtime.daten.DEPOT_VERMOEGEN_HISTORIE)
        runtime.advance_day()
        phases = {row["phase"] for row in runtime.daten.simulation_phase_timings}
        assert {"monthly_macro", "credit_interest", "derivatives", "future_settlements", "asset_market", "bond_portfolio"} <= phases
        assert runtime.daten.datum == datetime(1990, 1, 16)
        assert len(runtime.daten.DEPOT_VERMOEGEN_HISTORIE) == before + 1
        assert not daily_calls  # monthly production already booked the inventory flow
        runtime.advance_day()
        assert daily_calls == [True]
    finally:
        runtime.close()


@pytest.mark.parametrize("start_date", [datetime(1990, 1, 1), datetime(1990, 1, 17)])
def test_checkpoint_exact_continuation_across_monthly_processing(tmp_path, start_date):
    random.seed(1729)
    np.random.seed(1729)
    runtime = IntegratedRuntime(Path.cwd(), data_dir=tmp_path)
    try:
        runtime.daten.datum = start_date
        runtime.advance_days(13)
        runtime.save_game()
        expected = []
        for _ in range(4):
            runtime.advance_day()
            expected.append(encode(capture(runtime.daten)))
        runtime.close()
        random.seed(99)
        np.random.seed(99)
        runtime = IntegratedRuntime(Path.cwd(), data_dir=tmp_path)
        runtime.load_game()
        assert runtime.product_history("ELC", "price")
        for day, expected_day in enumerate(expected, start=1):
            runtime.advance_day()
            actual = encode(capture(runtime.daten))
            assert actual == expected_day, f"Continuation differs on day {day}"
    finally:
        runtime.close()


def test_real_qt_runtime_spot_future_fx_and_shutdown(tmp_path):
    from PySide6.QtWidgets import QApplication
    from kojakstreet.ui_qt.app import KojakStreetWindow
    app = QApplication.instance() or QApplication([])
    runtime = IntegratedRuntime(Path.cwd(), data_dir=tmp_path)
    window = KojakStreetWindow(runtime.snapshot_for_view("markets"), runtime)
    ticker = next(iter(runtime.daten.aktien))
    window._execute_trade(ticker, "SPOT", "BUY", 1., 1)
    assert runtime.daten.depot[ticker]["stueck"] == 1.
    window._execute_trade(ticker, "FUTURE", "LONG", 100., 2)
    assert len(runtime.daten.perpetuals) == 1
    window._close_future(next(iter(runtime.daten.perpetuals)))
    assert not runtime.daten.perpetuals
    window._exchange_currency("GD", "Ameron", 100.)
    assert runtime.daten.forex_depot["Ameron"] > 0
    window.close()
    app.processEvents()
    assert runtime.data_store._connection is None
    runtime.close()


def test_invalid_checkpoint_does_not_replace_world_or_rng(tmp_path):
    runtime = IntegratedRuntime(Path.cwd(), data_dir=tmp_path)
    try:
        before = encode(capture(runtime.daten))
        malformed = decode(before)
        malformed["rng"]["python"] = (999, (), None)
        with pytest.raises(ValueError):
            restore(runtime.daten, malformed)
        assert encode(capture(runtime.daten)) == before
    finally:
        runtime.close()


def test_qt_worker_finishes_before_store_close(tmp_path):
    import threading
    from PySide6.QtWidgets import QApplication
    from kojakstreet.ui_qt.app import KojakStreetWindow
    app = QApplication.instance() or QApplication([])
    runtime = IntegratedRuntime(Path.cwd(), data_dir=tmp_path)
    window = KojakStreetWindow(runtime.snapshot_for_view("markets"), runtime)
    original = runtime.advance_days
    started = threading.Event()
    def advance(*args):
        started.set()
        return original(*args)
    runtime.advance_days = advance
    window._request_simulation_steps(1, force_refresh=True)
    assert started.wait(5)
    window.close()
    app.processEvents()
    assert runtime.daten.datum == datetime(1990, 1, 2)
    assert runtime.data_store._connection is None
    import duckdb
    with duckdb.connect(str(tmp_path / "kojakstreet.duckdb")) as connection:
        assert connection.execute("SELECT COUNT(*) FROM asset_daily").fetchone()[0] > 0


def test_all_workspaces_fit_desktop_and_keep_navigation_consistent():
    from PySide6.QtWidgets import QApplication, QPushButton
    import daten
    from kojakstreet.adapters.legacy_state import snapshot_from_legacy
    from kojakstreet.ui_qt.app import KojakStreetWindow
    from kojakstreet.ui_qt.widgets.view_header import ViewHeader
    app = QApplication.instance() or QApplication([])
    window = KojakStreetWindow(snapshot_from_legacy(daten))
    window.resize(1366, 768)
    window.show()
    try:
        for key in window.VIEW_ORDER:
            window.set_active_view(key)
            app.processEvents()
            assert window.width() == 1366 and window.height() == 768
            assert window.side_nav.buttons[key].isChecked()
            header = window.views[key].findChild(ViewHeader)
            assert not header.findChildren(QPushButton)
            assert window.stack.height() <= max(window.workspace_scroll.viewport().height(), window.stack.minimumSizeHint().height())
    finally:
        window.close()
