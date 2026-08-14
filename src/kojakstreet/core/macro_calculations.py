# DATEI: makro.py START
import random
from datetime import timedelta

import daten
from kojakstreet.core.expectations import record_macro_report, record_policy_report
from kojakstreet.core.fiscal import ensure_country_financials, pre_macro_impulses, update_country_financials
from kojakstreet.core.global_macro import update_global_macro
from kojakstreet.core.ratings import DEFAULT_RATING, RATINGS, rating_index


def berechne_welt_zins(daten_module=None):
    daten_module = daten if daten_module is None else daten_module
    if not hasattr(daten_module, "LAENDER") or not daten_module.LAENDER: 
        return 0.05
    summe = 0.0
    for land in daten_module.LAENDER:
        summe += daten_module.makro.get(land, {"zins": 0.05}).get("zins", 0.05)
    return summe / len(daten_module.LAENDER)

def hole_zins_umfeld_effekt(land, daten_module=None):
    daten_module = daten if daten_module is None else daten_module
    zins_historie = daten_module.MAKRO_HISTORIE.get(f"{land}_ZINS", [])
    if len(zins_historie) < 3: 
        return 0.0
    letzte_zinsen = [float(z[0] if isinstance(z, (tuple, list)) else z) for z in zins_historie[-3:]]
    return letzte_zinsen[-1] - sum(letzte_zinsen)/len(letzte_zinsen)

def ist_letzter_tag_des_monats(daten_module=None):
    daten_module = daten if daten_module is None else daten_module
    try:
        morgen = daten_module.datum + timedelta(days=1)
        return morgen.month != daten_module.datum.month
    except (AttributeError, TypeError):
        return False

def update_global_liquidity_index(daten_module=None):
    daten_module = daten if daten_module is None else daten_module
    if not hasattr(daten_module, "gli_index") or daten_module.gli_index <= 100.0:
        daten_module.gli_index = 15420.0 
    if not hasattr(daten_module, "GLI_HISTORIE"):
        daten_module.GLI_HISTORIE = []
        
    gesamt_bip = sum(daten_module.makro[l]["bip_abs"] for l in daten_module.LAENDER)
    gewichtet_zins = 0.0
    for land in daten_module.LAENDER:
        m = daten_module.makro[land]
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
    for land in daten_module.LAENDER:
        m = daten_module.makro[land]
        gewicht = m["bip_abs"] / gesamt_bip if gesamt_bip > 0 else 0.2
        hist_bs = daten_module.MAKRO_HISTORIE.get(f"{land}_BS", [])
        if len(hist_bs) > 1:
            alt_bs = hist_bs[-2][0] if isinstance(hist_bs[-2], (tuple, list)) else hist_bs[-2]
            # Monatliche prozentuale Veränderung der Bilanz berechnen
            bs_aenderungsrate = (m["balance_sheet"] - alt_bs) / alt_bs if alt_bs > 0 else 0.0
            # Auf tägliche Basis herunterskalieren (/30) und nach Wirtschaftskraft gewichten
            bs_gesamt_impuls += (bs_aenderungsrate / 30.0) * gewicht
            
    taegliches_rauschen = random.uniform(-0.0010, 0.0020)
    Gesamt_impuls = taegliche_basis_rate + qe_qt_impuls + bs_gesamt_impuls + taegliches_rauschen
    
    daten_module.gli_index = max(5000.0, daten_module.gli_index * (1.0 + Gesamt_impuls))
    daten_module.GLI_HISTORIE.append(daten_module.gli_index)
    update_global_macro(daten_module)

def fuehre_monatlichen_zinsentscheid_durch(add_news_callback, daten_module=None):
    daten_module = daten if daten_module is None else daten_module
    monat_str = daten_module.datum.strftime("%B %Y")
    zeit_str = daten_module.datum.strftime("%d.%m.%Y")
    zins_meldungen = []
    reported_values = []
    kurz_namen = {land: land[:3].upper() for land in daten_module.LAENDER}
    
    for land in daten_module.LAENDER:
        m = daten_module.makro[land]
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
            
        reported_values.append((land, m["zins"], m["balance_sheet"]))
        
        k_name = kurz_namen.get(land, land)
        msg_zeile = "Policy rate"
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
        record_policy_report(daten_module, [land for land, _rate, _balance_sheet in reported_values])
        for land, rate, balance_sheet in reported_values:
            _append_macro_history_point(daten_module, f"{land}_ZINS", rate, zeit_str)
            _append_macro_history_point(daten_module, f"{land}_BS", balance_sheet, zeit_str)

