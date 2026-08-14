# DATEI: trading.py START
import tkinter as tk
from tkinter import messagebox
import daten
import layout
import engine
from kojakstreet.core.trading import (
    TradeError,
    exchange_currency,
    execute_spot_trade,
    open_perpetual,
    settle_perpetual,
)

# NEU HINZUGEFÜGTE HILFSFUNKTION
def get_currency_symbol(currency_code):
    """Gibt das Währungssymbol oder den Code selbst zurück, wenn kein Symbol definiert ist."""
    return daten.LAENDER.get(currency_code, currency_code)

def _gd_strength():
    return max(0.0001, daten.rohstoffe["XAU"]["kurs"] / 100.0)

def _currency_strength(land):
    return _gd_strength() if land == "GD" else max(0.0001, daten.waehrungen_staerke.get(land, 1.0))

def _betrag_in_gd(betrag_lokal, land):
    return betrag_lokal * (_currency_strength(land) / _gd_strength())

def _bezahle_lokal_oder_gd(betrag_lokal, land):
    if land == "USA":
        if daten.bargeld >= betrag_lokal:
            daten.bargeld -= betrag_lokal
            return True
    elif daten.forex_depot.get(land, 0.0) >= betrag_lokal:
        daten.forex_depot[land] -= betrag_lokal
        return True
    gd_betrag = _betrag_in_gd(betrag_lokal, land)
    if daten.forex_depot.get("GD", 0.0) >= gd_betrag:
        daten.forex_depot["GD"] -= gd_betrag
        return True
    return False

