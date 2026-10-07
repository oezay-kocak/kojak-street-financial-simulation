"""Read-only projections for the visible application, never an economic mirror.

One subscription describes a main view and its selected detail/tab. Navigation
seeds that scope; live updates carry only its current fields and price tails.
The worker does not keep a detached world or compare hidden entities.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

from kojakstreet.adapters.legacy_state import (
    UI_HISTORY_LIMIT,
    _copy_macro_mapping,
    snapshot_from_legacy,
)
from kojakstreet.core.history import _as_date
from kojakstreet.core.player_accounting import visible_news
from kojakstreet.day_delta import public_copy

BOOKS = {
    "Stock": ("aktien", "stocks"),
    "Commodity": ("rohstoffe", "commodities"),
    "Crypto": ("kryptos", "cryptos"),
    "Fund": ("fonds", "funds"),
    "Index": ("indizes", "indices"),
    "Derivative": ("derivatives", "derivatives"),
    "Product": ("processed_products", "processed_products"),
}
VIEWS = frozenset(
    (
        "markets",
        "supply_chain",
        "forex",
        "bondmarket",
        "portfolio",
        "macro",
        "trade_map",
        "global_macro",
        "news",
    )
)
QUOTE_FIELDS = frozenset(
    [
        "name",
        "kurs",
        "aenderung",
        "market_cap",
        "aum",
        "land",
        "ziel",
        "branche",
        "kategorie",
        "typ",
        "fund_type",
        "rating",
    ]
)
CHART_FIELDS = QUOTE_FIELDS | frozenset(
    [
        "open_interest",
        "long_interest",
        "short_interest",
        "squeeze_pressure",
        "issuer_bank",
        "revenue_growth",
        "fcf_margin",
        "eps",
        "fund_flow_pressure",
        "demand_change",
        "production_change",
        "inventories_change",
        "extraction_cost_change",
        "transaction_change",
        "fee_change",
        "inflation_rate",
        "instrument_type",
        "underlying",
        "yield_rate",
        "spread",
        "contract_type",
        "contract_size",
        "pricing_note",
        "maturity_date",
        "expiration_date",
        "expiry_date",
        "settlement_type",
        "trade_mode",
        "leverage",
    ]
)
PRODUCT_FIELDS = QUOTE_FIELDS | frozenset(
    [
        "supply",
        "production",
        "demand",
        "inventories",
        "shortage",
        "price_pressure",
        "supply_change",
        "demand_change",
        "production_change",
        "inventories_change",
        "category",
        "unit",
    ]
)
SUPPLY_FIELDS = PRODUCT_FIELDS | frozenset(
    [
        "output_mix",
        "specialization",
        "production_capacity",
        "service_code",
        "market_share",
        "network_capacity",
        "underlyings",
    ]
)
CURRENT_TABLES = {
    "markets": (),
    "supply_chain": ("product_current",),
    "forex": ("forex_current",),
    "bondmarket": ("bond_current",),
    "portfolio": ("portfolio_current",),
    "macro": ("country_current",),
    "trade_map": ("country_trade_current",),
    "global_macro": (),
    "news": ("news_current",),
}


def normalize_scope(scope: dict | None) -> dict:
    scope = dict(scope or {})
    view = str(scope.get("view", "markets"))
    if view not in VIEWS:
        raise ValueError(f"Unknown visible view: {view}")
    return {"view": view, "selection": dict(scope.get("selection") or {})}


def _pick(source: dict, keys) -> dict:
    return {key: public_copy(source[key]) for key in keys if key in source}


def _current(source: dict) -> dict:
    """Current scalar fields only; nested fields require an explicit consumer."""
    return {
        key: value
        for key, value in source.items()
        if not str(key).startswith("_")
        and key not in {"birth_rate", "death_rate"}
        and (value is None or isinstance(value, (str, int, float, bool)))
    }


def _bounded(value, limit=UI_HISTORY_LIMIT):
    if isinstance(value, list):
        return public_copy(value[-limit:])
    if isinstance(value, dict):
        return {
            key: _bounded(item, limit)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    return public_copy(value)


def _history(asset, since: str | None):
    history = asset.get("historie", [])
    if since is None:
        return public_copy(history[-UI_HISTORY_LIMIT:])
    # Simulation price histories are dated and append/replace their endpoint.
    # Walk backwards only through this request's intervening visible days.
    tail = []
    for point in reversed(history):
        date = (
            point.get("date", "")
            if isinstance(point, dict)
            else (point[1] if isinstance(point, (list, tuple)) and len(point) > 1 else "")
        )
        if not date or _as_date(date) < _as_date(since):
            break
        tail.append(point)
    return public_copy(list(reversed(tail)))


def ticker_items(daten) -> list[dict]:
    """The tape says 7D: rank and display the same authoritative seven-day move."""
    items = []
    kinds = {"rohstoffe": "Commodity", "kryptos": "Crypto", "aktien": "Stock", "indizes": "Index"}
    for name, limit in (("rohstoffe", 2), ("kryptos", 2), ("aktien", 4), ("indizes", 1000)):
        rows = []
        for ticker, asset in getattr(daten, name, {}).items():
            price = float(asset.get("kurs", 0.0))
            history = asset.get("historie", [])
            change = float(asset.get("aenderung", 0.0))
            if len(history) >= 7:
                point = history[-7]
                previous = (
                    float(point.get("close", point.get("value", 0.0)))
                    if isinstance(point, dict)
                    else float(point[0] if isinstance(point, (list, tuple)) else point)
                )
                change = (price / previous - 1) * 100 if previous else 0.0
            rows.append({"ticker": str(ticker), "price": price, "change": change, "asset_type": kinds[name]})
        items.extend(sorted(rows, key=lambda row: row["change"], reverse=True)[:limit])
    # A ranked item leaving the top list can still be on screen. Send its
    # current quote until that cell scrolls away, never yesterday's value.
    ranked = {(item["asset_type"], item["ticker"]) for item in items}
    displayed = {tuple(identity) for identity in getattr(daten, "_tape_display_ids", ()) if isinstance(identity, (list, tuple)) and len(identity) == 2} - ranked
    for name in ("rohstoffe", "kryptos", "aktien", "indizes"):
        for ticker in {ticker for kind, ticker in displayed if kind == kinds[name]} & getattr(daten, name, {}).keys():
            asset = getattr(daten, name)[ticker]
            price = float(asset.get("kurs", 0.0))
            history = asset.get("historie", [])
            change = float(asset.get("aenderung", 0.0))
            if len(history) >= 7:
                point = history[-7]
                previous = float(point.get("close", point.get("value", 0.0))) if isinstance(point, dict) else float(point[0] if isinstance(point, (tuple, list)) else point)
                change = (price / previous - 1) * 100 if previous else 0.0
            items.append({"ticker": str(ticker), "price": price, "change": change, "ranked": False, "asset_type": kinds[name]})
    return items


def _allocations(daten, fund):
    result = []
    for holding in fund.get("underlyings", []):
        ticker, kind = str(holding.get("ticker", "")), str(holding.get("asset_type", ""))
        weight = float(holding.get("weight", 0.0))
        if kind == "Index":
            for symbol, share in (
                getattr(daten, "indizes", {}).get(ticker, {}).get("constituents", {}).items()
            ):
                result.append(
                    {
                        "ticker": symbol,
                        "name": getattr(daten, "aktien", {}).get(symbol, {}).get("name", symbol),
                        "asset_type": "Stock",
                        "weight": weight * float(share),
                    }
                )
        else:
            if kind == "Bond":
                asset = next(
                    (
                        row
                        for row in getattr(daten, "bond_market", [])
                        if row.get("symbol") == ticker
                    ),
                    {},
                )
            else:
                asset = getattr(daten, BOOKS.get(kind, ("", ""))[0], {}).get(ticker, {})
            result.append(
                {
                    "ticker": ticker,
                    "name": asset.get("name", asset.get("issuer", ticker)),
                    "asset_type": kind,
                    "weight": weight,
                }
            )
    return sorted(result, key=lambda row: row["weight"], reverse=True)


def project_visible_state(runtime, scope: dict, *, history_since: str | None = None):
    """Return a detached GameState with exactly one consumer's live dependencies."""
    scope = normalize_scope(scope)
    daten, view, selection = runtime.daten, scope["view"], scope["selection"]
    started = time.perf_counter()
    state = snapshot_from_legacy(daten, "status")
    tape = ticker_items(daten)
    timings = {"global_ms": (time.perf_counter() - started) * 1000}
    started = time.perf_counter()
    if view == "markets":
        for kind, (legacy, target) in BOOKS.items():
            if kind != "Product":
                setattr(
                    state,
                    target,
                    {
                        key: _pick(asset, QUOTE_FIELDS)
                        for key, asset in getattr(daten, legacy, {}).items()
                    },
                )
        state.macro = {region: {} for region in getattr(daten, "makro", {})}
    elif view == "macro" and selection.get("area") in {"population_society", "society_politics"}:
        region = str(selection.get("region", ""))
        state.macro = {region: _current(getattr(daten, "makro", {}).get(region, {}))}
    elif view in {"supply_chain", "trade_map", "macro"}:
        for legacy, target in (BOOKS["Commodity"], BOOKS["Product"]):
            setattr(
                state,
                target,
                {
                    key: _pick(asset, PRODUCT_FIELDS)
                    for key, asset in getattr(daten, legacy, {}).items()
                },
            )
        state.macro = {
            region: _current(asset) for region, asset in getattr(daten, "makro", {}).items()
        }
        if view == "trade_map":
            keys = {
                "exports",
                "imports",
                "trade_partner_details",
                "regional_supply",
                "regional_demand",
            }
            for region, macro in getattr(daten, "makro", {}).items():
                state.macro[region].update(_pick(macro, keys))
    elif view == "forex":
        state.currency_strength = dict(getattr(daten, "waehrungen_staerke", {}))
        state.fx_balances = dict(getattr(daten, "forex_depot", {}))
        state.commodities = {
            "XAU": _pick(getattr(daten, "rohstoffe", {}).get("XAU", {}), QUOTE_FIELDS)
        }
        state.forex_history = {
            key: public_copy(points[-2:])
            for key, points in getattr(daten, "FOREX_PAARE_HISTORIE", {}).items()
        }
    elif view == "bondmarket":
        state.bond_market = [_current(asset) for asset in getattr(daten, "bond_market", [])]
        state.macro = {
            region: _current(asset) for region, asset in getattr(daten, "makro", {}).items()
        }
    elif view == "portfolio":
        for field, legacy in (
            ("portfolio", "depot"),
            ("perpetuals", "perpetuals"),
            ("fx_balances", "forex_depot"),
            ("loans", "kredite"),
            ("bonds", "anleihen"),
            ("currency_strength", "waehrungen_staerke"),
        ):
            setattr(
                state, field, public_copy(getattr(daten, legacy, {} if field != "bonds" else []))
            )
        symbols = (
            set(state.portfolio)
            | {str(asset.get("ticker", "")) for asset in state.perpetuals.values()}
            | {"XAU"}
        )
        for kind, (legacy, target) in BOOKS.items():
            if kind != "Product":
                setattr(
                    state,
                    target,
                    {
                        key: _pick(asset, QUOTE_FIELDS)
                        for key, asset in getattr(daten, legacy, {}).items()
                        if key in symbols
                    },
                )
        state.portfolio_history = _bounded(getattr(daten, "DEPOT_VERMOEGEN_HISTORIE", []))
        state.realized_pnl_history = _bounded(getattr(daten, "realisierte_guv_historie", []))
        bond_symbols = {str(bond.get("symbol", "")) for bond in state.bonds}
        state.bond_market = [
            _current(bond)
            for bond in getattr(daten, "bond_market", [])
            if str(bond.get("symbol", "")) in bond_symbols
        ]
    elif view == "global_macro":
        state.global_macro = public_copy(getattr(daten, "global_macro", {}))
        state.global_macro_history = {
            key: _bounded(points, 31)
            for key, points in getattr(daten, "GLOBAL_MACRO_HISTORIE", {}).items()
        }
    elif view == "news":
        state.news = public_copy(visible_news(daten))
        state.macro = {
            region: _current(asset) for region, asset in getattr(daten, "makro", {}).items()
        }
        # Calendar reads the latest two published values for each indicator.
        state.macro_history = {
            key: public_copy(points[-2:])
            for key, points in getattr(daten, "MAKRO_HISTORIE", {}).items()
        }
    timings["view_ms"] = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    if view == "markets" and selection.get("ticker"):
        kind, ticker = str(selection.get("kind", "Stock")), str(selection["ticker"])
        if kind not in BOOKS:
            raise ValueError(f"Unknown selected asset type: {kind}")
        legacy, target = BOOKS[kind]
        asset = getattr(daten, legacy, {}).get(ticker, {})
        tab = selection.get("tab", "chart")
        if tab == "overview":
            selected = _current(asset)
            # Fund overview displays Holdings count, without sending allocations.
            if kind == "Fund":
                selected["visible_holding_count"] = len(_allocations(daten, asset))
        elif tab == "supply":
            selected = _pick(asset, SUPPLY_FIELDS)
            if kind == "Fund":
                selected.pop("underlyings", None)
                selected["visible_allocations"] = _allocations(daten, asset)
            elif kind in {"Stock", "Crypto"}:
                # The supply table needs related products, not other companies.
                for product_legacy, product_target in (BOOKS["Commodity"], BOOKS["Product"]):
                    setattr(
                        state,
                        product_target,
                        {
                            code: _pick(data, PRODUCT_FIELDS)
                            for code, data in getattr(daten, product_legacy, {}).items()
                        },
                    )
        else:
            selected = _pick(asset, CHART_FIELDS)
        selected.update(_pick(asset, CHART_FIELDS))
        for key in ("company_output_history", "company_input_history"):
            if key in selected:
                selected[key] = _bounded(selected[key])
        if tab == "chart":
            selected["historie"] = _history(asset, history_since)
            metric = selection.get("supply_metric")
            if metric and kind in {"Stock", "Crypto"}:
                role, code = metric
                if kind == "Stock":
                    field = (
                        "company_output_history" if role == "Produces" else "company_input_history"
                    )
                    points = asset.get(field, {}).get(code, {}).get("history", [])
                else:
                    market = getattr(daten, "processed_products", {}).get(code) or getattr(
                        daten, "rohstoffe", {}
                    ).get(code, {})
                    points = market.get(
                        "supply_history" if role == "Provides" else "demand_history", []
                    )
                selected["visible_metric_history"] = [
                    float(point[0] if isinstance(point, (list, tuple)) else point)
                    for point in points[-UI_HISTORY_LIMIT:]
                ]
        getattr(state, target)[ticker] = selected
        # Only selected trading controls need balances/positions/conversions.
        state.portfolio = {ticker: public_copy(getattr(daten, "depot", {}).get(ticker, {}))}
        state.fx_balances = dict(getattr(daten, "forex_depot", {}))
        state.currency_strength = dict(getattr(daten, "waehrungen_staerke", {}))
        state.commodities.setdefault(
            "XAU", _pick(getattr(daten, "rohstoffe", {}).get("XAU", {}), QUOTE_FIELDS)
        )
    elif view == "macro" and selection.get("region"):
        region = str(selection["region"])
        macro = getattr(daten, "makro", {}).get(region, {})
        if selection.get("area") in {"population_society", "society_politics"}:
            from kojakstreet.core.workforce import projection

            state.macro.setdefault(region, {})["population_society"] = projection(macro)
            if selection.get("area") == "society_politics":
                from kojakstreet.core.politics import projection as politics_projection
                state.macro[region]["society_politics"] = politics_projection(macro.get("politics"))
            timings["detail_ms"] = (time.perf_counter() - started) * 1000
            return state, tape, timings
        tab = int(selection.get("tab", 0))
        keys = {
            0: {"trade_balance_history", "import_dependency_history", "export_strength_history"},
            1: {"regional_supply", "regional_demand"},
            2: {"exports", "imports", "trade_partner_details"},
            3: {"economic_profile", "sector_summary"},
        }.get(tab, set())
        state.macro.setdefault(region, {}).update(
            {key: _bounded(macro[key]) for key in keys if key in macro}
        )
        if tab == 0:
            state.macro_history = {
                key: _bounded(points)
                for key, points in getattr(daten, "MAKRO_HISTORIE", {}).items()
                if key.startswith(region + "_")
            }
        if tab == 3:
            sector_inputs = SimpleNamespace(
                makro={region: {}},
                aktien={
                    ticker: asset
                    for ticker, asset in getattr(daten, "aktien", {}).items()
                    if str(asset.get("land", "")) == region
                },
            )
            state.macro[region]["sector_summary"] = (
                _copy_macro_mapping(sector_inputs, include_sector_summary=True)
                .get(region, {})
                .get("sector_summary", {})
            )
        if selection.get("code"):
            code = str(selection["code"])
            state.macro[region]["regional_history"] = {
                code: _bounded(macro.get("regional_history", {}).get(code, {}), 180)
            }
    elif view == "supply_chain" and selection.get("code"):
        code = str(selection["code"])
        for legacy, target in (BOOKS["Commodity"], BOOKS["Product"]):
            asset = getattr(daten, legacy, {}).get(code)
            if asset:
                getattr(state, target)[code].update(
                    {
                        key: _bounded(asset.get(key, []))
                        for key in ("supply_history", "demand_history")
                    }
                )
        state.stocks = {
            ticker: _pick(
                asset, {"land", "branche", "output_mix", "specialization", "production_capacity"}
            )
            for ticker, asset in getattr(daten, "aktien", {}).items()
            if code in (asset.get("output_mix") or {asset.get("specialization", ""): 1})
        }
        for region, macro in getattr(daten, "makro", {}).items():
            state.macro[region].update(_pick(macro, {"economic_profile", "regional_supply"}))
    elif view == "bondmarket" and selection.get("ticker"):
        for asset in state.bond_market:
            if asset.get("symbol") == selection["ticker"]:
                source = next(
                    (
                        item
                        for item in getattr(daten, "bond_market", [])
                        if item.get("symbol") == selection["ticker"]
                    ),
                    {},
                )
                asset["historie"] = _bounded(source.get("historie", []))
    elif view == "forex" and selection.get("pair"):
        pair = str(selection["pair"])
        state.forex_history[pair] = _bounded(
            getattr(daten, "FOREX_PAARE_HISTORIE", {}).get(pair, [])
        )
    elif view == "portfolio" and selection.get("ticker"):
        kind, ticker = str(selection.get("kind", "Stock")), str(selection["ticker"])
        if kind in BOOKS:
            legacy, target = BOOKS[kind]
            asset = getattr(daten, legacy, {}).get(ticker, {})
            selected = _pick(asset, CHART_FIELDS)
            selected["historie"] = _bounded(asset.get("historie", []))
            getattr(state, target)[ticker] = selected
    elif view == "global_macro" and selection.get("metric"):
        metric = str(selection["metric"])
        state.global_macro_history[metric] = _bounded(
            getattr(daten, "GLOBAL_MACRO_HISTORIE", {}).get(metric, [])
        )
    elif view == "news" and selection.get("history_key"):
        key = str(selection["history_key"])
        state.macro_history[key] = _bounded(getattr(daten, "MAKRO_HISTORIE", {}).get(key, []))
    timings["detail_ms"] = (time.perf_counter() - started) * 1000
    return state, tape, timings
