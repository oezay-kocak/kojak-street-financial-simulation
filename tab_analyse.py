# DATEI: tab_analyse.py START
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import daten

_canvas_fonds = None
_canvas_gli = None
_fig_fonds = None
_fig_gli = None
_ax_fonds = None
_ax_gli = None
_aktuelles_intervall = "ALL" 

def baue_tab(notebook_parent):
    global _canvas_fonds, _canvas_gli, _fig_fonds, _fig_gli, _ax_fonds, _ax_gli
    import layout
    
    tab_analyse_frame = tk.Frame(notebook_parent, bg=layout.BG_MAIN)
    notebook_parent.add(tab_analyse_frame, text="ANALYSE")
    
    chart_container = tk.Frame(tab_analyse_frame, bg=layout.BG_MAIN)
    chart_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 0))
    
    frame_links = tk.Frame(chart_container, bg=layout.BG_PANEL, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    frame_links.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
    
    frame_rechts = tk.Frame(chart_container, bg=layout.BG_PANEL, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    frame_rechts.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))
    
    _fig_fonds = Figure(figsize=(4, 3.8), facecolor=layout.BG_PANEL)
    _ax_fonds = _fig_fonds.add_subplot(111)
    _canvas_fonds = FigureCanvasTkAgg(_fig_fonds, master=frame_links)
    _canvas_fonds.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    
    _fig_gli = Figure(figsize=(4, 3.8), facecolor=layout.BG_PANEL)
    _ax_gli = _fig_gli.add_subplot(111)
    _canvas_gli = FigureCanvasTkAgg(_fig_gli, master=frame_rechts)
    _canvas_gli.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    
    bot_panel = tk.Frame(tab_analyse_frame, bg=layout.BG_PANEL, padx=12, pady=10, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    bot_panel.pack(fill="x", side="bottom", padx=12, pady=12)
    
    tk.Label(bot_panel, text="Liquiditäts-Zeitfenster", fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL, font=(layout.FONT_UI, 9, "bold")).pack(side="left", padx=10)
    
    intervalle = [
        (" MAX ", "ALL"), 
        (" 3J ", "3J"), 
        (" 1J ", "1J"), 
        (" 6M ", "6M"), 
        (" 3M ", "3M"), 
        (" 1M ", "1M"), 
        (" 1W ", "1W")
    ]
    for text, key in intervalle:
        btn = tk.Button(bot_panel, text=text.strip(), command=lambda k=key: setze_intervall(k))
        layout.style_button(btn, "neutral")
        btn.pack(side="right", padx=3)
        
    aktualisiere_charts()
    return tab_analyse_frame

def setze_intervall(key):
    global _aktuelles_intervall
    _aktuelles_intervall = key
    aktualisiere_charts()

def aktualisiere_charts():
    global _canvas_fonds, _canvas_gli, _ax_fonds, _ax_gli, _fig_fonds, _fig_gli, _aktuelles_intervall
    if _canvas_fonds is None or _canvas_gli is None: return
    
    # 1. LÄNDERFONDS BALKENDIAGRAMM
    _ax_fonds.clear()
    _ax_fonds.set_facecolor("#0D1118")
    _ax_fonds.tick_params(colors='white', labelsize=8)
    _ax_fonds.grid(True, color="#263347", linestyle=":", axis="y")
    
    try:
        fonds_dict = getattr(daten, "fonds", {})
        laender = ["USA", "EU", "China", "Japan", "Großbritannien"]
        kurz_namen = {"USA": "USA", "EU": "EU", "China": "CH", "Japan": "JP", "Großbritannien": "GB"}
        labels = [kurz_namen[l] for l in laender]
        
        fonds_kurse = []
        for land in laender:
            kurs_gefunden = 100.0
            for f_id, f_data in fonds_dict.items():
                if f_data.get("typ") == "Land" and f_data.get("ziel") == land:
                    kurs_gefunden = f_data.get("kurs", 100.0)
                    break
            fonds_kurse.append(kurs_gefunden)
            
        farben = ['#4472C4', '#ED7D31', '#A5A5A5', '#FFC000', '#5B9BD5']
        _ax_fonds.bar(labels, fonds_kurse, color=farben[:len(laender)], edgecolor="#333344")
        _ax_fonds.set_title("AKTIENMARKT-STÄRKE (LÄNDERFONDS IN €)", color="#22D3EE", fontsize=9, weight="bold")
    except Exception:
        _ax_fonds.text(0.5, 0.5, "Lade Aktienmärkte...", color="white", ha='center', va='center')
        
    # 2. GLI HISTORIE & LIVE-RENDITE
    _ax_gli.clear()
    _ax_gli.set_facecolor("#0D1118")
    _ax_gli.tick_params(colors='white', labelsize=8)
    _ax_gli.grid(True, color="#263347", linestyle=":")
    
    gli_historie = getattr(daten, "GLI_HISTORIE", [])
    current_gli = getattr(daten, "gli_index", 15420.0)
    
    if len(gli_historie) > 1:
        if _aktuelles_intervall == "1W": daten_punkte = gli_historie[-7:]; titel_zusatz = "1W"
        elif _aktuelles_intervall == "1M": daten_punkte = gli_historie[-30:]; titel_zusatz = "1M"
        elif _aktuelles_intervall == "3M": daten_punkte = gli_historie[-90:]; titel_zusatz = "3M"
        elif _aktuelles_intervall == "6M": daten_punkte = gli_historie[-180:]; titel_zusatz = "6M"
        elif _aktuelles_intervall == "1J": daten_punkte = gli_historie[-365:]; titel_zusatz = "1J"
        elif _aktuelles_intervall == "3J": daten_punkte = gli_historie[-1095:]; titel_zusatz = "3J"
        else: daten_punkte = gli_historie; titel_zusatz = "MAX"
        
        start_preis = daten_punkte[0] if daten_punkte else current_gli
        prozent_perf = ((current_gli - start_preis) / start_preis) * 100 if start_preis > 0 else 0.0
        perf_farbe = "#14B8A6" if prozent_perf >= 0 else "#F43F5E"
        perf_sign = "+" if prozent_perf >= 0 else ""
        
        _ax_gli.plot(daten_punkte, color='#F59E0B', linewidth=2.5, label="M2 Liquidität")
        
        titel_text = f"GLI - {titel_zusatz} (AKTUELL: {current_gli:.2f} | {perf_sign}{prozent_perf:.2f}%)"
        _ax_gli.set_title(titel_text, color=perf_farbe, fontsize=9, weight="bold")
        _ax_gli.legend(facecolor="#0D1118", labelcolor="white", fontsize=8, loc="upper left")
    else:
        _ax_gli.text(0.5, 0.5, "Sammle Liquiditätsdaten...", color="white", ha='center', va='center', style='italic')
        _ax_gli.set_title("GLOBAL LIQUIDITY INDEX (GLI)", color="#22D3EE", fontsize=9, weight="bold")
        
    _fig_fonds.tight_layout()
    _fig_gli.tight_layout()
    _canvas_fonds.draw()
    _canvas_gli.draw()

# DATEI: tab_analyse.py ENDE
