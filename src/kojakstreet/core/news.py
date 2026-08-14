"""News feed normalization, translation and impact classification."""

from __future__ import annotations

from dataclasses import dataclass

from kojakstreet.core.state import GameState


@dataclass(slots=True)
class NewsItem:
    date: str
    topic: str
    category: str
    headline: str
    body: str
    priority: str
    impact: str
    search_text: str


def build_news_items(state: GameState) -> list[NewsItem]:
    items = []
    for raw_item in state.news:
        if len(raw_item) < 3:
            continue
        date, body, category = raw_item
        body_text = translate_news_text(str(body).strip())
        category_text = normalize_category(str(category))
        headline = body_text.splitlines()[0].strip() if body_text else "News"
        topic = classify_topic(body_text, category_text)
        priority = classify_priority(body_text, category_text)
        impact = classify_impact(body_text, category_text)
        search_text = " ".join([str(date), topic, category_text, headline, body_text, priority, impact]).lower()
        items.append(
            NewsItem(
                date=str(date),
                topic=topic,
                category=category_text,
                headline=headline,
                body=body_text,
                priority=priority,
                impact=impact,
                search_text=search_text,
            )
        )
    return items


def normalize_category(category: str) -> str:
    mapping = {
        "ROT": "Negative",
        "NEGATIVE": "Negative",
        "CRASH": "Negative",
        "GRUEN": "Positive",
        "POSITIVE": "Positive",
        "KAUF": "Positive",
        "ZENTRALBANK": "Central Bank",
        "MAKRO": "Macro",
        "GLOBAL": "Macro",
        "FED": "Central Bank",
        "WEISS": "Neutral",
    }
    return mapping.get(category.upper(), category.title() if category else "Neutral")


def classify_topic(body: str, category: str) -> str:
    text = body.upper()
    if any(keyword in text for keyword in ["INSOLVENT", "DEFAULTED", "LIQUIDATION", "MARGIN CALL"]):
        return "Solvency"
    if any(keyword in text for keyword in ["IPO", "NEW COMPANY", "LISTED"]):
        return "IPO"
    if any(keyword in text for keyword in ["CENTRAL BANK", "POLICY RATE", "BALANCE SHEET", "QE", "QT"]):
        return "Policy"
    if any(keyword in text for keyword in ["IMPORT", "EXPORT", "TRADE", "PARTNER"]):
        return "Trade"
    if any(keyword in text for keyword in ["COUNTRY", "REGION", "INFLATION", "GDP", "UNEMP."]):
        return "Country"
    if any(keyword in text for keyword in ["CAPACITY", "BOTTLENECK", "SHORTAGE", "SUPPLY"]):
        return "Capacity"
    if any(keyword in text for keyword in ["SECTOR", "BRANCHE", "INDUSTRY"]):
        return "Sector"
    if category == "Central Bank":
        return "Policy"
    if category == "Macro":
        return "Country"
    if category in {"Positive", "Negative"}:
        return "Market"
    return "General"


def classify_priority(body: str, category: str) -> str:
    text = body.upper()
    if any(keyword in text for keyword in ["MARGIN CALL", "LIQUIDATION", "DEFAULTED", "INSOLVENT"]):
        return "Critical"
    if any(keyword in text for keyword in ["BREAKING NEWS", "ALERT", "CRASH", "GENERAL STRIKE"]):
        return "High"
    if any(keyword in text for keyword in ["SHORTAGE", "BOTTLENECK", "SUPPLY SHOCK", "GEOPOLITICAL"]):
        return "High"
    if category in {"Negative", "Central Bank"}:
        return "Medium"
    return "Normal"


def classify_impact(body: str, category: str) -> str:
    text = body.upper()
    if category == "Positive":
        return "Bullish"
    if category == "Negative":
        return "Bearish"
    if category == "Central Bank":
        if any(keyword in text for keyword in ["RAISED", "QT"]):
            return "Tightening"
        if any(keyword in text for keyword in ["CUT", "QE"]):
            return "Easing"
        return "Policy"
    if any(keyword in text for keyword in ["STABILIZING", "RECOVERY", "RECOVERED"]):
        return "Stabilizing"
    return "Informational"


