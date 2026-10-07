"""Heterogeneous roots, finished Day-1 books and exact continuation boundaries."""
import json
import random
from collections import Counter
from copy import deepcopy
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import capture, decode, encode, restore
from kojakstreet.core.companies import BRANCHEN
from kojakstreet.core.countries import COUNTRY_SYMBOLS
from kojakstreet.core.established_world import WorldGenerationConfig, WorldMode
from kojakstreet.core.financial_products import _price_product
from kojakstreet.core.fundamentals import SECTOR_PROFILES
from kojakstreet.core.heterogeneous_start import (
    COMPANY_CLASSES,
    GDP_BUDGET,
    MARKET_CAP_BUDGET,
    POPULATION_BUDGET,
    POPULATION_CLASSES,
    bounded_budget,
    generate_roots,
    initialization_roots,
)
from kojakstreet.ui_qt.new_simulation import NewSimulationDialog

ROOT = Path(__file__).resolve().parents[1]
COUNTRIES = list(COUNTRY_SYMBOLS)


def config(seed=1729):
    return WorldGenerationConfig(mode=WorldMode.HETEROGENEOUS, seed=seed,
                                 world_id="test-world", created_at="test-created").normalized()


@pytest.mark.parametrize("seed", range(20))
def test_root_budgets_bands_coverage_and_concentration(seed):
    rng_before = encode({"python": random.getstate(), "numpy": np.random.get_state()})
    roots = generate_roots(seed, COUNTRIES, BRANCHEN)
    assert encode({"python": random.getstate(), "numpy": np.random.get_state()}) == rng_before
    assert roots == generate_roots(seed, COUNTRIES, BRANCHEN)
    assert sum(roots.population.values()) == POPULATION_BUDGET
    assert sum(roots.gdp.values()) == GDP_BUDGET
    assert sum(v for caps in roots.company_caps.values() for v in caps) == MARKET_CAP_BUDGET
    assert min(roots.gdp.values()) >= 1000
    assert .10 <= max(roots.gdp.values()) / GDP_BUDGET <= .20
    assert max(roots.country_caps.values()) / MARKET_CAP_BUDGET <= .20
    pop_bands = {name: (lo, hi) for name, _, lo, hi in POPULATION_CLASSES}
    cap_bands = {name: (lo, hi) for name, _, lo, hi in COMPANY_CLASSES}
    assert Counter(roots.population_class.values()) == {name: count for name, count, _, _ in POPULATION_CLASSES}
    assert Counter(c for classes in roots.company_classes.values() for c in classes) == {name: count for name, count, _, _ in COMPANY_CLASSES}
    class_populations = [[v for c, v in roots.population.items() if roots.population_class[c] == name]
                         for name, _, _, _ in POPULATION_CLASSES]
    assert all(min(a) >= max(b) for a, b in pairwise(class_populations))
    for country in COUNTRIES:
        assert pop_bands[roots.population_class[country]][0] <= roots.population[country] <= pop_bands[roots.population_class[country]][1]
        assert .70 <= roots.productivity[country] <= 1.40
        assert sum(len(roots.company_caps[country, s]) for s in BRANCHEN) == 64
        assert sum(c == "Mega Cap" for s in BRANCHEN for c in roots.company_classes[country, s]) <= 2
        assert sum(v for s in BRANCHEN for v in roots.company_caps[country, s]) == roots.country_caps[country]
    for key, caps in roots.company_caps.items():
        assert len(caps) == 4
        assert all(cap_bands[c][0] <= value <= cap_bands[c][1] for value, c in zip(caps, roots.company_classes[key]))


def test_seed_variation_and_infeasible_budgets_are_explicit():
    roots = [generate_roots(seed, COUNTRIES, BRANCHEN) for seed in range(6)]
    for field in ("population", "gdp", "country_caps", "company_caps"):
        assert len({repr(getattr(root, field)) for root in roots}) == len(roots)
    assert sum(count * lo for _, count, lo, _ in COMPANY_CLASSES) <= MARKET_CAP_BUDGET <= sum(count * hi for _, count, _, hi in COMPANY_CLASSES)
    with pytest.raises(ValueError, match="outside the feasible"):
        bounded_budget([1., 2.], [5, 5], [8, 8], 9)
    with pytest.raises(ValueError, match="20 × 16"):
        generate_roots(7, COUNTRIES[:-1], BRANCHEN)


