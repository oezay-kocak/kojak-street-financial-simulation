"""Activate a genuine old bundle in a disposable copy without rewriting history."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/workforce-implementation"
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]


def main():
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture, encode
    from kojakstreet.core.established_world import read_compressed_checkpoint, validate_bundle
    from kojakstreet.core.history import ECONOMIC_MODEL_VERSION, LEGACY_ECONOMIC_MODEL_VERSION

    source = OUT / "legacy-established-source-v1/bundle"
    target = OUT / "legacy-established-reader-v1"
    assert source.resolve().is_relative_to(OUT.resolve()) and target.resolve().is_relative_to(OUT.resolve())
    assert not target.exists()
    original_metadata = validate_bundle(source)
    old = read_compressed_checkpoint(source / "checkpoint.json.gz")
    assert old["save_version"] == 7
    shutil.copytree(source, target)
    runtime = IntegratedRuntime.open_world_bundle(ROOT, target)
    try:
        actual = capture(runtime.daten)
        for country, macro in actual["checkpoint"]["makro"].items():
            assert macro["workforce"]["activated_on"] == runtime.daten.datum.date().isoformat()
            assert macro["workforce"]["provenance"] == "legacy_activation"
            assert macro["workforce"]["population_interval_years"] == 0
            comparable = {k: v for k, v in macro.items() if k not in {"workforce", "birth_rate", "death_rate"}}
            assert encode(comparable) == encode(old["checkpoint"]["makro"][country])
        for book in ("aktien", "rohstoffe", "kryptos", "fonds", "indizes", "derivatives", "depot", "forex_depot", "kredite", "perpetuals"):
            assert encode(actual["checkpoint"][book]) == encode(old["checkpoint"][book]), book
        assert encode(actual["rng"]) == encode(old["rng"])
        metadata = runtime.daten.world_generation
        assert metadata["economic_model_version"] == LEGACY_ECONOMIC_MODEL_VERSION
        assert metadata["active_economic_model_version"] == ECONOMIC_MODEL_VERSION
        runtime.data_store.flush()
        raw = runtime.data_store._connection
        assert raw.execute("SELECT count(*) FROM country_workforce_monthly").fetchone()[0] == 0
        assert raw.execute("SELECT count(*) FROM country_workforce_current").fetchone()[0] == 20
        assert raw.execute("SELECT count(*) FROM history_aggregate WHERE source_table='country_workforce_monthly'").fetchone()[0] == 0
        manifest = runtime.data_store.history_manifest()
        assert manifest["history_id"] == old["analytics_session"]["manifest"]["history_id"]
        assert manifest["origin"]["origin_economic_model_version"] == LEGACY_ECONOMIC_MODEL_VERSION
        result = {"passed": True, "activation_date": runtime.daten.datum.isoformat(),
                  "history_manifest": manifest, "country_roots_current": 20,
                  "backfilled_rows": 0, "world_player_rng_preserved": True}
        (target / "probe-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        runtime.close()
    assert validate_bundle(source) == original_metadata


if __name__ == "__main__":
    main()
