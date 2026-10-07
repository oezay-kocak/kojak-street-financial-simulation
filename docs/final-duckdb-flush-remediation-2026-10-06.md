# Kojak Street – vollständiger Flush-Audit und sichere Remediation

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Auftrag vom 6. Oktober 2026, abgeschlossen am 7. Oktober (Berlin). Alle Performance-Verteilungen: Median / interpoliertes p95 / Maximum; ms, sofern nicht anders angegeben.

## 1. Ursprüngliche Architektur und Vergleichsgrundlage

Dieser Auftrag betrifft ausschließlich den verbleibenden Persistenz-Stall. Die bereits vorhandenen Änderungen bleiben erhalten. Vor dem ersten Eingriff wurden 106 Produktionsdateien eingefroren; danach sind es 107. Maßgeblich ist dieser frische Stand, nicht Git-HEAD oder ein älterer Performance-Bericht.

Zuvor: Simulation → Materialisieren täglicher Zeilen und aktueller Tabellen → bei Flush eine synchrone DuckDB-Transaktion → Veröffentlichung. CSV-Erzeugung, Aggregation, WAL und Checkpoint liefen auf dem Worker des Tageswechsels. Die Welt und ihre Rechenhistorien bleiben weiterhin im bestehenden Simulationseigentümer.

## 2. Trigger und Takt

IntegratedRuntime sammelt normalerweise 30 unterschiedliche Persistenztage; EconomicDataStore allein hat den bestehenden Standard von zehn Tagen. Vollständiges Record, explizites Flush, Save und Close bleiben Barrieren. Datenbankoperationen außerhalb des Flush werden ebenfalls geordnet auf demselben Eigentümer ausgeführt. Im Stresstest wurde nur im Messwerkzeug das Intervall auf zwei Tage verkürzt; der Produktionstakt wurde nicht geändert.

## 3. Tabellen, Zeilen, Bytes und Vorbereitung

Reife Kopie: 98,316,288 DB-Bytes vor dem Flush, 116,033 gepufferte und 23,856 aktuelle Zeilen. Nach dem Flush: 31 Tabellen, 1.775.592 Zeilen. Die Zeilenfixture umfasst 8,849,620 Bytes als lokale Prüffixture; das produktive Journal benötigt für denselben Batch 18,812,709 UTF-8-Bytes.

Die Tabelle zeigt jeweils den ersten unmittelbar benachbarten warmen Rohmesslauf. „SQL-API“ enthält Python-Binding und die native SQL-Ausführung; reine native Zeiten sind separat profiliert. Null COPY-Bytes bedeutet keine COPY-Datei, nicht kostenlose gebundene Daten. Python umfasst Vorbereitung, CSV, Temp-Datei und Cleanup und darf nicht nochmals mit der enthaltenen CSV-Zeit addiert werden.

