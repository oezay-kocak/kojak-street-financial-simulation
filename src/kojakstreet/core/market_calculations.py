# DATEI: markt.py START
import math
import random
from dataclasses import dataclass

import numpy as np

import daten
from kojakstreet.core.commodities import commodity_price_signal
from kojakstreet.core.cryptos import crypto_price_signal
from kojakstreet.core.fundamentals import consume_fundamental_repricing, ema_values
from kojakstreet.core.funds import update_funds
from kojakstreet.core.global_macro import global_market_signals
from kojakstreet.core.ohlc import append_ohlc_from_move, normalize_commodity_supply_key
from kojakstreet.core.psychology import (
    daily_asset_psychology_values,
    market_psychology_bias,
    update_market_psychology,
)

ALL_SECTORS = "All Sectors"


@dataclass(frozen=True, slots=True)
class MarketAssetRuntime:
    ticker: str
    asset: dict
    land: str = ""
    branch: str = ""
    shares: float = 10_000_000.0
    is_monetary_metal: bool = False


def get_gd_diff(historie, tage):
    saubere_zahlen = []
    for x in historie:
        try:
            if isinstance(x, (tuple, list)): 
                saubere_zahlen.append(float(x[0]))
            else: 
                saubere_zahlen.append(float(x))
        except (TypeError, ValueError):
            continue
    if not saubere_zahlen: return 0.0
    aktueller_kurs = saubere_zahlen[-1]
    mittelwert = float(np.mean(saubere_zahlen[-tage:])) if len(saubere_zahlen) >= tage else float(np.mean(saubere_zahlen))
    return (aktueller_kurs - mittelwert) / mittelwert if mittelwert != 0.0 else 0.0

