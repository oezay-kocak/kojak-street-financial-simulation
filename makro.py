# DATEI: makro.py START
import random
from datetime import timedelta
import daten

def berechne_welt_zins():
    if not hasattr(daten, "LAENDER") or not daten.LAENDER: 
        return 0.05
    summe = 0.0
    for land in daten.LAENDER:
        summe += daten.makro.get(land, {"zins": 0.05}).get("zins", 0.05)
    return summe / len(daten.LAENDER)

def hole_zins_umfeld_effekt(land):
    zins_historie = daten.MAKRO_HISTORIE.get(f"{land}_ZINS", [])
    if len(zins_historie) < 3: 
        return 0.0
    letzte_zinsen = [float(z if isinstance(z, (tuple, list)) else z) for z in zins_historie[-3:]]
    return letzte_zinsen[-1] - sum(letzte_zinsen)/len(letzte_zinsen)

def ist_letzter_tag_des_monats():
    try:
        morgen = daten.datum + timedelta(days=1)
        return morgen.month != daten.datum.month
    except Exception:
        return False

def update_global_liquidity_index():
    if not hasattr(daten, "gli_index") or daten.gli_index <= 100.0:
        daten.gli_index = 15420.0 
    if not hasattr(daten, "GLI_HISTORIE"):
        daten.GLI_HISTORIE = []
        
    gesamt_bip = sum(daten.makro[l]["bip_abs"] for l in daten.LAENDER)
    gewichtet_zins = 0.0
    for land in daten.LAENDER:
        m = daten.makro[land]
        gewicht = m["bip_abs"] / gesamt_bip if gesamt_bip > 0 else 0.2
        gewichtet_zins += m["zins"] * gewicht
    
    zins_abweichung_5prozent = (0.05 - gewichtet_zins) / 0.05 
    taegliche_basis_rate = 0.00012 * zins_abweichung_5prozent
    
    if gewichtet_zins < 0.03:
         qe_qt_impuls = (0.03 - gewichtet_zins) * 0.010
    elif gewichtet_zins > 0.07:
        qe_qt_impuls = (0.07 - gewichtet_zins) * 0.008
    else:
        qe_qt_impuls = 0.0001
    
    # NEU: BIP-gewichteter Balance-Sheet-Impuls aller Zentralbanken auf die Weltliquidität
    bs_gesamt_impuls = 0.0
    for land in daten.LAENDER:
        m = daten.makro[land]
        gewicht = m["bip_abs"] / gesamt_bip if gesamt_bip > 0 else 0.2
        hist_bs = daten.MAKRO_HISTORIE.get(f"{land}_BS", [])
        if len(hist_bs) > 1:
            alt_bs = hist_bs[-2][0] if isinstance(hist_bs[-2], (tuple, list)) else hist_bs[-2]
            # Monatliche prozentuale Veränderung der Bilanz berechnen
            bs_aenderungsrate = (m["balance_sheet"] - alt_bs) / alt_bs if alt_bs > 0 else 0.0
            # Auf tägliche Basis herunterskalieren (/30) und nach Wirtschaftskraft gewichten
            bs_gesamt_impuls += (bs_aenderungsrate / 30.0) * gewicht
            
    taegliches_rauschen = random.uniform(-0.0010, 0.0020)
    Gesamt_impuls = taegliche_basis_rate + qe_qt_impuls + bs_gesamt_impuls + taegliches_rauschen
    
    daten.gli_index = max(5000.0, daten.gli_index * (1.0 + Gesamt_impuls))
    daten.GLI_HISTORIE.append(daten.gli_index)

