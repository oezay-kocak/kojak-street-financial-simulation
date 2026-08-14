# DATEI: anleihen.py START
import daten

def update_laufende_anleihen(add_news_callback):
    """Berechnet die Kupon-Auszahlung in der jeweiligen Landeswährung."""
    for anl in daten.anleihen[:]:
        anl["resttage"] -= 1
        
        if "zinstage_zaehler" not in anl: anl["zinstage_zaehler"] = 0
        anl["zinstage_zaehler"] += 1
        
        land = anl.get("land", "USA")
        sym = daten.LAENDER.get(land, land)
        
        def pnl_to_usd(amount, l):
            if l == "USA": return amount
            if l == "GD": return amount * (daten.rohstoffe["XAU"]["kurs"] / 100.0)
            return amount * (daten.waehrungen_staerke.get("USA", 1.0) / daten.waehrungen_staerke.get(l, 1.0))
        
        # HALBJÄHRLICHER TRIGGER
        if anl["zinstage_zaehler"] >= 180 and anl["resttage"] > 0:
            anl["zinstage_zaehler"] = 0
            halbjahres_kupon = anl["nominal"] * (anl["zins"] / 2)
            
            if land == "USA": daten.bargeld += halbjahres_kupon
            else: daten.forex_depot[land] = daten.forex_depot.get(land, 0.0) + halbjahres_kupon
            
            daten.realisierte_guv_historie.append((daten.datum, pnl_to_usd(halbjahres_kupon, land)))
            bez = f"Staatsanleihe ({land})" if anl["typ"] == "STAAT" else f"Aktienanleihe [{anl['ticker']}]"
            add_news_callback(f" KUPON-AUSZAHLUNG: Halbjährlicher Zins von {halbjahres_kupon:.2f} {sym} für {bez} erhalten.", "GRUEN")
        
        # FÄLLIGKEIT (Laufzeitende)
        if anl["resttage"] <= 0:
            rest_kupon = anl["nominal"] * (anl["zins"] * (anl["zinstage_zaehler"] / 365))
            
            # Zins wird immer gezahlt
            if land == "USA": daten.bargeld += rest_kupon
            else: daten.forex_depot[land] = daten.forex_depot.get(land, 0.0) + rest_kupon
            daten.realisierte_guv_historie.append((daten.datum, pnl_to_usd(rest_kupon, land)))
            
            if anl["typ"] == "STAAT":
                if land == "USA": daten.bargeld += anl["nominal"]
                else: daten.forex_depot[land] = daten.forex_depot.get(land, 0.0) + anl["nominal"]
                add_news_callback(f" STAATSANLEIHE: ({land}) über {anl['nominal']:.2f} {sym} nach Laufzeitende zu 100% zurückgezahlt.", "ZENTRALBANK")
            else:
                import random
                akt_rating = daten.aktien[anl["ticker"]].get("rating", "BB")
                r_idx = daten.RATINGS.index(akt_rating) if akt_rating in daten.RATINGS else 4
                ausfall_risiko = r_idx * 0.05
                
                if random.random() < ausfall_risiko:
                    add_news_callback(f" RATING-AUSFALL: Aktienanleihe {anl['ticker']} (Rating: {akt_rating}) ist insolvent!\nDer Nominalwert von {anl['nominal']:.2f} {sym} ist komplett verloren.", "ROT")
                else:
                    if land == "USA": daten.bargeld += anl["nominal"]
                    else: daten.forex_depot[land] = daten.forex_depot.get(land, 0.0) + anl["nominal"]
                    add_news_callback(f" AKTIENANLEIHE: {anl['ticker']} erfolgreich beendet (Rating: {akt_rating}).\nNominalwert von {anl['nominal']:.2f} {sym} zu 100% erstattet.", "GRUEN")
            
            daten.anleihen.remove(anl)
# DATEI: anleihen.py ENDE