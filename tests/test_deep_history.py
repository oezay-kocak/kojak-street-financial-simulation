from __future__ import annotations

from datetime import date, datetime, timedelta
import random
from types import SimpleNamespace

import numpy as np
import pytest

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.cryptos import CRYPTO_TASK_TYPES, TARGET_CRYPTO_COUNT, ensure_crypto_universe
from kojakstreet.core.data_store import EconomicDataStore
from kojakstreet.core.financial_products import _input_cost_spread_price
from kojakstreet.core.history import HOT_PRICE_POINTS, SemanticType, aggregate_values
from kojakstreet.core.ohlc import append_ohlc_from_move
from kojakstreet.core.market_calculations import _asset_ema_diff
from kojakstreet.core.shocks import add_shock, shock_multiplier


def test_semantic_aggregation_preserves_price_shape_and_flow_sum() -> None:
    points = [(date(1990, 1, day), value) for day, value in ((1, 100.0), (2, 115.0), (3, 90.0), (4, 108.0))]

    price = aggregate_values(points, SemanticType.PRICE)
    flow = aggregate_values(points, SemanticType.FLOW)

    assert (price.open, price.high, price.low, price.close) == (100.0, 115.0, 90.0, 108.0)
    assert price.total == 0.0
    assert flow.total == 413.0
    assert price.mean == pytest.approx(103.25)


def test_asset_hot_history_stops_growing_after_computational_window() -> None:
    asset: dict = {}
    for index in range(HOT_PRICE_POINTS + 80):
        append_ohlc_from_move(asset, 100.0 + index, 101.0 + index, f"{index}")

    assert len(asset["historie"]) == HOT_PRICE_POINTS
    assert asset["historie"][0][0] == pytest.approx(181.0)


def test_ema_cache_continues_updating_after_hot_window_rollover() -> None:
    asset = {"historie": [(100.0, str(index), "") for index in range(HOT_PRICE_POINTS)]}
    first = _asset_ema_diff(asset, 20)
    asset["historie"].pop(0)
    asset["historie"].append((120.0, "next", ""))
    second = _asset_ema_diff(asset, 20)

    assert second != first
    assert tuple(asset["_ema_cache"]["20"]["marker"]) == ("next", 120.0)


def test_adaptive_history_spans_compacted_world_and_is_bounded(tmp_path) -> None:
    store = EconomicDataStore(tmp_path / "history.duckdb", auto_flush=False)
    if not store.enabled:
        pytest.skip("DuckDB unavailable")
    start = date(1990, 1, 1)
    rows = []
    for index in range(365 * 4):
        day = start + timedelta(days=index)
        value = 100.0 + index * 0.1
        rows.append((day.isoformat(), "AAA", "Stock", "Atlas", "Ameron", "Technology", value, 0.0, 1.0, 1.0, 0.1, "BBB"))
    store._insert_rows("asset_daily", rows)
    store._compact_completed_history()
    first_count = store._connection.execute("SELECT count(*) FROM history_aggregate").fetchone()[0]
    store._compact_completed_history()
    second_count = store._connection.execute("SELECT count(*) FROM history_aggregate").fetchone()[0]

    points = store.history_series("asset_daily", "ticker", "Stock:AAA", "price", pixel_budget=24, semantic_type="price")

    assert first_count == second_count
    assert len(points) <= 24
    assert points[0]["start"].startswith("1990") or points[0]["date"].startswith("1990")
    assert points[-1]["date"].startswith("1993")
    assert {point["resolution"] for point in points} <= {"yearly", "raw"}
    store.close()


def test_global_macro_adaptive_history_preserves_rate_and_level_semantics(tmp_path) -> None:
    store = EconomicDataStore(tmp_path / "global-macro.duckdb", auto_flush=False)
    if not store.enabled:
        pytest.skip("DuckDB unavailable")
    start = date(1990, 1, 1)
    rows = []
    for index in range(365 * 4):
        day = start + timedelta(days=index)
        value = 100.0 + index
        rows.extend(((day.isoformat(), "global_m2", value), (day.isoformat(), "global_cpi", value)))
    store._insert_rows("global_macro_daily", rows)
    # asset_daily supplies the store's compaction reference date.
    store._insert_rows("asset_daily", [((start + timedelta(days=365 * 4 - 1)).isoformat(), "AAA", "Stock", "Atlas", "Ameron", "Technology", 100.0, 0.0, 1.0, 1.0, 0.1, "BBB")])
    store._compact_completed_history()

    level = store.history_series("global_macro_daily", "metric", "global_m2", "value", pixel_budget=8, semantic_type="level")
    rate = store.history_series("global_macro_daily", "metric", "global_cpi", "value", pixel_budget=8, semantic_type="rate")

    assert level[0]["resolution"] == "yearly"
    assert rate[0]["resolution"] == "yearly"
    assert level[0]["value"] == pytest.approx(464.0)
    assert rate[0]["value"] == pytest.approx((100.0 + 464.0) / 2.0)
    store.close()


