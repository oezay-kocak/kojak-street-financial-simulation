# DATEI: depot_charts.py START
import tkinter as tk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import daten
import layout

def oeffne_allocation_pie():
    """Generiert ein echtes In-Game Kreisdiagramm deiner aktuellen Vermögensaufteilung."""
    if not layout.root: return
    w_key = daten.anzeige_waehrung
    sym = daten.LAENDER[w_key]
    
    cash_usd = daten.bargeld
    for land, bestand in daten.forex_depot.items():
        if land != "USA" and land in daten.waehrungen_staerke and daten.waehrungen_staerke["USA"] > 0:
            cash_usd += bestand * (daten.waehrungen_staerke[land] / daten.waehrungen_staerke["USA"])
            
    aktien_usd = 0.0
    rohstoffe_usd = 0.0
    kryptos_usd = 0.0
    fonds_usd = 0.0
    
    for t, d in daten.depot.items():
        stk = d.get("stueck", 0)
        if t in daten.aktien: aktien_usd += stk * daten.aktien[t]["kurs"]
        elif t in daten.rohstoffe: rohstoffe_usd += stk * daten.rohstoffe[t]["kurs"]
        elif t in daten.kryptos: kryptos_usd += stk * daten.kryptos[t]["kurs"]
        elif t in daten.fonds: fonds_usd += stk * daten.fonds[t]["kurs"]
        
    labels, werte, colors = [], [], []
    if cash_usd > 0: labels.append("Devisen / Cash"); werte.append(cash_usd); colors.append(layout.COLOR_WARNING)
    if aktien_usd > 0: labels.append("Aktien"); werte.append(aktien_usd); colors.append(layout.COLOR_PRIMARY)
    if rohstoffe_usd > 0: labels.append("Rohstoffe"); werte.append(rohstoffe_usd); colors.append(layout.COLOR_ACCENT)
    if kryptos_usd > 0: labels.append("Kryptowährungen"); werte.append(kryptos_usd); colors.append("#A78BFA")
    if fonds_usd > 0: labels.append("Index-Fonds"); werte.append(fonds_usd); colors.append(layout.COLOR_SUCCESS)
    
    if not werte or sum(werte) <= 0: return
    
    pie_win = tk.Toplevel(layout.root)
    pie_win.title("Depot-Analyse: Asset Allocation")
    pie_win.geometry("500x450")
    pie_win.configure(bg=layout.BG_MAIN)
    pie_win.transient(layout.root)
    
    fig, ax = plt.subplots(figsize=(5, 4))
    fig.patch.set_facecolor(layout.BG_PANEL)
    ax.set_facecolor(layout.BG_PANEL)
    
    ax.pie(werte, labels=labels, colors=colors, autopct='%1.1f%%', textprops={'color': 'white', 'weight': 'bold', 'fontsize': 9}, startangle=140)
    ax.axis('equal') 
    plt.title(f"Gesamt-Portfolio Allocation ({sym})", color=layout.COLOR_PRIMARY, fontsize=11, weight="bold", pad=15)
    
    canvas = FigureCanvasTkAgg(fig, master=pie_win)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=15)
    canvas.draw()

def oeffne_networth_chart():
    """Zeichnet den historischen Vermögensverlauf live in die ausgewählte Währung umgerechnet."""
    if not layout.root or not daten.DEPOT_VERMOEGEN_HISTORIE: return
    w_key = daten.anzeige_waehrung
    sym = daten.LAENDER[w_key]
    
    umgerechnete_kurve = []
    for usd_val, zeit in daten.DEPOT_VERMOEGEN_HISTORIE:
        umgerechnete_kurve.append(layout.umrechnen(usd_val, w_key))
        
    net_win = tk.Toplevel(layout.root)
    net_win.title(f"Depot-Performance: Vermögensaufbau ({w_key})")
    net_win.geometry("600x420")
    net_win.configure(bg=layout.BG_MAIN)
    net_win.transient(layout.root)
    
    fig, ax = plt.subplots(figsize=(6, 3.8))
    fig.patch.set_facecolor(layout.BG_PANEL)
    ax.set_facecolor(layout.BG_FIELD)
    
    ax.plot(umgerechnete_kurve, color=layout.COLOR_SUCCESS, linewidth=2.5, label=f"Nettovermögen ({sym})")
    ax.tick_params(colors='white', labelsize=8)
    ax.grid(True, color=layout.COLOR_BORDER, linestyle=":")
    ax.legend(facecolor=layout.BG_FIELD, labelcolor="white", fontsize=9, loc="upper left")
    plt.title(f"HISTORISCHER NETTOVERMÖGENS-VERLAUF IN {w_key}", color=layout.COLOR_PRIMARY, fontsize=10, weight="bold", pad=10)
    
    canvas = FigureCanvasTkAgg(fig, master=net_win)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=15)
    canvas.draw()
    # DATEI: depot_charts.py ENDE
