# DATEI: tab_anleihen.py START
import tkinter as tk
from tkinter import ttk
import daten

tree_anl_market = None
cb_anl_br = None
ent_anl_summe = None

def baue_tab(notebook, anl_cmd):
    global tree_anl_market, cb_anl_br, ent_anl_summe
    import layout
    
    tab_anl = tk.Frame(notebook, bg=layout.BG_MAIN)
    notebook.add(tab_anl, text="ANLEIHEN") 
    anl_flt = tk.Frame(tab_anl, bg=layout.BG_PANEL, padx=12, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    anl_flt.pack(fill="x", padx=12, pady=(12, 8))
    tk.Label(anl_flt, text="Typ/Sektor", fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL, font=(layout.FONT_UI, 9, "bold")).pack(side="left", padx=5)
    
    cb_anl_br = ttk.Combobox(anl_flt, values=["Alle", "Staatsanleihen"] + daten.BRANCHEN, width=18, state="readonly")
    cb_anl_br.set("Alle")
    cb_anl_br.pack(side="left", padx=5)
    cb_anl_br.bind("<<ComboboxSelected>>", lambda e: update_grafik())
    
    table_panel = tk.Frame(tab_anl, bg=layout.BG_PANEL, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    table_panel.pack(fill="both", expand=True, padx=12, pady=4)
    
    tree_anl_market = ttk.Treeview(table_panel, columns=("Ticker", "Name", "Sektor", "R3J", "R5J", "R10J"), show="headings", height=13)
    tree_anl_market.heading("Ticker", text="Symbol")
    tree_anl_market.heading("Name", text="Emittent [Land]")
    tree_anl_market.heading("Sektor", text="Kategorie")
    tree_anl_market.heading("R3J", text="Rendite 3J")
    tree_anl_market.heading("R5J", text="Rendite 5J")
    tree_anl_market.heading("R10J", text="Rendite 10J")
    
    tree_anl_market.column("Ticker", width=80, anchor="center")
    tree_anl_market.column("Name", width=240, anchor="center")
    tree_anl_market.column("Sektor", width=130, anchor="center")
    tree_anl_market.column("R3J", width=95, anchor="center")
    tree_anl_market.column("R5J", width=95, anchor="center")
    tree_anl_market.column("R10J", width=100, anchor="center")
    tree_anl_market.pack(fill="both", expand=True, padx=1, pady=1)
    
    anl_ord_f = tk.Frame(tab_anl, bg=layout.BG_PANEL, padx=12, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    anl_ord_f.pack(fill="x", side="bottom", padx=12, pady=(8, 12))
    tk.Label(anl_ord_f, text="Anlage-Betrag (Lokal)", fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL, font=(layout.FONT_UI, 9, "bold")).pack(side="left", padx=10)
    
    ent_anl_summe = tk.Entry(anl_ord_f, width=12, font=(layout.FONT_MONO, 10, "bold"), bg=layout.BG_FIELD, fg=layout.COLOR_TEXT_MAIN, insertbackground=layout.COLOR_TEXT_MAIN, relief="flat", highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    ent_anl_summe.insert(0, "10000")
    ent_anl_summe.pack(side="left", padx=5)
    
    for text, years in [("ZEICHNEN 3J", 3), ("ZEICHNEN 5J", 5), ("ZEICHNEN 10J", 10)]:
        btn = tk.Button(anl_ord_f, text=text, command=lambda j=years: anl_cmd(j))
        layout.style_button(btn, "warning")
        btn.pack(side="left", padx=5)

def update_grafik():
    if not tree_anl_market or not cb_anl_br: return
    for x in tree_anl_market.get_children(): tree_anl_market.delete(x)
    
    f_br = cb_anl_br.get()
    
    # 1. STAATSANLEIHEN
    if f_br in ["Alle", "Staatsanleihen"]:
        for land in daten.LAENDER:
            lz = daten.makro[land].get("zins", 0.05) if land in daten.makro else 0.05
            r3 = lz * 100
            r5 = (lz + 0.004) * 100
            r10 = (lz + 0.009) * 100
            tree_anl_market.insert("", "end", values=(f"GOV_{land[:3].upper()}", f"Zentralregierung {land}", "Staat", f"{r3:.2f}%", f"{r5:.2f}%", f"{r10:.2f}%"))
            
    # 2. FIRMENANLEIHEN
    for t, d in daten.aktien.items():
        if f_br != "Alle" and f_br != "Staatsanleihen" and d["branche"] != f_br: continue
        if f_br == "Staatsanleihen": continue
        
        land_name = d["land"]
        lz = daten.makro[land_name].get("zins", 0.05) if land_name in daten.makro else 0.05
        # Rating abrufen und Index (0=AAA, 8=C) berechnen
        rating = d.get("rating", "BB")
        r_idx = daten.RATINGS.index(rating) if rating in daten.RATINGS else 4
        
        # Basis-Aufschlag für Unternehmen weglassen, stattdessen exaktes Rating-System:
        # Jede Stufe unter AAA (r_idx) kostet +1% Zins (0.01)
        zins_aufschlag = r_idx * 0.01
        
        r3 = (lz + 0.010 + zins_aufschlag) * 100
        r5 = (lz + 0.015 + zins_aufschlag) * 100
        r10 = (lz + 0.025 + zins_aufschlag) * 100
        
        # Zeigt den Namen jetzt mit dem Rating an, z.B. "Apple [USA] (AA)"
        tree_anl_market.insert("", "end", values=(t, f"{d['name']} [{land_name}] ({rating})", d["branche"], f"{r3:.2f}%", f"{r5:.2f}%", f"{r10:.2f}%"))

# DATEI: tab_anleihen.py ENDE
