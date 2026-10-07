"""Versioned UI current-state/history deltas, independent of savegame state."""

from __future__ import annotations

import base64
import gc
import io
import pickle
import time
import zlib
from copy import deepcopy
from dataclasses import fields
from typing import Any

from kojakstreet.core.checkpoints import decode, encode
from kojakstreet.core.state import GameState

_ATOMS = {str, int, float, bool, bytes, type(None)}
_NATIVE_TYPES = _ATOMS | {list, tuple, dict, set, frozenset}


def public_copy(value):
    """Detach UI data; private computation caches stay with the simulation."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {
            key: public_copy(item) for key, item in value.items() if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [public_copy(item) for item in value]
    if isinstance(value, tuple):
        if all(type(item) in _ATOMS for item in value):
            return value
        return tuple(public_copy(item) for item in value)
    return deepcopy(value)


def state_values(state: GameState) -> dict[str, Any]:
    return {field.name: getattr(state, field.name) for field in fields(GameState)}


class DayStateEncoder:
    """Track an exact detached UI baseline, separate from economic/RNG state.

    History equality uses values without date parsing, sorting or serialization.
    Ordinary append/rollover copies only the new tail. Earlier corrections use
    an explicit splice; only that series is retransmitted when necessary.
    """

    def __init__(self, state: GameState):
        self.baseline = public_copy(state_values(state))
        self.revision = 0

    def update(self, state: GameState) -> dict:
        changes = []
        collecting = gc.isenabled()
        if collecting:
            gc.disable()
        try:
            self._mapping(self.baseline, state_values(state), [], changes)
            encoded = encode_changes(changes)
            previous = self.revision
            self.revision += 1
            return {
                "version": 1,
                "base_revision": previous,
                "revision": self.revision,
                **encoded,
            }
        finally:
            # Operation paths/tails and pickle memos live only for this message.
            # Release them before collecting, rather than promoting them while
            # still building the batch and repeatedly scanning a mature world.
            changes.clear()
            if collecting:
                gc.collect(0)
                gc.enable()

    def _mapping(self, old, new, path, changes):
        removed = [key for key in old if key not in new or str(key).startswith("_")]
        if removed:
            changes.append(["remove", path, removed])
            for key in removed:
                del old[key]
        updates = {}
        for key, value in new.items():
            if str(key).startswith("_"):
                continue
            previous = old.get(key)
            child_path = [*path, key]
            if key in old and isinstance(previous, dict) and isinstance(value, dict):
                self._mapping(previous, value, child_path, changes)
            elif key in old and isinstance(previous, list) and isinstance(value, list):
                self._sequence(previous, value, child_path, changes)
            elif key not in old or previous != value:
                updates[key] = public_copy(value)
        if updates:
            changes.append(["update", path, updates])
            old.update(updates)

    def _sequence(self, old, new, path, changes):
        if old == new:
            return
        # Lists of entities (notably bonds) retain per-item history deltas.
        if old and new and isinstance(old[0], dict) and isinstance(new[0], dict):
            count = min(len(old), len(new))
            for index in range(count):
                if isinstance(old[index], dict) and isinstance(new[index], dict):
                    self._mapping(old[index], new[index], [*path, index], changes)
                elif old[index] != new[index]:
                    value = public_copy(new[index])
                    old[index] = value
                    changes.append(["set", [*path, index], value])
            if len(old) != len(new):
                tail = public_copy(new[count:])
                changes.append(["splice", path, [0, count, tail]])
                old[count:] = tail
            return
        shared = min(len(old), len(new))
        drop = 0
        if old == new[: len(old)]:
            keep = len(old)
        elif old and len(new) >= len(old) - 1 and old[1:] == new[: len(old) - 1]:
            drop, keep = 1, len(old) - 1
        elif shared and old[: shared - 1] == new[: shared - 1]:
            keep = shared - 1
        else:
            keep = 0
            while keep < shared and old[keep] == new[keep]:
                keep += 1
        tail = public_copy(new[keep:])
        changes.append(["splice", path, [drop, keep, tail]])
        if drop:
            del old[:drop]
        old[keep:] = tail


class PreparedDayDelta(dict):
    """Typed payload produced by the process reader, never a wire-level flag."""


class _DataUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError("Day deltas cannot instantiate Python classes")

    def persistent_load(self, value):
        if not isinstance(value, tuple) or len(value) != 2 or value[0] != "checkpoint-value":
            raise pickle.UnpicklingError("Unsupported day-delta value")
        return decode(value[1])


class _DataPickler(pickle.Pickler):
    def persistent_id(self, value):
        if type(value) in _NATIVE_TYPES:
            return None
        return ("checkpoint-value", encode(value))


def encode_changes(changes: list) -> dict:
    """Use a data-only binary body for large local-process messages.

    Saves keep their existing JSON schema. The private pipe's body consists
    solely of built-in containers/scalars; class lookup is forbidden on read.
    Rare datetime/set/array values use the existing data-only checkpoint tags
    as persistent data tags, avoiding per-point tuple tags in large histories.
    """
    if len(changes) < 256:
        return {"changes": encode(changes)}
    chunks = []
    for offset in range(0, len(changes), 2048):
        stream = io.BytesIO()
        batch = []
        for operation, path, value in changes[offset : offset + 2048]:
            if operation == "splice":
                drop, keep, tail = value
                value = (drop, keep, tuple(tail))
            batch.append((operation, tuple(path), value))
        _DataPickler(stream, protocol=5).dump(batch)
        chunks.append(base64.b64encode(zlib.compress(stream.getvalue(), level=1)).decode("ascii"))
    return {"codec": "data-pickle5-zlib1", "changes": chunks}


def prepare_day_delta(payload: dict) -> PreparedDayDelta:
    codec = payload.get("codec")
    if codec is None:
        changes = decode(payload["changes"])
    elif codec == "data-pickle5-zlib1":
        chunks = payload["changes"]
        if isinstance(chunks, str):
            chunks = [chunks]
        changes = []
        collecting = gc.isenabled()
        if collecting:
            gc.disable()
        try:
            for chunk in chunks:
                blob = zlib.decompress(base64.b64decode(chunk, validate=True))
                changes.extend(_DataUnpickler(io.BytesIO(blob)).load())
                # Collect complete chunks, so scalar history tuples become
                # untracked before promotion. Automatic full-world scans in a
                # half-built batch otherwise hold the GIL for hundreds of ms.
                if collecting:
                    gc.collect(0)
                time.sleep(0)
            if collecting:
                gc.collect(1)
        finally:
            if collecting:
                gc.enable()
    else:
        raise ValueError("Unsupported day-delta codec")
    return PreparedDayDelta({**payload, "changes": changes})


def apply_day_delta(state: GameState, payload: dict, revision: int) -> int:
    if payload.get("version") != 1:
        raise ValueError("Unsupported day-delta version")
    if payload.get("base_revision") != revision or payload.get("revision") != revision + 1:
        raise ValueError("Day-delta revision mismatch")
    root = state_values(state)
    changes = (
        payload["changes"]
        if isinstance(payload, PreparedDayDelta)
        else prepare_day_delta(payload)["changes"]
    )
    for operation, path, value in changes:
        target = root
        for key in path[:-1] if operation == "set" else path:
            target = target[key]
        if operation == "update":
            target.update(value)
        elif operation == "remove":
            for key in value:
                del target[key]
        elif operation == "set":
            target[path[-1]] = value
        elif operation == "splice":
            drop, keep, tail = value
            if drop:
                del target[:drop]
            target[keep:] = tail
        else:
            raise ValueError(f"Unknown day-delta operation: {operation}")
    for field in fields(GameState):
        setattr(state, field.name, root[field.name])
    return payload["revision"]
