# DATEI: terminal.py START------------------------------
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import tkinter as tk
from tkinter import ttk, messagebox
import random
import daten
import layout
import trading
import engine
import charts
import speicher
import makro
import markt
from kojakstreet.core.ohlc import append_ohlc_from_move, normalize_commodity_supply_key

menu_root = None

def toggle_pause():
    daten.spiel_pausiert = not daten.spiel_pausiert
    # FIX: daten.vergangene_ms = 0 wurde hier komplett entfernt! 
    # Dadurch läuft die Uhr nach der Pause exakt an der gestoppten Millisekunde weiter.
    if layout.btn_pse:
        layout.style_button(layout.btn_pse, "success" if daten.spiel_pausiert else "warning")
        layout.btn_pse.config(text="WEITER" if daten.spiel_pausiert else "PAUSE")

def tages_uhr_tick():
    # 1. NOTAUSSCHALTER: Existiert das Hauptfenster überhaupt noch?
    if not layout.root or not layout.root.winfo_exists():
        return  # Wenn nein -> Geister-Timer sofort und lautlos beenden!

    if daten.spiel_pausiert:
        layout.root.after(100, tages_uhr_tick)
        return
        
    if not hasattr(daten, 'vergangene_ms'): daten.vergangene_ms = 0
    daten.vergangene_ms += 100
    fortschritt = daten.vergangene_ms / daten.intervall
    
    if fortschritt >= 1.0:
        daten.vergangene_ms = 0
        engine.markt_update_tag()
    else:
        winkel = 360 * fortschritt
        if hasattr(layout, 'canvas_uhr') and layout.canvas_uhr:
            layout.canvas_uhr.delete("all")
            layout.canvas_uhr.create_oval(4, 4, 26, 26, outline=layout.COLOR_BORDER, width=2)
            layout.canvas_uhr.create_arc(4, 4, 26, 26, start=90, extent=-winkel, outline=layout.COLOR_PRIMARY, width=2, style="arc")
            
    layout.root.after(100, tages_uhr_tick)

def starte_haupt_terminal():
    layout.baue_das_interface(
        toggle_pause, trading.execute_trade, trading.execute_anleihe_zeichnung, 
        trading.handle_kredit, charts.oeffne_chart_fenster, 
        trading.fx_calc_callback, trading.fx_trade_callback
    )
    daten.vergangene_ms = 0
    layout.update_ui_graphics()
    layout.root.after(100, tages_uhr_tick)

def cmd_neues_spiel_tag1():
    global menu_root
    menu_root.destroy()
    starte_haupt_terminal()

def cmd_neues_spiel_zufall():
    global menu_root
    lbl_title.config(text="⚙️ GENERIERE WELT-HISTORIE...", fg="cyan")
    menu_root.update()
    
    from datetime import timedelta
    
    def stummer_news_ticker(text, kat="WEISS"):
        pass

    for tag in range(3650):
        makro.update_makro_oekonomie(stummer_news_ticker)
        markt.update_markt_kurse()
        
        if makro.ist_letzter_tag_des_monats():
            z_str = daten.datum.strftime("%d.%m.%Y")
            makro.fuehre_monatlichen_zinsentscheid_durch(stummer_news_ticker)
            
            for t, d in daten.aktien.items():
                ergebnis = random.uniform(-0.18, 0.18)
                old_price = d["kurs"]
                d["kurs"] = max(1.0, d["kurs"] * (1 + ergebnis * 0.4))
                d["eps"] = max(0.5, d.get("eps", 5.0) * (1 + ergebnis * random.uniform(0.6, 1.1)))
                append_ohlc_from_move(d, old_price, d["kurs"], z_str, volatility=abs(ergebnis), label=f"Rep {ergebnis*100:+.0f}%")
                
            for t, d in daten.rohstoffe.items():
                ergebnis = random.uniform(-0.12, 0.15)
                old_price = d["kurs"]
                d["kurs"] = max(1.0, d["kurs"] * (1 - ergebnis * 0.35))
                d["foerder_menge"] = max(-3.0, min(3.0, normalize_commodity_supply_key(d) * 0.70 + (ergebnis * 15.0) * 0.30))
                append_ohlc_from_move(d, old_price, d["kurs"], z_str, volatility=abs(ergebnis), label=f"Rep {ergebnis*100:+.0f}%")
                
            for t, d in daten.kryptos.items():
                ergebnis = random.uniform(-0.25, 0.30)
                old_price = d["kurs"]
                d["kurs"] = max(0.1, d["kurs"] * (1 + ergebnis * 0.5))
                d["netzwerk_aktivitaet"] = max(-3.0, min(3.0, d.get("netzwerk_aktivitaet", 0.0) * 0.75 + (ergebnis * 8.0) * 0.25))
                d["netzwerk_fees"] = max(-3.0, min(3.0, d["netzwerk_aktivitaet"] * 1.1 + random.uniform(-0.4, 0.4)))
                d["gebühren"] = max(500.0, 50000.0 * ((d["netzwerk_aktivitaet"] + 4.0) / 4.0) * (d["kurs"] / 100.0))
                append_ohlc_from_move(d, old_price, d["kurs"], z_str, volatility=abs(ergebnis), label=f"Net {ergebnis*100:+.0f}%")
                
        daten.datum += timedelta(days=1)
        import kredite
        daten.DEPOT_VERMOEGEN_HISTORIE.append((kredite.get_nettovermoegen(), daten.datum.strftime("%d.%m.%Y")))
        
    menu_root.destroy()
    starte_haupt_terminal()
    messagebox.showinfo("Kojak Street", "🚀 Szenario erfolgreich generiert! Willkommen im Jahr 2000. Analysiere das Zins- und KGV-Umfeld der Länder!")

