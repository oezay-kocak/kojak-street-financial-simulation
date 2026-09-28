"""Generate compact deterministic evidence for the contained integrity fixes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import tempfile

import numpy as np


def _oil_snapshot(runtime) -> dict[str, float]:
    oil = runtime.daten.rohstoffe["CL"]
    return {
        key: float(oil.get(key, 0.0))
        for key in ("supply", "shortage", "price_pressure", "kurs")
    }


def shock_comparison(root: Path, output: Path) -> dict:
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.shocks import add_shock

    series = {}
    with tempfile.TemporaryDirectory(prefix="kojak-deep-history-shock-") as parent:
        for name, shocked in (("baseline", False), ("supply_shock", True)):
            random.seed(707)
            np.random.seed(707)
            runtime = IntegratedRuntime(root, data_dir=Path(parent) / name)
            runtime.data_store.enabled = False
            try:
                if shocked:
                    add_shock(
                        runtime.daten,
                        shock_id="oil-evidence",
                        shock_type="supply",
                        target="CL",
                        magnitude=-0.5,
                        duration_days=10,
                        decay="linear",
                    )
                observations = []
                for day in range(1, 15):
                    runtime.advance_day()
                    observations.append({"day": day, **_oil_snapshot(runtime)})
                series[name] = observations
            finally:
                runtime.close()
    payload = {
        "schema_version": 1,
        "seed": 707,
        "horizon_days": 14,
        "store_mode": "disabled_after_runtime_initialization",
        "intervention": {"type": "supply", "target": "CL", "magnitude": -0.5, "duration_days": 10, "decay": "linear"},
        "observations": series,
        "acceptance": {
            "day_6_supply_lower": series["supply_shock"][5]["supply"] < series["baseline"][5]["supply"],
            "day_6_shortage_higher": series["supply_shock"][5]["shortage"] > series["baseline"][5]["shortage"],
            "day_6_pressure_higher": series["supply_shock"][5]["price_pressure"] > series["baseline"][5]["price_pressure"],
            "post_shock_supply_recovery": series["supply_shock"][-1]["supply"] > series["supply_shock"][8]["supply"],
        },
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def crypto_invariant(output: Path) -> dict:
    from types import SimpleNamespace
    from kojakstreet.core.cryptos import TARGET_CRYPTO_COUNT, ensure_crypto_universe

    state = SimpleNamespace(kryptos={}, depot={}, perpetuals={}, fonds={})
    ensure_crypto_universe(state)
    initial = len(state.kryptos)
    moved = next(iter(state.kryptos.values()))
    original_task = moved["task_type"]
    moved["task_type"] = next(item["task_type"] for item in state.kryptos.values() if item["task_type"] != original_task)
    created_after_imbalance = ensure_crypto_universe(state)
    after_imbalance = len(state.kryptos)
    for ticker in ("XTRA", "XTRB"):
        extra = dict(next(iter(state.kryptos.values())))
        extra.update({"ticker": ticker, "market_share": 0.0, "kurs": 1.0})
        state.kryptos[ticker] = extra
    state.fonds = {"F": {"underlyings": [{"ticker": "XTRA"}, {"ticker": next(iter(state.kryptos))}]}}
    ensure_crypto_universe(state)
    payload = {
        "schema_version": 1,
        "target": TARGET_CRYPTO_COUNT,
        "initial_count": initial,
        "uneven_full_count": after_imbalance,
        "created_after_imbalance": created_after_imbalance,
        "post_migration_count": len(state.kryptos),
        "fund_references_valid": all(item["ticker"] in state.kryptos for item in state.fonds["F"]["underlyings"]),
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shock = shock_comparison(root, output / "shock-comparison.json")
    crypto = crypto_invariant(output / "crypto-invariant-results.json")
    print(json.dumps({"shock": shock["acceptance"], "crypto": crypto}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