def fuehre_monatlichen_zinsentscheid_durch(add_news_callback):
    monat_str = daten.datum.strftime("%B %Y")
    zeit_str = daten.datum.strftime("%d.%m.%Y")
    zins_meldungen = []
    kurz_namen = {"USA": "US", "Japan": "JP", "Großbritannien": "GB", "EU": "EU", "China": "CH"}
    
    for land in daten.LAENDER:
        m = daten.makro[land]
        alt_zins = m["zins"]
        inf_abweichung = m["inflation"] - 0.02
        bip_abweichung = m["bip_prozent"] - 0.015
        zins_ziel = 0.035 + (inf_abweichung * 1.6) + (bip_abweichung * 0.6)
        
        # NEU: Variable, dynamische Zinsschritte basierend auf der Entfernung zum Zinsziel
        abweichung = abs(m["zins"] - zins_ziel)
        if abweichung > 0.030:    schritt_weite = 0.0100  # 1.0% Schock-Anpassung bei schweren Krisen
        elif abweichung > 0.012:  schritt_weite = 0.0050  # 0.5% Regelschritt
        else:                     schritt_weite = 0.0025  # 0.25% Feintuning nahe am Ziel
        
        if m["zins"] < zins_ziel - 0.001:
            schritt = schritt_weite
        elif m["zins"] > zins_ziel + 0.001:
            schritt = -schritt_weite
        else:
            schritt = 0.0
        
        # KORREKTUR: Unteres Zinslimit auf exakt 0.0% herabgesenkt
        m["zins"] = max(0.0000, min(0.0950, m["zins"] + schritt))
        
        # NEU: UNCONVENTIONAL MONETARY POLICY (QE / QT über das Balance Sheet)
        alt_bs = m["balance_sheet"]
        # Fall A: Zins ist bei 0.0% gefangen und das Wachstum hinkt hinterher -> Quantitative Easing!
        if m["zins"] <= 0.0001 and m["bip_prozent"] < 0.015:
            krisen_faktor = max(0.01, (0.015 - m["bip_prozent"]) * 2.5)
            m["balance_sheet"] *= (1.0 + krisen_faktor) # Bilanz bläht sich auf
        # Fall B: Zins wieder normal, aber Inflation kocht über -> Quantitative Tightening (Bilanzabbau)
        elif m["zins"] > 0.020 and m["inflation"] > 0.025 and m["balance_sheet"] > 1000.0:
            m["balance_sheet"] = max(1000.0, m["balance_sheet"] * 0.975) # -2.5% Liquiditätsentzug
            
        if f"{land}_ZINS" in daten.MAKRO_HISTORIE:
            daten.MAKRO_HISTORIE[f"{land}_ZINS"].append((m["zins"], zeit_str, ""))
        if f"{land}_BS" in daten.MAKRO_HISTORIE:
            daten.MAKRO_HISTORIE[f"{land}_BS"].append((m["balance_sheet"], zeit_str, ""))
        
        k_name = kurz_namen.get(land, land)
        msg_zeile = f"Leitzins"
        if m["zins"] != alt_zins:
            richtung = " ERHÖHT" if m["zins"] > alt_zins else " GESENKT"
            msg_zeile += f"{richtung} auf {m['zins']*100:.2f}%"
        else:
            msg_zeile += f" KONSTANT auf {m['zins']*100:.2f}%"
            
        # Detail-Ticker für Balance Sheet Aktionen anhängen
        if m["balance_sheet"] > alt_bs:
            msg_zeile += f" | [QE]: Bilanz auf {m['balance_sheet']:.0f} Mrd. ausgeweitet"
        elif m["balance_sheet"] < alt_bs:
            msg_zeile += f" | [QT]: Bilanz auf {m['balance_sheet']:.0f} Mrd. verkürzt"
            
        zins_meldungen.append(f"- {k_name}: {msg_zeile}")
    
    if zins_meldungen and add_news_callback:
        bericht_gesamt = f" ZENTRALBANK-ENTSCHEID & NOTENBANK-BILANZEN ({monat_str}):\n" + "\n".join(zins_meldungen)
        add_news_callback(bericht_gesamt, "ZENTRALBANK")