def cmd_spiel_laden():
    global menu_root
    import os
    if not os.path.exists("spielstand.dat"):
        messagebox.showwarning("Hauptmenü", "Kein Speicherstand vorhanden!")
        return
    menu_root.destroy()
    starte_haupt_terminal()
    speicher.spiel_laden()

if __name__ == "__main__":
    menu_root = tk.Tk()
    menu_root.title("Kojak Street - Start-Zentrale")
    menu_root.geometry("500x500")
    menu_root.configure(bg=layout.BG_MAIN)
    
    style = ttk.Style()
    style.theme_use("clam")
    
    frame_box = tk.Frame(menu_root, bg=layout.BG_PANEL, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    frame_box.place(relx=0.5, rely=0.5, anchor="center", width=410, height=400)
    
    lbl_title = tk.Label(frame_box, text="KOJAK STREET", font=(layout.FONT_MONO, 26, "bold"), fg=layout.COLOR_PRIMARY, bg=layout.BG_PANEL)
    lbl_title.pack(pady=(30, 5))
    tk.Label(frame_box, text="FINANCIAL TERMINAL SIMULATION", font=(layout.FONT_UI, 8, "bold"), fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL).pack(pady=(0, 25))
    
    btn_opt = dict(width=30)
    
    for text, command, variant in [
        ("NEUES SPIEL (TAG 1 - 1990)", cmd_neues_spiel_tag1, "primary"),
        ("ZUFALLS-SZENARIO (10J ORBIT)", cmd_neues_spiel_zufall, "warning"),
        ("SPIELSTAND LADEN", cmd_spiel_laden, "neutral"),
        ("BEENDEN", menu_root.quit, "danger"),
    ]:
        button = tk.Button(frame_box, text=text, command=command, **btn_opt)
        layout.style_button(button, variant)
        button.pack(pady=7)
    
    menu_root.mainloop()

def zeige_hauptmenue():
    """Startet das Hauptmenü des Spiels."""
    global menu_root
    if menu_root and menu_root.winfo_exists():
        menu_root.deiconify() # Falls es minimiert war
        menu_root.focus_set() # Fokus auf das Menü
    else:
        # Falls das Hauptmenü komplett geschlossen wurde, neu erstellen
        global lbl_title # Damit lbl_title für die Initialisierung vorhanden ist
        menu_root = tk.Tk()
        menu_root.title("Kojak Street - Start-Zentrale")
        menu_root.geometry("500x500")
        menu_root.configure(bg=layout.BG_MAIN)
        
        style = ttk.Style()
        style.theme_use("clam")
        
        frame_box = tk.Frame(menu_root, bg=layout.BG_PANEL, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
        frame_box.place(relx=0.5, rely=0.5, anchor="center", width=410, height=400)
        
        lbl_title = tk.Label(frame_box, text="KOJAK STREET", font=(layout.FONT_MONO, 26, "bold"), fg=layout.COLOR_PRIMARY, bg=layout.BG_PANEL)
        lbl_title.pack(pady=(30, 5))
        tk.Label(frame_box, text="FINANCIAL TERMINAL SIMULATION", font=(layout.FONT_UI, 8, "bold"), fg=layout.COLOR_TEXT_MUTED, bg=layout.BG_PANEL).pack(pady=(0, 25))
        
        btn_opt = dict(width=30)
        
        for text, command, variant in [
            ("NEUES SPIEL (TAG 1 - 1990)", cmd_neues_spiel_tag1, "primary"),
            ("ZUFALLS-SZENARIO (10J ORBIT)", cmd_neues_spiel_zufall, "warning"),
            ("SPIELSTAND LADEN", cmd_spiel_laden, "neutral"),
            ("BEENDEN", menu_root.quit, "danger"),
        ]:
            button = tk.Button(frame_box, text=text, command=command, **btn_opt)
            layout.style_button(button, variant)
            button.pack(pady=7)
        
        menu_root.mainloop()
        # DATEI: terminal.py ENDE------------------------------
