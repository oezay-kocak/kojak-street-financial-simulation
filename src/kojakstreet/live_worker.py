"""Line-delimited JSON worker owning the live IntegratedRuntime."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import decode, restore
from kojakstreet.live_process import CURRENT_METHODS, economic_signature, game_state_payload
from kojakstreet.visible_state import CURRENT_TABLES, normalize_scope, project_visible_state

_OUTPUT_LOCK = threading.Lock()


def _emit(value: dict) -> None:
    encoded = json.dumps(value, separators=(",", ":"))
    with _OUTPUT_LOCK:
        print(encoded, flush=True)


def _load_runtime(project_root: Path, data_dir: Path, bootstrap: Path, *, on_persistence_error=None) -> IntegratedRuntime:
    with bootstrap.open(encoding="utf-8") as stream:
        payload = decode(json.load(stream))
    seed = int(payload.get("checkpoint", {}).get("simulation_seed", 0) or 0)
    runtime = IntegratedRuntime(project_root, data_dir=data_dir, seed=seed)
    restore(runtime.daten, payload)
    runtime.state.sync_from_legacy()
    runtime.data_store.restore_checkpoint_session(payload.get("analytics_session", {}))
    runtime.market.warm_runtime_indexes()
    runtime.data_store.record_day(runtime.state, current_scope="full")
    if on_persistence_error is not None:
        runtime.data_store.enable_background_flush(on_error=on_persistence_error)
    bootstrap.unlink(missing_ok=True)
    return runtime


def _runtime_result(
    runtime: IntegratedRuntime,
    *,
    profile: str = "status",
    include_snapshot: bool = False,
    simulation_ms: float = 0.0,
    changed_tables: set[str] | None = None,
    scope: dict | None = None,
    history_since: str | None = None,
) -> dict[str, Any]:
    runtime.data_store.check_persistence_health()
    delta = runtime.current_delta()
    tables = delta.tables if changed_tables is None else changed_tables
    # A complete state is explicit (restore/debug), never a normal-day fallback.
    visible_scope = normalize_scope(scope or getattr(runtime, "_visible_scope", None))
    runtime._visible_scope = visible_scope
    snapshot_profile = "full" if include_snapshot else visible_scope["view"]
    if include_snapshot:
        state = runtime.snapshot_for_view("full")
        tape, timings = [], {}
    else:
        state, tape, timings = project_visible_state(runtime, visible_scope, history_since=history_since)
    current_rows = {
        table: getattr(runtime, method)()
        for table, method in CURRENT_METHODS.items()
        if table in CURRENT_TABLES[visible_scope["view"]] and hasattr(runtime, method)
    }
    result = {
        "profile": snapshot_profile,
        "state": game_state_payload(state),
        "delta": {"version": delta.version, "date_text": delta.date_text, "tables": sorted(tables)},
        "current_rows": current_rows,
        "simulation_ms": simulation_ms,
        "visible_scope": visible_scope,
        "ticker": tape,
        "extraction_ms": timings,
        "history_since": history_since,
        "visible_state": not include_snapshot,
        "phase_metrics": runtime.phase_metric_current_rows(),
    }
    if not include_snapshot and visible_scope["view"] == "news":
        from types import SimpleNamespace

        from kojakstreet.core.economic_calendar import build_economic_calendar

        calendar = build_economic_calendar(SimpleNamespace(
            date=runtime.daten.datum, macro=runtime.daten.makro,
            macro_history=runtime.daten.MAKRO_HISTORIE,
        ))
        key = visible_scope["selection"].get("history_key") or (calendar[0].history_key if calendar else "")
        result["calendar_rows"] = [
            {**{field.name: getattr(row, field.name) for field in fields(row) if field.name != "history"},
             "history": row.history[-520:] if row.history_key == key else []}
            for row in calendar
        ]
    return result


def _execute(runtime: IntegratedRuntime, command: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    if "tape_ids" in arguments:
        runtime.daten._tape_display_ids = list(arguments["tape_ids"])
    profile = str(arguments.get("profile", "status"))
    if "scope" in arguments:
        runtime._visible_scope = normalize_scope(arguments["scope"])
    if command == "visible":
        return _runtime_result(runtime, scope=arguments.get("scope")), False
    if command == "advance":
        started = time.perf_counter()
        changed_tables = set()
        for _ in range(max(0, int(arguments.get("steps", 1)))):
            runtime.advance_day()
            changed_tables.update(runtime.current_delta().tables)
        elapsed = (time.perf_counter() - started) * 1000.0
        return _runtime_result(
            runtime,
            profile=profile,
            include_snapshot=bool(arguments.get("force_snapshot", False)),
            simulation_ms=elapsed,
            changed_tables=changed_tables,
            scope=arguments.get("scope"),
            history_since=arguments.get("history_since"),
        ), False
    if command == "set_running":
        runtime.set_running(bool(arguments.get("running", False)))
        return {}, False
    if command == "save":
        runtime.save_game()
        return _runtime_result(runtime, profile="status"), False
    if command == "load":
        runtime.load_game()
        return _runtime_result(runtime), False
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
        return {"rows": rows, "date_text": runtime.current_delta().date_text}, False
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
        runtime.data_store.flush()
        return {}, True
    else:
        raise ValueError(f"Unknown live simulation command: {command}")
    runtime.data_store.record_day(runtime.state, current_scope="full")
    return _runtime_result(runtime, profile="status"), False


def run(project_root: Path, data_dir: Path, bootstrap: Path) -> int:
    runtime = None
    try:
        runtime = _load_runtime(
            project_root, data_dir, bootstrap,
            on_persistence_error=lambda error: _emit({"event": "persistence_error", "error": str(error)}),
        )
        ready = _runtime_result(runtime, profile="status")
        _emit({"event": "ready", "result": ready})
        for line in sys.stdin:
            request = json.loads(line)
            request_id = str(request.get("id", ""))
            try:
                result, stop = _execute(runtime, str(request.get("command", "")), dict(request.get("arguments", {})))
                _emit({"id": request_id, "ok": True, "result": result})
                if stop:
                    return 0
            except Exception as exc:  # noqa: BLE001 - process protocol boundary
                _emit({"id": request_id, "ok": False, "error": str(exc)})
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