def execute_trade(modus):
    """Verarbeitet den Kauf und Verkauf von Wertpapieren (Aktien, Kryptos, Rohstoffe, Fonds)."""
    import tab_maerkte
    import tab_depot
    
    # 1. Weiche: Woher kommt der Befehl?
    is_depot = "DEPOT" in modus
    modus_clean = modus.replace("_DEPOT", "") # Macht aus KAUF_DEPOT einfach KAUF
    
    if is_depot:
        # Depot-Modus: Hole Ticker und Stückzahl aus dem Depot-Tab
        if not tab_depot.tree_dep or not tab_depot.ent_dep_stueck: return
        selected = tab_depot.tree_dep.selection()
        if not selected:
            layout.zeige_status_meldung("⚠️ KEIN ASSET IM DEPOT AUSGEWÄHLT!", "ROT")
            return
        values = tab_depot.tree_dep.item(selected, "values")
        ticker = values[0]
        # Versuche die Stückzahl aus dem Depot-Feld zu lesen
        try:
            stueck = float(tab_depot.ent_dep_stueck.get())
            if stueck <= 0: raise ValueError
        except ValueError:
            layout.zeige_status_meldung("❌ UNGÜLTIGE STÜCKZAHL!", "ROT")
            return
        # Bestimme Kategorie automatisch über den Ticker
        if ticker in daten.aktien: sel_kat = "Aktien"
        elif ticker in daten.rohstoffe: sel_kat = "Rohstoffe"
        elif ticker in daten.kryptos: sel_kat = "Kryptos"
        else: sel_kat = "Fonds"
    else:
        # Markt-Modus: Bestehendes Verhalten
        if not tab_maerkte.tree_mkt or not tab_maerkte.ent_stueck: return
        selected = tab_maerkte.tree_mkt.selection()
        if not selected:
            layout.zeige_status_meldung("⚠️ KEIN ASSET AUSGEWÄHLT!", "ROT")
            return
        try:
            stueck = float(tab_maerkte.ent_stueck.get())
            if stueck <= 0: raise ValueError
        except ValueError:
            layout.zeige_status_meldung("❌ UNGÜLTIGE STÜCKZAHL!", "ROT")
            return
        values = tab_maerkte.tree_mkt.item(selected, "values")
        ticker = values[0]
        sel_kat = tab_maerkte.cb_kat.get()

        if isinstance(ticker, str) and (ticker.startswith("IDX_") or ticker in getattr(daten, "indizes", {})):
            layout.zeige_status_meldung("❌ INDIZES SIND NICHT HANDELBAR!", "ROT")
            return

    side = "BUY" if modus_clean == "KAUF" else "SELL"
    try:
        execute_spot_trade(daten, ticker, stueck, side)
    except TradeError as exc:
        layout.zeige_status_meldung(f"TRADE FEHLGESCHLAGEN: {exc}", "ROT")
        return

    if side == "BUY":
        layout.zeige_status_meldung(f"{stueck:.0f}x {ticker} ERFOLGREICH GEKAUFT!", "#00ffaa")
    else:
        layout.zeige_status_meldung(f"{stueck:.0f}x {ticker} ERFOLGREICH VERKAUFT!", "#ff3333")
    layout.update_ui_graphics()
    return

    # 2. Asset-Daten laden
    if sel_kat == "Aktien": src = daten.aktien
    elif sel_kat == "Rohstoffe": src = daten.rohstoffe
    elif sel_kat == "Kryptos": src = daten.kryptos
    else: src = daten.fonds
    
    asset = src[ticker]
    kurs = asset["kurs"]
    land = asset.get("land", "GD")
    
    # 3. Handelslogik
    if modus_clean == "KAUF":
        if land == "USA":
            gesamtkosten_usd = stueck * kurs
            if daten.bargeld < gesamtkosten_usd:
                layout.zeige_status_meldung("❌ UNZUREICHENDES BARGELD (USD)!", "ROT")
                return
            daten.bargeld -= gesamtkosten_usd
        else:
            s_lokal = daten.waehrungen_staerke.get(land, 1.0)
            s_usa = daten.waehrungen_staerke.get("USA", 1.0)
            if land == "GD":
                gold_preis_usd = daten.rohstoffe["XAU"]["kurs"]
                gesamtkosten_usd = stueck * kurs * (gold_preis_usd / 100.0)
            else:
                gesamtkosten_usd = stueck * kurs * (s_usa / s_lokal)
            kosten_lokal = stueck * kurs
            if daten.forex_depot.get(land, 0.0) < kosten_lokal:
                layout.zeige_status_meldung(f"❌ UNZUREICHENDE MITTEL IN {land}!", "ROT")
                return
            daten.forex_depot[land] -= kosten_lokal
            
        if ticker not in daten.depot:
            daten.depot[ticker] = {"stueck": 0.0, "kaufkurs": 0.0}
        
        alt_stk = daten.depot[ticker]["stueck"]
        alt_kurs = daten.depot[ticker]["kaufkurs"]
        neues_stk = alt_stk + stueck
        daten.depot[ticker]["kaufkurs"] = ((alt_stk * alt_kurs) + (stueck * kurs)) / neues_stk
        daten.depot[ticker]["stueck"] = neues_stk
        layout.zeige_status_meldung(f"🟢 {stueck:.0f}x {ticker} ERFOLGREICH GEKAUFT!", "#00ffaa")
        
    elif modus_clean == "VERKAUF":
        # 1. Kategorie automatisch bestimmen
        if ticker in daten.aktien: src = daten.aktien
        elif ticker in daten.rohstoffe: src = daten.rohstoffe
        elif ticker in daten.kryptos: src = daten.kryptos
        else: src = daten.fonds
        
        asset = src[ticker]
        kurs = asset["kurs"]
        land = asset.get("land", "GD")

        # 2. Bestand prüfen
        if ticker not in daten.depot or daten.depot[ticker]["stueck"] < stueck:
            layout.zeige_status_meldung("❌ NICHT GENUG BESTAND IM DEPOT!", "ROT")
            return
            
        # 3. GuV berechnen und in Historie schreiben
        guv_lokal = stueck * (kurs - daten.depot[ticker]["kaufkurs"])
        
        if land == "USA":
            guv_usd = guv_lokal
        elif land == "GD":
            gold_preis_usd = daten.rohstoffe["XAU"]["kurs"]
            guv_usd = guv_lokal * (gold_preis_usd / 100.0)
        else:
            s_lokal = daten.waehrungen_staerke.get(land, 1.0)
            s_usa = daten.waehrungen_staerke.get("USA", 1.0)
            guv_usd = guv_lokal * (s_usa / s_lokal)
           
        daten.realisierte_guv_historie.append((daten.datum, guv_usd))
        
        # 4. Erlös verbuchen
        erloes_lokal = stueck * kurs
        if land == "USA":
            daten.bargeld += erloes_lokal
        else:
            daten.forex_depot[land] = daten.forex_depot.get(land, 0.0) + erloes_lokal
            
        # 5. Depotbestand reduzieren
        daten.depot[ticker]["stueck"] -= stueck
        if daten.depot[ticker]["stueck"] <= 0:
            del daten.depot[ticker]
            
        layout.zeige_status_meldung(f"🔴 {stueck:.0f}x {ticker} ERFOLGREICH VERKAUFT!", "#ff3333")

    layout.update_ui_graphics()

