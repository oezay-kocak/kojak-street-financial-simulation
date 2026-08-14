# DATEI: charts.py START
import warnings
import tkinter as tk
import daten
import chart_engine
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

aktive_zeitraeume = {}

def oeffne_chart_fenster(event):
    tabelle = event.widget
    selected = tabelle.selection()
    if not selected: return
    values = tabelle.item(selected, "values")
    if not values: return
    
    if isinstance(values, (tuple, list)):
        ticker_raw = str(values[0]).strip()
    else:
        ticker_raw = str(values).strip()
        
    if ticker_raw.startswith("(") or ticker_raw.startswith("["):
        ticker_raw = ticker_raw.replace("(", "").replace(")", "").replace("[", "").replace("]", "").replace("'", "").replace('"', "")
    parts = ticker_raw.split(",")
    if parts: ticker_raw = parts[0].strip()
    ticker = ticker_raw
    
    if ticker in daten.LAENDER:
        t_str = "Makro-Zyklus"
        name = f"Wirtschafts-Historie {ticker}"
        f = "#F43F5E" 
    elif "/" in ticker:
        if ticker in daten.FOREX_PAARE_HISTORIE: 
            h = daten.FOREX_PAARE_HISTORIE[ticker]
            f = "#F59E0B" 
            t_str = "Wechselkurs"
            name = f"Devisenpaar {ticker}"
        else: return
    else:
        ticker = ticker_raw.upper()
        if ticker in daten.aktien: 
            t_str = "Aktie"
            f = "#22D3EE" 
            a_data = daten.aktien[ticker]
            name = f"[{a_data['land']}] {a_data['branche'].upper()} | {a_data['name']} ({ticker})"
        elif ticker in daten.rohstoffe: 
            t_str = "Rohstoff"
            f = "#F59E0B" 
            name = f"{daten.rohstoffe[ticker]['name']} ({ticker})"
        elif ticker in daten.kryptos: 
            t_str = "Krypto"
            f = "#A78BFA" 
            name = f"{daten.kryptos[ticker]['name']} ({ticker})"
        elif ticker in daten.fonds: 
            t_str = "Fonds"
            f = "#14B8A6" 
            name = f"{daten.fonds[ticker]['name']} ({ticker})"
        elif ticker in getattr(daten, "indizes", {}):
            t_str = "Index"
            name = f"Index-Monitor: {daten.indizes[ticker]['name']}"
            f = "#22D3EE"
        else: return
        
    import layout
    if not layout.root: return
    
    chart_win = tk.Toplevel(layout.root)
    chart_win.title(f"{t_str}-Chart: {name} | Kojak Street")
    chart_win.geometry("700x600") 
    chart_win.configure(bg=layout.BG_MAIN)
    chart_win.transient(layout.root)
    chart_win.focus_set()
    
    fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
    fig.patch.set_facecolor(layout.BG_PANEL) 
    ax.set_facecolor(layout.BG_FIELD) 
    
    canvas = FigureCanvasTkAgg(fig, master=chart_win)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=8)
    
    aktive_zeitraeume[ticker] = "ALL"
    daten.CHART_REFFS[ticker] = {"fig": fig, "ax": ax, "color": f, "type": t_str, "canvas": canvas, "window": chart_win}
    
    def waehle_zeitraum(label, tk_id=ticker):
        aktive_zeitraeume[tk_id] = label
        chart_engine.zeichne_einzelnen_chart(tk_id)
        
    btn_frame = tk.Frame(chart_win, bg=layout.BG_PANEL, padx=8, pady=8, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    btn_frame.pack(fill="x", side="bottom", padx=12, pady=(0, 12))
    
    for label in ["1W", "1M", "3M", "6M", "1J", "3J", "ALL"]:
        b = tk.Button(btn_frame, text=label, command=lambda l=label: waehle_zeitraum(l))
        layout.style_button(b, "neutral")
        b.pack(side="left", padx=4, expand=True)
        
    def on_close():
        if ticker in daten.CHART_REFFS: del daten.CHART_REFFS[ticker]
        if ticker in aktive_zeitraeume: del aktive_zeitraeume[ticker]
        plt.close(fig)
        chart_win.destroy()

    chart_win.protocol("WM_DELETE_WINDOW", on_close)
    chart_engine.zeichne_einzelnen_chart(ticker)

def aktualisiere_offene_charts():
    for ticker in list(daten.CHART_REFFS.keys()):
        try: chart_engine.zeichne_einzelnen_chart(ticker)
        except Exception: pass

# DATEI: charts.py ENDE
