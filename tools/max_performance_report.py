"""Produce the final 32-point report only after all evidence gates succeed."""
import hashlib
import json
import pstats
from pathlib import Path
from xml.etree import ElementTree

from max_performance_evidence import OUT, ROOT, RUNS, summary
from visible_sync_report import normal, run, stats

REPORT = ROOT / "docs/final-maximum-performance-squeeze-2026-10-06.md"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def link(path):
    path = ROOT / path
    return f"[{path.relative_to(ROOT).as_posix()}](<{path.as_posix()}>)"


def table(headers, rows):
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(map(str, row)) + " |" for row in rows),
    ])


def profile_rows(label, ui=False):
    paths = [
        RUNS / f"ui-profile-{label}-{i}.pstats" if ui
        else OUT / f"worker-{label}-worker-{i}.pstats"
        for i in range(3)
    ]
    profile = pstats.Stats(*map(str, paths))
    rows = {}
    for (filename, _line, name), (_primitive, calls, own, cumulative, _callers) in profile.stats.items():
        if name.startswith("<") or "day_transition_audit_support" in filename:
            continue
        if ui and ("acquire" in name or name in {"wait", "qt", "exec", "heartbeat"}):
            continue
        key = f"{Path(filename).name}::{name}" if filename != "~" else name
        if key in rows:
            continue
        rows[key] = (calls, own * 1000 / 3, cumulative * 1000 / 3)
    return profile, rows


def profile_table(ui=False):
    before, old = profile_rows("max-profile-before", ui)
    after, new = profile_rows("max-profile-final", ui)
    ranked = sorted(old, key=lambda key: old[key][1], reverse=True)[:30]
    rows = []
    for key in ranked:
        first = old[key]
        second = new.get(key, (0, 0.0, 0.0))
        rows.append([key, first[0], f"{first[1]:.2f} / {first[2]:.2f}", second[0], f"{second[1]:.2f} / {second[2]:.2f}"])
    return table(["Funktion", "Aufrufe vorher (3 Tage)", "Self / Cum vorher ms/Tag", "Aufrufe danach (3 Tage)", "Self / Cum danach ms/Tag"], rows), before.total_calls, after.total_calls


