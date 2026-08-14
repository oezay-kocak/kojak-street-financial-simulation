# DATEI: engine.py START 
import random
import sys
from datetime import datetime, timedelta
import daten
import makro
import markt
import anleihen
import kredite
import layout
import tab_news
import charts
from kojakstreet.core.companies import (
    bankrupt_tickers,
    fill_company_universe,
    ensure_company_universe,
    rating_from_finances,
    remove_bankrupt_companies,
    update_company_finances,
)
from kojakstreet.core.ohlc import normalize_commodity_supply_key
from kojakstreet.core.production_chains import update_production_chain

def _safe_ui_news_update(aktuelle_zeit_str, voller_text, kat):
    # === UI-SCHUTZ: Verhindert Abstürze bei gelöschten UI-Elementen ===
    if not getattr(daten, 'SPIEL_AKTIV', True):
        return

    if not tab_news.tree_news or not tab_news.txt_detail: return
    try:
        t_color = "neutral"
        if kat == "GRUEN": t_color = "positive"
        elif kat == "ROT": t_color = "negative"
        elif kat == "ZENTRALBANK": t_color = "macro"
        
        zeilen = voller_text.split("\n")
        schlagzeile = zeilen[0].strip() if zeilen else "EILMELDUNG"
        
        neues_item = tab_news.tree_news.insert("", 0, values=(aktuelle_zeit_str, schlagzeile), tags=(t_color,))
        tab_news.tree_news.selection_set(neues_item)
        tab_news.tree_news.focus(neues_item)
        
        tab_news.txt_detail.config(state="normal")
        tab_news.txt_detail.delete("1.0", "end")
        tab_news.txt_detail.insert("1.0", voller_text)
        tab_news.txt_detail.config(state="disabled")
    except Exception:
        pass

def add_news(text, kategorie="WEISS"):
    if "Gewinn" in text or "Verlust" in text: return
    zeit_str = daten.datum.strftime("%d.%m.%Y")
    daten.NEWS_SPEICHER.insert(0, (zeit_str, text, kategorie))
    if len(daten.NEWS_SPEICHER) > 50: daten.NEWS_SPEICHER.pop()
    
    if layout.root:
        layout.root.after_idle(lambda: _safe_ui_news_update(zeit_str, text, kategorie))
    
    daten.spiel_pausiert = True
    if layout.btn_pse:
        layout.style_button(layout.btn_pse, "success")
        layout.btn_pse.config(text="WEITER")

def initialisiere_neues_spiel():
    daten.datum = getattr(daten, "START_DATUM", datetime(1990, 1, 1))
    daten.LETZTER_REPORT_MONAT = -1
    daten.LETZTER_ZINS_TAG = None  # Reset für das neue Spiel
    daten.gli_index = 15420.0
    daten.GLI_HISTORIE = []
    fiktiver_wert = 15150.0
    for i in range(120):
        fiktiver_wert += random.uniform(-12.0, 16.0)
        daten.GLI_HISTORIE.append(fiktiver_wert)
    
    daten.GLI_HISTORIE.append(daten.gli_index)
    ensure_company_universe(daten, reset=True)
    
    for land in daten.LAENDER:
        daten.MAKRO_HISTORIE[f"{land}_ZINS"] = []
        daten.MAKRO_HISTORIE[f"{land}_BIP"] = []
        daten.MAKRO_HISTORIE[f"{land}_INF"] = []
        daten.MAKRO_HISTORIE[f"{land}_ALO"] = []
    
    for t, d in daten.aktien.items():
        d["gewinn_kennzahl"] = round(random.uniform(-1.0, 1.5), 1)
    
    makro.update_global_liquidity_index()
    markt.update_markt_kurse()

