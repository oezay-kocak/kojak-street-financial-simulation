# DATEI: tab_maerkte.py START
import tkinter as tk
from tkinter import ttk
import daten

tree_mkt, tree_top, tree_flop = None, None, None
cb_kat, cb_land, cb_branche, cb_r_kat, ent_stueck = None, None, None, None, None

def _filter_geaendert(event):
    import layout
    layout.update_ui_graphics()

def baue_tab(notebook, chart_cmd, trade_cmd):
    global tree_mkt, tree_top, tree_flop, cb_kat, cb_land, cb_branche, cb_r_kat, ent_stueck
    import layout
    tab_mkt = tk.Frame(notebook, bg=layout.BG_MAIN)
    notebook.add(tab_mkt, text="MÄRKTE")
    
    flt = tk.Frame(tab_mkt, bg=layout.BG_PANEL, padx=12, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    flt.pack(fill="x", padx=12, pady=(12, 8))
    
    def internal_adjust_filters(event):
        kat = cb_kat.get()
        if kat == "Aktien":
            cb_land.pack(side="left", padx=5) 
            cb_branche.pack(side="left", padx=5)
            cb_r_kat.pack_forget()
        elif kat == "Rohstoffe":
            cb_r_kat.pack(side="left", padx=5)
            cb_land.pack_forget() 
            cb_branche.pack_forget()
        else:
            cb_land.pack_forget()
            cb_branche.pack_forget() 
            cb_r_kat.pack_forget()
        import layout
        layout.update_ui_graphics()
        
    tk.Label(flt, text="Kategorie", fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL, font=(layout.FONT_UI, 9, "bold")).pack(side="left", padx=5)
    cb_kat = ttk.Combobox(flt, values=["Aktien", "Rohstoffe", "Kryptos", "Fonds", "Indizes"], width=10, state="readonly")
    cb_kat.set("Aktien")
    cb_kat.pack(side="left", padx=5) 
    cb_kat.bind("<<ComboboxSelected>>", internal_adjust_filters)
    
    cb_land = ttk.Combobox(flt, values=["Alle", "USA", "Japan", "Großbritannien", "EU", "China"], width=10, state="readonly")
    cb_land.set("Alle")
    cb_land.pack(side="left", padx=5) 
    cb_land.bind("<<ComboboxSelected>>", _filter_geaendert)
    
    cb_branche = ttk.Combobox(flt, values=["Alle"] + daten.BRANCHEN, width=15, state="readonly")
    cb_branche.set("Alle")
    cb_branche.pack(side="left", padx=5) 
    cb_branche.bind("<<ComboboxSelected>>", _filter_geaendert)
    
    cb_r_kat = ttk.Combobox(flt, values=["Alle", "Edelmetalle", "Industriemetalle", "Seltene Erden", "Energieträger", "Lebensmittel"], width=15, state="readonly")
    cb_r_kat.set("Alle")
    cb_r_kat.pack(side="left", padx=5) 
    cb_r_kat.bind("<<ComboboxSelected>>", _filter_geaendert)
    
    table_panel = tk.Frame(tab_mkt, bg=layout.BG_PANEL, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    table_panel.pack(fill="both", expand=True, padx=12, pady=4)
    
    tree_mkt = ttk.Treeview(table_panel, columns=("Ticker", "Name", "Kurs", "Aenderung", "MarketCap"), show="headings", height=9)
    for c, w, a in [("Ticker", 110, "center"), ("Name", 240, "center"), ("Kurs", 120, "center"), ("Aenderung", 90, "center"), ("MarketCap", 140, "center")]:
        tree_mkt.heading(c, text=c if c!="Aenderung" else "Woche %")
        tree_mkt.column(c, width=w, anchor=a)
    tree_mkt.pack(fill="both", expand=True, padx=1, pady=1) 
    tree_mkt.bind("<Double-1>", chart_cmd)
    
    frame_ausreisser = tk.Frame(tab_mkt, bg=layout.BG_MAIN, pady=5) 
    frame_ausreisser.pack(fill="x", side="top", padx=12)
    
    def build_sub_tree(parent, text, color):
        f = tk.Frame(parent, bg=layout.BG_PANEL, highlightbackground=layout.COLOR_BORDER, highlightthickness=1, bd=0) 
        f.pack(side="left", fill="both", expand=True, padx=8)
        
        tk.Label(f, text=text, fg=color, bg=layout.BG_PANEL, font=(layout.FONT_UI, 11, "bold"), pady=8).pack()
        
        t = ttk.Treeview(f, columns=("Ticker", "Name", "WochePerf"), show="headings", height=6)
        for col, w, hd in [("Ticker", 70, "Symbol"), ("Name", 170, "Name"), ("WochePerf", 70, "Woche %")]:
            t.heading(col, text=hd)
            t.column(col, width=w, anchor="center")
        t.pack(fill="both", expand=True)
        t.bind("<Double-1>", chart_cmd)
        return t
        
    tree_top = build_sub_tree(frame_ausreisser, " TOP PERFORMER 1 W.", "#00ff00")
    tree_flop = build_sub_tree(frame_ausreisser, " FLOP PERFORMER 1 W.", "#ff3333")
    
    ord_f = tk.Frame(tab_mkt, bg=layout.BG_PANEL, padx=12, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    ord_f.pack(fill="x", side="bottom", padx=12, pady=(8, 12))
    tk.Label(ord_f, text="Stück", fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL, font=(layout.FONT_UI, 9, "bold")).pack(side="left", padx=5)
    ent_stueck = tk.Entry(ord_f, width=8, font=(layout.FONT_MONO, 10, "bold"), bg=layout.BG_FIELD, fg=layout.COLOR_TEXT_MAIN, insertbackground=layout.COLOR_TEXT_MAIN, relief="flat", highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    ent_stueck.insert(0, "10")
    ent_stueck.pack(side="left", padx=5)
    
    btn_buy = tk.Button(ord_f, text="KAUFEN", command=lambda: trade_cmd("KAUF"))
    layout.style_button(btn_buy, "success")
    btn_buy.pack(side="left", padx=5)
    btn_sell = tk.Button(ord_f, text="VERKAUFEN", command=lambda: trade_cmd("VERKAUF"))
    layout.style_button(btn_sell, "danger")
    btn_sell.pack(side="left", padx=5)

def update_grafik():
    if not tree_mkt or not cb_kat: return
    kat = cb_kat.get()
    
    selected = tree_mkt.selection()
    focused_ticker = tree_mkt.item(selected, "values") if selected and tree_mkt.item(selected, "values") else None
    
    for x in tree_mkt.get_children(): tree_mkt.delete(x)
    
    liste_all = []

    def get_woche_perf(d_asset):
        hist = d_asset.get("historie", [])
        if not hist: return 0.0
        # Wir gehen 7 Tage zurück (heute + 7 Historien-Tage = Index -8)
        idx = max(0, len(hist) - 8)
        alt_k = float(hist[idx][0]) if isinstance(hist[idx], (tuple, list)) else float(hist[idx])
        cur_k = float(d_asset.get("kurs", 1.0))
        return ((cur_k - alt_k) / alt_k) * 100.0 if alt_k > 0 else 0.0
    
    if kat == "Aktien":
        f_land = cb_land.get()
        f_br = cb_branche.get()
        for t, d in daten.aktien.items():
            if f_land != "Alle" and d["land"] != f_land: continue
            if f_br != "Alle" and d["branche"] != f_br: continue
            
            land_name = d["land"]
            sym = daten.LAENDER.get(land_name, "$")
            paar_key = f"{land_name}/GD"
            
            if paar_key in daten.FOREX_PAARE_HISTORIE and daten.FOREX_PAARE_HISTORIE[paar_key]:
                letzter_eintrag = daten.FOREX_PAARE_HISTORIE[paar_key][-1]
                # FIX: Extrahiert den numerischen Zahlenwert aus dem Tupel
                kurs_fiat_pro_gd = letzter_eintrag[0] if isinstance(letzter_eintrag, (tuple, list)) else letzter_eintrag
            else:
                kurs_fiat_pro_gd = 100.0
            
            reale_market_cap = d["market_cap"] * kurs_fiat_pro_gd if kurs_fiat_pro_gd > 0 else d["market_cap"]
            liste_all.append((reale_market_cap, t, d["name"], d["kurs"], get_woche_perf(d), d["market_cap"], sym))
            
    elif kat == "Rohstoffe":
        f_rkat = cb_r_kat.get()
        for t, d in daten.rohstoffe.items():
            if f_rkat != "Alle" and d["kategorie"] != f_rkat: continue
            liste_all.append((d["market_cap"], t, d["name"], d["kurs"], get_woche_perf(d), d["market_cap"], "GD"))
            
    elif kat == "Kryptos":
        for t, d in daten.kryptos.items():
            liste_all.append((d["market_cap"], t, d["name"], d["kurs"], get_woche_perf(d), d["market_cap"], "GD"))
            
    elif kat == "Fonds":
        for t, d in daten.fonds.items():
            land_name = d["ziel"]
            sym = daten.LAENDER.get(land_name, "$")
            paar_key = f"{land_name}/GD"
            
            if paar_key in daten.FOREX_PAARE_HISTORIE and daten.FOREX_PAARE_HISTORIE[paar_key]:
                letzter_eintrag = daten.FOREX_PAARE_HISTORIE[paar_key][-1]
                # FIX: Extrahiert den numerischen Zahlenwert aus dem Tupel
                kurs_fiat_pro_gd = letzter_eintrag[0] if isinstance(letzter_eintrag, (tuple, list)) else letzter_eintrag
            else:
                kurs_fiat_pro_gd = 100.0
            
            reale_market_cap = d["market_cap"] * kurs_fiat_pro_gd if kurs_fiat_pro_gd > 0 else d["market_cap"]
            liste_all.append((reale_market_cap, t, d["name"], d["kurs"], get_woche_perf(d), d["market_cap"], sym))

    elif kat == "Indizes":
        for t, d in getattr(daten, "indizes", {}).items():
            liste_all.append((d["kurs"], t, d["name"], d["kurs"], get_woche_perf(d), d["kurs"], "Punkte"))

    # Sortierung nach realer Kaufkraft-Market-Cap
    sortiert = sorted(liste_all, key=lambda x: x[0], reverse=True)
    
    for real_cap, t, name, kurs, aend, mcap, waehrung_sym in sortiert:
        if waehrung_sym == "Punkte":
            kurs_str = f"{kurs:.2f} Pkt."
            mcap_str = f"{mcap:.0f} Punkte"
        else:
            kurs_str = f"{kurs:.2f} {waehrung_sym}"
            mcap_str = f"{mcap/1000000:.1f}M {waehrung_sym}"
            
        item_id = tree_mkt.insert("", "end", values=(t, name, kurs_str, f"{aend:+.2f}%", mcap_str))
        if focused_ticker and t == focused_ticker:
            tree_mkt.selection_set(item_id)
            tree_mkt.focus(item_id)
            
    for x in tree_top.get_children(): tree_top.delete(x)
    for x in tree_flop.get_children(): tree_flop.delete(x)
    
    # Sortierung nach Performance
    sortiert_nach_perf = sorted(liste_all, key=lambda x: x[4], reverse=True)
    for _, t, name, _, aend, _, _ in sortiert_nach_perf[:5]:
        tree_top.insert("", "end", values=(t, name, f"{aend:+.2f}%"))
    for _, t, name, _, aend, _, _ in reversed(sortiert_nach_perf[-5:]):
        tree_flop.insert("", "end", values=(t, name, f"{aend:+.2f}%"))

# DATEI: tab_maerkte.py ENDE
