"""Line-delimited JSON worker owning the live IntegratedRuntime."""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import decode, restore
from kojakstreet.live_process import CURRENT_METHODS, economic_signature, game_state_payload


def _load_runtime(project_root: Path, data_dir: Path, bootstrap: Path) -> IntegratedRuntime:
    with bootstrap.open(encoding="utf-8") as stream:
        payload = decode(json.load(stream))
    seed = int(payload.get("checkpoint", {}).get("simulation_seed", 0) or 0)
    runtime = IntegratedRuntime(project_root, data_dir=data_dir, seed=seed)
    restore(runtime.daten, payload)
    runtime.state.sync_from_legacy()
    runtime.data_store.restore_checkpoint_session(payload.get("analytics_session", {}))
    runtime.market.warm_runtime_indexes()
    runtime.data_store.record_day(runtime.state, current_scope="full")
    bootstrap.unlink(missing_ok=True)
    return runtime


def _runtime_result(
    runtime: IntegratedRuntime,
    *,
    profile: str = "status",
    include_snapshot: bool = False,
    simulation_ms: float = 0.0,
) -> dict[str, Any]:
    delta = runtime.current_delta()
    snapshot_profile = profile if include_snapshot else "status"
    state = runtime.snapshot_for_view(snapshot_profile)
    current_rows = {
        table: getattr(runtime, method)()
        for table, method in CURRENT_METHODS.items()
        if table in delta.tables and hasattr(runtime, method)
    }
    return {
        "profile": snapshot_profile,
        "state": game_state_payload(state),
        "delta": {"version": delta.version, "date_text": delta.date_text, "tables": sorted(delta.tables)},
        "current_rows": current_rows,
        "simulation_ms": simulation_ms,
    }


def _execute(runtime: IntegratedRuntime, command: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    profile = str(arguments.get("profile", "status"))
    if command == "advance":
        started = time.perf_counter()
        for _ in range(max(0, int(arguments.get("steps", 1)))):
            runtime.advance_day()
        elapsed = (time.perf_counter() - started) * 1000.0
        return _runtime_result(
            runtime,
            profile=profile,
            include_snapshot=bool(arguments.get("force_snapshot", False)),
            simulation_ms=elapsed,
        ), False
    if command == "set_running":
        runtime.set_running(bool(arguments.get("running", False)))
        return {}, False
    if command == "save":
        runtime.save_game()
        return _runtime_result(runtime, profile="status"), False
    if command == "load":
        runtime.load_game()
        return _runtime_result(runtime, profile="full", include_snapshot=True), False
    if command == "validate_trade":
        validation = runtime.validate_trade(
            str(arguments["ticker"]), str(arguments["mode"]), str(arguments["side"]),
            float(arguments["amount"]), int(arguments.get("leverage", 1)),
        )
        return {"validation": asdict(validation)}, False
    if command == "signature":
        return {"signature": economic_signature(runtime.daten)}, False
    if command == "history":
        kind = str(arguments.get("kind", ""))
        values = list(arguments.get("arguments", []))
        if kind == "asset":
            rows = runtime.asset_history(str(values[0]), str(values[1]), int(values[2]))
        elif kind == "bond":
            rows = runtime.bond_history(str(values[0]), int(values[1]))
        elif kind == "product":
            rows = runtime.product_history(str(values[0]), str(values[1]), int(values[2]))
        elif kind == "forex":
            rows = runtime.forex_history(str(values[0]), int(values[1]))
        elif kind == "country":
            rows = runtime.country_history_points(str(values[0]), str(values[1]), int(values[2]))
        elif kind == "global":
            rows = runtime.global_macro_history(str(values[0]), int(values[1]))
        else:
            raise ValueError(f"Unknown history request: {kind}")
        return {"rows": rows}, False
    if command == "trade_spot":
        runtime.trade_spot(str(arguments["ticker"]), float(arguments["quantity"]), str(arguments["side"]))
    elif command == "trade_future":
        runtime.trade_future(
            str(arguments["ticker"]), str(arguments["direction"]),
            int(arguments["leverage"]), float(arguments["margin"]),
        )
    elif command == "close_future":
        runtime.close_future(str(arguments["position_id"]))
    elif command == "exchange_currency":
        runtime.exchange_currency(
            str(arguments["source_region"]), str(arguments["target_region"]), float(arguments["amount"])
        )
    elif command == "shutdown":
        return {}, True
    else:
        raise ValueError(f"Unknown live simulation command: {command}")
    runtime.data_store.record_day(runtime.state, current_scope="full")
    return _runtime_result(runtime, profile="mutation", include_snapshot=True), False


def run(project_root: Path, data_dir: Path, bootstrap: Path) -> int:
    runtime = None
    try:
        runtime = _load_runtime(project_root, data_dir, bootstrap)
        ready = _runtime_result(runtime, profile="status")
        print(json.dumps({"event": "ready", "result": ready}, separators=(",", ":")), flush=True)
        for line in sys.stdin:
            request = json.loads(line)
            request_id = str(request.get("id", ""))
            try:
                result, stop = _execute(runtime, str(request.get("command", "")), dict(request.get("arguments", {})))
                print(json.dumps({"id": request_id, "ok": True, "result": result}, separators=(",", ":")), flush=True)
                if stop:
                    return 0
            except Exception as exc:  # noqa: BLE001 - process protocol boundary
                print(json.dumps({"id": request_id, "ok": False, "error": str(exc)}, separators=(",", ":")), flush=True)
        return 0
    except Exception:  # noqa: BLE001 - startup errors go to stderr for the parent
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        if runtime is not None:
            runtime.close()
        bootstrap.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--bootstrap", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(args.project_root.resolve(), args.data_dir.resolve(), args.bootstrap.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