def execute_anleihe_zeichnung(jahre):
    """Trägt eine neue Staats- oder Unternehmensanleihe in das Depot ein."""
    import tab_anleihen
    if not tab_anleihen.tree_anl_market or not tab_anleihen.ent_anl_summe: return
    
    selected = tab_anleihen.tree_anl_market.selection()
    if not selected:
        layout.zeige_status_meldung("⚠️ KEINE ANLEIHE AUSGEWÄHLT!", "ROT")
        return
        
    try:
        nominal = float(tab_anleihen.ent_anl_summe.get())
        if nominal <= 0: raise ValueError
    except ValueError:
        layout.zeige_status_meldung("❌ UNGÜLTIGER ANLAGE-BETRAG!", "ROT")
        return
        
    values = tab_anleihen.tree_anl_market.item(selected, "values")
    ticker = values[0]
    kategorie = values[2]
    
    col_idx = 3 if jahre == 3 else 4 if jahre == 5 else 5
    zins = float(values[col_idx].replace("%", "")) / 100.0
    
    # 1. Land ermitteln
    if kategorie == "Staat": land = ticker.replace("GOV_", "")
    else: land = daten.aktien[ticker]["land"]
    sym = get_currency_symbol(land)
    
    # 2. Bezahlen aus dem richtigen Topf
    if land == "USA":
        if daten.bargeld < nominal:
            layout.zeige_status_meldung(f"❌ UNZUREICHENDES BARGELD ({sym})!", "#ff3333")
            return
        daten.bargeld -= nominal
    else:
        if daten.forex_depot.get(land, 0.0) < nominal:
            layout.zeige_status_meldung(f"❌ UNZUREICHENDES GUTHABEN ({sym})!", "#ff3333")
            return
        daten.forex_depot[land] -= nominal
        
    resttage = jahre * 365
    
    neue_anl = {
        "nominal": nominal,
        "zins": zins,
        "resttage": resttage,
        "zinstage_zaehler": 0,
        "land": land  # WICHTIG: Das Land wird gespeichert!
    }
    
    if kategorie == "Staat":
        neue_anl["typ"] = "STAAT"
    else:
        neue_anl["typ"] = "UNTERNEHMEN"
        neue_anl["ticker"] = ticker
        neue_anl["startkurs"] = daten.aktien[ticker]["kurs"]
        
    daten.anleihen.append(neue_anl)
    layout.zeige_status_meldung(f"💼 ANLEIHE {ticker} ({jahre}J) GEZEICHNET!", "#00ffaa")
    layout.update_ui_graphics()