def translate_news_text(text: str) -> str:
    translated = text.strip()
    translated = _translate_exact(translated)
    for source, target in _NEWS_REPLACEMENTS.items():
        translated = translated.replace(source, target)
    translated = translated.replace("Policy rate UNCHANGED to", "Policy rate UNCHANGED at")
    translated = translated.replace("  ", " ")
    return translated


def _translate_exact(text: str) -> str:
    exact = {
        "MARGIN CALL: Dein Nettovermoegen ist aufgebraucht.": (
            "MARGIN CALL: Your net worth is depleted."
        ),
        "MARGIN CALL: Dein Nettovermögen ist aufgebraucht.": (
            "MARGIN CALL: Your net worth is depleted."
        ),
    }
    return exact.get(text, text)


_NEWS_REPLACEMENTS = {
    "ACHTUNG - EILMELDUNG": "ALERT - BREAKING NEWS",
    "ZENTRALBANK-ENTSCHEID & NOTENBANK-BILANZEN": (
        "CENTRAL BANK DECISION & BALANCE SHEETS"
    ),
    "ZENTRALBANK-ENTSCHEID": "CENTRAL BANK DECISION",
    "MONATLICHER WIRTSCHAFTSBERICHT": "MONTHLY ECONOMIC REPORT",
    "KUPON-AUSZAHLUNG": "COUPON PAYMENT",
    "STAATSANLEIHE": "GOVERNMENT BOND",
    "AKTIENANLEIHE": "CORPORATE BOND",
    "RATING-AUSFALL": "RATING DEFAULT",
    "Leitzins": "Policy rate",
    "ERHOEHT": "RAISED",
    "ERHÖHT": "RAISED",
    "ERHÃ–HT": "RAISED",
    "GESENKT": "CUT",
    "KONSTANT": "UNCHANGED",
    " auf ": " to ",
    " bei ": " at ",
    "Bilanz": "balance sheet",
    "ausgeweitet": "expanded",
    "verkürzt": "reduced",
    "verkÃ¼rzt": "reduced",
    "Mrd.": "B",
    "BIP": "GDP",
    "Inf": "CPI",
    "Alo": "Unemp.",
    "GENERALSTREIK & UNRUHEN": "GENERAL STRIKE & CIVIL UNREST",
    "GENERALSTREIK": "GENERAL STRIKE",
    "GEOPOLITISCHER KONFLIKT": "GEOPOLITICAL CONFLICT",
    "LIEFERENGPASS & EMBARGO": "SUPPLY SHORTAGE & EMBARGO",
    "Massive Generalstreiks legen Infrastruktur und Fabriken": (
        "Massive general strikes paralyze infrastructure and factories"
    ),
    " lahm": "",
    "Schwere geopolitische Spannungen zwischen": "Severe geopolitical tensions between",
    "Ein Lieferengpass erschuettert": "A supply shortage disrupts",
    "geschlossen": "closed",
    "Das Sonderereignis": "The special event",
    "ist beendet": "has ended",
    "für": "for",
    "fÃ¼r": "for",
    "erhalten": "received",
    "Halbjährlicher Zins": "Semiannual interest",
    "HalbjÃ¤hrlicher Zins": "Semiannual interest",
    "nach Laufzeitende zu 100% zurückgezahlt": "matured and was repaid at 100%",
    "nach Laufzeitende zu 100% zurÃ¼ckgezahlt": "matured and was repaid at 100%",
    "ist insolvent": "has defaulted",
    "Der Nominalwert von": "The principal amount of",
    "ist komplett verloren": "was lost completely",
    "erfolgreich beendet": "matured successfully",
    "Nominalwert von": "Principal amount of",
    "zu 100% erstattet": "was repaid at 100%",
}
