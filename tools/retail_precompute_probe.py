"""Measure detached-copy cost without publishing or changing a player's world."""

import gc
import json
import statistics
import sys
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]
from day_transition_audit_support import rss_bytes

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.asset_market_engine import AssetMarketEngine
from kojakstreet.core.bond_portfolio_engine import BondPortfolioEngine
from kojakstreet.core.checkpoints import FIELDS, decode, restore
from kojakstreet.core.macro_engine import MacroEngine
from kojakstreet.core.production_engine import ProductionEngine
from kojakstreet.core.simulation import DailySimulation
from kojakstreet.core.simulation_state import SimulationState

PLAYER_FIELDS = {
    "bargeld", "depot", "perpetuals", "anleihen", "kredite", "forex_depot",
    "DEPOT_VERMOEGEN_HISTORIE", "realisierte_guv_historie", "player_rng_state",
    "PLAYER_NEWS_SPEICHER", "spiel_pausiert", "SPIEL_AKTIV", "turbo_modus",
    "intervall", "anzeige_waehrung",
}


def clone_world(daten):
    """Measurement-only isolated graph; never publish or enable speculation."""
    values = deepcopy({key: getattr(daten, key) for key in FIELDS - PLAYER_FIELDS if hasattr(daten, key)})
    values.update(
        depot={}, perpetuals={}, anleihen=[], kredite={}, forex_depot={}, bargeld=0.0,
        DEPOT_VERMOEGEN_HISTORIE=[], realisierte_guv_historie=[],
        SPIEL_AKTIV=True, spiel_pausiert=False,
    )
    namespace = SimpleNamespace(**values)
    state = SimulationState.from_legacy(namespace)
    market = AssetMarketEngine(state)
    simulation = DailySimulation(state, MacroEngine(state), market, BondPortfolioEngine(state), ProductionEngine(state))
    market.warm_runtime_indexes()
    return namespace, state, simulation


def main():
    output = ROOT / ".cache/retail-decoupling"
    runtime = IntegratedRuntime(ROOT, data_dir=output / "clone-probe-world", seed=1729)
    results = {}
    try:
        for label in ("1990-01-10", "end"):
            payload = decode(
                json.loads(
                    (ROOT / f".cache/day-transition-audit/checkpoint-{label}.json").read_text(encoding="utf-8")
                )
            )
            restore(runtime.daten, payload)
            runtime.state.sync_from_legacy()
            runtime.market.warm_runtime_indexes()
            samples = []
            for _ in range(5):
                gc.collect()
                before = rss_bytes()
                started = time.perf_counter()
                gc.disable()
                try:
                    clone = clone_world(runtime.daten)
                finally:
                    gc.enable()
                elapsed = (time.perf_counter() - started) * 1000
                after = rss_bytes()
                samples.append(
                    {
                        "clone_ms": elapsed,
                        "rss_before": before,
                        "rss_after": after,
                        "increment_bytes": after - before,
                        "world_stocks": len(clone[0].aktien),
                    }
                )
                del clone
            results[label] = samples
            print(
                label,
                "copy median ms",
                round(statistics.median(s["clone_ms"] for s in samples), 2),
                "increment MiB",
                round(max(s["increment_bytes"] for s in samples) / 1048576, 2),
                flush=True,
            )
        (output / "clone-probe.json").write_text(json.dumps(results, indent=2))
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
