"""Dynamic public-company universe, name generation and bankruptcy rules."""

from __future__ import annotations

import random
import string
from collections import Counter
from datetime import datetime
from types import ModuleType

from kojakstreet.core.countries import COUNTRY_STYLES
from kojakstreet.core.fundamentals import ensure_stock_fundamentals
from kojakstreet.core.production_chains import (
    assign_company_specialization,
    assign_company_specializations,
    opportunity_sector,
)
from kojakstreet.core.ratings import DEFAULT_RATING, RATINGS, default_probability, rating_index

BRANCHEN = [
    "Automobil",
    "Chemie",
    "\u00d6l und Gas",
    "Stromerzeuger",
    "Maschinenbau",
    "Telekommunikation",
    "Einzelhandel",
    "Konsumg\u00fcter",
    "Finanzen",
    "Edelmetallf\u00f6rderer",
    "Gesundheit",
    "Technologie",
    "Immobilien",
    "Transport und Logistik",
    "Verteidigung",
    "Landwirtschaft",
]

START_COMPANIES_PER_COUNTRY_SECTOR = 4
TARGET_COMPANY_COUNT = len(COUNTRY_STYLES) * len(BRANCHEN) * START_COMPANIES_PER_COUNTRY_SECTOR
INITIAL_MARKET_CAP = 1_000_000_000.0
BANKRUPT_RATING_INDEX = rating_index("CCC-")

