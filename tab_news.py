# DATEI: tab_news.py START ---------------
import tkinter as tk
from tkinter import ttk
import daten

tree_news = None
txt_detail = None

def baue_tab(notebook):
    global tree_news, txt_detail
    import layout
    
    tab_nws = tk.Frame(notebook, bg=layout.BG_MAIN)
    notebook.add(tab_nws, text="NEWS")
    
    paned = tk.PanedWindow(tab_nws, orient=tk.VERTICAL, bg=layout.COLOR_BORDER, bd=0, sashwidth=5)
    paned.pack(fill="both", expand=True, padx=12, pady=12)
    
    frame_oben = tk.Frame(paned, bg=layout.BG_PANEL, highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    tree_news = ttk.Treeview(frame_oben, columns=("Zeit", "Meldung"), show="headings", height=8)
    tree_news.heading("Zeit", text="Datum")
    tree_news.heading("Meldung", text="Nachrichteninhalt / Marktereignis")
    
    tree_news.column("Zeit", width=120, anchor="center")
    tree_news.column("Meldung", width=760, anchor="w")
    tree_news.pack(fill="both", expand=True)
    
    frame_unten = tk.Frame(paned, bg=layout.BG_PANEL, bd=1, relief="flat", highlightbackground=layout.COLOR_BORDER, highlightthickness=1)
    
    lbl_hint = tk.Label(frame_unten, text="DETAIL INSPECTOR", font=(layout.FONT_UI, 9, "bold"), fg=layout.COLOR_PRIMARY, bg=layout.BG_PANEL, anchor="w")
    lbl_hint.pack(fill="x", padx=10, pady=(8, 2))
    
    txt_detail = tk.Text(frame_unten, bg=layout.BG_FIELD, fg=layout.COLOR_TEXT_MAIN, insertbackground="white",
                         font=(layout.FONT_MONO, 10), wrap="word", bd=0, highlightthickness=0)
    txt_detail.pack(fill="both", expand=True, padx=10, pady=(4, 10))
    
    tree_news.bind("<<TreeviewSelect>>", zeige_nachrichten_details)
    
    paned.add(frame_oben, minsize=150)
    paned.add(frame_unten, minsize=150)
    
    tree_news.tag_configure("positive", foreground=layout.COLOR_SUCCESS)
    tree_news.tag_configure("negative", foreground=layout.COLOR_DANGER)
    tree_news.tag_configure("macro", foreground=layout.COLOR_PRIMARY)
    tree_news.tag_configure("neutral", foreground=layout.COLOR_TEXT_MAIN)

def zeige_nachrichten_details(event):
    global tree_news, txt_detail
    if not tree_news or not txt_detail: return
    
    selected = tree_news.selection()
    if not selected: return
    
    try:
        item = tree_news.item(selected[0])
        werte = item["values"]
        if not werte: return
        
        such_zeit = werte[0]
        such_titel = str(werte[1]).strip()
        
        # Säubert eventuell abgeschnittene Punkte am Ende des Treeview-Titels
        if such_titel.endswith("..."):
            such_titel = such_titel[:-3]
        
        # FIX: Prüft robust über den Teil-String am Anfang der Langmeldung im RAM
        for zeit_str, voller_text, _ in daten.NEWS_SPEICHER:
            if zeit_str == such_zeit and voller_text.strip().startswith(such_titel):
                txt_detail.config(state="normal")
                txt_detail.delete("1.0", tk.END)
                txt_detail.insert("1.0", voller_text)
                txt_detail.config(state="disabled")
                break
    except Exception:
        pass

def update_grafik():
    global tree_news
    if not tree_news: return
    
    for item in tree_news.get_children(): 
        tree_news.delete(item)
        
    for zeit_str, voller_text, kat in reversed(daten.NEWS_SPEICHER):
        zeilen = voller_text.split("\n")
        kurz_text = zeilen[0].strip() if zeilen else "Meldung"
        if len(kurz_text) > 80:
            kurz_text = kurz_text[:77] + "..."
            
        tag_name = "neutral"
        if kat in ["POSITIVE", "KAUF", "ZINS_SENKUNG", "GRUEN"]: tag_name = "positive"
        elif kat in ["NEGATIVE", "CRASH", "ZINS_ERHOEHUNG", "ROT"]: tag_name = "negative"
        elif kat in ["MAKRO", "GLOBAL", "FED", "ZENTRALBANK"]: tag_name = "macro"
        
        tree_news.insert("", "end", values=(zeit_str, kurz_text), tags=(tag_name,))

# DATEI: tab_news.py ENDE ---------------