Operation / Tabelle | Zeilen | COPY-Bytes vorher | SQL-Anweisungen vorher / nachher | Python ms vorher / nachher | SQL-API ms vorher / nachher
--- | ---: | ---: | ---: | ---: | ---:
buffered / `product_daily` | 3720 | 638,358 | 2 / 2 | 26.42 / 28.77 | 114.15 / 35.62
buffered / `bond_daily` | 3640 | 939,073 | 2 / 2 | 34.06 / 36.96 | 116.45 / 39.59
buffered / `asset_daily` | 75690 | 10,974,147 | 2 / 2 | 351.42 / 342.61 | 213.55 / 131.93
buffered / `global_macro_daily` | 660 | 32,225 | 2 / 2 | 5.71 / 5.70 | 102.53 / 16.09
buffered / `forex_daily` | 12600 | 781,811 | 2 / 2 | 28.20 / 28.92 | 123.87 / 36.28
buffered / `phase_metric_daily` | 460 | 24,378 | 2 / 2 | 5.69 / 5.57 | 94.43 / 14.60
buffered / `company_daily` | 1280 | 258,017 | 2 / 2 | 14.64 / 13.87 | 26.45 / 24.41
buffered / `country_daily` | 20 | 7,047 | 2 / 2 | 4.48 / 4.47 | 7.92 / 4.94
buffered / `company_output_daily` | 13066 | 719,283 | 2 / 2 | 30.06 / 29.89 | 39.98 / 37.70
buffered / `country_trade_daily` | 2480 | 314,427 | 2 / 2 | 17.06 / 16.87 | 32.01 / 29.79
buffered / `fund_allocation_daily` | 2381 | 126,199 | 2 / 2 | 9.21 / 8.64 | 27.04 / 29.07
buffered / `portfolio_daily` | 30 | 960 | 2 / 2 | 4.60 / 5.01 | 81.38 / 4.95
buffered / `news_events` | 3 | 0 | 2 / 2 | 2.80 / 4.35 | 31.06 / 3.81
buffered / `event_log` | 3 | 0 | 2 / 2 | 2.85 / 4.47 | 53.94 / 3.64
current / `asset_current` | 2523 | 365,382 | 2 / 2 | 16.81 / 15.83 | 31.42 / 30.63
current / `product_current` | 124 | 21,299 | 2 / 2 | 4.99 / 4.96 | 11.00 / 11.73
current / `company_current` | 1280 | 258,017 | 2 / 2 | 14.09 / 14.58 | 24.54 / 22.90
current / `company_output_current` | 13066 | 719,283 | 2 / 2 | 27.76 / 29.12 | 37.12 / 38.71
current / `country_trade_current` | 2480 | 314,427 | 2 / 2 | 16.44 / 17.21 | 27.82 / 27.63
current / `fund_allocation_current` | 2381 | 126,199 | 2 / 2 | 8.79 / 8.46 | 25.43 / 27.15
current / `country_current` | 20 | 7,047 | 2 / 2 | 4.64 / 4.16 | 5.11 / 4.53
current / `global_macro_current` | 22 | 1,069 | 2 / 2 | 4.10 / 4.20 | 3.89 / 3.54
current / `forex_current` | 420 | 26,051 | 2 / 2 | 4.89 / 4.82 | 12.58 / 12.23
current / `portfolio_current` | 1 | 32 | 2 / 2 | 4.25 / 4.62 | 3.73 / 3.74
current / `news_current` | 0 | 0 | 1 / 1 | 1.59 / 1.21 | 0.46 / 0.54
current / `event_current` | 0 | 0 | 1 / 1 | 1.28 / 1.11 | 0.64 / 0.50
current / `phase_metric_current` | 15 | 798 | 2 / 2 | 3.88 / 3.72 | 4.21 / 3.53
current / `bond_current` | 1524 | 371,924 | 2 / 2 | 16.88 / 15.71 | 26.40 / 24.80

Aggregation: 177.288 → 227.674 Zeilen; sämtliche bestehenden Buckets, Werte und Marker bleiben erhalten. Vollständige SQL-Texte, CPU-Zeiten, CSV-Bytes, Dateigrößen und verschachtelte Operationszeiten stehen in den Rohartefakten. COMMIT sowie BEGIN sind tabellenübergreifend; Aggregation und Cleanup sind in Punkt 23 separat ausgewiesen.

## 4. COMMIT-Ursache

DuckDB 1.5.5, bestehende 24 Threads, preserve_insertion_order=true und checkpoint_threshold=16 MiB. Im separaten nativen Profil: COMMIT 1.696,84 ms, davon checkpoint_latency 1.244,92 ms; 26.480.640 geschriebene Bytes. Der Checkpoint dominiert einen erheblichen Teil der Commit-Latenz. Das Profil weist keine separate verlässliche fsync-Einzelzeit aus; diese wird nicht erfunden. Nach Commit: DB 104.607.744 Bytes, WAL 0. Transaktionsgröße und Checkpoint tragen zum Stall bei; WAL-Schwelle, Synchronisierung und Transaktionsschutz wurden nicht gelockert.

## 5. DELETE-Ursache

Die 30 gebundenen Datumswerte lösten wiederholt optionale pandas-Importprüfungen aus. Der Diagnose-Lauf zählte 534 erfolglose Prüfungen mit 813,96 ms. Einzelne DELETE-API-Aufrufe kosteten etwa 95–117 ms, während das native Profil nur etwa 2–3 ms und teilweise null gescannte Zeilen auswies. Sichere DATE-Konstanten umgehen dieses Binding. Aktuelle Tabellen brauchen weiterhin vollständiges Replace, damit verschwundene Entitäten nicht stehen bleiben. Tägliche Daten brauchen datumsbezogenes Replace für Re-Record, Load und idempotentes Replay.

## 6. COPY-Ursache

