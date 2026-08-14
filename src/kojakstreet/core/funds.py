"""Demand-driven fund and ETF universe."""

from __future__ import annotations

import random
import re
from collections import defaultdict
from datetime import datetime
from types import ModuleType
from typing import Any

from kojakstreet.core.bonds import ensure_dynamic_bond_market
from kojakstreet.core.companies import BRANCHEN
from kojakstreet.core.countries import COUNTRIES, RESERVE_CURRENCY
from kojakstreet.core.indices import COMPOSITE_TICKERS, SECTOR_INDEX_LABELS, SECTOR_PREFIXES
from kojakstreet.core.ohlc import append_ohlc_from_move
from kojakstreet.core.production_chains import COMMODITY_GROUPS
from kojakstreet.core.ratings import normalize_rating

START_FUND_PRICE = 100.0
MINIMUM_AUM = 18_000_000.0
TARGET_COUNTRY_SECTOR_FUNDS_PER_COUNTRY = 4
TARGET_COUNTRY_SECTOR_ETFS_PER_COUNTRY = 3
INVESTMENT_GRADE = {"AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"}

WORLD_FUND_STYLES = ["Equity", "Growth", "Dividend", "Value", "Small Cap"]
BOND_FUND_STYLES = [
    "Government Bond",
    "Corporate Bond",
    "Investment Grade",
    "High Yield",
    "Short Duration",
    "Long Duration",
]
CRYPTO_GROUP_LABELS = {
    "STORE": "Digital Store of Value",
    "PAY": "Payment Rails",
    "DATA": "Decentralized Storage",
    "GRID": "Energy Trading Grid",
}
COMMODITY_GROUP_LABELS = {
    "EnergietrÃ¤ger": "Energy Commodities",
    "Energieträger": "Energy Commodities",
    "Industriemetalle und Mineralische Rohstoffe": "Industrial Metals & Minerals",
    "Edel- und Spezialmetalle": "Precious & Specialty Metals",
    "Seltene Erden": "Rare Earths",
    "Landwirtschaftliche PrimÃ¤rgÃ¼ter": "Agricultural Primary Goods",
    "Landwirtschaftliche Primärgüter": "Agricultural Primary Goods",
    "Tierische GÃ¼ter": "Animal Products",
    "Tierische Güter": "Animal Products",
}


def ensure_fund_universe(daten: ModuleType, *, reset: bool = False) -> None:
    if not hasattr(daten, "fonds"):
        daten.fonds = {}
    if reset or any("fund_type" not in fund for fund in getattr(daten, "fonds", {}).values()):
        daten.fonds = {}
        daten.fund_universe_complete = False
    if getattr(daten, "fund_universe_complete", False) and getattr(daten, "fonds", {}):
        return
    if reset or not getattr(daten, "bond_market", []):
        try:
            ensure_dynamic_bond_market(daten)
        except Exception:
            if not hasattr(daten, "bond_market"):
                daten.bond_market = []

    existing_keys = {str(fund.get("mandate_key", "")) for fund in daten.fonds.values()}
    for mandate in _target_mandates(daten):
        if mandate["mandate_key"] in existing_keys:
            continue
        _add_fund(daten, mandate)
    daten.fund_universe_complete = True


def update_funds(daten: ModuleType, zeit_str: str) -> None:
    ensure_fund_universe(daten)
    month_index = _month_index(getattr(daten, "datum", datetime(1990, 1, 1)))
    current_ordinal = getattr(daten, "datum", datetime(1990, 1, 1)).toordinal()
    lookup = _underlying_lookup(daten)
    asset_cache = _cached_fund_asset_cache(daten, lookup)
    dead_tickers = []
    flow_pressures: dict[tuple[str, str], float] = defaultdict(float)
    for ticker, fund in list(daten.fonds.items()):
        if _needs_rebalance(fund, month_index):
            _rebalance_fund(daten, fund, month_index)
            _update_asset_cache_for_fund(asset_cache, lookup, fund)
        _reinvest_cash_reserve(fund)
        old_price = float(fund.get("kurs", START_FUND_PRICE))
        old_aum = float(fund.get("aum", fund.get("market_cap", MINIMUM_AUM)))
        daily_return = _fund_daily_return(fund, asset_cache, current_ordinal=current_ordinal)
        if fund.get("fund_type") not in {"ETF", "Short ETF", "Leveraged ETF", "Short Leveraged ETF"}:
            daily_return += random.uniform(-0.0008, 0.0010) * _active_skill(fund)
        daily_return = max(-0.08, min(0.08, daily_return))
        fund["kurs"] = max(1.0, old_price * (1.0 + daily_return))
        fund["aenderung"] = ((float(fund["kurs"]) - old_price) / old_price * 100.0) if old_price > 0 else 0.0

        flow = _aum_flow(daten, fund, daily_return)
        fund["aum"] = max(0.0, old_aum * (1.0 + daily_return) + flow)
        fund["aum_change"] = ((float(fund["aum"]) - old_aum) / old_aum * 100.0) if old_aum > 0 else 0.0
        fund["market_cap"] = fund["aum"]
        _collect_fund_purchase_pressure(fund, max(0.0, flow), lookup, flow_pressures)
        fund["fund_age_months"] = _fund_age_months(daten, fund)
        _refresh_allocations_if_needed(fund)
        _refresh_performance_metrics(fund)
        _refresh_distribution_yield_if_needed(fund, asset_cache, month_index)
        _credit_issuer_fees(daten, fund)
        append_ohlc_from_move(fund, old_price, fund["kurs"], zeit_str, volatility=abs(daily_return))
        fund.setdefault("aum_history", []).append((fund["aum"], zeit_str, ""))
        if len(fund["historie"]) > 1040:
            del fund["historie"][:-1040]
        if len(fund["aum_history"]) > 1040:
            del fund["aum_history"][:-1040]
        if _fund_should_close(fund):
            dead_tickers.append(ticker)

    _apply_collected_purchase_pressures(flow_pressures, lookup, asset_cache)

    for ticker in dead_tickers:
        del daten.fonds[ticker]

    if dead_tickers:
        _invalidate_fund_runtime_cache(daten)
        daten.fund_universe_complete = False
        ensure_fund_universe(daten)


