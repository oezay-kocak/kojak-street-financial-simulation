"""Production-faithful hot-state cardinality soak for Deep History evidence."""

from __future__ import annotations

import json
import random
import tempfile
import ctypes
import os
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import capture, encode


def _measure(runtime: IntegratedRuntime, day: int, elapsed: float) -> dict[str, object]:
    daten = runtime.daten
    universes = [daten.aktien, daten.rohstoffe, daten.kryptos, daten.fonds, daten.indizes, daten.derivatives]
    price_lengths = [len(asset.get("historie", [])) for universe in universes for asset in universe.values()]
    forex_lengths = [len(rows) for rows in daten.FOREX_PAARE_HISTORIE.values()]
    metric_lengths = [
        len(asset.get(key, []))
        for universe in (daten.rohstoffe, daten.processed_products)
        for asset in universe.values()
        for key in ("supply_history", "demand_history", "inventory_history", "price_pressure_history")
    ]
    return {
        "day": day,
        "simulation_date": daten.datum.strftime("%Y-%m-%d"),
        "wall_seconds": round(elapsed, 3),
        "rss_bytes": _rss_bytes(),
        "asset_price_points_total": sum(price_lengths),
        "asset_price_points_max": max(price_lengths, default=0),
        "forex_points_total": sum(forex_lengths),
        "forex_points_max": max(forex_lengths, default=0),
        "product_metric_points_total": sum(metric_lengths),
        "product_metric_points_max": max(metric_lengths, default=0),
        "portfolio_points": len(daten.DEPOT_VERMOEGEN_HISTORIE),
        "gli_points": len(daten.GLI_HISTORIE),
        "global_macro_points_max": max((len(rows) for rows in daten.GLOBAL_MACRO_HISTORIE.values()), default=0),
        "session_product_rows": len(runtime.data_store._session_rows.get("product_daily", [])),
        "session_bond_rows": len(runtime.data_store._session_rows.get("bond_daily", [])),
    }


def _rss_bytes() -> int:
    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return int(counters.WorkingSetSize)
    try:
        value = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", f"(Get-Process -Id {os.getpid()}).WorkingSet64"],
            text=True,
        )
        return int(value.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "docs" / "audit-data" / "deep-history-v1"
    output_dir.mkdir(parents=True, exist_ok=True)
    random.seed(811)
    np.random.seed(811)
    started = perf_counter()
    with tempfile.TemporaryDirectory(prefix="kojak-soak-") as directory:
        runtime = IntegratedRuntime(root, data_dir=Path(directory))
        runtime.data_store.enabled = False
        samples = []
        try:
            for day in range(1, 1101):
                runtime.advance_day()
                if day % 100 == 0:
                    print(f"day={day}", flush=True)
                if day in {520, 900, 1040, 1100}:
                    samples.append(_measure(runtime, day, perf_counter() - started))
            evidence_path = output_dir / "retention-measurements.json"
            evidence_path.write_text(json.dumps({"schema_version": 1, "seed": 811, "horizon_days": 1100, "samples": samples, "checkpoint_json_bytes": None}, indent=2), encoding="utf-8")
            checkpoint_bytes = len(json.dumps(encode(capture(runtime.daten)), separators=(",", ":"), allow_nan=False).encode("utf-8"))
        finally:
            runtime.close()
    payload = {
        "schema_version": 1,
        "seed": 811,
        "store_mode": "disabled_after_runtime_initialization",
        "horizon_days": 1100,
        "samples": samples,
        "checkpoint_json_bytes": checkpoint_bytes,
        "cardinality_bounded": all(
            sample["asset_price_points_max"] <= 1040
            and sample["forex_points_max"] <= 520
            and sample["portfolio_points"] <= 520
            and sample["product_metric_points_max"] <= 900
            for sample in samples
        ),
    }
    evidence_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