Viele kleine COPY-Aufrufe, CSV-Konvertierung und Dateiarbeit kommen zur großen Asset-Datei hinzu. Asset-Daily allein: 10.974.147 CSV-Bytes. CSV sowie native COPY sind beide echte Kosten; Transport und Datenbankarbeit werden im Bericht getrennt. Kleine Texttabellen nutzen jetzt denselben bereits vorhandenen präzisen Parameter-CSV-Codec wie die Phasenwerte. Null, Leerstring, wörtliches Backslash-N, Unicode, Quotes und Zeilenumbrüche wurden gegen die alte Parameterbindung verglichen.

## 7. Synchrone Kandidaten

Übernommen: validierte kanonische DATE-Konstanten bei Datumslöschung und Cutoffs; sichere kleine Textbatches über den vorhandenen Codec. Nicht-kanonische Datumseingaben bleiben gebunden; nicht-textuelle Eingaben behalten die alte Parameterkonvertierung.

Isoliert geprüft: DATE-Literale; NumPy-Relationen; globale Ein-Thread-Ausführung; ein Thread nur für COPY oder COMMIT; temporäre Staging-Tabelle mit anschließendem INSERT. NumPy erforderte abweichende Null/NaN-Konvertierungen und überschritt im typisierten Versuch 45 s. Globale Ein-Thread-Ausführung verändert parallel berechnete Float-Bits und bleibt ein Testmittel. COPY-/COMMIT-Umschaltung brachte keinen belastbaren Vorteil. Staging war im warmen Vergleich langsamer (Median 3,742.28 / 3,856.64 / 3,869.35 ms gegenüber dem direkten Weg in Punkt 8) und fügte CREATE/INSERT/DROP hinzu.

Key-Upserts ändern ohne neue Schlüssel die vorhandene Duplikat- und Datumsreplacement-Semantik; reine aktuelle Upserts lassen entfernte Entitäten zurück. Sie werden daher nicht als sichere Ersatzoperation behandelt. Keine neue Schlüsseldeklaration oder spekulative Schemaänderung. Bestehende Compaction-Marker überspringen unveränderte Buckets bereits; Aggregatmathematik und Retention bleiben unverändert.

## 8. Synchrone Vorher/Nachher-Messung

Warme, unmittelbar benachbarte Rohmessungen, n=3 je Variante, Median / p95 / Maximum in ms: vorher **4,249.69 / 4,285.95 / 4,289.98**, synchron optimiert **3,641.06 / 3,641.43 / 3,641.47**. Der frühere instrumentierte Audit ergab 5.872,68 → 5.020,77 ms Median; Instrumentierungs- und native Zeiten werden nicht gemischt.

Im ersten nativen Drei-Sekunden-Lauf: Flush-Tageswechsel 5.046,08 → 3.412,88 ms; eigentlicher Flush 4.637,72 → 2.994,53 ms. Das verbleibt ein mehrsekündiger Stall und rechtfertigt die weitere Writer-Prüfung. Alle 31 Tabellen der identischen Fixture sind im kontrollierten Vorher/Nachher-Vergleich exakt, inklusive Schema, Metadata und Aggregaten; keine Toleranz.

## 9. A–G-Klassifizierung und Persistenzpflicht

Klasse | Daten | Vertrag
--- | --- | ---
A / F | Alle `*_daily`, `news_events`, `event_log` | Vollständige Werte; Datumsreplacement statt blindem Append für Replay/Load. Bisherige Tagespuffer bleiben erlaubt.
B / F / G | Alle `*_current`, `news_current`, `event_current` | Vollständiges Replace einschließlich leerer Tabellen; aus Welt/Recorder rekonstruierbar, trotzdem unverändert persistiert.
C / F | `history_aggregate` | Monatliche/jährliche Buckets, alle Semantikfelder und Retention; nach Raw-Trim nicht beliebig rekonstruierbar.
D | `phase_metric_daily`, `phase_metric_current` | Weiterhin alle Zeilen/Spalten persistiert; Laufzeitmesswerte schwanken naturgemäß zwischen unabhängigen Läufen.
E / F | `history_metadata` | History-ID, Schema-/Modellversion und Compaction-Marker vollständig erhalten.
A / E / F | `structural_event` | Bestehende IDs und Event-Upserts unverändert; kein doppeltes Replay.
F | Spielstand / Checkpoint / RNG / Analytics-Manifest | Save wartet auf DuckDB-Commit und schreibt erst danach den bestehenden atomaren Spielstand.

G erlaubt hier keine ausgelassene Persistenz. Für einen automatischen Flush muss vor sichtbarer Veröffentlichung ein vollständiger dauerhafter Batch vorhanden sein. Bereits erlaubte Nicht-Flush-Tagespuffer erhalten dieselben bisherigen Grenzen.

