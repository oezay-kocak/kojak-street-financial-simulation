"""Own one unpublished world day; never copy or replace the player's books."""

from __future__ import annotations

import hashlib
import importlib
import pickle
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np

from kojakstreet.core.asset_market_engine import AssetMarketEngine
from kojakstreet.core.bond_portfolio_engine import BondPortfolioEngine
from kojakstreet.core.checkpoints import FIELDS
from kojakstreet.core.macro_engine import MacroEngine
from kojakstreet.core.production_engine import ProductionEngine
from kojakstreet.core.simulation import DailySimulation
from kojakstreet.core.simulation_state import SimulationState

_local = threading.local()


class _WorldRandom:
    def __getattr__(self, name):
        stream = getattr(_local, "rng", None)
        return getattr(stream if stream is not None and hasattr(stream, name) else random, name)


def install_detached_rng():
    """Measurement-only routing; application imports and scheduling stay unchanged."""
    for name in (
        "bonds", "commodities", "companies", "company_lifecycle", "cryptos",
        "established_world", "events", "funds", "global_macro",
        "macro_calculations", "market_calculations", "monthly_assets",
    ):
        importlib.import_module("kojakstreet.core." + name).random = _WorldRandom()


@contextmanager
def detached_world_rng(state):
    stream = random.Random(0)
    stream.setstate(state)
    previous = getattr(_local, "rng", None)
    _local.rng = stream
    try:
        yield stream
    finally:
        _local.rng = previous

PLAYER_FIELDS = frozenset({
    "bargeld", "depot", "perpetuals", "anleihen", "kredite", "forex_depot",
    "DEPOT_VERMOEGEN_HISTORIE", "realisierte_guv_historie", "player_rng_state",
    "PLAYER_NEWS_SPEICHER", "spiel_pausiert", "SPIEL_AKTIV", "turbo_modus",
    "intervall", "anzeige_waehrung",
})
WORLD_FIELDS = FIELDS - PLAYER_FIELDS
SCALARS = frozenset({str, int, float, bool, type(None)})


def immutable(value):
    return type(value) in SCALARS or (
        type(value) is datetime and (value.tzinfo is None or isinstance(value.tzinfo, timezone))
    )


def copy_graph(value, memo=None):
    """Share proven immutable points, preserving an isolated mutable graph."""
    if immutable(value):
        return value
    if type(value) is tuple and all(immutable(item) for item in value):
        return value
    if memo is None:
        memo = {}
    identity = id(value)
    if identity in memo:
        return memo[identity]
    if type(value) is dict:
        result = {}
        memo[identity] = result
        for key, item in value.items():
            result[copy_graph(key, memo)] = copy_graph(item, memo)
        return result
    if type(value) is list:
        result = []
        memo[identity] = result
        result.extend(copy_graph(item, memo) for item in value)
        return result
    if type(value) is tuple:
        items = [copy_graph(item, memo) for item in value]
        if identity in memo:
            return memo[identity]
        result = tuple(items)
        memo[identity] = result
        return result
    return deepcopy(value, memo)


def clone_world(daten):
    values = copy_graph({name: getattr(daten, name) for name in WORLD_FIELDS if hasattr(daten, name)})
    values.update(
        depot={}, perpetuals={}, anleihen=[], kredite={}, forex_depot={}, bargeld=0.0,
        DEPOT_VERMOEGEN_HISTORIE=[], realisierte_guv_historie=[],
        SPIEL_AKTIV=True, spiel_pausiert=False, PYSIDE_RUNTIME=True, CHART_REFFS={},
    )
    namespace = SimpleNamespace(**values)
    state = SimulationState.from_legacy(namespace)
    market = AssetMarketEngine(state)
    simulation = DailySimulation(state, MacroEngine(state), market, BondPortfolioEngine(state), ProductionEngine(state))
    market.warm_runtime_indexes()
    return namespace, simulation


def world_key(daten, epoch=0):
    return (
        epoch, daten.datum, getattr(daten, "world_generation", 0),
        getattr(daten, "simulation_seed", 0),
        hashlib.sha256(pickle.dumps((random.getstate(), np.random.get_state()), protocol=5)).digest(),
    )


@dataclass
class PreparedWorld:
    namespace: SimpleNamespace
    frame: object
    rng: tuple
    key: tuple
    metrics: dict


def prepare_world(daten, key, rng):
    started = time.perf_counter()
    with detached_world_rng(rng) as stream:
        namespace, simulation = clone_world(daten)
        copied = time.perf_counter()
        frame = simulation.prepare_world_day()
        future_rng = stream.getstate()
    ready = time.perf_counter()
    return PreparedWorld(namespace, frame, future_rng, key, {
        "source_date": frame.date.date().isoformat(), "started_perf": started,
        "ready_perf": ready, "copy_ms": (copied-started)*1000,
        "world_ms": (ready-copied)*1000, "preparation_ms": (ready-started)*1000,
    })


def publish_world(runtime, prepared, epoch=0):
    if prepared.key != world_key(runtime.daten, epoch):
        raise ValueError("Prepared world no longer matches the authoritative world")
    started = time.perf_counter()
    daten = runtime.daten
    for name in list(vars(daten)):
        if (name.startswith("_") and not name.startswith("__") and name != "_tape_display_ids") or name in {
            "market_runtime_assets", "market_runtime_index", "bond_market_by_symbol",
            "bond_market_symbol_signature",
        }:
            delattr(daten, name)
    for name in WORLD_FIELDS:
        if hasattr(prepared.namespace, name):
            setattr(daten, name, getattr(prepared.namespace, name))
    daten.simulation_phase_timings = prepared.namespace.simulation_phase_timings
    daten.bond_market_by_symbol = {str(bond["symbol"]): bond for bond in daten.bond_market}
    runtime.state.sync_from_legacy()
    runtime.market.warm_runtime_indexes()
    random.setstate(prepared.rng)
    transferred = time.perf_counter()
    runtime.simulation.commit_player_day(prepared.frame)
    committed = time.perf_counter()
    return {**prepared.metrics, "hit": True,
            "publication_ms": (transferred-started)*1000,
            "accounting_ms": (committed-transferred)*1000}


class WorldPreparer:
    """One speculative result; explicit world replacements invalidate its epoch."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="world-prepare")
        self.future = self.key = None
        self.epoch = 0
        self.closed = False
        self.miss_reason = "not_started"

    def start(self):
        if self.closed or not self.runtime.daten.SPIEL_AKTIV:
            return
        key = world_key(self.runtime.daten, self.epoch)
        if self.future is not None and self.key == key:
            return
        self.discard()
        self.key = key
        self.future = self.executor.submit(prepare_world, self.runtime.daten, key, random.getstate())

    def take(self):
        future = self.future
        if future is None:
            self.miss_reason = "not_started"
            return None
        if self.key != world_key(self.runtime.daten, self.epoch):
            self.miss_reason = "stale"
            self.discard()
            return None
        if not future.done():
            self.miss_reason = "not_ready"
            self.discard()
            return None
        self.future = self.key = None
        try:
            return future.result()
        except Exception as exc:  # noqa: BLE001 - speculative failure always falls back
            self.miss_reason = "failed:" + type(exc).__name__
            return None

    def discard(self):
        if self.future is not None:
            self.future.cancel()
        self.future = self.key = None

    def invalidate(self):
        self.epoch += 1
        self.discard()

    def close(self):
        self.closed = True
        self.invalidate()
        self.executor.shutdown(wait=False, cancel_futures=True)
