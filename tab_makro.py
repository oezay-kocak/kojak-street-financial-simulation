# DATEI: tab_makro.py START
import tkinter as tk
from tkinter import ttk
import daten

tree_makro = None

def baue_tab(notebook):
    global tree_makro
    import layout
    
    tab_mak = tk.Frame(notebook, bg=layout.BG_MAIN)
    notebook.add(tab_mak, text="MAKRO")
    
    header = tk.Frame(tab_mak, bg=layout.BG_PANEL, padx=14, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    header.pack(fill="x", padx=12, pady=(12, 8))
    tk.Label(header, text="ZENTRALBANK- UND KONJUNKTURMONITOR", fg=layout.COLOR_PRIMARY, bg=layout.BG_PANEL, font=(layout.FONT_UI, 10, "bold")).pack(anchor="w")
    
    table_panel = tk.Frame(tab_mak, bg=layout.BG_PANEL, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    table_panel.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    
    tree_makro = ttk.Treeview(table_panel, columns=("Land", "Waehrung", "Zins", "BIP", "Inflation", "Arbeitslos", "Bilanz"), show="headings", height=12)
    tree_makro.heading("Land", text="Land / Region")
    tree_makro.heading("Waehrung", text="Währung")
    tree_makro.heading("Zins", text="Leitzins")
    tree_makro.heading("BIP", text="BIP-Entwicklung (Mo.)")
    tree_makro.heading("Inflation", text="Inflationsrate")
    tree_makro.heading("Arbeitslos", text="Arbeitslosenquote")
    tree_makro.heading("Bilanz", text="Notenbank-Bilanz") # NEU
    
    tree_makro.column("Land", width=140, anchor="center")
    tree_makro.column("Waehrung", width=70, anchor="center")
    tree_makro.column("Zins", width=100, anchor="center")
    tree_makro.column("BIP", width=140, anchor="center")
    tree_makro.column("Inflation", width=110, anchor="center")
    tree_makro.column("Arbeitslos", width=130, anchor="center")
    tree_makro.column("Bilanz", width=150, anchor="center") # NEU
    tree_makro.pack(fill="both", expand=True, padx=1, pady=1)
    
    import charts
    tree_makro.bind("<Double-1>", lambda event: charts.oeffne_chart_fenster(event))

def update_grafik():
    if not tree_makro: return
    selected = tree_makro.selection()
    focused_land = tree_makro.item(selected, "values")[0] if selected and tree_makro.item(selected, "values") else None
    
    for x in tree_makro.get_children(): tree_makro.delete(x)
    for land in daten.LAENDER:
        m_data = daten.makro.get(land, {"bip_abs": 5000.0, "bip_prozent": 0.002, "zins": 0.05, "inflation": 0.02, "arbeitslosigkeit": 0.05, "balance_sheet": 1000.0})
        
        lz = m_data.get("zins", 0.05) * 100
        bip_trend = m_data.get("bip_prozent", 0.002) * 100
        inf = m_data.get("inflation", 0.02) * 100
        al = m_data.get("arbeitslosigkeit", 0.05) * 100
        bs = m_data.get("balance_sheet", 1000.0) # NEU
        sym = daten.LAENDER[land]
        
        item_id = tree_makro.insert("", "end", values=(land, f"{sym}", f"{lz:.2f}%", f"{bip_trend:+.2f}%", f"{inf:.2f}%", f"{al:.2f}%", f"{bs:.0f} Mrd. {sym}"))
        if focused_land and land == focused_land:
            tree_makro.selection_set(item_id)
            tree_makro.focus(item_id)

# DATEI: tab_makro.py ENDE