## 10. Durability und Veröffentlichung

Gewählte Reihenfolge: Simulation → unveränderliche bereits materialisierte Zeilen → vollständiger Batch mit Länge, SHA-256, History-ID und Sequenz im fsync-geschützten Journal → Veröffentlichung → geordnete DuckDB-Transaktion → COMMIT → fsync-geschütztes Journal-ACK. Keine Veröffentlichung allein aufgrund einer RAM-Queue.

Die analytische DB darf kurz hinterherlaufen, weil vor dem bisherigen Flush-Veröffentlichungspunkt bereits ein vollständiger Replay-Batch dauerhaft vorliegt. DB-Leser sind Barrieren. Save bestätigt erst DuckDB-Commit plus den vorhandenen atomaren Checkpoint. Das Journal ersetzt keinen Welt-Checkpoint: ungespeicherte Weltfortschritte haben den bisherigen Save-Vertrag. Physischer Stromverlust wurde nicht emuliert; es gelten dieselben Betriebssystem-/Dateisystem-/Hardware-Fsync-Annahmen. Beschädigte Dateien führen zu einem sichtbaren Abbruch statt zu geratenen Daten.

## 11. Entscheidung zum Hintergrund-Writer

Ein einzelner Writer ist nach den synchronen Restkosten erforderlich und durch die nachstehenden Queue-, Save-, Crash-, Recovery- und Regressionsprüfungen unterstützt. Aktiv im Live-Worker nach abgeschlossener Initialisierung. Direkte/headless Runtime bleibt standardmäßig synchron; die Langzeitprüfungen aktivieren den Writer ausdrücklich. Transiente In-Memory-Stores aktivieren ihn nicht; vorhandene dauerhafte Journale dürfen dort nicht scheinbar recovered werden.

## 12. Verbindungseigentum

Genau ein nicht-daemonischer Owner-Thread öffnet und benutzt die aktive DuckDB-Verbindung. Initialisierung und Schemaarbeit sind vor der Übergabe beendet. Simulation und GUI besitzen keine parallele SQL-Verbindung. Alle späteren SQL-Leser und -Schreiber laufen als geordnete Calls auf demselben Owner; ein Ergebnis wird atomar materialisiert, bevor der nächste Auftrag es überschreiben könnte. Der SQL-Batch-Target hat ausschließlich eine Verbindung, keine Welt-, RNG-, Session- oder Current-Cache-Referenz.

## 13. Queue und Doppelbuffer

Zwei feste wiederverwendbare Journal-Slots, höchstens zwei ausstehende Datenbatches insgesamt einschließlich des aktiven Batches. Auftragsqueue maxsize=3; immutable Tupel enthalten nur str/int/float/None. Maximal 64 MiB kodierte Daten je Batch; damit höchstens 128 MiB plus zwei 4-KiB-Header auf Disk. Zu große Batches nehmen nach Drain den synchronen Weg mit denselben Transaktionen. Keine Vollweltkopie und keine unbeschränkte Queue. Die Datei wird vor Veröffentlichung vollständig geschrieben und fsynced; nach Commit wird der Header dauerhaft geleert, ohne von durable unlink abhängig zu sein.

## 14. Backpressure und Fehlerpolitik

Freie Slots werden nur nach COMMIT und dauerhaftem ACK zurückgegeben. Ein dritter Produzent wartet; die Ordnung bleibt erhalten. Fehler werden gelatcht, stoppen weitere Tageswechsel und SQL-Aufträge und erhalten das Journal zur Recovery. Kein stiller Retry über einen unklaren Commit hinweg. Ein Neustart replayt idempotent; beschädigte Header/Checksums, fehlende Slots oder falsche History-ID werden zurückgewiesen. Fsync-Fehler vor Veröffentlichung löschen keine Puffer. Writer-Fehler werden über ein gesondertes Protokollereignis auch während Pause sichtbar, ohne Antwort-IDs zu verschieben; die UI stoppt den Spieltakt.

## 15. Save-Vertrag und gemessene Kosten

Save wartet bei leerem, aktivem oder belegtem Writer auf alle Vorgänger und den vollständigen Save-Record. Erst danach wird der Checkpoint atomar geschrieben und Erfolg gemeldet. Die folgenden Zeiten enthalten auch die bestehende vollständige Save-Erzeugung und sind keine reinen Flush-Zeiten.