def handle_kredit(modus):
    """Verarbeitet die Aufnahme und Tilgung von Krediten in verschiedenen Regionen."""
    import tab_depot
    if not tab_depot.cb_kr_land or not tab_depot.ent_kredit: return
    
    land = tab_depot.cb_kr_land.get()
    try:
        betrag = float(tab_depot.ent_kredit.get())
        if betrag <= 0: raise ValueError
    except ValueError:
        layout.zeige_status_meldung("❌ UNGÜLTIGER KREDITBETRAG!", "ROT")
        return
        
    if modus == "LEIHEN":
        daten.kredite[land] = daten.kredite.get(land, 0.0) + betrag
        if land == "USA":
            daten.bargeld += betrag
        else:
            daten.forex_depot[land] = daten.forex_depot.get(land, 0.0) + betrag
        layout.zeige_status_meldung(f"💸 {betrag:.2f} Kredit in {land} aufgenommen!", "#00ffaa")
        
    elif modus == "TILGEN":
        if daten.kredite.get(land, 0.0) < betrag:
            layout.zeige_status_meldung("❌ BETRAG ÜBERSTEIGT OFFENE SCHULDEN!", "ROT")
            return
            
        if land == "USA":
            if daten.bargeld < betrag:
                layout.zeige_status_meldung("❌ UNZUREICHENDES CASH ZUM TILGEN!", "ROT")
                return
            daten.bargeld -= betrag
        else:
            if daten.forex_depot.get(land, 0.0) < betrag:
                layout.zeige_status_meldung("❌ UNZUREICHENDE MITTEL IN LOKALWÄHRUNG!", "ROT")
                return
            daten.forex_depot[land] -= betrag
            
        daten.kredite[land] -= betrag
        layout.zeige_status_meldung(f"✅ {betrag:.2f} Kredit in {land} getilgt!", "#00ffaa")
        
    layout.update_ui_graphics()

# ... existing code ...

def fx_calc_callback(event=None):
    """Berechnet live den Wechselkurs im Forex-Tab vor dem Tausch."""
    import tab_forex
    if not tab_forex.cb_basis or not tab_forex.cb_ziel or not tab_forex.ent_fx_summe: return
    
    l1 = tab_forex.cb_basis.get()
    l2 = tab_forex.cb_ziel.get()
    if l1 == l2: return
    
    try:
        betrag = float(tab_forex.ent_fx_summe.get())
    except ValueError:
        return
        
    gold_preis_usd = daten.rohstoffe["XAU"]["kurs"]
    
    # Einheitliche Umrechnungsbasis für GD in Währungsstärke
    # Wir nehmen an, 1 GD-Einheit in der "Stärke"-Skala entspricht dem USD-Wert von 1/100 des Goldpreises.
    gd_strength_equivalent = (gold_preis_usd / 100.0) 
    
    s1 = daten.waehrungen_staerke.get(l1, 0.0) if l1 != "GD" else gd_strength_equivalent
    s2 = daten.waehrungen_staerke.get(l2, 0.0) if l2 != "GD" else gd_strength_equivalent
    
    if s1 <= 0 or s2 <= 0: # Division durch Null vermeiden
        tab_forex.lbl_fx_bestand.config(text="Erhalt: FEHLER")
        return

    kurs = s1 / s2
    ergebnis = betrag * kurs
    
    # Symbol-Abfrage durch Hilfsfunktion
    sym2 = get_currency_symbol(l2)
    tab_forex.lbl_fx_bestand.config(text=f"Erhalt: {ergebnis:.2f} {sym2}")

