"""Versioned, data-only checkpoints. No executable objects are accepted."""

from __future__ import annotations

import json
import os
import random
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np

VERSION = 6
SUPPORTED_VERSIONS = {4, 5, VERSION}
# These caches contain live object references, not independent numerical state.
# JSON cannot preserve that identity. Rebuild them from holdings after restore.
REFERENCE_CACHE_KEYS = frozenset({"_resolved_underlyings", "_fund_pressure_targets"})
FIELDS = frozenset("""
LAENDER WAEHRUNGEN RATINGS BRANCHEN ROHSTOFFE_KAT datum bargeld kredite depot
perpetuals anleihen spiel_pausiert SPIEL_AKTIV turbo_modus intervall aktives_event
event_dauer NEWS_SPEICHER anzeige_waehrung waehrungen_staerke forex_depot aktien
rohstoffe processed_products kryptos fonds indizes derivatives makro
FOREX_PAARE_HISTORIE LETZTER_ZINS_TAG LETZTER_REPORT_MONAT MAKRO_HISTORIE
DEPOT_VERMOEGEN_HISTORIE gli_index realisierte_guv_historie GLI_HISTORIE
global_macro GLOBAL_MACRO_HISTORIE fund_universe_complete bond_market
last_bond_issue_year last_need_based_bond_issue_month derivative_universe_complete
market_regime market_psychology bond_market_refresh_cursor bond_market_archive
bond_market_archive_count retired_company_tickers simulation_seed
    handels_tage_zaehler last_completed_simulation_date last_bond_market_update_ordinal
    economic_shocks structural_event_state extreme_tail_events extreme_tail_seen world_generation
""".split())
REQUIRED = {"datum", "aktien", "rohstoffe", "kryptos", "makro", "depot", "forex_depot", "bargeld"}


def encode(value):
    if isinstance(value, datetime):
        return {"__type__": "datetime", "value": value.isoformat()}
    if isinstance(value, np.ndarray):
        return {"__type__": "ndarray", "dtype": str(value.dtype), "items": value.tolist()}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (tuple, set)):
        return {"__type__": type(value).__name__, "items": [encode(v) for v in value]}
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value):
            return {k: encode(v) for k, v in value.items()}
        return {"__type__": "mapping", "items": [[encode(k), encode(v)] for k, v in value.items()]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"Unsupported checkpoint value: {type(value).__name__}")


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if isinstance(value, dict):
        tag = value.get("__type__")
        if tag == "datetime":
            return datetime.fromisoformat(value["value"])
        if tag in ("tuple", "set"):
            return (tuple if tag == "tuple" else set)(decode(v) for v in value["items"])
        if tag == "ndarray":
            dtype = np.dtype(value["dtype"])
            if dtype.kind not in "biuf":
                raise ValueError("Checkpoint arrays must be numeric")
            return np.array(value["items"], dtype=dtype)
        if tag == "mapping":
            return {decode(k): decode(v) for k, v in value["items"]}
        return {k: decode(v) for k, v in value.items()}
    return value


def capture(state):
    # Preserve bounded computational histories and EMA/momentum state exactly.
    # Reference caches are rebuilt, never copied into independent asset objects.
    return {"save_version": VERSION, "checkpoint": {k: _checkpoint_copy(getattr(state, k), k) for k in sorted(FIELDS) if hasattr(state, k)},
            "rng": {"python": random.getstate(), "numpy": np.random.get_state()}}


def restore(state, payload):
    if payload.get("save_version") not in SUPPORTED_VERSIONS:
        raise ValueError("Unsupported checkpoint version")
    world = payload.get("checkpoint", {})
    if not isinstance(world, dict) or not REQUIRED.issubset(world) or set(world) - FIELDS:
        raise ValueError("Incomplete or unknown checkpoint fields")
    if not isinstance(world["datum"], datetime):
        raise ValueError("Invalid checkpoint date")
    for key in REQUIRED - {"datum", "bargeld"}:
        if not isinstance(world[key], dict):
            raise ValueError(f"Invalid checkpoint book: {key}")
    for book in ("aktien", "rohstoffe", "kryptos", "makro", "depot"):
        if not all(isinstance(v, dict) for v in world[book].values()):
            raise ValueError(f"Invalid checkpoint entries: {book}")
    session = payload.get("analytics_session", {})
    if not isinstance(session, dict) or set(session) - {"product_daily", "bond_daily", "manifest", "recent_rows"}:
        raise ValueError("Invalid checkpoint analytics")
    rows_by_table = session.get("recent_rows", session)
    if not isinstance(rows_by_table, dict) or set(rows_by_table) - {"product_daily", "bond_daily"}:
        raise ValueError("Invalid checkpoint recent history")
    for table, rows in rows_by_table.items():
        width = {"product_daily": 11, "bond_daily": 17}[table]
        if not isinstance(rows, list) or any(not isinstance(row, (tuple, list)) or len(row) != width for row in rows):
            raise ValueError("Invalid checkpoint history rows")
    # Older v4/v5 files may contain serialized copies of reference caches.
    # Discard those too; missing history from old saves cannot be recovered.
    world = _checkpoint_copy(world)
    bond_lookup = {str(b["symbol"]): b for b in world.get("bond_market", [])}
    # Validate RNGs on temporary instances before mutating the live world.
    rng = payload["rng"]
    random.Random().setstate(rng["python"])
    np.random.RandomState().set_state(rng["numpy"])
    for key in list(vars(state)):
        if key in FIELDS or (key.startswith("_") and not key.startswith("__")) or key in {"market_runtime_assets", "market_runtime_index", "bond_market_by_symbol", "bond_market_symbol_signature", "simulation_phase_timings"}:
            delattr(state, key)
    for key, value in world.items():
        setattr(state, key, value)
    state.bond_market_by_symbol = bond_lookup
    random.setstate(rng["python"])
    np.random.set_state(rng["numpy"])


def _checkpoint_copy(value, key: str = ""):
    """Copy numerical state without breaking the live world's reference graph.

    Retention belongs to the simulation/history layer. Truncating it only on
    save changes EMA cache lengths, momentum lookbacks and future fund returns.
    """

    if key in {"regional_history", "company_output_history", "company_input_history"}:
        # Display/analytics topology, not market lookbacks. The current
        # input sample is also used by data_store; two samples retain it.
        # Older analytics belong to the session store, not the checkpoint.
        return _copy_recent_display_history(value)
    if isinstance(value, dict):
        return {
            name: _checkpoint_copy(item, str(name))
            for name, item in value.items()
            if name not in REFERENCE_CACHE_KEYS
        }
    if isinstance(value, list):
        return [_checkpoint_copy(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_checkpoint_copy(item) for item in value)
    return value


def _copy_recent_display_history(value):
    if isinstance(value, dict):
        return {name: _copy_recent_display_history(item) for name, item in value.items()}
    if isinstance(value, list):
        return [_checkpoint_copy(item) for item in value[-2:]]
    return _checkpoint_copy(value)


def atomic_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(encode(payload), stream, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
