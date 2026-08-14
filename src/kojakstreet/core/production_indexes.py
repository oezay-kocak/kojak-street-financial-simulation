"""Runtime indexes for production calculations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CompanyProductionRuntime:
    asset: dict[str, Any]
    country: str
    sector: str


def company_runtimes(daten: Any) -> list[CompanyProductionRuntime]:
    """Return cached company runtime rows for the current company universe shape."""

    stocks = getattr(daten, "aktien", {})
    signature = tuple(stocks.keys())
    cache = getattr(daten, "_production_company_runtime_cache", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["runtimes"]
    runtimes = [
        CompanyProductionRuntime(
            asset=asset,
            country=str(asset.get("land", "")),
            sector=str(asset.get("branche", "")),
        )
        for asset in stocks.values()
    ]
    daten._production_company_runtime_cache = {"signature": signature, "runtimes": runtimes}
    return runtimes


def main_country_sectors(company_rows: list[CompanyProductionRuntime]) -> dict[str, str]:
    totals_by_country: dict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in company_rows:
        if not row.country:
            continue
        totals_by_country[row.country][row.sector] += float(row.asset.get("production_capacity", 0.0))
    return {
        country: max(totals, key=totals.get)
        for country, totals in totals_by_country.items()
        if totals
    }
