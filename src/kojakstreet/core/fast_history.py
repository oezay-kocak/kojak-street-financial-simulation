"""Deterministic coarse prehistory followed by a production daily burn-in."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from kojakstreet.core.bonds import ensure_dynamic_bond_market
from kojakstreet.core.fundamentals import ensure_stock_fundamentals
from kojakstreet.core.history import ECONOMIC_MODEL_VERSION, SemanticType
from kojakstreet.core.macro_calculations import update_sovereign_ratings
from kojakstreet.core.market_calculations import ALL_SECTORS, _stock_index_members
from kojakstreet.core.ratings import DEFAULT_RATING, rating_spread
from kojakstreet.core.workforce import advance_population, integrate_coarse
from kojakstreet.core.politics import advance_coarse as advance_politics, macro_snapshot

MONTHLY_HISTORY_YEARS = 19
DAILY_BURN_IN_DAYS = 365
FAST_HISTORY_VERSION = 3


@dataclass(frozen=True, slots=True)
class FastHistoryPlan:
    start: date
    target: date
    yearly_end: date
    monthly_end: date
    burn_in_start: date
    daily_days: int


def build_plan(start: date, years: int, *, burn_in_days: int = DAILY_BURN_IN_DAYS) -> FastHistoryPlan:
    target = date(start.year + years, start.month, start.day)
    daily_days = min(max(1, int(burn_in_days)), (target - start).days)
    burn_start = target - timedelta(days=daily_days)
    monthly_start_year = max(start.year, burn_start.year - MONTHLY_HISTORY_YEARS)
    return FastHistoryPlan(
        start=start,
        target=target,
        yearly_end=date(monthly_start_year - 1, 12, 31),
        monthly_end=burn_start - timedelta(days=1),
        burn_in_start=burn_start,
        daily_days=daily_days,
    )


def generate_coarse_history(
    runtime: Any,
    seed: int,
    years: int,
    *,
    burn_in_days: int = DAILY_BURN_IN_DAYS,
    progress: Callable[[str, int, int, date], None] | None = None,
) -> FastHistoryPlan:
    """Advance live state in correlated yearly/monthly steps and seed Deep History."""
    state = runtime.daten
    plan = build_plan(state.datum.date(), years, burn_in_days=burn_in_days)
    buckets: list[tuple[Any, ...]] = []

    yearly_dates = [date(year, 12, 31) for year in range(plan.start.year, plan.yearly_end.year + 1)]
    monthly_dates: list[date] = []
    cursor = date(plan.yearly_end.year + 1, 1, 1)
    while cursor <= plan.monthly_end:
        next_month = date(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        bucket_end = min(next_month - timedelta(days=1), plan.monthly_end)
        monthly_dates.append(bucket_end)
        cursor = next_month

    total = len(yearly_dates) + len(monthly_dates)
    completed = 0
    previous = plan.start
    for resolution, dates in (("yearly", yearly_dates), ("monthly", monthly_dates)):
        for bucket_end in dates:
            elapsed_years = max(1.0 / 365.0, (bucket_end - previous).days / 365.2425)
            before_politics = {c: macro_snapshot(m) for c, m in state.makro.items()}
            _advance_correlated_state(state, seed, bucket_end, elapsed_years)
            advance_politics(state, previous, bucket_end, before_politics)
            bucket_start = date(bucket_end.year, 1, 1) if resolution == "yearly" else date(bucket_end.year, bucket_end.month, 1)
            _capture_bucket(state, resolution, bucket_start, bucket_end, buckets)
            previous = bucket_end
            completed += 1
            if progress:
                progress(resolution, completed, total, bucket_end)

    state.datum = datetime.combine(plan.burn_in_start, datetime.min.time())
    _rebaseline_handoff_state(state)
    _install_recent_lookbacks(state, plan.burn_in_start)
    state.last_completed_simulation_date = state.datum - timedelta(days=1)
    state.LETZTER_REPORT_MONAT = -1
    state.LETZTER_ZINS_TAG = None
    # Initial Genesis bonds are dated around the original start year. Rebuild
    # the active issue set at the handoff date so the production engine does
    # not attempt to back-issue and price a century of already matured paper.
    state.bond_market = []
    state.bond_market_archive = []
    state.last_bond_issue_year = state.datum.year
    for cache_name in ("bond_market_by_symbol", "bond_market_symbol_signature"):
        if hasattr(state, cache_name):
            delattr(state, cache_name)
    ensure_dynamic_bond_market(state)
    runtime.data_store.seed_history_aggregates(
        buckets,
        last_yearly=plan.yearly_end,
        last_monthly=plan.monthly_end,
    )
    # The coarse phase mutates the live domain directly.  Publish that final
    # state now instead of leaving the Genesis current rows in place until the
    # first production monthly report.
    runtime.data_store.record_day(state, current_scope="full")
    runtime.state.sync_from_legacy()
    runtime.market.warm_runtime_indexes()
    return plan


def _advance_correlated_state(state: Any, seed: int, when: date, dt: float) -> None:
    before_population = {c: m["bevoelkerung"] for c, m in state.makro.items()}
    before_companies = {t: (a["revenue"], a["production_capacity"], a.get("cash_reserves", 0.0))
                        for t, a in state.aktien.items()}
    previous_prices = _composite_underlying_prices(state)
    previous_stock_caps = {
        str(ticker): max(0.0, float(asset.get("market_cap", 0.0)))
        for ticker, asset in state.aktien.items()
    }
    global_cycle = _normal(seed, when, "global", 0.0, 0.012) * math.sqrt(dt)
    country_growth: dict[str, float] = {}
    for region, macro in state.makro.items():
        base = 0.012 + _uniform(seed, when, f"country:{region}:trend", -0.004, 0.018)
        growth = _clamp(base * dt + global_cycle + _normal(seed, when, f"country:{region}", 0.0, 0.008) * math.sqrt(dt), -0.12, 0.16)
        macro["bip_abs"] = max(100.0, float(macro.get("bip_abs", 5000.0)) * (1.0 + growth))
        inflation = _clamp(float(macro.get("inflation", 0.02)) * 0.82 + (0.018 + global_cycle * 0.25) * 0.18, -0.01, 0.12)
        rate = _clamp(float(macro.get("zins", 0.035)) * 0.80 + (inflation + 0.012) * 0.20, 0.0, 0.18)
        macro["inflation"] = inflation
        macro["zins"] = rate
        annual_growth = _clamp(growth / max(dt, 1.0 / 12.0), -0.08, 0.12)
        macro["bip_prozent"] = annual_growth
        unemployment_target = _clamp(0.052 + (0.015 - annual_growth) * 0.45, 0.02, 0.22)
        adjustment = 1.0 - math.exp(-0.18 * max(1.0, dt * 12.0))
        unemployment = _clamp(
            float(macro.get("arbeitslosigkeit", 0.06))
            + (unemployment_target - float(macro.get("arbeitslosigkeit", 0.06))) * adjustment
            + _normal(seed, when, f"unemployment:{region}", 0.0, 0.0015) * math.sqrt(dt),
            0.02,
            0.22,
        )
        macro["arbeitslosigkeit"] = unemployment
        advance_population(macro, dt, floor=100_000.0, when=when)
        macro["expected_growth"] = annual_growth
        macro["expected_inflation"] = inflation
        macro["expected_rate"] = rate
        macro["expected_unemployment"] = unemployment
        macro["macro_surprise"] = 0.0
        macro["macro_surprise_momentum"] = 0.0
        debt_ratio = _clamp(float(macro.get("debt_to_gdp", 0.62)) + _normal(seed, when, f"debt:{region}", 0.0, 0.012) * math.sqrt(dt), 0.15, 1.65)
        macro["debt_to_gdp"] = debt_ratio
        macro["government_debt"] = float(macro["bip_abs"]) * debt_ratio
        macro["interest_burden"] = debt_ratio * rate
        deficit_ratio = _clamp(
            0.018
            + max(0.0, unemployment - 0.052) * 0.42
            + max(0.0, -annual_growth) * 0.24
            + macro["interest_burden"] * 0.18,
            -0.045,
            0.14,
        )
        credit_target = _clamp(
            0.024 + annual_growth * 0.42 - max(0.0, rate - 0.035) * 0.85 - max(0.0, inflation - 0.04) * 0.30,
            -0.10,
            0.12,
        )
        credit_growth = float(macro.get("credit_growth", 0.018)) + (
            credit_target - float(macro.get("credit_growth", 0.018))
        ) * adjustment
        macro["fiscal_deficit"] = float(macro["bip_abs"]) * deficit_ratio
        macro["fiscal_impulse"] = _clamp(deficit_ratio - 0.025, -0.04, 0.08)
        macro["credit_growth"] = credit_growth
        macro["private_credit"] = max(
            float(macro["bip_abs"]) * 0.18,
            float(macro.get("private_credit", float(macro["bip_abs"]) * 0.92)) * (1.0 + credit_growth * dt),
        )
        macro["balance_sheet"] = max(1.0, float(macro.get("balance_sheet", 1000.0)) * (1.0 + max(-0.05, growth + inflation * dt)))
        country_growth[region] = growth

    sectors = sorted({str(asset.get("branche", "Other")) for asset in state.aktien.values()})
    sector_growth = {
        sector: global_cycle + _normal(seed, when, f"sector:{sector}", 0.008 * dt, 0.018 * math.sqrt(dt))
        for sector in sectors
    }
    for ticker, asset in state.aktien.items():
        region = str(asset.get("land", ""))
        sector = str(asset.get("branche", "Other"))
        fundamental = country_growth.get(region, global_cycle) + sector_growth.get(sector, 0.0)
        company = _normal(seed, when, f"company:{ticker}", 0.0, 0.025 * math.sqrt(dt))
        revenue_factor = max(0.72, 1.0 + fundamental * 0.65 + company * 0.35)
        price_factor = max(0.55, 1.0 + fundamental + company)
        asset["revenue"] = max(1.0, float(asset.get("revenue", 1.0)) * revenue_factor)
        # Workforce changes the margin's level, not its random-walk baseline.
        # Feeding the adjusted level back here would add the full health term
        # again at every coarse bucket and double-count persistent mismatch.
        margin = _clamp(float(asset.get("_workforce_coarse_base_margin",
                                        asset.get("free_cash_flow_margin", 0.08))) + company * 0.08, -0.08, 0.30)
        asset["free_cash_flow_margin"] = margin
        asset["fcf_margin"] = margin
        asset["free_cash_flow"] = float(asset["revenue"]) * margin
        asset["kurs"] = max(0.05, float(asset.get("kurs", 100.0)) * price_factor)
        shares = max(1.0, float(asset.get("aktien_anzahl", 10_000_000.0)))
        raw_market_cap = float(asset["kurs"]) * shares
        revenue = float(asset["revenue"])
        asset["market_cap"] = _clamp(raw_market_cap, revenue * 0.45, revenue * 16.0)
        asset["kurs"] = float(asset["market_cap"]) / shares
        asset["cash_reserves"] = _clamp(
            float(asset.get("cash_reserves", 0.0)) * revenue_factor + max(0.0, float(asset["free_cash_flow"])) * dt * 0.25,
            0.0,
            revenue * 2.5,
        )
        asset["debt"] = _clamp(
            float(asset.get("debt", 0.0)) * (1.0 + max(-0.08, fundamental * 0.25)),
            0.0,
            float(asset["market_cap"]) * 1.5,
        )
        asset["debt_to_market_cap"] = float(asset["debt"]) / max(1.0, float(asset["market_cap"]))
        asset["production_capacity"] = max(1.0, float(asset.get("production_capacity", 1.0)) * revenue_factor)

    integrate_coarse(state, before_population, before_companies, when=when, years=dt)

    for code, asset in state.rohstoffe.items():
        shock = global_cycle * 0.7 + _normal(seed, when, f"commodity:{code}", 0.006 * dt, 0.04 * math.sqrt(dt))
        asset["kurs"] = max(0.05, float(asset.get("kurs", 100.0)) * max(0.55, 1.0 + shock))
        asset["market_cap"] = max(1.0, float(asset.get("market_cap", 1.0)) * max(0.65, 1.0 + shock * 0.6))
    for code, asset in state.kryptos.items():
        shock = global_cycle + _normal(seed, when, f"crypto:{code}", 0.01 * dt, 0.10 * math.sqrt(dt))
        asset["kurs"] = max(0.000001, float(asset.get("kurs", 1.0)) * max(0.30, 1.0 + shock))
        supply = max(1.0, float(asset.get("circulating_supply", asset.get("umlauf", 1_000_000.0))))
        asset["market_cap"] = float(asset["kurs"]) * supply

    average_growth = sum(country_growth.values()) / max(1, len(country_growth))
    for code, product in state.processed_products.items():
        factor = max(0.75, 1.0 + average_growth * 0.6 + _normal(seed, when, f"product:{code}", 0.0, 0.015 * math.sqrt(dt)))
        product["supply"] = max(0.0, float(product.get("supply", 1.0)) * factor)
        product["demand"] = max(0.0, float(product.get("demand", 1.0)) * max(0.75, 1.0 + average_growth * 0.7))
        product["inventories"] = max(0.0, float(product.get("inventories", 1.0)) * max(0.70, 1.0 + (factor - 1.0) * 0.35))

    strengths = state.waehrungen_staerke
    for currency in strengths:
        if currency == "GD":
            strengths[currency] = 1.0
            continue
        macro = state.makro.get(currency, {})
        relative = country_growth.get(currency, 0.0) - average_growth - float(macro.get("inflation", 0.02)) * dt * 0.08
        strengths[currency] = _clamp(float(strengths.get(currency, 1.0)) * math.exp(relative), 0.05, 20.0)

    total_gdp = sum(float(row.get("bip_abs", 0.0)) for row in state.makro.values())
    state.global_macro["global_gdp_growth"] = _clamp(average_growth / max(dt, 1.0 / 12.0), -0.06, 0.10)
    state.global_macro["global_cpi"] = sum(float(row.get("inflation", 0.0)) for row in state.makro.values()) / max(1, len(state.makro))
    state.global_macro["global_m2"] = max(1.0, total_gdp * 1.15)
    state.global_macro["net_liquidity"] = max(1.0, total_gdp * 0.92)
    state.global_macro["expected_global_growth"] = state.global_macro["global_gdp_growth"]
    state.global_macro["expected_global_cpi"] = state.global_macro["global_cpi"]
    state.global_macro["expected_avg_policy_rate"] = sum(float(row.get("zins", 0.0)) for row in state.makro.values()) / max(1, len(state.makro))
    state.global_macro["macro_surprise_index"] = 0.0
    update_sovereign_ratings(state)
    for macro in state.makro.values():
        funding_rate = _clamp(
            float(macro.get("zins", 0.035))
            + rating_spread(str(macro.get("rating", DEFAULT_RATING)))
            + max(0.0, float(macro.get("debt_to_gdp", 0.0)) - 0.75) * 0.012,
            0.002,
            0.25,
        )
        macro["sovereign_funding_rate"] = funding_rate
        macro["interest_burden"] = float(macro.get("debt_to_gdp", 0.0)) * funding_rate
    current_stock_caps = {
        str(ticker): max(0.0, float(asset.get("market_cap", 0.0)))
        for ticker, asset in state.aktien.items()
    }
    _refresh_composite_assets(state, previous_prices, previous_stock_caps, current_stock_caps)


def _refresh_composite_assets(
    state: Any,
    previous_prices: dict[tuple[str, str], float] | None = None,
    previous_stock_caps: dict[str, float] | None = None,
    current_stock_caps: dict[str, float] | None = None,
) -> None:
    previous_prices = previous_prices or _composite_underlying_prices(state)
    previous_stock_caps = previous_stock_caps or {
        str(ticker): max(0.0, float(asset.get("market_cap", 0.0)))
        for ticker, asset in state.aktien.items()
    }
    current_stock_caps = current_stock_caps or previous_stock_caps
    index_members = _stock_index_members(state)
    for ticker, asset in state.indizes.items():
        branch = str(asset.get("branche", ALL_SECTORS))
        members = index_members.get((str(asset.get("land", "")), branch), [])
        previous_cap = sum(previous_stock_caps.get(member, 0.0) for member in members)
        current_cap = sum(current_stock_caps.get(member, 0.0) for member in members)
        old_level = max(0.05, float(asset.get("kurs", 1000.0)))
        if previous_cap > 0.0:
            asset["kurs"] = max(0.05, old_level * current_cap / previous_cap)
        asset["market_cap"] = current_cap
        asset["constituent_count"] = len(members)
        asset["constituents"] = {
            member: current_stock_caps.get(member, 0.0) / current_cap if current_cap else 0.0
            for member in members
        }
        asset["aenderung"] = (float(asset["kurs"]) / old_level - 1.0) * 100.0

    current_prices = _composite_underlying_prices(state)
    for asset in state.fonds.values():
        weighted_return = 0.0
        for holding in asset.get("underlyings", []):
            asset_type = str(holding.get("asset_type", ""))
            ticker = str(holding.get("ticker", ""))
            old_price = previous_prices.get((asset_type, ticker), 0.0)
            new_price = current_prices.get((asset_type, ticker), old_price)
            if old_price > 0.0 and math.isfinite(new_price):
                weighted_return += float(holding.get("weight", 0.0)) * (new_price / old_price - 1.0)
        if str(asset.get("fund_type", "")) in {"Short ETF", "Leveraged ETF", "Short Leveraged ETF"}:
            weighted_return *= float(asset.get("leverage", 1.0))
        weighted_return *= 1.0 - _clamp(float(asset.get("cash_allocation", 0.0)), 0.0, 1.0)
        old_price = max(0.05, float(asset.get("kurs", 100.0)))
        asset["kurs"] = max(0.05, old_price * max(0.05, 1.0 + weighted_return))
        asset["aenderung"] = (float(asset["kurs"]) / old_price - 1.0) * 100.0
        old_aum = max(1.0, float(asset.get("aum", asset.get("market_cap", 1.0))))
        asset["aum"] = max(1.0, old_aum * max(0.05, 1.0 + weighted_return))
        asset["market_cap"] = asset["aum"]


def _composite_underlying_prices(state: Any) -> dict[tuple[str, str], float]:
    books = (
        ("Stock", state.aktien),
        ("Commodity", state.rohstoffe),
        ("Crypto", state.kryptos),
        ("Index", state.indizes),
    )
    return {
        (asset_type, str(ticker)): max(0.0, float(asset.get("kurs", asset.get("price", 0.0))))
        for asset_type, book in books
        for ticker, asset in book.items()
    }


def _rebaseline_handoff_state(state: Any) -> None:
    """Make the first production report compare one month with one month."""

    for asset in state.aktien.values():
        asset.pop("_workforce_coarse_base_margin", None)
        ensure_stock_fundamentals(asset)
        revenue = max(1.0, float(asset.get("revenue", 1.0)))
        free_cash_flow = float(asset.get("free_cash_flow", 0.0))
        margin = free_cash_flow / revenue
        shares = max(1.0, float(asset.get("aktien_anzahl", 10_000_000.0)))
        eps = max(0.1, free_cash_flow / shares)
        dividend_yield = float(asset.get("dividend_yield", 0.0))
        asset.update(
            previous_revenue=revenue,
            revenue_growth=0.0,
            previous_revenue_growth=0.0,
            free_cash_flow=free_cash_flow,
            previous_free_cash_flow=free_cash_flow,
            free_cash_flow_margin=margin,
            fcf_margin=margin,
            previous_fcf_margin=margin,
            eps=eps,
            previous_eps=eps,
            previous_dividend_yield=dividend_yield,
            operating_health=asset.pop("_workforce_coarse_health", 0.0),
            fundamental_repricing_remaining=0.0,
            fundamental_repricing_days=0,
            expectation=0.0,
            surprise=0.0,
            fear=0.0,
            euphoria=0.0,
            sentiment=0.0,
            crowding=0.0,
            news_momentum=0.0,
        )
        asset["_psychology_state"] = [0.0, 0.0, 0.0, 0.0, 0.0]
        asset["_psychology_ready"] = True


def _capture_bucket(state: Any, resolution: str, start: date, end: date, output: list[tuple[Any, ...]]) -> None:
    def add(table: str, entity: str, field: str, semantic: SemanticType, value: float) -> None:
        if not math.isfinite(value):
            return
        output.append((table, entity, field, semantic.value, resolution, start, end, value, value, value, value, value, 0.0, 1))

    for asset_type, book in (("Stock", state.aktien), ("Commodity", state.rohstoffe), ("Crypto", state.kryptos), ("Fund", state.fonds), ("Index", state.indizes), ("Derivative", state.derivatives)):
        for ticker, asset in book.items():
            add("asset_daily", f"{asset_type}:{ticker}", "price", SemanticType.PRICE, float(asset.get("kurs", 0.0)))
    if resolution == "yearly":
        for ticker, asset in state.aktien.items():
            for field, semantic in (("price", SemanticType.PRICE), ("market_cap", SemanticType.LEVEL), ("revenue", SemanticType.LEVEL), ("free_cash_flow", SemanticType.LEVEL)):
                key = "kurs" if field == "price" else field
                add("company_daily", str(ticker), field, semantic, float(asset.get(key, 0.0)))
    for region, macro in state.makro.items():
        fields = {"population": "bevoelkerung", "gdp": "bip_abs", "growth": "bip_prozent", "rate": "zins", "inflation": "inflation", "unemployment": "arbeitslosigkeit", "debt_to_gdp": "debt_to_gdp", "balance_sheet": "balance_sheet"}
        for field, key in fields.items():
            add("country_daily", str(region), field, SemanticType.RATE if field in {"growth", "rate", "inflation", "unemployment", "debt_to_gdp"} else SemanticType.LEVEL, float(macro.get(key, 0.0)))
        workforce = macro.get("workforce")
        if workforce:
            add("country_workforce_monthly", str(region), "population_growth_annualized", SemanticType.RATE,
                workforce["population_growth_annualized"])
            for pool in ("basic", "skilled", "highly_qualified"):
                for metric in ("supply", "demand", "coverage", "shortage"):
                    semantic = SemanticType.LEVEL if metric in {"supply", "demand"} else SemanticType.RATE
                    add("country_workforce_monthly", str(region), f"{pool}_{metric}", semantic,
                        workforce[metric][pool])
    for code, item in {**state.rohstoffe, **state.processed_products}.items():
        for field, key, semantic in (("price", "kurs", SemanticType.PRICE), ("produced", "supply", SemanticType.LEVEL), ("demanded", "demand", SemanticType.LEVEL), ("inventories", "inventories", SemanticType.LEVEL)):
            add("product_daily", str(code), field, semantic, float(item.get(key, 0.0)))
    for pair in state.FOREX_PAARE_HISTORIE:
        base, quote = pair.split("/", 1)
        rate = float(state.waehrungen_staerke.get(base, 1.0)) / max(1e-9, float(state.waehrungen_staerke.get(quote, 1.0)))
        add("forex_daily", pair, "rate", SemanticType.PRICE, rate)


def _install_recent_lookbacks(state: Any, end: date) -> None:
    for name in ("aktien", "rohstoffe", "kryptos", "fonds", "indizes", "derivatives"):
        for asset in getattr(state, name).values():
            price = max(0.000001, float(asset.get("kurs", 1.0)))
            asset["historie"] = [
                (price * (0.99 + index / 18_000.0), (end - timedelta(days=179 - index)).strftime("%d.%m.%Y"), "burn-in seed")
                for index in range(180)
            ]
            asset["aenderung"] = 0.0
            asset["prognose_target"] = price
            market_cap = max(1.0, float(asset.get("market_cap", 1.0)))
            asset["long_interest"] = market_cap * 0.020
            asset["short_interest"] = market_cap * 0.016
            asset["open_interest"] = market_cap * 0.036
    for pair in state.FOREX_PAARE_HISTORIE:
        base, quote = pair.split("/", 1)
        rate = float(state.waehrungen_staerke.get(base, 1.0)) / max(1e-9, float(state.waehrungen_staerke.get(quote, 1.0)))
        state.FOREX_PAARE_HISTORIE[pair] = [
            (rate, (end - timedelta(days=179 - index)).strftime("%d.%m.%Y"), "burn-in seed")
            for index in range(180)
        ]
    macro_fields = {
        "ZINS": "zins",
        "BIP": "bip_abs",
        "INF": "inflation",
        "ALO": "arbeitslosigkeit",
        "BS": "balance_sheet",
        "DEBT_GDP": "debt_to_gdp",
        "CREDIT": "credit_growth",
        "DEFICIT": "fiscal_deficit",
    }
    for region, macro in state.makro.items():
        for suffix, field in macro_fields.items():
            value = float(macro.get(field, 0.0))
            state.MAKRO_HISTORIE[f"{region}_{suffix}"] = [
                (value, (end - timedelta(days=30 * (23 - index))).strftime("%d.%m.%Y"), "burn-in seed")
                for index in range(24)
            ]
    state.GLOBAL_MACRO_HISTORIE = {
        key: [
            (float(value), (end - timedelta(days=179 - index)).strftime("%d.%m.%Y"), "burn-in seed")
            for index in range(180)
        ]
        for key, value in state.global_macro.items()
        if isinstance(value, (int, float))
    }
    state.gli_index = 15420.0
    state.GLI_HISTORIE = [15420.0] * 180


def _unit(seed: int, when: date, key: str, salt: str) -> float:
    payload = f"{seed}|{ECONOMIC_MODEL_VERSION}|{FAST_HISTORY_VERSION}|{when.isoformat()}|{key}|{salt}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / float(2**64 - 1)


def _uniform(seed: int, when: date, key: str, low: float, high: float) -> float:
    return low + (high - low) * _unit(seed, when, key, "u")


def _normal(seed: int, when: date, key: str, mean: float, sigma: float) -> float:
    u1 = max(1e-12, _unit(seed, when, key, "n1"))
    u2 = _unit(seed, when, key, "n2")
    return mean + sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