STYLE_NAME_PARTS = {
    "american": {
        "prefix": ["Blue", "United", "Summit", "Pioneer", "Liberty", "Grand", "North", "Vertex"],
        "core": ["Creek", "Harbor", "Ridge", "Valley", "River", "Stone", "Prairie", "Forge"],
        "suffix": ["Holdings", "Systems", "Works", "Industries", "Resources", "Group", "Corp"],
    },
    "british": {
        "prefix": ["Royal", "Crown", "Albion", "Sterling", "Thames", "Regent", "Harbour", "Britannic"],
        "core": ["Vale", "Bridge", "Marsh", "Foundry", "Heath", "Moor", "Cairn", "Wick"],
        "suffix": ["plc", "Holdings", "Group", "Works", "Industries", "Resources"],
    },
    "german": {
        "prefix": ["Arden", "Nord", "Rhein", "Kron", "Berg", "Hansa", "Eisen", "Wald"],
        "core": ["Werk", "Feld", "Stahl", "Haus", "Technik", "Fabrik", "Kraft", "Handel"],
        "suffix": ["AG", "Gruppe", "Werke", "Industrie", "Holding", "Systeme"],
    },
    "french": {
        "prefix": ["Val", "Belle", "Mont", "Lumiere", "Rive", "Bleu", "Avenir", "Ciel"],
        "core": ["Maison", "Forge", "Terre", "Soleil", "Marches", "Rhone", "Clair", "Vall"],
        "suffix": ["SA", "Groupe", "Industries", "Services", "Holding", "Syst\u00e8mes"],
    },
    "italian": {
        "prefix": ["Roma", "Venezia", "Luna", "Stella", "Aurea", "Monte", "Nova", "Riva"],
        "core": ["Ferro", "Casa", "Motori", "Vita", "Ponte", "Mare", "Valle", "Forma"],
        "suffix": ["SpA", "Gruppo", "Industrie", "Holding", "Sistemi", "Societa"],
    },
    "spanish": {
        "prefix": ["Sol", "Iber", "Castilla", "Brava", "Rio", "Nova", "Luz", "Costa"],
        "core": ["Fabrica", "Mercado", "Valle", "Toro", "Mar", "Piedra", "Campo", "Forma"],
        "suffix": ["SA", "Grupo", "Industrias", "Servicios", "Holding", "Sistemas"],
    },
    "nordic": {
        "prefix": ["Nord", "Fjord", "Arctic", "Saga", "Vik", "Boreal", "Skye", "Polar"],
        "core": ["Mark", "Havn", "Fjell", "Kraft", "Sten", "Vann", "Verk", "Lund"],
        "suffix": ["ASA", "Group", "Works", "Industries", "Holding", "Systems"],
    },
    "polish": {
        "prefix": ["Sarma", "Vistula", "Baltic", "Orzel", "Nova", "Krak", "Mazur", "Zorin"],
        "core": ["Stal", "Most", "Pol", "Tech", "Huta", "Rynek", "Energia", "Dom"],
        "suffix": ["SA", "Group", "Works", "Industries", "Holding", "Systems"],
    },
    "hungarian": {
        "prefix": ["Duna", "Magyar", "Pannon", "Karp", "Tisza", "Buda", "Floren", "Alba"],
        "core": ["Muvek", "Hid", "Ferro", "Piac", "Energia", "Tech", "Haz", "Forma"],
        "suffix": ["Nyrt", "Group", "Works", "Industries", "Holding", "Systems"],
    },
    "slavic": {
        "prefix": ["Karp", "Volga", "Zarya", "Sever", "Mir", "Ural", "Korin", "Novaya"],
        "core": ["Prom", "Stal", "Neft", "Mash", "Energo", "Dom", "Tekh", "Most"],
        "suffix": ["Group", "Industries", "Works", "Holding", "Systems", "Resources"],
    },
    "turkish": {
        "prefix": ["Anatol", "Mavi", "Yeni", "Lira", "Bosphor", "Kaya", "Ege", "Toros"],
        "core": ["Sanayi", "Enerji", "Makina", "Ticaret", "Demir", "Yapi", "Tek", "Liman"],
        "suffix": ["AS", "Holding", "Group", "Industries", "Systems", "Works"],
    },
    "arabian": {
        "prefix": ["Azar", "Safa", "Najm", "Desert", "Falcon", "Zinar", "Oasis", "Gulf"],
        "core": ["Energy", "Sands", "Pearl", "Capital", "Harbor", "Petro", "Trade", "Works"],
        "suffix": ["Holding", "Group", "Industries", "Resources", "Systems", "Corp"],
    },
    "indian": {
        "prefix": ["Indara", "Bharat", "Lotus", "Ganga", "Rupa", "Sundar", "Nova", "Ashoka"],
        "core": ["Tech", "Motors", "Steel", "Foods", "Capital", "Works", "Power", "Bazaar"],
        "suffix": ["Ltd", "Group", "Industries", "Holdings", "Systems", "Works"],
    },
    "chinese": {
        "prefix": ["Han", "Xin", "Dragon", "Jade", "Tian", "Hua", "Long", "Yuan"],
        "core": ["River", "Shan", "Ming", "Guang", "Lotus", "Peak", "Harbor", "Stone"],
        "suffix": ["Holdings", "Group", "Industries", "Resources", "Systems", "Ltd"],
    },
    "japanese": {
        "prefix": ["Shin", "Nichi", "Sakura", "Kiri", "Towa", "Aki", "Mizu", "Hikari"],
        "core": ["Denki", "Kogyo", "Seiko", "Mirai", "Hana", "Kawa", "Takumi", "Nami"],
        "suffix": ["Kabushiki", "Holdings", "Works", "Systems", "Group", "Corp"],
    },
    "korean": {
        "prefix": ["Koryo", "Han", "Seoul", "Daehan", "Mirae", "Blue", "Won", "Haneul"],
        "core": ["Tech", "Heavy", "Motors", "Steel", "Networks", "Foods", "Capital", "Ship"],
        "suffix": ["Co", "Group", "Holdings", "Industries", "Systems", "Works"],
    },
    "brazilian": {
        "prefix": ["Amazon", "Verde", "Rio", "Sul", "Aurora", "Reala", "Nova", "Bahia"],
        "core": ["Energia", "Foods", "Minas", "Banco", "Logistica", "Ferro", "Mercado", "Tech"],
        "suffix": ["SA", "Group", "Industries", "Holding", "Systems", "Works"],
    },
    "canadian": {
        "prefix": ["Maple", "Northern", "Canadia", "Prairie", "Hudson", "Cedar", "Rocky", "Aurora"],
        "core": ["Lake", "Timber", "Mining", "Harbor", "Energy", "Capital", "Rail", "Forge"],
        "suffix": ["Corp", "Group", "Holdings", "Resources", "Industries", "Systems"],
    },
    "australian": {
        "prefix": ["Austral", "Southern", "Outback", "Pacific", "Auroria", "Opal", "Harbor", "Terra"],
        "core": ["Mining", "Energy", "Foods", "Logistics", "Iron", "Capital", "Works", "Ridge"],
        "suffix": ["Ltd", "Group", "Holdings", "Resources", "Industries", "Systems"],
    },
    "south_african": {
        "prefix": ["Savanna", "Cape", "Kora", "Ubuntu", "Goldveld", "Karoo", "Southern", "Rand"],
        "core": ["Mining", "Foods", "Energy", "Capital", "Harbor", "Steel", "Trade", "Works"],
        "suffix": ["Ltd", "Group", "Holdings", "Resources", "Industries", "Systems"],
    },
}

