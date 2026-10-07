"""Measure a data-only graph copy that shares only proven immutable values."""

from __future__ import annotations

import gc
import json
import random
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(ROOT / "tools")]
import retail_precompute_probe as probe
from day_transition_audit_support import rss_bytes

from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.core.checkpoints import FIELDS, decode, restore

SCALARS = frozenset({str, int, float, bool, type(None)})


def immutable(value):
    return type(value) in SCALARS or (
        type(value) is datetime and (value.tzinfo is None or isinstance(value.tzinfo, timezone))
    )


def copy_graph(value, memo=None):
    """Keep immutable points; copy every mutable container and its references."""
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
        if identity in memo:  # Tuple/list cycles, as in the standard copier.
            return memo[identity]
        result = tuple(items)
        memo[identity] = result
        return result
    return deepcopy(value, memo)


def mutable_ids(value, found=None, seen=None):
    found = set() if found is None else found
    seen = set() if seen is None else seen
    if immutable(value) or id(value) in seen:
        return found
    seen.add(id(value))
    if isinstance(value, (dict, list, set, np.ndarray)):
        found.add(id(value))
    if isinstance(value, dict):
        for key, item in value.items():
            mutable_ids(key, found, seen)
            mutable_ids(item, found, seen)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            mutable_ids(item, found, seen)
    return found


def equal(left, right, seen=None):
    seen = set() if seen is None else seen
    pair = id(left), id(right)
    if pair in seen:
        return
    seen.add(pair)
    assert type(left) is type(right)
    if left is right:
        assert immutable(left) or (type(left) is tuple and all(immutable(v) for v in left))
        return
    if isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            equal(left[key], right[key], seen)
    elif isinstance(left, (list, tuple)):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            equal(a, b, seen)
    elif isinstance(left, np.ndarray):
        assert left.dtype == right.dtype and np.array_equal(left, right)
    else:
        assert left == right


def main():
    out = ROOT / ".cache/retail-decoupling"
    runtime = IntegratedRuntime(ROOT, data_dir=out / "alternate-copy-world", seed=1729)
    probe.deepcopy = copy_graph
    results = {}
    try:
        for label in ("1990-01-10", "end"):
            payload = decode(json.loads((ROOT / f".cache/day-transition-audit/checkpoint-{label}.json").read_text(encoding="utf-8")))
            restore(runtime.daten, payload)
            runtime.state.sync_from_legacy()
            runtime.market.warm_runtime_indexes()
            values = {k: getattr(runtime.daten, k) for k in FIELDS - probe.PLAYER_FIELDS if hasattr(runtime.daten, k)}
            samples = []
            for _ in range(3):
                gc.collect()
                pulses = []
                stop = threading.Event()

                def heartbeat():
                    while not stop.is_set():
                        pulses.append(time.perf_counter())
                        stop.wait(0.005)

                observer = threading.Thread(target=heartbeat)
                observer.start()
                before, rng = rss_bytes(), random.getstate()
                started = time.perf_counter()
                gc.disable()
                try:
                    clone = probe.clone_world(runtime.daten)
                finally:
                    gc.enable()
                finished, after = time.perf_counter(), rss_bytes()
                stop.set()
                observer.join()
                assert random.getstate() == rng
                times = [started, *[p for p in pulses if started <= p <= finished], finished]
                samples.append({"copy_ms": (finished-started)*1000,
                                "heartbeat_max_ms": max((b-a)*1000 for a,b in zip(times,times[1:])),
                                "rss_before": before, "rss_after": after})
                if not results:
                    actual = {k: getattr(clone[0], k) for k in values}
                    equal(values, actual)
                    assert not (mutable_ids(values) & mutable_ids(actual))
                del clone
            # Verify mature ownership too, outside all measured samples.
            clone = probe.clone_world(runtime.daten)
            actual = {k: getattr(clone[0], k) for k in values}
            equal(values, actual)
            assert not (mutable_ids(values) & mutable_ids(actual))
            del clone, actual
            results[label] = samples
            print(label, json.dumps(samples), flush=True)
        (out / "alternate-copy.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
