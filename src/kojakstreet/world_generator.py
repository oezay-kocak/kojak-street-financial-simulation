"""Isolated command-line worker for hybrid Established Worlds."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path


def _emit(stage: str, **payload: object) -> None:
    print(json.dumps({"stage": stage, **payload}, separators=(",", ":")), flush=True)


def _peak_rss_bytes() -> int | None:
    """Best-effort peak resident memory without adding a runtime dependency."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in (
                        "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                        "PagefileUsage", "PeakPagefileUsage",
                    )
                ]

            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            query = getattr(ctypes.windll.kernel32, "K32GetProcessMemoryInfo", None)
            if query is None:
                query = ctypes.windll.psapi.GetProcessMemoryInfo
            query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            query.restype = wintypes.BOOL
            if query(handle, ctypes.byref(counters), counters.cb):
                return int(counters.PeakWorkingSetSize)
        except (AttributeError, OSError, TypeError, ValueError, ctypes.ArgumentError):
            return None
    try:
        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return peak if sys.platform == "darwin" else peak * 1024
    except (ImportError, OSError):
        return None


def generate(
    project_root: Path,
    output: Path,
    seed: int,
    years: int,
    world_name: str = "",
    *,
    diagnostic_days: int | None = None,
    burn_in_days: int = 365,
    production_equivalent: bool = False,
) -> Path:
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.established_world import (
        WorldGenerationConfig,
        WorldMode,
        build_bundle_metadata,
        capture_world_payload,
        record_extreme_tail_crossings,
        reset_player_state,
        sanity_gate,
        write_compressed_checkpoint,
    )
    from kojakstreet.core.fast_history import generate_coarse_history

    config = WorldGenerationConfig(
        mode=WorldMode.ESTABLISHED,
        seed=seed,
        prehistory_years=years,
        world_name=world_name,
    ).normalized()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"World bundle already exists: {output}")
    partial = output.parent / f".{output.name}.{uuid.uuid4().hex}.partial"
    partial.mkdir()
    runtime = None
    started = time.perf_counter()
    started_cpu = time.process_time()
    try:
        _emit("initialization", config=asdict(config), percent=0.0)
        runtime = IntegratedRuntime(project_root, data_dir=partial, seed=seed, flush_interval_days=90)
        use_full_daily = production_equivalent or diagnostic_days is not None
        target_days = years * 365 if diagnostic_days is None else max(1, int(diagnostic_days))
        progress_interval = 30
        if use_full_daily:
            for day in range(1, target_days + 1):
                runtime.advance_day()
                record_extreme_tail_crossings(runtime.daten)
                if day % progress_interval == 0 or day == target_days:
                    elapsed = time.perf_counter() - started
                    rate = day / elapsed if elapsed else 0.0
                    remaining = (target_days - day) / rate if rate else None
                    _emit(
                        "simulation",
                        phase="production_equivalent",
                        days_completed=day,
                        target_days=target_days,
                        years_completed=day / 365.0,
                        target_years=years,
                        simulation_date=runtime.daten.datum.isoformat(),
                        percent=day / target_days * 100.0,
                        elapsed_seconds=elapsed,
                        eta_seconds=remaining,
                    )
            daily_days = target_days
            coarse_buckets = 0
        else:
            def coarse_progress(resolution: str, completed: int, total: int, simulation_date) -> None:
                _emit(
                    "coarse_history",
                    phase=resolution,
                    buckets_completed=completed,
                    target_buckets=total,
                    target_years=years,
                    simulation_date=simulation_date.isoformat(),
                    percent=(completed / max(1, total)) * 35.0,
                    elapsed_seconds=time.perf_counter() - started,
                )

            plan = generate_coarse_history(
                runtime,
                seed,
                years,
                burn_in_days=burn_in_days,
                progress=coarse_progress,
            )
            coarse_buckets = (plan.yearly_end.year - plan.start.year + 1) + (
                (plan.monthly_end.year - plan.yearly_end.year - 1) * 12 + plan.monthly_end.month
            )
            daily_days = plan.daily_days
            burn_started = time.perf_counter()
            for day in range(1, daily_days + 1):
                runtime.advance_day()
                record_extreme_tail_crossings(runtime.daten)
                if day % progress_interval == 0 or day == daily_days:
                    elapsed_burn = time.perf_counter() - burn_started
                    rate = day / elapsed_burn if elapsed_burn else 0.0
                    _emit(
                        "daily_burn_in",
                        phase="daily_burn_in",
                        days_completed=day,
                        target_days=daily_days,
                        years_completed=years - ((daily_days - day) / 365.0),
                        target_years=years,
                        simulation_date=runtime.daten.datum.isoformat(),
                        percent=35.0 + (day / daily_days) * 63.0,
                        elapsed_seconds=time.perf_counter() - started,
                        eta_seconds=(daily_days - day) / rate if rate else None,
                    )
        simulation_seconds = time.perf_counter() - started
        _emit("compaction", percent=99.0)
        runtime.data_store.flush()
        manifest = runtime.data_store.history_manifest()
        gate = sanity_gate(runtime.daten, manifest)
        _emit("validation", sanity_gate=gate, percent=99.2)
        if not gate["passed"]:
            raise ValueError("Established World failed sanity gate: " + "; ".join(gate["errors"]))
        reset_player_state(runtime.daten)
        runtime.daten.world_generation = asdict(config)
        runtime.data_store.record_day(runtime.state, current_scope="full", flush=True)
        manifest = runtime.data_store.history_manifest()
        analytics = runtime.data_store.checkpoint_session()
        checkpoint_payload = capture_world_payload(runtime.daten, analytics, config)
        _emit("checkpoint", percent=99.5)
        checkpoint_metrics = write_compressed_checkpoint(partial / "checkpoint.json.gz", checkpoint_payload)
        runtime.close()
        runtime = None
        store_path = partial / "kojakstreet.duckdb"
        metadata = build_bundle_metadata(config, partial / "checkpoint.json.gz", store_path, manifest, gate)
        elapsed_seconds = time.perf_counter() - started
        metadata["generation"] = {
            "elapsed_seconds": elapsed_seconds,
            "simulation_seconds": simulation_seconds,
            "finalization_seconds": elapsed_seconds - simulation_seconds,
            "days_per_second": target_days / simulation_seconds if simulation_seconds else None,
            "simulated_years_per_minute": years / (simulation_seconds / 60.0) if simulation_seconds else None,
            "strategy": "production_equivalent" if use_full_daily else "fast_history_v3",
            "coarse_buckets": coarse_buckets,
            "daily_burn_in_days": daily_days,
            "process_cpu_seconds": time.process_time() - started_cpu,
            "cpu_to_wall_ratio": (time.process_time() - started_cpu) / elapsed_seconds if elapsed_seconds else None,
            "peak_rss_bytes": _peak_rss_bytes(),
            "store_bytes": store_path.stat().st_size,
            "checkpoint": checkpoint_metrics,
            "extreme_tail_events": len(checkpoint_payload["checkpoint"].get("extreme_tail_events", [])),
        }
        (partial / "world.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(partial, output)
        _emit("complete", percent=100.0, bundle=str(output), metadata=metadata)
        return output
    except BaseException:
        if runtime is not None:
            runtime.close()
        # A partial directory is deliberately never playable. It is removed on
        # ordinary failures; forced process termination may leave a .partial
        # directory that can be safely deleted or ignored on restart.
        shutil.rmtree(partial, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--years", type=int, choices=(50, 75, 100), required=True)
    parser.add_argument("--world-name", default="")
    args = parser.parse_args()
    try:
        generate(args.project_root.resolve(), args.output, args.seed, args.years, args.world_name)
    except Exception as exc:  # noqa: BLE001 - worker boundary reports every failure as JSON
        _emit("failed", error=str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
