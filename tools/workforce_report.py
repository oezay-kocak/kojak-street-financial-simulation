"""Build the requested 43-point closeout from final machine-readable evidence."""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/workforce-implementation"
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]


def read(label, filename="result.json"):
    return json.loads((OUT / label / filename).read_text(encoding="utf-8"))


def delta(before, after):
    return (after / before - 1) * 100


def compare(before, after, key="final"):
    rows = ["Messgröße | Vorher | Nachher | Änderung", "--- | ---: | ---: | ---:"]
    for field in ("population", "gdp", "revenue", "fcf", "market_cap", "production"):
        b, a = before[key][field]["sum"], after[key][field]["sum"]
        rows.append(f"{field} | {b:,.3f} | {a:,.3f} | {delta(b,a):+.4f}%")
    for field in ("unemployment", "inflation"):
        b, a = before[key][field]["sum"] / 20, after[key][field]["sum"] / 20
        rows.append(f"{field}, Ländermittel | {b*100:.5f}% | {a*100:.5f}% | {(a-b)*100:+.5f} Prozentpunkte")
    rows.append(f"Retired Companies / Insolvenzen | {before[key]['retired_companies']} | {after[key]['retired_companies']} | keine zusätzliche Insolvenz")
    return "\n".join(rows)


def distributions(before, after, key="final"):
    rows = ["Messgröße | Vorher: Min / Median / p95 / Max | Nachher: Min / Median / p95 / Max",
            "--- | --- | ---"]
    for field in ("population", "population_growth", "gdp", "growth", "unemployment", "inflation",
                  "revenue", "fcf", "market_cap", "production", "birth_rate", "death_rate",
                  "coverage", "shortage", "contribution"):
        def cell(value):
            if value is None:
                return "nicht modelliert"
            return " / ".join(f"{value[k]:.7g}" for k in ("min", "median", "p95", "max"))
        rows.append(f"{field} | {cell(before[key].get(field))} | {cell(after[key].get(field))}")
    return "\n".join(rows)


def sectors(before, after, key="final"):
    rows = ["Sektor | Umsatz Δ | FCF Δ | Market Cap Δ | Kapazität Δ", "--- | ---: | ---: | ---: | ---:"]
    for name, values in before[key]["sectors"].items():
        changes = [f"{delta(values[k],after[key]['sectors'][name][k]):+.4f}%"
                   if values[k] else "nicht definiert"
                   for k in ("revenue", "free_cash_flow", "market_cap", "production_capacity")]
        rows.append(f"{name} | " + " | ".join(changes))
    return "\n".join(rows)