def update_markt_kurse(daten_module=None):
    daten_module = daten if daten_module is None else daten_module
    zeit_str = daten_module.datum.strftime("%d.%m.%Y")
    runtime_assets = _market_runtime_assets(daten_module)
    gli = getattr(daten_module, "gli_index", 15420.0)
    gli_faktor = math.sqrt(gli / 15420.0)
    
    countries = tuple(daten_module.LAENDER)
    macro_by_country = daten_module.makro
    macro_values = [macro_by_country.get(country, {}) for country in countries]
    welt_zins = sum(float(macro.get("zins", 0.04)) for macro in macro_values) / max(1, len(countries))
    average_inflation = sum(float(m.get("inflation", 0.01)) for m in daten_module.makro.values()) / max(1, len(daten_module.makro))
    global_signals = global_market_signals(daten_module)
    liquidity_impulse = global_signals["liquidity_impulse"]
    risk_pressure = global_signals["risk_pressure"]
    curve_pressure = max(0.0, -global_signals["yield_curve"])
    global_expected_growth = global_signals["expected_growth"]
    global_macro_surprise = global_signals["macro_surprise"]
    psychology = update_market_psychology(daten_module)
    commodity_macro_bias = market_psychology_bias("Commodity", psychology)
    stock_macro_bias = market_psychology_bias("Stock", psychology)
    crypto_macro_bias = market_psychology_bias("Crypto", psychology)
    
    # 1. FIAT-WÄHRUNGSSTÄRKEN BERECHNEN (KAUFKRAFT)
    for land in countries:
        m = macro_by_country.get(land, {"zins": 0.04, "bip_prozent": 0.01})
        forex_stabilisator = (1.0 - daten_module.waehrungen_staerke[land]) * 0.004
        expected_rate = float(m.get("expected_rate", m["zins"]))
        expected_growth = float(m.get("expected_growth", m["bip_prozent"]))
        surprise = float(m.get("macro_surprise_momentum", 0.0))
        real_rate_edge = (expected_rate - float(m.get("expected_inflation", m.get("inflation", 0.02)))) - (welt_zins - average_inflation)
        zins_impuls = real_rate_edge * 0.014
        bip_impuls = (expected_growth + surprise) * 0.006
        
        krisen_malus = -0.0065 if (daten_module.aktives_event and land in daten_module.aktives_event["laender"]) else 0.0
        stress = abs(m["zins"] - welt_zins) + abs(m["bip_prozent"]) + abs(m.get("inflation", 0.0) - 0.02)
        rauschen = random.uniform(-0.0016, 0.0016) * (1.0 + min(4.0, stress * 18.0))
        
        daten_module.waehrungen_staerke[land] = max(0.2, min(5.0, daten_module.waehrungen_staerke[land] * (1.0 + zins_impuls + bip_impuls + krisen_malus + rauschen + forex_stabilisator)))

    # TÄGLICHE HISTORIE FÜR ALLE 30 HANDELSPAARE SCHREIBEN (Inkl. GD)
    gold_basis_preis = daten_module.rohstoffe["XAU"]["kurs"]
    gd_strength = gold_basis_preis / 100.0  # GD skaliert mit dem Goldpreis

    for l1 in daten_module.WAEHRUNGEN:
        for l2 in daten_module.WAEHRUNGEN:
            if l1 != l2:
                paar_key = f"{l1}/{l2}"
                if paar_key not in daten_module.FOREX_PAARE_HISTORIE: 
                    daten_module.FOREX_PAARE_HISTORIE[paar_key] = []
                
                # Stärke abrufen (GD bekommt seinen Sonderwert)
                s1 = daten_module.waehrungen_staerke.get(l1, 1.0) if l1 != "GD" else gd_strength
                s2 = daten_module.waehrungen_staerke.get(l2, 1.0) if l2 != "GD" else gd_strength
                
                # Kurs berechnen
                wechselkurs = s1 / s2 if s2 > 0 else 1.0
                daten_module.FOREX_PAARE_HISTORIE[paar_key].append((wechselkurs, zeit_str, ""))
                if len(daten_module.FOREX_PAARE_HISTORIE[paar_key]) > 520:
                    del daten_module.FOREX_PAARE_HISTORIE[paar_key][:-520]

    # 2. ROHSTOFFE DIREKT IN GOLD-DINAR (GD) SCHWANKEN LASSEN
    for runtime in runtime_assets["commodities"]:
        t = runtime.ticker
        d = runtime.asset
        diff_ema20 = _asset_ema_diff(d, 20)
        chance = 0.50 - (diff_ema20 * 0.30) + d.get("news_momentum", 0.0)
        chance += float(d.get("fund_flow_pressure", 0.0))
        commodity_signal = commodity_price_signal(d)
        chance += commodity_signal
        
        foerder_effekt = -normalize_commodity_supply_key(d) * 0.08
        chance += foerder_effekt
        
        gli_effekt = 0.0045 * gli_faktor if runtime.is_monetary_metal else 0.0015 * gli_faktor
        inflation_hedge = average_inflation * 0.5 if runtime.is_monetary_metal else 0.0
        
        alt = d["kurs"]
        psych_signal, psych_volatility, *_psych_state = daily_asset_psychology_values(
            d,
            "Commodity",
            psychology,
            commodity_macro_bias,
            assume_ready=True,
        )
        anchor_signal = _commodity_price_anchor_signal(d)
        final_chance = chance + gli_effekt + inflation_hedge + psych_signal + anchor_signal
        richtung = 1 if random.random() < _direction_probability(final_chance) else -1
        d["news_momentum"] = d.get("news_momentum", 0.0) * 0.80
        d["fund_flow_pressure"] = float(d.get("fund_flow_pressure", 0.0)) * 0.70
        
        event_pressure = _event_pressure(daten_module, None, "Commodity")
        shortage_pressure = (
            max(0.0, float(d.get("demand_change", 0.0)) - float(d.get("production_change", 0.0)))
            + max(0.0, -float(d.get("inventories_change", 0.0)))
        )
        euphoria_score = _tail_score(
            max(0.0, commodity_signal) * 5.0,
            max(0.0, psych_signal) * 9.0,
            max(0.0, anchor_signal) * 4.0,
            max(0.0, inflation_hedge) * 10.0,
            shortage_pressure * 4.0,
            event_pressure,
        )
        stress_score = _tail_score(
            max(0.0, -commodity_signal) * 5.0,
            max(0.0, -psych_signal) * 9.0,
            max(0.0, -anchor_signal) * 4.0,
            event_pressure * 0.55,
        )
        positioning = _update_open_interest(daten_module, t, d, "Commodity", final_chance)
        final_chance += float(positioning["chance_impulse"])
        euphoria_score += max(0.0, float(positioning["squeeze_pressure"])) * 4.0
        stress_score += max(0.0, -float(positioning["squeeze_pressure"])) * 4.0
        shock_pressure = max(0.0, commodity_signal - 0.18) + max(0.0, -float(d.get("inventories_change", 0.0)) - 0.03)
        basis_schwankung = random.uniform(0.0025, 0.014) * (1.0 + min(2.6, shock_pressure * 6.0))
        tages_vola = _open_ended_daily_volatility(
            basis_schwankung,
            final_chance,
            d.get("news_momentum", 0.0),
            tail_weight=0.95,
            asset_type="Commodity",
            stress_score=stress_score,
            euphoria_score=euphoria_score,
        ) * psych_volatility * float(positioning["volatility_multiplier"])
        
        d["kurs"] = _apply_price_move(d["kurs"], tages_vola, richtung, asset_type="Commodity")
        append_ohlc_from_move(d, alt, d["kurs"], zeit_str, volatility=tages_vola)
        d["aenderung"] = ((d["kurs"] - alt) / alt) * 100
        d["market_cap"] = d["kurs"] * 10000000.0

    # 3. AKTIEN BERECHNEN (IN LOKALWÄHRUNG)
    energy_return = sum(
        float(daten_module.rohstoffe[code].get("aenderung", 0.0)) / 100.0
        for code in ("CL", "TTF")
    ) / 2.0
    stock_caps: dict[str, tuple[float, float]] = {}
    for runtime in runtime_assets["stocks"]:
        t = runtime.ticker
        d = runtime.asset
        land_data = daten_module.makro.get(runtime.land, {"zins": 0.04, "bip_prozent": 0.01})
        br = runtime.branch
        expected_rate = float(land_data.get("expected_rate", land_data["zins"]))
        expected_growth = float(land_data.get("expected_growth", land_data["bip_prozent"]))
        expected_inflation = float(land_data.get("expected_inflation", land_data.get("inflation", 0.02)))
        macro_surprise = float(land_data.get("macro_surprise_momentum", 0.0))
        lokaler_zins_effekt = (0.035 - expected_rate) * 0.3
        matrix_effekt = 0.0
        
        matrix_effekt += stock_energy_price_signal(br, energy_return)
        if br == "Finanzen": matrix_effekt += (expected_rate - 0.035) * 0.12
        if br == "Immobilien": matrix_effekt -= max(0.0, expected_rate - 0.035) * 0.38
        if br in {"Einzelhandel", "Konsumgüter", "Automobil"}:
            matrix_effekt += macro_surprise * 0.55
        
        fundamental_hebel = consume_fundamental_repricing(d)
        
        event_pressure = _event_pressure(daten_module, runtime.land, "Stock")
        chance = 0.50 + (expected_growth * 2.2) + lokaler_zins_effekt + matrix_effekt + d.get("news_momentum", 0.0) + (0.0025 * gli_faktor) + fundamental_hebel
        chance += float(d.get("fund_flow_pressure", 0.0))
        chance += macro_surprise * 1.4 - max(0.0, expected_inflation - 0.035) * 0.85
        chance += (liquidity_impulse * 1.6) - (risk_pressure * 0.55) - (curve_pressure * 0.35)
        chance -= event_pressure * 0.035
        diff_ema20 = _asset_ema_diff(d, 20)
        if diff_ema20 > 0.05: chance -= 0.15
        elif diff_ema20 < -0.05: chance += 0.15
        long_return = _asset_return(d, 120)
        if long_return > 0.45:
            chance -= min(0.14, (long_return - 0.45) * 0.10)
        elif long_return < -0.35:
            chance += min(0.09, abs(long_return + 0.35) * 0.08)
        psych_signal, psych_volatility, *_psych_state = daily_asset_psychology_values(
            d,
            "Stock",
            psychology,
            stock_macro_bias,
            assume_ready=True,
        )
        chance += psych_signal
        d["news_momentum"] = d.get("news_momentum", 0.0) * 0.75
        d["fund_flow_pressure"] = float(d.get("fund_flow_pressure", 0.0)) * 0.72
        
        alt = d["kurs"]
        richtung = 1 if random.random() < _direction_probability(chance) else -1
        euphoria_score = _tail_score(
            max(0.0, fundamental_hebel) * 7.5,
            max(0.0, macro_surprise) * 16.0,
            max(0.0, liquidity_impulse) * 22.0,
            max(0.0, psych_signal) * 8.0,
            max(0.0, expected_growth - 0.018) * 18.0,
            max(0.0, -diff_ema20) * 3.0,
        )
        stress_score = _tail_score(
            max(0.0, -fundamental_hebel) * 7.5,
            max(0.0, -macro_surprise) * 16.0,
            max(0.0, risk_pressure) * 8.0,
            max(0.0, curve_pressure) * 8.0,
            max(0.0, expected_inflation - 0.035) * 20.0,
            max(0.0, -psych_signal) * 8.0,
            event_pressure,
            max(0.0, diff_ema20) * 2.0,
        )
        positioning = _update_open_interest(daten_module, t, d, "Stock", chance)
        chance += float(positioning["chance_impulse"])
        euphoria_score += max(0.0, float(positioning["squeeze_pressure"])) * 4.0
        stress_score += max(0.0, -float(positioning["squeeze_pressure"])) * 4.0
        
        tages_vola = _open_ended_daily_volatility(
            random.uniform(0.002, 0.012),
            chance,
            d.get("news_momentum", 0.0),
            tail_weight=0.45,
            asset_type="Stock",
            stress_score=stress_score,
            euphoria_score=euphoria_score,
        ) * psych_volatility * float(positioning["volatility_multiplier"])
        
        d["kurs"] = _apply_price_move(d["kurs"], tages_vola, richtung, asset_type="Stock")
        append_ohlc_from_move(d, alt, d["kurs"], zeit_str, volatility=tages_vola)
        d["aenderung"] = ((d["kurs"] - alt) / alt) * 100 if alt > 0 else 0.0
        shares = runtime.shares
        d["market_cap"] = d["kurs"] * shares
        stock_caps[t] = (alt * shares, d["market_cap"])

    # 4. KRYPTOS IN GOLD-DINAR (GD) SCHWANKEN LASSEN
    for runtime in runtime_assets["cryptos"]:
        t = runtime.ticker
        d = runtime.asset
        diff_gd20 = _asset_ema_diff(d, 20)
        chain_fundamente = (d.get("netzwerk_aktivitaet", 0.0) * 0.04) + (d.get("netzwerk_fees", 0.0) * 0.04)
        crypto_fundamente = crypto_price_signal(d)
        chance = 0.50 + (global_expected_growth * 2.5) + ((0.035 - welt_zins) * 0.5) + (0.0085 * gli_faktor) + chain_fundamente + crypto_fundamente
        chance += float(d.get("fund_flow_pressure", 0.0))
        chance += global_macro_surprise * 1.2
        chance += liquidity_impulse * 2.0
        if diff_gd20 > 0.10: chance -= 0.20
        elif diff_gd20 < -0.10: chance += 0.20
        long_return = _asset_return(d, 180)
        if long_return > 1.50:
            chance -= min(0.38, (long_return - 1.50) * 0.055)
        elif long_return < -0.65:
            chance += min(0.16, abs(long_return + 0.65) * 0.10)
        price_heat = max(0.0, math.log(max(1.0, float(d.get("kurs", 1.0))) / 900.0))
        chance -= min(0.24, price_heat * 0.075)

        psych_signal, psych_volatility, *_psych_state = daily_asset_psychology_values(
            d,
            "Crypto",
            psychology,
            crypto_macro_bias,
            assume_ready=True,
        )
        chance += psych_signal
        positioning = _update_open_interest(daten_module, t, d, "Crypto", chance)
        chance += float(positioning["chance_impulse"])
        
        alt = d["kurs"]
        richtung = 1 if random.random() < _direction_probability(chance) else -1
        d["fund_flow_pressure"] = float(d.get("fund_flow_pressure", 0.0)) * 0.74
        euphoria_score = _tail_score(
            max(0.0, crypto_fundamente) * 6.5,
            max(0.0, chain_fundamente) * 11.0,
            max(0.0, liquidity_impulse) * 28.0,
            max(0.0, global_macro_surprise) * 14.0,
            max(0.0, psych_signal) * 8.5,
            max(0.0, float(positioning["squeeze_pressure"])) * 4.8,
            max(0.0, -diff_gd20) * 2.5,
        )
        stress_score = _tail_score(
            max(0.0, -crypto_fundamente) * 6.5,
            max(0.0, risk_pressure) * 7.0,
            max(0.0, -global_macro_surprise) * 14.0,
            max(0.0, -psych_signal) * 8.5,
            max(0.0, -float(positioning["squeeze_pressure"])) * 4.8,
            max(0.0, long_return - 1.50) * 0.75,
            price_heat * 0.35,
            max(0.0, diff_gd20) * 1.8,
        )
        
        basis_schwankung = random.uniform(0.004, 0.018) # Etwas höherer Grund-Floor als Aktien
        tages_vola = _open_ended_daily_volatility(
            basis_schwankung,
            chance,
            d.get("netzwerk_aktivitaet", 0.0),
            tail_weight=0.65,
            asset_type="Crypto",
            stress_score=stress_score,
            euphoria_score=euphoria_score,
        ) * psych_volatility * float(positioning["volatility_multiplier"])
        
        d["kurs"] = _apply_price_move(d["kurs"], tages_vola, richtung, asset_type="Crypto")
        append_ohlc_from_move(d, alt, d["kurs"], zeit_str, volatility=tages_vola)
        d["aenderung"] = ((d["kurs"] - alt) / alt) * 100 if alt > 0 else 0.0
        previous_market_cap = max(1.0, float(d.get("market_cap", d["kurs"] * d.get("circulating_supply", 10000000.0))))
        d["market_cap"] = d["kurs"] * d.get("circulating_supply", 10000000.0)
        d["market_cap_change"] = (d["market_cap"] / previous_market_cap - 1.0) if previous_market_cap else 0.0

    # Crypto chains trade as standalone assets; no fixed BTC forex anchor is assumed.

    # 5. INDICES: market-cap weighted country and country-sector baskets
    _update_indices_from_runtime_cache(daten_module, zeit_str, stock_caps)

    # 6. FUNDS AND ETFS: active baskets, passive index trackers and AUM flows
    update_funds(daten_module, zeit_str)