SECTOR_TERMS = {
    "Automobil": ["Motors", "Mobility", "Auto"],
    "Chemie": ["Chem", "Materials", "Polymers"],
    "\u00d6l und Gas": ["Energy", "Petro", "Gas"],
    "Stromerzeuger": ["Power", "Grid", "Utilities"],
    "Maschinenbau": ["Machinery", "Engineering", "Forge"],
    "Telekommunikation": ["Telecom", "Networks", "Signal"],
    "Einzelhandel": ["Retail", "Stores", "Markets"],
    "Konsumg\u00fcter": ["Consumer", "Brands", "Goods"],
    "Finanzen": ["Capital", "Bank", "Finance"],
    "Edelmetallf\u00f6rderer": ["Metals", "Mining", "Gold"],
    "Gesundheit": ["Health", "Medica", "Care"],
    "Technologie": ["Tech", "Digital", "Data"],
    "Immobilien": ["Properties", "Realty", "Estates"],
    "Transport und Logistik": ["Logistics", "Freight", "Cargo"],
    "Verteidigung": ["Defense", "Aerospace", "Secure"],
    "Landwirtschaft": ["Agri", "Harvest", "Foods"],
}


def ensure_company_universe(daten: ModuleType, *, reset: bool = False) -> None:
    if reset or not getattr(daten, "aktien", None):
        daten.aktien = {}
        for country in daten.LAENDER:
            for sector in BRANCHEN:
                for _ in range(START_COMPANIES_PER_COUNTRY_SECTOR):
                    spawn_company(daten, country=country, sector=sector)
        assign_company_specializations(daten)
    fill_company_universe(daten)
    _compact_existing_company_names(daten.aktien.values())
    _align_existing_company_tickers(daten)


def fill_company_universe(daten: ModuleType, target_count: int = TARGET_COMPANY_COUNT) -> list[str]:
    created = []
    while len(daten.aktien) < target_count:
        ticker = spawn_company(daten)
        created.append(ticker)
    return created


def spawn_company(
    daten: ModuleType,
    *,
    country: str | None = None,
    sector: str | None = None,
    ipo_date: datetime | None = None,
) -> str:
    country = country or _least_represented(daten.LAENDER.keys(), [a.get("land") for a in daten.aktien.values()])
    sector = sector or opportunity_sector(daten) or _least_represented(BRANCHEN, [a.get("branche") for a in daten.aktien.values()])
    name = _company_name(country, sector, daten.aktien.values())
    ticker = _unique_ticker(_unavailable_company_tickers(daten), name)
    price = round(random.uniform(18.0, 145.0), 2)
    shares = INITIAL_MARKET_CAP / price
    market_cap = price * shares
    asset = {
        "name": name,
        "land": country,
        "branche": sector,
        "kurs": price,
        "historie": [(price, _date_string(ipo_date or getattr(daten, "datum", None)), "IPO")],
        "news_momentum": 0.0,
        "aenderung": 0.0,
        "aktien_anzahl": shares,
        "market_cap": market_cap,
        "long_interest": market_cap * 0.020,
        "short_interest": market_cap * 0.016,
        "open_interest": market_cap * 0.036,
        "open_interest_history": [],
        "eps": max(0.1, price / random.uniform(14.0, 28.0)),
        "prognose_target": price,
        "rating": random.choice(["A-", "BBB+", "BBB", "BBB-", "BB+"]),
        "cash_reserves": market_cap * random.uniform(0.04, 0.22),
        "debt": market_cap * random.uniform(0.05, 0.45),
        "debt_to_market_cap": 0.0,
        "status": "active",
        "founded": _date_string(ipo_date or getattr(daten, "datum", None)),
    }
    asset["debt_to_market_cap"] = asset["debt"] / max(1.0, market_cap)
    ensure_stock_fundamentals(asset)
    assign_company_specialization(asset, len(daten.aktien))
    daten.aktien[ticker] = asset
    return ticker