def test_selector_exposes_three_modes_and_only_established_has_history():
    dialog = NewSimulationDialog()
    assert dialog.config().mode is WorldMode.GENESIS
    dialog.established.click()
    assert dialog.years.isEnabled()
    dialog.years.setCurrentIndex(1)
    dialog.heterogeneous.click()
    assert dialog.config().mode is WorldMode.HETEROGENEOUS
    assert dialog.config().prehistory_years == 0 and not dialog.years.isEnabled()
    assert not dialog.genesis.isChecked() and not dialog.established.isChecked()
    assert "heterogeneous_initialization_version" in dialog.config().trajectory_identity()
    assert "heterogeneous_initialization_version" not in WorldGenerationConfig().trajectory_identity()
    assert dialog.years.currentIndex() == -1
    dialog.established.click()
    assert dialog.config().prehistory_years == 75


@pytest.mark.parametrize("seed", [7, 42, 1729])
def test_day1_finished_books_and_first_day_keep_their_root_scales(tmp_path, seed):
    from test_genesis_country_indices import assert_complete

    from kojakstreet.core.global_macro import _observed_government_yields

    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path, world_config=config(seed))
    try:
        data = runtime.daten
        roots = generate_roots(seed, COUNTRIES, BRANCHEN)
        assert initialization_roots.get() is None and not hasattr(data, "_initial_roots")
        assert sum(a["market_cap"] for a in data.aktien.values()) == MARKET_CAP_BUDGET
        assert sum(c["bip_abs"] for c in data.makro.values()) == GDP_BUDGET
        assert sum(c["bevoelkerung"] for c in data.makro.values()) == POPULATION_BUDGET
        assert_complete(data)
        assert data.global_macro["central_bank_balance_sheets"] == sum(c["balance_sheet"] for c in data.makro.values())
        assert data.global_macro["net_liquidity"] == data.global_macro["global_m2"] + data.global_macro["central_bank_balance_sheets"] - data.global_macro["rrp"] - data.global_macro["tga"]
        observed = _observed_government_yields(data, .035)
        assert data.global_macro["avg_10y_yield"] == observed["10y"]
        for country, macro in data.makro.items():
            assert macro["bip_abs"] == roots.gdp[country]
            assert data.MAKRO_HISTORIE[f"{country}_BIP"][0][0] == macro["bip_abs"]
        for stock in data.aktien.values():
            profile = SECTOR_PROFILES[stock["branche"]]
            assert stock["revenue"] == stock["market_cap"] / profile["ps"]
            assert stock["free_cash_flow"] == stock["revenue"] * profile["fcf_margin"]
            assert stock["eps"] == stock["previous_eps"] == max(.1, stock["free_cash_flow"] / stock["aktien_anzahl"])
            assert stock["kurs"] * stock["aktien_anzahl"] == pytest.approx(stock["market_cap"], rel=2e-16)
            assert stock["production_capacity"] > 0
        assert all(b["ticker"] in data.aktien for b in data.bond_market if b["issuer_type"] == "Corporate")
        for fund in data.fonds.values():
            for holding in fund["underlyings"]:
                if holding["asset_type"] == "Stock":
                    assert holding["ticker"] in data.aktien
        for ticker, product in data.derivatives.items():
            assert product["kurs"] == max(.01, _price_product(data, ticker, product))
        for book in (data.aktien, data.rohstoffe, data.kryptos, data.fonds, data.indizes, data.derivatives):
            assert all(not a["historie"] for a in book.values())
        before = deepcopy(data.makro)
        stock_before = deepcopy(data.aktien)
        net_before = data.global_macro["net_liquidity"]
        runtime.advance_day()
        assert_complete(data)
        for country, macro in data.makro.items():
            assert macro["bip_abs"] == before[country]["bip_abs"]
        for ticker, stock in data.aktien.items():
            if ticker in stock_before:
                assert stock["previous_revenue"] == stock_before[ticker]["revenue"]
                assert stock["previous_eps"] == stock_before[ticker]["eps"]
                assert stock["aktien_anzahl"] == stock_before[ticker]["aktien_anzahl"]
        assert abs(data.global_macro["net_liquidity"] / net_before - 1) < .01
        assert data.datum.strftime("%Y-%m-%d") == "1990-01-02"
        runtime.advance_days(13)
        report_macro = deepcopy(data.makro)
        report_stocks = deepcopy(data.aktien)
        runtime.advance_day()
        assert data.datum.strftime("%Y-%m-%d") == "1990-01-16"
        for country, macro in data.makro.items():
            assert macro["bip_abs"] == report_macro[country]["bip_abs"] * (1 + macro["bip_prozent"] / 12)
        for ticker, stock in data.aktien.items():
            if ticker in report_stocks:
                assert stock["previous_revenue"] == report_stocks[ticker]["revenue"]
                assert stock["previous_eps"] == report_stocks[ticker]["eps"]
    finally:
        runtime.close()


