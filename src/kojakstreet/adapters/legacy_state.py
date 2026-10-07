"""Read-only adapter for the current legacy `daten.py` module."""

from __future__ import annotations

from collections.abc import Mapping
from copy import copy

from kojakstreet.core.checkpoints import REFERENCE_CACHE_KEYS
from kojakstreet.core.countries import RESERVE_CURRENCY
from kojakstreet.core.state import GameState
from kojakstreet.core.player_accounting import visible_news

UI_HISTORY_LIMIT = 520


def snapshot_from_legacy(daten_module, profile: str = "full") -> GameState:
    """Create a detached state snapshot from the legacy global data module."""

    include = _profile_includes(profile)
    include_asset_histories = "asset_histories" in include
    include_bond_histories = "bond_histories" in include
    return GameState(
        date=daten_module.datum,
        cash=_total_cash_in_gd(daten_module),
        display_currency=getattr(daten_module, "anzeige_waehrung", RESERVE_CURRENCY),
        stocks=_copy_asset_universe(getattr(daten_module, "aktien", {}), include_history=include_asset_histories) if "stocks" in include else {},
        commodities=_copy_asset_universe(getattr(daten_module, "rohstoffe", {}), include_history=include_asset_histories) if "commodities" in include else {},
        processed_products=_copy_asset_universe(getattr(daten_module, "processed_products", {}), include_history=include_asset_histories) if "processed_products" in include else {},
        cryptos=_copy_asset_universe(getattr(daten_module, "kryptos", {}), include_history=include_asset_histories) if "cryptos" in include else {},
        funds=_copy_asset_universe(getattr(daten_module, "fonds", {}), include_history=include_asset_histories) if "funds" in include else {},
        indices=_copy_index_universe(daten_module, include_history=include_asset_histories) if "indices" in include else {},
        derivatives=_copy_asset_universe(getattr(daten_module, "derivatives", {}), include_history=include_asset_histories) if "derivatives" in include else {},
        portfolio=_copy_dict_mapping(getattr(daten_module, "depot", {})) if "portfolio" in include else {},
        perpetuals=_copy_dict_mapping(getattr(daten_module, "perpetuals", {})) if "perpetuals" in include else {},
        fx_balances=dict(getattr(daten_module, "forex_depot", {})) if "fx" in include else {},
        loans=dict(getattr(daten_module, "kredite", {})) if "loans" in include else {},
        bonds=[dict(bond) for bond in getattr(daten_module, "anleihen", [])] if "bonds" in include else [],
        bond_market=_copy_bond_market(getattr(daten_module, "bond_market", []), include_history=include_bond_histories) if "bond_market" in include else [],
        news=visible_news(daten_module) if "news" in include else [],
        macro=_copy_macro_mapping(daten_module, include_sector_summary="stocks" not in include) if "macro" in include else {},
        macro_history=_copy_history_mapping(getattr(daten_module, "MAKRO_HISTORIE", {})) if "macro_history" in include else {},
        global_macro=dict(getattr(daten_module, "global_macro", {})) if "global_macro" in include else {},
        global_macro_history=_copy_history_mapping(getattr(daten_module, "GLOBAL_MACRO_HISTORIE", {})) if "global_macro_history" in include else {},
        forex_history=_copy_history_mapping(
            getattr(daten_module, "FOREX_PAARE_HISTORIE", {}),
            limit=UI_HISTORY_LIMIT if "forex_histories" in include else 2,
        ) if "forex_history" in include else {},
        currency_strength=dict(getattr(daten_module, "waehrungen_staerke", {})) if "currency_strength" in include else {},
        portfolio_history=_copy_limited_history(getattr(daten_module, "DEPOT_VERMOEGEN_HISTORIE", [])) if "portfolio_history" in include else [],
        realized_pnl_history=_copy_limited_history(getattr(daten_module, "realisierte_guv_historie", [])) if "realized_pnl" in include else [],
    )


def _profile_includes(profile: str) -> set[str]:
    all_sections = {
        "stocks", "commodities", "processed_products", "cryptos", "funds", "indices", "derivatives",
        "portfolio", "perpetuals", "fx", "loans", "bonds", "bond_market", "news",
        "macro", "macro_history", "global_macro", "global_macro_history", "forex_history",
        "currency_strength", "portfolio_history", "realized_pnl", "asset_histories", "bond_histories", "forex_histories",
    }
    if profile == "markets":
        return {"stocks", "commodities", "processed_products", "cryptos", "funds", "indices", "derivatives", "macro", "portfolio", "perpetuals", "fx", "currency_strength", "asset_histories"}
    if profile == "status":
        return set()
    if profile == "mutation":
        return {"portfolio", "perpetuals", "fx", "loans", "bonds", "currency_strength"}
    if profile == "supply_chain":
        return {"stocks", "commodities", "processed_products", "macro"}
    if profile == "trade_map":
        return {"commodities", "processed_products", "macro"}
    if profile == "forex":
        return {"commodities", "forex_history", "currency_strength", "fx", "macro"}
    if profile == "bondmarket":
        return {"bond_market", "macro", "portfolio"}
    if profile == "portfolio":
        return {
            "stocks", "commodities", "cryptos", "funds", "indices", "derivatives",
            "portfolio", "perpetuals", "fx", "loans", "bonds", "portfolio_history",
            "realized_pnl", "asset_histories", "currency_strength", "bond_market",
        }
    if profile == "macro":
        return {"commodities", "processed_products", "macro", "news"}
    if profile == "global_macro":
        return {"global_macro", "global_macro_history"}
    if profile == "news":
        return {"news", "macro", "macro_history"}
    return all_sections


