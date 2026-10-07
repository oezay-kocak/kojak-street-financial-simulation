"""Read a genuine version-8 Established bundle through a disposable copy."""
import gc
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
OUT = ROOT / ".cache/politics-implementation"


def digest(value):
    from kojakstreet.core.checkpoints import encode
    result = hashlib.sha256()
    for chunk in json.JSONEncoder(sort_keys=True, ensure_ascii=False).iterencode(encode(value)):
        result.update(chunk.encode())
    return result.hexdigest()


def main():
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture
    from kojakstreet.core.established_world import file_sha256, read_compressed_checkpoint
    source = OUT / "legacy-sealed-reference-v8/bundle"
    target = OUT / "legacy-established-reader-final-v2"
    assert not target.exists()
    hashes = {p.name: file_sha256(p) for p in source.iterdir() if p.is_file()}
    old = read_compressed_checkpoint(source / "checkpoint.json.gz")
    assert old["save_version"] == 8
    keys = ("makro", "aktien", "rohstoffe", "kryptos", "fonds", "indizes", "derivatives",
            "bond_market", "bond_market_archive", "depot", "forex_depot", "kredite", "perpetuals",
            "anleihen", "bargeld", "world_generation", "datum")
    expected = {key: digest(old["checkpoint"][key]) for key in keys}
    expected_rng = digest(old["rng"])
    expected_manifest = old["analytics_session"]["manifest"]
    del old
    gc.collect()
    shutil.copytree(source, target)
    rt = IntegratedRuntime.open_world_bundle(ROOT, target)
    try:
        actual = capture(rt.daten)
        activation = rt.daten.datum.date().isoformat()
        for macro in actual["checkpoint"]["makro"].values():
            politics = macro.pop("politics")
            assert politics["activated_on"] == activation
            assert politics["provenance"] == "legacy_activation"
            assert politics["last_election"] is None and politics["latest_result"] is None
            assert politics["premium"] == 0
            assert politics["next_election"] > activation
        assert actual["checkpoint"]["world_generation"].pop("politics_activated_on") == activation
        assert expected == {key: digest(actual["checkpoint"][key]) for key in keys}
        assert expected_rng == digest(actual["rng"])
        rt.data_store.flush()
        manifest = rt.data_store.history_manifest()
        assert manifest["history_id"] == expected_manifest["history_id"]
        if "origin" in expected_manifest:
            assert manifest["origin"] == expected_manifest["origin"]
        else:
            assert manifest['economic_model_version'] == expected_manifest['economic_model_version']
            assert manifest['origin']['origin_history_schema_version'] == str(expected_manifest['history_schema_version'])
        counts = {table: rt.data_store._connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in ("country_politics_current", "country_politics_monthly", "politics_events")}
        assert counts == {"country_politics_current": 20, "country_politics_monthly": 0, "politics_events": 20}
        result = {"passed": True, "activation_date": activation, "original_save_version": 8,
                  "economy_player_rng_exact": True, "history_origin_exact": True, "counts": counts}
        (target / "probe-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        rt.close()
    assert hashes == {p.name: file_sha256(p) for p in source.iterdir() if p.is_file()}


if __name__ == "__main__":
    main()
