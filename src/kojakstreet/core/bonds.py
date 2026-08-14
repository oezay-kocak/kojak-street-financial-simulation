"""Dynamic bond-market analytics and issuance."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from kojakstreet.core.countries import RESERVE_CURRENCY
from kojakstreet.core.ratings import DEFAULT_RATING, default_probability, rating_spread
from kojakstreet.core.state import GameState

BOND_TERMS = [3, 5, 10, 15, 20, 30]
CORPORATE_BOND_TERMS = [3, 5, 10, 20, 30]
BASE_GOVERNMENT_TERMS = [3, 10, 30]
BASE_CORPORATE_TERMS = [5]
MAX_MONTHLY_CORPORATE_NEED_ISSUES = 8
MAX_ACTIVE_BOND_MARKET_SIZE = 2_400
BOND_MARKET_ARCHIVE_LIMIT = 2_000


@dataclass(slots=True)
class BondOffer:
    symbol: str
    issuer: str
    issuer_type: str
    category: str
    region: str
    rating: str
    coupon: float
    yield_to_maturity: float
    price: float
    maturity_years: float
    duration: float
    default_risk: float
    liquidity: float
    maturity_date: datetime


def ensure_dynamic_bond_market(daten_module) -> None:
    if not hasattr(daten_module, "bond_market"):
        daten_module.bond_market = []
    if not daten_module.bond_market:
        _issue_initial_market(daten_module)
    _ensure_base_corporate_bonds(daten_module)
    daten_module.last_bond_issue_year = getattr(daten_module, "last_bond_issue_year", daten_module.datum.year)
    update_dynamic_bond_market(daten_module)


def update_dynamic_bond_market(daten_module, *, max_refresh: int | None = None) -> None:
    today = daten_module.datum
    source_market = list(getattr(daten_module, "bond_market", []))
    refresh_symbols = _refresh_symbol_slice(daten_module, source_market, max_refresh)
    market = []
    midpoint_issues: list[tuple[str, int]] = []
    for bond in source_market:
        maturity = _parse_date(bond.get("maturity_date"), today)
        if maturity <= today:
            continue
        symbol = str(bond.get("symbol", ""))
        should_refresh = max_refresh is None or symbol in refresh_symbols
        if should_refresh:
            _refresh_bond_quote(daten_module, bond)
        else:
            bond["aenderung"] = 0.0
        if should_refresh and _needs_midpoint_corporate_issue(bond, today):
            midpoint_issues.append((str(bond.get("ticker", "")), int(bond.get("term_years", 0))))
            bond["midpoint_issued"] = True
        market.append(bond)
    daten_module.bond_market = market

    for ticker, term_years in midpoint_issues:
        if ticker in getattr(daten_module, "aktien", {}) and term_years in CORPORATE_BOND_TERMS:
            _add_corporate_bond(daten_module, ticker, term_years, today, reason="refinancing")

    last_year = getattr(daten_module, "last_bond_issue_year", today.year)
    if today > _issue_date(daten_module, today.year) and today.year > last_year:
        for year in range(last_year + 1, today.year + 1):
            _issue_yearly_market(daten_module, year)
        daten_module.last_bond_issue_year = today.year
    _issue_need_based_market(daten_module)
    _archive_excess_bond_market(daten_module)
    _refresh_bond_symbol_lookup(daten_module)


def _refresh_symbol_slice(daten_module, market: list[dict[str, Any]], max_refresh: int | None) -> set[str]:
    if max_refresh is None or max_refresh <= 0 or len(market) <= max_refresh:
        return {str(bond.get("symbol", "")) for bond in market}
    cursor = int(getattr(daten_module, "bond_market_refresh_cursor", 0) or 0)
    selected = []
    for offset in range(max_refresh):
        bond = market[(cursor + offset) % len(market)]
        selected.append(str(bond.get("symbol", "")))
    daten_module.bond_market_refresh_cursor = (cursor + max_refresh) % len(market)
    return {symbol for symbol in selected if symbol}


def _refresh_bond_symbol_lookup(daten_module) -> None:
    market = getattr(daten_module, "bond_market", [])
    signature = tuple(str(bond.get("symbol", "")) for bond in market)
    cache_signature = getattr(daten_module, "bond_market_symbol_signature", None)
    if cache_signature == signature and isinstance(getattr(daten_module, "bond_market_by_symbol", None), dict):
        return
    daten_module.bond_market_by_symbol = {
        str(bond.get("symbol", "")): bond
        for bond in market
        if str(bond.get("symbol", ""))
    }
    daten_module.bond_market_symbol_signature = signature


def _archive_excess_bond_market(daten_module) -> None:
    market = list(getattr(daten_module, "bond_market", []))
    if len(market) <= MAX_ACTIVE_BOND_MARKET_SIZE:
        return

    today = getattr(daten_module, "datum", datetime(1990, 1, 1))
    ranked = sorted(
        market,
        key=lambda bond: _bond_retention_score(bond, today),
        reverse=True,
    )
    active = ranked[:MAX_ACTIVE_BOND_MARKET_SIZE]
    archived = ranked[MAX_ACTIVE_BOND_MARKET_SIZE:]
    archive = list(getattr(daten_module, "bond_market_archive", []))
    archive.extend(_archived_bond_snapshot(bond, today) for bond in archived)
    if len(archive) > BOND_MARKET_ARCHIVE_LIMIT:
        archive = archive[-BOND_MARKET_ARCHIVE_LIMIT:]
    daten_module.bond_market = sorted(active, key=lambda bond: str(bond.get("symbol", "")))
    daten_module.bond_market_archive = archive
    daten_module.bond_market_archive_count = int(getattr(daten_module, "bond_market_archive_count", 0)) + len(archived)


def _bond_retention_score(bond: dict[str, Any], today: datetime) -> tuple[float, str]:
    issuer_type = str(bond.get("issuer_type", "Corporate"))
    issue_reason = str(bond.get("issue_reason", "base"))
    maturity = _parse_date(bond.get("maturity_date"), today)
    issue_date = _parse_date(bond.get("issue_date"), today)
    years_to_maturity = max(0.0, (maturity - today).days / 365.0)
    age_years = max(0.0, (today - issue_date).days / 365.0)
    liquidity = float(bond.get("liquidity", 0.6))
    base_score = 100.0 if issue_reason == "base" else 0.0
    government_score = 80.0 if issuer_type == "Government" else 0.0
    recency_score = max(0.0, 20.0 - age_years * 2.0)
    maturity_score = min(20.0, years_to_maturity)
    liquidity_score = liquidity * 10.0
    return (
        base_score + government_score + recency_score + maturity_score + liquidity_score,
        str(bond.get("symbol", "")),
    )


def _archived_bond_snapshot(bond: dict[str, Any], today: datetime) -> dict[str, Any]:
    return {
        "symbol": str(bond.get("symbol", "")),
        "issuer": str(bond.get("issuer", "")),
        "issuer_type": str(bond.get("issuer_type", "")),
        "region": str(bond.get("region", "")),
        "rating": str(bond.get("rating", "")),
        "issue_reason": str(bond.get("issue_reason", "")),
        "issue_date": bond.get("issue_date"),
        "maturity_date": bond.get("maturity_date"),
        "last_price": float(bond.get("price", 100.0)),
        "last_yield_to_maturity": float(bond.get("yield_to_maturity", 0.0)),
        "archived_at": today,
    }


def build_bond_offers(
    state: GameState,
    category: str = "Government",
    *,
    region: str = "All Regions",
    rating: str = "All Ratings",
    maturity: str = "All Maturities",
) -> list[BondOffer]:
    offers = [_offer_from_dict(state, bond) for bond in state.bond_market]
    if not offers:
        offers = _fallback_offers(state)
    return [
        offer
        for offer in offers
        if _matches_category(offer, category)
        and _matches_region(offer, region)
        and _matches_rating(offer, rating)
        and _matches_maturity(offer, maturity)
    ]


def _issue_initial_market(daten_module) -> None:
    for region in daten_module.makro:
        daten_module.makro[region].setdefault("rating", DEFAULT_RATING)
        for term in BASE_GOVERNMENT_TERMS:
            _add_government_bond(daten_module, region, term, daten_module.datum.year, reason="base")
    for ticker in sorted(getattr(daten_module, "aktien", {})):
        for term in BASE_CORPORATE_TERMS:
            _add_corporate_bond(daten_module, ticker, term, daten_module.datum.year, reason="base")


def _issue_yearly_market(daten_module, year: int) -> None:
    for region in daten_module.makro:
        _add_government_bond(daten_module, region, random.choice(BASE_GOVERNMENT_TERMS), year, reason="base")


def _add_government_bond(
    daten_module,
    region: str,
    term_years: int,
    issue_year_or_date: int | datetime,
    *,
    reason: str = "base",
) -> None:
    local_rate = float(daten_module.makro.get(region, {}).get("zins", 0.035))
    rating = str(daten_module.makro.get(region, {}).get("rating", DEFAULT_RATING))
    coupon = _coupon_for(local_rate, rating, "Government", term_years)
    issue_date = (
        _issue_date(daten_module, issue_year_or_date)
        if isinstance(issue_year_or_date, int)
        else issue_year_or_date
    )
    issue_code = issue_date.strftime("%Y%m%d")
    reason_code = _reason_code(reason)
    bond = {
        "symbol": f"GOV-{_region_code(region)}-{issue_code}-{reason_code}-{term_years}Y",
        "issuer": f"Central Government {region}",
        "issuer_type": "Government",
        "category": "Government",
        "region": region,
        "rating": rating,
        "coupon": coupon,
        "nominal": 100.0,
        "term_years": term_years,
        "issue_reason": reason,
        "issue_date": issue_date,
        "maturity_date": issue_date + timedelta(days=term_years * 365),
        "liquidity": random.uniform(0.75, 1.0),
    }
    if any(str(existing.get("symbol", "")) == bond["symbol"] for existing in getattr(daten_module, "bond_market", [])):
        return
    _refresh_bond_quote(daten_module, bond)
    daten_module.bond_market.append(bond)
    if reason != "base":
        _apply_government_issue_proceeds(daten_module, region, term_years)


def _add_corporate_bond(
    daten_module,
    ticker: str,
    term_years: int,
    issue_year_or_date: int | datetime,
    *,
    reason: str = "base",
) -> None:
    asset = daten_module.aktien[ticker]
    region = str(asset.get("land", RESERVE_CURRENCY))
    rating = str(asset.get("rating", DEFAULT_RATING))
    local_rate = float(daten_module.makro.get(region, {}).get("zins", 0.045))
    coupon = _coupon_for(local_rate, rating, "Corporate", term_years)
    issue_date = (
        _issue_date(daten_module, issue_year_or_date)
        if isinstance(issue_year_or_date, int)
        else issue_year_or_date
    )
    issue_code = issue_date.strftime("%Y%m%d")
    reason_code = _reason_code(reason)
    symbol = f"CORP-{ticker}-{issue_code}-{reason_code}-{term_years}Y"
    if any(str(bond.get("symbol", "")) == symbol for bond in getattr(daten_module, "bond_market", [])):
        return
    bond = {
        "symbol": symbol,
        "issuer": str(asset.get("name", ticker)),
        "issuer_type": "Corporate",
        "category": str(asset.get("branche", "Corporate")),
        "region": region,
        "rating": rating,
        "coupon": coupon,
        "nominal": 100.0,
        "ticker": ticker,
        "term_years": term_years,
        "issue_reason": reason,
        "issue_date": issue_date,
        "maturity_date": issue_date + timedelta(days=term_years * 365),
        "liquidity": random.uniform(0.35, 0.85),
        "midpoint_issued": False,
    }
    _refresh_bond_quote(daten_module, bond)
    daten_module.bond_market.append(bond)
    if reason != "base":
        _apply_corporate_issue_proceeds(asset, term_years)


def _ensure_base_corporate_bonds(daten_module) -> None:
    existing = {
        (str(bond.get("ticker", "")), int(bond.get("term_years", 0)))
        for bond in getattr(daten_module, "bond_market", [])
        if str(bond.get("issuer_type", "")) == "Corporate"
        and str(bond.get("issue_reason", "base")) == "base"
        and _parse_date(bond.get("maturity_date"), daten_module.datum) > daten_module.datum
    }
    for ticker in sorted(getattr(daten_module, "aktien", {})):
        for term in BASE_CORPORATE_TERMS:
            if (ticker, term) not in existing:
                _add_corporate_bond(daten_module, ticker, term, daten_module.datum.year, reason="base")
                existing.add((ticker, term))


def _needs_midpoint_corporate_issue(bond: dict[str, Any], today: datetime) -> bool:
    if str(bond.get("issuer_type", "")) != "Corporate" or bond.get("midpoint_issued"):
        return False
    ticker = str(bond.get("ticker", ""))
    term_years = int(bond.get("term_years", 0))
    if not ticker or term_years not in CORPORATE_BOND_TERMS:
        return False
    issue_date = _parse_date(bond.get("issue_date"), today)
    midpoint_date = issue_date + timedelta(days=round(term_years * 365 / 2))
    return today >= midpoint_date


def _apply_corporate_issue_proceeds(asset: dict[str, Any], term_years: int) -> None:
    market_cap = max(1.0, float(asset.get("market_cap", 1.0)))
    issue_size = market_cap * min(0.035, 0.010 + term_years * 0.001)
    asset["debt"] = float(asset.get("debt", market_cap * 0.20)) + issue_size
    asset["cash_reserves"] = float(asset.get("cash_reserves", market_cap * 0.08)) + issue_size * 0.92
    asset["debt_to_market_cap"] = asset["debt"] / market_cap
    asset["refinancing_momentum"] = min(0.04, float(asset.get("refinancing_momentum", 0.0)) + issue_size / market_cap)


def _issue_need_based_market(daten_module) -> None:
    today = daten_module.datum
    month_key = today.strftime("%Y-%m")
    if getattr(daten_module, "last_need_based_bond_issue_month", "") == month_key:
        return
    issued = _issue_government_need_bonds(daten_module, today)
    issued += _issue_corporate_need_bonds(daten_module, today)
    if issued:
        daten_module.last_need_based_bond_issue_month = month_key


def _issue_government_need_bonds(daten_module, today: datetime) -> int:
    issued = 0
    for region, macro in getattr(daten_module, "makro", {}).items():
        gdp = max(1.0, float(macro.get("bip_abs", 1.0)))
        deficit_ratio = float(macro.get("fiscal_deficit", 0.0)) / gdp
        debt_to_gdp = float(macro.get("debt_to_gdp", 0.62))
        interest_burden = float(macro.get("interest_burden", 0.025))
        need_score = (
            max(0.0, deficit_ratio - 0.035) * 9.0
            + max(0.0, debt_to_gdp - 0.85) * 0.55
            + max(0.0, interest_burden - 0.045) * 7.5
        )
        if need_score <= 0.02:
            continue
        terms = [3] if need_score < 0.12 else [3, 10]
        if need_score > 0.28:
            terms.append(20)
        for term in terms:
            _add_government_bond(daten_module, region, term, today, reason="funding")
            issued += 1
    return issued


def _issue_corporate_need_bonds(daten_module, today: datetime) -> int:
    candidates: list[tuple[float, str, int]] = []
    for ticker, asset in getattr(daten_module, "aktien", {}).items():
        market_cap = max(1.0, float(asset.get("market_cap", 1.0)))
        revenue = max(1.0, float(asset.get("revenue", market_cap * 0.35)))
        cash_buffer = float(asset.get("cash_reserves", market_cap * 0.08)) / revenue
        debt_ratio = float(asset.get("debt_to_market_cap", 0.20))
        fcf_margin = float(asset.get("fcf_margin", 0.08))
        need_score = (
            max(0.0, 0.10 - cash_buffer) * 1.5
            + max(0.0, debt_ratio - 0.55) * 0.50
            + max(0.0, 0.025 - fcf_margin) * 2.0
        )
        if need_score <= 0.03:
            continue
        term = 3 if cash_buffer < 0.04 else 5 if debt_ratio > 0.75 else 10
        candidates.append((need_score, str(ticker), term))
    candidates.sort(reverse=True)
    issued = 0
    for _score, ticker, term in candidates[:MAX_MONTHLY_CORPORATE_NEED_ISSUES]:
        _add_corporate_bond(daten_module, ticker, term, today, reason="funding")
        issued += 1
    return issued


def _apply_government_issue_proceeds(daten_module, region: str, term_years: int) -> None:
    macro = getattr(daten_module, "makro", {}).get(region)
    if not isinstance(macro, dict):
        return
    gdp = max(1.0, float(macro.get("bip_abs", 1.0)))
    issue_size = gdp * min(0.028, 0.006 + term_years * 0.0008)
    macro["government_debt"] = float(macro.get("government_debt", gdp * 0.62)) + issue_size
    macro["sovereign_cash_buffer"] = float(macro.get("sovereign_cash_buffer", gdp * 0.015)) + issue_size * 0.94
    macro["debt_to_gdp"] = macro["government_debt"] / gdp
    macro["interest_burden"] = macro["government_debt"] * float(macro.get("zins", 0.035)) / gdp
    macro["bond_funding_impulse"] = min(0.05, float(macro.get("bond_funding_impulse", 0.0)) + issue_size / gdp)


def _refresh_bond_quote(daten_module, bond: dict[str, Any]) -> None:
    today = daten_module.datum
    maturity = _parse_date(bond.get("maturity_date"), today)
    years = max(0.05, (maturity - today).days / 365.0)
    region = str(bond.get("region", RESERVE_CURRENCY))
    rating = str(bond.get("rating", DEFAULT_RATING))
    issuer_type = str(bond.get("issuer_type", "Corporate"))
    local_rate = float(daten_module.makro.get(region, {}).get("zins", 0.04))
    issuer_spread = 0.0 if issuer_type == "Government" else 0.012
    term_spread = min(0.020, years * 0.0012)
    default_risk = _default_risk(rating, years, issuer_type)
    balance_spread = _issuer_balance_spread(daten_module, bond, issuer_type, region)
    market_yield = max(0.001, local_rate + rating_spread(rating) + issuer_spread + term_spread + balance_spread)
    coupon = float(bond.get("coupon", market_yield))
    fair_price = _bond_price(100.0, coupon, market_yield, years)
    liquidity = float(bond.get("liquidity", 0.6))
    previous_price = float(bond.get("price", fair_price))
    previous_yield = float(bond.get("yield_to_maturity", market_yield))
    smooth_price = _smooth_secondary_market_price(
        previous_price,
        fair_price - ((1.0 - liquidity) * 0.35),
        previous_yield,
        market_yield,
        years,
        liquidity,
        issuer_type,
    )
    bond["yield_to_maturity"] = market_yield
    bond["fair_price"] = fair_price
    bond["price"] = max(20.0, min(160.0, smooth_price))
    bond["aenderung"] = ((bond["price"] - previous_price) / previous_price) * 100 if previous_price > 0 else 0.0
    bond["last_price_update_ordinal"] = today.toordinal()
    bond["maturity_years"] = years
    bond["duration"] = min(years, years / (1.0 + market_yield))
    bond["default_risk"] = default_risk
    _append_price_history(bond, today)


def _issuer_balance_spread(daten_module, bond: dict[str, Any], issuer_type: str, region: str) -> float:
    if issuer_type == "Government":
        macro = getattr(daten_module, "makro", {}).get(region, {})
        debt_to_gdp = float(macro.get("debt_to_gdp", 0.62))
        fiscal_impulse = float(macro.get("fiscal_impulse", 0.0))
        interest_burden = float(macro.get("interest_burden", 0.025))
        return max(0.0, debt_to_gdp - 0.75) * 0.018 + max(0.0, fiscal_impulse) * 0.12 + max(0.0, interest_burden - 0.04) * 0.35
    ticker = str(bond.get("ticker", ""))
    asset = getattr(daten_module, "aktien", {}).get(ticker, {})
    debt_ratio = float(asset.get("debt_to_market_cap", 0.20))
    fcf_margin = float(asset.get("fcf_margin", 0.08))
    cash_reserves = float(asset.get("cash_reserves", 0.0))
    revenue = max(1.0, float(asset.get("revenue", 1.0)))
    cash_buffer = cash_reserves / revenue
    return max(0.0, debt_ratio - 0.45) * 0.026 + max(0.0, 0.04 - fcf_margin) * 0.18 - min(0.006, cash_buffer * 0.012)


def _offer_from_dict(state: GameState, bond: dict[str, Any]) -> BondOffer:
    maturity = _parse_date(bond.get("maturity_date"), state.date)
    return BondOffer(
        symbol=str(bond.get("symbol", "")),
        issuer=str(bond.get("issuer", "")),
        issuer_type=str(bond.get("issuer_type", "Corporate")),
        category=str(bond.get("category", "")),
        region=str(bond.get("region", "")),
        rating=str(bond.get("rating", DEFAULT_RATING)),
        coupon=float(bond.get("coupon", 0.0)),
        yield_to_maturity=float(bond.get("yield_to_maturity", 0.0)),
        price=float(bond.get("price", 100.0)),
        maturity_years=float(bond.get("maturity_years", max(0.0, (maturity - state.date).days / 365.0))),
        duration=float(bond.get("duration", 0.0)),
        default_risk=float(bond.get("default_risk", 0.0)),
        liquidity=float(bond.get("liquidity", 0.6)),
        maturity_date=maturity,
    )


def _fallback_offers(state: GameState) -> list[BondOffer]:
    today = state.date
    offers = []
    for region, data in state.macro.items():
        local_rate = float(data.get("zins", 0.035))
        rating = str(data.get("rating", DEFAULT_RATING))
        offers.append(
            BondOffer(
                symbol=f"GOV-{_region_code(region)}",
                issuer=f"Central Government {region}",
                issuer_type="Government",
                category="Government",
                region=region,
                rating=rating,
                coupon=local_rate + rating_spread(rating),
                yield_to_maturity=local_rate + rating_spread(rating) + 0.010,
                price=100.0,
                maturity_years=10.0,
                duration=8.8,
                default_risk=default_probability(rating),
                liquidity=0.95,
                maturity_date=today + timedelta(days=3650),
            )
        )
    return offers


def _bond_price(face: float, coupon: float, market_yield: float, years: float) -> float:
    periods = max(1, round(years * 2))
    period_coupon = face * coupon / 2.0
    discount = 1.0 + (market_yield / 2.0)
    discount_power = discount**periods
    if abs(discount - 1.0) < 1e-9:
        coupon_value = period_coupon * periods
    else:
        coupon_value = period_coupon * (1.0 - (1.0 / discount_power)) / (discount - 1.0)
    principal_value = face / discount_power
    return coupon_value + principal_value


def _smooth_secondary_market_price(
    previous_price: float,
    fair_price: float,
    previous_yield: float,
    market_yield: float,
    years: float,
    liquidity: float,
    issuer_type: str,
) -> float:
    duration = min(years, years / (1.0 + max(market_yield, 0.001)))
    rate_shock = previous_yield - market_yield
    expectation_move = previous_price * rate_shock * duration * 0.28
    gap = fair_price - previous_price
    digestion_speed = 0.035 + min(0.065, duration * 0.002)
    if issuer_type != "Government":
        digestion_speed += 0.020
    liquidity_noise = random.uniform(-0.018, 0.018) * (1.0 - liquidity) * max(1.0, duration / 6.0)
    return previous_price + expectation_move + (gap * digestion_speed) + liquidity_noise


def _coupon_for(local_rate: float, rating: str, issuer_type: str, term_years: int) -> float:
    issuer_spread = 0.0 if issuer_type == "Government" else 0.012
    return max(0.001, local_rate + rating_spread(rating) + issuer_spread + min(0.02, term_years * 0.0012))


def _default_risk(rating: str, years: float, issuer_type: str) -> float:
    horizon_factor = max(0.45, years / 10.0)
    issuer_factor = 0.75 if issuer_type == "Government" else 1.0
    return min(0.95, default_probability(rating) * horizon_factor * issuer_factor)


def _matches_category(offer: BondOffer, category: str) -> bool:
    return category in {"All", "All Categories"} or offer.category == category or offer.issuer_type == category


def _matches_region(offer: BondOffer, region: str) -> bool:
    return region == "All Regions" or offer.region == region


def _matches_rating(offer: BondOffer, rating: str) -> bool:
    return rating == "All Ratings" or offer.rating == rating


def _matches_maturity(offer: BondOffer, maturity: str) -> bool:
    years = offer.maturity_years
    if maturity == "All Maturities":
        return True
    if maturity == "0-3Y":
        return years <= 3.0
    if maturity == "3-7Y":
        return 3.0 < years <= 7.0
    if maturity == "7-15Y":
        return 7.0 < years <= 15.0
    if maturity == "15Y+":
        return years > 15.0
    return True


def _region_code(region: str) -> str:
    return region.replace("ß", "B").replace("ÃŸ", "B")[:3].upper()


def _reason_code(reason: str) -> str:
    cleaned = "".join(char for char in str(reason).upper() if char.isalnum())
    return (cleaned or "BASE")[:4]


def _parse_date(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return fallback
    return fallback


def _issue_date(daten_module, issue_year: int) -> datetime:
    return daten_module.datum.replace(year=issue_year, month=1, day=2)


def _append_price_history(bond: dict[str, Any], today: datetime) -> None:
    history = bond.setdefault("historie", [])
    date_text = today.strftime("%d.%m.%Y")
    price = float(bond.get("price", 100.0))
    if history and isinstance(history[-1], (tuple, list)) and len(history[-1]) > 1 and history[-1][1] == date_text:
        history[-1] = (price, date_text, "")
    else:
        history.append((price, date_text, ""))
    if len(history) > 520:
        del history[:-520]
