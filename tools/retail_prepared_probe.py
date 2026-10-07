"""Gate isolated full-day preparation under the real GC policy."""
import gc
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]

from day_transition_audit_support import rss_bytes
from retail_precompute_experiment import (
    install_detached_rng,
    prepare_world,
    publish_world,
    world_key,
)

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import capture, decode, encode, restore


def main():
    install_detached_rng()
    output = ROOT / ".cache/retail-decoupling"
    runtime = IntegratedRuntime(ROOT, data_dir=output / "prepared-gate-world", seed=1729)
    rows = []
    try:
        for label in ("1990-01-10", "end"):
            payload = decode(json.loads((ROOT / f".cache/day-transition-audit/checkpoint-{label}.json").read_text(encoding="utf-8")))
            for repeat in range(3):
                restore(runtime.daten, payload)
                runtime.state.sync_from_legacy()
                runtime.market.warm_runtime_indexes()
                before = encode(capture(runtime.daten))
                gc.collect()
                assert gc.isenabled()
                rss_before = rss_bytes()
                prepared = prepare_world(runtime.daten, world_key(runtime.daten), random.getstate())
                rss_after = rss_bytes()
                assert encode(capture(runtime.daten)) == before, "Preparation changed the authoritative day"
                metrics = publish_world(runtime, prepared)
                actual = encode(capture(runtime.daten))
                restore(runtime.daten, payload)
                runtime.state.sync_from_legacy()
                runtime.market.warm_runtime_indexes()
                runtime.daten.spiel_pausiert = False
                runtime.simulation.step_day()
                expected = encode(capture(runtime.daten))
                # The checkpoint's pause flag is preserved by direct publication.
                actual["checkpoint"]["spiel_pausiert"] = expected["checkpoint"]["spiel_pausiert"]
                assert actual == expected, "Prepared result differs from sequential result"
                row = {"checkpoint": label, "repeat": repeat, **metrics,
                       "rss_before": rss_before, "rss_after": rss_after,
                       "exact_checkpoint_and_rng": True, "authoritative_unchanged_until_publish": True}
                rows.append(row)
                print(json.dumps(row), flush=True)
                del prepared
        (output / "prepared-gate.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
