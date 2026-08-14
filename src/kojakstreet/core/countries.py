"""Fictional country and currency registry used by the simulation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CountryDefinition:
    name: str
    currency_name: str
    symbol: str
    code: str
    style: str


COUNTRIES: tuple[CountryDefinition, ...] = (
    CountryDefinition("Ameron", "Dollar", "$", "DOL", "american"),
    CountryDefinition("Albionia", "Crown", "\u212d", "CRN", "british"),
    CountryDefinition("Ardonia", "Arden", "\u20b3", "ARD", "german"),
    CountryDefinition("Valoria", "Valoir", "\u20b6", "VAL", "french"),
    CountryDefinition("Romara", "Venezio", "\u0474", "VEN", "italian"),
    CountryDefinition("Soleria", "Sol", "\u20b7", "SOLR", "spanish"),
    CountryDefinition("Nordmark", "Krone", "\u16d5", "KRN", "nordic"),
    CountryDefinition("Sarmatia", "Zorin", "\ua762", "ZOR", "polish"),
    CountryDefinition("Danubria", "Floren", "\u0192", "FLR", "hungarian"),
    CountryDefinition("Carpathia", "Korin", "\u20ad", "KOR", "slavic"),
    CountryDefinition("Anatria", "Lira", "\u20ba", "LIR", "turkish"),
    CountryDefinition("Azaria", "Zinar", "\u01b5", "ZIN", "arabian"),
    CountryDefinition("Indara", "Rupa", "\u20b9", "RUP", "indian"),
    CountryDefinition("Hanxia", "Yuan", "\u5143", "YUA", "chinese"),
    CountryDefinition("Pacifica", "Yenka", "\u00a5", "YKA", "japanese"),
    CountryDefinition("Koryo", "Won", "\u20a9", "WON", "korean"),
    CountryDefinition("Amazonia", "Reala", "\u211c", "REA", "brazilian"),
    CountryDefinition("Canadia", "Maple", "\u2133", "MAP", "canadian"),
    CountryDefinition("Auroria", "Austral", "\u2c6d", "AUS", "australian"),
    CountryDefinition("Savanna", "Kora", "\ua740", "KRA", "south_african"),
)

RESERVE_CURRENCY = "GD"
RESERVE_CURRENCY_CODE = "GLD"
RESERVE_CURRENCY_SYMBOL = "GD"

COUNTRY_SYMBOLS = {country.name: country.symbol for country in COUNTRIES}
CURRENCY_CODES = {country.name: country.code for country in COUNTRIES}
CURRENCY_NAMES = {country.name: country.currency_name for country in COUNTRIES}
COUNTRY_STYLES = {country.name: country.style for country in COUNTRIES}

