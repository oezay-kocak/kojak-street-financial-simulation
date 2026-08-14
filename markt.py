# DATEI: markt.py START
import random
import math
import numpy as np
import daten
from kojakstreet.core.commodities import commodity_price_signal
from kojakstreet.core.ohlc import append_ohlc_from_move, normalize_commodity_supply_key

def get_gd_diff(historie, tage):
    saubere_zahlen = []
    for x in historie:
        try:
            if isinstance(x, (tuple, list)): 
                saubere_zahlen.append(float(x[0]))
            else: 
                saubere_zahlen.append(float(x))
        except Exception: 
            continue
    if not saubere_zahlen: return 0.0
    aktueller_kurs = saubere_zahlen[-1]
    mittelwert = float(np.mean(saubere_zahlen[-tage:])) if len(saubere_zahlen) >= tage else float(np.mean(saubere_zahlen))
    return (aktueller_kurs - mittelwert) / mittelwert if mittelwert != 0.0 else 0.0

def update_markt_kurse():
    zeit_str = daten.datum.strftime("%d.%m.%Y")
    gli = getattr(daten, "gli_index", 15420.0)
    gli_faktor = math.sqrt(gli / 15420.0)
    
    globales_bip_wachstum = sum([daten.makro.get(l, {}).get("bip_prozent", 0.01) for l in daten.LAENDER]) / len(daten.LAENDER)
    welt_zins = sum([daten.makro.get(l, {}).get("zins", 0.04) for l in daten.LAENDER]) / len(daten.LAENDER)
    
    # 1. FIAT-WÄHRUNGSSTÄRKEN BERECHNEN (KAUFKRAFT)
    for land in daten.LAENDER:
        m = daten.makro.get(land, {"zins": 0.04, "bip_prozent": 0.01})
        forex_stabilisator = (1.0 - daten.waehrungen_staerke[land]) * 0.01
        zins_impuls = (m["zins"] - welt_zins) * 0.12
        bip_impuls = m["bip_prozent"] * 0.05
        
        krisen_malus = -0.0065 if (daten.aktives_event and land in daten.aktives_event["laender"]) else 0.0
        rauschen = random.uniform(-0.015, 0.015)
        
        daten.waehrungen_staerke[land] = max(0.2, min(5.0, daten.waehrungen_staerke[land] * (1.0 + zins_impuls + bip_impuls + krisen_malus + rauschen + forex_stabilisator)))

    # TÄGLICHE HISTORIE FÜR ALLE 30 HANDELSPAARE SCHREIBEN (Inkl. GD)
    gold_basis_preis = daten.rohstoffe["XAU"]["kurs"]
    gd_strength = gold_basis_preis / 100.0  # GD skaliert mit dem Goldpreis

    for l1 in daten.WAEHRUNGEN:
        for l2 in daten.WAEHRUNGEN:
            if l1 != l2:
                paar_key = f"{l1}/{l2}"
                if paar_key not in daten.FOREX_PAARE_HISTORIE: 
                    daten.FOREX_PAARE_HISTORIE[paar_key] = []
                
                # Stärke abrufen (GD bekommt seinen Sonderwert)
                s1 = daten.waehrungen_staerke.get(l1, 1.0) if l1 != "GD" else gd_strength
                s2 = daten.waehrungen_staerke.get(l2, 1.0) if l2 != "GD" else gd_strength
                
                # Kurs berechnen
                wechselkurs = s1 / s2 if s2 > 0 else 1.0
                daten.FOREX_PAARE_HISTORIE[paar_key].append((wechselkurs, zeit_str, ""))

    # 2. ROHSTOFFE DIREKT IN GOLD-DINAR (GD) SCHWANKEN LASSEN
    for t, d in daten.rohstoffe.items():
        diff_gd20 = get_gd_diff(d["historie"], 20)
        chance = 0.50 - (diff_gd20 * 0.30) + d.get("news_momentum", 0.0)
        commodity_signal = commodity_price_signal(d)
        chance += commodity_signal
        d["news_momentum"] = d.get("news_momentum", 0.0) * 0.80
        
        foerder_effekt = -normalize_commodity_supply_key(d) * 0.08
        chance += foerder_effekt
        
        gli_effekt = 0.0045 * gli_faktor if t in ["XAU", "XAG"] else 0.0015 * gli_faktor
        inflation_hedge = daten.makro["USA"]["inflation"] * 0.5 if t in ["XAU", "XAG"] else 0.0
        
        alt = d["kurs"]
        richtung = 1 if random.random() < max(0.10, min(0.90, chance + gli_effekt + inflation_hedge)) else -1
        
        wucht_faktor = 1.0 + (abs(d.get("news_momentum", 0.0)) * 4.0)
        shock_pressure = max(0.0, commodity_signal - 0.18) + max(0.0, -float(d.get("inventories_change", 0.0)) - 0.03)
        basis_schwankung = random.uniform(0.0025, 0.014) * (1.0 + min(2.6, shock_pressure * 6.0))
        tages_vola = basis_schwankung * wucht_faktor
        
        d["kurs"] = max(1.0, d["kurs"] + (d["kurs"] * tages_vola * richtung))
        append_ohlc_from_move(d, alt, d["kurs"], zeit_str, volatility=tages_vola)
        d["aenderung"] = ((d["kurs"] - alt) / alt) * 100
        d["market_cap"] = d["kurs"] * 10000000.0

    # 3. AKTIEN BERECHNEN (IN LOKALWÄHRUNG)
    schock_energie = (daten.rohstoffe["CL"]["kurs"] + daten.rohstoffe["TTF"]["kurs"]) / 200.0
    for t, d in daten.aktien.items():
        land_data = daten.makro.get(d["land"], {"zins": 0.04, "bip_prozent": 0.01})
        br = d["branche"]
        lokaler_zins_effekt = (0.035 - land_data["zins"]) * 0.3
        matrix_effekt = 0.0
        
        if br in ["Öl und Gas", "Stromerzeuger"]: matrix_effekt += (schock_energie - 1.0) * 0.05
        elif br in ["Transport und Logistik", "Automobil", "Maschinenbau", "Landwirtschaft"]: matrix_effekt -= (schock_energie - 1.0) * 0.03
        if br == "\u00d6l und Gas": matrix_effekt += (schock_energie - 1.0) * 0.05
        if br == "Finanzen": matrix_effekt += (land_data["zins"] - 0.035) * 0.3
        
        gewinn_hebel = d.get("gewinn_kennzahl", 0.0) * 0.04
        
        aktuelles_eps = max(0.1, d.get("eps", 5.0))
        aktuelles_kgv = d["kurs"] / aktuelles_eps
        fundamental_bewertung = max(-0.25, min(0.20, (20.0 - aktuelles_kgv) * 0.003))
        
        chance = 0.50 + (land_data["bip_prozent"] * 2.2) + lokaler_zins_effekt + matrix_effekt + d.get("news_momentum", 0.0) + (0.0025 * gli_faktor) + fundamental_bewertung + gewinn_hebel
        d["news_momentum"] = d.get("news_momentum", 0.0) * 0.75
        
        diff_gd20 = get_gd_diff(d["historie"], 20)
        if diff_gd20 > 0.05: chance -= 0.15
        elif diff_gd20 < -0.05: chance += 0.15
        
        alt = d["kurs"]
        richtung = 1 if random.random() < max(0.12, min(0.88, chance)) else -1
        
        wucht_faktor = 1.0 + (abs(d.get("news_momentum", 0.0)) * 4.0)
        tages_vola = random.uniform(0.002, 0.012) * wucht_faktor
        
        d["kurs"] = max(1.0, d["kurs"] + (d["kurs"] * tages_vola * richtung))
        append_ohlc_from_move(d, alt, d["kurs"], zeit_str, volatility=tages_vola)
        d["aenderung"] = ((d["kurs"] - alt) / alt) * 100 if alt > 0 else 0.0
        d["market_cap"] = d["kurs"] * d.get("aktien_anzahl", 10000000.0)

    # 4. KRYPTOS IN GOLD-DINAR (GD) SCHWANKEN LASSEN
    for t, d in daten.kryptos.items():
        diff_gd20 = get_gd_diff(d["historie"], 20)
        chain_fundamente = (d.get("netzwerk_aktivitaet", 0.0) * 0.04) + (d.get("netzwerk_fees", 0.0) * 0.04)
        chance = 0.50 + (globales_bip_wachstum * 2.5) + ((0.035 - welt_zins) * 0.5) + (0.0085 * gli_faktor) + chain_fundamente
        if diff_gd20 > 0.10: chance -= 0.20
        elif diff_gd20 < -0.10: chance += 0.20
        
        alt = d["kurs"]
        richtung = 1 if random.random() < max(0.08, min(0.92, chance)) else -1
        
        wucht_faktor = 1.0 + (abs(d.get("netzwerk_aktivitaet", 0.0)) * 7.0)
        basis_schwankung = random.uniform(0.004, 0.018) # Etwas höherer Grund-Floor als Aktien
        tages_vola = basis_schwankung * wucht_faktor
        
        d["kurs"] = max(0.01, d["kurs"] + (d["kurs"] * tages_vola * richtung))
        append_ohlc_from_move(d, alt, d["kurs"], zeit_str, volatility=tages_vola)
        d["aenderung"] = ((d["kurs"] - alt) / alt) * 100 if alt > 0 else 0.0
        d["market_cap"] = d["kurs"] * 10000000.0

    # 5. INDEXFONDS (NATIVE LÄNDERFONDS FOLGEN DER NOMINALEN HEIMAT-PERFORMANCE)
    for tf, df in daten.fonds.items():
        alt = df["kurs"]
        prozent_aenderungen = []
        
        for ta, da in daten.aktien.items():
            if da["land"] == df["ziel"]: # Jeder Länderfonds trackt exakt sein Land
                prozent_aenderungen.append(da["aenderung"])
                
        if prozent_aenderungen:
            durchschnitts_performance = sum(prozent_aenderungen) / len(prozent_aenderungen)
            df["kurs"] = max(1.0, df["kurs"] * (1.0 + durchschnitts_performance / 100.0))
        
        append_ohlc_from_move(df, alt, df["kurs"], zeit_str)
        df["aenderung"] = ((df["kurs"] - alt) / alt) * 100 if alt > 0 else 0.0
        df["market_cap"] = df["kurs"] * 5000000.0

    # TÄGLICHE HISTORIE FÜR DIE 5 KRYPTO-ZENTRALBANK-ANKERPAARE (BTC/FIAT)
    btc_basis_gd = daten.kryptos["BTC"]["kurs"]
    for land in daten.LAENDER:
        paar_btc_key = f"BTC/{land}"
        if paar_btc_key not in daten.FOREX_PAARE_HISTORIE: 
            daten.FOREX_PAARE_HISTORIE[paar_btc_key] = []
        
        s_lokal = daten.waehrungen_staerke[land]
        wechselkurs_fiat_pro_gd = gold_basis_preis / s_lokal if s_lokal > 0 else gold_basis_preis
        wechselkurs_fiat_pro_btc = btc_basis_gd * wechselkurs_fiat_pro_gd
        daten.FOREX_PAARE_HISTORIE[paar_btc_key].append((wechselkurs_fiat_pro_btc, zeit_str, ""))

    # 6. INDIZES BERECHNEN (GEWICHTET NACH MARKET CAP DER AKTIEN)
    for ti, di in getattr(daten, "indizes", {}).items():
        alt_idx = di["kurs"]
        total_mcap_alt = 0.0
        total_mcap_neu = 0.0
        
        for ta, da in daten.aktien.items():
            if da["land"] == di["land"]:
                # Wir ermitteln den alten Kurs vor dem heutigen Tag über das da["aenderung"]
                aend_faktor = (1.0 + da["aenderung"] / 100.0)
                alt_kurs = da["kurs"] / aend_faktor if aend_faktor > 0 else da["kurs"]
                
                # Gewichtung nach der festen Aktienanzahl des Unternehmens
                anzahl = da.get("aktien_anzahl", 10000000.0)
                total_mcap_alt += alt_kurs * anzahl
                total_mcap_neu += da["kurs"] * anzahl
        
        # Der Index verändert sich exakt im selben Verhältnis wie die gesamte Marktkapitalisierung des Landes
        if total_mcap_alt > 0:
            perf_faktor = total_mcap_neu / total_mcap_alt
            di["kurs"] = max(1.0, di["kurs"] * perf_faktor)
        
        append_ohlc_from_move(di, alt_idx, di["kurs"], zeit_str)
        di["aenderung"] = ((di["kurs"] - alt_idx) / alt_idx) * 100 if alt_idx > 0 else 0.0

# DATEI: markt.py ENDE
