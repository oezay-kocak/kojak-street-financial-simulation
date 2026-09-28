"""Persistent process-owned runtime with a small cached UI-side proxy."""

from __future__ import annotations

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
from dataclasses import asdict
from pathlib import Path
from typing import Any

from kojakstreet.core.checkpoints import atomic_write, capture, decode, encode
from kojakstreet.core.runtime_context import SimulationDelta
from kojakstreet.core.state import GameState
from kojakstreet.core.trade_preview import TradeValidation

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
    return encode(asdict(state))


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
        "countries": book("makro", ("bip_abs", "bip_prozent", "inflation", "zins", "arbeitslosigkeit", "debt_to_gdp")),
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
        self._snapshots: dict[str, GameState] = {"full": initial_state, "markets": initial_state}
        self._status_state = initial_state
        self._current_rows = initial_rows
        self._current_delta = SimulationDelta(0, initial_state.date.strftime("%Y-%m-%d"), frozenset(initial_rows))
        self._request_lock = threading.Lock()
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr: list[str] = []
        self._history_cache: dict[tuple[Any, ...], list[Any]] = {}
        self._history_pending: set[tuple[int, tuple[Any, ...]]] = set()
        self._history_lock = threading.Lock()
        self._history_generation = 0
        self.history_cache_version = 0
        self._closed = False
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

    @classmethod
    def from_runtime(cls, runtime, *, timeout_seconds: float = 30.0) -> LiveSimulationProcess:
        project_root = Path(getattr(runtime, "project_root", Path.cwd())).resolve()
        data_dir = Path(runtime.data_dir).resolve()
        initial_state = runtime.snapshot()
        initial_rows = {
            table: list(getattr(runtime, method)())
            for table, method in CURRENT_METHODS.items()
            if hasattr(runtime, method)
        }
        runtime.data_store.record_day(runtime.state, current_scope="full")
        runtime.data_store.flush()
        payload = capture(runtime.daten)
        payload["analytics_session"] = runtime.data_store.checkpoint_session()
        bootstrap_path = data_dir / f".live-worker-{uuid.uuid4().hex}.json"
        atomic_write(bootstrap_path, payload)
        runtime.close()
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
        return self._snapshots.get(self._active_view_key, self._snapshots["full"])

    def snapshot(self) -> GameState:
        return self._snapshots.get("full", self._status_state)

    def snapshot_for_view(self, view_key: str) -> GameState:
        self._active_view_key = view_key
        return self._snapshots.get(view_key, self._snapshots.get("full", self._status_state))

    def set_running(self, running: bool) -> None:
        self.running = bool(running)
        self._request("set_running", running=self.running)

    def advance_days(self, steps: int, view_key: str = "full") -> GameState:
        force_snapshot = view_key != "status"
        profile = self._active_view_key if view_key == "status" else view_key
        result = self._request(
            "advance", steps=max(0, int(steps)), profile=profile, force_snapshot=force_snapshot
        )
        self._apply_result(result)
        return self._status_state if not force_snapshot else self.snapshot_for_view(profile)

    def save_game(self) -> GameState:
        result = self._request("save", profile=self._active_view_key)
        self._apply_result(result)
        return self.snapshot_for_view(self._active_view_key)

    def load_game(self) -> GameState:
        result = self._request("load", profile="full")
        self.running = False
        self._apply_result(result)
        loaded = self._snapshots["full"]
        self._snapshots = {"full": loaded, self._active_view_key: loaded}
        with self._history_lock:
            self._history_generation += 1
            self._history_cache.clear()
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

    def phase_metric_current_rows(self):
        return self._current_rows.get("phase_metric_current", [])

    def ticker_tape_quotes(self) -> list[dict[str, float | str]]:
        quotes = self.asset_quote_rows()
        items: list[dict[str, float | str]] = []
        for asset_type, limit in {"Commodity": 2, "Crypto": 2, "Stock": 4, "Index": 1000}.items():
            ranked = sorted(
                (quote for quote in quotes if quote.get("asset_type") == asset_type),
                key=lambda quote: float(quote.get("change", 0.0)),
                reverse=True,
            )[:limit]
            items.extend(
                {"ticker": str(row["ticker"]), "price": float(row["price"]), "change": float(row["change"])}
                for row in ranked
            )
        return items

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
        fallback = [float(row[0] if isinstance(row, (tuple, list)) else row) for row in item.get(key, [])[-limit:]]
        return self._history_result(("product", code, metric, limit), fallback)

    def forex_history(self, pair: str, limit: int = 520):
        fallback = [float(row[0] if isinstance(row, (tuple, list)) else row) for row in self.state.forex_history.get(pair, [])[-limit:]]
        return self._history_result(("forex", pair, limit), fallback)

    def country_history_points(self, region: str, metric: str, limit: int = 0):
        key = {"inflation": "INF", "growth": "BIP", "gdp": "BIP", "unemployment": "ALO", "rate": "ZINS"}.get(metric, metric.upper())
        rows = self.state.macro_history.get(f"{region}_{key}", [])
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

    def _history_result(self, key: tuple[Any, ...], fallback: list[Any]) -> list[Any]:
        with self._history_lock:
            cached = self._history_cache.get(key)
            if cached is not None:
                return cached
            wants_worker = int(key[-1]) > 520 or int(key[-1]) <= 0
            pending_id = (self._history_generation, key)
            if wants_worker and pending_id not in self._history_pending and not self._closed:
                self._history_pending.add(pending_id)
                threading.Thread(target=self._prefetch_history, args=(key, pending_id), daemon=True).start()
        return fallback

    def _prefetch_history(self, key: tuple[Any, ...], pending_id: tuple[int, tuple[Any, ...]]) -> None:
        try:
            result = self._request("history", kind=str(key[0]), arguments=list(key[1:]))
            rows = list(result.get("rows", []))
            with self._history_lock:
                if pending_id[0] == self._history_generation:
                    self._history_cache[key] = rows
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
            return response.get("result", {})

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
        state_payload = result.get("state")
        profile = str(result.get("profile", "status"))
        if isinstance(state_payload, dict):
            state = game_state_from_payload(state_payload)
            self._status_state = state
            if profile == "mutation":
                for cached in {id(item): item for item in self._snapshots.values()}.values():
                    cached.date = state.date
                    cached.cash = state.cash
                    cached.portfolio = state.portfolio
                    cached.perpetuals = state.perpetuals
                    cached.fx_balances = state.fx_balances
                    cached.loans = state.loans
                    cached.bonds = state.bonds
                    cached.currency_strength = state.currency_strength
            elif profile != "status":
                self._snapshots[profile] = state
                if profile == "full":
                    self._snapshots["full"] = state
        for table, rows in result.get("current_rows", {}).items():
            self._current_rows[str(table)] = rows
        self._merge_current_rows()
        delta = result.get("delta")
        if isinstance(delta, dict):
            self._current_delta = SimulationDelta(
                int(delta.get("version", self._current_delta.version)),
                str(delta.get("date_text", "")),
                frozenset(delta.get("tables", [])),
            )
        self.last_simulation_ms = float(result.get("simulation_ms", self.last_simulation_ms))
        self.last_apply_ms = (time.perf_counter() - started) * 1000.0

    def _merge_current_rows(self) -> None:
        snapshots = list({id(state): state for state in self._snapshots.values()}.values())
        for state in snapshots:
            state.date = self._status_state.date
        asset_books = {
            "Stock": "stocks",
            "Commodity": "commodities",
            "Crypto": "cryptos",
            "Fund": "funds",
            "Index": "indices",
            "Derivative": "derivatives",
        }
        for row in self._current_rows.get("asset_current", []):
            book_name = asset_books.get(str(row.get("asset_type", "")))
            if book_name is None:
                continue
            ticker = str(row.get("ticker", ""))
            for state in snapshots:
                asset = getattr(state, book_name, {}).get(ticker)
                if asset is None:
                    continue
                asset["kurs"] = float(row.get("price", asset.get("kurs", 0.0)))
                asset["aenderung"] = float(row.get("change", asset.get("aenderung", 0.0)))
                asset["market_cap"] = float(row.get("market_cap", asset.get("market_cap", 0.0)))
                if "revenue" in row:
                    asset["revenue"] = float(row["revenue"])
                if "free_cash_flow" in row:
                    asset["free_cash_flow"] = float(row["free_cash_flow"])
                if row.get("rating"):
                    asset["rating"] = str(row["rating"])
        for row in self._current_rows.get("product_current", []):
            code = str(row.get("code", ""))
            for state in snapshots:
                item = state.processed_products.get(code) or state.commodities.get(code)
                if item is None:
                    continue
                item.update(
                    supply=float(row.get("produced", item.get("supply", 0.0))),
                    demand=float(row.get("demanded", item.get("demand", 0.0))),
                    inventories=float(row.get("inventories", item.get("inventories", 0.0))),
                    shortage=float(row.get("shortage", item.get("shortage", 0.0))),
                    price_pressure=float(row.get("pressure", item.get("price_pressure", 0.0))),
                )
        for row in self._current_rows.get("country_current", []):
            region = str(row.get("region", ""))
            for state in snapshots:
                macro = state.macro.get(region)
                if macro is None:
                    continue
                for public, legacy in {
                    "gdp": "bip_abs", "growth": "bip_prozent", "rate": "zins",
                    "inflation": "inflation", "unemployment": "arbeitslosigkeit",
                    "debt_to_gdp": "debt_to_gdp", "credit_growth": "credit_growth",
                    "balance_sheet": "balance_sheet",
                }.items():
                    if public in row:
                        macro[legacy] = float(row[public])
                if row.get("rating"):
                    macro["rating"] = str(row["rating"])
        portfolio_rows = self._current_rows.get("portfolio_current", [])
        if portfolio_rows:
            cash = float(portfolio_rows[0].get("cash", 0.0))
            for state in snapshots:
                state.cash = cash

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            try:
                self._responses.put(json.loads(line))
            except json.JSONDecodeError:
                self._stderr.append(f"Invalid worker output: {line.strip()}")

    def _read_stderr(self) -> None:
        assert self._process.stderr is not None
        for line in self._process.stderr:
            self._stderr.append(line.rstrip())

    def _worker_error(self, fallback: str) -> str:
        return self._stderr[-1] if self._stderr else fallback