Variante / Zustand | n | Save Median / p95 / max ms | Shutdown Median / p95 / max ms
--- | ---: | ---: | ---:
Vorher synchron / idle | 3 | 38,933.49 / 43,132.65 / 43,599.22 | 1,127.29 / 1,173.82 / 1,178.99
Vorher synchron / active | 3 | 40,728.52 / 41,444.01 / 41,523.51 | 1,111.47 / 1,147.98 / 1,152.04
Vorher synchron / queued | 1 | 39,706.58 / 39,706.58 / 39,706.58 | 1,062.52 / 1,062.52 / 1,062.52
Nachher Writer / idle | 3 | 38,204.02 / 48,048.72 / 49,142.57 | 1,360.07 / 1,467.34 / 1,479.26
Nachher Writer / active | 3 | 43,850.79 / 43,993.02 / 44,008.82 | 1,151.53 / 1,195.15 / 1,200.00
Nachher Writer / queued | 1 | 39,872.82 / 39,872.82 / 39,872.82 | 1,817.20 / 1,817.20 / 1,817.20

Der synchrone Vorher-Code kennt keinen laufenden Hintergrund-Writer; active/queued bezeichnen dort denselben vorbereiteten noch ungeflushten Datenbestand. Nachher werden wirkliche SQL-Batches gestartet. Der tatsächliche Queued-Fall belegt nach gewöhnlichem Tagesfortschritt vor Save und Shutdown nachweislich beide Slots (n=1). Der erste Versuch mit vollständigem Record drainte den ersten Batch bereits vor Save und ist hierfür keine Ergebnisquelle. Keine künstliche Writer-Verzögerung in diesen Leistungsmessungen.

## 16. Load und Recovery

Load wartet vor Weltrestore und Analytics-Reset auf den Owner. Save lädt unmittelbar danach wieder exakt denselben Wirtschafts- und RNG-Zustand. Die Tests vergleichen außerdem den vollständigen kodierten Folgetag nach Load mit dem ununterbrochenen Folgetag. Startup prüft History-ID, Format, Länge und SHA-256, replayt nach Sequenz und ACKt erst nach erfolgreichem COMMIT. Nach einem bereits erfolgreichen, aber nicht ACKten Commit bleibt Replay idempotent.

## 17. Fehler- und Crash-Injection

Sechs Prozessabstürze mit Exit 91: vor BEGIN, während COPY, vor COMMIT, während nativem COMMIT, nach COMMIT vor ACK und nach ACK. Große Kopie: alle 31 Tabellen, 1.775.592 Zeilen, identische Schema-/Metadata-/Aggregatwerte und erneut leeres Journal nach Recovery. COPY/COMMIT werden beim großen Versuch durch Timer mitten in der nativen Ausführung unterbrochen.

Zusätzlich: Rollback bei BEGIN/COPY/COMMIT-Fehler, beschädigtes Journal, andere History-ID, persistenter Writer-Fehler, Fsync-Fehler ohne falsches ACK, fehlender Journal-Slot, unklare Commit-Bestätigung mit exakt idempotentem Retry, Startup-Replay-Fehler einschließlich zusätzlichem Close-Fehler, Übergrößenfallback und blockierter dritter Batch. Kleine Crash-Tests kontrollieren unmittelbar nach dem Absturz „ganze alte“ oder „ganze neue“ Transaktion. Wiederholtes Replay erzeugt keine Duplikate.

## 18. Shutdown

Shutdown ist eine geordnete Drain-Barriere. Der Live-Worker ACKt Shutdown erst nach seinem expliziten Flush; anschließend beendet und joint er den nicht-daemonischen Owner. Close-Fehler wecken wartende Aufrufer und werden nicht verschluckt. Die Busy-/Queued-Tests prüfen geschlossenen Thread, leeres Journal und wieder geöffnetes History-Manifest; Zeiten stehen in Punkt 15. Ein fehlgeschlagener Writer liefert keinen scheinbar erfolgreichen Shutdown.

## 19. Geänderte Dateien

- `src/kojakstreet/adapters/legacy_runtime.py`
- `src/kojakstreet/core/data_store.py`
- `src/kojakstreet/core/persistence_writer.py`
- `src/kojakstreet/live_process.py`
- `src/kojakstreet/live_worker.py`
- `src/kojakstreet/ui_qt/app.py`