def update_company_finances(
    asset: dict,
    *,
    local_rate: float,
    sector_factor: float,
) -> None:
    market_cap = max(1.0, float(asset.get("market_cap", 1.0)))
    cash = float(asset.get("cash_reserves", market_cap * 0.08))
    debt = float(asset.get("debt", market_cap * 0.20))
    free_cash_flow = float(asset.get("free_cash_flow", 0.0))
    monthly_cash_flow = (free_cash_flow / 12.0) * max(0.35, sector_factor)
    interest = debt * max(0.0, local_rate + 0.025) / 12.0
    cash += monthly_cash_flow - interest
    if cash < 0:
        debt += abs(cash) * 1.15
        cash = 0.0
    elif debt > 0 and cash > market_cap * 0.12:
        repayment = min(debt * 0.03, cash - market_cap * 0.12)
        debt -= repayment
        cash -= repayment
    asset["cash_reserves"] = cash
    asset["debt"] = max(0.0, debt)
    asset["debt_to_market_cap"] = asset["debt"] / market_cap


def rating_from_finances(asset: dict, current_index: int) -> int:
    debt_ratio = float(asset.get("debt_to_market_cap", 0.0))
    fcf = float(asset.get("free_cash_flow", 0.0))
    cash = float(asset.get("cash_reserves", 0.0))
    revenue = max(1.0, float(asset.get("revenue", 1.0)))
    if fcf < 0 or cash <= 0:
        current_index += 1
    if debt_ratio > 0.75:
        current_index += 1
    if debt_ratio > 1.15:
        current_index += 1
    if cash > revenue * 0.10 and debt_ratio < 0.35 and fcf > 0:
        current_index -= 1
    return max(0, min(len(RATINGS) - 1, current_index))


def bankrupt_tickers(daten: ModuleType) -> list[str]:
    result = []
    for ticker, asset in daten.aktien.items():
        rating = asset.get("rating", DEFAULT_RATING)
        cash_exhausted = float(asset.get("cash_reserves", 0.0)) <= 0.0
        overlevered = float(asset.get("debt_to_market_cap", 0.0)) >= 1.0
        default_grade = rating_index(rating) >= BANKRUPT_RATING_INDEX or default_probability(rating) >= 0.55
        if cash_exhausted and overlevered and default_grade:
            result.append(ticker)
    return result


def remove_bankrupt_companies(daten: ModuleType, tickers: list[str]) -> None:
    retired = getattr(daten, "retired_company_tickers", set())
    if not isinstance(retired, set):
        retired = set(retired)
    for ticker in tickers:
        daten.aktien.pop(ticker, None)
        daten.depot.pop(ticker, None)
        daten.perpetuals = {
            pos_id: pos for pos_id, pos in daten.perpetuals.items() if pos.get("ticker") != ticker
        }
        daten.anleihen = [bond for bond in daten.anleihen if bond.get("ticker") != ticker]
        retired.add(str(ticker))
    daten.retired_company_tickers = retired


def _company_name(country: str, sector: str, existing_assets) -> str:
    existing = {str(asset.get("name", "")) for asset in existing_assets}
    style = COUNTRY_STYLES.get(country, "american")
    parts = STYLE_NAME_PARTS.get(style, STYLE_NAME_PARTS["american"])
    terms = SECTOR_TERMS.get(sector, ["Industries"])
    for _ in range(100):
        name = _short_company_name(parts, terms)
        if name not in existing:
            return name
    return f"{random.choice(parts['prefix'])}{random.randint(100, 999)} {random.choice(terms)}"


