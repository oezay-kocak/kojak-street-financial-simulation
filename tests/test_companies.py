from __future__ import annotations

from types import SimpleNamespace

from kojakstreet.core.companies import (
    BRANCHEN,
    INITIAL_MARKET_CAP,
    TARGET_COMPANY_COUNT,
    _unique_ticker,
    bankrupt_tickers,
    ensure_company_universe,
    fill_company_universe,
    remove_bankrupt_companies,
)
from kojakstreet.core.countries import COUNTRY_SYMBOLS


def test_company_universe_generates_dynamic_public_companies() -> None:
    daten = _minimal_daten()

    ensure_company_universe(daten, reset=True)

    assert len(daten.aktien) == TARGET_COMPANY_COUNT
    assert "Landwirtschaft" in BRANCHEN
    assert all(ticker.isupper() and 3 <= len(ticker) <= 5 for ticker in daten.aktien)
    assert all(len(asset["name"].split()) <= 2 for asset in daten.aktien.values())
    assert all(abs(asset["market_cap"] - INITIAL_MARKET_CAP) < 0.01 for asset in daten.aktien.values())
    assert all("cash_reserves" in asset and "debt" in asset for asset in daten.aktien.values())


def test_company_tickers_are_derived_from_short_company_names() -> None:
    assert _unique_ticker({}, "North") == "NORTH"
    assert _unique_ticker({"NORTH": {}}, "North") == "NRTH"
    assert _unique_ticker({}, "North Tech") == "NORTH"
    assert _unique_ticker({"NORTH": {}}, "North Tech") == "NTECH"


def test_bankrupt_company_is_removed_and_replaced() -> None:
    daten = _minimal_daten()
    ensure_company_universe(daten, reset=True)
    ticker = next(iter(daten.aktien))
    daten.aktien[ticker]["cash_reserves"] = 0.0
    daten.aktien[ticker]["debt_to_market_cap"] = 1.4
    daten.aktien[ticker]["rating"] = "CC"
    daten.depot[ticker] = {"stueck": 3.0, "kaufkurs": 100.0}

    failed = bankrupt_tickers(daten)
    remove_bankrupt_companies(daten, failed)
    replacements = fill_company_universe(daten)

    assert failed == [ticker]
    assert ticker not in daten.aktien
    assert ticker not in daten.depot
    assert ticker in daten.retired_company_tickers
    assert len(replacements) == 1
    assert len(daten.aktien) == TARGET_COMPANY_COUNT


def _minimal_daten() -> SimpleNamespace:
    return SimpleNamespace(
        LAENDER=dict(COUNTRY_SYMBOLS),
        aktien={},
        depot={},
        perpetuals={},
        anleihen=[],
    )
