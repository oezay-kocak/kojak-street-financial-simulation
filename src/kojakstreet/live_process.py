"""Persistent process-owned runtime with a small cached UI-side proxy."""

from __future__ import annotations

import gc
import hashlib
import json
import os
import pickle
import queue
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from kojakstreet.adapters.legacy_state import snapshot_from_legacy
from kojakstreet.core.checkpoints import atomic_write, capture, decode, encode
from kojakstreet.core.history import _as_date
from kojakstreet.core.runtime_context import SimulationDelta
from kojakstreet.core.state import GameState
from kojakstreet.core.trade_preview import TradeValidation
from kojakstreet.day_delta import state_values
from kojakstreet.visible_state import normalize_scope

CURRENT_METHODS = {
    "asset_current": "asset_quote_rows",
    "product_current": "product_current_rows",
    "company_current": "company_current_rows",
    "company_output_current": "company_output_current_rows",
    "country_trade_current": "country_trade_current_rows",
    "fund_allocation_current": "fund_allocation_current_rows",
    "country_current": "country_current_rows",
    "global_macro_current": "global_macro_current_rows",
    "forex_current": "forex_current_rows",
    "bond_current": "bond_current_rows",
    "portfolio_current": "portfolio_current_rows",
    "news_current": "news_current_rows",
    "event_current": "event_current_rows",
    "phase_metric_current": "phase_metric_current_rows",
}


def game_state_payload(state: GameState) -> dict[str, Any]:
    return encode(state_values(state))


def game_state_from_payload(payload: dict[str, Any]) -> GameState:
    return GameState(**decode(payload))


def economic_signature(state: Any) -> dict[str, Any]:
    """Compact deterministic signature used across the process boundary."""

    import random

    import numpy as np

    def book(name: str, fields: tuple[str, ...]) -> list[tuple[Any, ...]]:
        return [
            (str(key), *(float(item.get(field, 0.0)) for field in fields))
            for key, item in sorted(getattr(state, name, {}).items())
        ]

    bonds = [
        (
            str(item.get("symbol", "")),
            float(item.get("price", 0.0)),
            float(item.get("yield_to_maturity", 0.0)),
            str(item.get("rating", "")),
        )
        for item in getattr(state, "bond_market", [])
    ]
    rng_blob = pickle.dumps((random.getstate(), np.random.get_state()), protocol=5)
    return {
        "date": state.datum.isoformat(),
        "countries": book("makro", ("bip_abs", "bip_prozent", "inflation", "zins", "arbeitslosigkeit", "debt_to_gdp", "bevoelkerung", "population_growth", "birth_rate", "death_rate")),
        "workforce": encode({country: macro.get("workforce") for country, macro in sorted(state.makro.items())}),
        "politics": encode({country: macro.get("politics") for country, macro in sorted(state.makro.items())}),
        "companies": book("aktien", ("kurs", "market_cap", "revenue", "free_cash_flow")),
        "funds": book("fonds", ("kurs", "aum")),
        "indices": book("indizes", ("kurs", "market_cap")),
        "cryptos": book("kryptos", ("kurs", "market_cap")),
        "bonds": bonds,
        "portfolio": {
            "cash": float(getattr(state, "bargeld", 0.0)),
            "fx": sorted((str(key), float(value)) for key, value in getattr(state, "forex_depot", {}).items()),
            "positions": sorted((str(key), repr(value)) for key, value in getattr(state, "depot", {}).items()),
            "perpetuals": sorted((str(key), repr(value)) for key, value in getattr(state, "perpetuals", {}).items()),
        },
        "rng": hashlib.sha256(rng_blob).hexdigest(),
    }