def update_makro_oekonomie(add_news_callback, daten_module=None):
    daten_module = daten if daten_module is None else daten_module
    ensure_country_financials(daten_module)
    monat_str = daten_module.datum.strftime("%B %Y")
    zeit_str = daten_module.datum.strftime("%d.%m.%Y")
    report_zeilen = []
    reported_values = []
    kurz_namen = {land: land[:3].upper() for land in daten_module.LAENDER}
    
    for land in daten_module.LAENDER:
        m = daten_module.makro[land]
        rauschen_bip = random.uniform(-0.008, 0.006)
        rauschen_inf = random.uniform(-0.003, 0.003)
        financial_impulses = pre_macro_impulses(daten_module, land)
        
        kr_makel = 0.0
        if daten_module.aktives_event and land in daten_module.aktives_event["laender"]:
            kr_makel = daten_module.aktives_event["bip_makel"]
            m["arbeitslosigkeit"] += random.uniform(0.015, 0.030)
            m["inflation"] += random.uniform(0.010, 0.025)
        
        zins_bremse = max(0.0, (m["zins"] - 0.035) * 0.65)
        if m["zins"] > 0.05: 
            zins_bremse *= 1.8 
            
        # NEU: Bilanz-Wachstums-Impuls auf Wirtschaftsentwicklung berechnen
        hist_bs = daten_module.MAKRO_HISTORIE.get(f"{land}_BS", [])
        bs_wachstum = 0.0
        if len(hist_bs) > 1:
            alt_bs = hist_bs[-2][0] if isinstance(hist_bs[-2], (tuple, list)) else hist_bs[-2]
            bs_wachstum = (m["balance_sheet"] - alt_bs) / alt_bs if alt_bs > 0 else 0.0
            
        qe_bip_impuls = max(0.0, bs_wachstum * 0.12)  # QE kurbelt Wirtschaftsleistung an
        qe_inf_impuls = bs_wachstum * 0.22           # QE heizt Inflation an, QT dämpft sie
        
        inflations_bremse = max(0.0, (m["inflation"] - 0.03) * 0.25)
        mittelwert_tendenz = (0.015 - m["bip_prozent"]) * 0.22
        zins_impuls = (0.035 - m["zins"]) * 0.25 
        
        m["bip_prozent"] = m["bip_prozent"] + zins_impuls + mittelwert_tendenz - zins_bremse - inflations_bremse + rauschen_bip + kr_makel + qe_bip_impuls + financial_impulses["growth_impulse"]
        m["bip_prozent"] = max(-0.060, min(0.045, m["bip_prozent"]))
        m["bip_abs"] = max(1000.0, m["bip_abs"] * (1.0 + m["bip_prozent"] / 12.0))
        
        natuerliche_arbeitslosigkeit = 0.052
        bip_effekt = (0.015 - m["bip_prozent"]) * 0.45
        stabilisator_alo = (natuerliche_arbeitslosigkeit - m["arbeitslosigkeit"]) * 0.18
        m["arbeitslosigkeit"] += bip_effekt + stabilisator_alo + random.uniform(-0.001, 0.001)
        
        # KORREKTUR: Cap der Arbeitslosigkeit bei 15% komplett entfernt!
        m["arbeitslosigkeit"] = max(0.020, m["arbeitslosigkeit"])
        
        arbeitsmarkt_druck = (0.048 - m["arbeitslosigkeit"]) * 0.25
        rohstoff_cpi_impuls = _commodity_cpi_impulse(daten_module, land)
        ziel_tendenz_inf = (0.020 - m["inflation"]) * 0.28
        m["inflation"] = (
            m["inflation"]
            + arbeitsmarkt_druck
            + ziel_tendenz_inf
            + qe_inf_impuls
            + financial_impulses["inflation_impulse"]
            + rohstoff_cpi_impuls
            + rauschen_inf
        )
        
        # KORREKTUR: Deflationsgrenze auf heftige -8% ausgeweitet
        m["inflation"] = max(-0.080, min(0.120, m["inflation"]))
        
        k_name = kurz_namen.get(land, land)
        update_country_financials(daten_module, land)
        report_zeilen.append(f"- {k_name}: BIP: {m['bip_prozent']*100:+.1f}% | Inf: {m['inflation']*100:+.1f}% | Alo: {m['arbeitslosigkeit']*100:.1f}% | Debt/GDP: {m['debt_to_gdp']*100:.0f}%")
        reported_values.append((land, m["bip_abs"], m["inflation"], m["arbeitslosigkeit"]))
        
    if report_zeilen and add_news_callback:
        bericht_gesamt = f" MONATLICHER WIRTSCHAFTSBERICHT ({monat_str}):\n" + "\n".join(report_zeilen)
        add_news_callback(bericht_gesamt, "ZENTRALBANK")
        record_macro_report(daten_module, [land for land, _gdp, _inflation, _unemployment in reported_values])
        for land, gdp, inflation, unemployment in reported_values:
            _append_macro_history_point(daten_module, f"{land}_BIP", gdp, zeit_str)
            _append_macro_history_point(daten_module, f"{land}_INF", inflation, zeit_str)
            _append_macro_history_point(daten_module, f"{land}_ALO", unemployment, zeit_str)
            macro = daten_module.makro[land]
            _append_macro_history_point(daten_module, f"{land}_DEBT_GDP", float(macro.get("debt_to_gdp", 0.0)), zeit_str)
            _append_macro_history_point(daten_module, f"{land}_CREDIT", float(macro.get("credit_growth", 0.0)), zeit_str)
            _append_macro_history_point(daten_module, f"{land}_DEFICIT", float(macro.get("fiscal_deficit", 0.0)), zeit_str)