def markt_update_tag():
    # === SCHUTZ GEGEN SCHNELLES KLICKEN / NEUSTART ===
    if not getattr(daten, 'SPIEL_AKTIV', True):
        return

    if daten.spiel_pausiert: return
    
    # -------------------------------------------------------------------------
    # MONATLICHES INTERVALL AM 15. (BERICHT ERZEUGEN & KENNZAHLEN ANSTOSSEN)
    # -------------------------------------------------------------------------
    report_monat_key = daten.datum.year * 100 + daten.datum.month
    report_bereits_erledigt = (
        daten.LETZTER_REPORT_MONAT == report_monat_key
        or (daten.LETZTER_REPORT_MONAT == daten.datum.month and daten.datum.year <= 1990)
    )
    if daten.datum.day == 15 and not report_bereits_erledigt:
        # ABSOLUT KRITISCHER FIX: Sofort für diesen Monat verriegeln, damit keine Endlosschleife entsteht!
        daten.LETZTER_REPORT_MONAT = report_monat_key
        
        # Führt das monatliche Update der Makroökonomie durch
        makro.update_makro_oekonomie(add_news)
        
        # Fundamentaldaten-Update berechnen
        s_en = (daten.rohstoffe["CL"]["kurs"] + daten.rohstoffe["TTF"]["kurs"]) / 200.0
        s_me = (daten.rohstoffe["HG"]["kurs"] + daten.rohstoffe["LIT"]["kurs"]) / 200.0
        
        for t, d in daten.aktien.items():
            ergebnis = random.uniform(-0.18, 0.18)
            ergebnis += float(d.get("production_score", 0.0)) * 0.32
            ergebnis += (float(d.get("capacity_utilization", 0.85)) - 0.85) * 0.18
            ergebnis -= float(d.get("supply_chain_shortage", 0.0)) * 0.10
            if daten.aktives_event and d["land"] in daten.aktives_event["laender"]: ergebnis -= 0.35 
            
            d["gewinn_kennzahl"] = max(-3.0, min(3.0, round(random.uniform(-1.0, 1.0) + (ergebnis * 12.0), 1)))
            d["news_momentum"] = ergebnis
            land_bip_prozent = daten.makro.get(d["land"], {}).get("bip_prozent", 0.002)
            br = d["branche"]
            br_faktor = 1.0
            if br in ["Transport und Logistik", "Automobil", "Chemie", "Maschinenbau"]:
                br_faktor *= max(0.70, 1.0 - (s_en - 1.0) * 0.25)
            elif br in ["Öl und Gas", "Stromerzeuger"]:
                br_faktor *= min(1.40, 1.0 + (s_en - 1.0) * 0.30)
            if br == "Technologie":
                br_faktor *= max(0.75, 1.0 - (s_me - 1.0) * 0.20)
            
            d["eps"] = max(0.1, d.get("eps", 5.0) * (1.0 + land_bip_prozent + (ergebnis * 0.15)) * br_faktor)
            update_company_finances(
                d,
                local_rate=float(daten.makro.get(d["land"], {}).get("zins", 0.035)),
                sector_factor=br_faktor,
            )
            
            # --- NEUES RATING-SYSTEM ---
            aktuelles_rating = d.get("rating", "BB")
            r_idx = daten.RATINGS.index(aktuelles_rating) if aktuelles_rating in daten.RATINGS else 4
            
            # Rating verbessern oder verschlechtern (basierend auf der gewinn_kennzahl)
            if d["gewinn_kennzahl"] >= 1.5 and d["news_momentum"] > 0:
                r_idx = max(0, r_idx - 1)  # Ein Rating nach oben (Richtung AAA)
            elif d["gewinn_kennzahl"] <= -1.5 or d["news_momentum"] < -0.1:
                r_idx = min(len(daten.RATINGS) - 1, r_idx + 1) # Ein Rating nach unten (Richtung C)
                
            d["rating"] = daten.RATINGS[rating_from_finances(d, r_idx)]
            # ---------------------------
            
            if t in daten.depot and d["kurs"] > 10.0:
                if land_bip_prozent > 0 or d.get("news_momentum", 0) > 0:
                    gesamt_div = daten.depot[t]["stueck"] * (d["eps"] * random.uniform(0.01, 0.03))
                    if d["land"] == "USA": daten.bargeld += gesamt_div
                    else: daten.forex_depot[d["land"]] = daten.forex_depot.get(d["land"], 0.0) + gesamt_div

        insolvente_ticker = bankrupt_tickers(daten)
        if insolvente_ticker:
            namen = [daten.aktien[ticker].get("name", ticker) for ticker in insolvente_ticker[:3]]
            remove_bankrupt_companies(daten, insolvente_ticker)
            neue = fill_company_universe(daten)
            add_news(
                " INSOLVENZ: "
                + ", ".join(namen)
                + f" ist zahlungsunfaehig. {len(neue)} neue Boersengaenge ersetzen die Ausfaelle.",
                "ROT",
            )
        
        for t, d in daten.rohstoffe.items():
            ergebnis = random.uniform(-0.12, 0.15)
            if daten.aktives_event and daten.aktives_event["typ"] in ["ENERGIE", "BILATERAL"]: ergebnis -= 0.40
            d["news_momentum"] = ergebnis
            d["foerder_menge"] = max(-3.0, min(3.0, normalize_commodity_supply_key(d) * 0.70 + (ergebnis * 15.0) * 0.30))
        
        update_production_chain(daten)

        for t, d in daten.kryptos.items():
            ergebnis = random.uniform(-0.25, 0.30)
            d["netzwerk_aktivitaet"] = max(-3.0, min(3.0, d.get("netzwerk_aktivitaet", 0.0) * 0.75 + (ergebnis * 8.0) * 0.25))
            d["netzwerk_fees"] = max(-3.0, min(3.0, d["netzwerk_aktivitaet"] * 1.1 + random.uniform(-0.4, 0.4)))
            d["gebühren"] = max(500.0, 50000.0 * ((d["netzwerk_aktivitaet"] + 4.0) / 4.0) * (d["kurs"] / 100.0))
            if t in daten.depot:
                daten.bargeld += (d["gebühren"] / 1000000.0) * daten.depot[t]["stueck"] * random.uniform(0.01, 0.03)
        
        # Die neuen Wechselkurse berechnen, UI updaten, Charts zeichnen
        markt.update_markt_kurse()
        
        # Den Tag beenden und auf den 16. schalten, bevor add_news die Schleife pausiert
        daten.datum += timedelta(days=1)
        layout.update_ui_graphics()
        charts.aktualisiere_offene_charts()
        return

    # REGULÄRER TAGES-ABLAUF
    # === SCHRITT 2 SCHUTZFILTER: Altdaten-Bereinigung für GD-Land ===
    if daten.aktives_event and "GD" in daten.aktives_event.get("laender", []):
        daten.aktives_event = None

    if daten.aktives_event:
        if not hasattr(daten, 'event_dauer'): daten.event_dauer = 0
        daten.event_dauer -= 1
        if daten.event_dauer <= 0:
            add_news(f" NEWS: Das Sonderereignis '{daten.aktives_event['name']}' ist offiziell beendet. Die Märkte stabilisieren sich.", "ZENTRALBANK")
            daten.aktives_event = None
    
    if not daten.aktives_event and random.random() < 0.008:
        krisen_liste = [
            {
                "name": "GENERALSTREIK & UNRUHEN", "typ": "NATIONAL",
                "laender": [random.choice(list(daten.LAENDER.keys()))], "dauer": random.randint(30, 90), "bip_makel": -0.035,
                "text": "Massive Generalstreiks legen die Infrastruktur und Fabriken in {} lahm! Das BIP bricht ein."
            },
            {
                "name": "GEOPOLITISCHER KONFLIKT", "typ": "BILATERAL",
                "laender": random.sample(list(daten.LAENDER.keys()), 2), "dauer": random.randint(60, 120), "bip_makel": -0.025,
                "text": "Schwere geopolitische Spannungen und Handelsblockaden zwischen {} und {}! Lieferketten kollabieren."
            },
            {
                "name": "LIEFERENGPASS & EMBARGO", "typ": "ENERGIE",
                "laender": [random.choice(["USA", "EU", "China"])], "dauer": random.randint(45, 90), "bip_makel": -0.020,
                "text": "Ein schwerer Lieferengpass erschüttert {}. Energie- und Rohstoffexporte wurden drastisch gedrosselt!"
            }
        ]
        ev = random.choice(krisen_liste)
        daten.event_dauer = ev["dauer"]
        formatiert_text = ev["text"].format(ev["laender"]) if len(ev["laender"]) == 1 else ev["text"].format(ev["laender"], ev["laender"])
        daten.aktives_event = {"name": ev["name"], "laender": ev["laender"], "bip_makel": ev["bip_makel"], "typ": ev["typ"]}
        add_news(f" ACHTUNG - EILMELDUNG: {ev['name']}!\n\n{formatiert_text}\nBetroffene Regionen haben für die nächsten {ev['dauer']} Tage mit schweren wirtschaftlichen Schäden zu kämpfen.", "ROT")
    
    makro.update_global_liquidity_index()
    kredite.update_kredit_zinsen()
    markt.update_markt_kurse()

    # --- NEU: PERPETUAL LIQUIDATION CHECK ---
    zu_loeschende_positionen = []
    for p_id, pos in daten.perpetuals.items():
        ticker = pos["ticker"]
        typ = pos["typ"]
        ep = pos["einstiegskurs"]
        hebel = pos["hebel"]
        
        # Aktuellen Kurs holen
        if ticker in daten.aktien: cur_k = daten.aktien[ticker]["kurs"]
        elif ticker in daten.rohstoffe: cur_k = daten.rohstoffe[ticker]["kurs"]
        elif ticker in daten.kryptos: cur_k = daten.kryptos[ticker]["kurs"]
        else: cur_k = daten.fonds[ticker]["kurs"]
        
        liquidiert = False
        if typ == "LONG":
            liq_preis = ep * (1.0 - (1.0 / hebel))
            if cur_k <= liq_preis: liquidiert = True
        elif typ == "SHORT":
            liq_preis = ep * (1.0 + (1.0 / hebel))
            if cur_k >= liq_preis: liquidiert = True
            
        if liquidiert:
            zu_loeschende_positionen.append(p_id)
            verlust = pos["margin"]
            land = pos.get("land", "USA")
            sym = daten.LAENDER.get(land, land)
            # News-Meldung in den Ticker jagen
            add_news(f" LIQUIDATION: {hebel}x {typ} auf {ticker} zwangsgeschlossen!\nDer Kurs hat die kritische Grenze erreicht. Totalverlust der Margin: {verlust:.2f} {sym}", "ROT")
            
    # Liquidierte Positionen aus dem System werfen
    for p_id in zu_loeschende_positionen:
        del daten.perpetuals[p_id]
    # ----------------------------------------
    
    anleihen.update_laufende_anleihen(add_news)
    
    if kredite.get_nettovermoegen() <= 0:
        if layout.root:
            layout.show_game_over_screen()
        return
        
    if not hasattr(daten, 'handels_tage_zaehler'): daten.handels_tage_zaehler = 0
    daten.handels_tage_zaehler += 1
    zeit_str = daten.datum.strftime("%d.%m.%Y")
    
    daten.DEPOT_VERMOEGEN_HISTORIE.append((kredite.get_nettovermoegen(), zeit_str))
    
    if makro.ist_letzter_tag_des_monats():
        # FIX: Nutzen nun die feste Variable aus daten.py, die mitspeichert wird
        if daten.LETZTER_ZINS_TAG != daten.datum:
            daten.LETZTER_ZINS_TAG = daten.datum
            makro.fuehre_monatlichen_zinsentscheid_durch(add_news)
    
    daten.datum += timedelta(days=1)
    layout.update_ui_graphics()
    charts.aktualisiere_offene_charts()
# DATEI: engine.py ENDE