`data_store`: sichere synchrone Konvertierung, Recovery, Writer-Übergabe und Barrieren. `persistence_writer`: Journal, Queue und alleiniger SQL-Owner. `legacy_runtime`: Health-/Load-Barrieren. `live_worker`/`live_process`: Aktivierung, geordnetes Protokoll und Fehlerweitergabe. `ui_qt/app`: Fehleranzeige über den bestehenden Timer. Neue Tests: `test_flush_remediation.py`, `test_persistence_writer.py`; `test_visible_state.py` ergänzt die neue Health-Schnittstelle im Testmodell und kontrolliert ihren Aufruf. Neue Auditwerkzeuge: `flush_remediation_*`, `flush_writer_probe.py`, `flush_writer_recovery.py`. Kein Commit, keine Schema-/Gameplayänderung. Der vollständige ausschließlich aktuelle Diff liegt in `current-pass-production.diff`.

## 20. Gewöhnlicher Tageswechsel

Warmer nativer Windows-Lauf, derselbe 365-Tage-Checkpoint, echte Drei-Sekunden-Anfragen, jeweils 37 / 37 gewöhnliche Tage: T0→T4 vorher **311.12 / 445.42 / 480.92**, nachher **298.11 / 376.53 / 409.49** ms. Maximale Heartbeat-Lücke je Tag vorher **54.59 / 73.84 / 91.61**, nachher **48.58 / 63.41 / 81.12** ms. Wirtschaftscode ist unverändert; unterschiedliche Systemzustände werden nicht als kausale Verbesserung des Simulationskerns verkauft.

## 21. Sichtbarer Flush-Tageswechsel

Warme native Reihe, n=1 / 1: vorher **4,116.80 / 4,116.80 / 4,116.80**, nachher **1,154.58 / 1,154.58 / 1,154.58** ms. Der erste unabhängige Vergleich ergab 5.046,08 ms vor, 3.412,88 ms synchron optimiert und 1.075,54 ms mit Writer. Einzelne reguläre Monatsflushes liefern keine belastbare Verteilungsabschätzung; deshalb zusätzlich zehn reale wiederholte Flushes in Punkt 28. Veröffentlichung ist jeweils erst nach dauerhaftem Journal-Handoff erlaubt; DB-Commit erfolgt anschließend.

## 22. Rohflush, Writer und Handoff

Rohflush vorher: **4,249.69 / 4,285.95 / 4,289.98** ms; synchron optimiert: **3,641.06 / 3,641.43 / 3,641.47** ms, n=3 je Variante. Großer isolierter Batch mit unveränderten Zeilen: Handoff einschließlich Freeze **704.64 / 781.06 / 789.55** ms; Handoff bis vollständig abgearbeitet **5,224.85 / 5,247.48 / 5,249.99** ms. Das ist reale zusätzliche Journalarbeit, keine verkürzte Datenbanktransaktion.

Native Writer-Dauern einschließlich Bootstrap/Monatsflush/Shutdown: **1,320.88 / 2,477.07 / 2,605.54** ms; reine Journal-Handoff-Zeiten **224.30 / 506.26 / 537.59** ms. `freeze_ms` und `queue_wait_ms` werden getrennt erfasst; das ältere Feld `backpressure_ms` enthält auch Freeze-Vorbereitung und darf nicht als reine Slotwartezeit gelesen werden.

## 23. SQL-Gruppen und Vorbereitung

Gruppe | Vorher Median / p95 / max ms | Synchron nachher Median / p95 / max ms
--- | ---: | ---:
BEGIN | 0.37 / 0.37 / 0.37 | 0.33 / 0.45 / 0.47
DELETE | 668.23 / 670.01 / 670.21 | 43.43 / 44.98 / 45.15
COPY | 595.31 / 605.01 / 606.08 | 618.97 / 623.61 / 624.12
INSERT | 879.04 / 884.65 / 885.27 | 813.76 / 815.32 / 815.50
SELECT | 9.01 / 9.13 / 9.14 | 9.27 / 10.30 / 10.41
COMMIT | 1,297.60 / 1,303.71 / 1,304.39 | 1,304.21 / 1,305.43 / 1,305.56
Python/Temp/Cleanup außerhalb SQL-API | 813.85 / 834.61 / 836.92 | 841.61 / 848.94 / 849.76
Beobachtete generische CSV-Zeit (Teil der Vorbereitung) | 550.71 / 573.71 / 576.26 | 564.84 / 574.40 / 575.46
Aggregation/Compaction (überlappt SQL-Gruppen) | 1,003.71 / 1,019.45 / 1,021.20 | 981.36 / 985.33 / 985.77