def update_sovereign_ratings(daten_module=None) -> None:
    daten_module = daten if daten_module is None else daten_module
    for data in daten_module.makro.values():
        current_index = rating_index(data.get("rating", DEFAULT_RATING))
        growth = float(data.get("bip_prozent", 0.0))
        inflation = float(data.get("inflation", 0.0))
        unemployment = float(data.get("arbeitslosigkeit", 0.06))
        debt_to_gdp = float(data.get("debt_to_gdp", 0.62))
        interest_burden = float(data.get("interest_burden", 0.025))
        if growth > 0.025 and inflation < 0.035 and unemployment < 0.07 and debt_to_gdp < 0.75:
            current_index = max(0, current_index - 1)
        elif growth < -0.01 or inflation > 0.08 or unemployment > 0.12 or debt_to_gdp > 1.15 or interest_burden > 0.075:
            current_index = min(len(RATINGS) - 1, current_index + 1)
        data["rating"] = RATINGS[current_index]


def _append_macro_history_point(daten_module, key: str, value: float, date_text: str) -> None:
    history = daten_module.MAKRO_HISTORIE.setdefault(key, [])
    if history and isinstance(history[-1], (tuple, list)) and len(history[-1]) > 1 and history[-1][1] == date_text:
        history[-1] = (value, date_text, "")
    else:
        history.append((value, date_text, ""))
    if len(history) > 520:
        del history[:-520]


def _commodity_cpi_impulse(daten_module=None, land: str | None = None):
    if land is None and isinstance(daten_module, str):
        land = daten_module
        daten_module = daten
    daten_module = daten if daten_module is None else daten_module
    groups = getattr(daten_module, "rohstoffe", {})
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
    regional_scarcity = _regional_cpi_pressure(daten_module, land)
    raw = (
        ((energy - 1.0) * 0.0035)
        + ((food - 1.0) * 0.0025)
        + ((metals - 1.0) * 0.0018)
        + (scarcity * 0.038)
        + (regional_scarcity * 0.018)
    )
    return max(-0.0035, min(0.0060, raw))


def _regional_cpi_pressure(daten_module, land: str | None = None) -> float:
    if land is None and isinstance(daten_module, str):
        land = daten_module
        daten_module = daten
    if land is None:
        return 0.0
    country = getattr(daten_module, "makro", {}).get(land, {})
    pressures = country.get("regional_pressure", {})
    if not pressures:
        return 0.0
    basket = {
        "FOOD": 1.20,
        "DRINK": 0.55,
        "ELC": 0.70,
        "REAL": 0.50,
        "HLTH": 0.42,
        "FUEL": 0.18,
        "MOB": 0.16,
        "DATA": 0.14,
    }
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
