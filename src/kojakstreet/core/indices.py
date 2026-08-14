"""Market-cap weighted equity index universe."""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Any

from kojakstreet.core.companies import BRANCHEN
from kojakstreet.core.countries import COUNTRIES
from kojakstreet.core.ohlc import append_ohlc_from_move

START_INDEX_LEVEL = 1000.0


@dataclass(frozen=True, slots=True)
class IndexDefinition:
    ticker: str
    name: str
    country: str
    branch: str | None = None


COMPOSITE_TICKERS = {
    "Ameron": "AMX",
    "Albionia": "ABX",
    "Ardonia": "ADX",
    "Valoria": "VLX",
    "Romara": "RMX",
    "Soleria": "SLX",
    "Nordmark": "NMX",
    "Sarmatia": "SMX",
    "Danubria": "DBX",
    "Carpathia": "CPX",
    "Anatria": "ATX",
    "Azaria": "AZX",
    "Indara": "IDX",
    "Hanxia": "HNX",
    "Pacifica": "PFX",
    "Koryo": "KRX",
    "Amazonia": "ANX",
    "Canadia": "CNX",
    "Auroria": "AUX",
    "Savanna": "SVX",
}

SECTOR_PREFIXES = {
    "Ameron": "AMX",
    "Albionia": "ALX",
    "Ardonia": "ARX",
    "Valoria": "VLX",
    "Romara": "RMX",
    "Soleria": "SLX",
    "Nordmark": "NMX",
    "Sarmatia": "SMX",
    "Danubria": "DBX",
    "Carpathia": "CPX",
    "Anatria": "ATX",
    "Azaria": "AZX",
    "Indara": "IDX",
    "Hanxia": "HNX",
    "Pacifica": "PFX",
    "Koryo": "KRX",
    "Amazonia": "ANX",
    "Canadia": "CNX",
    "Auroria": "AUX",
    "Savanna": "SVX",
}

SECTOR_INDEX_LABELS = {
    "Automobil": ("Automotive", "AUTO"),
    "Chemie": ("Chemicals", "CHEM"),
    "\u00d6l und Gas": ("Oil & Gas", "OIL"),
    "Stromerzeuger": ("Utilities", "UTIL"),
    "Maschinenbau": ("Industrials", "IND"),
    "Telekommunikation": ("Telecommunications", "TEL"),
    "Einzelhandel": ("Retail", "RET"),
    "Konsumg\u00fcter": ("Consumer Goods", "CONS"),
    "Finanzen": ("Financials", "FIN"),
    "Edelmetallf\u00f6rderer": ("Precious Metals", "PMET"),
    "Gesundheit": ("Healthcare", "HEAL"),
    "Technologie": ("Technology", "TECH"),
    "Immobilien": ("Real Estate", "REAL"),
    "Transport und Logistik": ("Transport & Logistics", "LOG"),
    "Verteidigung": ("Defense", "DEF"),
    "Landwirtschaft": ("Agriculture", "AGR"),
}


def index_definitions() -> list[IndexDefinition]:
    definitions: list[IndexDefinition] = []
    for country in COUNTRIES:
        composite_ticker = COMPOSITE_TICKERS[country.name]
        definitions.append(IndexDefinition(composite_ticker, f"{country.name} Composite", country.name))
        sector_prefix = SECTOR_PREFIXES[country.name]
        for branch in BRANCHEN:
            label, suffix = SECTOR_INDEX_LABELS[branch]
            definitions.append(
                IndexDefinition(
                    f"{sector_prefix}-{suffix}",
                    f"{country.name} {label} Index",
                    country.name,
                    branch,
                )
            )
    return definitions


def ensure_index_universe(daten: ModuleType) -> None:
    existing = getattr(daten, "indizes", {})
    next_indices: dict[str, dict[str, Any]] = {}
    for definition in index_definitions():
        current = dict(existing.get(definition.ticker, {}))
        current.setdefault("kurs", START_INDEX_LEVEL)
        current.setdefault("historie", [(START_INDEX_LEVEL, "01.01.1990", "")])
        current.setdefault("aenderung", 0.0)
        current.update(
            {
                "name": definition.name,
                "land": definition.country,
                "branche": definition.branch or "All Sectors",
                "typ": "Equity Index",
                "index_type": "Country" if definition.branch is None else "Sector",
                "methodology": "Market-cap weighted",
                "base_level": START_INDEX_LEVEL,
            }
        )
        _refresh_index_composition(current, getattr(daten, "aktien", {}))
        next_indices[definition.ticker] = current
    daten.indizes = next_indices


def update_indices(daten: ModuleType, zeit_str: str) -> None:
    ensure_index_universe(daten)
    for index in daten.indizes.values():
        old_level = float(index.get("kurs", START_INDEX_LEVEL))
        components = _matching_stocks(index, getattr(daten, "aktien", {}))
        previous_total = 0.0
        current_total = 0.0
        for _ticker, asset in components:
            shares = float(asset.get("aktien_anzahl", 10_000_000.0))
            price = float(asset.get("kurs", 0.0))
            change = float(asset.get("aenderung", 0.0))
            change_factor = 1.0 + change / 100.0
            previous_price = price / change_factor if change_factor > 0 else price
            previous_total += previous_price * shares
            current_total += price * shares
        if previous_total > 0:
            index["kurs"] = max(1.0, old_level * (current_total / previous_total))
        index["market_cap"] = current_total
        index["aenderung"] = ((float(index["kurs"]) - old_level) / old_level * 100.0) if old_level > 0 else 0.0
        _refresh_index_composition(index, dict(components), total_market_cap=current_total)
        append_ohlc_from_move(index, old_level, index["kurs"], zeit_str)


def _refresh_index_composition(
    index: dict[str, Any],
    stocks: Any,
    *,
    total_market_cap: float | None = None,
) -> None:
    components = _matching_stocks(index, stocks)
    total = total_market_cap
    if total is None:
        total = sum(float(asset.get("market_cap", 0.0)) for _ticker, asset in components)
    index["market_cap"] = float(total or 0.0)
    index["constituent_count"] = len(components)
    index["constituents"] = {
        ticker: (
            float(asset.get("market_cap", 0.0)) / total if total else 0.0
        )
        for ticker, asset in components
    }


def _matching_stocks(index: dict[str, Any], stocks: dict[str, dict[str, Any]] | Any) -> list[tuple[str, dict[str, Any]]]:
    country = str(index.get("land", ""))
    branch = str(index.get("branche", "All Sectors"))
    items = stocks.items() if isinstance(stocks, dict) else enumerate(stocks)
    return [
        (str(ticker), asset)
        for ticker, asset in items
        if str(asset.get("land", "")) == country
        and (branch == "All Sectors" or str(asset.get("branche", "")) == branch)
    ]
