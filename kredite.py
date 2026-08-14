# DATEI: kredite.py START
import daten

def get_nettovermoegen():
    gesamt_wert_usd = daten.bargeld
    if hasattr(daten, 'forex_depot') and hasattr(daten, 'waehrungen_staerke'):
        for land, bestand in daten.forex_depot.items():
            if land != "USA" and land in daten.waehrungen_staerke and daten.waehrungen_staerke["USA"] > 0:
                gesamt_wert_usd += bestand * (daten.waehrungen_staerke[land] / daten.waehrungen_staerke["USA"])
    if hasattr(daten, 'depot'):
        for t, d in daten.depot.items():
            stk = d.get("stueck", 0)
            if stk > 0:
                kurs = 0.0
                if t in daten.aktien: kurs = daten.aktien[t]["kurs"]
                elif t in daten.rohstoffe: kurs = daten.rohstoffe[t]["kurs"]
                elif t in daten.kryptos: kurs = daten.kryptos[t]["kurs"]
                elif t in daten.fonds: kurs = daten.fonds[t]["kurs"]
                gesamt_wert_usd += (stk * kurs)
    if hasattr(daten, 'anleihen'):
        for anl in daten.anleihen: gesamt_wert_usd += anl.get("nominal", 0.0)
        
    offene_schulden_usd = 0.0
    if hasattr(daten, 'kredite') and hasattr(daten, 'waehrungen_staerke'):
        for land, schulden in daten.kredite.items():
            if land == "USA": offene_schulden_usd += schulden
            elif land in daten.waehrungen_staerke and daten.waehrungen_staerke["USA"] > 0:
                offene_schulden_usd += schulden * (daten.waehrungen_staerke[land] / daten.waehrungen_staerke["USA"])
    return gesamt_wert_usd - offene_schulden_usd

def update_kredit_zinsen():
    if hasattr(daten, 'kredite') and hasattr(daten, 'makro'):
        import layout # Importiere layout für Statusmeldungen
        for land, schulden in daten.kredite.items():
            if schulden > 0:
                m_data = daten.makro.get(land, {"zins": 0.05})
                zins_satz = m_data.get("zins", 0.05) + 0.06 
                taeglicher_zins = (schulden * zins_satz) / 365.0
                
                # FIX: Warnung bei negativem Saldo
                if land == "USA":
                    daten.bargeld -= taeglicher_zins
                    if daten.bargeld < 0 and abs(daten.bargeld) < taeglicher_zins * 2: # Warnung nur, wenn es gerade erst negativ wurde oder noch knapp ist
                        layout.zeige_status_meldung(f"🚨 ACHTUNG: Dein USD-Bargeldsaldo ist durch Kreditzinsen negativ ({daten.bargeld:.2f} $)! Tilge Schulden!", "ROT")
                else:
                    daten.forex_depot[land] = daten.forex_depot.get(land, 0.0) - taeglicher_zins
                    if daten.forex_depot[land] < 0 and abs(daten.forex_depot[land]) < taeglicher_zins * 2:
                        layout.zeige_status_meldung(f"🚨 ACHTUNG: Dein {land}-Depot ist durch Kreditzinsen negativ ({daten.forex_depot[land]:.2f} {daten.LAENDER.get(land, land)})! Tilge Schulden!", "ROT")

# DATEI: kredite.py ENDE
