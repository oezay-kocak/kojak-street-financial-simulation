"""Explicit savegame migrations for legacy and JSON payloads."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any

from kojakstreet.core.checkpoints import VERSION as CURRENT_SAVE_VERSION
from kojakstreet.core.financial_products import (
    CDS_CONTRACT_SCALE,
    CDS_CONTRACT_TYPES,
    derivative_pricing_note,
)
from kojakstreet.core.global_macro import ensure_global_macro
from kojakstreet.core.label_codes import attach_stable_label_codes
from kojakstreet.core.market_regime import update_market_regime


def migrate_save_payload(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    version = int(migrated.get("save_version", 1) or 1)
    if version > CURRENT_SAVE_VERSION:
        raise ValueError("Save was written by a newer version")
    while version < CURRENT_SAVE_VERSION:
        if version == 1:
            _migrate_v1_to_v2(migrated)
            version = 2
        elif version == 2:
            _migrate_v2_to_v3(migrated)
            version = 3
        else:
            version = CURRENT_SAVE_VERSION
        migrated["save_version"] = version
    _migrate_v2_to_v3(migrated)
    migrated["save_version"] = CURRENT_SAVE_VERSION
    return migrated


def finalize_loaded_state(state: Any) -> None:
    attach_stable_label_codes(state)
    ensure_global_macro(state)
    update_market_regime(state)
    for fund in getattr(state, "fonds", {}).values():
        if isinstance(fund, dict):
            fund["expense_ratio"] = 0.0
    if not hasattr(state, "bond_market_archive"):
        state.bond_market_archive = []
    for derivative in getattr(state, "derivatives", {}).values():
        if isinstance(derivative, dict):
            derivative["pricing_note"] = derivative_pricing_note(derivative)


def _migrate_v1_to_v2(payload: MutableMapping[str, Any]) -> None:
    payload.setdefault("perpetuals", {})
    payload.setdefault("processed_products", {})
    payload.setdefault("fonds", {})
    payload.setdefault("derivatives", {})
    payload.setdefault("indizes", {})
    payload.setdefault("realisierte_guv_historie", [])
    payload.setdefault("saved_at", datetime.now(UTC))


def _migrate_v2_to_v3(payload: MutableMapping[str, Any]) -> None:
    for book_name in ("aktien", "rohstoffe", "kryptos", "fonds", "indizes", "derivatives"):
        book = payload.get(book_name, {})
        if not isinstance(book, dict):
            continue
        for ticker, asset in book.items():
            if isinstance(asset, dict):
                asset.setdefault("ticker", str(ticker))
                if book_name == "fonds":
                    asset["expense_ratio"] = 0.0
    derivatives = payload.get("derivatives", {})
    if isinstance(derivatives, dict):
        for derivative in derivatives.values():
            if not isinstance(derivative, dict):
                continue
            if derivative.get("instrument_type") in CDS_CONTRACT_TYPES:
                derivative["contract_scale"] = CDS_CONTRACT_SCALE
                derivative["contract_size"] = float(derivative.get("notional", 0.0)) / CDS_CONTRACT_SCALE
            derivative["pricing_note"] = derivative_pricing_note(derivative)
