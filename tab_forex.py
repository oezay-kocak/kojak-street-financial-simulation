import tkinter as tk
from tkinter import ttk
import daten
import layout
import charts  # Wichtig für den Chart-Aufruf

# Globale Variablen für das Terminal
lbl_bestand_1 = None
lbl_bestand_2 = None
combo_l1 = None
combo_l2 = None
tree_fx = None
ent_menge = None 

def baue_tab(parent, fx_calc_cmd=None, fx_trade_cmd=None):
    """
    Erstellt das Forex-Terminal im einheitlichen Dark-Style.
    """
    global lbl_bestand_1, lbl_bestand_2, combo_l1, combo_l2, tree_fx, ent_menge
    
    frame = tk.Frame(parent, bg=layout.BG_MAIN)
    
    # 1. Kursübersicht (Vergrößert nach unten und im Dark-Style)
    frame_kurse = tk.LabelFrame(
        frame,
        text=" Devisenmarkt ",
        bg=layout.BG_PANEL,
        fg=layout.COLOR_PRIMARY,
        font=(layout.FONT_UI, 10, "bold"),
        padx=10,
        pady=10,
        highlightbackground=layout.COLOR_BORDER,
        highlightthickness=1,
        relief="flat"
    )
    # fill="both" und expand=True sorgen dafür, dass das Fenster den Platz nach unten voll ausnutzt
    frame_kurse.pack(fill="both", expand=True, padx=12, pady=(12, 8))
    
    # height=16 macht die Liste deutlich tiefer
    tree_fx = ttk.Treeview(frame_kurse, columns=("Paar", "Kurs"), show="headings", height=16)
    tree_fx.heading("Paar", text="Handelspaar")
    tree_fx.heading("Kurs", text="Aktueller Kurs")
    tree_fx.column("Paar", width=150, anchor="center")
    tree_fx.column("Kurs", width=150, anchor="center")
    tree_fx.pack(fill="both", expand=True)

    # Doppelklick-Event für die Candlestick-Charts
    tree_fx.bind("<Double-1>", charts.oeffne_chart_fenster)
    
    # 2. Handelsbereich (Ebenfalls komplett im dunklen Stil)
    frame_auswahl = tk.LabelFrame(
        frame,
        text=" Währungstausch ",
        bg=layout.BG_PANEL,
        fg=layout.COLOR_PRIMARY,
        font=(layout.FONT_UI, 10, "bold"),
        padx=12,
        pady=10,
        highlightbackground=layout.COLOR_BORDER,
        highlightthickness=1,
        relief="flat"
    )
    frame_auswahl.pack(fill="x", padx=12, pady=8)
    
    laender_liste = list(daten.WAEHRUNGEN.keys())
    
    tk.Label(frame_auswahl, text="Basiswährung (Haben)", bg=layout.BG_PANEL, fg=layout.COLOR_TEXT_MUTED, font=(layout.FONT_UI, 9, "bold")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
    combo_l1 = ttk.Combobox(frame_auswahl, values=laender_liste, state="readonly", width=15)
    combo_l1.set("USA")
    combo_l1.grid(row=0, column=1, padx=5, pady=5)
    combo_l1.bind("<<ComboboxSelected>>", lambda e: aktualisiere_forex_ansicht())
    
    lbl_bestand_1 = tk.Label(frame_auswahl, text="Verfügbar: 0.00 $", bg=layout.BG_PANEL, fg=layout.COLOR_WARNING, font=(layout.FONT_MONO, 10, "bold"))
    lbl_bestand_1.grid(row=0, column=2, padx=15, pady=5, sticky="w")
    
    tk.Label(frame_auswahl, text="Zielwährung (Kaufen)", bg=layout.BG_PANEL, fg=layout.COLOR_TEXT_MUTED, font=(layout.FONT_UI, 9, "bold")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
    combo_l2 = ttk.Combobox(frame_auswahl, values=laender_liste, state="readonly", width=15)
    combo_l2.set("EU")
    combo_l2.grid(row=1, column=1, padx=5, pady=5)
    combo_l2.bind("<<ComboboxSelected>>", lambda e: aktualisiere_forex_ansicht())
    
    lbl_bestand_2 = tk.Label(frame_auswahl, text="Verfügbar: 0.00 €", bg=layout.BG_PANEL, fg=layout.COLOR_WARNING, font=(layout.FONT_MONO, 10, "bold"))
    lbl_bestand_2.grid(row=1, column=2, padx=15, pady=5, sticky="w")
    
    # Eingabe und Buttons im passenden Design
    frame_handel = tk.Frame(frame, bg=layout.BG_PANEL, padx=12, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    frame_handel.pack(fill="x", padx=12, pady=(0, 12))
    
    tk.Label(frame_handel, text="Menge", bg=layout.BG_PANEL, fg=layout.COLOR_TEXT_MUTED, font=(layout.FONT_UI, 9, "bold")).pack(side="left", padx=5)
    ent_menge = ttk.Entry(frame_handel, width=15, font=(layout.FONT_MONO, 11))
    ent_menge.pack(side="left", padx=5)
    
    def Tausch_ausfuehren():
        # Ignoriert trading.py komplett und nutzt die robuste interne Logik
        fuehre_waehrungstausch_aus(ent_menge.get())
        aktualisiere_forex_ansicht()
        
    btn_tauschen = tk.Button(frame_handel, text="TAUSCHEN", command=Tausch_ausfuehren)
    layout.style_button(btn_tauschen, "success")
    btn_tauschen.pack(side="left", padx=15)
    
    befuelle_tabelle_start()
    aktualisiere_forex_ansicht()
    
    return frame

def befuelle_tabelle_start():
    global tree_fx
    if not tree_fx: return
    for item in tree_fx.get_children(): tree_fx.delete(item)
    for paar_key, historie in daten.FOREX_PAARE_HISTORIE.items():
        if "BTC" not in paar_key:
            aktueller_kurs = historie[-1][0] if historie else 1.0
            tree_fx.insert("", "end", values=(paar_key, f"{aktueller_kurs:.4f}"))

def aktualisiere_forex_ansicht():
    global lbl_bestand_1, lbl_bestand_2, combo_l1, combo_l2
    if not combo_l1 or not combo_l2: return
    
    l1 = combo_l1.get()
    l2 = combo_l2.get()
    
    raw_b1 = daten.bargeld if l1 == "USA" else daten.forex_depot.get(l1, 0.0)
    raw_b2 = daten.bargeld if l2 == "USA" else daten.forex_depot.get(l2, 0.0)
    
    if l1 == "USA":
        b1_umgerechnet = layout.umrechnen(raw_b1, "USA")
    else:
        usd_wert = raw_b1 / daten.waehrungen_staerke.get(l1, 1.0)
        b1_umgerechnet = layout.umrechnen(usd_wert, "USA")
        
    if l2 == "USA":
        b2_umgerechnet = layout.umrechnen(raw_b2, "USA")
    else:
        usd_wert = raw_b2 / daten.waehrungen_staerke.get(l2, 1.0)
        b2_umgerechnet = layout.umrechnen(usd_wert, "USA")
        
    symbol_anzeige = daten.LAENDER.get(daten.anzeige_waehrung, "$")
    lbl_bestand_1.config(text=f"Verfügbar: {b1_umgerechnet:.2f} {symbol_anzeige}")
    lbl_bestand_2.config(text=f"Verfügbar: {b2_umgerechnet:.2f} {symbol_anzeige}")

def fuehre_waehrungstausch_aus(menge_str):
    try:
        betrag = float(menge_str)
        if betrag <= 0: raise ValueError
    except ValueError:
        layout.zeige_status_meldung("❌ UNGÜLTIGER TAUSCHBETRAG!", "ROT")
        return
    
    l1 = combo_l1.get()
    l2 = combo_l2.get()
    if l1 == l2: 
        layout.zeige_status_meldung("❌ BASIS- UND ZIELWÄHRUNG SIND GLEICH!", "ROT")
        return

    # 1. Guthaben prüfen
    b1 = daten.bargeld if l1 == "USA" else daten.forex_depot.get(l1, 0.0)
    if b1 < betrag:
        layout.zeige_status_meldung("❌ UNZUREICHENDES GUTHABEN!", "ROT")
        return

    # 2. Gold-Dinar Stärke dynamisch berechnen
    gold_preis_usd = daten.rohstoffe["XAU"]["kurs"]
    gd_strength = gold_preis_usd / 100.0
    
    s1 = daten.waehrungen_staerke.get(l1, 0.0) if l1 != "GD" else gd_strength
    s2 = daten.waehrungen_staerke.get(l2, 0.0) if l2 != "GD" else gd_strength
    
    if s1 <= 0 or s2 <= 0:
        layout.zeige_status_meldung("❌ FEHLER: UNGÜLTIGE WÄHRUNGSSTÄRKE!", "ROT")
        return

    # 3. Kurs ausrechnen und Gelder verschieben
    kurs = s1 / s2
    erhalt = betrag * kurs
    
    # Abzug
    if l1 == "USA": daten.bargeld -= betrag
    else: daten.forex_depot[l1] -= betrag
    
    # Gutschrift
    if l2 == "USA": daten.bargeld += erhalt
    else: daten.forex_depot[l2] = daten.forex_depot.get(l2, 0.0) + erhalt

    # 4. Erfolgsmeldung und UI Update
    sym1 = daten.LAENDER.get(l1, l1)
    sym2 = daten.LAENDER.get(l2, l2)
    layout.zeige_status_meldung(f"💲 {betrag:.2f} {sym1} GETAUSCHT IN {erhalt:.2f} {sym2}!", "#00ffaa")
    layout.update_ui_graphics()

def update_grafik():
    """Sorgt dafür, dass die Kurse live aktualisiert werden, wenn die Zeit vergeht."""
    befuelle_tabelle_start()
    aktualisiere_forex_ansicht()