def test_history_manifest_rejects_unrelated_store(tmp_path) -> None:
    first = EconomicDataStore(tmp_path / "first.duckdb")
    second = EconomicDataStore(tmp_path / "second.duckdb")
    if not first.enabled or not second.enabled:
        pytest.skip("DuckDB unavailable")
    with pytest.raises(ValueError, match="history ID"):
        second.bind_history_manifest(first.history_manifest())
    first.close()
    second.close()


def test_shock_state_persists_then_recovers_deterministically() -> None:
    state = SimpleNamespace(datum=datetime(1990, 1, 1), economic_shocks=[])
    add_shock(state, shock_id="oil-1", shock_type="supply", target="CL", magnitude=-0.5, duration_days=10)

    assert shock_multiplier(state, "supply", "CL") == pytest.approx(0.5)
    state.datum += timedelta(days=5)
    assert 0.5 < shock_multiplier(state, "supply", "CL") < 1.0
    state.datum += timedelta(days=6)
    assert shock_multiplier(state, "supply", "CL") == pytest.approx(1.0)


def test_crypto_initialization_does_not_grow_an_uneven_full_universe() -> None:
    state = SimpleNamespace(kryptos={})
    ensure_crypto_universe(state)
    moved = next(iter(state.kryptos.values()))
    moved["task_type"] = next(code for code in CRYPTO_TASK_TYPES if code != moved["task_type"])

    created = ensure_crypto_universe(state)

    assert created == []
    assert len(state.kryptos) == TARGET_CRYPTO_COUNT


def test_crypto_migration_trims_accidental_growth_and_stale_fund_reference() -> None:
    state = SimpleNamespace(kryptos={}, depot={}, perpetuals={}, fonds={})
    ensure_crypto_universe(state)
    extra_a = dict(next(iter(state.kryptos.values())))
    extra_b = dict(next(iter(state.kryptos.values())))
    extra_a.update({"market_share": 0.0, "kurs": 1.0})
    extra_b.update({"market_share": 0.0, "kurs": 1.1})
    state.kryptos["XTRA"] = extra_a
    state.kryptos["XTRB"] = extra_b
    state.fonds = {"F": {"underlyings": [{"ticker": "XTRA"}, {"ticker": next(iter(state.kryptos))}]}}

    ensure_crypto_universe(state)

    assert len(state.kryptos) == TARGET_CRYPTO_COUNT
    assert all(entry["ticker"] in state.kryptos for entry in state.fonds["F"]["underlyings"])


def test_input_cost_spread_uses_modeled_output_and_input_price_indexes() -> None:
    state = SimpleNamespace(
        processed_products={
            "AIRPL": {"price_index": 120.0, "shortage": 0.0},
            "ALLOY": {"price_index": 100.0}, "ECOMP": {"price_index": 100.0},
            "SEMI": {"price_index": 100.0}, "MACH": {"price_index": 100.0},
            "FUEL": {"price_index": 100.0}, "ELC": {"price_index": 100.0},
        },
        rohstoffe={"ALU": {"kurs": 100.0}},
    )
    product: dict = {"output_code": "AIRPL"}

    initial = _input_cost_spread_price(state, product)
    assert _input_cost_spread_price(state, product) == pytest.approx(initial)
    state.processed_products["AIRPL"]["price_index"] = 130.0
    stronger_output = _input_cost_spread_price(state, product)
    state.rohstoffe["ALU"]["kurs"] = 180.0
    dearer_inputs = _input_cost_spread_price(state, product)

    assert initial > 100.0
    assert stronger_output > initial
    assert 1.0 <= dearer_inputs < stronger_output


def test_paired_oil_shock_reduces_supply_and_raises_price_pressure(tmp_path) -> None:
    root = __import__("pathlib").Path(__file__).resolve().parents[1]

    def run(name: str, shocked: bool) -> list[tuple[float, float, float]]:
        random.seed(707)
        np.random.seed(707)
        runtime = IntegratedRuntime(root, data_dir=tmp_path / name)
        runtime.data_store.enabled = False
        try:
            if shocked:
                add_shock(runtime.daten, shock_id="oil", shock_type="supply", target="CL", magnitude=-0.5, duration_days=10)
            result = []
            for _ in range(14):
                runtime.advance_day()
                oil = runtime.daten.rohstoffe["CL"]
                result.append((float(oil["supply"]), float(oil["shortage"]), float(oil["price_pressure"])))
            return result
        finally:
            runtime.close()

    baseline = run("baseline", False)
    shocked = run("shock", True)
    try:
        assert shocked[5][0] < baseline[5][0]
        assert shocked[5][1] > baseline[5][1]
        assert shocked[5][2] > baseline[5][2]
        assert shocked[-1][0] > shocked[8][0]  # recovery after the finite shock
    finally:
        # IntegratedRuntime deliberately owns the legacy module as a singleton.
        # Leave it in a fresh-world state so this test remains order-independent.
        clean_runtime = IntegratedRuntime(root, data_dir=tmp_path / "clean")
        clean_runtime.close()