def _copy_asset_universe(assets: Mapping, *, include_history: bool) -> dict:
    copied = {}
    for ticker, data in assets.items():
        # Never expand the simulation's live reference graph into an IPC/UI
        # snapshot. These caches can duplicate entire underlying universes.
        asset = {key: value for key, value in data.items() if key not in REFERENCE_CACHE_KEYS}
        if include_history:
            asset["historie"] = _copy_limited_history(data.get("historie", []))
        else:
            _strip_heavy_histories(asset)
        copied[ticker] = asset
    return copied


def _copy_bond_market(bonds: list, *, include_history: bool) -> list[dict]:
    copied = []
    for bond in bonds:
        item = dict(bond)
        if include_history:
            item["historie"] = _copy_limited_history(bond.get("historie", []))
        else:
            _strip_heavy_histories(item)
        copied.append(item)
    return copied


def _copy_index_universe(daten_module, *, include_history: bool) -> dict:
    indices = _copy_asset_universe(getattr(daten_module, "indizes", {}), include_history=include_history)
    stocks = getattr(daten_module, "aktien", {})
    for index in indices.values():
        if _safe_float(index.get("market_cap", 0.0)) > 0:
            continue
        region = str(index.get("land", ""))
        sector = str(index.get("branche", "All Sectors"))
        if not region:
            continue
        market_cap = 0.0
        for asset in stocks.values():
            if str(asset.get("land", "")) != region:
                continue
            if sector != "All Sectors" and str(asset.get("branche", "")) != sector:
                continue
            market_cap += _safe_float(asset.get("market_cap", 0.0))
        if market_cap > 0:
            index["market_cap"] = market_cap
    return indices


def _strip_heavy_histories(values: dict) -> None:
    for key in list(values):
        if key in {"company_output_history", "company_input_history"}:
            values[key] = {}
        elif key == "historie" or key.endswith(("_history", "_historie")):
            values[key] = []


def _copy_dict_mapping(values: Mapping) -> dict:
    return {
        key: dict(value) if isinstance(value, Mapping) else copy(value)
        for key, value in values.items()
    }


def _copy_macro_mapping(daten_module, *, include_sector_summary: bool) -> dict:
    macro = _copy_dict_mapping(getattr(daten_module, "makro", {}))
    # Feature roots belong to checkpoints and selected-country projections.
    # Even explicit broad UI snapshots must not distribute every country's
    # workforce structure and annual demographic roots.
    for country in macro.values():
        for key in ("workforce", "birth_rate", "death_rate", "politics"):
            country.pop(key, None)
    if not include_sector_summary:
        return macro
    summaries: dict[str, dict[str, dict[str, float]]] = {}
    for asset in getattr(daten_module, "aktien", {}).values():
        region = str(asset.get("land", ""))
        sector = str(asset.get("branche", ""))
        if not region or not sector:
            continue
        bucket = summaries.setdefault(region, {}).setdefault(
            sector,
            {"capacity": 0.0, "utilization_sum": 0.0, "utilization_count": 0.0, "trend": 0.0},
        )
        bucket["capacity"] += _safe_float(asset.get("production_capacity", 0.0))
        bucket["utilization_sum"] += _safe_float(asset.get("capacity_utilization", 0.0))
        bucket["utilization_count"] += 1.0
        bucket["trend"] += _safe_float(asset.get("capacity_growth", 0.0))
    for region, sectors in summaries.items():
        target = macro.setdefault(region, {})
        target["sector_summary"] = {
            sector: {
                "capacity": values["capacity"],
                "utilization": values["utilization_sum"] / values["utilization_count"] if values["utilization_count"] else 0.0,
                "trend": values["trend"],
            }
            for sector, values in sectors.items()
        }
    return macro


def _copy_history_mapping(values: Mapping, *, limit: int = UI_HISTORY_LIMIT) -> dict:
    return {key: _copy_limited_history(history, limit=limit) for key, history in values.items()}


def _copy_limited_history(history, *, limit: int = UI_HISTORY_LIMIT) -> list:
    return list(history[-limit:])


def _total_cash_in_gd(daten_module) -> float:
    balances = dict(getattr(daten_module, "forex_depot", {}))
    total = float(balances.get(RESERVE_CURRENCY, 0.0))
    gd_strength = _gd_strength(daten_module)
    if gd_strength <= 0:
        return total
    total += float(getattr(daten_module, "bargeld", 0.0))
    for region, amount in balances.items():
        if region == RESERVE_CURRENCY:
            continue
        total += float(amount) * (_currency_strength(daten_module, region) / gd_strength)
    return total


def _gd_strength(daten_module) -> float:
    try:
        return float(daten_module.rohstoffe["XAU"]["kurs"]) / 100.0
    except (AttributeError, KeyError, TypeError, ValueError):
        return 1.0


def _currency_strength(daten_module, region: str) -> float:
    try:
        return float(daten_module.waehrungen_staerke.get(region, 1.0))
    except (AttributeError, TypeError, ValueError):
        return 1.0


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
