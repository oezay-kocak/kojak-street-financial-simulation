# DATEI: chart_engine.py START
import warnings
import numpy as np
import daten
from kojakstreet.core.ohlc import history_ohlc, normalize_commodity_supply_key

def extract_clean_history(raw_history, zf, w_key, convert_currency, is_aktie, ticker=""):
    t_limit = len(raw_history)
    if zf == "1W": t_limit = 7
    elif zf == "1M": t_limit = 30
    elif zf == "3M": t_limit = 90
    elif zf == "6M": t_limit = 180
    elif zf == "1J": t_limit = 365
    elif zf == "3J": t_limit = 1095
    
    gefilterte = raw_history[-t_limit:]
    clean_h = []
    marker_punkte = []
    import layout
    
    # NEU: Wir prüfen sauber, ob es sich um ein Devisenpaar handelt (Schrägstrich im Ticker)
    is_forex = isinstance(ticker, str) and "/" in ticker
    
    for idx, entry in enumerate(gefilterte):
        try:
            if isinstance(entry, (tuple, list)):
                val = float(entry[0])
                lbl = str(entry[2]) if len(entry) > 2 else ""
            else:
                val = float(entry)
                lbl = ""
            
            # KORREKTUR: Devisenpaare (is_forex) bleiben immer roh und werden weder
            # künstlich umgedreht noch mit der Terminal-Währung multipliziert!
            if convert_currency and not is_aktie and not is_forex:
                val = layout.umrechnen(val, w_key)
            
            clean_h.append(val)
            if lbl != "": marker_punkte.append((idx, val, lbl))
        except Exception:
            continue
    
    return clean_h, marker_punkte

