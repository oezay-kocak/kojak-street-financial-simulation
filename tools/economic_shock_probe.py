"""Controlled impulse-response probes for the unmodified Kojak Street runtime.

Each scenario starts from the same seed and warm-up horizon.  Interventions are
direct, isolated state perturbations because the production runtime exposes no
public shock API.  Results therefore test propagation direction and persistence,
not calibrated shock magnitudes.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

import numpy as np


def _mean(rows, key: str) -> float:
    values = [float(row.get(key, 0.0)) for row in rows]
    return statistics.fmean(values) if values else 0.0


def snapshot(d: Any) -> dict[str, Any]:
    sectors = {}
    for sector in sorted({str(row.get("branche", "")) for row in d.aktien.values()}):
        rows = [row for row in d.aktien.values() if row.get("branche") == sector]
        sectors[sector] = _mean(rows, "kurs")
    oil = d.rohstoffe["CL"]
    return {
        "date": d.datum.strftime("%Y-%m-%d"),
        "macro": {
            "growth": _mean(d.makro.values(), "bip_prozent"),
            "inflation": _mean(d.makro.values(), "inflation"),
            "unemployment": _mean(d.makro.values(), "arbeitslosigkeit"),
            "policy_rate": _mean(d.makro.values(), "zins"),
            "debt_to_gdp": _mean(d.makro.values(), "debt_to_gdp"),
        },
        "market": {
            "mean_stock_price": _mean(d.aktien.values(), "kurs"),
            "vix": float(d.global_macro.get("vix", 0.0)),
            "regime": str(getattr(d, "market_regime", "Unknown")),
            "sectors": sectors,
        },
        "oil": {key: float(oil.get(key, 0.0)) for key in ("kurs", "supply", "demand", "inventories", "shortage", "price_pressure")},
    }


def oil_supply_shock(d: Any) -> None:
    oil = d.rohstoffe["CL"]
    for key in ("supply", "production", "inventories"):
        oil[key] = max(1.0, float(oil.get(key, 1.0)) * 0.50)


def policy_rate_shock(d: Any) -> None:
    for macro in d.makro.values():
        macro["zins"] = min(0.095, float(macro.get("zins", 0.035)) + 0.03)


def recession_shock(d: Any) -> None:
    for macro in d.makro.values():
        macro["bip_prozent"] = max(-0.06, float(macro.get("bip_prozent", 0.01)) - 0.04)


def risk_off_shock(d: Any) -> None:
    d.global_macro["vix"] = 55.0
    d.market_psychology.update({"risk_appetite": -2.0, "fear": 2.0, "liquidity_confidence": -1.5, "recession_fear": 2.0, "speculation": 0.0})


SCENARIOS: dict[str, Callable[[Any], None] | None] = {
    "baseline": None,
    "oil_supply_minus_50pct": oil_supply_shock,
    "policy_rate_plus_300bp": policy_rate_shock,
    "growth_minus_4pp": recession_shock,
    "risk_off_vix_55": risk_off_shock,
}


def run(project_root: Path, output: Path, seed: int, warmup_days: int, response_days: int) -> dict[str, Any]:
    sys.path[:0] = [str(project_root / "src"), str(project_root)]
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime

    checkpoints = sorted({1, min(30, response_days), response_days})
    results = {}
    with tempfile.TemporaryDirectory(prefix="kojak-shocks-") as parent:
        for name, intervention in SCENARIOS.items():
            random.seed(seed)
            np.random.seed(seed)
            runtime = IntegratedRuntime(project_root, data_dir=Path(parent) / name)
            runtime.data_store.enabled = False
            runtime.advance_days(warmup_days)
            before = snapshot(runtime.daten)
            if intervention is not None:
                intervention(runtime.daten)
            observations = {}
            elapsed = 0
            for target in checkpoints:
                runtime.advance_days(target - elapsed)
                elapsed = target
                observations[str(target)] = snapshot(runtime.daten)
            results[name] = {"before": before, "after": observations}
            runtime.close()
    payload = {
        "schema_version": 1,
        "seed": seed,
        "warmup_days": warmup_days,
        "response_days": response_days,
        "method": "Direct isolated state perturbations on deterministic IntegratedRuntime worlds; DuckDB recording disabled.",
        "limitations": "No public shock API exists. Magnitudes are diagnostic impulses, not empirically calibrated scenarios.",
        "scenarios": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=404)
    parser.add_argument("--warmup-days", type=int, default=180)
    parser.add_argument("--response-days", type=int, default=90)
    args = parser.parse_args()
    payload = run(args.project_root.resolve(), args.output.resolve(), args.seed, args.warmup_days, args.response_days)
    print(json.dumps({"seed": payload["seed"], "scenarios": list(payload["scenarios"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
