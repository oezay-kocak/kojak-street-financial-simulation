from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.established_world import (
    PLAYER_STARTING_CASH_GD,
    WorldGenerationConfig,
    WorldMode,
    capture_world_payload,
    read_compressed_checkpoint,
    record_extreme_tail_crossings,
    reset_player_state,
    sanity_gate,
    validate_bundle,
    write_compressed_checkpoint,
)
from kojakstreet.world_generator import generate


def _world_signature(runtime: IntegratedRuntime) -> tuple:
    state = runtime.daten
    companies = tuple(
        (ticker, round(float(asset["kurs"]), 8), round(float(asset.get("revenue", 0.0)), 4), asset.get("rating"))
        for ticker, asset in sorted(state.aktien.items())
    )
    macro = tuple(
        (country, round(float(row["bip_abs"]), 5), round(float(row["debt_to_gdp"]), 8), row.get("rating"))
        for country, row in sorted(state.makro.items())
    )
    return state.datum.isoformat(), companies, macro, len(state.kryptos), len(state.bond_market)


@pytest.mark.parametrize("days", [30, 90])
def test_generation_flush_batching_preserves_economic_trajectory(tmp_path, days) -> None:
    root = Path(__file__).resolve().parents[1]
    normal = IntegratedRuntime(root, data_dir=tmp_path / f"normal-{days}", seed=90210, flush_interval_days=30)
    try:
        normal.advance_days(days)
        expected = _world_signature(normal)
    finally:
        normal.close()

    generated = IntegratedRuntime(root, data_dir=tmp_path / f"generated-{days}", seed=90210, flush_interval_days=90)
    try:
        generated.advance_days(days)
        actual = _world_signature(generated)
    finally:
        generated.close()

    assert actual == expected


def test_established_config_separates_metadata_from_trajectory() -> None:
    first = WorldGenerationConfig(mode=WorldMode.ESTABLISHED, seed=7, prehistory_years=50, world_name="A").normalized()
    second = WorldGenerationConfig(mode=WorldMode.ESTABLISHED, seed=7, prehistory_years=50, world_name="B").normalized()

    assert first.trajectory_identity() == second.trajectory_identity()
    assert first.world_id != second.world_id
    assert WorldGenerationConfig(mode=WorldMode.GENESIS, seed=7, prehistory_years=100).normalized().prehistory_years == 0


def test_player_reset_does_not_reset_world(tmp_path) -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1], data_dir=tmp_path, seed=8)
    try:
        runtime.advance_days(2)
        world_price = runtime.daten.aktien[next(iter(runtime.daten.aktien))]["kurs"]
        world_date = runtime.daten.datum
        runtime.daten.depot = {"TEST": {"stueck": 5}}
        runtime.daten.perpetuals = {"P": {"margin": 100.0}}
        reset_player_state(runtime.daten)

        assert runtime.daten.datum == world_date
        assert runtime.daten.aktien[next(iter(runtime.daten.aktien))]["kurs"] == world_price
        assert runtime.daten.depot == {}
        assert runtime.daten.perpetuals == {}
        assert runtime.daten.forex_depot["GD"] == PLAYER_STARTING_CASH_GD
        assert sum(runtime.daten.kredite.values()) == 0.0
    finally:
        runtime.close()
def test_tail_recorder_only_records_first_crossing(tmp_path) -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1], data_dir=tmp_path, seed=9)
    try:
        ticker, company = next(iter(runtime.daten.aktien.items()))
        initial_max = max(float(asset.get("cash_reserves", 0.0)) for asset in runtime.daten.aktien.values())
        company["cash_reserves"] = initial_max + 2.0
        thresholds = {"cash_reserves": initial_max + 1.0}
        first = record_extreme_tail_crossings(runtime.daten, thresholds)
        second = record_extreme_tail_crossings(runtime.daten, thresholds)
        assert len(first) == 1
        assert first[0]["ticker"] == ticker
        assert second == []
    finally:
        runtime.close()
