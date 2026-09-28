# DATEI: speicher.py START
import json
import os
import pickle
from kojakstreet.core.checkpoints import atomic_write, capture, decode, encode, restore
from collections.abc import Mapping
from datetime import UTC, datetime

import daten
from kojakstreet.core.companies import ensure_company_universe
from kojakstreet.core.countries import RESERVE_CURRENCY
from kojakstreet.core.cryptos import ensure_crypto_fundamentals, ensure_crypto_universe
from kojakstreet.core.financial_products import ensure_financial_product_universe
from kojakstreet.core.funds import ensure_fund_universe
from kojakstreet.core.indices import ensure_index_universe
from kojakstreet.core.production_chains import (
    ensure_country_economies,
    ensure_population,
    ensure_processed_products,
)
from kojakstreet.core.save_migrations import CURRENT_SAVE_VERSION, finalize_loaded_state, migrate_save_payload

SPEICHER_DATEI = "spielstand.dat"
SAVE_VERSION = CURRENT_SAVE_VERSION


def _layout():
    if getattr(daten, "PYSIDE_RUNTIME", False):
        return None
    try:
        import layout

        return layout
    except Exception:
        return None


def _show_status(text, color):
    ui_layout = _layout()
    if ui_layout is not None:
        ui_layout.zeige_status_meldung(text, color)


def _show_warning(title, message):
    try:
        import tkinter.messagebox as mb

        mb.showwarning(title, message)
    except Exception:
        print(f"{title}: {message}")


def _show_error(title, message):
    try:
        import tkinter.messagebox as mb

        mb.showerror(title, message)
    except Exception:
        print(f"{title}: {message}")

def spiel_speichern(path=None, *, analytics=None):
    payload = _save_payload()
    if analytics is not None:
        payload["analytics_session"] = analytics
    atomic_write(path or SPEICHER_DATEI, payload)
    _show_status(" SAVE GAME WRITTEN SUCCESSFULLY!", "#00ffaa")


def _save_payload():
    return capture(daten)


def _json_ready(value):
    if isinstance(value, datetime):
        return {"__type__": "datetime", "value": value.isoformat()}
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return {"__type__": "tuple", "items": [_json_ready(item) for item in value]}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _from_json_ready(value):
    if isinstance(value, dict):
        if value.get("__type__") == "datetime":
            return datetime.fromisoformat(str(value["value"]))
        if value.get("__type__") == "tuple":
            return tuple(_from_json_ready(item) for item in value.get("items", []))
        return {key: _from_json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_from_json_ready(item) for item in value]
    return value

def spiel_laden(path=None):
    path = path or SPEICHER_DATEI
    if not os.path.exists(path):
        raise FileNotFoundError("No saved game found")
    try:
        load_data = _load_payload(path)
        if "checkpoint" in load_data:
            restore(daten, load_data)
            return load_data
        
        daten.bargeld = load_data["bargeld"]
        daten.forex_depot = load_data["forex_depot"]
        daten.depot = load_data["depot"]
        daten.perpetuals = load_data.get("perpetuals", {})
        daten.kredite = load_data["kredite"]
        daten.anleihen = load_data["anleihen"]
        daten.datum = load_data["datum"]
        daten.aktien = load_data["aktien"]
        daten.rohstoffe = load_data["rohstoffe"]
        daten.processed_products = load_data.get("processed_products", getattr(daten, "processed_products", {}))
        daten.kryptos = load_data["kryptos"]
        daten.fonds = load_data.get("fonds", {})
        daten.derivatives = load_data.get("derivatives", {})
        daten.makro = load_data["makro"]
        daten.indizes = load_data.get("indizes", {})
        daten.waehrungen_staerke = load_data["waehrungen_staerke"]
        daten.FOREX_PAARE_HISTORIE = load_data["FOREX_PAARE_HISTORIE"]
        daten.NEWS_SPEICHER = load_data["NEWS_SPEICHER"]
        daten.LETZTER_REPORT_MONAT = load_data["LETZTER_REPORT_MONAT"]
        
        daten.MAKRO_HISTORIE = load_data.get("MAKRO_HISTORIE", daten.MAKRO_HISTORIE)
        daten.DEPOT_VERMOEGEN_HISTORIE = load_data.get("DEPOT_VERMOEGEN_HISTORIE", daten.DEPOT_VERMOEGEN_HISTORIE)
        daten.anzeige_waehrung = load_data.get("anzeige_waehrung", daten.anzeige_waehrung)
        daten.realisierte_guv_historie = load_data.get("realisierte_guv_historie", [])
        _migrate_country_universe()
        ensure_processed_products(daten)
        ensure_population(daten)
        ensure_country_economies(daten)
        ensure_company_universe(daten)
        if any("task_type" not in asset for asset in daten.kryptos.values()):
            ensure_crypto_universe(daten, reset=True)
        else:
            ensure_crypto_universe(daten)
        for asset in daten.kryptos.values():
            ensure_crypto_fundamentals(asset)
        ensure_index_universe(daten)
        ensure_fund_universe(daten)
        ensure_financial_product_universe(daten)
        finalize_loaded_state(daten)

        ui_layout = _layout()
        if ui_layout is not None:
            if hasattr(ui_layout, 'cb_global_waehrung') and ui_layout.cb_global_waehrung:
                ui_layout.cb_global_waehrung.set(daten.anzeige_waehrung)
            ui_layout.update_ui_graphics()
            ui_layout.zeige_status_meldung(" SAVE GAME LOADED SUCCESSFULLY!", "#00ffaa")
    except Exception as e:
        raise ValueError(f"Could not load save: {e}") from e


