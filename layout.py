# DATEI: layout.py Code Anfang
import tkinter as tk
from tkinter import ttk
import daten
import kredite
import speicher
import tab_maerkte
import tab_anleihen
import tab_forex
import tab_makro
import tab_analyse
import tab_depot
import tab_news

root = None
lbl_dat = None
lbl_cas = None
lbl_net = None
lbl_status_ticker = None
btn_pse = None
canvas_uhr = None
cb_global_waehrung = None
notebook_main = None
cb_guv_zeit = None

# Modernes Terminal-Farbschema
BG_MAIN = "#07090D"
BG_PANEL = "#0D1118"
BG_CARD = "#111827"
BG_CARD_LIGHT = "#172033"
BG_FIELD = "#0A0F16"
BG_HOVER = "#233047"
COLOR_PRIMARY = "#22D3EE"
COLOR_ACCENT = "#F59E0B"
COLOR_SUCCESS = "#14B8A6"
COLOR_DANGER = "#F43F5E"
COLOR_WARNING = "#FBBF24"
COLOR_BORDER = "#263347"
COLOR_TEXT_MAIN = "#E5EEF8"
COLOR_TEXT_MUTED = "#8EA3B8"
FONT_UI = "Segoe UI"
FONT_MONO = "Cascadia Mono"

def style_button(button, variant="neutral"):
    palette = {
        "neutral": ("#243244", "#2F4158"),
        "primary": ("#0E7490", "#0891B2"),
        "success": ("#0F766E", "#0D9488"),
        "danger": ("#9F1239", "#BE123C"),
        "warning": ("#B45309", "#D97706"),
    }
    bg, active = palette.get(variant, palette["neutral"])
    button.configure(
        bg=bg,
        activebackground=active,
        activeforeground="#FFFFFF",
        fg="#FFFFFF",
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=12,
        pady=6,
        font=(FONT_UI, 9, "bold"),
    )

def _waehrung_gewaehlt(event):
    global cb_global_waehrung
    daten.anzeige_waehrung = cb_global_waehrung.get()
    update_ui_graphics()

def zeige_status_meldung(text, farbe="#10B981"):
    global lbl_status_ticker, root
    if farbe == "ROT":
        farbe = COLOR_DANGER
    elif farbe == "#00ffaa":
        farbe = COLOR_SUCCESS
    elif farbe == "#ff3333":
        farbe = COLOR_DANGER
    if lbl_status_ticker and root:
        lbl_status_ticker.config(text=text, fg=farbe)
        root.after(1800, loesche_status_ticker)

def loesche_status_ticker():
    global lbl_status_ticker
    if lbl_status_ticker:
        lbl_status_ticker.config(text="")