Die Zeiten sind API-Wallzeiten auf identischen isolierten Kopien, keine addierbaren unabhängigen Profilerphasen. Text-/Phasen-CSV benutzt einen eigenen Codec; dessen Zeit liegt in Python-Vorbereitung und nicht vollständig in der generischen CSV-Zeile. Temp-Dateien werden in finally entfernt. Aggregation wird nicht verzögert, ausgelassen oder als fremde Kategorie verborgen.

## 24. Durchsatz und Queue-Tiefe

20 Tage, zehn automatische Flushes, alle neun Ansichten. Tatsächlicher Abstand der T0-Anfragen: 3.096 s Median, 3.019–3.254 s. Die beobachtete Queue-Tiefe blieb maximal 1; Produktion kann höchstens zwei Batches belegen. Maximal gemessene reine Slotwartezeit: 0.022 ms. Writer-Zeiten: **671.17 / 1,019.54 / 1,078.33** ms. Es entsteht bei diesem geprüften Takt kein wachsender Rückstau. Die absichtlich langsamere Unit-Injection zeigt die definierte blockierende Backpressure und strikt gleiche Reihenfolge statt verlorener Daten.

## 25. RAM, RSS und Disk

Große Fixture: 8,849,620 Bytes lokale binäre Prüffixture, produktiver JSON-Batch 18,812,709 Bytes. RSS in MiB, Median / p95 / Maximum: vor Handoff **101.67 / 102.50 / 102.60**, nach Handoff **107.88 / 108.83 / 108.93**, nach Writer **171.17 / 172.75 / 172.92**. Die Zunahme umfasst DuckDB-Puffer und Zeilen, nicht nur den Batch. Peak zwischen Messpunkten wurde nicht bestimmt. Beide Journaldateien benötigen in diesem Versuch zusammen 18,820,901 Bytes; die feste maximale Diskgrenze ist 128 MiB plus Header.

Native Messungen enthalten Worker-RSS pro Tagesanfang/-ende. Das Spiel behält weiterhin seine bestehenden begrenzten Rechenhistorien; RowBatch enthält nur skalare Persistenzzeilen. Der separate Save-Messaufbau hält zur Reproduzierbarkeit einen Welt-Checkpoint im Auditwerkzeug; das ist kein produktiver Writer-Puffer und wird nicht als produktiver RAM-Wert verwendet.

## 26. Tests und statische Prüfung

Gesamte aktuelle Testsuite: **472 Tests**, zunächst zwei Fehlschläge, 1603.60 s. Das monatliche Zeitbudget scheiterte unter paralleler Last (73,13 statt höchstens 70 ms); alle drei Budgettests bestanden anschließend einzeln ohne diese Last. Das sichtbare Zustands-Testmodell benötigte die neue Health-Schnittstelle und prüft jetzt ihren Aufruf; alle zehn zugehörigen Tests bestanden. Damit sind alle 472 Tests abschließend validiert. Die ursprüngliche Suite und beide Retests bleiben getrennt als XML dokumentiert. Der bereits vor diesem Auftrag vorhandene Suite-Erfolg wird nicht dafür verwendet. Alle 31 neuen Flush-/Writer-Tests bestanden; sie prüfen Konvertierung, Transaktion, Eigentum, Crash, Backpressure und Save/Load. Neue Module/Werkzeuge/Tests bestehen Ruff; der bestehende Importordnungsbefund in data_store.py ist bereits in der eingefrorenen Referenz vorhanden.

## 27. Exakter Ein- und Zwei-Jahresvergleich

365 Tage mit den unveränderten nativen Thread-Einstellungen: jeder tägliche Welt-/RNG-Vergleich, vollständige Zwischen- und Abschlusscheckpoints, Tabellenwerte und Zeilenzahlen stimmen exakt. 730 Tage mit für beide Prüfseiten kontrollierten SQL-Threads=1: ebenfalls exakt, einschließlich aller Aggregate. Diese Einstellung dient ausschließlich der Prüfung; Produktion bleibt bei 24 Threads. 64 Spieler-Szenarien über vier Datumsgrenzen stimmen im vollständigen Zustand überein.

Bei unabhängigen Weltläufen werden ausschließlich zufällige History-UUID und gemessene duration_ms aus dem Vergleich entfernt; ihre übrigen Spalten/Zeilen bleiben geprüft. In identischen Fixture-/Recovery-Vergleichen gibt es keine solchen Ausnahmen, keine Rundung und keine Float-Toleranz.