def update_makro_oekonomie(add_news_callback):
    monat_str = daten.datum.strftime("%B %Y")
    zeit_str = daten.datum.strftime("%d.%m.%Y")
    report_zeilen = []
    kurz_namen = {"USA": "US", "Japan": "JP", "Großbritannien": "GB", "EU": "EU", "China": "CH"}
    
    for land in daten.LAENDER:
        m = daten.makro[land]
        rauschen_bip = random.uniform(-0.008, 0.006)
        rauschen_inf = random.uniform(-0.003, 0.003)
        
        kr_makel = 0.0
        if daten.aktives_event and land in daten.aktives_event["laender"]:
            kr_makel = daten.aktives_event["bip_makel"]
            m["arbeitslosigkeit"] += random.uniform(0.015, 0.030)
            m["inflation"] += random.uniform(0.010, 0.025)
        
        zins_bremse = max(0.0, (m["zins"] - 0.035) * 0.65)
        if m["zins"] > 0.05: 
            zins_bremse *= 1.8 
            
        # NEU: Bilanz-Wachstums-Impuls auf Wirtschaftsentwicklung berechnen
        hist_bs = daten.MAKRO_HISTORIE.get(f"{land}_BS", [])
        bs_wachstum = 0.0
        if len(hist_bs) > 1:
            alt_bs = hist_bs[-2][0] if isinstance(hist_bs[-2], (tuple, list)) else hist_bs[-2]
            bs_wachstum = (m["balance_sheet"] - alt_bs) / alt_bs if alt_bs > 0 else 0.0
            
        qe_bip_impuls = max(0.0, bs_wachstum * 0.12)  # QE kurbelt Wirtschaftsleistung an
        qe_inf_impuls = bs_wachstum * 0.22           # QE heizt Inflation an, QT dämpft sie
        
        inflations_bremse = max(0.0, (m["inflation"] - 0.03) * 0.25)
        mittelwert_tendenz = (0.015 - m["bip_prozent"]) * 0.22
        zins_impuls = (0.035 - m["zins"]) * 0.25 
        
        m["bip_prozent"] = m["bip_prozent"] + zins_impuls + mittelwert_tendenz - zins_bremse - inflations_bremse + rauschen_bip + kr_makel + qe_bip_impuls
        m["bip_prozent"] = max(-0.060, min(0.045, m["bip_prozent"]))
        m["bip_abs"] = max(1000.0, m["bip_abs"] * (1.0 + m["bip_prozent"] / 12.0))
        
        natuerliche_arbeitslosigkeit = 0.052
        bip_effekt = (0.015 - m["bip_prozent"]) * 0.45
        stabilisator_alo = (natuerliche_arbeitslosigkeit - m["arbeitslosigkeit"]) * 0.18
        m["arbeitslosigkeit"] += bip_effekt + stabilisator_alo + random.uniform(-0.001, 0.001)
        
        # KORREKTUR: Cap der Arbeitslosigkeit bei 15% komplett entfernt!
        m["arbeitslosigkeit"] = max(0.020, m["arbeitslosigkeit"])
        
        arbeitsmarkt_druck = (0.048 - m["arbeitslosigkeit"]) * 0.25
        rohstoff_cpi_impuls = _commodity_cpi_impulse(land)
        ziel_tendenz_inf = (0.020 - m["inflation"]) * 0.28
        m["inflation"] = (
            m["inflation"]
            + arbeitsmarkt_druck
            + ziel_tendenz_inf
            + qe_inf_impuls
            + rohstoff_cpi_impuls
            + rauschen_inf
        )
        
        # KORREKTUR: Deflationsgrenze auf heftige -8% ausgeweitet
        m["inflation"] = max(-0.080, min(0.120, m["inflation"]))
        
        daten.MAKRO_HISTORIE[f"{land}_ZINS"].append((m["zins"], zeit_str, ""))
        daten.MAKRO_HISTORIE[f"{land}_BIP"].append((m["bip_abs"], zeit_str, ""))
        daten.MAKRO_HISTORIE[f"{land}_INF"].append((m["inflation"], zeit_str, ""))
        daten.MAKRO_HISTORIE[f"{land}_ALO"].append((m["arbeitslosigkeit"], zeit_str, ""))
        daten.MAKRO_HISTORIE[f"{land}_BS"].append((m["balance_sheet"], zeit_str, ""))
        
        k_name = kurz_namen.get(land, land)
        report_zeilen.append(f"- {k_name}: BIP: {m['bip_prozent']*100:+.1f}% | Inf: {m['inflation']*100:+.1f}% | Alo: {m['arbeitslosigkeit']*100:.1f}%")
        
    if report_zeilen and add_news_callback:
        bericht_gesamt = f" MONATLICHER WIRTSCHAFTSBERICHT ({monat_str}):\n" + "\n".join(report_zeilen)
        add_news_callback(bericht_gesamt, "ZENTRALBANK")


def _commodity_cpi_impulse(land=None):
    groups = getattr(daten, "rohstoffe", {})
    if not groups:
        return 0.0
    energy = _average_price_level(groups, ["CL", "TTF", "NEWC"])
    metals = _average_price_level(groups, ["HG", "LIT", "COB"])
    food = _average_price_level(groups, ["ZW", "ZRC", "COF", "COC", "SUG", "MEAT", "FISH"])
    scarcity = 0.0
    samples = 0
    for asset in groups.values():
        scarcity += max(0.0, -float(asset.get("inventories_change", 0.0))) + max(0.0, float(asset.get("demand_change", 0.0)) - float(asset.get("production_change", 0.0)))
        samples += 1
    scarcity = scarcity / samples if samples else 0.0
    regional_scarcity = _regional_cpi_pressure(land)
    raw = ((energy - 1.0) * 0.0035) + ((food - 1.0) * 0.0025) + ((metals - 1.0) * 0.0018) + (scarcity * 0.038) + (regional_scarcity * 0.018)
    return max(-0.0035, min(0.0060, raw))


def _regional_cpi_pressure(land):
    if land is None:
        return 0.0
    country = getattr(daten, "makro", {}).get(land, {})
    pressures = country.get("regional_pressure", {})
    if not pressures:
        return 0.0
    basket = {"FOOD": 1.20, "DRINK": 0.55, "ELC": 0.70, "REAL": 0.50, "HLTH": 0.42, "FUEL": 0.18, "MOB": 0.16, "DATA": 0.14}
    weighted = 0.0
    total = 0.0
    for code, weight in basket.items():
        weighted += max(-0.10, min(0.35, float(pressures.get(code, 0.0)))) * weight
        total += weight
    return weighted / total if total else 0.0


def _average_price_level(assets, tickers):
    values = [float(assets[ticker].get("kurs", 100.0)) / 100.0 for ticker in tickers if ticker in assets]
    return sum(values) / len(values) if values else 1.0

# DATEI: makro.py ENDE