def _target_mandates(daten: ModuleType) -> list[dict[str, Any]]:
    mandates: list[dict[str, Any]] = []
    sector_cycle = list(BRANCHEN)
    for country in COUNTRIES:
        country_name = country.name
        mandates.append(
            {
                "mandate_key": f"COUNTRY:{country_name}",
                "fund_type": "Country Fund",
                "strategy": "Country Equity",
                "country": country_name,
                "name_suffix": f"{country_name} Equity Fund",
                "allocation_template": "Equity",
                "rebalance": True,
                "target_aum": _country_target_aum(daten, country_name, 0.018),
            }
        )
        mandates.append(
            {
                "mandate_key": f"ETF:COUNTRY:{country_name}",
                "fund_type": "ETF",
                "strategy": "Country Index ETF",
                "country": country_name,
                "tracked_index": COMPOSITE_TICKERS[country_name],
                "name_suffix": f"{country_name} Composite ETF",
                "allocation_template": "Equity",
                "rebalance": False,
                "target_aum": _country_target_aum(daten, country_name, 0.012),
            }
        )
        start = list(COUNTRIES).index(country) % len(sector_cycle)
        country_sectors = [sector_cycle[(start + offset) % len(sector_cycle)] for offset in range(TARGET_COUNTRY_SECTOR_FUNDS_PER_COUNTRY)]
        for branch in country_sectors:
            sector_label = _sector_label(branch)
            mandates.append(
                {
                    "mandate_key": f"SECTOR:{country_name}:{branch}",
                    "fund_type": "Sector Fund",
                    "strategy": "Country Sector",
                    "country": country_name,
                    "branch": branch,
                    "name_suffix": f"{country_name} {sector_label} Fund",
                    "allocation_template": "Equity",
                    "rebalance": True,
                    "target_aum": _country_target_aum(daten, country_name, 0.006),
                }
            )
        for branch in country_sectors[:TARGET_COUNTRY_SECTOR_ETFS_PER_COUNTRY]:
            sector_label = _sector_label(branch)
            mandates.append(
                {
                    "mandate_key": f"ETF:SECTOR:{country_name}:{branch}",
                    "fund_type": "ETF",
                    "strategy": "Sector Index ETF",
                    "country": country_name,
                    "branch": branch,
                    "tracked_index": f"{SECTOR_PREFIXES[country_name]}-{SECTOR_INDEX_LABELS[branch][1]}",
                    "name_suffix": f"{country_name} {sector_label} ETF",
                    "allocation_template": "Equity",
                    "rebalance": False,
                    "target_aum": _country_target_aum(daten, country_name, 0.004),
                }
            )

    for branch in BRANCHEN:
        sector_label = _sector_label(branch)
        mandates.append(
            {
                "mandate_key": f"GLOBAL_SECTOR:{branch}",
                "fund_type": "Global Sector Fund",
                "strategy": "Global Sector",
                "branch": branch,
                "name_suffix": f"{sector_label} Global Fund",
                "allocation_template": "Equity",
                "rebalance": True,
                "target_aum": _global_equity_cap(daten) * 0.004,
            }
        )

    for style in WORLD_FUND_STYLES:
        mandates.append(
            {
                "mandate_key": f"WORLD:{style}",
                "fund_type": "World Fund",
                "strategy": f"Global {style}",
                "style": style,
                "name_suffix": f"Global {style} Fund",
                "allocation_template": "Equity",
                "rebalance": True,
                "target_aum": _global_equity_cap(daten) * 0.011,
            }
        )

    for style in BOND_FUND_STYLES:
        mandates.append(
            {
                "mandate_key": f"BOND:{style}",
                "fund_type": "Bond Fund",
                "strategy": style,
                "style": style,
                "name_suffix": f"{style} Fund",
                "allocation_template": "Bond",
                "rebalance": True,
                "target_aum": max(200_000_000.0, _global_equity_cap(daten) * 0.006),
            }
        )

    for group in COMMODITY_GROUPS:
        label = COMMODITY_GROUP_LABELS.get(group, group)
        mandates.append(
            {
                "mandate_key": f"COMMODITY:{group}",
                "fund_type": "Commodity Fund",
                "strategy": "Commodity Basket",
                "group": group,
                "name_suffix": f"{label} Fund",
                "allocation_template": "Commodity",
                "rebalance": True,
                "target_aum": _commodity_group_cap(daten, group) * 0.018,
            }
        )

    for task, label in CRYPTO_GROUP_LABELS.items():
        mandates.append(
            {
                "mandate_key": f"CRYPTO:{task}",
                "fund_type": "Crypto Fund",
                "strategy": label,
                "task_type": task,
                "name_suffix": f"{label} Fund",
                "allocation_template": "Crypto",
                "rebalance": True,
                "target_aum": _crypto_group_cap(daten, task) * 0.030,
            }
        )
    mandates.extend(_leveraged_and_short_mandates(mandates))
    return mandates


