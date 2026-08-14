"""Stable internal label codes with backward-compatible display labels."""

from __future__ import annotations

from typing import Any


SECTOR_CODES: dict[str, str] = {
    "Automobil": "AUTOMOTIVE",
    "Chemie": "CHEMICALS",
    "Öl und Gas": "OIL_GAS",
    "Ã–l und Gas": "OIL_GAS",
    "Ãƒâ€“l und Gas": "OIL_GAS",
    "Stromerzeuger": "POWER_UTILITIES",
    "Maschinenbau": "INDUSTRIAL_MACHINERY",
    "Telekommunikation": "TELECOM",
    "Einzelhandel": "RETAIL",
    "Konsumgüter": "CONSUMER_GOODS",
    "KonsumgÃ¼ter": "CONSUMER_GOODS",
    "Finanzen": "FINANCIALS",
    "Edelmetallförderer": "PRECIOUS_METALS_MINING",
    "EdelmetallfÃ¶rderer": "PRECIOUS_METALS_MINING",
    "Gesundheit": "HEALTHCARE",
    "Technologie": "TECHNOLOGY",
    "Immobilien": "REAL_ESTATE",
    "Transport und Logistik": "TRANSPORT_LOGISTICS",
    "Verteidigung": "DEFENSE",
    "Landwirtschaft": "AGRICULTURE",
}

COMMODITY_GROUP_CODES: dict[str, str] = {
    "Energieträger": "ENERGY_COMMODITIES",
    "EnergietrÃ¤ger": "ENERGY_COMMODITIES",
    "Industriemetalle und Mineralische Rohstoffe": "INDUSTRIAL_METALS",
    "Edel- und Spezialmetalle": "PRECIOUS_SPECIALTY_METALS",
    "Seltene Erden": "RARE_EARTHS",
    "Landwirtschaftliche Primärgüter": "AGRICULTURAL_PRIMARY",
    "Landwirtschaftliche PrimÃ¤rgÃ¼ter": "AGRICULTURAL_PRIMARY",
    "Tierische Güter": "ANIMAL_PRODUCTS",
    "Tierische GÃ¼ter": "ANIMAL_PRODUCTS",
}


def stable_label_code(value: object, *, category: str = "generic") -> str:
    text = str(value or "")
    if category == "sector":
        return SECTOR_CODES.get(text, _fallback_code(text))
    if category == "commodity_group":
        return COMMODITY_GROUP_CODES.get(text, _fallback_code(text))
    return _fallback_code(text)


def attach_stable_label_codes(daten: Any) -> None:
    for asset in getattr(daten, "aktien", {}).values():
        asset["sector_code"] = stable_label_code(asset.get("branche", ""), category="sector")
    for asset in getattr(daten, "rohstoffe", {}).values():
        asset["group_code"] = stable_label_code(asset.get("kategorie", ""), category="commodity_group")
    for asset in getattr(daten, "fonds", {}).values():
        asset["group_code"] = stable_label_code(asset.get("branche", ""), category="sector")
    for asset in getattr(daten, "indizes", {}).values():
        if asset.get("branche"):
            asset["sector_code"] = stable_label_code(asset.get("branche", ""), category="sector")


def _fallback_code(value: str) -> str:
    cleaned = []
    replacements = {
        "Ä": "AE",
        "Ö": "OE",
        "Ü": "UE",
        "ä": "AE",
        "ö": "OE",
        "ü": "UE",
        "ß": "SS",
    }
    for char in value:
        replacement = replacements.get(char, char)
        for item in replacement.upper():
            cleaned.append(item if item.isalnum() else "_")
    code = "".join(cleaned).strip("_")
    while "__" in code:
        code = code.replace("__", "_")
    return code or "UNKNOWN"
