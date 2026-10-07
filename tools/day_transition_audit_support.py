"""Measurement-only hooks. No production source or economic logic is changed."""
from __future__ import annotations

import ast
import cProfile
import ctypes
import functools
import gc
import inspect
import json
import os
import re
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

ACTIVE = None
ORIGINAL_DUMPS = json.dumps
INSTALLED = False


def rss_bytes():
    if os.name != "nt":
        return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [(x, ctypes.c_size_t) for x in ("peak_rss", "rss", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]
    row = Counters()
    row.cb = ctypes.sizeof(row)
    process = ctypes.windll.kernel32.GetCurrentProcess
    process.restype = ctypes.c_void_p
    fn = ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    return int(row.rss) if fn(process(), ctypes.byref(row), row.cb) else None


def begin(date, profile_path=None):
    global ACTIVE
    ACTIVE = {"date": str(date), "t_start": time.perf_counter(), "cpu_start": time.process_time(),
              "rss_start": rss_bytes(), "thread_cpu_start": time.thread_time(), "spans": defaultdict(float), "calls": defaultdict(int),
              "sql": [], "batches": [], "gc": [], "profile_path": str(profile_path) if profile_path else None}
    if profile_path:
        ACTIVE["profiler"] = cProfile.Profile()
        ACTIVE["profiler"].enable()
    return ACTIVE


def finish():
    global ACTIVE
    current = ACTIVE
    if current is None:
        return None
    if "profiler" in current:
        profiler = current.pop("profiler")
        profiler.disable()
        profiler.dump_stats(current["profile_path"])
    current.update(t_end=time.perf_counter(), cpu_ms=(time.process_time()-current.pop("cpu_start"))*1000,
                   main_worker_thread_cpu_ms=(time.thread_time()-current.pop("thread_cpu_start"))*1000,
                   rss_end=rss_bytes())
    current["spans"] = dict(current["spans"])
    current["calls"] = dict(current["calls"])
    ACTIVE = None
    return current


@contextmanager
def span(label):
    active = ACTIVE
    if active is None:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        active["spans"][label] += (time.perf_counter()-start)*1000
        active["calls"][label] += 1


def wrap(owner, name, label):
    original = getattr(owner, name, None)
    if original is None or getattr(original, "_audit_wrapped", False):
        return
    @functools.wraps(original)
    def measured(*args, **kwargs):
        with span(label):
            return original(*args, **kwargs)
    measured._audit_wrapped = True
    setattr(owner, name, measured)


class ConnectionProxy:
    def __init__(self, connection):
        self.raw = connection

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def execute(self, sql, *args, **kwargs):
        return self._invoke("execute", sql, *args, **kwargs)

    def executemany(self, sql, *args, **kwargs):
        return self._invoke("executemany", sql, *args, **kwargs)

    def _invoke(self, method, sql, *args, **kwargs):
        active = ACTIVE
        if active is not None:
            active["last_sql"] = str(sql)
        copy_bytes = None
        if active is not None and str(sql).lstrip().upper().startswith("COPY "):
            match = re.search(r"FROM '([^']+)'", str(sql))
            if match:
                copy_bytes = Path(match.group(1)).stat().st_size
        start = time.perf_counter()
        result = getattr(self.raw, method)(sql, *args, **kwargs)
        if active is not None:
            elapsed = (time.perf_counter()-start)*1000
            command = str(sql).lstrip().split()[0].upper()
            active["sql"].append({"command": command, "method": method, "ms": elapsed,
                                  "sql": str(sql)[:300], "rows": len(args[0]) if method == "executemany" and args else None,
                                  "copy_bytes": copy_bytes})
            active["spans"]["duckdb.native_api"] += elapsed
            active["calls"]["duckdb.native_api"] += 1
        return self if result is self.raw else result

    def fetchall(self):
        with span("duckdb.materialize"):
            return self.raw.fetchall()

    def fetchone(self):
        with span("duckdb.materialize"):
            return self.raw.fetchone()


def instrument_market_sections(module):
    """Add five timers around existing top-level loops, preserving their AST."""
    function = module.update_markt_kurse
    tree = ast.parse(inspect.getsource(function))
    root = tree.body[0]
    names = {"countries": "market.fx_strength", "daten_module.WAEHRUNGEN": "market.fx_pairs"}
    for i, statement in enumerate(root.body):
        if not isinstance(statement, ast.For):
            continue
        expression = ast.unparse(statement.iter)
        label = names.get(expression)
        for key, title in (("commodities", "commodity_prices"), ("stocks", "stock_prices"), ("cryptos", "crypto_prices")):
            if expression == f"runtime_assets['{key}']":
                label = "market." + title
        if label:
            root.body[i] = ast.With(items=[ast.withitem(context_expr=ast.Call(func=ast.Name(id="_audit_span", ctx=ast.Load()), args=[ast.Constant(label)], keywords=[]))], body=[statement])
    ast.fix_missing_locations(tree)
    ast.increment_lineno(tree, inspect.getsourcelines(function)[1] - 1)
    module.__dict__["_audit_span"] = span
    namespace = {}
    exec(compile(tree, inspect.getsourcefile(function), "exec"), module.__dict__, namespace)
    module.update_markt_kurse = namespace[root.name]


def install():
    global INSTALLED
    if INSTALLED:
        return
    INSTALLED = True
    from kojakstreet.adapters import legacy_runtime, legacy_state
    from kojakstreet.core import production_chains, market_calculations, data_store
    from kojakstreet.core.simulation import DailySimulation
    instrument_market_sections(market_calculations)
    for name in ("_update_country_trade_flows", "_update_company_utilization", "_company_capacities", "_sector_activity", "_sector_input_demand", "_record_company_quantity_history"):
        if name != "_record_company_quantity_history":
            wrap(production_chains, name, "production." + name.lstrip("_"))
    for name in ("update_funds", "_update_indices_from_runtime_cache", "update_market_psychology"):
        wrap(market_calculations, name, "market." + name.lstrip("_"))
    for name in ("record_day", "flush", "_compact_completed_history", "_asset_rows", "_product_rows", "_company_rows", "_company_output_rows", "_country_trade_rows", "_fund_allocation_rows", "_bond_row_sets", "history_series", "recent_series", "asset_history", "_replace_current_tables"):
        wrap(data_store.EconomicDataStore, name, "store." + name.lstrip("_"))
    original_init = data_store.EconomicDataStore.__init__
    def store_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if self._connection is not None:
            self._connection = ConnectionProxy(self._connection)
    data_store.EconomicDataStore.__init__ = store_init
    original_insert = data_store.EconomicDataStore._insert_rows
    def insert(self, table, rows):
        if ACTIVE is not None:
            ACTIVE["batches"].append({"table": table, "rows": len(rows), "cells": len(rows)*len(rows[0]) if rows else 0})
        with span("store.insert_with_csv"):
            return original_insert(self, table, rows)
    data_store.EconomicDataStore._insert_rows = insert
    original_step = DailySimulation.step_day
    def step(self):
        if ACTIVE is not None:
            ACTIVE["t_sim_start"] = time.perf_counter()
        with span("simulation.core"):
            result = original_step(self)
        if ACTIVE is not None:
            ACTIVE["t1"] = time.perf_counter()
            ACTIVE["phases"] = list(getattr(self.daten, "simulation_phase_timings", []))
        return result
    DailySimulation.step_day = step
    wrap(DailySimulation, "_run_policy_decision", "simulation.policy_decision")
    original_record = data_store.EconomicDataStore.record_day
    def record(self, *args, **kwargs):
        result = original_record(self, *args, **kwargs)
        if ACTIVE is not None:
            ACTIVE["t_persist"] = time.perf_counter()
        return result
    data_store.EconomicDataStore.record_day = record
    wrap(legacy_runtime.IntegratedRuntime, "snapshot_for_view", "snapshot.prepare")
    wrap(legacy_runtime, "snapshot_from_legacy", "snapshot.copy")
    def gc_event(phase, info):
        if ACTIVE is not None:
            ACTIVE["gc"].append({"phase": phase, "time": time.perf_counter(), **info})
    gc.callbacks.append(gc_event)


def install_worker_logging(output):
    """Run the real process protocol; only wrappers and an out-of-band log differ."""
    import sys
    from kojakstreet import live_worker, live_process
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    stream = output.open("a", encoding="utf-8")
    original_execute = live_worker._execute
    def execute(runtime, command, arguments):
        if command == "advance":
            begin(runtime.daten.datum.date())
        with span("worker.execute"):
            result = original_execute(runtime, command, arguments)
        if ACTIVE is not None:
            ACTIVE["t_worker_prepared"] = time.perf_counter()
            ACTIVE["row_counts"] = {k: len(v) for k,v in result[0].get("current_rows", {}).items()}
        return result
    live_worker._execute = execute
    wrap(live_worker, "_runtime_result", "worker.result_prepare")
    wrap(live_worker, "game_state_payload", "worker.state_encode")
    try:
        from kojakstreet.day_delta import DayStateEncoder
    except ModuleNotFoundError:
        pass  # Frozen pre-remediation source has no delta contract.
    else:
        wrap(DayStateEncoder, "update", "worker.day_delta")
    def dumps(value, *args, **kwargs):
        with span("worker.json_encode"):
            result = ORIGINAL_DUMPS(value, *args, **kwargs)
        if ACTIVE is not None and isinstance(value, dict) and "id" in value and "result" in value:
            ACTIVE["response_bytes"] = len(result.encode("utf-8")) + 1
            ACTIVE["t_encoded"] = time.perf_counter()
        return result
    json.dumps = dumps
    class Output:
        def __getattr__(self, name):
            return getattr(sys.__stdout__, name)
        def write(self, text):
            with span("worker.pipe_write"):
                return sys.__stdout__.write(text)
        def flush(self):
            with span("worker.pipe_flush"):
                result = sys.__stdout__.flush()
            if ACTIVE is not None and "t_encoded" in ACTIVE:
                row = finish()
                stream.write(ORIGINAL_DUMPS(row) + "\n")
                stream.flush()
            return result
    sys.stdout = Output()
    return live_worker
