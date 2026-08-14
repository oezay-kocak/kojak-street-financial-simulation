"""Derived details for bonds held in the player portfolio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kojakstreet.core.ratings import default_probability, normalize_rating


@dataclass(frozen=True, slots=True)
class BondPositionDetail:
    bond_type: str
    issuer: str
    region: str
    nominal: float
    market_value: float
    coupon: float
    remaining_years: float
    duration: float
    yield_to_maturity: float
    rating: str
    default_risk: float
    meta: str


def owned_bond_details(state: Any) -> list[BondPositionDetail]:
    lookup = _bond_market_lookup(state)
    rows: list[BondPositionDetail] = []
    for bond in getattr(state, "bonds", getattr(state, "anleihen", [])):
        if not isinstance(bond, dict):
            continue
        market_bond = lookup.get(str(bond.get("symbol", "")), {})
        merged = {**market_bond, **bond}
        nominal = float(merged.get("nominal", 0.0))
        market_price = float(merged.get("market_price", merged.get("price", 100.0)))
        remaining_years = _remaining_years(merged)
        rating = normalize_rating(str(merged.get("rating", "BBB")))
        annual_pd = default_probability(rating)
        default_risk = 1.0 - ((1.0 - annual_pd) ** max(0.0, remaining_years))
        rows.append(
            BondPositionDetail(
                bond_type=str(merged.get("typ", merged.get("issuer_type", "Bond"))),
                issuer=str(merged.get("ticker", merged.get("issuer", "Bond"))),
                region=str(merged.get("land", merged.get("region", ""))),
                nominal=nominal,
                market_value=nominal * market_price / 100.0,
                coupon=float(merged.get("zins", merged.get("coupon", 0.0))),
                remaining_years=remaining_years,
                duration=float(merged.get("duration", remaining_years)),
                yield_to_maturity=float(merged.get("yield_to_maturity", merged.get("yield", 0.0))),
                rating=rating,
                default_risk=default_risk,
                meta="Held",
            )
        )
    return rows


def _bond_market_lookup(state: Any) -> dict[str, dict[str, Any]]:
    lookup = getattr(state, "bond_market_by_symbol", None)
    if isinstance(lookup, dict):
        return lookup
    return {
        str(bond.get("symbol", "")): bond
        for bond in getattr(state, "bond_market", [])
        if isinstance(bond, dict) and str(bond.get("symbol", ""))
    }


def _remaining_years(bond: dict[str, Any]) -> float:
    if "resttage" in bond:
        return max(0.0, float(bond.get("resttage", 0.0)) / 365.0)
    if "remaining_years" in bond:
        return max(0.0, float(bond.get("remaining_years", 0.0)))
    return max(0.0, float(bond.get("maturity_years", 0.0)))