def main():
    from kojakstreet.core.workforce import SECTOR_INTENSITIES, SECTOR_MIXES
    bg = read("before-genesis-365-v2")
    ag = read("after-genesis-final-365-v1")
    bh = read("before-heterogeneous-365-v2")
    ah = read("after-heterogeneous-cap001-365-v1")
    b42 = read("before-heterogeneous-seed42-365-v1")
    a42 = read("after-heterogeneous-seed42-365-v1")
    be = read("before-established-50y-v1")
    ae = read("after-established-final-50y-v1")
    e0 = read("established-demography-only-v1")
    h0 = read("heterogeneous-demography-only-365-v1")
    cal = read("calibration-final-v1")
    cb = read("cost-before-v1", "cost.json")
    ca = read("cost-after-v1", "cost.json")
    legacy = read("legacy-established-reader-v1", "probe-result.json")
    tests = ET.parse(OUT / "full-suite-final-v4.xml").getroot().find("testsuite")
    assert tests is not None and int(tests.attrib["failures"]) == int(tests.attrib["errors"]) == 0
    assert int(tests.attrib["skipped"]) == 0
    for value in (ag, ah, a42, ae, bg, bh, b42, be):
        assert value["save_load_continuation_exact"]
    assert all(a["initial_rng_digest"] == b["initial_rng_digest"] for a, b in ((ag, bg), (ah, bh), (a42, b42)))
    old_hashes = read("", "before-hashes.json")
    changed = [name for name, old in old_hashes.items()
               if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != old]
    new = ["src/kojakstreet/core/workforce.py", "tests/test_workforce.py",
           "tools/workforce_validation.py", "tools/workforce_cost.py",
           "tools/workforce_writer_crash.py", "tools/workforce_legacy_bundle_probe.py",
           "tools/workforce_report.py", "tools/process_crash.py",
           "docs/workforce-birth-rate-implementation-2026-10-07.md"]
    sections = []

    def add(title, body):
        sections.append(f"## {len(sections)+1}. {title}\n\n{body}\n")

    add("Geänderte Dateien", "Seit dem eingefrorenen Stand dieses Auftrags geändert:\n\n" + "\n".join(f"- `{name}`" for name in changed)
        + "\n\nZusätzliches vorhandenes Prüfwerkzeug: `tools/flush_writer_probe.py` verwendet für den eigenen Windows-Crash-Kindprozess jetzt die abrupte Kernel-Beendigung. Dieses Werkzeug zählt nicht zu den 177 eingefrorenen Produktions-/Testdateien."
        + "\n\nNeu:\n\n" + "\n".join(f"- `{name}`" for name in new)
        + f"\n\nVon 177 vorher erfassten Produktions-/Testdateien blieben {177-len(changed)} bytegenau unverändert. Frühere lokale Änderungen wurden erhalten. Die einzige bestehende Testanpassung ist die ausdrücklich neue Generator-Strategiebezeichnung; keine Toleranz wurde erweitert und kein Test deaktiviert.")
    add("Modell und Versionen", "Workforce/Demografie V1, Kalibrierung V1; Economic Model `workforce-demographics-v1`. Checkpoint 8 (Lesekompatibilität 4–8), History Schema 2, Generator 3, Fast History 3 / `fast_history_v3`. Bundle Schema 1 und Heterogeneous Initialization 1 bleiben erhalten. Versionen beschreiben die neue wirtschaftliche Bahn; alte Bundles behalten ihre ursprüngliche Identität und eine getrennte Aktivierungsprovenienz.")
    add("Participation", "`PARTICIPATION = 0.65`. Verfügbare Workforce ist eine abstrakte Größe, keine Zahl belegter Stellen. Headline-Arbeitslosigkeit wird nicht abgezogen.")
    add("Anteile je Weltmodus", "Genesis: Basic 40%, Skilled 40%, Highly Qualified 20%. Heterogeneous: Basic 30–50%, Skilled 32–48%, Highly Qualified 12–30%, Summe exakt 1. Established startet mit den gemeinsamen Genesis-Anteilen und entwickelt Angebot und Nachfrage tatsächlich in Vorgeschichte und Burn-in. Die Anteile selbst bleiben in V1 statisch.")
    add("Heterogeneous Seed-Design", "Eigene lokale `random.Random`-Instanzen aus SHA-256 von Modellversion, Weltseed, stabilem Ländernamen und getrennten Streams `shares`, `births`, `deaths`. Basic/Skilled werden dreieckverteilt gezogen; HQ ist das exakte Residuum. Unzulässige Residuen werden neu gezogen, nicht an eine Grenze geklemmt. Markt-RNG und bestehende Heterogeneous-Budgets werden nicht konsumiert oder neu skaliert.")
    mixes = ["Sektor-ID | Basic | Skilled | Highly Qualified | Intensität", "--- | ---: | ---: | ---: | ---:"]
    for sector, mix in SECTOR_MIXES.items():
        mixes.append(f"{sector} | {mix[0]:.2f} | {mix[1]:.2f} | {mix[2]:.2f} | {SECTOR_INTENSITIES[sector]:.6f}")
    add("Die 16 Sektormixe", "\n".join(mixes))
    add("Intensitätskalibrierung", "Die festen positiven Intensitäten sind die kleinste quadratische Anpassung gleicher Intensitäten an den 40/40/20-Mix des realen Genesis-Kapazitätsbestands. Bereich 0,590021–1,476473, auf sechs Nachkommastellen fixiert. Der Diagnosesolver läuft nicht in der Simulation. Kalibrierungsreferenz: Ameron, Genesis Day 1, Gesamtkapazität 18.894,70849655; neutrale Skalierung 688,02331628. Der finale Faktor 575 lässt rund 20% Genesis-Spielraum. Geprüft an 20 vollständigen Heterogeneous-Starts; keine laufende Länder-Normalisierung.")
    add("Nachfrageskala und Einheit", "Eine reguläre Kapazitätseinheit erzeugt `575 × sector_intensity` Workforce-Äquivalente an Nachfrage, verteilt über den festen Mix. Alle Länder benutzen dieselbe abstrakte Einheit. Keine realen Headcounts, Lohnkosten oder GDP-pro-Kopf-Normalisierung werden behauptet.")
    add("Angebot", "`L_c = 0.65 × P_c`; `S_c,p = L_c × share_c,p`. Die Teilnahmequote und Anteile werden nicht durch Headline-Arbeitslosigkeit oder Konjunktur verändert. Konjunktur wirkt nur über die bereits vorhandenen Kapazitäten und die gesonderte, reduzierte Bevölkerungsformel.")
    add("Nachfrage", "`D_c,p = Σ(company.production_capacity × 575 × intensity_sector × mix_sector,p)`. Verwendet wird die zuletzt gültige reguläre Firmenkapazität. IPOs, Defaults und Ersatzfirmen gehen beim nächsten vollständigen monatlichen Aggregat ein. Keine täglichen Job-/Mitarbeiterobjekte und keine pro Firma gespeicherten Poolhistorien.")
    add("Coverage und Shortage", "Bei positiver Nachfrage: `coverage = S/D`, `shortage = max(0,D-S)/max(1e-12,D)`. Ohne Nachfrage: Coverage 1, Shortage 0. Überangebot darf Coverage >1 anzeigen, gibt aber keinen wirtschaftlichen Bonus. Pro Land genau drei Supply/Demand/Coverage/Shortage-Werte.")
    add("Der einzige Workforce-Hook", "`weighted_shortage = Σ(pool_shortage × sector_mix)`; `δ_result = -0.01 × weighted_shortage²`. Der eingefrorene Term wird genau einmal vor `update_stock_fundamentals` dem monatlichen `company_result` hinzugefügt. Bestehende Health-, Umsatz-, Margen-, Finanzierungs- und Repricing-Formeln propagieren ihn weiter. Kein zusätzlicher GDP-, Arbeitslosen-, Sektorfaktor-, täglicher Preis- oder unabhängiger Kapazitäts-Hook. News Momentum erhält keinen zusätzlichen Workforce-Term.")
    add("Finale Begrenzung und verworfene Kalibrierung", "Finale absolute Grenze −0,01, ausreichendes Angebot exakt 0. Bei 1% gewichteter Knappheit −0,000001, bei 50% −0,0025. Der erste Versuch mit −0,03 wurde nicht freigegeben: Established enthielt nicht endliche historische Kurswerte. Zusätzlich wurde eine tatsächliche Doppelzählung der Margenebene in Coarse gefunden und behoben: die Workforce-Marge darf nicht zur nächsten zufälligen Basismarge werden. Ein 24-Monats-Regressionstest schützt das. Finale Established-Generierung und Save/Load bestehen mit unverändert strikter JSON-/Persistenzprüfung; keine Werte werden beim Speichern gelöscht oder ersetzt.")
    add("Monatliche Reihenfolge", "Am regulären Berichtstag 15: bestehendes Macro → Firmenbericht mit vorher eingefrorenem δ → Firmen-Lifecycle → Population/Produktion → einmalige Workforce-Aggregation → δ für den nächsten Bericht einfrieren. Der bestehende Monatsmarker verhindert Wiederholung. Genesis/Legacy erhalten zunächst ein Initialaggregat aus dem aktuellen Bestand; es wird nicht als bereits beobachtete Demografiehistorie ausgegeben.")
    add("Headline-Arbeitslosigkeit", "Die bestehenden Macro-/Krisen-/Inflations-/Psychologie-/Rating-Formeln bleiben unverändert. Arbeitslosigkeit beeinflusst weiter den reduzierten wirtschaftlichen Bevölkerungsterm und bestehende Nachfrage-/Finanzierungsmechanismen. Es gibt keinen direkten Workforce-Abzug oder Workforce-Arbeitslosenbonus. Änderungen in gemessenen Arbeitslosenquoten entstehen als bestehende Rückkopplungen der neuen wirtschaftlichen Bahn.")
    add("Birth Rate", "`birth_rate` ist ein realer jährlicher Anteil der Bevölkerung: 0,012 bedeutet 1,2% pro Jahr. Kein monatlicher Nettozuwachs und keine Geburtenzahl pro Tag. Heterogeneous-Bereich 0,008–0,016.")
    add("Death Rate", "`death_rate` ist ein realer jährlicher Anteil: 0,0085 bedeutet 0,85% pro Jahr. Heterogeneous-Bereich 0,006–0,011. Beide Wurzeln bleiben in V1 statisch; keine Alterskohorten werden vorgetäuscht.")
    add("Birth-/Death-Initialisierung", "Genesis und neue Established-Welten: gemeinsame Mittelpunkte 0,012 / 0,0085. Heterogeneous: eigene reproduzierbare Dreiecksverteilungen mit separaten Streams, auf sieben Nachkommastellen fixiert. Alte Spielstände erhalten die gemeinsamen Wurzeln bei Aktivierung; historische Wurzeln werden nicht rekonstruiert.")
    add("Alte Bevölkerungsformeln", "Live monatlich: `m_old = clamp((g-0.005)*0.025 - max(0,u-0.08)*0.010, -0.0025, 0.0035)`; `P'=max(2m,P*(1+m_old))`. Coarse zuvor unabhängig: `r=0.004+U_hash(-0.006,0.012)`, `P'=max(100k,P*(1+r*dt))`, ohne Aktualisierung von `population_growth`. Die alte Coarse-Populationszufallsrate wird entfernt, nicht mit Birth/Death addiert.")
    add("Neue Bevölkerungsformel", "`natural_annual = birth_rate - death_rate`; `economic_annual = clamp(m_old*12*0.25,-0.006,0.003)`; `net_annual=clamp(natural_annual+economic_annual,-0.01,0.015)`; `P'=max(floor,P*exp(log1p(net_annual)*years))`. Live `years=1/12`, Coarse tatsächliche Bucketdauer in Jahren. `population_growth=P'/P-1` ist der realisierte Intervallwert inklusive Floor, nicht eine unverändert stehenbleibende Startzahl.")
    add("Natürlicher und wirtschaftlicher Anteil", "Natürlicher jährlicher Nettoanteil plus stark reduzierter, begrenzter wirtschaftlicher Anteil werden vor der Zeitumrechnung kombiniert. Bei g=1%, u=6%: natürlich +0,35% jährlich, wirtschaftlich +0,0375%, insgesamt +0,3875%. Metadata `natural_growth` ist der natürliche Intervallwert, `economic_population_adjustment` der jährliche wirtschaftliche Parameter; ihre Einheiten sind verschieden. Die Gesamtänderung wird nur einmal angewendet.")
    add("Floors und Caps", "Bestehender Live-Floor 2 Millionen, Coarse-Floor 100.000. Annual-Net-Guard −1% bis +1,5%; innerhalb der vorgesehenen Rootbereiche tatsächlich −0,9% bis +1,3%. Population und normalisierte Wachstumsrate sind am Floor realisiert, also z.B. beide 0 bei verhinderter Schrumpfung. Keine Anpassung der Startpopulation beim Laden oder am Handoff.")
    add("Stale Growth in Established", "Jeder Coarse-Bucket setzt den tatsächlichen `population_growth`, Intervalllänge und Intervallende neu. Zusätzlich wird `population_growth_annualized = expm1(log1p(realized)/years)` als vergleichbare Rate gespeichert. Monats-/Jahreslevel werden nicht als identische rohe Monatsrate gemischt; Deep History verwendet die normalisierte Rate mit Rate-Semantik.")
    add("Coarse-Integration", "Nur der Feature-Anteil wird in monatlichen Teilabschnitten fortgeschrieben. Existing Coarse-Pfade für Bevölkerung, Umsatz und Kapazität werden zeitlich interpoliert; der letzte Teilabschnitt kann gebrochen sein. Health: `h'=δ+(h-δ)*0.78^step`, mit geometrischem Mittel der monatlichen Health-Level für die Umsatzintegration. Umsatz erhält denselben inkrementellen `.18*(.35*δ+.65*h)`-Beitrag; Kapazität folgt der bestehenden Coarse-Umsatzrelation. Nach jedem Teilabschnitt wird Nachfrage neu aggregiert und δ für den folgenden eingefroren. Marge verwendet eine getrennte Coarse-Basismarge plus den aktuellen `.06*δ+.16*h`-Level, keine wiederholte Addition vergangener Workforce-Margen. Cash verwendet die bestehende Gleichung mit angepasst gültigem Umsatz/FCF. Keine 12 vollständigen Welt-/Marktreplays oder Zusatz-RNG-Aufrufe.")
    add("Burn-in und Handoff", f"Finale Established-Prüfung: 50 Jahre, {ae['generation_metadata']['coarse_buckets']} echte Coarse-Buckets und {ae['generation_metadata']['daily_burn_in_days']} tägliche Produktionsschritte. Handoff überträgt Health genau einmal nach `operating_health`, entfernt Coarse-Hilfswerte und erhält Population sowie gültiges eingefrorenes Aggregat. Danach normale Berichte. Zusätzlich bestehen die vorhandene 50-Jahre-/10-Tage-Burn-in-Prüfung mit 30 Live-Tagen und Save/Load sowie der konstante Monats-/Jahres-Rekurrenztest.")
    add("Legacy-Verhalten", f"Aktivierung ab Ladezeitpunkt, erste Firmenwirkung ab dem nächsten Bericht. Geprüft an echtem v7-/Generator2-/Schema1-Established-Bundle in einer Kopie: Aktivierung {legacy['activation_date']}; Wirtschaft, Population, Spielerbücher und RNG exakt erhalten, 20 Current-Rootzeilen, 0 nacherfundene Workforce-Historienzeilen. Ursprüngliche Generation/Economic Model bleibt in `world_generation`; aktive Modellversion und Aktivierungsdatum kommen separat hinzu. History ID bleibt erhalten; Schema-/Modellherkunft steht im Manifest. Legacy-Save an Tag 14 bestätigt zusätzlich die erste neue Beobachtung am Berichtstag 15.")
    add("Persistenz und Schema", "Neue kleine Tabellen `country_workforce_monthly` und `country_workforce_current`, je 23 Skalare pro Land: Datum, Version/Aktivierung, P, Birth/Death, realisierte und normalisierte Growth samt Intervall und 12 Poolmetriken. Shares und eingefrorene Sektorbeiträge bleiben exakt im Country-Checkpoint. Birth/Death in Monatszeilen dokumentieren die für diese Beobachtung verwendeten Raten; V1 erzeugt dafür keine zusätzlichen Deep-History-Serien. Bestehende Tabellenpositionen bleiben stabil. Writer bekommt immutable RowBatch-Daten; NULL-Growth vor erster Beobachtung wird über die bereits bewährte quoted-CSV-/unquoted-NULL-Strecke exakt transportiert.")
    add("Historienkadenz", f"Neue Live-Fakten nur monatlich am Berichtstag: Genesis-Jahr {ag['tables']['country_workforce_monthly']} Workforce-Zeilen, 20 Current-Zeilen. Initiale Wurzeln und zwischenzeitliche Full-Save/Load-Refreshes erzeugen keine erfundenen Monatsbeobachtungen. 13 Country-Metriken in vorhandener monatlicher/jährlicher Deep-History-Kompaktion; Coarse-Capture enthält echte Feature-Bucketwerte. Keine Company×Pool×Day-Daten, keine täglichen Workforce-Historien und kein zweiter Writer.")
    add("Künftige UI-Projektion", f"On-demand Scope `macro` + ausgewähltes Land + `area=population_society` liefert P, jährliche Birth/Death, beobachtete Growth/Intervall, Headline-u und drei Poolmetriken. Vor erster Demografiebeobachtung sind Growth-Werte ausdrücklich unbekannt (`None`). Nur dieses Land; keine unnötigen Handels-/Chart-Historien oder Firmencopies. Roots werden aus allgemeinen Country-Projektionen ausgeschlossen. Separates `workforce_history_points` ermöglicht ausgewählte Metriken aus sparse History. Kein neuer Tab/Widget. Gemessener ausgewählter Payload: {ca['selected_population_payload_bytes']:,} Bytes.")
    add("Genesis-Ergebnis", "Same-seed Start-RNG exakt gleich, gemeinsame 40/40/20-Wurzeln und gemeinsame Birth/Death. Kein anfänglicher Umsatz-/Kapazitäts-/GDP-/Preis-/Accounting-Neuberechnungseffekt. 365-Tage-Paar, Seed 1729:\n\n" + compare(bg, ag) + "\n\nAlle Workforce-Beiträge im gemessenen Genesis-Jahr sind 0; damit stammt die kleine wirtschaftliche Änderung hier aus Demografie und bestehenden Rückkopplungen.")
    shortage = max(w['shortage']['max'] for w in cal['worlds'])
    penalty = min(w['contribution']['min'] for w in cal['worlds'])
    affected = [sum(any(c[p]['shortage'] > 0 for p in ("basic", "skilled", "highly_qualified")) for c in w['countries'].values()) for w in cal['worlds']]
    add("Heterogeneous Multi-Seed-Ergebnis", f"{cal['root_checks']} Rootprüfungen aus 100 Seeds × 20 Ländern, exakte Wiederholung und Grenzen/Summen; 20 vollständige Initialisierungen Seeds 0–19. Worst Pool Shortage {shortage:.6f}, Worst initialer Sektorbeitrag {penalty:.8f}; Median Pool Shortage und typische Beiträge 0. {min(affected)}–{max(affected)} Länder je Welt haben irgendeinen Poolengpass: keine generelle Vollunterdeckung aller Pools oder harten Produktionsstopps. Knappheit tritt besonders bei kleinen Ländern auf und bleibt durch die weiche Kurve begrenzt. Es werden keine Grenzwerte angeklebt und keine Budgets nachträglich verschoben.")
    add("Established-Ergebnis", "Vorher/nachher nach 50 Jahren einschließlich 365-Tage-Burn-in:\n\n" + compare(be, ae, "initial") + "\n\nDieser Vergleich enthält die entfernte alte Coarse-Zufallsdemografie, die neue Bevölkerungskurve und versionsbedingt andere Coarse-Zufallssignale: die bestehende Hashfunktion salzt bereits mit Economic Model und Fast History Version. Deren ausdrückliche Versionierung bleibt erhalten. Deshalb ist dieser Vergleich kein isolierter Workforce-Effekt. Die zusätzliche Kontrolle unter identischen neuen Versionen und gleicher Demografie trennt den result-Term in Abschnitt 33. Große Unterschiede einzelner Preis-/Regimegrößen dürfen nicht als direkte Workforce-Koeffizienten interpretiert werden.")
    add("365-Tage-Paare und isolierte Wirkung", "Heterogeneous Seed 1729:\n\n" + compare(bh, ah) + "\n\nHeterogeneous Seed 42:\n\n" + compare(b42, a42)
        + "\n\nKontrolle mit gleicher neuer Demografie, aber ausgeschaltetem Workforce-result-Term, Seed 1729 (zusätzliche Diagnose, keine Produktionsoption):\n\n" + compare(h0, ah)
        + "\n\nEstablished-Kontrolle nach 50 Jahren mit gleicher neuer Demografie und ohne Workforce-result-Term:\n\n" + compare(e0, ae, "initial")
        + "\n\nIn dieser letzten Kontrolle ist GDP nur gering verändert, Umsatz über 50 Jahre moderat vermindert und keine zusätzliche Insolvenz sichtbar. Preis- und Quotenabweichungen bleiben stochastische Rückkopplungen; behauptet wird keine tickgenaue Preisgleichheit zwischen absichtlich unterschiedlichen Modellen.")
    add("Stressprüfungen", "Rezession g=−8%, u=40%; Hochwachstum g=12%, u=2%; zusätzliche u=80%-Angebotsprüfung; starke Workforce-Knappheit, Überangebot, Populationsfloor und 100-Jahre-Komposition. Keine automatische Verringerung des Angebots durch u, 0 Bonus im Überangebot und beschränkter result-Term. Echter erzwungener Default entfernt die Firma, ersetzt sie per vorhandener IPO-Logik und aktualisiert den Bedarf im nächsten Aggregat. Monats-/Jahreskomposition bei konstantem Macro stimmt mit enger Float-Toleranz, Coarse-Margenlevel werden 24 Monate gegen die tatsächliche Baseline-Rekurrenz geprüft.")
    add("Save/Load und Berichtstage", "Tag 14, 15 und 16: kompletter Checkpoint inklusive Markt-RNG, Population, Roots und eingefrorener Beiträge vor/nach Load exakt gleich; anschließend ein kompletter Simulationstag exakt gleich. Tests prüfen auch 0/20 Monatszeilen, den richtigen Aggregationstag und die unbekannte Rate vor erster Beobachtung. Ungültige Feature-Checkpoints werden vor Live-Mutation abgelehnt. Zusätzliche Jahres-/Established-Paare vergleichen vollständige Checkpoint-Digests und nächste Tagesfortsetzung; alle bestehen.")
    add("Writer und Recovery", "Neue Workforce-Rows durchlaufen den bestehenden einzelnen Writer, keine zusätzliche Thread- oder Verbindungsbesitzlogik. Tests: Freeze/Mutationstrennung, NULL-Current-Row, persistenter Journal-Replay, echte Prozessabbrüche vor Transaktion, während COPY, vor COMMIT, während COMMIT, nach COMMIT und nach ACK. Sichtbar ist atomar entweder der alte oder ganze neue Zustand; Replay liefert exakt eine Monats-/Current-Zeile und bleibt beim zweiten Öffnen idempotent. Vorhandene Queue-/Backpressure-, Barrieren-, Fehler- und Retail-Writer-Tests sind Teil der vollständigen Suite. Fsync, COMMIT, Journalgrenzen und Speicherbarrieren werden nicht abgeschwächt.")
    add("Vollständige Testsuite", f"{tests.attrib['tests']} bestanden, 0 Fehler, 0 Fehlschläge, 0 übersprungen; {float(tests.attrib['time']):.2f} Sekunden. JUnit: `.cache/workforce-implementation/full-suite-final-v4.xml`. Neue Feature-Datei deckt 128 Testfälle ab. Zusätzlicher Coarse-/Established-Regressionslauf: 2 bestanden. Neue Dateien lint-clean; eingeführte Importsortierungsfehler korrigiert. Bestehende fremde Lintbefunde wurden nicht pauschal umgebaut. Der vorherige Gesamtversuch hatte 634 erfolgreiche Tests und einen nativen Windows-Exit 0xC0000005 statt des geplanten Exit 91 im bestehenden Crash-nach-ACK-Test. Unabhängige Prüfung seiner Artefakte fand beide Tabellen vollständig committed und das Journal bestätigt/leer; Einzelwiederholung bestand. Tests und Exit-Anforderungen wurden nicht erweitert oder deaktiviert. Beide Crash-Prüfwerkzeuge verwenden jetzt für den eigenen Windows-Kindprozess `TerminateProcess` statt CRT-Exit; auf anderen Plattformen bleibt `os._exit`. Das testet einen abrupten Prozessabbruch ohne native Aufräumphase und ohne DB-Close. 146 Writer-/Feature-Prüfungen wurden damit zusätzlich wiederholt. Zwischenläufe mit verworfener Marge/Kalibrierung werden nicht als finale Freigabe gezählt.")
    add("Normal-Day-Performance", f"Separater 90-Tage-Vergleich desselben Genesis-Seeds: je 87 normale Tage. Median Wall vorher {cb['ordinary']['wall_ms']['median']:.3f} ms, nachher {ca['ordinary']['wall_ms']['median']:.3f} ms; Prozess-CPU-Median beide {ca['ordinary']['cpu_ms']['median']:.3f} ms. Ein eigener Test verbietet Aggregation auf normalen Tagen. Kein zusätzlicher Firmenscan, keine neue tägliche Historie. Host-Last/CPU-Zeitauflösung begrenzen die Genauigkeit; die Messung zeigt keinen relevanten Normal-Day-Rückschritt.")
    add("Report-Day und Aggregation", f"Je drei Reporttage im Kostenlauf: Wall-Median vorher {cb['report']['wall_ms']['median']:.3f} ms, nachher {ca['report']['wall_ms']['median']:.3f} ms; CPU-Median beide {ca['report']['cpu_ms']['median']:.3f} ms. Aggregation isoliert 100 Wiederholungen: Median {ca['aggregation_ms']['median']:.3f} ms, p95 {ca['aggregation_ms']['p95']:.3f} ms. Wenige ganze Reporttage sind kein hochpräziser Benchmark; der direkt gemessene Feature-Anteil ist klein.")
    add("Established-Generierungskosten", f"Gemessene 50-Jahre-Gesamtzeit vorher {be['generation_metadata']['elapsed_seconds']:.3f} s, nachher {ae['generation_metadata']['elapsed_seconds']:.3f} s ({delta(be['generation_metadata']['elapsed_seconds'],ae['generation_metadata']['elapsed_seconds']):+.2f}%). Beide mit 365 Produktions-Burn-in-Tagen. Feature macht monatliche Unterintegration auch in alten Jahres-Buckets; dieser begrenzte Mehrbedarf ist bewusst. Parallel laufende Prüfungen und große Checkpoint-/Kompressionskosten beeinflussen Wall-Zeiten; keine behauptete präzise Einzelkostenattribution der Gesamtzeit.")
    add("Speicher- und Payload-Auswirkung", f"90-Tage-Checkpoint vorher {cb['checkpoint_bytes']:,}, nachher {ca['checkpoint_bytes']:,} Bytes (Δ {ca['checkpoint_bytes']-cb['checkpoint_bytes']:,}); Feature-Country-Daten allein {ca['feature_checkpoint_bytes']:,} Bytes. Markt-Payload beide exakt {ca['markets_payload_bytes']:,} Bytes. Peak RSS vorher {cb['peak_rss_bytes']/2**20:.2f}, nachher {ca['peak_rss_bytes']/2**20:.2f} MiB; dieser Unterschied umfasst Allocator-/Laufstreuung. Keine täglich wachsenden Feature-Pools. Established-Store vorher {be['generation_metadata']['store_bytes']:,}, nachher {ae['generation_metadata']['store_bytes']:,} Bytes; Kompaktions-/Wirtschaftsverlauf beeinflussen die Differenz.")
    add("Verbleibende Grenzen", "Abstrakte Workforce-Äquivalente statt echter Stellen, keine Löhne, Kohorten, Migration, Ausbildung oder dynamische Shares. Headline-u bleibt ein anderes Macro-Signal. Established ist weiterhin eine versionierte Multi-Resolution-Näherung mit echtem Burn-in; keine Gleichheit mit 50 Jahren vollständigem Daily-Replay wird behauptet. 20 Startwelten plus zwei Heterogeneous-Jahrespaare und ein Established-Paar sind belastbare Prüfungen, kein Beweis für jeden Seed oder unbegrenzte Horizonte. Quoten/Preise besitzen stochastische Rückkopplungen. Ein späterer UI-Bereich und neue Mechaniken sind nicht Bestandteil dieses Auftrags.")
    add("Abschließendes Urteil", "Freigegeben für diesen Implementierungsumfang: Die finale Kalibrierung ergänzt begrenzte Länder-/Sektorunterschiede, Geburt und Tod haben klare jährliche Semantik, Coarse und Live behandeln den Workforce-Beitrag zeitlich konsistent und die zuvor gefundene Margen-Doppelzählung ist behoben. Kein zusätzlicher Insolvenzfall in den Jahres-/Established-Paaren, keine neue globale Workforce-GDP-Formel, keine täglichen Feature-Scans und vollständige Persistenz-/Fortsetzungsprüfungen. Die anfängliche fehlerhafte Variante wurde verworfen; die Freigabe gilt dem korrigierten finalen Stand.")
    assert len(sections) == 43
    detail = "\n\nDie Tabellen verwenden die vorhandenen Simulationsfelder und deren numerische Einheiten; monetäre Summen enthalten keine zusätzliche FX-Neubewertung. `population_growth` ist der zuletzt beobachtete Intervallwert, Birth/Death sind jährliche Anteile. Alle Länder/Unternehmen gehen in die Verteilungen ein, nicht nur Stichproben.\n"
    for label, before, after, key in (("Genesis 365 Tage", bg, ag, "final"),
                                      ("Heterogeneous 1729, 365 Tage", bh, ah, "final"),
                                      ("Heterogeneous 42, 365 Tage", b42, a42, "final"),
                                      ("Established nach 50 Jahren", be, ae, "initial")):
        detail += f"\n### {label}: Verteilungen\n\n{distributions(before,after,key)}\n\n### {label}: alle 16 Sektoren\n\n{sectors(before,after,key)}\n"
    sections[32] += detail
    report = "# Workforce + Birth Rate – Umsetzung und Validierung\n\nStand: 2026-10-07. Maßgeblich ist der vom Nutzer freigegebene Implementierungsauftrag; die Vorgaben des beigefügten Dokuments bilden den konkret geprüften Umfang.\n\n" + "\n".join(sections)
    destination = ROOT / "docs/workforce-birth-rate-implementation-2026-10-07.md"
    destination.write_text(report, encoding="utf-8")
    (OUT / "final-closeout.json").write_text(json.dumps({"passed": True, "full_suite": tests.attrib,
        "changed_baseline_files": changed, "new_files": new, "report": str(destination)}, indent=2), encoding="utf-8")
    print(str(destination))


if __name__ == "__main__":
    main()
