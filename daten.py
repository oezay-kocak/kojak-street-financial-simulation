# DATEI: daten.py START
import os
import sys
from datetime import datetime

from kojakstreet.core.companies import BRANCHEN as GENERATED_BRANCHEN
from kojakstreet.core.companies import ensure_company_universe
from kojakstreet.core.countries import COUNTRY_SYMBOLS, RESERVE_CURRENCY, RESERVE_CURRENCY_SYMBOL
from kojakstreet.core.cryptos import ensure_crypto_universe
from kojakstreet.core.expectations import ensure_macro_expectations
from kojakstreet.core.financial_products import ensure_financial_product_universe
from kojakstreet.core.fiscal import ensure_country_financials
from kojakstreet.core.funds import ensure_fund_universe
from kojakstreet.core.heterogeneous_start import initialization_roots
from kojakstreet.core.indices import ensure_index_universe
from kojakstreet.core.label_codes import attach_stable_label_codes
from kojakstreet.core.market_regime import update_market_regime
from kojakstreet.core.production_chains import (
    COMMODITY_GROUPS,
    ensure_population,
    ensure_processed_products,
    update_production_chain,
)
from kojakstreet.core.workforce import initialize as initialize_workforce

LAENDER = dict(COUNTRY_SYMBOLS)
WAEHRUNGEN = {**LAENDER, RESERVE_CURRENCY: RESERVE_CURRENCY_SYMBOL}
RATINGS = [
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D",
]

BRANCHEN = GENERATED_BRANCHEN


ROHSTOFFE_KAT = COMMODITY_GROUPS

datum = datetime(1990, 1, 1)  # noqa: DTZ001 - legacy simulation dates are deliberately naive.
bargeld = 0.0
kredite = {currency: 0.0 for currency in WAEHRUNGEN}
depot = {}
perpetuals = {}
anleihen = []
spiel_pausiert = False
SPIEL_AKTIV = True
turbo_modus = True
intervall = 2500
aktives_event = None
NEWS_SPEICHER = []
CHART_REFFS = {}
anzeige_waehrung = RESERVE_CURRENCY
waehrungen_staerke = {currency: 1.0 for currency in WAEHRUNGEN}
forex_depot = {currency: 0.0 for currency in WAEHRUNGEN}
forex_depot[RESERVE_CURRENCY] = 25_000.0


def _resource_path(filename):
    candidates = [os.path.join(os.getcwd(), filename)]
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), filename))
        candidates.append(os.path.join(os.path.dirname(sys.executable), filename))
    candidates.append(os.path.join(os.path.dirname(__file__), filename))
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return filename


aktien = {}
_initial_roots = initialization_roots.get()
ensure_company_universe(
    sys.modules[__name__], reset=True,
    initial_caps=_initial_roots.company_caps if _initial_roots is not None else None,
)

rohstoffe = {}
for kat, items in ROHSTOFFE_KAT.items():
    for name, ticker in items.items():
        rohstoffe[ticker] = {
            "name": name,
            "kurs": 100.0,
            "historie": [],
            "news_momentum": 0.0,
            "aenderung": 0.0,
            "kategorie": kat,
            "market_cap": 1_000_000_000.0,
            "long_interest": 20_000_000.0,
            "short_interest": 16_000_000.0,
            "open_interest": 36_000_000.0,
            "open_interest_history": [],
            "prognose_target": 100.0,
            "foerder_menge": 0.0,
        }

processed_products = {}
ensure_processed_products(sys.modules[__name__])

kryptos = {}
ensure_crypto_universe(sys.modules[__name__], reset=True)

fonds = {}
indizes = {}
derivatives = {}
ensure_index_universe(sys.modules[__name__])

makro = {}
for country in LAENDER:
    makro[country] = {
        "bip_abs": _initial_roots.gdp[country] if _initial_roots is not None else 5000.0,
        "bip_prozent": 0.010,
        "zins": 0.035,
        "inflation": 0.010,
        "arbeitslosigkeit": 0.060,
        "balance_sheet": 1000.0,
        "rating": "BBB",
        "bevoelkerung": float(_initial_roots.population[country]) if _initial_roots is not None else 20_000_000.0,
        "population_growth": 0.0,
    }
ensure_population(sys.modules[__name__])
ensure_country_financials(sys.modules[__name__])
ensure_macro_expectations(sys.modules[__name__])

FOREX_PAARE_HISTORIE = {}
for base in WAEHRUNGEN:
    for quote in WAEHRUNGEN:
        if base != quote:
            FOREX_PAARE_HISTORIE[f"{base}/{quote}"] = []

LETZTER_ZINS_TAG = None
LETZTER_REPORT_MONAT = -1

MAKRO_HISTORIE = {}
for country in LAENDER:
    MAKRO_HISTORIE[f"{country}_ZINS"] = [(0.035, "01.01.1990", "")]
    MAKRO_HISTORIE[f"{country}_BIP"] = [(makro[country]["bip_abs"], "01.01.1990", "")]
    MAKRO_HISTORIE[f"{country}_INF"] = [(0.010, "01.01.1990", "")]
    MAKRO_HISTORIE[f"{country}_ALO"] = [(0.060, "01.01.1990", "")]
    MAKRO_HISTORIE[f"{country}_BS"] = [(1000.0, "01.01.1990", "")]
    MAKRO_HISTORIE[f"{country}_DEBT_GDP"] = [(makro[country]["debt_to_gdp"], "01.01.1990", "")]
    MAKRO_HISTORIE[f"{country}_CREDIT"] = [(makro[country]["credit_growth"], "01.01.1990", "")]
    MAKRO_HISTORIE[f"{country}_DEFICIT"] = [(makro[country]["fiscal_deficit"], "01.01.1990", "")]

DEPOT_VERMOEGEN_HISTORIE = [(25_000.0, "01.01.1990")]
gli_index = 15420.0
realisierte_guv_historie = []
GLI_HISTORIE = [15420.0]

global_macro = {
    "global_m2": 100000.0,
    "central_bank_balance_sheets": 5000.0,
    "rrp": 7500.0,
    "tga": 4500.0,
    "avg_3y_yield": 0.038,
    "avg_5y_yield": 0.040,
    "avg_10y_yield": 0.047,
    "yield_curve_3y10y": 0.009,
    "global_cpi": 0.010,
    "global_gdp_growth": 0.010,
    "global_unemployment": 0.060,
    "expected_global_growth": 0.010,
    "expected_global_cpi": 0.010,
    "expected_avg_policy_rate": 0.035,
    "macro_surprise_index": 0.0,
    "vix": 18.0,
    "net_liquidity": 93000.0,
}
GLOBAL_MACRO_HISTORIE = {
    key: [(value, "01.01.1990", "")]
    for key, value in global_macro.items()
}

ensure_fund_universe(sys.modules[__name__], reset=True)
ensure_financial_product_universe(sys.modules[__name__], reset=True)
attach_stable_label_codes(sys.modules[__name__])
update_market_regime(sys.modules[__name__])
for asset_group in (aktien, rohstoffe, kryptos, fonds, indizes, derivatives):
    for asset in asset_group.values():
        asset["historie"] = []
update_production_chain(sys.modules[__name__], advance_population=False)
initialize_workforce(sys.modules[__name__])
del _initial_roots
# DATEI: daten.py ENDE