def zeichne_einzelnen_chart(ticker):
    if ticker not in daten.CHART_REFFS: return
    ref = daten.CHART_REFFS[ticker]
    fig = ref["fig"]
    canvas = ref["canvas"]
    
    import charts
    zf = charts.aktive_zeitraeume.get(ticker, "ALL")
    import layout
    w_key = daten.anzeige_waehrung
    
    # --- 1. LÄNDER-MAKRO-CHARTS (LINIEN-DIAGRAMME) ---
    # [In chart_engine.py - Ersetze den gesamten Block unter "1. LÄNDER-MAKRO-CHARTS"]
    if ref["type"] == "Makro-Zyklus" or ticker in daten.LAENDER:
        fig.clear()
        ax_bip = fig.add_subplot(511)   # Geändert von 411 auf 511
        ax_zins = fig.add_subplot(512) 
        ax_inf = fig.add_subplot(513) 
        ax_alo = fig.add_subplot(514) 
        ax_bs = fig.add_subplot(515)    # NEU: Fünfter Subplot für Bilanzsumme
        
        fig.patch.set_facecolor("#0f0f14")
        for ax_sub in [ax_bip, ax_zins, ax_inf, ax_alo, ax_bs]:
            ax_sub.set_facecolor("#12121a")
            ax_sub.tick_params(colors='white', labelsize=7)
            ax_sub.grid(True, color="#252535", linestyle=":")
        
        c_zins, _ = extract_clean_history(daten.MAKRO_HISTORIE.get(f"{ticker}_ZINS", []), zf, w_key, False, False, ticker)
        c_bip, _ = extract_clean_history(daten.MAKRO_HISTORIE.get(f"{ticker}_BIP", []), zf, w_key, False, False, ticker)
        c_inf, _ = extract_clean_history(daten.MAKRO_HISTORIE.get(f"{ticker}_INF", []), zf, w_key, False, False, ticker)
        c_alo, _ = extract_clean_history(daten.MAKRO_HISTORIE.get(f"{ticker}_ALO", []), zf, w_key, False, False, ticker)
        c_bs, _ = extract_clean_history(daten.MAKRO_HISTORIE.get(f"{ticker}_BS", []), zf, w_key, False, False, ticker)
        
        if c_bip:
            ax_bip.plot(c_bip, color="#00ffaa", linewidth=2, label="BIP (Mrd. $)")
            ax_bip.set_ylim(min(c_bip) * 0.995, max(c_bip) * 1.005)
            ax_bip.set_title(f" VOLKSWIRTSCHAFTS-MONITORING: {ticker}", color="cyan", fontsize=9, weight="bold")
            ax_bip.legend(facecolor="#12121a", labelcolor="white", fontsize=7, loc="upper left")
        
        if c_zins: ax_zins.plot([v*100 for v in c_zins], color="cyan", linewidth=2, label="Leitzins %")
        if c_zins: ax_zins.legend(facecolor="#12121a", labelcolor="white", fontsize=7, loc="upper left")
        if c_inf: ax_inf.plot([v*100 for v in c_inf], color="#ff3333", linewidth=1.5, label="Inflation %")
        if c_inf: ax_inf.legend(facecolor="#12121a", labelcolor="white", fontsize=7, loc="upper left")
        if c_alo: ax_alo.plot([v*100 for v in c_alo], color="yellow", linewidth=1.5, linestyle=":", label="Arbeitslos %")
        if c_alo: ax_alo.legend(facecolor="#12121a", labelcolor="white", fontsize=7, loc="upper left")
        if c_bs: ax_bs.plot(c_bs, color="#aa66ff", linewidth=1.5, label="Bilanzsumme (Mrd.)") # NEU
        if c_bs: ax_bs.legend(facecolor="#12121a", labelcolor="white", fontsize=7, loc="upper left") # NEU
        
        fig.tight_layout()
        canvas.draw()
        return

    # --- 2. ASSET-CHARTS (CANDLESTICKS) ---
    ax = ref["ax"]
    ax.clear()
    
    if "/" in ticker: 
        h = daten.FOREX_PAARE_HISTORIE[ticker]
    elif ref["type"] == "Aktie": h = daten.aktien[ticker]["historie"]
    elif ref["type"] == "Rohstoff": h = daten.rohstoffe[ticker]["historie"]
    elif ref["type"] == "Krypto": h = daten.kryptos[ticker]["historie"]
    elif ref["type"] == "Index": h = daten.indizes[ticker]["historie"]
    else: h = daten.fonds[ticker]["historie"]
    
    clean_h, marker_punkte = extract_clean_history(h, zf, w_key, True, ref["type"] == "Aktie", ticker)
    if not clean_h: return
    
    # --- TEXTBOX-METRIKEN IM MONITOR RENDERN ---
    if ref["type"] == "Aktie" and ticker in daten.aktien:
        d_act = daten.aktien[ticker]
        gew_skala = d_act.get("gewinn_kennzahl", 0.0)
        sign_g = "+" if gew_skala > 0 else ""
        guide = "Hoher Gewinn" if gew_skala > 1.5 else "Starker Verlust" if gew_skala < -1.5 else "Konstant / Stabil"
        ax.text(0.02, 0.95, f"Gewinn-Skala: {sign_g}{gew_skala:.1f} ({guide})", transform=ax.transAxes, color="#00ffaa", 
                fontname="monospace", weight="bold", fontsize=8, bbox=dict(facecolor='#12121a', alpha=0.8, edgecolor='#252535'))
    elif ref["type"] == "Rohstoff" and ticker in daten.rohstoffe:
        m_menge = normalize_commodity_supply_key(daten.rohstoffe[ticker])
        sign_str = "+" if m_menge > 0 else ""
        guide = "Bullish (Knappheit)" if m_menge < -1.5 else "Bearish (Überangebot)" if m_menge > 1.5 else "Neutral"
        ax.text(0.02, 0.95, f"Angebot Skala: {sign_str}{m_menge:.1f} ({guide})", transform=ax.transAxes, color="#ffaa00", 
                fontname="monospace", weight="bold", fontsize=8, bbox=dict(facecolor='#12121a', alpha=0.8, edgecolor='#252535'))
    elif ref["type"] == "Krypto" and ticker in daten.kryptos:
        d_kry = daten.kryptos[ticker]
        act = d_kry.get("netzwerk_aktivitaet", 0.0)
        fees = d_kry.get("netzwerk_fees", 0.0)
        sign_a = "+" if act > 0 else ""
        sign_f = "+" if fees > 0 else ""
        guide_f = "Bullish" if fees > 1.5 else "Bearish" if fees < -1.5 else "Neutral"
        ax.text(0.02, 0.95, f"Aktivität: {sign_a}{act:.1f} | Gebühren-Skala: {sign_f}{fees:.1f} ({guide_f})", transform=ax.transAxes, 
                color="#cc00ff", fontname="monospace", weight="bold", fontsize=8, bbox=dict(facecolor='#12121a', alpha=0.8, edgecolor='#252535'))
    
    if len(clean_h) > 0:
        start_kurs = clean_h[0]
        end_kurs = clean_h[-1]
        if start_kurs > 0:
            perf_prozent = ((end_kurs - start_kurs) / start_kurs) * 100
            perf_color = "#00ff00" if perf_prozent >= 0 else "#ff3333"
            v_sign = "+" if perf_prozent >= 0 else ""
            # PLATZIERUNG: Bleibt stabil angehoben auf 0.82
            ax.text(0.02, 0.82, f"Rendite ({zf}): {v_sign}{perf_prozent:.2f}%", transform=ax.transAxes, color=perf_color, 
                    fontname="monospace", weight="bold", fontsize=8, ha="left", bbox=dict(facecolor='#12121a', alpha=0.8, edgecolor='#252535'))

    # --- NEU: LIVE FUTURES PNL IM CHART ANZEIGEN ---
    for t_typ in ["LONG", "SHORT"]:
        p_key = f"{ticker}_{t_typ}"
        if hasattr(daten, 'perpetuals') and p_key in daten.perpetuals:
            pos = daten.perpetuals[p_key]
            p_ep = pos["einstiegskurs"]
            p_hebel = pos["hebel"]
            p_groesse = pos["groesse"]
            p_margin = pos.get("margin", 1000.0)
            cur_k = clean_h[-1] if len(clean_h) > 0 else p_ep
            
            p_pnl = (cur_k - p_ep) * p_groesse if t_typ == "LONG" else (p_ep - cur_k) * p_groesse
            p_pnl_prozent = (p_pnl / p_margin) * 100 if p_margin > 0 else 0.0
            
            p_color = "#00ffaa" if p_pnl >= 0 else "#ff3333"
            p_sign = "+" if p_pnl >= 0 else ""
            y_pos = 0.72 if t_typ == "LONG" else 0.62
            
            ax.text(0.02, y_pos, f"FUTURES {t_typ} ({p_hebel}x): {p_sign}{p_pnl_prozent:.2f}%", transform=ax.transAxes, color=p_color, fontname="monospace", weight="bold", fontsize=8, bbox=dict(facecolor='#12121a', alpha=0.9, edgecolor=p_color))

    # --- SÄUBERUNG: PRÄZISE EINE KERZE PRO HANDELSTAG RENDERN ---
    chart_history = h[-len(clean_h):]
    for i in range(len(clean_h)):
        open_p, high_p, low_p, close_p = history_ohlc(chart_history[i])
        
        color_candle = "#00ff00" if close_p >= open_p else "#ff3333"
        
        # 1. Wick (Senkrechter Strich)
        ax.vlines(i, low_p, high_p, color=color_candle, linewidth=1, zorder=1)
        
        # 2. Body (Balken)
        body_height = close_p - open_p
        if abs(body_height) < 0.00001:
            ax.hlines(close_p, i - 0.25, i + 0.25, color=color_candle, linewidth=2, zorder=2)
        else:
            ax.bar(i, body_height, bottom=open_p, width=0.5, color=color_candle, edgecolor=color_candle, zorder=2)

    # --- TECH-INDIKATOREN (GLEITENDE DURCHSCHNITTE) ---
    hist_len_act = len(clean_h)
    if hist_len_act >= 2:
        t_gd20 = min(20, hist_len_act)
        ax.plot([np.mean(clean_h[max(0, idx-(t_gd20-1)):idx+1]) for idx in range(hist_len_act)], color="white", linestyle="--", alpha=0.4, label=f"GD{t_gd20}", zorder=3)
        
        t_gd100 = min(100, hist_len_act)
        ax.plot([np.mean(clean_h[max(0, idx-(t_gd100-1)):idx+1]) for idx in range(hist_len_act)], color="#df9fff", linestyle=":", alpha=0.5, label=f"GD{t_gd100}", zorder=3)
        
        t_gd365 = min(365, hist_len_act)
        ax.plot([np.mean(clean_h[max(0, idx-(t_gd365-1)):idx+1]) for idx in range(hist_len_act)], color="#ff8800", linestyle="-.", alpha=0.5, label=f"GD{t_gd365}", zorder=3)
        
        # PRÄZISIONS-KORREKTUR: Wir nutzen bbox_to_anchor, um die Legende exakt unter den Performance-Kasten zu hängen.
        # X=0.02 (bündig links), Y=0.68 (schwebt perfekt im freien Raum über dem Chart-Boden)
        ax.legend(facecolor="#12121a", labelcolor="white", fontsize=7, loc="upper left", bbox_to_anchor=(0.02, 0.78))

    # --- MARKER FÜR EVENTS & NEWS EINFÜGEN ---
    for idx, val, lbl in marker_punkte:
        ax.annotate(lbl, (idx, val), textcoords="offset points", xytext=(0,10), ha='center',
                    arrowprops=dict(arrowstyle="->", color="white", lw=0.5),
                    color="white", fontsize=7, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="#252535", alpha=0.8, ec="white", lw=0.5))

    # --- AXEN-STYLING UND RENDER-REFRESH ---
    ax.tick_params(colors='white', labelsize=8)
    ax.grid(True, color="#252535", linestyle=":")
    ax.set_xlim(-1, len(clean_h))
    
    y_min, y_max = min(clean_h), max(clean_h)
    y_puffer = (y_max - y_min) * 0.05 if y_max > y_min else y_min * 0.05
    ax.set_ylim(max(0.00001, y_min - y_puffer), y_max + y_puffer)
    
    fig.tight_layout()
    canvas.draw()
    # DATEI: chart_engine.py ENDE