def main():
    frozen = read(OUT / "final-source-hashes.json")
    assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == value for path, value in frozen.items())
    assert all(read(OUT / "final-exact.json").values())
    assert all(read(OUT / "players-exact.json").values())
    suite = ElementTree.parse(OUT / "full-final.xml").getroot().find("testsuite")
    assert suite is not None and int(suite.attrib["failures"]) == int(suite.attrib["errors"]) == 0
    assert int(suite.attrib["skipped"]) == 0
    navigation = read(RUNS / "max-final-navigation.json")
    assert navigation["save_load_exact"]
    before = run(RUNS, "max-before-native-mature")
    mature = run(RUNS, "max-final-mature")
    young = run(RUNS, "max-final-young")
    year = run(RUNS, "max-final-year")
    profile = run(RUNS, "max-profile-final")
    run(RUNS, "max-profile-year")
    assert before["signature"] == mature["signature"] == profile["signature"]
    old, new = normal(before["rows"]), normal(mature["rows"])
    assert len(old) == len(new) >= 30
    b, a = summary(old), summary(new)
    phase_table = table(["Segment / Messgröße", "Vorher", "Danach"], [[key, b[key], a[key]] for key in b if key != "n"])
    section = []

    def add(number, title, body):
        section.append(f"## {number}. {title}\n\n{body}\n")

    add(1, "Frischer Ausgangspunkt", f"106 Produktionsdateien wurden vor der ersten Änderung eingefroren und gehasht. Referenz: {link('.cache/max-performance/before-source-hashes.json')}. Die Referenz enthält bereits sichtbare/on-demand Synchronisierung, UI-Kontinuität und die freigegebene Kleinanleger-Regel. Ältere Git-Stände dienen nicht als Vergleich.\n\nJe 40 native Windows-Übergänge aus demselben reifen Checkpoint, davon {len(new)} gewöhnliche Tage. Anforderung ungefähr alle drei Sekunden; Setup und Navigation liegen außerhalb der Tagesgrenze. T4 wartet auf aktuelle sichtbare Werte, abgeschlossene Historienanforderungen, Chart-Commit und tatsächlichen Paint. Werte sind **Median / p95 / Maximum**, Zeiten in ms; p95 linear interpoliert. Sondertage und Profiler-Läufe sind getrennt.\n\n{phase_table}")
    worker_top, worker_before, worker_after = profile_table()
    ui_top, ui_before, ui_after = profile_table(True)
    add(2, "Top-30-Profile", f"Verglichen werden dieselben ersten drei reifen Tage. Self-Rangfolge, Aufrufe über drei Tage, Zeiten pro Tag. Cumulative-Zeiten überlappen und dürfen nicht addiert werden. Profilierung verlangsamt die Ausführung; diese Werte sind keine Gameplay-Latenzen. Anonyme Comprehensions und Messwrapper sind für die Tabelle ausgeblendet.\n\n### Worker\n\n{worker_top}\n\nGesamte Worker-Aufrufe: {worker_before:,} → {worker_after:,}.\n\n### UI / Parent\n\n{ui_top}\n\nGesamte Parent-Aufrufe: {ui_before:,} → {ui_after:,}. Thread-Wartefunktionen sind keine gemessenen GUI-Blockaden und wurden aus der UI-Hotspot-Rangfolge entfernt. Die vollständigen Rohprofile und 40-Tage-Sondertagprofile liegen in `.cache/max-performance` und `.cache/visible-ui-sync`.")
    add(3, "Produktion und Lieferketten", "Die Firmenauslastung liest unveränderte Marktgrößen einmal pro Markt und Aufruf. Bei Alias zwischen Markt- und Firmenobjekt wird nicht gecacht. Länder-/Sektorboni gelten nur während der unveränderten Firmenaggregation. Ein bereits vorhandener Produktionskapazitätswert vermeidet die zuvor trotzdem ausgewertete Fallback-Funktion. Gewichtete Additionen, Multiplikationen, Reihenfolge, Inventare und Historien bleiben exakt gleich. Zwei separate reife Fünf-Tage-Vergleiche bestätigen vollständige Checkpoints und Datenbankinhalt.")
    add(4, "Asset-Markt und Fonds", "Aktien-, FX-, Rohstoff-, Krypto-, Psychologie-, NPC-Positionierungs- und Squeeze-Formeln bleiben erhalten. Beim Rebalancing werden Aktien einmal nach Land/Sektor gruppiert. Die Listen behalten die ursprüngliche Buchreihenfolge; jeder Fonds bewertet die aktuellen Asset-Objekte mit unveränderten Scores, Sortierung, Gewichten und Zufallsaufrufen. Der Index wird nur bei Bedarf aufgebaut und nach dem laufenden Fonds-Update verworfen. Fonds-Flow wird weiterhin zum bisherigen Zeitpunkt angewendet. Im separaten Kontrolllauf sank der Rebalancing-Aufwand am ersten Monatstag von etwa 67 auf 41 ms; das Profil bestätigt die entfernten Universumsscans.")
    add(5, "Derivate, Bonds und kleinere Phasen", "Zins-Futures teilen innerhalb eines Derivate-Updates ein Länderverzeichnis der Staatsanleihen. Positive Renditen, Laufzeitabstand, stabile Sortierung bei Gleichstand, Auswahl der drei nächsten Anleihen und Summationsreihenfolge bleiben erhalten. Standalone-Aufrufe haben den bisherigen vollständigen Suchpfad. Der Index wird täglich neu aufgebaut. Weitere Bond-, Makro-, Ereignis- und Settlement-Mechaniken wurden unverändert gelassen.")
    add(6, "Persistenz, Projektion und IPC", "Der Checkpoint-Encoder erkennt unveränderte einfache Python-Typen früh; NumPy-Werte, Arrays, Datumswerte, Tupel, Sets, gemischte Mapping-Schlüssel und Subklassen behalten ihren bisherigen Protokollpfad. Keine Felder wurden aus Payloads entfernt. Aktuelle Tabellen bleiben sichtbarkeitsgebunden; Historien, Flush, Transaktion und Haltbarkeit sind unverändert. Tests prüfen insbesondere NumPy-Typen, Tags, Save/Load und Checkpoint-Caches.")
    add(7, "Sichtbare UI-Aktualisierung", "Die Kursliste löst Buchzugehörigkeit und Symbolpriorität einmal pro synchronem Lesezugriff auf. Mehrfach vorhandene Symbole, numerische Schlüssel, erste Buchpriorität, Währungsregeln und Originaldaten-Identität bleiben erhalten. Es gibt keinen Cache über Tages- oder Buchwechsel hinweg. Dadurch entfallen die pro Kurs mehrfach wiederholten Buch-/Typ-/Regionsauflösungen. Tabellen-/Widgetstruktur, Selektion, Scrollen und Fokus verwenden weiterhin die etablierte inkrementelle Aktualisierung.")
    add(8, "Paint und Render", "Der Live-Linienchart bündelt bereits wartende Updates im nächsten Qt-Durchlauf anstelle einer zusätzlichen festen 48-ms-Wartezeit. Er zeichnet weiterhin die neuesten Punkte und dazugehörigen Daten. Ein Regressionstest prüft zwei wartende Updates, genau einen Commit und die neueste Historie. Charts und Achsen werden wiederverwendet; der Ticker läuft unverändert weiter. T4 wartet auch nach der Änderung auf Chart-Commit und korrekten Paint.")
    add(9, "Hauptthread und Event-Loop", "Separate Stack-Sampler erfassen den Qt-Hauptthread während T0–T4. Vorher sind wiederholte `_book → asset_books → asset_type/region/quote`-Aufrufe sichtbar, daneben Ticker-Textmessung, Tabellenformatierung und PyQtGraph-Achsen/Paint. Danach bleiben Formatierung, Chart- und Qt-Zeichenarbeit. Die gemessenen Heartbeat-Werte stehen oben. Seltene längere Pausen bleiben; eine Garantie unter 25 ms wäre durch die Messungen nicht gedeckt. Messobserver (`findChildren`, RSS-Abfrage) verursachen ebenfalls Aufwand und werden nicht als Produktions-Hotspots ausgegeben.")
    allocation_files = list(OUT.glob("worker-allocations-max-allocations-final-worker-*.json"))
    parent_files = list(RUNS.glob("allocations-max-allocations-final-*.json"))
    assert len(allocation_files) == len(parent_files) == 3
    allocations = []
    for name, paths in (("Worker", allocation_files), ("Parent", parent_files)):
        values = [read(path) for path in paths]
        allocations.append([name, stats([x["peak_bytes"] / 2**20 for x in values]), stats([x["net_bytes"] / 2**20 for x in values]), stats([x["net_blocks"] for x in values])])
    allocation_table = table(["Prozess", "Traced Peak MiB", "Netto MiB", "Netto Blöcke"], allocations)
    add(10, "GC und Allokationen", f"GC-Zeit und Prozess-Working-Set sind in der Haupttabelle gemessen. Separate Tracemalloc-Läufe zählen temporäre und verbleibende Allokationen einschließlich der Diagnosebuchhaltung; sie beeinflussen Laufzeit und sind von den Gameplay-Latenzen ausgeschlossen. Quellen/Blockzahlen liegen in den Allocation-JSONs.\n\n{allocation_table}\n\nKeine globale GC-Deaktivierung oder Verschiebung von notwendiger Arbeit hinter T4 wurde ergänzt. Die bereits vorhandene begrenzte GC-Behandlung des Simulation-Cores bleibt erhalten. Ein außerhalb T0–T4 untersuchter geschlossener Bootstrap-Store hielt nur 124 Produkt-Historienzeilen und aktuelle Tabellen; eine zusätzliche Cache-Löschmechanik wäre damit keine begründete Lösung für die seltenen längeren GC-Pausen. Working-Set ist kein Nachweis eines neuen Welt-Mirrors und umfasst auch native/Allocator-Speicher.")
    add(11, "Verworfene Optimierungen", "Nicht umgesetzt: erneute Precomputation, Welt-Mirror, neue IPC-Architektur/Codec, Rust/C++, ausgelassene Historien oder Berechnungen, spätere unsichtbare Nacharbeit, Näherungen für Finanzformeln und monospaced Textbreiten, veränderte RNG-Reihenfolge, GC-Schwellenverschiebung, vorgezogener/asynchroner Flush. Weitere kleine Country-/Branch-Lookup-Caches und Formatter-Spezialisierungen würden überwiegend einzelne Millisekunden sparen und zusätzliche Invalidierungs-/Darstellungsregeln einführen. Die verbleibende große Arbeit besteht aus realer täglicher Modellberechnung, erforderlichen Historien, Serialisierung und korrekter Qt-Darstellung.")
    before_hashes = read(OUT / "before-source-hashes.json")
    changed = [path for path, value in frozen.items() if before_hashes[path] != value]
    assert len(changed) == 6
    files = "\n".join("- " + link(path) for path in changed)
    add(12, "Dateien dieses Passes", f"Produktionsänderungen gegenüber dem frischen Freeze:\n\n{files}\n\nNeue Regressionstests: `test_market_quote_batch.py`, `test_yield_pricing_scope.py`, `test_checkpoint_scalars.py`, `test_live_chart_commit.py`, `test_fund_candidate_scope.py`. Reproduktionswerkzeuge: `max_performance_benchmark.py`, `max_performance_matrix.py`, `max_performance_validate.py`, `max_performance_evidence.py`, `max_performance_report.py`. Der Diff dieses Passes liegt unter {link('.cache/max-performance/production-changes.diff')}; ältere uncommittete Änderungen wurden nicht zurückgesetzt.")
    phase_names = [row["phase"] for row in old[0]["worker"]["phases"]]
    phase_data = []
    for phase in phase_names:
        def values(rows, name=phase):
            return [next((p["duration_ms"] for p in row["worker"]["phases"] if p["phase"] == name), 0) for row in rows]
        phase_data.append([phase, stats(values(old)), stats(values(new))])
    add(13, "Core vorher / danach", f"T0→T1: **{b['T0-T1']} → {a['T0-T1']} ms**. Phasen aus denselben gewöhnlichen Übergängen; `daily_production_chain_core` ist in `daily_production` enthalten.\n\n" + table(["Phase", "Vorher ms", "Danach ms"], phase_data))
    add(14, "T1→T2 vorher / danach", f"**{b['T1-T2']} → {a['T1-T2']} ms**. Enthält Tagespersistenz, sichtbare Extraktion, Encoder, JSON, Pipe, Antwortannahme und Snapshot-Decodierung. Kein persistenter Welt-Diff oder versteckter Voll-Sync wurde ergänzt.")
    add(15, "UI-Patch vorher / danach", f"T2→T3: **{b['T2-T3']} → {a['T2-T3']} ms**. Der Hauptgewinn kommt aus der einmaligen Kursauflösung. Alle sichtbaren Modelle erhalten aktuelle Zahlen.")
    add(16, "Korrekte Darstellung vorher / danach", f"T3→T4: **{b['T3-T4']} → {a['T3-T4']} ms**. Diese Zeit enthält die tatsächliche Event-Loop-/Paint-Bereitschaft und ist nicht die Summe überlappender Paint-Spans.")
    add(17, "Gesamter Übergang vorher / danach", f"T0→T4: **{b['T0-T4']} → {a['T0-T4']} ms**. Die längeren 40-Tage-Messungen sind maßgeblich; kurze Zwischenkontrollen lagen teils niedriger und ersetzen die Abschlussmessung nicht.")
    add(18, "Heartbeat vorher / danach", f"Pro Übergang längster gemessener Heartbeat-Abstand: **{b['Heartbeat']} → {a['Heartbeat']} ms**. Der Median verbessert sich; seltene lange Pausen verschwinden nicht vollständig. Native Messung mit 10-ms-Prüftimer und kontinuierlichem Ticker.")
    add(19, "Payload vorher / danach", f"**{b['Bytes']} → {a['Bytes']} Bytes**. Der wirtschaftliche Inhalt und die sichtbaren Felder bleiben gleich; wenige Bytes Variation kommen aus Laufzeit-/Antwortmetadaten. Keine Payload-Reduktion durch das Weglassen erforderlicher Werte.")
    young_before = run(RUNS, "max-before-young")["rows"]
    cases = [("Jung vorher", young_before), ("Jung danach, gleiche 12 Tage", young["rows"][:len(young_before)]), ("Jung danach, alle 20 Tage", young["rows"])]
    young_rows = []
    for name, rows in cases:
        values = summary(normal(rows))
        young_rows.append([name, *[values[key] for key in ("n", "T0-T1", "T1-T2", "T2-T3", "T3-T4", "T0-T4", "Heartbeat", "Bytes")]])
    add(20, "Junge Welt", table(["Fall", "N gewöhnlich", "T0→T1", "T1→T2", "T2→T3", "T3→T4", "T0→T4", "Heartbeat", "Bytes"], young_rows) + "\n\nStartcheckpoint 1990-01-10. Der erste gemeinsame 12-Tage-Ausschnitt ist zusätzlich paarweise ausgewertet; 20 Tage im endgültigen jungen Lauf.")
    view_rows = []
    view_aux = []
    for age, label in (("jung", "max-final-all-young"), ("reif", "max-final-all-mature")):
        data = run(RUNS, label)
        for view in sorted({row["view"] for row in data["rows"]}):
            rows = [row for row in data["rows"] if row["view"] == view]
            values = summary(rows)
            view_rows.append([f"{age} / {view}", len(rows), *[values[key] for key in ("T0-T1", "T1-T2", "T2-T3", "T3-T4", "T0-T4", "Heartbeat", "Bytes")]])
            view_aux.append([f"{age} / {view}", *[values[key] for key in ("Worker CPU", "Parent CPU", "Worker RSS MiB", "Parent RSS MiB", "Worker GC", "Parent GC")]])
    add(21, "Reife Welt und neun Ansichten", f"Reifer Abschlusslauf: {len(new)} gewöhnliche Übergänge aus 40, gleiche Termine und Startzustände wie die Referenz. Zusätzlich drei native Übergänge je Ansicht und Weltalter, mit aktuellen sichtbaren Kursen, GUI-Thread-Prüfung, unverändertem Ticker und abgeschlossener Worker-Beendigung.\n\n" + table(["Welt / Ansicht", "N", "T0→T1", "T1→T2", "T2→T3", "T3→T4", "T0→T4", "Heartbeat", "Bytes"], view_rows) + "\n\n" + table(["Welt / Ansicht", "Worker CPU ms", "Parent CPU ms", "Worker RSS MiB", "Parent RSS MiB", "Worker GC ms", "Parent GC ms"], view_aux) + "\n\nDie kurzen Ansichtsserien enthalten gegebenenfalls Sondertage und sind Korrektheits-/Breitenkontrollen, keine 30-Tage-Schätzung pro Ansicht.")
    detail_rows = []
    for name in ("chart", "overview", "supply"):
        first = run(RUNS, f"max-before-company-{name}")
        second = run(RUNS, f"max-final-company-{name}")
        assert first["signature"] == second["signature"]
        for label, data in (("vorher", first), ("danach", second)):
            s = summary(data["rows"])
            detail_rows.append([f"{name} {label}", s["n"], *[s[k] for k in ("T0-T1", "T1-T2", "T2-T3", "T3-T4", "T0-T4", "Heartbeat", "Bytes")]])
    add(22, "Firmen-Chart, Übersicht und Supply", table(["Fall", "N", "T0→T1", "T1→T2", "T2→T3", "T3→T4", "T0→T4", "Heartbeat", "Bytes"], detail_rows) + "\n\nJe sechs native Übergänge mit derselben tatsächlich ausgewählten Firma. Die Endsignaturen einschließlich Welt-RNG stimmen exakt mit den jeweiligen Referenzläufen überein.")
    special_rows = []
    for label, data in (("vorher", before), ("danach", mature), ("Jahresgrenze danach", year)):
        for row in data["rows"]:
            if row in normal(data["rows"]) and data is not year:
                continue
            s = summary([row])
            special_rows.append([label, row["date"], *[s[k] for k in ("T0-T1", "T1-T2", "T2-T3", "T3-T4", "T0-T4", "Heartbeat", "Bytes")]])
    add(23, "Report, Monatsende und Jahresgrenze", table(["Fall", "Startdatum", "T0→T1", "T1→T2", "T2→T3", "T3→T4", "T0→T4", "Heartbeat", "Bytes"], special_rows) + "\n\n40 separate profilierte reife Übergänge decken Report, Monatsende und Flush ab; zusätzlich gibt es ein Profil der Jahresgrenze. Veröffentlichung, Weltfortschritt und Player-Accounting bleiben in derselben Reihenfolge.")
    flush_rows = [row for row in mature["rows"] if row["worker"]["spans"].get("store.flush", 0)]
    assert flush_rows
    sql = [query for row in flush_rows for query in row["worker"]["sql"]]
    by_command = {}
    for query in sql:
        by_command[query["command"]] = by_command.get(query["command"], 0) + query["ms"]
    add(24, "Dauerhafter Flush", "Der Flush bleibt ein längerer Übergang, mit unveränderter Transaktion, vollständigen Tabellen und Historienaggregation. Gemessene native Datenbank-Aufrufzeiten sind Teil des Flush, keine zusätzliche Summanden der Gesamtlatenz.\n\n" + table(["SQL-Gruppe", "Native Gesamtzeit ms im Flush"], [[name, f"{value:.2f}"] for name, value in sorted(by_command.items(), key=lambda item: item[1], reverse=True)]) + "\n\nDatenbank- oder Publication-Arbeit wurde weder ausgelassen noch hinter T4 verschoben. Die Rohprofile unterscheiden CSV-Schreiben, native Datenbankaufrufe, Aggregation und Commit.")
    add(25, "Vollständige Tests", f"**{suite.attrib['tests']} Tests bestanden**, keine Fehler, Fehlschläge oder übersprungenen Tests. Laufzeit {float(suite.attrib['time']):.2f} s. Nachweis: {link('.cache/max-performance/full-final.xml')}. Zusätzlich wurden die Änderungen schrittweise mit fokussierten Tests und exakten reifen Vergleichen geprüft. Alle neuen Dateien bestehen Ruff; in den sechs Produktionsdateien wurden gegenüber dem Freeze keine neuen Linter-Befunde eingeführt (12 bestehende Befunde unverändert).")
    database = read(OUT / "final-reference.json")["database"]
    add(26, "365 Tage exakt", f"365 Tage mit Seed 1729 aus frischen Welten: tägliche Zustands-/RNG-Signaturen, volle Checkpoints an Tag 15/31/181/365, finaler vollständiger Checkpoint sowie {sum(entry['rows'] for entry in database.values()):,} dauerhaft geschriebene Zeilen in {len(database)} Tabellen einschließlich Historien stimmen exakt überein. Keine wirtschaftliche Toleranz oder Versionsnormalisierung. Nachweis: {link('.cache/max-performance/final-exact.json')}.")
    add(27, "Kleinanleger und Player-Accounting", f"64 Aktions-/Datumsfälle, je ein bis zwei Tage: Aktienkauf/-verkauf, Fonds, Rohstoffe, Krypto, FX, Long, Short/Schließen, Futures, Option, CDS, Bond, Kredit, Margin Call und Liquidation an gewöhnlichem Tag, Report, Monatsende und Jahresgrenze. Die vollständigen Checkpoints einschließlich Player-Accounting, PnL, Margin, Settlements und Player-RNG stimmen vor/nach diesem Pass überein. Die separate bestehende Retail-Testsuite prüft weiterhin die Unabhängigkeit der Welt von gewöhnlichen Spieler-Trades/Holdings. Nachweis: {link('.cache/max-performance/players-exact.json')}.")
    add(28, "RNG, Checkpoints, Historien und Datenbank", "Python-/NumPy-Welt-RNG und Player-RNG sind erhalten. Numerische Werte werden ohne Rundung verglichen. Datenbankhashes schließen ausschließlich nichtwirtschaftliche Laufzeitmessungen (`phase_metric_*.duration_ms`) und die pro neuem Store unabhängige UUID `history_metadata.history_id` aus; Tabelleninhalte, Zeilenzahlen, wirtschaftliche Historien und Aggregationen bleiben vollständig im Vergleich. Checkpoints werden einschließlich Version 7 und vorhandener computational caches verglichen.")
    add(29, "Save/Load und Pause", f"Native Navigation: {len(navigation['rows'])} geprüfte Wechsel/Detailfälle über alle neun Ansichten und mehrere Asset-Typen; Save/Load mit exakter Signatur nach zwischenzeitlich weitergelaufenen Tagen bestanden. Die vollständige Testsuite umfasst Pause/Resume, direkt vor der Tagesgrenze ausgeführte Trades, Margin-Stopp, abgeschlossene World-/Player-Publikation und Save/Replay. Sichtbare Charts/Historien und Ticker-Kontinuität bleiben erhalten.")
    add(30, "Verbleibende Hotspots", "Die Aktienpreisberechnung, Produktions-/Handelsabschluss und das erforderliche Schreiben begrenzter Historien dominieren den Core. Danach verbleiben persistente Tageszeilen, sichtbare Projektion/JSON, Tabellenformatierung, Ticker-Textmessung und Qt-/PyQtGraph-Paint. Seltene GC-Pausen und der dauerhafte Flush beeinflussen die Spitzen. Weitere Eingriffe benötigen neue Belege für einen großen sicheren Gewinn; eine neue Architektur wurde nicht begonnen.")
    fastest = min(new, key=lambda row: row["total_ms"])
    add(31, "Gemessene praktische Unterkante", f"Der schnellste gewöhnliche reife Übergang in der endgültigen 40-Tage-Serie betrug **{fastest['total_ms']:.2f} ms**. Das ist eine beobachtete Unterkante auf diesem Rechner, kein Beweis einer absoluten mathematischen Grenze. Core, Übertragung/Aufbereitung und korrekte Darstellung bleiben notwendige Kosten. Ein sicherer Weg unter 200 ms wurde in diesem Pass nicht nachgewiesen.")
    add(32, "Urteil zur Spiel-Flüssigkeit", "Die korrekte sichtbare Tagesaktualisierung wird spürbar früher fertig und die typische zusammenhängende Hauptthread-Belastung fällt. Die vertrauenswürdige sequentielle Architektur, alle neun Ansichten, Kleinanleger-Regel und Player-Accounting bleiben erhalten. Seltene längere Pausen und Flush-Tage bleiben reale Einschränkungen. Unter 200 ms oder vollständig unter 25-ms-Blockaden wird nicht behauptet; der Pass endet nach Entfernung der nachgewiesenen großen redundanten Arbeit.")
    REPORT.write_text("# Kojak Street – finaler Performance-Pass\n\nStand: 2026-10-06. Messungen und exakte Regressionen gegen den frisch eingefrorenen Produktionsstand.\n\n" + "\n".join(section), encoding="utf-8")
    print(REPORT, flush=True)


if __name__ == "__main__":
    main()