def fx_trade_callback():
    """Führt den Währungstausch auf dem Forex-Markt aus (inklusive GD)."""
    import tab_forex
    if not tab_forex.combo_l1 or not tab_forex.combo_l2 or not tab_forex.ent_menge: return
    
    l1 = tab_forex.combo_l1.get()
    l2 = tab_forex.combo_l2.get()
    
    if l1 == l2:
        layout.zeige_status_meldung("❌ BASIS- UND ZIELWÄHRUNG SIND GLEICH!", "ROT")
        return
        
    try:
        betrag = float(tab_forex.ent_menge.get())
        if betrag <= 0: raise ValueError
    except ValueError:
        layout.zeige_status_meldung("❌ UNGÜLTIGER TAUSCHBETRAG!", "ROT")
        return
        
    try:
        erhalt = exchange_currency(daten, l1, l2, betrag)
    except TradeError as exc:
        layout.zeige_status_meldung(f"FX-TAUSCH FEHLGESCHLAGEN: {exc}", "ROT")
        return

    sym1_display = get_currency_symbol(l1)
    sym2_display = get_currency_symbol(l2)
    layout.zeige_status_meldung(f"{betrag:.2f} {sym1_display} GETAUSCHT IN {erhalt:.2f} {sym2_display}!", "#00ffaa")
    layout.update_ui_graphics()
    return

    # Bestand prüfen
    if l1 == "USA": b1 = daten.bargeld
    else: b1 = daten.forex_depot.get(l1, 0.0)
    
    if b1 < betrag:
        layout.zeige_status_meldung("❌ UNZUREICHENDES GUTHABEN!", "ROT")
        return
        
    gold_preis_usd = daten.rohstoffe["XAU"]["kurs"]
    gd_strength_equivalent = (gold_preis_usd / 100.0)
    
    s1 = daten.waehrungen_staerke.get(l1, 0.0) if l1 != "GD" else gd_strength_equivalent
    s2 = daten.waehrungen_staerke.get(l2, 0.0) if l2 != "GD" else gd_strength_equivalent
    
    if s1 <= 0 or s2 <= 0:
        layout.zeige_status_meldung("❌ FEHLER: UNGÜLTIGE WÄHRUNGSSTÄRKE!", "ROT")
        return

    kurs = s1 / s2
    erhalt = betrag * kurs
    
    # Abzug
    if l1 == "USA": daten.bargeld -= betrag
    else: daten.forex_depot[l1] -= betrag
    
    # Gutschrift
    if l2 == "USA": daten.bargeld += erhalt
    else: daten.forex_depot[l2] = daten.forex_depot.get(l2, 0.0) + erhalt
    
    sym1_display = get_currency_symbol(l1)
    sym2_display = get_currency_symbol(l2)
    layout.zeige_status_meldung(f"💲 {betrag:.2f} {sym1_display} GETAUSCHT IN {erhalt:.2f} {sym2_display}!", "#00ffaa")
    layout.update_ui_graphics()

def execute_perpetual_trade(ticker, typ, hebel, margin_lokal):
    """Öffnet eine neue Perpetual-Position in Lokalwährung."""
    import daten
    import layout

    try:
        open_perpetual(daten, ticker, typ, hebel, margin_lokal)
    except TradeError as exc:
        layout.zeige_status_meldung(f"FUTURE FEHLGESCHLAGEN: {exc}", "#ff3333")
        return
    layout.zeige_status_meldung(f"{hebel}x {typ}-POSITION AUF {ticker} EROEFFNET!", "#00ffaa")
    layout.update_ui_graphics()
    return
    
    # 1. Kurs und Währung (Land) ermitteln
    if ticker in daten.aktien: 
        cur_k, land = daten.aktien[ticker]["kurs"], daten.aktien[ticker]["land"]
    elif ticker in daten.rohstoffe: 
        cur_k, land = daten.rohstoffe[ticker]["kurs"], "GD"
    elif ticker in daten.kryptos: 
        cur_k, land = daten.kryptos[ticker]["kurs"], "GD"
    elif ticker in daten.fonds: 
        cur_k, land = daten.fonds[ticker]["kurs"], daten.fonds[ticker]["ziel"]
    else: return
    
    sym = get_currency_symbol(land)

    # 2. Cash-Check in der richtigen Währung
    if land == "USA":
        if daten.bargeld < margin_lokal:
            layout.zeige_status_meldung(f"❌ UNZUREICHENDES BARGELD ({sym})!", "#ff3333")
            return
        daten.bargeld -= margin_lokal
    else:
        if daten.forex_depot.get(land, 0.0) < margin_lokal:
            layout.zeige_status_meldung(f"❌ UNZUREICHENDES GUTHABEN ({sym})!", "#ff3333")
            return
        daten.forex_depot[land] -= margin_lokal
        
    zusatz_groesse = (margin_lokal * hebel) / cur_k
    pos_key = f"{ticker}_{typ}"
    
    # 3. Position anlegen
    if pos_key in daten.perpetuals:
        pos = daten.perpetuals[pos_key]
        alt_groesse = pos["groesse"]
        alt_ep = pos["einstiegskurs"]
        
        neu_ep = ((alt_groesse * alt_ep) + (zusatz_groesse * cur_k)) / (alt_groesse + zusatz_groesse)
        pos["einstiegskurs"] = neu_ep
        pos["groesse"] += zusatz_groesse
        pos["margin"] += margin_lokal
        layout.zeige_status_meldung(f"🔄 MARGIN HINZUGEFÜGT: {typ} auf {ticker}. Neuer EP: {neu_ep:.2f} {sym}", "#00ffaa")
    else:
        daten.perpetuals[pos_key] = {
            "ticker": ticker, "typ": typ, "hebel": hebel, "margin": margin_lokal,
            "groesse": zusatz_groesse, "einstiegskurs": cur_k, "land": land
        }
        layout.zeige_status_meldung(f"🚀 {hebel}x {typ}-POSITION AUF {ticker} ERÖFFNET!", "#00ffaa")
        
    layout.update_ui_graphics()