def baue_das_interface(pause_cmd, trade_cmd, anl_cmd, kredit_cmd, chart_cmd, fx_calc_cmd, fx_trade_cmd):
    global root, lbl_dat, lbl_cas, lbl_net, lbl_status_ticker, btn_pse, canvas_uhr, cb_global_waehrung, notebook_main, cb_guv_zeit
    
    root = tk.Tk()
    root.title("Kojak Street Pro Terminal")
    root.geometry("1220x820")
    root.minsize(1080, 720)
    root.configure(bg=BG_MAIN)
    
    # --- HIGH-DPI & MODERN TTK STYLING ---
    s = ttk.Style()
    s.theme_use("clam")
    
    s.configure("Treeview",
                background=BG_PANEL,
                fieldbackground=BG_PANEL,
                foreground=COLOR_TEXT_MAIN, 
                font=(FONT_UI, 10),
                rowheight=32,
                borderwidth=0,
                relief="flat")
    
    s.configure("Treeview.Heading", 
                background=BG_CARD_LIGHT,
                foreground=COLOR_PRIMARY, 
                font=(FONT_UI, 9, "bold"),
                borderwidth=0, 
                relief="flat")
    s.map("Treeview",
          background=[("selected", "#134E4A")],
          foreground=[("selected", "#FFFFFF")])
    s.map("Treeview.Heading", background=[('active', BG_HOVER)], foreground=[('active', '#ffffff')])
    s.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
    
    s.configure("TCombobox", 
                arrowbackground=BG_FIELD,
                arrowcolor=COLOR_PRIMARY, 
                bordercolor=COLOR_BORDER,
                darkcolor=BG_MAIN, 
                lightcolor=BG_MAIN, 
                background=BG_FIELD,
                foreground=COLOR_TEXT_MAIN, 
                fieldbackground=BG_FIELD,
                padding=(6, 4),
                font=(FONT_UI, 10))
    s.map("TCombobox",
          fieldbackground=[('readonly', BG_FIELD)],
          foreground=[('readonly', COLOR_TEXT_MAIN)],
          selectbackground=[('readonly', BG_FIELD)])

    s.configure("TEntry",
                fieldbackground=BG_FIELD,
                foreground=COLOR_TEXT_MAIN,
                bordercolor=COLOR_BORDER,
                lightcolor=BG_MAIN,
                darkcolor=BG_MAIN,
                padding=(6, 5))
    
    s.configure("TNotebook", background=BG_MAIN, borderwidth=0)
    s.configure("TNotebook.Tab", 
                background=BG_PANEL,
                foreground=COLOR_TEXT_MUTED, 
                font=(FONT_UI, 9, "bold"),
                padding=(18, 10),
                borderwidth=0)
    s.map("TNotebook.Tab",
          background=[('selected', BG_CARD_LIGHT), ('active', BG_HOVER)],
          foreground=[('selected', COLOR_PRIMARY), ('active', COLOR_TEXT_MAIN)])
    
    # --- TOP NAVIGATION & KPI DASHBOARD ---
    top_navbar = tk.Frame(root, bg=BG_PANEL, padx=18, pady=14, highlightbackground=COLOR_BORDER, highlightthickness=1)
    top_navbar.pack(fill="x", side="top", padx=14, pady=(14, 0))
    
    brand_frame = tk.Frame(top_navbar, bg=BG_PANEL)
    brand_frame.pack(side="left", fill="y")
    
    tk.Label(brand_frame, text="KOJAK STREET", font=(FONT_MONO, 19, "bold"), fg=COLOR_PRIMARY, bg=BG_PANEL).pack(anchor="w")
    tk.Label(brand_frame, text="GLOBAL MARKET SIMULATION", font=(FONT_UI, 8, "bold"), fg=COLOR_TEXT_MUTED, bg=BG_PANEL).pack(anchor="w", pady=(0, 8))
    
    lbl_dat = tk.Label(brand_frame, text="", font=(FONT_MONO, 10, "bold"), fg=COLOR_TEXT_MAIN, bg=BG_PANEL)
    lbl_dat.pack(side="top", anchor="w")
    
    lbl_status_ticker = tk.Label(brand_frame, text="Terminal bereit", font=(FONT_UI, 9, "bold"), bg=BG_PANEL, fg=COLOR_ACCENT)
    lbl_status_ticker.pack(side="top", anchor="w", pady=(3, 0))
    
    kpi_frame = tk.Frame(top_navbar, bg=BG_PANEL)
    kpi_frame.pack(side="left", expand=True, padx=20)
    
    card_net = tk.Frame(kpi_frame, bg=BG_CARD, padx=16, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
    card_net.pack(side="left", padx=8)
    tk.Label(card_net, text="TOTAL CASH BALANCE", font=(FONT_UI, 8, "bold"), fg=COLOR_TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
    lbl_net = tk.Label(card_net, text="", font=(FONT_MONO, 14, "bold"), fg=COLOR_TEXT_MAIN, bg=BG_CARD)
    lbl_net.pack(anchor="w")
    
    card_pnl = tk.Frame(kpi_frame, bg=BG_CARD, padx=16, pady=10, highlightbackground=COLOR_BORDER, highlightthickness=1)
    card_pnl.pack(side="left", padx=8)
    
    pnl_sub_top = tk.Frame(card_pnl, bg=BG_CARD)
    pnl_sub_top.pack(fill="x", anchor="w")
    tk.Label(pnl_sub_top, text="REALIZED PNL", font=(FONT_UI, 8, "bold"), fg=COLOR_TEXT_MUTED, bg=BG_CARD).pack(side="left")
    
    cb_guv_zeit = ttk.Combobox(pnl_sub_top, values=["1 Monat", "3 Monate", "6 Monate", "1 Jahr", "Alle"], width=8, state="readonly")
    cb_guv_zeit.set("Alle")
    cb_guv_zeit.pack(side="right", padx=(10, 0))
    cb_guv_zeit.bind("<<ComboboxSelected>>", lambda e: update_ui_graphics())
    
    lbl_cas = tk.Label(card_pnl, text="", font=(FONT_MONO, 14, "bold"), fg=COLOR_SUCCESS, bg=BG_CARD)
    lbl_cas.pack(anchor="w")
    
    right_frame = tk.Frame(top_navbar, bg=BG_PANEL)
    right_frame.pack(side="right", fill="y")
    
    cfg_frame = tk.Frame(right_frame, bg=BG_PANEL)
    cfg_frame.pack(side="top", anchor="e", pady=(0, 6))
    tk.Label(cfg_frame, text="TERMINAL-CURRENCY", fg=COLOR_TEXT_MUTED, bg=BG_PANEL, font=(FONT_UI, 8, "bold")).pack(side="left", padx=4)
    cb_global_waehrung = ttk.Combobox(cfg_frame, values=list(daten.LAENDER.keys()), width=5, state="readonly")
    cb_global_waehrung.set("USA")
    cb_global_waehrung.pack(side="left")
    cb_global_waehrung.bind("<<ComboboxSelected>>", _waehrung_gewaehlt)
    
    btn_frame = tk.Frame(right_frame, bg=BG_PANEL)
    btn_frame.pack(side="bottom", anchor="e")
    
    btn_pse = tk.Button(btn_frame, text="PAUSE", command=pause_cmd)
    style_button(btn_pse, "warning")
    btn_pse.pack(side="left", padx=4)
    
    btn_load = tk.Button(btn_frame, text="LOAD", command=speicher.spiel_laden)
    style_button(btn_load, "neutral")
    btn_load.pack(side="left", padx=4)
    
    btn_save = tk.Button(btn_frame, text="SAVE STATE", command=speicher.spiel_speichern)
    style_button(btn_save, "success")
    btn_save.pack(side="left", padx=4)
    
    canvas_uhr = tk.Canvas(btn_frame, width=30, height=30, bg=BG_PANEL, highlightthickness=0)
    canvas_uhr.pack(side="left", padx=8)
    
    # --- MAIN CONTENT AREA (TAB NOTEBOOK) ---
    notebook_main = ttk.Notebook(root)
    notebook_main.pack(fill="both", expand=True, padx=12, pady=12)
    
    tab_maerkte.baue_tab(notebook_main, chart_cmd, trade_cmd)
    tab_anleihen.baue_tab(notebook_main, anl_cmd)
    forex_frame = tab_forex.baue_tab(notebook_main, fx_calc_cmd, fx_trade_cmd)
    notebook_main.add(forex_frame, text="FOREX MARKT")
    tab_makro.baue_tab(notebook_main)
    tab_analyse.baue_tab(notebook_main) 
    tab_depot.baue_tab(notebook_main, kredit_cmd, trade_cmd, chart_cmd)
    tab_news.baue_tab(notebook_main)
    
    if tab_forex.tree_fx: 
        tab_forex.tree_fx.bind("<Double-1>", chart_cmd)

def umrechnen(usd_betrag, ziel_land):
    if ziel_land == "USA": return usd_betrag
    if daten.waehrungen_staerke[ziel_land] == 0: return 0.0
    return usd_betrag * (daten.waehrungen_staerke["USA"] / daten.waehrungen_staerke[ziel_land])

def update_ui_graphics():
    if not root: return
    w_key = daten.anzeige_waehrung
    symbol = daten.LAENDER[w_key]
    
    gesamtes_cash_usd = daten.bargeld
    for land, bestand in daten.forex_depot.items():
        if land != "USA":
            gesamtes_cash_usd += bestand * (daten.waehrungen_staerke[land] / daten.waehrungen_staerke["USA"])
            
    anzeige_cash = umrechnen(gesamtes_cash_usd, w_key) 
    lbl_dat.config(text=f" SYSTEM TIME: {daten.datum.strftime('%d.%m.%Y')}")
    lbl_net.config(text=f"{anzeige_cash:,.2f} {symbol}")
    
    zeit_filter = cb_guv_zeit.get()
    tage_limit = -1
    if zeit_filter == "1 Monat": tage_limit = 30
    elif zeit_filter == "3 Monate": tage_limit = 90
    elif zeit_filter == "6 Monate": tage_limit = 180
    elif zeit_filter == "1 Jahr": tage_limit = 365
    
    summe_guv_usd = 0.0
    for eintrag_datum, wert_usd in getattr(daten, 'realisierte_guv_historie', []):
        if tage_limit == -1 or (daten.datum - eintrag_datum).days <= tage_limit:
            summe_guv_usd += wert_usd
            
    anzeige_guv = umrechnen(summe_guv_usd, w_key)
    guv_farbe = COLOR_SUCCESS if anzeige_guv >= 0 else COLOR_DANGER
    vorzeichen = "+" if anzeige_guv > 0 else ""
    lbl_cas.config(text=f"{vorzeichen}{anzeige_guv:,.2f} {symbol}", fg=guv_farbe)
       
    if hasattr(tab_maerkte, 'update_grafik'): tab_maerkte.update_grafik()
    if hasattr(tab_anleihen, 'update_grafik'): tab_anleihen.update_grafik()
    if hasattr(tab_forex, 'update_grafik'): tab_forex.update_grafik()
    if hasattr(tab_makro, 'update_grafik'): tab_makro.update_grafik()
    if hasattr(tab_depot, 'update_grafik'): tab_depot.update_grafik()
    
    if hasattr(tab_analyse, 'aktualisiere_charts'):
        root.after_idle(lambda: tab_analyse.aktualisiere_charts())

def show_game_over_screen():
    global root
    if not root: return
    import terminal 
    daten.spiel_pausiert = True
    
    game_over_win = tk.Toplevel(root)
    game_over_win.title("TERMINAL DISCONNECTED")
    game_over_win.geometry("400x280")
    game_over_win.configure(bg=BG_PANEL)
    game_over_win.transient(root)
    game_over_win.grab_set()
    game_over_win.focus_set()

    tk.Label(game_over_win, text="MARGIN CALL / LIQUIDATION", font=(FONT_UI, 16, "bold"), fg=COLOR_DANGER, bg=BG_PANEL).pack(pady=24)
    tk.Label(game_over_win, text="Dein Nettovermögen ist vollständig aufgebraucht.", font=(FONT_UI, 10), fg=COLOR_TEXT_MAIN, bg=BG_PANEL).pack(pady=8)
   
    def restart_game():
        game_over_win.destroy()
        root.destroy()
        terminal.cmd_neues_spiel_tag1()

    def back_to_menu():
        game_over_win.destroy()
        root.destroy()
        terminal.zeige_hauptmenue()

    btn_restart = tk.Button(game_over_win, text="RESTART TERMINAL", command=restart_game)
    style_button(btn_restart, "primary")
    btn_restart.pack(pady=8)
    btn_menu = tk.Button(game_over_win, text="MAIN MENU", command=back_to_menu)
    style_button(btn_menu, "neutral")
    btn_menu.pack(pady=4)
    game_over_win.protocol("WM_DELETE_WINDOW", lambda: None)

    #Code Ende