def _direction_probability(chance: float) -> float:
    return max(0.005, min(0.995, chance))


def stock_energy_price_signal(sector: str, energy_return: float) -> float:
    energy_move = max(-0.08, min(0.08, float(energy_return)))
    if sector in {"Transport und Logistik", "Automobil", "Maschinenbau", "Landwirtschaft"}:
        return -energy_move * 0.30
    if sector == "Öl und Gas":
        return energy_move * 0.18
    # Utilities already receive energy/input effects through monthly production
    # and fundamentals; another daily price bonus would count the exposure twice.
    return 0.0


def _market_runtime_assets(daten_module) -> dict[str, list[MarketAssetRuntime]]:
    commodities = getattr(daten_module, "rohstoffe", {})
    stocks = getattr(daten_module, "aktien", {})
    cryptos = getattr(daten_module, "kryptos", {})
    signature = (
        tuple(commodities.keys()),
        tuple(stocks.keys()),
        tuple(cryptos.keys()),
    )
    cache = getattr(daten_module, "market_runtime_assets", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["assets"]

    assets = {
        "commodities": [
            MarketAssetRuntime(
                str(ticker),
                asset,
                is_monetary_metal=str(ticker) in {"XAU", "XAG"},
            )
            for ticker, asset in commodities.items()
        ],
        "stocks": [
            MarketAssetRuntime(
                str(ticker),
                asset,
                land=str(asset.get("land", "")),
                branch=str(asset.get("branche", "")),
                shares=float(asset.get("aktien_anzahl", 10_000_000.0)),
            )
            for ticker, asset in stocks.items()
        ],
        "cryptos": [
            MarketAssetRuntime(str(ticker), asset)
            for ticker, asset in cryptos.items()
        ],
    }
    daten_module.market_runtime_assets = {"signature": signature, "assets": assets}
    return assets


def market_runtime_assets(daten_module) -> dict[str, list[MarketAssetRuntime]]:
    return _market_runtime_assets(daten_module)


def _update_indices_from_runtime_cache(
    daten_module,
    zeit_str: str,
    stock_caps: dict[str, tuple[float, float]] | None = None,
) -> None:
    index_members = _stock_index_members(daten_module)
    if stock_caps is None:
        stock_caps = {}
        for ticker, asset in daten_module.aktien.items():
            change_factor = 1.0 + float(asset.get("aenderung", 0.0)) / 100.0
            current_price = float(asset.get("kurs", 0.0))
            previous_price = current_price / change_factor if change_factor > 0 else current_price
            shares = float(asset.get("aktien_anzahl", 10_000_000.0))
            stock_caps[ticker] = (previous_price * shares, current_price * shares)

    for index, tickers in _index_runtime_rows(daten_module, index_members):
        old_level = float(index.get("kurs", 1000.0))
        total_previous = 0.0
        total_current = 0.0
        constituents = {}
        for ticker in tickers:
            previous_cap, current_cap = stock_caps.get(ticker, (0.0, 0.0))
            total_previous += previous_cap
            total_current += current_cap
            constituents[ticker] = current_cap

        if total_previous > 0:
            index["kurs"] = max(1.0, old_level * (total_current / total_previous))

        index["market_cap"] = total_current
        index["constituent_count"] = len(tickers)
        index["constituents"] = {
            ticker: market_cap / total_current if total_current else 0.0
            for ticker, market_cap in constituents.items()
        }
        append_ohlc_from_move(index, old_level, index["kurs"], zeit_str)
        index["aenderung"] = ((float(index["kurs"]) - old_level) / old_level) * 100 if old_level > 0 else 0.0


def _index_runtime_rows(daten_module, index_members) -> list[tuple[dict, list[str]]]:
    indices = getattr(daten_module, "indizes", {})
    signature = tuple(
        (ticker, str(index.get("land", "")), str(index.get("branche", ALL_SECTORS)))
        for ticker, index in indices.items()
    )
    cache = getattr(daten_module, "_market_index_runtime_rows", None)
    if isinstance(cache, dict) and cache.get("signature") == signature:
        return cache["rows"]
    rows = [
        (
            index,
            index_members.get(
                (str(index.get("land", "")), str(index.get("branche", ALL_SECTORS))),
                [],
            ),
        )
        for index in indices.values()
    ]
    daten_module._market_index_runtime_rows = {"signature": signature, "rows": rows}
    return rows


def _stock_index_members(daten_module) -> dict[tuple[str, str], list[str]]:
    stocks = getattr(daten_module, "aktien", {})
    signature = (len(stocks), tuple(stocks.keys()))
    cache = getattr(daten_module, "market_runtime_index", None)
    if isinstance(cache, dict) and cache.get("stock_members_signature") == signature:
        return cache["stock_index_members"]

    members: dict[tuple[str, str], list[str]] = {}
    for ticker, asset in stocks.items():
        land = str(asset.get("land", ""))
        branch = str(asset.get("branche", ""))
        members.setdefault((land, ALL_SECTORS), []).append(str(ticker))
        members.setdefault((land, branch), []).append(str(ticker))

    daten_module.market_runtime_index = {
        "stock_members_signature": signature,
        "stock_index_members": members,
    }
    daten_module._market_index_runtime_rows = None
    return members


def _asset_ema_diff(asset: dict, period: int) -> float:
    history = asset.get("historie", [])
    if not history:
        return 0.0
    cache = asset.setdefault("_ema_cache", {})
    cache_key = str(period)
    cached = cache.get(cache_key, {})
    current_len = len(history)
    current_price = _history_price(history[-1])
    if current_price <= 0:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    previous_len = int(cached.get("length", 0) or 0)
    previous_ema = float(cached.get("ema", 0.0) or 0.0)
    marker = (str(history[-1][1]) if isinstance(history[-1], (tuple, list)) and len(history[-1]) > 1 else "", current_price)
    previous_marker = tuple(cached.get("marker", ()))
    if previous_ema > 0 and current_len in {previous_len, previous_len + 1} and marker != previous_marker:
        ema = (current_price * alpha) + (previous_ema * (1.0 - alpha))
    elif previous_ema > 0 and marker == previous_marker:
        ema = previous_ema
    else:
        prices = [_history_price(entry) for entry in history[-max(period * 4, period + 1) :]]
        prices = [price for price in prices if price > 0]
        if not prices:
            return 0.0
        ema = ema_values(prices, min(period, len(prices)))[-1]
    cache[cache_key] = {"length": current_len, "ema": ema, "marker": marker}
    return ((current_price - ema) / ema) if ema else 0.0


def _asset_return(asset: dict, lookback: int) -> float:
    history = asset.get("historie", [])
    if len(history) < 2:
        return 0.0
    current_price = _history_price(history[-1])
    previous_entry = history[-min(len(history), max(2, lookback))]
    previous_price = _history_price(previous_entry)
    return (current_price / previous_price - 1.0) if current_price > 0 and previous_price > 0 else 0.0


def _commodity_price_anchor_signal(asset: dict) -> float:
    price = max(1.0, float(asset.get("kurs", 100.0)))
    anchor = max(1.0, float(asset.get("fundamental_anchor_price", 100.0)))
    return max(-0.22, min(0.28, -math.log(price / anchor) * 0.18))


def _history_price(entry) -> float:
    try:
        return float(entry[0] if isinstance(entry, (tuple, list)) else entry)
    except (TypeError, ValueError):
        return 0.0


def _open_ended_daily_volatility(
    base_volatility: float,
    chance: float,
    momentum: float,
    *,
    tail_weight: float,
    asset_type: str = "Stock",
    stress_score: float = 0.0,
    euphoria_score: float = 0.0,
) -> float:
    raw_strength = abs(chance - 0.50) + abs(float(momentum))
    routine_strength = min(raw_strength, 0.22)
    extreme_strength = max(0.0, raw_strength - 0.22)
    confluence = max(0.0, float(stress_score)) + max(0.0, float(euphoria_score))
    normal_multiplier = 1.0 + (routine_strength * 1.4) + (extreme_strength * 2.2) + min(1.6, confluence * 0.10)
    base_tail = {"Commodity": 0.0010, "Stock": 0.0018, "Crypto": 0.0030}.get(asset_type, 0.0018)
    tail_probability = base_tail * (1.0 + max(0.0, extreme_strength - 0.12) * 9.0 + confluence**1.35 * 0.42)
    tail_probability += max(0.0, extreme_strength - 0.18) * 0.018
    tail_multiplier = 1.0
    if random.random() < tail_probability:
        tail_multiplier += random.lognormvariate(0.0, 0.32 + min(1.8, (extreme_strength + confluence * 0.16) * tail_weight))
    return base_volatility * normal_multiplier * tail_multiplier


def _apply_price_move(
    current_price: float,
    daily_volatility: float,
    direction: int,
    *,
    asset_type: str,
) -> float:
    if current_price <= 0.0:
        return 0.01 if asset_type == "Crypto" else 1.0
    log_move = max(0.0, float(daily_volatility)) * (1 if direction > 0 else -1)
    log_move += {"Commodity": -0.00005, "Stock": 0.00002, "Crypto": 0.00000}.get(asset_type, 0.0)
    try:
        next_price = float(current_price) * math.exp(log_move)
    except OverflowError:
        next_price = float("inf")
    if not math.isfinite(next_price):
        next_price = float(current_price) * 1000.0
    absolute_floor = 0.01 if asset_type == "Crypto" else 1.0
    return max(absolute_floor, next_price)


def _tail_score(*signals: float) -> float:
    score = 0.0
    for signal in signals:
        value = float(signal)
        if value > 0.0:
            score += value
    return min(8.0, score)


def _event_pressure(daten_module, country: str | None, asset_type: str) -> float:
    event = getattr(daten_module, "aktives_event", None)
    if not event:
        return 0.0
    event_countries = event.get("laender", [])
    if country is not None and country not in event_countries:
        return 0.0
    shock = abs(min(0.0, float(event.get("bip_makel", 0.0))))
    if asset_type == "Commodity":
        event_type = str(event.get("typ", ""))
        return shock * (42.0 if event_type in {"ENERGIE", "BILATERAL"} else 18.0)
    return shock * 34.0


def _update_open_interest(
    daten_module,
    ticker: str,
    asset: dict,
    asset_type: str,
    chance: float,
) -> dict[str, float | str]:
    market_size = _open_interest_market_size(asset, asset_type)
    crypto = asset_type == "Crypto"
    decay = 0.88 if crypto else 0.92
    base_long = 0.035 if crypto else 0.020
    base_short = 0.030 if crypto else 0.016
    flow_long = 0.010 if crypto else 0.006
    flow_short = 0.009 if crypto else 0.005
    crowding_long = 0.018 if crypto else 0.010
    crowding_short = 0.019 if crypto else 0.011
    interest_cap = 0.85 if crypto else 0.55
    long_interest = float(asset.get("long_interest", market_size * base_long)) * decay
    short_interest = float(asset.get("short_interest", market_size * base_short)) * decay
    momentum = _asset_return(asset, 20)
    crowding = max(-1.0, min(1.0, (chance - 0.50) * 4.0 + momentum * 1.4))
    long_interest += market_size * (flow_long + max(0.0, crowding) * crowding_long)
    short_interest += market_size * (flow_short + max(0.0, -crowding) * crowding_short)
    long_interest = max(0.0, min(market_size * interest_cap, long_interest))
    short_interest = max(0.0, min(market_size * interest_cap, short_interest))
    open_interest = long_interest + short_interest
    imbalance = (long_interest - short_interest) / max(1.0, open_interest)
    short_ratio = short_interest / max(1.0, open_interest)
    long_ratio = long_interest / max(1.0, open_interest)
    squeeze_pressure = _squeeze_pressure(asset, chance, short_ratio, long_ratio, open_interest, market_size, asset_type)

    asset["long_interest"] = long_interest
    asset["short_interest"] = short_interest
    asset["open_interest"] = open_interest
    asset["open_interest_ratio"] = open_interest / max(1.0, market_size)
    asset["positioning_imbalance"] = imbalance
    asset["squeeze_pressure"] = squeeze_pressure
    asset["squeeze_type"] = "SHORT" if squeeze_pressure > 0 else "LONG" if squeeze_pressure < 0 else ""
    _append_open_interest_history(asset, long_interest, short_interest)

    chance_multiplier = 0.24 if crypto else 0.18
    volatility_scale = 3.0 if crypto else 2.2
    volatility_cap = 1.6 if crypto else 1.2
    return {
        "chance_impulse": squeeze_pressure * chance_multiplier,
        "squeeze_pressure": squeeze_pressure,
        "volatility_multiplier": 1.0 + min(volatility_cap, abs(squeeze_pressure) * volatility_scale),
    }


def _open_interest_market_size(asset: dict, asset_type: str) -> float:
    if asset_type == "Stock":
        return max(1.0, float(asset.get("market_cap", float(asset.get("kurs", 100.0)) * 10_000_000.0)))
    return max(1.0, float(asset.get("market_cap", float(asset.get("kurs", 100.0)) * 10_000_000.0)))


def _squeeze_pressure(
    asset: dict,
    chance: float,
    short_ratio: float,
    long_ratio: float,
    open_interest: float,
    market_size: float,
    asset_type: str,
) -> float:
    oi_ratio = open_interest / max(1.0, market_size)
    shock = (chance - 0.50) + _asset_return(asset, 5) * 0.80 + float(asset.get("news_momentum", 0.0)) * 0.50
    short_threshold = 0.54 if asset_type == "Crypto" else 0.58
    long_threshold = 0.57 if asset_type == "Crypto" else 0.62
    shock_threshold = 0.018 if asset_type == "Crypto" else 0.025
    max_pressure = 0.34 if asset_type == "Crypto" else 0.28
    squeeze_scale = 3.4 if asset_type == "Crypto" else 2.8
    short_squeeze = (
        max(0.0, short_ratio - short_threshold)
        * max(0.0, shock - shock_threshold)
        * (1.0 + oi_ratio * 4.0)
    )
    long_squeeze = (
        max(0.0, long_ratio - long_threshold)
        * max(0.0, -shock - shock_threshold)
        * (1.0 + oi_ratio * 4.0)
    )
    pressure = min(max_pressure, short_squeeze * squeeze_scale) - min(max_pressure, long_squeeze * squeeze_scale)
    if abs(pressure) < 0.002:
        return 0.0
    return pressure


def _append_open_interest_history(asset: dict, long_interest: float, short_interest: float) -> None:
    history = asset.setdefault("open_interest_history", [])
    history.append((float(long_interest), float(short_interest)))
    if len(history) > 260:
        del history[:-260]


# DATEI: markt.py ENDE