def close_perpetual_position(pos_key):
    """Schließt eine Hebelposition, berechnet den PnL und gibt Margin + PnL ans Cash zurück."""
    import daten
    import layout
    
    if pos_key not in daten.perpetuals: return

    try:
        result = settle_perpetual(daten, pos_key)
    except TradeError as exc:
        layout.zeige_status_meldung(f"SCHLIESSEN FEHLGESCHLAGEN: {exc}", "ROT")
        return
    pnl = float(result["pnl"])
    farbe = "#00ffaa" if pnl >= 0 else "#ff3333"
    vorzeichen = "+" if pnl > 0 else ""
    layout.zeige_status_meldung(
        f"POSITION {result['ticker']} GESCHLOSSEN. GuV: {vorzeichen}{pnl:.2f} {result['region']}",
        farbe,
    )
    layout.update_ui_graphics()
    return
    
    pos = daten.perpetuals[pos_key]
    ticker = pos["ticker"]
    typ = pos["typ"]
    ep = pos["einstiegskurs"]
    groesse = pos["groesse"]
    margin = pos["margin"]
    
    if ticker in daten.aktien: cur_k = daten.aktien[ticker]["kurs"]
    elif ticker in daten.rohstoffe: cur_k = daten.rohstoffe[ticker]["kurs"]
    elif ticker in daten.kryptos: cur_k = daten.kryptos[ticker]["kurs"]
    else: cur_k = daten.fonds[ticker]["kurs"]
    
    # Gewinn/Verlust (PnL) berechnen
    if typ == "LONG": pnl = (cur_k - ep) * groesse
    else: pnl = (ep - cur_k) * groesse
        
    land = pos.get("land", "USA")
    sym = get_currency_symbol(land)
    
    # Zurück aufs richtige Konto (verhindert negative Auszahlung)
    erloes = margin + pnl
    if erloes < 0: erloes = 0.0
    
    if land == "USA": daten.bargeld += erloes
    else: daten.forex_depot[land] = daten.forex_depot.get(land, 0.0) + erloes
        
    # PnL in USD umrechnen für die globale GuV-Historie
    if land == "USA": pnl_usd = pnl
    elif land == "GD": pnl_usd = pnl * (daten.rohstoffe["XAU"]["kurs"] / 100.0)
    else: pnl_usd = pnl * (daten.waehrungen_staerke.get("USA", 1.0) / daten.waehrungen_staerke.get(land, 1.0))
        
    daten.realisierte_guv_historie.append((daten.datum, pnl_usd))
    del daten.perpetuals[pos_key]
    
    farbe = "#00ffaa" if pnl >= 0 else "#ff3333"
    vorzeichen = "+" if pnl > 0 else ""
    layout.zeige_status_meldung(f"💰 POSITION {ticker} {typ} GESCHLOSSEN. GuV: {vorzeichen}{pnl:.2f} {sym}", farbe)
    layout.update_ui_graphics()

# DATEI: trading.py ENDE
