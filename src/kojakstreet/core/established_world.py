"""Established-world configuration, validation, diagnostics and bundle I/O."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import random
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np

from kojakstreet.core.checkpoints import SUPPORTED_VERSIONS, capture, decode, encode
from kojakstreet.core.cryptos import TARGET_CRYPTO_COUNT
from kojakstreet.core.history import (
    ECONOMIC_MODEL_VERSION,
    HISTORY_SCHEMA_VERSION,
    LEGACY_ECONOMIC_MODEL_VERSION,
)

GENERATOR_VERSION = 4
BUNDLE_SCHEMA_VERSION = 1
SUPPORTED_PREHISTORY_YEARS = (50, 75, 100)
PLAYER_STARTING_CASH_GD = 25_000.0


class WorldMode(StrEnum):
    GENESIS = "GENESIS"
    HETEROGENEOUS = "HETEROGENEOUS"
    ESTABLISHED = "ESTABLISHED"


@dataclass(frozen=True, slots=True)
class WorldGenerationConfig:
    mode: WorldMode = WorldMode.GENESIS
    seed: int = 1729
    prehistory_years: int = 0
    economic_model_version: str = ECONOMIC_MODEL_VERSION
    history_schema_version: int = HISTORY_SCHEMA_VERSION
    generator_version: int = GENERATOR_VERSION
    world_id: str = ""
    world_name: str = ""
    created_at: str = ""

    def normalized(self) -> WorldGenerationConfig:
        mode = WorldMode(self.mode)
        years = int(self.prehistory_years)
        if mode in {WorldMode.GENESIS, WorldMode.HETEROGENEOUS}:
            years = 0
        elif years not in SUPPORTED_PREHISTORY_YEARS:
            raise ValueError(f"Established prehistory must be one of {SUPPORTED_PREHISTORY_YEARS}")
        return WorldGenerationConfig(
            mode=mode,
            seed=int(self.seed),
            prehistory_years=years,
            economic_model_version=str(self.economic_model_version),
            history_schema_version=int(self.history_schema_version),
            generator_version=int(self.generator_version),
            world_id=self.world_id or uuid.uuid4().hex,
            world_name=str(self.world_name).strip(),
            created_at=self.created_at or datetime.now(UTC).isoformat(),
        )

    def trajectory_identity(self) -> dict[str, object]:
        """Return only inputs that may define the economic trajectory."""
        identity = {
            "mode": str(self.mode),
            "seed": int(self.seed),
            "prehistory_years": int(self.prehistory_years),
            "economic_model_version": self.economic_model_version,
            "history_schema_version": self.history_schema_version,
            "generator_version": self.generator_version,
            "politics_model_version": 1,
        }
        if self.mode == WorldMode.HETEROGENEOUS:
            from kojakstreet.core.heterogeneous_start import INITIALIZATION_VERSION
            identity["heterogeneous_initialization_version"] = INITIALIZATION_VERSION
        return identity


TAIL_THRESHOLDS = {
    "cash_reserves": 100_000_000_000.0,
    "debt": 100_000_000_000.0,
    "market_cap": 1_000_000_000_000.0,
    "kurs": 100_000.0,
    "revenue": 100_000_000_000.0,
    "free_cash_flow": 25_000_000_000.0,
}


def record_extreme_tail_crossings(state: Any, thresholds: dict[str, float] | None = None) -> list[dict[str, object]]:
    """Record the first company/metric threshold crossing without changing economics."""
    thresholds = thresholds or TAIL_THRESHOLDS
    seen = set(getattr(state, "extreme_tail_seen", set()))
    events = list(getattr(state, "extreme_tail_events", []))
    added = []
    for ticker, asset in getattr(state, "aktien", {}).items():
        for metric, threshold in thresholds.items():
            key = f"{ticker}:{metric}:{threshold:g}"
            value = _number(asset.get(metric, 0.0))
            if key in seen or value < threshold:
                continue
            history = asset.get("historie", [])
            recent_values = [_history_close(item) for item in history[-31:]]
            recent_return = (
                (recent_values[-1] / recent_values[0]) - 1.0
                if len(recent_values) >= 2 and recent_values[0] != 0
                else 0.0
            )
            event = {
                "date": state.datum.isoformat(),
                "ticker": str(ticker),
                "sector": str(asset.get("branche", "")),
                "metric": metric,
                "threshold": threshold,
                "value": value,
                "price": _number(asset.get("kurs", 0.0)),
                "shares_outstanding": _number(asset.get("aktien_anzahl", 0.0)),
                "market_cap": _number(asset.get("market_cap", 0.0)),
                "revenue": _number(asset.get("revenue", 0.0)),
                "free_cash_flow": _number(asset.get("free_cash_flow", 0.0)),
                "cash": _number(asset.get("cash_reserves", 0.0)),
                "debt": _number(asset.get("debt", 0.0)),
                "funding_rate": _number(asset.get("funding_rate", 0.0)),
                "interest_coverage": _number(asset.get("interest_coverage", 0.0)),
                "rating": str(asset.get("rating", "")),
                "credit_score": _number(asset.get("credit_score", 0.0)),
                "operating_health": _number(asset.get("operating_health", 0.0)),
                "capacity": _number(asset.get("production_capacity", 0.0)),
                "capacity_utilization": _number(asset.get("capacity_utilization", 0.0)),
                "recent_30d_return": recent_return,
                "valuation_residual": _number(asset.get("fundamental_repricing_remaining", 0.0)),
                "source": "first_threshold_crossing",
            }
            seen.add(key)
            events.append(event)
            added.append(event)
    state.extreme_tail_seen = seen
    state.extreme_tail_events = events
    return added


def reset_player_state(state: Any) -> None:
    """Reset player books after prehistory while preserving the simulated world."""
    currencies = list(getattr(state, "WAEHRUNGEN", {}))
    state.bargeld = 0.0
    state.depot = {}
    state.perpetuals = {}
    state.anleihen = []
    state.kredite = {currency: 0.0 for currency in currencies}
    state.forex_depot = {currency: 0.0 for currency in currencies}
    reserve = "GD" if "GD" in state.forex_depot else next(iter(state.forex_depot), "GD")
    state.forex_depot[reserve] = PLAYER_STARTING_CASH_GD
    state.realisierte_guv_historie = []
    state.DEPOT_VERMOEGEN_HISTORIE = [(PLAYER_STARTING_CASH_GD, state.datum.strftime("%d.%m.%Y"))]
    state.spiel_pausiert = True
    state.SPIEL_AKTIV = True


def sanity_gate(state: Any, history_manifest: dict[str, object] | None = None) -> dict[str, object]:
    """Reject structurally broken worlds while allowing unusual coherent ones."""
    errors: list[str] = []
    warnings: list[str] = []
    books = {
        "countries": getattr(state, "makro", {}),
        "stocks": getattr(state, "aktien", {}),
        "commodities": getattr(state, "rohstoffe", {}),
        "products": getattr(state, "processed_products", {}),
        "currencies": getattr(state, "WAEHRUNGEN", {}),
    }
    for name, book in books.items():
        if not book:
            errors.append(f"missing {name}")
    if len(getattr(state, "kryptos", {})) != TARGET_CRYPTO_COUNT:
        errors.append("invalid crypto universe size")
    sectors = {str(asset.get("branche", "")) for asset in getattr(state, "aktien", {}).values()}
    expected_sectors = set(getattr(state, "BRANCHEN", []))
    if expected_sectors - sectors:
        errors.append("missing intended company sectors")
    ratings = {str(asset.get("rating", "")) for asset in getattr(state, "aktien", {}).values()}
    if len(ratings) < 2:
        errors.append("corporate ratings collapsed")
    for ticker, asset in _all_priced_assets(state):
        price = _number(asset.get("kurs", asset.get("price", 0.0)))
        if not math.isfinite(price) or price <= 0:
            errors.append(f"invalid price: {ticker}")
            break
    for country, macro in getattr(state, "makro", {}).items():
        for field in ("bip_abs", "bevoelkerung"):
            value = _number(macro.get(field, 0.0))
            if not math.isfinite(value) or value <= 0:
                errors.append(f"invalid {field}: {country}")
                break
    for code, product in getattr(state, "processed_products", {}).items():
        for field in ("supply", "demand", "inventories"):
            value = _number(product.get(field, 0.0))
            if not math.isfinite(value) or value < 0:
                errors.append(f"invalid product quantity: {code}.{field}")
                break
    if history_manifest:
        if str(history_manifest.get("history_id", "")) == "":
            errors.append("missing history identity")
        if int(history_manifest.get("history_schema_version", -1)) != HISTORY_SCHEMA_VERSION:
            errors.append("history schema mismatch")
        if str(history_manifest.get("economic_model_version", "")) != ECONOMIC_MODEL_VERSION:
            errors.append("economic model mismatch")
    if len(getattr(state, "bond_market", [])) == 0:
        errors.append("empty bond universe")
    if not getattr(state, "FOREX_PAARE_HISTORIE", {}):
        warnings.append("forex history not yet populated")
    return {"passed": not errors, "errors": errors, "warnings": warnings}


def write_compressed_checkpoint(path: Path, payload: dict[str, object]) -> dict[str, object]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    started = datetime.now(UTC)
    try:
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        os.close(fd)
        temporary = Path(name)
        with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as stream:
            json.dump(encode(payload), stream, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {
        "bytes": path.stat().st_size,
        "seconds": (datetime.now(UTC) - started).total_seconds(),
        "sha256": file_sha256(path),
    }


def read_compressed_checkpoint(path: Path) -> dict[str, object]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        payload = decode(json.load(stream, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))))
    if not isinstance(payload, dict):
        raise TypeError("World checkpoint must be a mapping")
    return payload


def build_bundle_metadata(config: WorldGenerationConfig, checkpoint_path: Path, store_path: Path, manifest: dict[str, object], gate: dict[str, object]) -> dict[str, object]:
    return {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "complete": True,
        "config": asdict(config),
        "trajectory_identity": config.trajectory_identity(),
        "history_manifest": manifest,
        "sanity_gate": gate,
        "files": {
            checkpoint_path.name: {"sha256": file_sha256(checkpoint_path), "bytes": checkpoint_path.stat().st_size},
            store_path.name: {"sha256": file_sha256(store_path), "bytes": store_path.stat().st_size},
        },
    }


def validate_bundle(path: Path) -> dict[str, object]:
    path = Path(path)
    metadata_path = path / "world.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("bundle_schema_version") != BUNDLE_SCHEMA_VERSION or metadata.get("complete") is not True:
        raise ValueError("Incomplete or unsupported world bundle")
    config = metadata.get("config", {})
    legacy = config.get("economic_model_version") == LEGACY_ECONOMIC_MODEL_VERSION
    if config.get("economic_model_version") not in {ECONOMIC_MODEL_VERSION, LEGACY_ECONOMIC_MODEL_VERSION}:
        raise ValueError("World bundle economic model version mismatch")
    if config.get("history_schema_version") not in ({1} if legacy else {2, HISTORY_SCHEMA_VERSION}):
        raise ValueError("World bundle history schema version mismatch")
    for name, expected in metadata.get("files", {}).items():
        candidate = path / name
        if not candidate.is_file() or file_sha256(candidate) != expected.get("sha256"):
            raise ValueError(f"World bundle file checksum mismatch: {name}")
    checkpoint = read_compressed_checkpoint(path / "checkpoint.json.gz")
    if checkpoint.get("save_version") not in SUPPORTED_VERSIONS:
        raise ValueError("World checkpoint version mismatch")
    checkpoint_config = checkpoint.get("checkpoint", {}).get("world_generation")
    if checkpoint_config != config:
        raise ValueError("World checkpoint/config mismatch")
    try:
        rng = checkpoint["rng"]
        random.Random().setstate(rng["python"])
        np.random.RandomState().set_state(rng["numpy"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("World checkpoint RNG state is invalid") from exc
    checkpoint_manifest = checkpoint.get("analytics_session", {}).get("manifest", {})
    if checkpoint_manifest != metadata.get("history_manifest"):
        raise ValueError("World checkpoint/history manifest mismatch")
    return metadata


def capture_world_payload(state: Any, analytics: dict[str, object], config: WorldGenerationConfig) -> dict[str, object]:
    payload = capture(state)
    payload["analytics_session"] = analytics
    payload["world_generation"] = asdict(config)
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _all_priced_assets(state: Any) -> Iterable[tuple[str, dict]]:
    for name in ("aktien", "rohstoffe", "kryptos", "fonds", "indizes", "derivatives"):
        yield from getattr(state, name, {}).items()


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _history_close(item: object) -> float:
    if isinstance(item, dict):
        return _number(item.get("close", item.get("value", 0.0)))
    if isinstance(item, (tuple, list)) and item:
        return _number(item[0])
    return _number(item)