def test_immediate_save_load_exact_world_rng_and_continuation(tmp_path):
    runtime = IntegratedRuntime(ROOT, data_dir=tmp_path, world_config=config())
    try:
        runtime.set_running(False)
        original = encode(capture(runtime.daten))
        invalid = deepcopy(capture(runtime.daten))
        invalid["checkpoint"]["world_generation"]["heterogeneous_initialization_version"] = 999
        with pytest.raises(ValueError, match="unsupported Heterogeneous"):
            restore(runtime.daten, invalid)
        assert encode(capture(runtime.daten)) == original
        runtime.save_game()
        runtime.advance_day()
        expected_next = encode(capture(runtime.daten))
        runtime.load_game()
        assert encode(capture(runtime.daten)) == original
        assert runtime.daten.world_generation["mode"] == "HETEROGENEOUS"
        runtime.advance_day()
        assert encode(capture(runtime.daten)) == expected_next
        runtime.set_running(True)
        runtime.set_running(False)
        paused = deepcopy(expected_next)
        paused["checkpoint"]["spiel_pausiert"] = True
        assert encode(capture(runtime.daten)) == paused
    finally:
        runtime.close()


def test_live_worker_all_nine_views_indices_and_player_retail_boundary(tmp_path, qt_application):
    from kojakstreet.live_process import LiveSimulationProcess
    from kojakstreet.ui_qt.app import KojakStreetWindow

    bootstrap = IntegratedRuntime(ROOT, data_dir=tmp_path, world_config=config(42))
    process = LiveSimulationProcess.from_runtime(bootstrap, timeout_seconds=90)
    window = KojakStreetWindow(process.state, process)
    try:
        assert sum(r["asset_type"] == "Index" for r in process.asset_quote_rows()) == 340
        for key in window.VIEW_ORDER:
            window.set_active_view(key)
            qt_application.processEvents()
            assert window.active_view_key == key
            assert window.stack.currentWidget() is window.views[key]
        window.set_active_view("global_macro")
        process.advance_days(2)
        assert not process.state.indices
        window.set_active_view("markets")
        rows = [r for r in window.markets_view.model.rows if r["asset_type"] == "Index"]
        assert len(rows) == 340
        authoritative = process.snapshot()
        assert all(r["data"]["kurs"] == authoritative.indices[r["ticker"]]["kurs"] for r in rows)
        before = process.snapshot()
        stock = next(t for t in before.stocks if t not in before.indices)
        process.trade_spot(stock, 1, "BUY")
        after = process.snapshot()
        assert before.stocks == after.stocks
        assert before.macro == after.macro
        assert after.portfolio != before.portfolio
        process.save_game()
        saved_signature = process.deterministic_signature()
        saved_checkpoint = decode(json.loads((tmp_path / "spielstand.dat").read_text(encoding="utf-8")))["checkpoint"]
        process.advance_days(1)
        process.load_game()
        assert process.deterministic_signature() == saved_signature
        loaded = process.snapshot()
        # Check the actual save representation, including its existing two-sample
        # display topology retention; computational price histories stay complete.
        assert loaded.stocks == saved_checkpoint["aktien"]
        assert loaded.indices == after.indices
        assert loaded.portfolio == after.portfolio
    finally:
        window.close()
        process.close()