class _LegacyDataUnpickler(pickle.Unpickler):
    """Legacy primitives and datetime only; never import arbitrary classes."""
    def find_class(self, module, name):
        if module == "datetime" and name == "datetime":
            return datetime
        raise pickle.UnpicklingError(f"Unsafe legacy pickle global: {module}.{name}")


def _reject_nonfinite(value):
    raise ValueError(f"Non-finite number in save: {value}")


def _load_payload(path):
    try:
        with open(path, encoding="utf-8") as f:
            payload = decode(json.load(f, parse_constant=_reject_nonfinite))
    except (UnicodeDecodeError, json.JSONDecodeError):
        with open(path, "rb") as f:
            payload = _LegacyDataUnpickler(f).load()
    if not isinstance(payload, dict):
        raise ValueError("Save must contain a mapping")
    if int(payload.get("save_version", 1)) > SAVE_VERSION:
        raise ValueError("Save was written by a newer version")
    if "checkpoint" in payload:
        return payload
    return migrate_save_payload(payload)


def _without_runtime_cache(value):
    if isinstance(value, Mapping):
        return {
            key: _without_runtime_cache(item)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [_without_runtime_cache(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_without_runtime_cache(item) for item in value)
    return value


def _migrate_country_universe():
    valid_countries = set(daten.LAENDER)
    valid_currencies = set(daten.WAEHRUNGEN)
    daten.forex_depot = {currency: float(daten.forex_depot.get(currency, 0.0)) for currency in valid_currencies}
    daten.forex_depot[RESERVE_CURRENCY] = max(0.0, daten.forex_depot.get(RESERVE_CURRENCY, 0.0))
    daten.kredite = {currency: float(daten.kredite.get(currency, 0.0)) for currency in valid_currencies}
    daten.waehrungen_staerke = {currency: float(daten.waehrungen_staerke.get(currency, 1.0)) for currency in valid_currencies}
    daten.anzeige_waehrung = daten.anzeige_waehrung if daten.anzeige_waehrung in valid_currencies else RESERVE_CURRENCY
    countries = list(daten.LAENDER)
    for index, asset in enumerate(daten.aktien.values()):
        if asset.get("land") not in valid_countries:
            asset["land"] = countries[index % len(countries)]
    daten.makro = {
        country: dict(daten.makro.get(country, {
            "bip_abs": 5000.0,
            "bip_prozent": 0.010,
            "zins": 0.035,
            "inflation": 0.010,
            "arbeitslosigkeit": 0.060,
            "balance_sheet": 1000.0,
            "rating": "BBB",
            "bevoelkerung": 20_000_000.0,
            "population_growth": 0.0,
        }))
        for country in countries
    }
    next_forex_history = {}
    for base in daten.WAEHRUNGEN:
        for quote in daten.WAEHRUNGEN:
            if base == quote:
                continue
            pair = f"{base}/{quote}"
            next_forex_history[pair] = list(daten.FOREX_PAARE_HISTORIE.get(pair, []))
    for currency in daten.WAEHRUNGEN:
        pair = f"BTC/{currency}"
        next_forex_history[pair] = list(daten.FOREX_PAARE_HISTORIE.get(pair, []))
    daten.FOREX_PAARE_HISTORIE = next_forex_history
    daten.MAKRO_HISTORIE = {
        key: list(history)
        for key, history in daten.MAKRO_HISTORIE.items()
        if any(key.startswith(f"{country}_") for country in countries)
    }
    for country in countries:
        daten.MAKRO_HISTORIE.setdefault(f"{country}_ZINS", [(0.035, "01.01.1990", "")])
        daten.MAKRO_HISTORIE.setdefault(f"{country}_BIP", [(5000.0, "01.01.1990", "")])
        daten.MAKRO_HISTORIE.setdefault(f"{country}_INF", [(0.010, "01.01.1990", "")])
        daten.MAKRO_HISTORIE.setdefault(f"{country}_ALO", [(0.060, "01.01.1990", "")])
        daten.MAKRO_HISTORIE.setdefault(f"{country}_BS", [(1000.0, "01.01.1990", "")])
    if any("fund_type" not in fund for fund in getattr(daten, "fonds", {}).values()):
        daten.fonds = {}
    daten.indizes = {}

# DATEI: speicher.py ENDE