class LiveSimulationProcess:
    """RuntimePort implementation whose mutable world lives in one subprocess."""

    is_process_runtime = True

    def __init__(
        self,
        project_root: Path,
        data_dir: Path,
        bootstrap_path: Path,
        initial_state: GameState,
        initial_rows: dict[str, list[dict[str, object]]],
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.timeout_seconds = float(timeout_seconds)
        self.running = False
        self._active_view_key = "markets"
        self._snapshots: dict[str, GameState] = {"markets": initial_state}
        self.visible_scope = normalize_scope(None)
        self._ticker_items = []
        self.last_extraction_ms = {}
        self._calendar_rows = []
        self.has_current_state_delta = False
        self._status_state = initial_state
        self._current_rows = initial_rows
        self._current_delta = SimulationDelta(0, initial_state.date.strftime("%Y-%m-%d"), frozenset(initial_rows))
        self._request_lock = threading.Lock()
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr: list[str] = []
        self._history_cache: dict[tuple[Any, ...], list[Any]] = {}
        self._history_cache_dates: dict[tuple[Any, ...], str] = {}
        self._history_pending: set[tuple[int, tuple[Any, ...]]] = set()
        self._history_lock = threading.Lock()
        self._history_generation = 0
        self.history_cache_version = 0
        self._closed = False
        self._persistence_error: str | None = None
        self.last_simulation_ms = 0.0
        self.last_ipc_ms = 0.0
        self.last_apply_ms = 0.0

        command = self._worker_command(bootstrap_path)
        environment = os.environ.copy()
        source = str(self.project_root / "src")
        environment["PYTHONPATH"] = source + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
        startup_info: dict[str, Any] = {}
        if sys.platform == "win32":
            startup_info["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = subprocess.Popen(
            command,
            cwd=str(self.project_root),
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            **startup_info,
        )
        threading.Thread(target=self._read_stdout, name="kojak-live-worker-output", daemon=True).start()
        threading.Thread(target=self._read_stderr, name="kojak-live-worker-errors", daemon=True).start()
        ready = self._wait_response(self.timeout_seconds, "startup")
        if ready.get("event") != "ready":
            self.close(force=True)
            raise RuntimeError(str(ready.get("error", "Live simulation worker failed to start")))
        self._apply_result(ready.get("result", {}))
        # Bootstrap/checkpoint conversion creates a large temporary graph.
        # Release it at the startup boundary before interactive day requests.
        gc.collect()

    @classmethod
    def from_runtime(cls, runtime, *, timeout_seconds: float = 30.0, release_bootstrap: bool = False) -> LiveSimulationProcess:
        project_root = Path(getattr(runtime, "project_root", Path.cwd())).resolve()
        data_dir = Path(runtime.data_dir).resolve()
        runtime.data_store.record_day(runtime.state, current_scope="full")
        runtime.data_store.flush()
        payload = capture(runtime.daten)
        # The checkpoint deliberately bounds some display histories. Build both
        # sides' initial UI baseline from that same restored representation.
        initial_state = snapshot_from_legacy(SimpleNamespace(**payload["checkpoint"]), "status")
        initial_rows = {}
        payload["analytics_session"] = runtime.data_store.checkpoint_session()
        bootstrap_path = data_dir / f".live-worker-{uuid.uuid4().hex}.json"
        atomic_write(bootstrap_path, payload)
        runtime.close()
        # Handoff is complete: the closed bootstrap runtime must not retain an
        # obsolete economic world in the UI process. The checkpoint is detached
        # and already durable; the worker restores it independently.
        world_fields = (
            "aktien", "rohstoffe", "processed_products", "kryptos", "fonds", "indizes",
            "derivatives", "makro", "depot", "perpetuals", "forex_depot", "kredite",
            "anleihen", "bond_market", "bond_market_archive", "NEWS_SPEICHER",
            "MAKRO_HISTORIE", "GLOBAL_MACRO_HISTORIE", "FOREX_PAARE_HISTORIE",
            "DEPOT_VERMOEGEN_HISTORIE", "realisierte_guv_historie", "global_macro",
            "market_runtime_assets", "market_runtime_index", "bond_market_by_symbol",
        )
        if release_bootstrap:
            for name in world_fields:
                value = getattr(runtime.daten, name, None)
                if isinstance(value, (dict, list)):
                    setattr(runtime.daten, name, {} if isinstance(value, dict) else [])
            for name, value in list(vars(runtime.daten).items()):
                if name.startswith("_") and not name.startswith("__") and isinstance(value, (dict, list, tuple)):
                    delattr(runtime.daten, name)
            runtime.state.sync_from_legacy()
        try:
            return cls(
                project_root,
                data_dir,
                bootstrap_path,
                initial_state,
                initial_rows,
                timeout_seconds=timeout_seconds,
            )
        except BaseException:
            bootstrap_path.unlink(missing_ok=True)
            raise

    @property
    def state(self) -> GameState:
        return next(iter(self._snapshots.values()), self._status_state)

    def snapshot(self) -> GameState:
        # Full state is an explicit debug read, never a retained UI baseline.
        result = self._request("advance", steps=0, profile="full", force_snapshot=True)
        return game_state_from_payload(result["state"])

    def snapshot_for_view(self, view_key: str) -> GameState:
        if view_key == "full":
            return self.snapshot()
        if view_key == "status":
            return self._status_state
        if view_key != self.visible_scope["view"]:
            return self.sync_visible_scope({"view": view_key})
        return self.state

    def sync_visible_scope(self, scope: dict) -> GameState:
        scope = normalize_scope(scope)
        self._requested_scope = scope
        result = self._request("visible", scope=scope)
        self._apply_result(result)
        return self.state

    def set_running(self, running: bool) -> None:
        self.running = bool(running)
        self._request("set_running", running=self.running)

    def advance_days(self, steps: int, view_key: str = "full") -> GameState:
        force_snapshot = view_key == "full"
        profile = self.visible_scope["view"] if view_key == "status" else view_key
        if not force_snapshot and profile != self.visible_scope["view"]:
            self.visible_scope = normalize_scope({"view": profile})
            self._requested_scope = self.visible_scope
        # Small chunks bound parser pauses without retransmitting the current
        # universe for every day of a queued multi-day advance. The worker
        # includes every intervening history point and changed current table.
        count = max(0, int(steps))
        batches = [count] if force_snapshot or not count else [min(5, count - i) for i in range(0, count, 5)]
        simulation_ms = 0.0
        ipc_ms = 0.0
        for batch in batches:
            result = self._request(
                "advance", steps=batch, profile=profile, force_snapshot=force_snapshot,
                scope=self.visible_scope,
                history_since=self._current_delta.date_text if not force_snapshot else None,
            )
            if not force_snapshot and not result.get("visible_state"):
                raise ValueError("Worker did not return the required visible state")
            if not force_snapshot:
                self._apply_result(result)
            simulation_ms += float(result.get("simulation_ms", 0.0))
            ipc_ms += self.last_ipc_ms
        self.last_simulation_ms = simulation_ms
        self.last_ipc_ms = ipc_ms
        return self._status_state if not force_snapshot else game_state_from_payload(result["state"])

    def save_game(self) -> GameState:
        result = self._request("save", profile=self._active_view_key)
        self._apply_result(result)
        return self.snapshot_for_view(self._active_view_key)

    def load_game(self) -> GameState:
        result = self._request("load", profile="full")
        self.running = False
        self._apply_result(result)
        loaded = self.state
        with self._history_lock:
            self._history_generation += 1
            self._history_cache.clear()
            self._history_cache_dates.clear()
            self.history_cache_version += 1
        return loaded

    def validate_trade(self, ticker: str, mode: str, side: str, amount: float, leverage: int = 1) -> TradeValidation:
        result = self._request(
            "validate_trade", ticker=ticker, mode=mode, side=side, amount=float(amount), leverage=int(leverage)
        )
        return TradeValidation(**result["validation"])

    def trade_spot(self, ticker: str, quantity: float, side: str) -> GameState:
        return self._mutation("trade_spot", ticker=ticker, quantity=float(quantity), side=side)

    def trade_future(self, ticker: str, direction: str, leverage: int, margin: float) -> GameState:
        return self._mutation(
            "trade_future", ticker=ticker, direction=direction, leverage=int(leverage), margin=float(margin)
        )

    def close_future(self, position_id: str) -> GameState:
        return self._mutation("close_future", position_id=position_id)

    def exchange_currency(self, source_region: str, target_region: str, amount: float) -> GameState:
        return self._mutation(
            "exchange_currency", source_region=source_region, target_region=target_region, amount=float(amount)
        )

    def _mutation(self, command: str, **arguments: Any) -> GameState:
        result = self._request(command, profile=self._active_view_key, **arguments)
        self._apply_result(result)
        return self.snapshot_for_view(self._active_view_key)

    def current_version(self) -> int:
        return self._current_delta.version

    def current_delta(self) -> SimulationDelta:
        return self._current_delta

    def asset_quote_rows(self):
        if self.visible_scope["view"] == "markets":
            from kojakstreet.core.market_data_service import MarketDataService

            return [{"ticker": q.ticker, "asset_type": q.asset_type, "price": q.price,
                     "change": q.change, "market_cap": q.market_cap, "region": q.region}
                    for q in MarketDataService(self.state).quotes()]
        return self._current_rows.get("asset_current", [])

    def product_current_rows(self):
        return self._current_rows.get("product_current", [])

    def company_current_rows(self):
        return self._current_rows.get("company_current", [])

    def company_output_current_rows(self):
        return self._current_rows.get("company_output_current", [])

    def country_trade_current_rows(self):
        return self._current_rows.get("country_trade_current", [])

    def country_current_rows(self):
        return self._current_rows.get("country_current", [])

    def forex_current_rows(self):
        return self._current_rows.get("forex_current", [])

    def bond_current_rows(self):
        return self._current_rows.get("bond_current", [])

    def portfolio_current_rows(self):
        return self._current_rows.get("portfolio_current", [])

    def news_current_rows(self):
        return self._current_rows.get("news_current", [])

    def economic_calendar_rows(self):
        from kojakstreet.core.economic_calendar import EconomicCalendarItem

        return [EconomicCalendarItem(**row) for row in self._calendar_rows]

    def phase_metric_current_rows(self):
        return self._current_rows.get("phase_metric_current", [])

    def ticker_tape_quotes(self) -> list[dict[str, float | str]]:
        return self._ticker_items

    def set_ticker_display_ids(self, tickers: list[tuple[str, str]]) -> None:
        self._tape_display_ids = list(tickers)

    def asset_history(self, asset_type: str, ticker: str, limit: int = 520):
        book = {
            "Stock": self.state.stocks,
            "Commodity": self.state.commodities,
            "Crypto": self.state.cryptos,
            "Fund": self.state.funds,
            "Index": self.state.indices,
            "Derivative": self.state.derivatives,
        }.get(asset_type, {})
        fallback = list(book.get(ticker, {}).get("historie", [])[-limit:])
        return self._history_result(("asset", asset_type, ticker, limit), fallback)

    def bond_history(self, symbol: str, limit: int = 520):
        bond = next((item for item in self.state.bond_market if str(item.get("symbol", "")) == symbol), {})
        fallback = list(bond.get("historie", [])[-limit:])
        return self._history_result(("bond", symbol, limit), fallback)

    def product_history(self, code: str, metric: str, limit: int = 520):
        item = self.state.processed_products.get(code) or self.state.commodities.get(code, {})
        key = {"produced": "supply_history", "demanded": "demand_history", "inventories": "inventory_history"}.get(metric, f"{metric}_history")
        recent = list(item.get(key, [])[-limit:])
        fallback = [float(row[0] if isinstance(row, (tuple, list)) else row) for row in recent]
        return self._history_result(("product", code, metric, limit), fallback, dated_rows=recent)

    def forex_history(self, pair: str, limit: int = 520):
        recent = list(self.state.forex_history.get(pair, [])[-limit:])
        fallback = [float(row[0] if isinstance(row, (tuple, list)) else row) for row in recent]
        return self._history_result(("forex", pair, limit), fallback, dated_rows=recent)

    def country_history_points(self, region: str, metric: str, limit: int = 0):
        key = {"inflation": "INF", "growth": "BIP", "gdp": "BIP", "unemployment": "ALO", "rate": "ZINS"}.get(metric, metric.upper())
        rows = self.state.macro_history.get(f"{region}_{key}", [])
        if metric in {"trade_balance", "import_dependency", "export_strength"}:
            rows = self.state.macro.get(region, {}).get(f"{metric}_history", [])
        if limit > 0:
            rows = rows[-limit:]
        fallback = [
            {"date": str(row[1]), "value": float(row[0]), "open": float(row[0]), "high": float(row[0]), "low": float(row[0]), "close": float(row[0]), "resolution": "cached"}
            for row in rows
        ]
        return self._history_result(("country", region, metric, limit), fallback)

    def global_macro_history(self, metric: str, limit: int = 0):
        rows = self.state.global_macro_history.get(metric, [])
        if limit > 0:
            rows = rows[-limit:]
        fallback = [
            {"date": str(row[1]), "value": float(row[0]), "open": float(row[0]), "high": float(row[0]), "low": float(row[0]), "close": float(row[0]), "resolution": "cached"}
            for row in rows
        ]
        return self._history_result(("global", metric, limit), fallback)

    def _history_result(
        self, key: tuple[Any, ...], fallback: list[Any], *, dated_rows: list[Any] | None = None,
    ) -> list[Any]:
        with self._history_lock:
            cached = self._history_cache.get(key)
            stale_gap = False
            if cached is not None:
                marker = self._history_cache_dates.get(key)
                if marker:
                    cutoff = _as_date(marker).toordinal()
                    dated = [(self._history_point_ordinal(point), value)
                             for point, value in zip(dated_rows if dated_rows is not None else fallback, fallback)]
                    known = [ordinal for ordinal, _ in dated if ordinal is not None]
                    stale_gap = bool(known and min(known) > cutoff)
                    base = list(cached)
                    same_day = [value for ordinal, value in dated if ordinal == cutoff]
                    if base and same_day and (
                        dated_rows is not None or self._history_point_ordinal(base[-1]) == cutoff
                    ):
                        # A query can precede completion of this calendar day,
                        # notably the initial full-store record. Its final
                        # local value/OHLC must replace that cached endpoint.
                        base[-1] = same_day[-1]
                    result = [*base, *(value for ordinal, value in dated if ordinal is not None and ordinal > cutoff)]
                    if int(key[-1]) > 0:
                        result = result[-int(key[-1]):]
                    if not stale_gap:
                        return result
                else:
                    return cached
            wants_worker = int(key[-1]) > 520 or int(key[-1]) <= 0
            pending_id = (self._history_generation, key)
            if wants_worker and pending_id not in self._history_pending and not self._closed:
                self._history_pending.add(pending_id)
                threading.Thread(target=self._prefetch_history, args=(key, pending_id), daemon=True).start()
        return result if cached is not None and stale_gap else fallback

    @staticmethod
    def _history_point_ordinal(point: Any) -> int | None:
        value = point.get("date", point.get("bucket_end", "")) if isinstance(point, dict) else (
            point[1] if isinstance(point, (tuple, list)) and len(point) > 1 else ""
        )
        try:
            return _as_date(value).toordinal() if value else None
        except (ValueError, TypeError):
            return None

    def _prefetch_history(self, key: tuple[Any, ...], pending_id: tuple[int, tuple[Any, ...]]) -> None:
        try:
            result = self._request("history", kind=str(key[0]), arguments=list(key[1:]))
            rows = list(result.get("rows", []))
            with self._history_lock:
                if pending_id[0] == self._history_generation:
                    self._history_cache[key] = rows
                    self._history_cache_dates[key] = str(result.get("date_text", self._current_delta.date_text))
                    self.history_cache_version += 1
        except (OSError, RuntimeError, TimeoutError):
            pass
        finally:
            with self._history_lock:
                self._history_pending.discard(pending_id)

    def performance_snapshot(self) -> dict[str, object]:
        phases = {str(row["phase"]): float(row["duration_ms"]) for row in self.phase_metric_current_rows()}
        return {
            "current_version": self.current_version(),
            "date": self._current_delta.date_text,
            "phases": phases,
            "total_phase_ms": sum(phases.values()),
            "slowest_phase": max(phases, key=phases.get) if phases else "",
            "worker_simulation_ms": self.last_simulation_ms,
            "ipc_ms": self.last_ipc_ms,
            "apply_ms": self.last_apply_ms,
        }

    def deterministic_signature(self) -> dict[str, Any]:
        return self._request("signature")["signature"]

    @property
    def worker_pid(self) -> int:
        return int(self._process.pid)

    def cancel_pending(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()

    def close(self, *, force: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        if not force and self._process.poll() is None:
            try:
                self._request("shutdown", _allow_closed=True)
            except (OSError, RuntimeError, TimeoutError):
                force = True
        if self._process.poll() is None:
            if force:
                self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2.0)

    def _worker_command(self, bootstrap_path: Path) -> list[str]:
        arguments = [
            "--project-root", str(self.project_root),
            "--data-dir", str(self.data_dir),
            "--bootstrap", str(bootstrap_path),
        ]
        if getattr(sys, "frozen", False):
            return [sys.executable, "--live-worker", *arguments]
        return [sys.executable, "-m", "kojakstreet.live_worker", *arguments]

    def _request(self, command: str, _allow_closed: bool = False, **arguments: Any) -> dict[str, Any]:
        if self._closed and not _allow_closed:
            raise RuntimeError("Live simulation worker is closed")
        with self._request_lock:
            if command != "shutdown" and self.poll_persistence_error():
                raise RuntimeError(self.poll_persistence_error())
            arguments["tape_ids"] = list(getattr(self, "_tape_display_ids", ()))
            if self._process.poll() is not None:
                raise RuntimeError(self._worker_error("Live simulation worker exited"))
            request_id = uuid.uuid4().hex
            message = {"id": request_id, "command": command, "arguments": arguments}
            started = time.perf_counter()
            assert self._process.stdin is not None
            self._process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            self._process.stdin.flush()
            response = self._wait_response(self.timeout_seconds, command)
            self.last_ipc_ms = (time.perf_counter() - started) * 1000.0
            if response.get("id") != request_id:
                raise RuntimeError("Live simulation IPC response was out of sequence")
            if not response.get("ok", False):
                raise RuntimeError(str(response.get("error", "Live simulation command failed")))
            if command != "shutdown" and self.poll_persistence_error():
                raise RuntimeError(self.poll_persistence_error())
            return response.get("result", {})

    def poll_persistence_error(self) -> str | None:
        return getattr(self, "_persistence_error", None)

    def _wait_response(self, timeout: float, context: str) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise TimeoutError(f"Live simulation worker timed out during {context}")
            try:
                return self._responses.get(timeout=min(0.10, remaining))
            except queue.Empty:
                if self._process.poll() is not None:
                    raise RuntimeError(self._worker_error(f"Live simulation worker exited during {context}"))

    def _apply_result(self, result: dict[str, Any]) -> None:
        started = time.perf_counter()
        if result.get("visible_state"):
            state = game_state_from_payload(result["state"])
            scope = normalize_scope(result["visible_scope"])
            if getattr(self, "_requested_scope", scope) != scope:
                return  # A late response must not publish the previous detail.
            if result.get("history_since") and scope == self.visible_scope:
                from kojakstreet.ui_qt.chart_series import incremental_history
                from kojakstreet.visible_state import BOOKS

                selection = scope["selection"]
                kind, ticker = selection.get("kind"), selection.get("ticker")
                if scope["view"] == "markets" and kind in BOOKS and ticker:
                    book = BOOKS[kind][1]
                    asset = getattr(state, book).get(ticker, {})
                    old = getattr(self.state, book).get(ticker, {})
                    history = incremental_history(old.get("historie", []))
                    for point in asset.get("historie", []):
                        history.append_point(point, limit=520)
                    asset["historie"] = history
            self.visible_scope = scope
            self._active_view_key = scope["view"]
            self._snapshots = {scope["view"]: state}
            self._status_state = GameState(state.date, state.cash, state.display_currency)
            self._current_rows = dict(result.get("current_rows", {}))
            self._current_rows["phase_metric_current"] = result.get("phase_metrics", [])
            self._ticker_items = list(result.get("ticker", []))
            self._calendar_rows = list(result.get("calendar_rows", []))
            self.last_extraction_ms = dict(result.get("extraction_ms", {}))
            delta = result["delta"]
            self._current_delta = SimulationDelta(int(delta["version"]), str(delta["date_text"]), frozenset(delta["tables"]))
            self.has_current_state_delta = True
            self.last_simulation_ms = float(result.get("simulation_ms", 0.0))
            self.last_apply_ms = (time.perf_counter() - started) * 1000
            return
        # Explicit full debug reads are returned to the caller, never cached.
        if result.get("profile") == "full":
            return
        raise ValueError("Missing visible-state contract")

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            response = None
            try:
                response = json.loads(line)
                if response.get("event") == "persistence_error":
                    self._persistence_error = str(response.get("error", "History persistence failed"))
                    continue
                self._responses.put(response)
            except json.JSONDecodeError:
                self._stderr.append(f"Invalid worker output: {line.strip()}")
            except (ValueError, TypeError, KeyError, pickle.UnpicklingError) as error:
                self._responses.put({
                    "id": response.get("id") if isinstance(response, dict) else None,
                    "ok": False,
                    "error": f"Invalid worker visible state: {error}",
                })

    def _read_stderr(self) -> None:
        assert self._process.stderr is not None
        for line in self._process.stderr:
            self._stderr.append(line.rstrip())

    def _worker_error(self, fallback: str) -> str:
        return self._stderr[-1] if self._stderr else fallback
