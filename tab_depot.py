# DATEI: tab_depot.py START
import tkinter as tk
from tkinter import ttk
import daten
import layout
import depot_charts

tree_dep = None
tree_dep_anl = None
tree_perps = None
tree_kasse = None        # NEU: Tabelle für Hebel-Positionen
ent_perp_ticker = None   # NEU: Eingabefeld für Futures-Ticker
cb_perp_typ = None       # NEU: Auswahl Long/Short
cb_perp_hebel = None     # NEU: Auswahl Hebel (1x-5x)
ent_perp_margin = None   # NEU: Eingabefeld für Margin ($)
lbl_schuld = None
ent_kredit = None
cb_kr_land = None
ent_dep_stueck = None

def baue_tab(notebook, kredit_cmd, trade_cmd, chart_cmd):
    global tree_dep, tree_dep_anl, tree_perps, ent_perp_ticker, cb_perp_typ, cb_perp_hebel, ent_perp_margin, lbl_schuld, ent_kredit, cb_kr_land, ent_dep_stueck, tree_kasse
    
    tab_dep = tk.Frame(notebook, bg=layout.BG_MAIN)
    notebook.add(tab_dep, text="DEPOT")
    
    nb_dep = ttk.Notebook(tab_dep)
    nb_dep.pack(fill="both", expand=True, padx=12, pady=12)
    
    sub_dep_assets = tk.Frame(nb_dep, bg=layout.BG_MAIN)
    sub_dep_bonds = tk.Frame(nb_dep, bg=layout.BG_MAIN)
    sub_dep_perps = tk.Frame(nb_dep, bg=layout.BG_MAIN)
    sub_dep_kasse = tk.Frame(nb_dep, bg=layout.BG_MAIN)

    nb_dep.add(sub_dep_assets, text=" WERTPAPIERE ")
    nb_dep.add(sub_dep_bonds, text=" LAUFENDE ANLEIHEN ")
    nb_dep.add(sub_dep_perps, text=" FUTURES ")
    nb_dep.add(sub_dep_kasse, text=" WÄHRUNGSBESTAND ")

    # -------------------------------------------------------------------------
    # NEU: INTERFACE-STRUKTUR FÜR DAS FUTURES-TRADING-MONITOR-SYSTEM
    # -------------------------------------------------------------------------
    tree_kasse = ttk.Treeview(sub_dep_kasse, columns=("Waehrung", "Bestand", "WertTerminal"), show="headings", height=12)
    tree_kasse.heading("Waehrung", text="Währung Sektor")
    tree_kasse.heading("Bestand", text="Verfügbarer Kontostand (Lokal)")
    tree_kasse.heading("WertTerminal", text="Wert in gewählter Terminal-Währung")
    tree_kasse.column("Waehrung", width=150, anchor="center")
    tree_kasse.column("Bestand", width=250, anchor="e")
    tree_kasse.column("WertTerminal", width=250, anchor="e")
    tree_kasse.pack(fill="both", expand=True, padx=10, pady=10)

    tree_perps = ttk.Treeview(sub_dep_perps, columns=("Ticker", "Typ", "Hebel", "Groesse", "EP", "Liq", "Kurs", "PnL"), show="headings", height=10)
    tree_perps.heading("Ticker", text="Symbol")
    tree_perps.heading("Typ", text="Typ")
    tree_perps.heading("Hebel", text="Hebel")
    tree_perps.heading("Groesse", text="Bestand")
    tree_perps.heading("EP", text="Einstieg Ø")
    tree_perps.heading("Liq", text="Liquidation")
    tree_perps.heading("Kurs", text="Aktuell")
    tree_perps.heading("PnL", text="GuV (Live)")
    
    tree_perps.column("Ticker", width=70, anchor="center")
    tree_perps.column("Typ", width=70, anchor="center")
    tree_perps.column("Hebel", width=60, anchor="center")
    tree_perps.column("Groesse", width=90, anchor="center")
    tree_perps.column("EP", width=100, anchor="e")
    tree_perps.column("Liq", width=110, anchor="e")
    tree_perps.column("Kurs", width=100, anchor="e")
    tree_perps.column("PnL", width=160, anchor="e")
    tree_perps.pack(fill="both", expand=True, padx=10, pady=10)
    tree_perps.bind("<Double-1>", chart_cmd) # Doppelklick öffnet Chart inkl. Risiko-Linie
    
    # Bedienfeld am unteren Rand des Futures-Tabs
    perp_ord_f = tk.Frame(sub_dep_perps, bg=layout.BG_PANEL, padx=12, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    perp_ord_f.pack(fill="x", side="bottom", padx=10, pady=(0, 10))
    
    import trading
    def _cmd_close_selected_perp():
        selected = tree_perps.selection()
        if not selected:
            layout.zeige_status_meldung("⚠️ KEINE HEBEL-POSITION AUSGEWÄHLT!", "ROT")
            return
        vals = tree_perps.item(selected[0], "values")
        p_key = f"{vals[0]}_{vals[1]}"
        trading.close_perpetual_position(p_key)
        
    def _cmd_open_or_add_perp():
        tkr = ent_perp_ticker.get().upper().strip()
        typ = cb_perp_typ.get()
        try:
            hbl = int(cb_perp_hebel.get().replace("x", ""))
            mgn = float(ent_perp_margin.get())
            if mgn <= 0: raise ValueError
        except ValueError:
            layout.zeige_status_meldung("❌ UNGÜLTIGER HEBEL ODER MARGIN-BETRAG!", "#ff3333")
            return
            
        if tkr not in daten.aktien and tkr not in daten.rohstoffe and tkr not in daten.kryptos and tkr not in daten.fonds:
            layout.zeige_status_meldung("❌ ASSET-SYMBOL NICHT GEFUNDEN!", "#ff3333")
            return
            
        trading.execute_perpetual_trade(tkr, typ, hbl, mgn)

    # UI-Elemente von links nach rechts anordnen
    btn_close_perp = tk.Button(perp_ord_f, text="POSITION SCHLIESSEN", command=_cmd_close_selected_perp)
    layout.style_button(btn_close_perp, "danger")
    btn_close_perp.pack(side="left", padx=10)
    
    btn_open_perp = tk.Button(perp_ord_f, text="POSITION ÖFFNEN / ERWEITERN", command=_cmd_open_or_add_perp)
    layout.style_button(btn_open_perp, "primary")
    btn_open_perp.pack(side="right", padx=10)
    
    ent_perp_margin = tk.Entry(perp_ord_f, width=8, font=(layout.FONT_MONO, 10, "bold"), bg=layout.BG_FIELD, fg=layout.COLOR_TEXT_MAIN, insertbackground="white", relief="flat", highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    ent_perp_margin.insert(0, "1000")
    ent_perp_margin.pack(side="right", padx=5)
    tk.Label(perp_ord_f, text="Margin (Lokal)", fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL, font=(layout.FONT_UI, 9, "bold")).pack(side="right", padx=2)
    
    cb_perp_hebel = ttk.Combobox(perp_ord_f, values=["1x", "2x", "3x", "4x", "5x"], width=4, state="readonly")
    cb_perp_hebel.set("3x")
    cb_perp_hebel.pack(side="right", padx=5)
    tk.Label(perp_ord_f, text="Hebel", fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL, font=(layout.FONT_UI, 9, "bold")).pack(side="right", padx=2)
    
    cb_perp_typ = ttk.Combobox(perp_ord_f, values=["LONG", "SHORT"], width=6, state="readonly")
    cb_perp_typ.set("LONG")
    cb_perp_typ.pack(side="right", padx=5)
    
    ent_perp_ticker = tk.Entry(perp_ord_f, width=6, font=(layout.FONT_MONO, 10, "bold"), bg=layout.BG_FIELD, fg=layout.COLOR_TEXT_MAIN, insertbackground="white", relief="flat", highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    ent_perp_ticker.insert(0, "BTC")
    ent_perp_ticker.pack(side="right", padx=5)
    tk.Label(perp_ord_f, text="Symbol", fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL, font=(layout.FONT_UI, 9, "bold")).pack(side="right", padx=2)
    # -------------------------------------------------------------------------
    
    tree_dep = ttk.Treeview(sub_dep_assets, columns=("Ticker", "Name", "Stueck", "Kaufkurs", "Kurs", "GuV"), show="headings", height=10)
    tree_dep.heading("Ticker", text="Symbol")
    tree_dep.heading("Name", text="Bezeichnung")
    tree_dep.heading("Stueck", text="Bestand")
    tree_dep.heading("Kaufkurs", text="Kauf Ø")
    tree_dep.heading("Kurs", text="Aktuell")
    tree_dep.heading("GuV", text="GuV %")
    
    tree_dep.column("Ticker", width=70, anchor="center")
    tree_dep.column("Name", width=190, anchor="w")
    tree_dep.column("Stueck", width=80, anchor="center")
    tree_dep.column("Kaufkurs", width=100, anchor="e")
    tree_dep.column("Kurs", width=100, anchor="e")
    tree_dep.column("GuV", width=100, anchor="e")
    tree_dep.pack(fill="both", expand=True, padx=10, pady=10)
    tree_dep.bind("<Double-1>", chart_cmd)
    
    dep_ord_f = tk.Frame(sub_dep_assets, bg=layout.BG_PANEL, padx=12, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    dep_ord_f.pack(fill="x", side="bottom", padx=10, pady=(0, 10))
    tk.Label(dep_ord_f, text="Stück", fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL, font=(layout.FONT_UI, 9, "bold")).pack(side="left", padx=5)
    
    ent_dep_stueck = tk.Entry(dep_ord_f, width=8, font=(layout.FONT_MONO, 10, "bold"), bg=layout.BG_FIELD, fg=layout.COLOR_TEXT_MAIN, insertbackground="white", relief="flat", highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    ent_dep_stueck.insert(0, "10")
    ent_dep_stueck.pack(side="left", padx=5)
    
    # SCHNELLKAUF-BUTTON (Anpassen)
    btn_quick_buy = tk.Button(dep_ord_f, text="SCHNELLKAUF", command=lambda: trade_cmd("KAUF_DEPOT"))
    layout.style_button(btn_quick_buy, "success")
    btn_quick_buy.pack(side="left", padx=10)
    
    # SCHNELLVERKAUF-BUTTON (Anpassen)
    btn_quick_sell = tk.Button(dep_ord_f, text="SCHNELLVERKAUF", command=lambda: trade_cmd("VERKAUF_DEPOT"))
    layout.style_button(btn_quick_sell, "danger")
    btn_quick_sell.pack(side="left", padx=5)
    
    btn_networth = tk.Button(dep_ord_f, text="VERMÖGENS-CHART", command=depot_charts.oeffne_networth_chart)
    layout.style_button(btn_networth, "primary")
    btn_networth.pack(side="right", padx=10)
    btn_alloc = tk.Button(dep_ord_f, text="ASSET ALLOCATION", command=depot_charts.oeffne_allocation_pie)
    layout.style_button(btn_alloc, "warning")
    btn_alloc.pack(side="right", padx=5)
    
    tree_dep_anl = ttk.Treeview(sub_dep_bonds, columns=("Index", "Typ", "Nominal", "Kupon", "Restzeit"), show="headings", height=10)
    tree_dep_anl.heading("Index", text="ID")
    tree_dep_anl.heading("Typ", text="Anleihen-Bezeichnung")
    tree_dep_anl.heading("Nominal", text="Investiert")
    tree_dep_anl.heading("Kupon", text="Zins %")
    tree_dep_anl.heading("Restzeit", text="Restlaufzeit")
    
    tree_dep_anl.column("Index", width=50, anchor="center")
    tree_dep_anl.column("Typ", width=250, anchor="w")
    tree_dep_anl.column("Nominal", width=120, anchor="e")
    tree_dep_anl.column("Kupon", width=100, anchor="e")
    tree_dep_anl.column("Restzeit", width=120, anchor="center")
    tree_dep_anl.pack(fill="both", expand=True, padx=10, pady=10)
    
    kr_f = tk.Frame(tab_dep, bg=layout.BG_PANEL, padx=12, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    kr_f.pack(fill="x", side="bottom", padx=12, pady=(0, 12))
    
    lbl_schuld = tk.Label(kr_f, text="Schulden USA: 0.00 $", font=(layout.FONT_MONO, 10, "bold"), fg=layout.COLOR_DANGER, bg=layout.BG_PANEL, justify="left")
    lbl_schuld.pack(side="left", padx=10)
    
    cb_kr_land = ttk.Combobox(kr_f, values=list(daten.LAENDER.keys()), width=6, state="readonly")
    cb_kr_land.set("USA")
    cb_kr_land.pack(side="right", padx=10)
    cb_kr_land.bind("<<ComboboxSelected>>", lambda e: update_grafik())
    
    ent_kredit = tk.Entry(kr_f, width=12, font=(layout.FONT_MONO, 10, "bold"), bg=layout.BG_FIELD, fg=layout.COLOR_TEXT_MAIN, insertbackground="white", relief="flat", highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    ent_kredit.insert(0, "5000")
    ent_kredit.pack(side="right", padx=5)
    
    btn_borrow = tk.Button(kr_f, text="LEIHEN", command=lambda: kredit_cmd("LEIHEN"))
    layout.style_button(btn_borrow, "primary")
    btn_borrow.pack(side="right", padx=5)
    btn_repay = tk.Button(kr_f, text="TILGEN", command=lambda: kredit_cmd("TILGEN"))
    layout.style_button(btn_repay, "neutral")
    btn_repay.pack(side="right", padx=5)

def update_grafik():
    if not tree_dep or not tree_dep_anl or tree_perps is None or tree_kasse is None: return
    w_key = daten.anzeige_waehrung
    global_symbol = daten.LAENDER[w_key]

    for x in tree_kasse.get_children(): tree_kasse.delete(x)
    for w_code in daten.WAEHRUNGEN:
        if w_code == "USA":
            bestand_lokal = daten.bargeld
        else:
            bestand_lokal = daten.forex_depot.get(w_code, 0.0)
            
        sym_lokal = daten.WAEHRUNGEN[w_code]
        
        # Robuste Umrechnung in die aktive Haupt-Anzeigewährung des Terminals anwerfen
        if w_code == "USA":
            wert_terminal = layout.umrechnen(bestand_lokal, w_key)
        elif w_code == "GD":
            gold_preis_usd = daten.rohstoffe["XAU"]["kurs"]
            usd_wert = bestand_lokal * (gold_preis_usd / 100.0)
            wert_terminal = layout.umrechnen(usd_wert, w_key)
        else:
            usd_wert = bestand_lokal / daten.waehrungen_staerke.get(w_code, 1.0)
            wert_terminal = layout.umrechnen(usd_wert, w_key)
            
        tree_kasse.insert("", "end", values=(f"{w_code} ({sym_lokal})", f"{bestand_lokal:.2f} {sym_lokal}", f"{wert_terminal:.2f} {global_symbol}"))
    
    for x in tree_dep.get_children(): tree_dep.delete(x)
    for t, d in daten.depot.items():
        cur_k = daten.aktien[t]["kurs"] if t in daten.aktien else daten.rohstoffe[t]["kurs"] if t in daten.rohstoffe else daten.kryptos[t]["kurs"] if t in daten.kryptos else daten.fonds[t]["kurs"]
        name_orig = daten.aktien[t]["name"] if t in daten.aktien else daten.rohstoffe[t]["name"] if t in daten.rohstoffe else daten.kryptos[t]["name"] if t in daten.kryptos else daten.fonds[t]["name"]
        
        name_str = f"{name_orig} [{daten.aktien[t]['land']}]" if t in daten.aktien else name_orig
        gv = ((cur_k - d["kaufkurs"]) / d["kaufkurs"]) * 100
        asset_land = daten.aktien[t]["land"] if t in daten.aktien else "USA"
        l_symbol = daten.LAENDER[asset_land]
        
        tree_dep.insert("", "end", values=(t, name_str, d["stueck"], f"{d['kaufkurs']:.2f} {l_symbol}", f"{cur_k:.2f} {l_symbol}", f"{gv:+.2f}%"))
        
    for x in tree_dep_anl.get_children(): tree_dep_anl.delete(x)
    for i, anl in enumerate(daten.anleihen):
        bez = f"Staatsanleihe ({anl['land']})" if anl["typ"] == "STAAT" else f"Aktienanleihe [{anl['ticker']}]"
        anl_nom_anzo = layout.umrechnen(anl["nominal"], w_key)
        tree_dep_anl.insert("", "end", values=(i+1, bez, f"{anl_nom_anzo:.2f} {global_symbol}", f"{anl['zins']*100:.2f}%", f"{anl['resttage']/365:.2f} J"))
        
    # Live-Daten für offene Hebel-Positionen rendern
    try:
        for x in tree_perps.get_children(): tree_perps.delete(x)
        if hasattr(daten, 'perpetuals') and daten.perpetuals:
            for p_key, pos in daten.perpetuals.items():
                ticker = pos["ticker"]
                typ = pos["typ"]
                hebel = pos["hebel"]
                groesse = pos["groesse"]
                ep = pos["einstiegskurs"]
                
                # Aktuellen Kurs aus den Modulen ziehen
                if ticker in daten.aktien: cur_k = daten.aktien[ticker]["kurs"]
                elif ticker in daten.rohstoffe: cur_k = daten.rohstoffe[ticker]["kurs"]
                elif ticker in daten.kryptos: cur_k = daten.kryptos[ticker]["kurs"]
                elif ticker in daten.fonds: cur_k = daten.fonds[ticker]["kurs"]
                else: cur_k = 1.0
                
                # Liquidation und PnL live berechnen
                margin_val = pos.get("margin", 1000.0) # Echte Margin für die %-Berechnung holen
                if typ == "LONG":
                    liq_p = ep * (1.0 - (1.0 / hebel))
                    pnl = (cur_k - ep) * groesse
                else: # SHORT
                    liq_p = ep * (1.0 + (1.0 / hebel))
                    pnl = (ep - cur_k) * groesse
                
                # NEU: Gehebelter prozentualer Gewinn auf Basis des echten Geldes (Margin)
                pnl_prozent = (pnl / margin_val) * 100 if margin_val > 0 else 0.0
                
                # Dynamisches Symbol abrufen
                land = pos.get("land", "USA")
                sym = daten.LAENDER.get(land, land)
                    
                g_str = f"{groesse:.4f}" if groesse < 0.01 else f"{groesse:.2f}"
                tree_perps.insert("", "end", values=(ticker, typ, f"{hebel}x", g_str, f"{ep:.2f} {sym}", f"{liq_p:.2f} {sym}", f"{cur_k:.2f} {sym}", f"{pnl:+.2f} {sym} ({pnl_prozent:+.2f}%)"))
    except Exception as ui_error:
        layout.zeige_status_meldung(f"Listen-Fehler: {str(ui_error)}", "#ff3333")
        
    if lbl_schuld and cb_kr_land:
        sel_land = cb_kr_land.get()
        schuld_val = daten.kredite.get(sel_land, 0.0)
        m_data = daten.makro.get(sel_land, {"zins": 0.05})
        lokaler_zins = (m_data.get("zins", 0.05) + 0.06) * 100
        sym_lokal = daten.LAENDER[sel_land]
        lbl_schuld.config(text=f" Schulden {sel_land}: {schuld_val:.2f} {sym_lokal} (Zins: {lokaler_zins:.1f}%)")

# DATEI: tab_depot.py ENDE