**Vorbestandene Einschränkung:** Zwei unveränderte native 24-Thread-Flushes auf derselben großen Fixture unterscheiden sich bereits in den letzten Float-Bits jährlicher AVG-Werte; die anderen 30 Tabellen stimmen exakt. Die Audit-Analyse fand 1.081 von 227.674 Aggregatzeilen mit ausschließlich unterschiedlichen mean_value-Bits. Dies wird nicht durch Toleranzen verdeckt oder durch eine Produktionsänderung „repariert“. Für exakte Recovery-/Mehrjahresprüfung wurde deshalb die gleiche kontrollierte Ausführungsreihenfolge auf beiden Seiten eingesetzt. Eine allgemeine bitweise Wiederholbarkeit nativer paralleler Jahres-AVG wird nicht behauptet.

## 28. Wiederholte Flushes und sichtbare UI

Zehn Flush-Tageswechsel: T0→T4 **489.84 / 920.29 / 1,163.39** ms; alle 20 Tage **408.24 / 650.17 / 1,163.39** ms. Größte Heartbeat-Lücke je Tag: **49.53 / 85.89 / 98.57** ms. Alle Rows prüfen aktuelle Daten am Veröffentlichungspunkt, Qt-Main-Thread und sichtbare Ticker-Geometrie/Quotes. Reale Windows-UI zusätzlich: junge 20 Tage, alle neun jungen Ansichten 27 Tage, alle neun reifen Ansichten 27 Tage sowie 94 Navigationsfälle mit 35 versteckten Fortschrittstagen. Kein Writer-Fehler, sauberes Ende.

## 29. Save/Load-Gesamtergebnis

Sämtliche native Backend-Barriermessungen bestätigen unmittelbares exaktes Load nach Save. Native Navigation bestätigt Save/Load nach verstecktem Fortschritt. Unit-Prüfungen halten den aktiven Writer gezielt an, belegen beide Slots, verhindern vorzeitigen Save-Erfolg und vergleichen den nächsten vollständigen Welt-/RNG-Checkpoint. Recovery prüft identische History-ID und Metadata; kein halber DB-Zustand und keine verwaisten bestätigten Batches. Save-Zeiten sind vollständig in Punkt 15 ausgewiesen.

## 30. Verbleibende Kosten

DuckDB-COMMIT/Checkpoint, Aggregation, CSV/COPY und Journalkodierung bleiben echte Arbeit. Große Saves serialisieren weiterhin den vollständigen bestehenden Checkpoint und sind teuer. Explizite historische Abfragen, Save, Load und Shutdown sind geordnete Barrieren und können warten. In der Navigation brauchte die kalte Product-Detail-Abfrage 3.168,36 ms; das ist kein gewöhnlicher Flush-Tageswechsel und wird nicht als verschwundener Engpass ausgegeben. Übergrößen und ein langsamerer Datenträger können den ausdrücklich synchronen Rückfall bzw. Backpressure auslösen. Die getestete Hardware/Taktkombination garantiert keine beliebigen Produzentenraten.

## 31. Urteil und Nachweise

Der mehrsekündige automatische Flush-Stall im geprüften Gameplay-Pfad ist beseitigt. Das Ergebnis beruht auf synchroner Konvertierungsoptimierung und einem einzelnen geordneten Writer mit vorherigem dauerhaftem Journal-Handoff. Es wurden weder Daten ausgelassen noch Commit-Schutz, Retention oder Save-Erfolg abgeschwächt. Die bekannte native Jahres-AVG-Nichtwiederholbarkeit bleibt ausdrücklich dokumentiert; alle beschriebenen exakten Prüfungen benutzen keine Toleranzen.

Nachweise: `.cache/flush-remediation/{before-source-hashes,after-source-hashes,current-pass-production.diff,fixture,warm-raw-before,warm-raw-synchronous,candidate-staging,synchronous-controlled-exact,large-crash-recovery-final,final-exact-comparison,barriers-before-v2,barriers-final,barriers-queued-before,barriers-queued-final,full-final.xml,serial-budget-final.xml,visible-state-final.xml}` und `.cache/visible-ui-sync/flush-*`. Verworfene bzw. abgebrochene Messaufbauten sind keine Ergebnisquelle. Native Leistungsmessungen liefen seriell ohne gleichzeitig laufende Langzeitprüfungen. Die funktionale Suite und exakten Vergleiche liefen anschließend parallel; darin enthaltene Budgettests wurden abschließend allein wiederholt. Die tatsächlichen Queued-Barriermessungen liefen ebenfalls erst nach Ende aller Regressionsläufe.