def _short_company_name(parts: dict[str, list[str]], terms: list[str]) -> str:
    variants = [
        [random.choice(parts["prefix"])],
        [random.choice(parts["core"])],
        [random.choice(parts["prefix"]), random.choice(terms)],
        [random.choice(parts["core"]), random.choice(terms)],
        [random.choice(parts["prefix"]), random.choice(parts["suffix"])],
        [random.choice(parts["core"]), random.choice(parts["suffix"])],
    ]
    return " ".join(random.choice(variants))


def _compact_existing_company_names(existing_assets) -> None:
    used_names: set[str] = set()
    for asset in existing_assets:
        current_name = str(asset.get("name", "")).strip()
        if current_name and len(current_name.split()) <= 2 and current_name not in used_names:
            used_names.add(current_name)
            continue
        country = str(asset.get("land", ""))
        sector = str(asset.get("branche", ""))
        asset["name"] = _company_name(country, sector, [{"name": name} for name in used_names])
        used_names.add(str(asset["name"]))


def _align_existing_company_tickers(daten: ModuleType) -> None:
    renamed: dict[str, str] = {}
    next_assets = {}
    for old_ticker, asset in list(daten.aktien.items()):
        new_ticker = _unique_ticker(next_assets, str(asset.get("name", "")))
        renamed[str(old_ticker)] = new_ticker
        next_assets[new_ticker] = asset
    daten.aktien = next_assets
    _rewrite_ticker_references(daten, renamed)


def _rewrite_ticker_references(daten: ModuleType, renamed: dict[str, str]) -> None:
    if not renamed:
        return
    daten.depot = {
        renamed.get(str(ticker), str(ticker)): position
        for ticker, position in getattr(daten, "depot", {}).items()
    }
    for position in getattr(daten, "perpetuals", {}).values():
        ticker = str(position.get("ticker", ""))
        if ticker in renamed:
            position["ticker"] = renamed[ticker]
    for bond in getattr(daten, "anleihen", []):
        ticker = str(bond.get("ticker", ""))
        if ticker in renamed:
            bond["ticker"] = renamed[ticker]


def _unavailable_company_tickers(daten: ModuleType) -> dict[str, object]:
    unavailable = {str(ticker): True for ticker in getattr(daten, "aktien", {})}
    retired = getattr(daten, "retired_company_tickers", set())
    if isinstance(retired, (set, list, tuple)):
        unavailable.update({str(ticker): True for ticker in retired})
    return unavailable


def _unique_ticker(existing: dict, company_name: str = "") -> str:
    for ticker in _ticker_candidates(company_name):
        if ticker not in existing:
            return ticker
    for _ in range(1000):
        length = random.randint(3, 5)
        ticker = "".join(random.choice(string.ascii_uppercase) for _ in range(length))
        if ticker not in existing:
            return ticker
    return f"X{len(existing):04d}"


def _ticker_candidates(company_name: str) -> list[str]:
    words = [
        "".join(char for char in word.upper() if char in string.ascii_uppercase)
        for word in company_name.split()
    ]
    words = [word for word in words if word]
    if not words:
        return []
    base = words[0]
    candidates = [_fit_ticker(base)]
    if len(words) >= 2:
        second = words[1]
        candidates.extend(
            [
                _fit_ticker(base[0] + second[:4]),
                _fit_ticker(base[:2] + second[:3]),
                _fit_ticker(base[:3] + second[:2]),
                _fit_ticker(base[0] + second[0] + base[1:4]),
            ]
        )
    consonants = "".join(char for char in "".join(words) if char not in "AEIOU")
    candidates.append(_fit_ticker(consonants or "".join(words)))
    unique = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def _fit_ticker(value: str) -> str:
    clean = "".join(char for char in value.upper() if char in string.ascii_uppercase)
    if len(clean) >= 3:
        return clean[:5]
    return (clean + "X" * 3)[:3]


def _least_represented(candidates, existing_values) -> str:
    counts = Counter(existing_values)
    return min(list(candidates), key=lambda value: (counts.get(value, 0), random.random()))


def _date_string(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return "01.01.1990"