def _leveraged_and_short_mandates(base_mandates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index_mandates = [mandate for mandate in base_mandates if mandate.get("fund_type") == "ETF" and mandate.get("tracked_index")]
    target_count = max(1, len(base_mandates) // 4)
    variants = (
        ("SHORT", "Short ETF", -1.0, "Short"),
        ("LEV2", "Leveraged ETF", 2.0, "2x"),
        ("SLEV2", "Short Leveraged ETF", -2.0, "-2x"),
    )
    mandates: list[dict[str, Any]] = []
    for index, mandate in enumerate(index_mandates):
        if len(mandates) >= target_count:
            break
        key, fund_type, leverage, label = variants[index % len(variants)]
        clone = dict(mandate)
        clone.update(
            {
                "mandate_key": f"{key}:{mandate['mandate_key']}",
                "fund_type": fund_type,
                "strategy": f"{label} {mandate['strategy']}",
                "name_suffix": f"{label} {mandate['name_suffix']}",
                "leverage": leverage,
                "target_aum": float(mandate.get("target_aum", MINIMUM_AUM)) * 0.22,
                "rebalance": False,
            }
        )
        mandates.append(clone)
    return mandates


def _add_fund(daten: ModuleType, mandate: dict[str, Any]) -> None:
    issuer_ticker, issuer = _select_issuer_bank(daten, mandate)
    ticker = _unique_fund_ticker(daten, mandate, issuer_ticker)
    name = f"{issuer.get('name', issuer_ticker)} {mandate['name_suffix']}".strip()
    start_aum = max(MINIMUM_AUM * 1.5, float(mandate.get("target_aum", 90_000_000.0)) * random.uniform(0.35, 0.95))
    fund = {
        "name": name,
        "kurs": START_FUND_PRICE,
        "historie": [(START_FUND_PRICE, "01.01.1990", "")],
        "aenderung": 0.0,
        "market_cap": start_aum,
        "aum": start_aum,
        "aum_change": 0.0,
        "aum_history": [(start_aum, "01.01.1990", "")],
        "typ": "Funds and ETFs",
        "fund_type": mandate["fund_type"],
        "strategy": mandate["strategy"],
        "leverage": float(mandate.get("leverage", 1.0)),
        "mandate_key": mandate["mandate_key"],
        "issuer": issuer_ticker,
        "issuer_bank": issuer.get("name", issuer_ticker),
        "ziel": mandate.get("country", RESERVE_CURRENCY),
        "land": mandate.get("country", RESERVE_CURRENCY),
        "branche": mandate.get("branch", mandate.get("style", mandate.get("group", mandate.get("task_type", "Global")))),
        "tracked_index": mandate.get("tracked_index"),
        "target_aum": max(MINIMUM_AUM, float(mandate.get("target_aum", 90_000_000.0))),
        "inception_date": getattr(daten, "datum", datetime(1990, 1, 1)),
        "fund_age_months": 0,
        "last_rebalance_month": -99,
        "rebalance_quarterly": bool(mandate.get("rebalance", True)),
        "expense_ratio": _expense_ratio(mandate["fund_type"]),
        "distribution_yield": 0.0,
        "performance_1m": 0.0,
        "performance_6m": 0.0,
        "performance_1y": 0.0,
        "performance_all": 0.0,
        "cash_allocation": 0.0,
        "equity_allocation": 0.0,
        "bond_allocation": 0.0,
        "commodity_allocation": 0.0,
        "crypto_allocation": 0.0,
        "underlyings": [],
    }
    daten.fonds[ticker] = fund
    _rebalance_fund(daten, fund, _month_index(getattr(daten, "datum", datetime(1990, 1, 1))))
    _refresh_allocations(daten, fund)
    lookup = _underlying_lookup(daten)
    _refresh_distribution_yield(fund, _fund_asset_cache(daten, lookup))


def _rebalance_fund(daten: ModuleType, fund: dict[str, Any], month_index: int) -> None:
    previous = {
        (str(holding.get("asset_type", "")), str(holding.get("ticker", ""))): float(holding.get("weight", 0.0))
        for holding in fund.get("underlyings", [])
    }
    fund["underlyings"] = _build_underlyings(daten, fund)
    _compile_underlyings(fund)
    _invalidate_fund_runtime_cache(daten)
    fund["last_rebalance_month"] = month_index
    fund["_allocations_dirty"] = True
    fund["_distribution_yield_dirty"] = True
    if fund.get("fund_type") in {"ETF", "Short ETF", "Leveraged ETF", "Short Leveraged ETF"} or not previous:
        fund["cash_allocation"] = 0.0
        return
    next_weights = {
        (str(holding.get("asset_type", "")), str(holding.get("ticker", ""))): float(holding.get("weight", 0.0))
        for holding in fund.get("underlyings", [])
    }
    turnover = sum(abs(next_weights.get(key, 0.0) - previous.get(key, 0.0)) for key in set(previous) | set(next_weights)) / 2.0
    fund["cash_allocation"] = min(0.16, max(float(fund.get("cash_allocation", 0.0)), turnover * random.uniform(0.10, 0.28)))


def _reinvest_cash_reserve(fund: dict[str, Any]) -> None:
    if fund.get("fund_type") in {"ETF", "Short ETF", "Leveraged ETF", "Short Leveraged ETF"}:
        fund["cash_allocation"] = 0.0
        return
    cash = float(fund.get("cash_allocation", 0.0))
    if cash <= 0.0001:
        fund["cash_allocation"] = 0.0
        return
    fund["cash_allocation"] = max(0.0, cash - random.uniform(0.0010, 0.0040))


def _build_underlyings(daten: ModuleType, fund: dict[str, Any]) -> list[dict[str, Any]]:
    fund_type = str(fund.get("fund_type", ""))
    if fund_type in {"ETF", "Short ETF", "Leveraged ETF", "Short Leveraged ETF"}:
        tracked = str(fund.get("tracked_index", ""))
        return [{"ticker": tracked, "asset_type": "Index", "weight": 1.0}] if tracked in getattr(daten, "indizes", {}) else []
    if fund_type in {"Country Fund", "Sector Fund", "Global Sector Fund", "World Fund"}:
        return _equity_underlyings(daten, fund)
    if fund_type == "Bond Fund":
        return _bond_underlyings(daten, fund)
    if fund_type == "Commodity Fund":
        return _market_cap_underlyings(
            "Commodity",
            {
                ticker: asset
                for ticker, asset in getattr(daten, "rohstoffe", {}).items()
                if str(asset.get("kategorie", "")) == str(fund.get("branche", ""))
            },
        )
    if fund_type == "Crypto Fund":
        return _market_cap_underlyings(
            "Crypto",
            {
                ticker: asset
                for ticker, asset in getattr(daten, "kryptos", {}).items()
                if str(asset.get("task_type", "")) == str(fund.get("branche", ""))
            },
        )
    return []


def _equity_underlyings(daten: ModuleType, fund: dict[str, Any]) -> list[dict[str, Any]]:
    country = str(fund.get("ziel", ""))
    branch = str(fund.get("branche", ""))
    strategy = str(fund.get("strategy", ""))
    stocks = []
    for ticker, asset in getattr(daten, "aktien", {}).items():
        if fund.get("fund_type") in {"Country Fund", "Sector Fund"} and asset.get("land") != country:
            continue
        if fund.get("fund_type") in {"Sector Fund", "Global Sector Fund"} and asset.get("branche") != branch:
            continue
        stocks.append((ticker, asset))
    if "Small Cap" in strategy:
        scored = [(ticker, asset, 1.0 / max(1.0, float(asset.get("market_cap", 1.0)))) for ticker, asset in stocks]
    elif "Growth" in strategy:
        scored = [(ticker, asset, max(0.05, float(asset.get("revenue_growth", 0.0)) + 0.12)) for ticker, asset in stocks]
    elif "Dividend" in strategy:
        scored = [(ticker, asset, max(0.03, float(asset.get("dividend_yield", 0.0)) + 0.02)) for ticker, asset in stocks]
    elif "Value" in strategy:
        scored = [(ticker, asset, max(1.0, float(asset.get("market_cap", 0.0))) * _rating_quality(asset)) for ticker, asset in stocks]
    else:
        scored = [(ticker, asset, max(1.0, float(asset.get("market_cap", 0.0)))) for ticker, asset in stocks]
    scored.sort(key=lambda item: item[2], reverse=True)
    selected = scored[: min(35, max(8, len(scored)))]
    total = sum(score for _ticker, _asset, score in selected)
    return [
        {"ticker": ticker, "asset_type": "Stock", "weight": score / total if total else 0.0}
        for ticker, _asset, score in selected
        if total
    ]


def _bond_underlyings(daten: ModuleType, fund: dict[str, Any]) -> list[dict[str, Any]]:
    style = str(fund.get("strategy", ""))
    bonds = []
    for bond in getattr(daten, "bond_market", []):
        issuer_type = str(bond.get("issuer_type", ""))
        rating = normalize_rating(str(bond.get("rating", "BBB")))
        duration = float(bond.get("duration", bond.get("maturity_years", 0.0)))
        ytm = float(bond.get("yield_to_maturity", 0.0))
        if style == "Government Bond" and issuer_type != "Government":
            continue
        if style == "Corporate Bond" and issuer_type != "Corporate":
            continue
        if style == "Investment Grade" and rating not in INVESTMENT_GRADE:
            continue
        if style == "High Yield" and ytm < 0.055:
            continue
        if style == "Short Duration" and duration >= 5.0:
            continue
        if style == "Long Duration" and duration <= 15.0:
            continue
        bonds.append((str(bond.get("symbol", "")), bond, max(0.01, ytm) * float(bond.get("price", 100.0))))
    bonds.sort(key=lambda item: item[2], reverse=True)
    selected = bonds[:80]
    total = sum(score for _symbol, _bond, score in selected)
    return [
        {"ticker": symbol, "asset_type": "Bond", "weight": score / total if total else 0.0}
        for symbol, _bond, score in selected
        if total and symbol
    ]


def _market_cap_underlyings(asset_type: str, assets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    total = sum(max(0.0, float(asset.get("market_cap", 0.0))) for asset in assets.values())
    if total <= 0:
        return []
    return [
        {"ticker": ticker, "asset_type": asset_type, "weight": float(asset.get("market_cap", 0.0)) / total}
        for ticker, asset in assets.items()
    ]


def _fund_daily_return(
    fund: dict[str, Any],
    asset_cache: dict[tuple[str, str], dict[str, Any]],
    *,
    current_ordinal: int | None = None,
) -> float:
    weighted = 0.0
    for asset_type, ticker, weight in _compiled_underlyings(fund):
        asset = asset_cache.get((asset_type, ticker))
        if not asset:
            continue
        if asset_type == "Bond":
            change = _bond_price_return_for_day(asset, current_ordinal)
            carry = float(asset.get("yield_to_maturity", 0.0)) / 264.0
            weighted += weight * (change + carry)
        else:
            weighted += weight * (float(asset.get("aenderung", 0.0)) / 100.0)
    cash = float(fund.get("cash_allocation", 0.0))
    if fund.get("fund_type") in {"Short ETF", "Leveraged ETF", "Short Leveraged ETF"}:
        leverage = float(fund.get("leverage", 1.0))
        weighted *= leverage
    return weighted * (1.0 - cash)


def _bond_price_return_for_day(asset: dict[str, Any], current_ordinal: int | None) -> float:
    if current_ordinal is not None:
        try:
            last_update = int(asset.get("last_price_update_ordinal", -1))
        except (TypeError, ValueError):
            last_update = -1
        if last_update != current_ordinal:
            return 0.0
    return float(asset.get("aenderung", 0.0)) / 100.0


def _underlying_lookup(daten: ModuleType) -> dict[str, dict[str, dict[str, Any]]]:
    bond_lookup = getattr(daten, "bond_market_by_symbol", None)
    if not isinstance(bond_lookup, dict):
        bond_lookup = {
            str(bond.get("symbol", "")): bond
            for bond in getattr(daten, "bond_market", [])
            if str(bond.get("symbol", ""))
        }
        daten.bond_market_by_symbol = bond_lookup
    return {
        "Stock": getattr(daten, "aktien", {}),
        "Commodity": getattr(daten, "rohstoffe", {}),
        "Crypto": getattr(daten, "kryptos", {}),
        "Index": getattr(daten, "indizes", {}),
        "Bond": bond_lookup,
    }


def _fund_asset_cache(
    daten: ModuleType,
    lookup: dict[str, dict[str, dict[str, Any]]],
) -> dict[tuple[str, str], dict[str, Any]]:
    keys = {
        (asset_type, ticker)
        for fund in getattr(daten, "fonds", {}).values()
        for asset_type, ticker, _weight in _compiled_underlyings(fund)
    }
    return {
        (asset_type, ticker): asset
        for asset_type, ticker in keys
        if (asset := lookup.get(asset_type, {}).get(ticker))
    }


def _cached_fund_asset_cache(
    daten: ModuleType,
    lookup: dict[str, dict[str, dict[str, Any]]],
) -> dict[tuple[str, str], dict[str, Any]]:
    cache = getattr(daten, "_fund_runtime_asset_cache", None)
    if isinstance(cache, dict) and not getattr(daten, "_fund_runtime_cache_dirty", False):
        return cache["assets"]
    signature = tuple(
        (ticker, tuple(_compiled_underlyings(fund)))
        for ticker, fund in getattr(daten, "fonds", {}).items()
    )
    if isinstance(cache, dict) and cache.get("signature") == signature:
        daten._fund_runtime_cache_dirty = False
        return cache["assets"]
    assets = _fund_asset_cache(daten, lookup)
    daten._fund_runtime_asset_cache = {"signature": signature, "assets": assets}
    daten._fund_runtime_cache_dirty = False
    return assets


def _invalidate_fund_runtime_cache(daten: ModuleType) -> None:
    daten._fund_runtime_cache_dirty = True


def _update_asset_cache_for_fund(
    asset_cache: dict[tuple[str, str], dict[str, Any]],
    lookup: dict[str, dict[str, dict[str, Any]]],
    fund: dict[str, Any],
) -> None:
    for asset_type, ticker, _weight in _compiled_underlyings(fund):
        if asset := lookup.get(asset_type, {}).get(ticker):
            asset_cache[(asset_type, ticker)] = asset


def _underlying_asset(lookup: dict[str, dict[str, dict[str, Any]]], asset_type: str, ticker: str) -> dict[str, Any] | None:
    return lookup.get(asset_type, {}).get(ticker)


def _legacy_underlying_asset(daten: ModuleType, asset_type: str, ticker: str) -> dict[str, Any] | None:
    if asset_type == "Stock":
        return getattr(daten, "aktien", {}).get(ticker)
    if asset_type == "Commodity":
        return getattr(daten, "rohstoffe", {}).get(ticker)
    if asset_type == "Crypto":
        return getattr(daten, "kryptos", {}).get(ticker)
    if asset_type == "Index":
        return getattr(daten, "indizes", {}).get(ticker)
    if asset_type == "Bond":
        for bond in getattr(daten, "bond_market", []):
            if str(bond.get("symbol", "")) == ticker:
                return bond
    return None


def _aum_flow(daten: ModuleType, fund: dict[str, Any], daily_return: float) -> float:
    aum = float(fund.get("aum", 0.0))
    target = max(MINIMUM_AUM, float(fund.get("target_aum", MINIMUM_AUM)))
    issuer = getattr(daten, "aktien", {}).get(str(fund.get("issuer", "")), {})
    issuer_strength = 1.0 + min(0.35, max(-0.25, float(issuer.get("aenderung", 0.0)) / 100.0))
    performance_pull = max(-0.012, min(0.016, daily_return * 0.45))
    opportunity_pull = max(-0.010, min(0.018, (target - aum) / target * 0.006))
    base_creation = target * 0.00022 if aum < target else 0.0
    return (aum * (performance_pull + opportunity_pull) * issuer_strength) + base_creation


def _fund_should_close(fund: dict[str, Any]) -> bool:
    return (
        float(fund.get("aum", 0.0)) < MINIMUM_AUM
        and int(fund.get("fund_age_months", 0)) >= 18
        and float(fund.get("performance_1y", 0.0)) < -18.0
    )


def _credit_issuer_fees(daten: ModuleType, fund: dict[str, Any]) -> None:
    return


def _collect_fund_purchase_pressure(
    fund: dict[str, Any],
    positive_flow: float,
    lookup: dict[str, dict[str, dict[str, Any]]],
    flow_pressures: dict[tuple[str, str], float],
) -> None:
    if positive_flow <= 0:
        return
    for asset_type, ticker, weight in _compiled_underlyings(fund):
        if asset_type == "Index":
            index = lookup["Index"].get(ticker, {})
            constituents = index.get("constituents", {})
            for stock_ticker, index_weight in constituents.items():
                stock = lookup["Stock"].get(str(stock_ticker), {})
                flow_pressures[("Stock", str(stock_ticker))] += _flow_price_pressure(
                    positive_flow * weight * float(index_weight),
                    stock,
                )
            continue
        asset = lookup.get(asset_type, {}).get(ticker, {})
        flow_pressures[(asset_type, ticker)] += _flow_price_pressure(positive_flow * weight, asset)


def _apply_collected_purchase_pressures(
    flow_pressures: dict[tuple[str, str], float],
    lookup: dict[str, dict[str, dict[str, Any]]],
    asset_cache: dict[tuple[str, str], dict[str, Any]],
) -> None:
    for key, pressure in flow_pressures.items():
        asset_type, ticker = key
        asset = lookup["Stock"].get(ticker) if asset_type == "Stock" else asset_cache.get(key)
        _nudge_underlying(asset, pressure)


def _nudge_underlying(asset: dict[str, Any] | None, pressure: float) -> None:
    if not asset:
        return
    asset["fund_flow_pressure"] = float(asset.get("fund_flow_pressure", 0.0)) + pressure
    asset["news_momentum"] = min(0.035, float(asset.get("news_momentum", 0.0)) + pressure)


def _flow_price_pressure(flow_amount: float, asset: dict[str, Any]) -> float:
    if flow_amount <= 0 or not asset:
        return 0.0
    market_cap = max(1.0, float(asset.get("market_cap", float(asset.get("price", 100.0)) * 1_000_000.0)))
    liquidity_depth = max(1.0, market_cap * 0.035)
    return min(0.006, (flow_amount / liquidity_depth) * 0.35)


def _refresh_allocations(daten: ModuleType, fund: dict[str, Any]) -> None:
    totals = _compiled_allocation_totals(fund)
    cash = 0.0 if fund.get("fund_type") == "ETF" else max(0.0, min(0.30, float(fund.get("cash_allocation", 0.0))))
    invested_share = max(0.0, 1.0 - cash)
    invested_total = sum(totals.values()) or 1.0
    fund["cash_allocation"] = cash
    fund["equity_allocation"] = totals["equity"] / invested_total * invested_share
    fund["bond_allocation"] = totals["bond"] / invested_total * invested_share
    fund["commodity_allocation"] = totals["commodity"] / invested_total * invested_share
    fund["crypto_allocation"] = totals["crypto"] / invested_total * invested_share


def _refresh_allocations_if_needed(fund: dict[str, Any]) -> None:
    cash = 0.0 if fund.get("fund_type") == "ETF" else max(0.0, min(0.30, float(fund.get("cash_allocation", 0.0))))
    previous_cash = float(fund.get("_allocation_cash", -1.0))
    if fund.get("_allocations_dirty") is not True and abs(previous_cash - cash) < 0.00001:
        fund["cash_allocation"] = cash
        return
    totals = _compiled_allocation_totals(fund)
    invested_share = max(0.0, 1.0 - cash)
    invested_total = sum(totals.values()) or 1.0
    fund["cash_allocation"] = cash
    fund["equity_allocation"] = totals["equity"] / invested_total * invested_share
    fund["bond_allocation"] = totals["bond"] / invested_total * invested_share
    fund["commodity_allocation"] = totals["commodity"] / invested_total * invested_share
    fund["crypto_allocation"] = totals["crypto"] / invested_total * invested_share
    fund["_allocation_cash"] = cash
    fund["_allocations_dirty"] = False


def _refresh_performance_metrics(fund: dict[str, Any]) -> None:
    history = fund.get("historie", [])
    fund["performance_1m"] = _period_return_from_history(history, 22)
    fund["performance_6m"] = _period_return_from_history(history, 132)
    fund["performance_1y"] = _period_return_from_history(history, 264)
    fund["performance_all"] = _period_return_from_history(history, len(history) - 1)


def _refresh_distribution_yield(fund: dict[str, Any], asset_cache: dict[tuple[str, str], dict[str, Any]]) -> None:
    payout = 0.0
    for asset_type, ticker, weight in _compiled_income_underlyings(fund):
        asset = asset_cache.get((asset_type, ticker))
        if not asset:
            continue
        if asset_type == "Stock":
            payout += weight * float(asset.get("dividend_yield", 0.0))
        elif asset_type == "Bond":
            payout += weight * float(asset.get("coupon", asset.get("yield_to_maturity", 0.0)))
    fund["distribution_yield"] = max(0.0, payout * (1.0 - float(fund.get("cash_allocation", 0.0))))


def _refresh_distribution_yield_if_needed(
    fund: dict[str, Any],
    asset_cache: dict[tuple[str, str], dict[str, Any]],
    month_index: int,
) -> None:
    if (
        fund.get("_distribution_yield_dirty") is not True
        and int(fund.get("_distribution_yield_month", -1)) == month_index
    ):
        cash = float(fund.get("cash_allocation", 0.0))
        gross = float(fund.get("_gross_distribution_yield", fund.get("distribution_yield", 0.0)))
        fund["distribution_yield"] = max(0.0, gross * (1.0 - cash))
        return
    payout = 0.0
    for asset_type, ticker, weight in _compiled_income_underlyings(fund):
        asset = asset_cache.get((asset_type, ticker))
        if not asset:
            continue
        if asset_type == "Stock":
            payout += weight * float(asset.get("dividend_yield", 0.0))
        elif asset_type == "Bond":
            payout += weight * float(asset.get("coupon", asset.get("yield_to_maturity", 0.0)))
    fund["_gross_distribution_yield"] = max(0.0, payout)
    fund["_distribution_yield_month"] = month_index
    fund["_distribution_yield_dirty"] = False
    fund["distribution_yield"] = max(0.0, payout * (1.0 - float(fund.get("cash_allocation", 0.0))))


def _compiled_underlyings(fund: dict[str, Any]) -> list[tuple[str, str, float]]:
    compiled = fund.get("_compiled_underlyings")
    if isinstance(compiled, list):
        return compiled
    return _compile_underlyings(fund)


def _compiled_allocation_totals(fund: dict[str, Any]) -> dict[str, float]:
    totals = fund.get("_compiled_allocation_totals")
    if isinstance(totals, dict):
        return totals
    _compile_underlyings(fund)
    return fund.get("_compiled_allocation_totals", {"equity": 0.0, "bond": 0.0, "commodity": 0.0, "crypto": 0.0})


def _compiled_income_underlyings(fund: dict[str, Any]) -> list[tuple[str, str, float]]:
    income = fund.get("_compiled_income_underlyings")
    if isinstance(income, list):
        return income
    _compile_underlyings(fund)
    return fund.get("_compiled_income_underlyings", [])


def _compile_underlyings(fund: dict[str, Any]) -> list[tuple[str, str, float]]:
    compiled = [
        (
            str(holding.get("asset_type", "")),
            str(holding.get("ticker", "")),
            float(holding.get("weight", 0.0)),
        )
        for holding in fund.get("underlyings", [])
    ]
    fund["_compiled_underlyings"] = compiled
    totals = {"equity": 0.0, "bond": 0.0, "commodity": 0.0, "crypto": 0.0}
    income_underlyings = []
    for asset_type, ticker, weight in compiled:
        if asset_type in {"Stock", "Index"}:
            totals["equity"] += weight
        elif asset_type == "Bond":
            totals["bond"] += weight
            income_underlyings.append((asset_type, ticker, weight))
        elif asset_type == "Commodity":
            totals["commodity"] += weight
        elif asset_type == "Crypto":
            totals["crypto"] += weight
        if asset_type == "Stock":
            income_underlyings.append((asset_type, ticker, weight))
    fund["_compiled_allocation_totals"] = totals
    fund["_compiled_income_underlyings"] = income_underlyings
    return compiled


def _period_return(history: list[float], points: int) -> float:
    if len(history) < 2:
        return 0.0
    if points <= 0 or len(history) <= points:
        base = history[0]
    else:
        base = history[-points - 1]
    return ((history[-1] / base) - 1.0) * 100.0 if base else 0.0


def _period_return_from_history(history: list[Any], points: int) -> float:
    if len(history) < 2:
        return 0.0
    latest = _history_value(history[-1])
    if points <= 0 or len(history) <= points:
        base = _history_value(history[0])
    else:
        base = _history_value(history[-points - 1])
    return ((latest / base) - 1.0) * 100.0 if base else 0.0


def _history_value(entry: Any) -> float:
    try:
        return float(entry[0] if isinstance(entry, (tuple, list)) else entry)
    except (TypeError, ValueError):
        return 0.0


def _fund_age_months(daten: ModuleType, fund: dict[str, Any]) -> int:
    inception = fund.get("inception_date", getattr(daten, "datum", datetime(1990, 1, 1)))
    if not isinstance(inception, datetime):
        inception = getattr(daten, "datum", datetime(1990, 1, 1))
    today = getattr(daten, "datum", inception)
    return max(0, (today.year - inception.year) * 12 + today.month - inception.month)


def _needs_rebalance(fund: dict[str, Any], month_index: int) -> bool:
    if not fund.get("rebalance_quarterly", True):
        return False
    return month_index - int(fund.get("last_rebalance_month", -99)) >= 3


def _select_issuer_bank(daten: ModuleType, mandate: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    banks = [
        (ticker, asset)
        for ticker, asset in getattr(daten, "aktien", {}).items()
        if str(asset.get("branche", "")) == "Finanzen"
    ] or list(getattr(daten, "aktien", {}).items())
    if not banks:
        return "BANK", {"name": "Trust Meridian"}
    country = mandate.get("country")
    local = [(ticker, asset) for ticker, asset in banks if asset.get("land") == country]
    pool = local or banks
    return random.choice(pool)


def _unique_fund_ticker(daten: ModuleType, mandate: dict[str, Any], issuer_ticker: str) -> str:
    base = re.sub(r"[^A-Z]", "", f"F{issuer_ticker}{mandate['mandate_key']}")[:5] or "FND"
    if mandate["fund_type"] in {"ETF", "Short ETF", "Leveraged ETF", "Short Leveraged ETF"}:
        base = re.sub(r"[^A-Z]", "", f"E{issuer_ticker}{mandate['mandate_key']}")[:5] or "ETF"
    existing = set(getattr(daten, "aktien", {})) | set(getattr(daten, "rohstoffe", {})) | set(getattr(daten, "kryptos", {})) | set(getattr(daten, "indizes", {})) | set(getattr(daten, "fonds", {}))
    candidate = base
    counter = 1
    while candidate in existing:
        suffix = str(counter)
        candidate = f"{base[: max(1, 5 - len(suffix))]}{suffix}"
        counter += 1
    return candidate


def _country_target_aum(daten: ModuleType, country: str, share: float) -> float:
    total = sum(float(asset.get("market_cap", 0.0)) for asset in getattr(daten, "aktien", {}).values() if asset.get("land") == country)
    return max(MINIMUM_AUM * 2.0, total * share)


def _global_equity_cap(daten: ModuleType) -> float:
    return max(1.0, sum(float(asset.get("market_cap", 0.0)) for asset in getattr(daten, "aktien", {}).values()))


def _commodity_group_cap(daten: ModuleType, group: str) -> float:
    return max(1.0, sum(float(asset.get("market_cap", 0.0)) for asset in getattr(daten, "rohstoffe", {}).values() if asset.get("kategorie") == group))


def _crypto_group_cap(daten: ModuleType, task: str) -> float:
    return max(1.0, sum(float(asset.get("market_cap", 0.0)) for asset in getattr(daten, "kryptos", {}).values() if asset.get("task_type") == task))


def _rating_quality(asset: dict[str, Any]) -> float:
    rating = normalize_rating(str(asset.get("rating", "BBB")))
    ladder = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D"]
    try:
        return max(0.15, 1.0 - (ladder.index(rating) / len(ladder)))
    except ValueError:
        return 0.45


def _active_skill(fund: dict[str, Any]) -> float:
    if fund.get("fund_type") in {"ETF", "Short ETF", "Leveraged ETF", "Short Leveraged ETF"}:
        return 0.0
    return 1.0 + min(0.8, max(0.0, float(fund.get("aum", 0.0)) / max(1.0, float(fund.get("target_aum", 1.0))) - 0.4))


def _expense_ratio(fund_type: str) -> float:
    return 0.0


def _sector_label(branch: str) -> str:
    return SECTOR_INDEX_LABELS.get(branch, (branch, ""))[0]


def _month_index(date_value: datetime) -> int:
    return date_value.year * 12 + date_value.month
