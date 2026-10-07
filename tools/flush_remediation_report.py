"""Write the requested 31-point report from finished, checked evidence."""
import hashlib
import json
import statistics
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/flush-remediation'
UI = ROOT / '.cache/visible-ui-sync'
sys.path.insert(0, str(ROOT / 'tools'))
from visible_sync_report import normal, run, stats


def read(name):
    return json.loads((OUT / (name + '.json')).read_text(encoding='utf-8'))


def main():
    suite = ElementTree.parse(OUT / 'full-final.xml').getroot().find('testsuite')
    assert suite is not None and int(suite.attrib['errors']) == 0
    budgets = ElementTree.parse(OUT / 'serial-budget-final.xml').getroot().find('testsuite')
    assert budgets is not None and int(budgets.attrib['failures']) == int(budgets.attrib['errors']) == 0
    failed = [case for case in suite.findall('testcase') if case.find('failure') is not None]
    visible = ElementTree.parse(OUT / 'visible-state-final.xml').getroot().find('testsuite')
    assert visible is not None and int(visible.attrib['failures']) == int(visible.attrib['errors']) == 0
    repeated_cases = {(c.attrib['classname'], c.attrib['name']) for retest in (budgets, visible) for c in retest.findall('testcase')}
    assert all((c.attrib['classname'], c.attrib['name']) in repeated_cases for c in failed)
    exact = read('final-exact-comparison')
    assert all(exact.values())
    hashes = read('after-source-hashes')
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in hashes.items())
    before, after = run(UI, 'flush-warm-before-mature'), run(UI, 'flush-warm-final-mature')
    assert before['signature'] == after['signature']
    raw_before, raw_after = read('warm-raw-before'), read('warm-raw-synchronous')
    fixture = read('fixture')
    recovery = read('large-crash-recovery-final')
    assert all(value['exact'] for value in recovery['results'].values())
    controlled = read('synchronous-controlled-exact')
    assert all(value['exact'] for value in controlled.values())
    navigation = json.loads((UI / 'flush-final-navigation.json').read_text(encoding='utf-8'))
    assert navigation['save_load_exact'] and len(navigation['rows']) == 94
    repeated = run(UI, 'flush-final-repeated-all')
    repeated_writer = read('flush-final-repeated-all-worker-writer')[0]
    assert repeated_writer['closed'] and repeated_writer['error'] is None
    save_before, saves = read('barriers-before-v2'), read('barriers-final')
    # The first attempted queued setup used full Record, which drains SQL.
    # Replace that row with a verified actual two-slot Save/Close measurement.
    save_before = [r for r in save_before if r['mode'] != 'queued'] + read('barriers-queued-before')
    saves = [r for r in saves if r['mode'] != 'queued'] + read('barriers-queued-final')
    assert all(r['depth_before_save'] == r['depth_before_shutdown'] == 2 for r in saves if r['mode'] == 'queued')
    assert all(row['immediate_load_exact'] for row in [*save_before, *saves])
    probe = read('writer-prototype')
    sections = []

    def add(title, body):
        sections.append(f'## {len(sections) + 1}. {title}\n\n{body.strip()}\n')

    def flush_rows(result):
        return [row for row in result['rows'] if row['worker']['spans'].get('store.flush', 0)]

    def sql_values(runs, command):
        return [sum(row['ms'] for row in result['sql'] if row['command'] == command) for result in runs]

    add('Ursprüngliche Architektur und Vergleichsgrundlage', '''Dieser Auftrag betrifft ausschließlich den verbleibenden Persistenz-Stall. Die bereits vorhandenen Änderungen bleiben erhalten. Vor dem ersten Eingriff wurden 106 Produktionsdateien eingefroren; danach sind es 107. Maßgeblich ist dieser frische Stand, nicht Git-HEAD oder ein älterer Performance-Bericht.

Zuvor: Simulation → Materialisieren täglicher Zeilen und aktueller Tabellen → bei Flush eine synchrone DuckDB-Transaktion → Veröffentlichung. CSV-Erzeugung, Aggregation, WAL und Checkpoint liefen auf dem Worker des Tageswechsels. Die Welt und ihre Rechenhistorien bleiben weiterhin im bestehenden Simulationseigentümer.''')
    add('Trigger und Takt', '''IntegratedRuntime sammelt normalerweise 30 unterschiedliche Persistenztage; EconomicDataStore allein hat den bestehenden Standard von zehn Tagen. Vollständiges Record, explizites Flush, Save und Close bleiben Barrieren. Datenbankoperationen außerhalb des Flush werden ebenfalls geordnet auf demselben Eigentümer ausgeführt. Im Stresstest wurde nur im Messwerkzeug das Intervall auf zwei Tage verkürzt; der Produktionstakt wurde nicht geändert.''')
    table = ['Operation / Tabelle | Zeilen | COPY-Bytes vorher | SQL-Anweisungen vorher / nachher | Python ms vorher / nachher | SQL-API ms vorher / nachher',
             '--- | ---: | ---: | ---: | ---: | ---:']
    for kind in ('buffered', 'current'):
        for operation in raw_before[0]['operations']:
            if operation['operation'] != kind:
                continue
            name = operation['table']
            new = next(value for value in raw_after[0]['operations'] if value['operation'] == kind and value['table'] == name)
            sql_old = [value for value in raw_before[0]['sql'] if value['table'] == name]
            sql_new = [value for value in raw_after[0]['sql'] if value['table'] == name]
            byte_count = sum(value['copy_bytes'] or 0 for value in sql_old)
            table.append(f"{kind} / `{name}` | {operation['rows']} | {byte_count:,} | {len(sql_old)} / {len(sql_new)} | {operation['python_ms']:.2f} / {new['python_ms']:.2f} | {operation['duckdb_ms']:.2f} / {new['duckdb_ms']:.2f}")
    add('Tabellen, Zeilen, Bytes und Vorbereitung', f'''Reife Kopie: {fixture['database_bytes']:,} DB-Bytes vor dem Flush, {sum(fixture['rows'].values()):,} gepufferte und {sum(fixture['current_rows'].values()):,} aktuelle Zeilen. Nach dem Flush: 31 Tabellen, 1.775.592 Zeilen. Die Zeilenfixture umfasst {fixture['buffer_bytes']:,} Bytes als lokale Prüffixture; das produktive Journal benötigt für denselben Batch {probe[0]['metric']['bytes']:,} UTF-8-Bytes.

Die Tabelle zeigt jeweils den ersten unmittelbar benachbarten warmen Rohmesslauf. „SQL-API“ enthält Python-Binding und die native SQL-Ausführung; reine native Zeiten sind separat profiliert. Null COPY-Bytes bedeutet keine COPY-Datei, nicht kostenlose gebundene Daten. Python umfasst Vorbereitung, CSV, Temp-Datei und Cleanup und darf nicht nochmals mit der enthaltenen CSV-Zeit addiert werden.

''' + '\n'.join(table) + '''

Aggregation: 177.288 → 227.674 Zeilen; sämtliche bestehenden Buckets, Werte und Marker bleiben erhalten. Vollständige SQL-Texte, CPU-Zeiten, CSV-Bytes, Dateigrößen und verschachtelte Operationszeiten stehen in den Rohartefakten. COMMIT sowie BEGIN sind tabellenübergreifend; Aggregation und Cleanup sind in Punkt 23 separat ausgewiesen.''')
    add('COMMIT-Ursache', '''DuckDB 1.5.5, bestehende 24 Threads, preserve_insertion_order=true und checkpoint_threshold=16 MiB. Im separaten nativen Profil: COMMIT 1.696,84 ms, davon checkpoint_latency 1.244,92 ms; 26.480.640 geschriebene Bytes. Der Checkpoint dominiert einen erheblichen Teil der Commit-Latenz. Das Profil weist keine separate verlässliche fsync-Einzelzeit aus; diese wird nicht erfunden. Nach Commit: DB 104.607.744 Bytes, WAL 0. Transaktionsgröße und Checkpoint tragen zum Stall bei; WAL-Schwelle, Synchronisierung und Transaktionsschutz wurden nicht gelockert.''')
    add('DELETE-Ursache', '''Die 30 gebundenen Datumswerte lösten wiederholt optionale pandas-Importprüfungen aus. Der Diagnose-Lauf zählte 534 erfolglose Prüfungen mit 813,96 ms. Einzelne DELETE-API-Aufrufe kosteten etwa 95–117 ms, während das native Profil nur etwa 2–3 ms und teilweise null gescannte Zeilen auswies. Sichere DATE-Konstanten umgehen dieses Binding. Aktuelle Tabellen brauchen weiterhin vollständiges Replace, damit verschwundene Entitäten nicht stehen bleiben. Tägliche Daten brauchen datumsbezogenes Replace für Re-Record, Load und idempotentes Replay.''')
    add('COPY-Ursache', '''Viele kleine COPY-Aufrufe, CSV-Konvertierung und Dateiarbeit kommen zur großen Asset-Datei hinzu. Asset-Daily allein: 10.974.147 CSV-Bytes. CSV sowie native COPY sind beide echte Kosten; Transport und Datenbankarbeit werden im Bericht getrennt. Kleine Texttabellen nutzen jetzt denselben bereits vorhandenen präzisen Parameter-CSV-Codec wie die Phasenwerte. Null, Leerstring, wörtliches Backslash-N, Unicode, Quotes und Zeilenumbrüche wurden gegen die alte Parameterbindung verglichen.''')
    add('Synchrone Kandidaten', '''Übernommen: validierte kanonische DATE-Konstanten bei Datumslöschung und Cutoffs; sichere kleine Textbatches über den vorhandenen Codec. Nicht-kanonische Datumseingaben bleiben gebunden; nicht-textuelle Eingaben behalten die alte Parameterkonvertierung.

Isoliert geprüft: DATE-Literale; NumPy-Relationen; globale Ein-Thread-Ausführung; ein Thread nur für COPY oder COMMIT; temporäre Staging-Tabelle mit anschließendem INSERT. NumPy erforderte abweichende Null/NaN-Konvertierungen und überschritt im typisierten Versuch 45 s. Globale Ein-Thread-Ausführung verändert parallel berechnete Float-Bits und bleibt ein Testmittel. COPY-/COMMIT-Umschaltung brachte keinen belastbaren Vorteil. Staging war im warmen Vergleich langsamer (Median ''' + stats([value['ms'] for value in read('candidate-staging')]) + ''' ms gegenüber dem direkten Weg in Punkt 8) und fügte CREATE/INSERT/DROP hinzu.

Key-Upserts ändern ohne neue Schlüssel die vorhandene Duplikat- und Datumsreplacement-Semantik; reine aktuelle Upserts lassen entfernte Entitäten zurück. Sie werden daher nicht als sichere Ersatzoperation behandelt. Keine neue Schlüsseldeklaration oder spekulative Schemaänderung. Bestehende Compaction-Marker überspringen unveränderte Buckets bereits; Aggregatmathematik und Retention bleiben unverändert.''')
    add('Synchrone Vorher/Nachher-Messung', f'''Warme, unmittelbar benachbarte Rohmessungen, n=3 je Variante, Median / p95 / Maximum in ms: vorher **{stats([r['ms'] for r in raw_before])}**, synchron optimiert **{stats([r['ms'] for r in raw_after])}**. Der frühere instrumentierte Audit ergab 5.872,68 → 5.020,77 ms Median; Instrumentierungs- und native Zeiten werden nicht gemischt.

Im ersten nativen Drei-Sekunden-Lauf: Flush-Tageswechsel 5.046,08 → 3.412,88 ms; eigentlicher Flush 4.637,72 → 2.994,53 ms. Das verbleibt ein mehrsekündiger Stall und rechtfertigt die weitere Writer-Prüfung. Alle 31 Tabellen der identischen Fixture sind im kontrollierten Vorher/Nachher-Vergleich exakt, inklusive Schema, Metadata und Aggregaten; keine Toleranz.''')
    add('A–G-Klassifizierung und Persistenzpflicht', '''Klasse | Daten | Vertrag
--- | --- | ---
A / F | Alle `*_daily`, `news_events`, `event_log` | Vollständige Werte; Datumsreplacement statt blindem Append für Replay/Load. Bisherige Tagespuffer bleiben erlaubt.
B / F / G | Alle `*_current`, `news_current`, `event_current` | Vollständiges Replace einschließlich leerer Tabellen; aus Welt/Recorder rekonstruierbar, trotzdem unverändert persistiert.
C / F | `history_aggregate` | Monatliche/jährliche Buckets, alle Semantikfelder und Retention; nach Raw-Trim nicht beliebig rekonstruierbar.
D | `phase_metric_daily`, `phase_metric_current` | Weiterhin alle Zeilen/Spalten persistiert; Laufzeitmesswerte schwanken naturgemäß zwischen unabhängigen Läufen.
E / F | `history_metadata` | History-ID, Schema-/Modellversion und Compaction-Marker vollständig erhalten.
A / E / F | `structural_event` | Bestehende IDs und Event-Upserts unverändert; kein doppeltes Replay.
F | Spielstand / Checkpoint / RNG / Analytics-Manifest | Save wartet auf DuckDB-Commit und schreibt erst danach den bestehenden atomaren Spielstand.

G erlaubt hier keine ausgelassene Persistenz. Für einen automatischen Flush muss vor sichtbarer Veröffentlichung ein vollständiger dauerhafter Batch vorhanden sein. Bereits erlaubte Nicht-Flush-Tagespuffer erhalten dieselben bisherigen Grenzen.''')
    add('Durability und Veröffentlichung', '''Gewählte Reihenfolge: Simulation → unveränderliche bereits materialisierte Zeilen → vollständiger Batch mit Länge, SHA-256, History-ID und Sequenz im fsync-geschützten Journal → Veröffentlichung → geordnete DuckDB-Transaktion → COMMIT → fsync-geschütztes Journal-ACK. Keine Veröffentlichung allein aufgrund einer RAM-Queue.

Die analytische DB darf kurz hinterherlaufen, weil vor dem bisherigen Flush-Veröffentlichungspunkt bereits ein vollständiger Replay-Batch dauerhaft vorliegt. DB-Leser sind Barrieren. Save bestätigt erst DuckDB-Commit plus den vorhandenen atomaren Checkpoint. Das Journal ersetzt keinen Welt-Checkpoint: ungespeicherte Weltfortschritte haben den bisherigen Save-Vertrag. Physischer Stromverlust wurde nicht emuliert; es gelten dieselben Betriebssystem-/Dateisystem-/Hardware-Fsync-Annahmen. Beschädigte Dateien führen zu einem sichtbaren Abbruch statt zu geratenen Daten.''')
    add('Entscheidung zum Hintergrund-Writer', '''Ein einzelner Writer ist nach den synchronen Restkosten erforderlich und durch die nachstehenden Queue-, Save-, Crash-, Recovery- und Regressionsprüfungen unterstützt. Aktiv im Live-Worker nach abgeschlossener Initialisierung. Direkte/headless Runtime bleibt standardmäßig synchron; die Langzeitprüfungen aktivieren den Writer ausdrücklich. Transiente In-Memory-Stores aktivieren ihn nicht; vorhandene dauerhafte Journale dürfen dort nicht scheinbar recovered werden.''')
    add('Verbindungseigentum', '''Genau ein nicht-daemonischer Owner-Thread öffnet und benutzt die aktive DuckDB-Verbindung. Initialisierung und Schemaarbeit sind vor der Übergabe beendet. Simulation und GUI besitzen keine parallele SQL-Verbindung. Alle späteren SQL-Leser und -Schreiber laufen als geordnete Calls auf demselben Owner; ein Ergebnis wird atomar materialisiert, bevor der nächste Auftrag es überschreiben könnte. Der SQL-Batch-Target hat ausschließlich eine Verbindung, keine Welt-, RNG-, Session- oder Current-Cache-Referenz.''')
    add('Queue und Doppelbuffer', '''Zwei feste wiederverwendbare Journal-Slots, höchstens zwei ausstehende Datenbatches insgesamt einschließlich des aktiven Batches. Auftragsqueue maxsize=3; immutable Tupel enthalten nur str/int/float/None. Maximal 64 MiB kodierte Daten je Batch; damit höchstens 128 MiB plus zwei 4-KiB-Header auf Disk. Zu große Batches nehmen nach Drain den synchronen Weg mit denselben Transaktionen. Keine Vollweltkopie und keine unbeschränkte Queue. Die Datei wird vor Veröffentlichung vollständig geschrieben und fsynced; nach Commit wird der Header dauerhaft geleert, ohne von durable unlink abhängig zu sein.''')
    add('Backpressure und Fehlerpolitik', '''Freie Slots werden nur nach COMMIT und dauerhaftem ACK zurückgegeben. Ein dritter Produzent wartet; die Ordnung bleibt erhalten. Fehler werden gelatcht, stoppen weitere Tageswechsel und SQL-Aufträge und erhalten das Journal zur Recovery. Kein stiller Retry über einen unklaren Commit hinweg. Ein Neustart replayt idempotent; beschädigte Header/Checksums, fehlende Slots oder falsche History-ID werden zurückgewiesen. Fsync-Fehler vor Veröffentlichung löschen keine Puffer. Writer-Fehler werden über ein gesondertes Protokollereignis auch während Pause sichtbar, ohne Antwort-IDs zu verschieben; die UI stoppt den Spieltakt.''')
    add('Save-Vertrag und gemessene Kosten', '''Save wartet bei leerem, aktivem oder belegtem Writer auf alle Vorgänger und den vollständigen Save-Record. Erst danach wird der Checkpoint atomar geschrieben und Erfolg gemeldet. Die folgenden Zeiten enthalten auch die bestehende vollständige Save-Erzeugung und sind keine reinen Flush-Zeiten.

Variante / Zustand | n | Save Median / p95 / max ms | Shutdown Median / p95 / max ms
--- | ---: | ---: | ---:
''' + '\n'.join(f"{label} / {mode} | {len(rows)} | {stats([r['save_ms'] for r in rows])} | {stats([r['shutdown_ms'] for r in rows])}" for label, source in [('Vorher synchron', save_before), ('Nachher Writer', saves)] for mode in ('idle', 'active', 'queued') if (rows := [r for r in source if r['mode'] == mode])) + '''

Der synchrone Vorher-Code kennt keinen laufenden Hintergrund-Writer; active/queued bezeichnen dort denselben vorbereiteten noch ungeflushten Datenbestand. Nachher werden wirkliche SQL-Batches gestartet. Der tatsächliche Queued-Fall belegt nach gewöhnlichem Tagesfortschritt vor Save und Shutdown nachweislich beide Slots (n=1). Der erste Versuch mit vollständigem Record drainte den ersten Batch bereits vor Save und ist hierfür keine Ergebnisquelle. Keine künstliche Writer-Verzögerung in diesen Leistungsmessungen.''')
    add('Load und Recovery', '''Load wartet vor Weltrestore und Analytics-Reset auf den Owner. Save lädt unmittelbar danach wieder exakt denselben Wirtschafts- und RNG-Zustand. Die Tests vergleichen außerdem den vollständigen kodierten Folgetag nach Load mit dem ununterbrochenen Folgetag. Startup prüft History-ID, Format, Länge und SHA-256, replayt nach Sequenz und ACKt erst nach erfolgreichem COMMIT. Nach einem bereits erfolgreichen, aber nicht ACKten Commit bleibt Replay idempotent.''')
    add('Fehler- und Crash-Injection', '''Sechs Prozessabstürze mit Exit 91: vor BEGIN, während COPY, vor COMMIT, während nativem COMMIT, nach COMMIT vor ACK und nach ACK. Große Kopie: alle 31 Tabellen, 1.775.592 Zeilen, identische Schema-/Metadata-/Aggregatwerte und erneut leeres Journal nach Recovery. COPY/COMMIT werden beim großen Versuch durch Timer mitten in der nativen Ausführung unterbrochen.

Zusätzlich: Rollback bei BEGIN/COPY/COMMIT-Fehler, beschädigtes Journal, andere History-ID, persistenter Writer-Fehler, Fsync-Fehler ohne falsches ACK, fehlender Journal-Slot, unklare Commit-Bestätigung mit exakt idempotentem Retry, Startup-Replay-Fehler einschließlich zusätzlichem Close-Fehler, Übergrößenfallback und blockierter dritter Batch. Kleine Crash-Tests kontrollieren unmittelbar nach dem Absturz „ganze alte“ oder „ganze neue“ Transaktion. Wiederholtes Replay erzeugt keine Duplikate.''')
    add('Shutdown', '''Shutdown ist eine geordnete Drain-Barriere. Der Live-Worker ACKt Shutdown erst nach seinem expliziten Flush; anschließend beendet und joint er den nicht-daemonischen Owner. Close-Fehler wecken wartende Aufrufer und werden nicht verschluckt. Die Busy-/Queued-Tests prüfen geschlossenen Thread, leeres Journal und wieder geöffnetes History-Manifest; Zeiten stehen in Punkt 15. Ein fehlgeschlagener Writer liefert keinen scheinbar erfolgreichen Shutdown.''')
    add('Geänderte Dateien', '\n'.join('- `' + name + '`' for name in read('changed-production-files')) + '''

`data_store`: sichere synchrone Konvertierung, Recovery, Writer-Übergabe und Barrieren. `persistence_writer`: Journal, Queue und alleiniger SQL-Owner. `legacy_runtime`: Health-/Load-Barrieren. `live_worker`/`live_process`: Aktivierung, geordnetes Protokoll und Fehlerweitergabe. `ui_qt/app`: Fehleranzeige über den bestehenden Timer. Neue Tests: `test_flush_remediation.py`, `test_persistence_writer.py`; `test_visible_state.py` ergänzt die neue Health-Schnittstelle im Testmodell und kontrolliert ihren Aufruf. Neue Auditwerkzeuge: `flush_remediation_*`, `flush_writer_probe.py`, `flush_writer_recovery.py`. Kein Commit, keine Schema-/Gameplayänderung. Der vollständige ausschließlich aktuelle Diff liegt in `current-pass-production.diff`.''')
    old_normal, new_normal = normal(before['rows']), normal(after['rows'])
    add('Gewöhnlicher Tageswechsel', f'''Warmer nativer Windows-Lauf, derselbe 365-Tage-Checkpoint, echte Drei-Sekunden-Anfragen, jeweils {len(old_normal)} / {len(new_normal)} gewöhnliche Tage: T0→T4 vorher **{stats([r['total_ms'] for r in old_normal])}**, nachher **{stats([r['total_ms'] for r in new_normal])}** ms. Maximale Heartbeat-Lücke je Tag vorher **{stats([max(r['heartbeat_gaps_ms']) for r in old_normal])}**, nachher **{stats([max(r['heartbeat_gaps_ms']) for r in new_normal])}** ms. Wirtschaftscode ist unverändert; unterschiedliche Systemzustände werden nicht als kausale Verbesserung des Simulationskerns verkauft.''')
    add('Sichtbarer Flush-Tageswechsel', f'''Warme native Reihe, n={len(flush_rows(before))} / {len(flush_rows(after))}: vorher **{stats([r['total_ms'] for r in flush_rows(before)])}**, nachher **{stats([r['total_ms'] for r in flush_rows(after)])}** ms. Der erste unabhängige Vergleich ergab 5.046,08 ms vor, 3.412,88 ms synchron optimiert und 1.075,54 ms mit Writer. Einzelne reguläre Monatsflushes liefern keine belastbare Verteilungsabschätzung; deshalb zusätzlich zehn reale wiederholte Flushes in Punkt 28. Veröffentlichung ist jeweils erst nach dauerhaftem Journal-Handoff erlaubt; DB-Commit erfolgt anschließend.''')
    metrics = read('flush-warm-final-mature-worker-writer')[0]['metrics']
    add('Rohflush, Writer und Handoff', f'''Rohflush vorher: **{stats([r['ms'] for r in raw_before])}** ms; synchron optimiert: **{stats([r['ms'] for r in raw_after])}** ms, n=3 je Variante. Großer isolierter Batch mit unveränderten Zeilen: Handoff einschließlich Freeze **{stats([r['handoff_ms'] for r in probe])}** ms; Handoff bis vollständig abgearbeitet **{stats([r['total_ms'] for r in probe])}** ms. Das ist reale zusätzliche Journalarbeit, keine verkürzte Datenbanktransaktion.

Native Writer-Dauern einschließlich Bootstrap/Monatsflush/Shutdown: **{stats([m['writer_ms'] for m in metrics])}** ms; reine Journal-Handoff-Zeiten **{stats([m['handoff_ms'] for m in metrics])}** ms. `freeze_ms` und `queue_wait_ms` werden getrennt erfasst; das ältere Feld `backpressure_ms` enthält auch Freeze-Vorbereitung und darf nicht als reine Slotwartezeit gelesen werden.''')
    operation_rows = ['Gruppe | Vorher Median / p95 / max ms | Synchron nachher Median / p95 / max ms', '--- | ---: | ---:']
    for command in ('BEGIN', 'DELETE', 'COPY', 'INSERT', 'SELECT', 'COMMIT'):
        operation_rows.append(f'{command} | {stats(sql_values(raw_before, command))} | {stats(sql_values(raw_after, command))}')
    for label, extract in [
        ('Python/Temp/Cleanup außerhalb SQL-API', lambda r: r['ms'] - sum(v['ms'] for v in r['sql'])),
        ('Beobachtete generische CSV-Zeit (Teil der Vorbereitung)', lambda r: sum(o['ms'] for o in r['operations'] if o['operation'] == 'csv')),
        ('Aggregation/Compaction (überlappt SQL-Gruppen)', lambda r: next(o['ms'] for o in r['operations'] if o['operation'] == 'compaction')),
    ]:
        operation_rows.append(f'{label} | {stats([extract(r) for r in raw_before])} | {stats([extract(r) for r in raw_after])}')
    add('SQL-Gruppen und Vorbereitung', '\n'.join(operation_rows) + '''

Die Zeiten sind API-Wallzeiten auf identischen isolierten Kopien, keine addierbaren unabhängigen Profilerphasen. Text-/Phasen-CSV benutzt einen eigenen Codec; dessen Zeit liegt in Python-Vorbereitung und nicht vollständig in der generischen CSV-Zeile. Temp-Dateien werden in finally entfernt. Aggregation wird nicht verzögert, ausgelassen oder als fremde Kategorie verborgen.''')
    cadences = [b['t0'] - a['t0'] for a, b in zip(repeated['rows'], repeated['rows'][1:])]
    rm = repeated_writer['metrics']
    add('Durchsatz und Queue-Tiefe', f'''20 Tage, zehn automatische Flushes, alle neun Ansichten. Tatsächlicher Abstand der T0-Anfragen: {statistics.median(cadences):.3f} s Median, {min(cadences):.3f}–{max(cadences):.3f} s. Die beobachtete Queue-Tiefe blieb maximal {max(m['queue_depth'] for m in rm)}; Produktion kann höchstens zwei Batches belegen. Maximal gemessene reine Slotwartezeit: {max(m.get('queue_wait_ms', 0) for m in rm):.3f} ms. Writer-Zeiten: **{stats([m['writer_ms'] for m in rm])}** ms. Es entsteht bei diesem geprüften Takt kein wachsender Rückstau. Die absichtlich langsamere Unit-Injection zeigt die definierte blockierende Backpressure und strikt gleiche Reihenfolge statt verlorener Daten.''')
    add('RAM, RSS und Disk', f'''Große Fixture: {fixture['buffer_bytes']:,} Bytes lokale binäre Prüffixture, produktiver JSON-Batch {probe[0]['metric']['bytes']:,} Bytes. RSS in MiB, Median / p95 / Maximum: vor Handoff **{stats([r['rss_before'] / 2**20 for r in probe])}**, nach Handoff **{stats([r['rss_handoff'] / 2**20 for r in probe])}**, nach Writer **{stats([r['rss_done'] / 2**20 for r in probe])}**. Die Zunahme umfasst DuckDB-Puffer und Zeilen, nicht nur den Batch. Peak zwischen Messpunkten wurde nicht bestimmt. Beide Journaldateien benötigen in diesem Versuch zusammen {probe[0]['journal_bytes']:,} Bytes; die feste maximale Diskgrenze ist 128 MiB plus Header.

Native Messungen enthalten Worker-RSS pro Tagesanfang/-ende. Das Spiel behält weiterhin seine bestehenden begrenzten Rechenhistorien; RowBatch enthält nur skalare Persistenzzeilen. Der separate Save-Messaufbau hält zur Reproduzierbarkeit einen Welt-Checkpoint im Auditwerkzeug; das ist kein produktiver Writer-Puffer und wird nicht als produktiver RAM-Wert verwendet.''')
    add('Tests und statische Prüfung', f'''Gesamte aktuelle Testsuite: **{suite.attrib['tests']} Tests**, zunächst zwei Fehlschläge, {float(suite.attrib['time']):.2f} s. Das monatliche Zeitbudget scheiterte unter paralleler Last (73,13 statt höchstens 70 ms); alle drei Budgettests bestanden anschließend einzeln ohne diese Last. Das sichtbare Zustands-Testmodell benötigte die neue Health-Schnittstelle und prüft jetzt ihren Aufruf; alle zehn zugehörigen Tests bestanden. Damit sind alle 472 Tests abschließend validiert. Die ursprüngliche Suite und beide Retests bleiben getrennt als XML dokumentiert. Der bereits vor diesem Auftrag vorhandene Suite-Erfolg wird nicht dafür verwendet. Alle 31 neuen Flush-/Writer-Tests bestanden; sie prüfen Konvertierung, Transaktion, Eigentum, Crash, Backpressure und Save/Load. Neue Module/Werkzeuge/Tests bestehen Ruff; der bestehende Importordnungsbefund in data_store.py ist bereits in der eingefrorenen Referenz vorhanden.''')
    add('Exakter Ein- und Zwei-Jahresvergleich', '''365 Tage mit den unveränderten nativen Thread-Einstellungen: jeder tägliche Welt-/RNG-Vergleich, vollständige Zwischen- und Abschlusscheckpoints, Tabellenwerte und Zeilenzahlen stimmen exakt. 730 Tage mit für beide Prüfseiten kontrollierten SQL-Threads=1: ebenfalls exakt, einschließlich aller Aggregate. Diese Einstellung dient ausschließlich der Prüfung; Produktion bleibt bei 24 Threads. 64 Spieler-Szenarien über vier Datumsgrenzen stimmen im vollständigen Zustand überein.

Bei unabhängigen Weltläufen werden ausschließlich zufällige History-UUID und gemessene duration_ms aus dem Vergleich entfernt; ihre übrigen Spalten/Zeilen bleiben geprüft. In identischen Fixture-/Recovery-Vergleichen gibt es keine solchen Ausnahmen, keine Rundung und keine Float-Toleranz.

**Vorbestandene Einschränkung:** Zwei unveränderte native 24-Thread-Flushes auf derselben großen Fixture unterscheiden sich bereits in den letzten Float-Bits jährlicher AVG-Werte; die anderen 30 Tabellen stimmen exakt. Die Audit-Analyse fand 1.081 von 227.674 Aggregatzeilen mit ausschließlich unterschiedlichen mean_value-Bits. Dies wird nicht durch Toleranzen verdeckt oder durch eine Produktionsänderung „repariert“. Für exakte Recovery-/Mehrjahresprüfung wurde deshalb die gleiche kontrollierte Ausführungsreihenfolge auf beiden Seiten eingesetzt. Eine allgemeine bitweise Wiederholbarkeit nativer paralleler Jahres-AVG wird nicht behauptet.''')
    fr = flush_rows(repeated)
    add('Wiederholte Flushes und sichtbare UI', f'''Zehn Flush-Tageswechsel: T0→T4 **{stats([r['total_ms'] for r in fr])}** ms; alle 20 Tage **{stats([r['total_ms'] for r in repeated['rows']])}** ms. Größte Heartbeat-Lücke je Tag: **{stats([max(r['heartbeat_gaps_ms']) for r in repeated['rows']])}** ms. Alle Rows prüfen aktuelle Daten am Veröffentlichungspunkt, Qt-Main-Thread und sichtbare Ticker-Geometrie/Quotes. Reale Windows-UI zusätzlich: junge 20 Tage, alle neun jungen Ansichten 27 Tage, alle neun reifen Ansichten 27 Tage sowie 94 Navigationsfälle mit 35 versteckten Fortschrittstagen. Kein Writer-Fehler, sauberes Ende.''')
    add('Save/Load-Gesamtergebnis', '''Sämtliche native Backend-Barriermessungen bestätigen unmittelbares exaktes Load nach Save. Native Navigation bestätigt Save/Load nach verstecktem Fortschritt. Unit-Prüfungen halten den aktiven Writer gezielt an, belegen beide Slots, verhindern vorzeitigen Save-Erfolg und vergleichen den nächsten vollständigen Welt-/RNG-Checkpoint. Recovery prüft identische History-ID und Metadata; kein halber DB-Zustand und keine verwaisten bestätigten Batches. Save-Zeiten sind vollständig in Punkt 15 ausgewiesen.''')
    add('Verbleibende Kosten', '''DuckDB-COMMIT/Checkpoint, Aggregation, CSV/COPY und Journalkodierung bleiben echte Arbeit. Große Saves serialisieren weiterhin den vollständigen bestehenden Checkpoint und sind teuer. Explizite historische Abfragen, Save, Load und Shutdown sind geordnete Barrieren und können warten. In der Navigation brauchte die kalte Product-Detail-Abfrage 3.168,36 ms; das ist kein gewöhnlicher Flush-Tageswechsel und wird nicht als verschwundener Engpass ausgegeben. Übergrößen und ein langsamerer Datenträger können den ausdrücklich synchronen Rückfall bzw. Backpressure auslösen. Die getestete Hardware/Taktkombination garantiert keine beliebigen Produzentenraten.''')
    add('Urteil und Nachweise', '''Der mehrsekündige automatische Flush-Stall im geprüften Gameplay-Pfad ist beseitigt. Das Ergebnis beruht auf synchroner Konvertierungsoptimierung und einem einzelnen geordneten Writer mit vorherigem dauerhaftem Journal-Handoff. Es wurden weder Daten ausgelassen noch Commit-Schutz, Retention oder Save-Erfolg abgeschwächt. Die bekannte native Jahres-AVG-Nichtwiederholbarkeit bleibt ausdrücklich dokumentiert; alle beschriebenen exakten Prüfungen benutzen keine Toleranzen.

Nachweise: `.cache/flush-remediation/{before-source-hashes,after-source-hashes,current-pass-production.diff,fixture,warm-raw-before,warm-raw-synchronous,candidate-staging,synchronous-controlled-exact,large-crash-recovery-final,final-exact-comparison,barriers-before-v2,barriers-final,barriers-queued-before,barriers-queued-final,full-final.xml,serial-budget-final.xml,visible-state-final.xml}` und `.cache/visible-ui-sync/flush-*`. Verworfene bzw. abgebrochene Messaufbauten sind keine Ergebnisquelle. Native Leistungsmessungen liefen seriell ohne gleichzeitig laufende Langzeitprüfungen. Die funktionale Suite und exakten Vergleiche liefen anschließend parallel; darin enthaltene Budgettests wurden abschließend allein wiederholt. Die tatsächlichen Queued-Barriermessungen liefen ebenfalls erst nach Ende aller Regressionsläufe.''')
    report = ROOT / 'docs/final-duckdb-flush-remediation-2026-10-06.md'
    report.write_text('# Kojak Street – vollständiger Flush-Audit und sichere Remediation\n\n'
                      'Auftrag vom 6. Oktober 2026, abgeschlossen am 7. Oktober (Berlin). Alle Performance-Verteilungen: Median / interpoliertes p95 / Maximum; ms, sofern nicht anders angegeben.\n\n'
                      + '\n'.join(sections), encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()