def test_compressed_checkpoint_is_exact_and_smaller(tmp_path) -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1], data_dir=tmp_path / "runtime", seed=10)
    try:
        runtime.advance_days(2)
        runtime.data_store.flush()
        config = WorldGenerationConfig(mode=WorldMode.ESTABLISHED, seed=10, prehistory_years=50).normalized()
        runtime.daten.world_generation = asdict(config)
        payload = capture_world_payload(runtime.daten, runtime.data_store.checkpoint_session(), config)
        metrics = write_compressed_checkpoint(tmp_path / "checkpoint.json.gz", payload)
        restored = read_compressed_checkpoint(tmp_path / "checkpoint.json.gz")

        assert restored["checkpoint"]["datum"] == payload["checkpoint"]["datum"]
        assert restored["rng"]["python"] == payload["rng"]["python"]
        assert metrics["bytes"] > 0
        assert len(metrics["sha256"]) == 64
    finally:
        runtime.close()


def test_sanity_gate_rejects_invalid_crypto_count(tmp_path) -> None:
    runtime = IntegratedRuntime(Path(__file__).resolve().parents[1], data_dir=tmp_path, seed=11)
    try:
        assert sanity_gate(runtime.daten, runtime.data_store.history_manifest())["passed"]
        runtime.daten.kryptos.pop(next(iter(runtime.daten.kryptos)))
        result = sanity_gate(runtime.daten, runtime.data_store.history_manifest())
        assert not result["passed"]
        assert "invalid crypto universe size" in result["errors"]
    finally:
        runtime.close()


def test_generated_bundle_roundtrip_restores_world_and_player_baseline(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = generate(root, tmp_path / "world", seed=12, years=50, diagnostic_days=2)
    metadata = validate_bundle(bundle)
    mismatched = json.loads(json.dumps(metadata))
    mismatched["history_manifest"]["history_id"] = "unrelated-history"
    (bundle / "world.json").write_text(json.dumps(mismatched), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest mismatch"):
        validate_bundle(bundle)
    (bundle / "world.json").write_text(json.dumps(metadata), encoding="utf-8")
    runtime = IntegratedRuntime.open_world_bundle(root, bundle)
    try:
        assert runtime.daten.datum.isoformat() == "1990-01-03T00:00:00"
        assert runtime.daten.forex_depot["GD"] == PLAYER_STARTING_CASH_GD
        assert runtime.daten.depot == {}
        assert runtime.daten.perpetuals == {}
        assert runtime.data_store.history_manifest() == metadata["history_manifest"]
        assert runtime.daten.world_generation["seed"] == 12
    finally:
        runtime.close()
    # IntegratedRuntime deliberately owns the legacy module as a process
    # singleton. Restore a fresh module for tests that inspect startup data.
    clean = IntegratedRuntime(root, data_dir=tmp_path / "clean")
    clean.close()


def test_fast_history_is_deterministic_seeded_and_reaches_player_start(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]

    def signature(seed: int, name: str) -> tuple:
        bundle = generate(root, tmp_path / name, seed=seed, years=50, burn_in_days=5)
        metadata = validate_bundle(bundle)
        runtime = IntegratedRuntime.open_world_bundle(root, bundle)
        try:
            points = runtime.data_store.history_series(
                "asset_daily",
                "ticker",
                f"Stock:{next(iter(runtime.daten.aktien))}",
                "price",
                pixel_budget=1200,
                semantic_type="price",
            )
            assert metadata["generation"]["strategy"] == "fast_history_v2"
            assert metadata["generation"]["daily_burn_in_days"] == 5
            assert points[0]["date"][:4] == "1990"
            assert points[-1]["date"][:4] == "2040"
            assert sanity_gate(runtime.daten, runtime.data_store.history_manifest())["passed"]
            return _world_signature(runtime)
        finally:
            runtime.close()

    first = signature(4242, "first")
    second = signature(4242, "second")
    different = signature(4243, "different")

    assert first == second
    assert first != different


def test_fast_history_world_survives_post_generation_and_save_load(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    bundle = generate(root, tmp_path / "fast-world", seed=5150, years=50, burn_in_days=10)
    runtime = IntegratedRuntime.open_world_bundle(root, bundle)
    try:
        runtime.advance_days(30)
        before = _world_signature(runtime)
        runtime.save_game()
        runtime.advance_days(2)
        runtime.load_game()
        assert _world_signature(runtime) == before
        assert sanity_gate(runtime.daten, runtime.data_store.history_manifest())["passed"]
    finally:
        runtime.close()
