# Kojak Street: Performance-Audit des Tageswechsels

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Stand: 5. Oktober 2026. Messung auf dem lokalen Windows-Rechner. Untersucht wurde ausschließlich der Übergang zum nächsten Spieltag. Die absichtliche Wartezeit von 2.000 ms pro Spieltag ist ausgeschlossen. Es wurden keine Produktionsfunktionen optimiert, refaktoriert oder migriert.

Der bekannte Genesis-Workload umfasst **22.798.724 tatsächlich veränderte numerische Felder pro Spieljahr**, durchschnittlich etwa **1,9 Millionen pro Spielmonat** (`.cache/value-count-audit/result.json` (local evidence)). Jeder Wert wurde dabei höchstens einmal pro Tag gezählt. Zwischenrechnungen, unveränderte Neuberechnungen, History-Merges, Kopien und Funktionsaufrufe sind zusätzliches, in dieser Zahl nicht enthaltenes Arbeitsvolumen. Datenbank-Feldzellen oder Profiler-Aufrufe sind deshalb andere Größen und werden im Audit getrennt ausgewiesen.

Der normale Tageswechsel der vollständigen Anwendung liegt über das erste Spieljahr im Median bei **1.330,95 ms**, p95 **2.758,30 ms**. Ein normaler Tick ohne Oberfläche und ohne Datenbank-Flush benötigt **224,02 ms**. In der identischen, ein Jahr alten Vergleichswelt benötigt die Oberfläche ohne aktive Chart-Neuzeichnung **3.492,53 ms**, mit sichtbarem Detailchart **3.810,48 ms**.

Die Hauptbefunde sind die tägliche Verarbeitung der Historien aller Marktinstrumente im UI-Hauptthread und die periodischen DuckDB-Schreibläufe. Ein nativer Simulationskern würde diese Ursachen nur zu einem begrenzten Teil adressieren. Empfehlung: bestehenden Prozess-Worker behalten und zuerst die gemessenen History-/UI- und Persistenzpfade gezielt in Python beziehungsweise SQL verbessern. Ein vollständiger Rewrite ist aus diesen Messungen nicht begründbar.

**Zusätzlicher schwerer Befund im manuellen Step-/erzwungenen Snapshot-Pfad:** In der ein Jahr alten Welt wurden drei einzelne Schritte mit vollständigem Markets-Snapshot gemessen. Median **48.738,48 ms**; die drei Antworten enthalten rund 181–186 MB. Hier dominieren rekursives State-Encoding, JSON und State-Decoding sowie anschließendes History-Merge. Die normalen Timer-Ticks verwenden bereits den kleineren Status-/Current-Rows-Pfad; beide Bedienpfade werden im Bericht getrennt ausgewiesen.

## 1. Messumfang, Umgebung und Gültigkeit

| Merkmal | Messaufbau |
| --- | --- |
| Welt | Separate Genesis-Welt, Seed 1729, 1.280 Unternehmen, 20 Länder, 365 Kalendertage; Start 01.01.1990 |
| Portfolio | Genesis-Startvermögen, keine vom Audit hinzugefügten Trades oder offenen Spielerpositionen |
| Marktuniversum | 1.280 Aktien, 34 Rohstoffe, 90 verarbeitete Produkte, 32 Kryptowerte, 271 Fonds, 340 Indizes, 566 Derivate; 420 gerichtete FX-Paare |
| Bonds | Gesamtuniversum wächst; tägliche Auffrischung ist im Code auf bis zu 120 Instrumente begrenzt |
| Betriebssystem | Windows-11-10.0.26200-SP0 |
| Python | 3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)] |
| Bibliotheken | NumPy 2.5.1; DuckDB 1.5.5; PySide 6.11.1; pyqtgraph 0.14.0 |
| CPU | AMD Ryzen 9 3900 12-Core Processor; 24 logische CPUs |
| RAM | 15,90 GiB physisch |
| Git-Stand | 52b18024b9939c1fd57ff6e2e09acda3331813aa |
| Oberfläche | Echte Windows-Qt-Plattform, maximiertes Fenster; alle neun Ansichten einmal vor der Messung aufgebaut, Markets aktiv |
| Chartvergleich | 20 identische Tage ab Checkpoint 01.01.1991; keine aktive Neuzeichnung / Detail-Line ALL / Detail-Candle ALL / Preview-Line ALL |
| Jahresgrenze | 31.12.1990 bis 03.01.1991, fünf Wiederholungen desselben Ausgangszustands |
| Statistik | p95 linear interpoliert; Median und Mittelwert sind getrennt; ms sind reale Wandzeit |
| Profiler | Separate cProfile- und tracemalloc-Läufe; deren Zeiten werden nicht als unverfälschte Tick-Latenz verwendet |
| Isolation | Jeder Lauf besitzt eine eigene Datenbank und eigene Audit-Saves; keine gleichzeitig laufenden Benchmarks |

Alle GUI-Messreihen mit dem Suffix `-valid` prüfen zusätzlich, dass Trigger, Abschluss-Slot und UI-Aktualisierung dem Qt-Hauptthread zugeordnet sind. Ein früherer explorativer Messaufbau mit überschriebenem Slot hatte diese Zuordnung verändert und wurde vollständig aus den berichteten GUI-Ergebnissen ausgeschlossen. Der korrigierte Observer ist ein eigenes QObject mit explizit zugestelltem Queued-Slot; er ruft die unveränderte Produktionsfunktion auf. Dieser Messadapter verursacht einen zusätzlichen beobachteten Qt-Aufruf. Initialisierung, Datenbank-Klonen, Checkpoint-Laden, Aufbau der Ansichten und Screenshots liegen außerhalb T0→T4.

Eine zweite Messkorrektur betrifft ausschließlich den Adapter: zusätzliche Audit-Suchpfade verlängerten die wiederholten erfolglosen optionalen pandas-Imports. Nach Laden der Messmodule wird nun der Suchpfad des Produktions-Workers verwendet. Beide 365-Tage-Baselines und die dreifache Import-Diagnose wurden damit neu erhoben; der Bericht verwendet hierfür die Reihen mit `clean` im Namen. Frühere Jahresmessungen bleiben als Kontrollartefakte erhalten. Die Chart-/Reload-Vergleiche stammen aus der zuvor korrigierten Qt-Reihe und enthalten keine Flushs mit dem tausendfachen Parameter-/Importpfad; gelegentliche kleine Current-Reads bleiben separat erfasst. Profilerzeiten bleiben separate Diagnosewerte.

| Kontrollierter identischer Januar-Flush, n=1 je Pfad | Importversuche | pandas-Importzeit ms | gesamter Headless-Tick ms |
| --- | --- | --- | --- |
| legacy | 4260 | 3.335,76 | 9.226,05 |
| production | 4260 | 2.817,13 | 8.727,83 |

Diese kleine Gegenprobe belegt einen Messaufbau-Einfluss; sie ist kein Optimierungsbenchmark des Spiels. Zeiten alter und neuer Gesamtjahre werden wegen Laufzeit-/Rechnerlastschwankungen nicht voneinander subtrahiert, um eine vermeintlich erreichte Produktionsverbesserung zu behaupten.

| Messreihe / Tagtyp | n | Minimum ms | Median ms | Mean ms | p95 ms | Maximum ms |
| --- | --- | --- | --- | --- | --- | --- |
| 20-Tage-Kontrolle ohne Funktions-Observer | 20 | 150,45 | 170,89 | 179,68 | 218,14 | 274,98 |
| 20-Tage-Kontrolle mit Funktions-Observern | 20 | 150,50 | 176,39 | 190,32 | 230,21 | 296,70 |

Die Kontrollreihen zeigen die Größenordnung des Core-Messaufwands; getrennte Laufzeiten sind keine exakte isolierte Overhead-Messung jedes GUI-/IPC-Hooks. Die GUI-Observer und der 10-ms-Heartbeat kommen zusätzlich hinzu. Der Worker zählt Antwortbytes über eine zusätzliche UTF-8-Kodierung des vorhandenen JSON-Texts. Alle instrumentierten Baselines enthalten diesen Messaufwand; insbesondere die Speicherwerte sind deshalb keine behaupteten bytegenauen Produktions-Heapwerte.

Die Checkpoint-Vergleiche klonen den passenden analytischen Store einschließlich History-ID. Historische Datensätze nach dem jeweiligen Ausgangsdatum werden vor der Messung entfernt. Die ökonomischen Zustände und Zufallszustände stammen aus dem originalen Checkpoint; die Speicherpuffer werden über den bestehenden Restore-Pfad neu aufgebaut. Damit sind die Vergleichsvarianten untereinander gleich, jedoch keine bitgleiche Fortsetzung aller ursprünglichen flüchtigen Cache-/Flush-Zustände. Das erste Spieljahr wird zusätzlich durchgehend gemessen.

## 2. Exakter Kontrollfluss und T0/T1/T2/T3/T4

Der laufende Timer ruft [app.py](../src/kojakstreet/ui_qt/app.py) auf. `_request_simulation_steps(1, force_refresh=False)` sendet `simulation_requested` an einen persistenten QThread. Dessen `SimulationWorker.advance` ruft die Prozess-Proxy-API auf. Die eigentliche Welt und DuckDB befinden sich im separaten, persistenten `live_worker`-Prozess.

Der Worker rechnet `DailySimulation.step_day`, materialisiert die täglichen Store-Zeilen, führt gegebenenfalls den Flush aus und erzeugt eine Statusantwort plus geänderte aktuelle Tabellen. Die Antwort läuft als JSON-Zeile über stdout/stdin. Ein Reader-Thread im Elternprozess dekodiert JSON und legt das Ergebnis in eine Queue; der wartende Proxy-QThread übernimmt und vereinigt die aktuellen Tabellen. Anschließend liefert ein Queued-Slot den Abschluss an das Fenster. Der normale UI-Pfad plant `_apply_live_market_updates` für die nächste Event-Loop-Runde und aktualisiert die aktive Ansicht sowie den Ticker.

| Punkt | Genaue Messgrenze |
| --- | --- |
| T0 | Unmittelbar vor _request_simulation_steps; der vorherige absichtliche Timer-Abstand ist ausgeschlossen |
| T1 | DailySimulation.step_day ist beendet, einschließlich Portfolio, Policy und Datumsfortschritt; vor data_store.record_day |
| T2 | JSON dekodiert, Status und current_rows im Elternprozess durch LiveSimulationProcess._apply_result übernommen |
| T3 | Aktive UI-/Model-Aktualisierung beendet; beim erzwungenen Snapshot nach _refresh_active_view |
| T4 | Erster 10-ms-Heartbeat nach T3 und einem darauffolgenden Paint; kein laufender Simulations-, Live-Update-, History-Prefetch- oder erforderlicher Live-Chart-Timer mehr |

`T1−T0` umfasst die kleine Dispatch-/Worker-Anlaufzeit zusätzlich zur reinen Simulation. `simulation.core` misst nur `step_day`. `T2−T1` enthält Zeilenaufbereitung, möglichen Datenbank-Flush und Datenübergabe. `T4−T2` enthält Model-/State-Arbeit, sichtbare Chartarbeit, Paint und verbleibende Event-Loop-Wartezeit. Headless endet nach `advance_day`, also ohne Transfer/UI; dort entspricht die Summe im Wesentlichen Core plus Store-Aufbereitung. Persistenz bedeutet hier, dass der für diesen Tick vorgesehene Persistenzpfad fertig ist: an gewöhnlichen Tagen bleiben Fakten absichtlich im Puffer und sind noch nicht dauerhaft committed.

T4 ist ein operationaler Responsivitätsnachweis mit etwa einer Heartbeat-Periode Auflösung. Er misst Qt-Paint und wieder bearbeitete Events, nicht den tatsächlichen Monitor-/GPU-Present-Zeitpunkt und nicht die Reaktionszeit jeder denkbaren Benutzeraktion. Ein vorhandener, aber nicht aktiv aktualisierter Previewchart bleibt in der Variante „none“ sichtbar und statisch.

```mermaid
flowchart LR
T0["T0: GUI-Trigger"] --> Q["Proxy-QThread"] --> P["Simulationsprozess"] --> T1["T1: Core fertig"] --> D["Store / optionaler Flush"] --> J["JSON / Pipe / Decode / Merge"] --> T2["T2: State verfügbar"] --> U["GUI-Slot / aktive Models"] --> T3["T3: UI-Daten fertig"] --> C["sichtbarer Chart / Paint / Heartbeat"] --> T4["T4: responsiv"]
```

## 3. Vollständige Latenzstatistik je Tagtyp

| Messreihe / Tagtyp | n | Minimum ms | Median ms | Mean ms | p95 ms | Maximum ms |
| --- | --- | --- | --- | --- | --- | --- |
| Qt erstes Jahr: alle Tage | 365 | 377,46 | 1.360,22 | 1.596,25 | 2.791,56 | 9.605,27 |
| Qt erstes Jahr: normal, inklusive möglicher Flushs | 341 | 377,46 | 1.330,95 | 1.565,24 | 2.758,30 | 9.605,27 |
| Qt erstes Jahr: normal ohne Flush | 331 | 377,46 | 1.259,01 | 1.376,19 | 2.385,26 | 3.662,02 |
| Qt erstes Jahr: Reporting am 15. | 12 | 888,43 | 1.664,93 | 1.754,39 | 2.727,21 | 2.796,04 |
| Qt erstes Jahr: Monatsende, ohne 31.12. | 11 | 710,83 | 1.596,07 | 2.314,58 | 6.269,02 | 6.892,94 |
| Qt erstes Jahr: 31.12., Einzelbeobachtung | 1 | 2.373,14 | 2.373,14 | 2.373,14 | 2.373,14 | 2.373,14 |
| Qt erstes Jahr: periodischer Flush | 12 | 5.645,11 | 7.836,70 | 7.563,83 | 9.201,86 | 9.605,27 |

| Messreihe / Tagtyp | n | Minimum ms | Median ms | Mean ms | p95 ms | Maximum ms |
| --- | --- | --- | --- | --- | --- | --- |
| Headless erstes Jahr: normal inkl. Flush | 341 | 163,98 | 226,18 | 404,36 | 279,87 | 7.448,18 |
| Headless erstes Jahr: normal ohne Flush | 331 | 163,98 | 224,02 | 225,21 | 267,89 | 343,62 |
| Headless erstes Jahr: Reporting | 12 | 251,00 | 341,14 | 339,16 | 389,95 | 403,85 |
| Headless erstes Jahr: Monatsende | 11 | 187,58 | 228,68 | 1.131,81 | 5.207,47 | 5.699,30 |
| Headless erstes Jahr: 31.12., Einzelbeobachtung | 1 | 244,18 | 244,18 | 244,18 | 244,18 | 244,18 |
| Headless erstes Jahr: Flush | 12 | 4.715,64 | 6.060,21 | 6.146,49 | 7.200,85 | 7.448,18 |

Normale Tage enthalten in der ersten Tabelle bewusst auch diejenigen normalen Kalendertage, an denen ein Pufferflush fällig ist. Die zusätzliche Zeile „normal ohne Flush“ trennt diesen unabhängigen Auslöser. Das Monatsende umfasst elf Tage; der 31.12. wird getrennt behandelt. Die Einzelbeobachtung des 31.12. begründet keine allgemeine Jahreswechsel-Aussage; dafür folgt die Wiederholungsmessung.

| Messreihe / Tagtyp | n | Minimum ms | Median ms | Mean ms | p95 ms | Maximum ms |
| --- | --- | --- | --- | --- | --- | --- |
| Identische reife Welt: Headless | 20 | 167,59 | 176,58 | 183,25 | 243,88 | 256,02 |
| Identische reife Welt: Qt ohne aktive Chart-Neuzeichnung | 20 | 3.207,30 | 3.495,58 | 3.506,81 | 3.769,90 | 4.144,63 |
| Identische reife Welt: Qt Detail-Line ALL | 20 | 3.371,88 | 3.862,91 | 3.945,93 | 4.686,30 | 5.141,05 |
| Identische reife Welt: Qt Detail-Candle ALL | 20 | 3.976,11 | 4.144,00 | 4.188,78 | 4.485,86 | 4.492,08 |
| Identische reife Welt: Qt Preview-Line ALL | 20 | 3.983,46 | 4.140,33 | 4.206,19 | 4.572,69 | 4.584,88 |
| Identische reife Welt: Qt Detail-Line ALL + EMA 20/50/200 | 20 | 3.926,01 | 4.143,17 | 4.172,32 | 4.412,09 | 4.571,04 |

| Messreihe / Tagtyp | n | Minimum ms | Median ms | Mean ms | p95 ms | Maximum ms |
| --- | --- | --- | --- | --- | --- | --- |
| Jahresgrenze: 31.12. | 5 | 4.279,73 | 6.789,38 | 6.317,14 | 6.948,31 | 6.972,00 |
| Jahresgrenze: 01.01. | 5 | 3.973,53 | 4.288,53 | 4.212,15 | 4.316,20 | 4.318,12 |
| Jahresgrenze: 03.01., jährlicher Bond-Pfad | 5 | 3.956,02 | 4.089,33 | 4.088,65 | 4.210,82 | 4.218,99 |

Die fünf Jahresgrenzen-Wiederholungen laden jeweils denselben Checkpoint; damit wird die Kalendergrenze von wachsender Welt-/History-Größe getrennt. n=5 ist eine kleine Stichprobe: der p95 beschreibt diese Messungen und ist kein belastbarer Extremwert einer langen Spielsitzung. Jährliche Bond-Emissionen können im aktuellen Code erst nach dem 02.01. ausgelöst werden; der 31.12. allein würde diesen Pfad übersehen.

## 4. End-to-End-Zerlegung

| Variante | Grenze | Median ms | p95 ms |
| --- | --- | --- | --- |
| erstes Jahr, normal ohne Flush | T1−T0 Simulation + Dispatch | 229,73 | 258,37 |
| erstes Jahr, normal ohne Flush | T2−T1 Daten/Persistenz/Transfer | 115,73 | 394,43 |
| erstes Jahr, normal ohne Flush | T4−T2 UI gesamt | 907,72 | 1.863,08 |
| erstes Jahr, normal ohne Flush | davon T3−T2 UI-/Model-Aufbereitung | 873,28 | 1.825,43 |
| erstes Jahr, normal ohne Flush | davon T4−T3 Chart/Paint/Event-Wartezeit | 20,71 | 74,08 |
| erstes Jahr, normal ohne Flush | T4−T1 Core fertig → responsiv | 1.044,49 | 2.137,75 |
| reife Welt ohne Chart | T1−T0 Simulation + Dispatch | 223,48 | 282,87 |
| reife Welt ohne Chart | T2−T1 Daten/Persistenz/Transfer | 112,24 | 172,23 |
| reife Welt ohne Chart | T4−T2 UI gesamt | 3.117,92 | 3.353,17 |
| reife Welt ohne Chart | davon T3−T2 UI-/Model-Aufbereitung | 3.083,49 | 3.298,33 |
| reife Welt ohne Chart | davon T4−T3 Chart/Paint/Event-Wartezeit | 55,49 | 76,10 |
| reife Welt ohne Chart | T4−T1 Core fertig → responsiv | 3.229,65 | 3.465,07 |
| reife Welt Detailchart | T1−T0 Simulation + Dispatch | 251,59 | 332,32 |
| reife Welt Detailchart | T2−T1 Daten/Persistenz/Transfer | 147,88 | 216,14 |
| reife Welt Detailchart | T4−T2 UI gesamt | 3.476,45 | 4.054,92 |
| reife Welt Detailchart | davon T3−T2 UI-/Model-Aufbereitung | 3.391,05 | 3.991,52 |
| reife Welt Detailchart | davon T4−T3 Chart/Paint/Event-Wartezeit | 75,82 | 136,72 |
| reife Welt Detailchart | T4−T1 Core fertig → responsiv | 3.595,99 | 4.282,98 |
| erstes Jahr, Flush | T1−T0 Simulation + Dispatch | 226,73 | 253,57 |
| erstes Jahr, Flush | T2−T1 Daten/Persistenz/Transfer | 6.235,83 | 7.184,30 |
| erstes Jahr, Flush | T4−T2 UI gesamt | 1.104,74 | 1.909,64 |
| erstes Jahr, Flush | davon T3−T2 UI-/Model-Aufbereitung | 1.071,05 | 1.885,94 |
| erstes Jahr, Flush | davon T4−T3 Chart/Paint/Event-Wartezeit | 19,92 | 48,21 |
| erstes Jahr, Flush | T4−T1 Core fertig → responsiv | 7.617,64 | 8.971,26 |

Nur die drei Zeitgrenzen T1−T0, T2−T1 und T4−T2 sind disjunkt und summieren sich pro Tick exakt zu T4−T0. Mediane verschiedener Größen müssen sich nicht zum Median des Gesamtticks addieren. Die folgenden Funktions-/Subsystemzeiten sind zum Teil ineinander verschachtelt; beispielsweise enthält Production bereits Trade und Companies, und UI gesamt enthält History und Models. Sie dürfen nicht einfach aufsummiert werden.

| Subsystem | Median ms | p95 ms | % Transition¹ | Kategorie | Native-Core-Potenzial |
| --- | --- | --- | --- | --- | --- |
| Simulationskern gesamt | 222,63 | 276,93 | 6,49 % | A/C | Obergrenze; auch nicht numerische Logik enthalten |
| Globale Makroökonomie / Regime | 2,67 | 3,16 | 0,08 % | A | klein |
| Production / Supply Chain gesamt | 87,62 | 98,59 | 2,43 % | A/C | isolierter numerischer PoC |
| Internationaler Handel / Länderflüsse | 43,57 | 53,84 | 1,27 % | A/C | geeigneter PoC |
| Unternehmenskapazitäten | 5,13 | 7,91 | 0,16 % | A | begrenzter kleiner Anteil |
| Unternehmensauslastung / IO-Historien | 22,18 | 26,16 | 0,60 % | A/I | teilweise |
| Aktienkurse / Fundamentals / Erwartungen | 72,74 | 86,07 | 2,14 % | A/C | geeigneter Batch-PoC |
| Fonds | 17,61 | 28,07 | 0,59 % | A/C | möglich, geringe Gesamtwirkung |
| Indizes | 3,82 | 4,76 | 0,11 % | A | klein |
| Anleihemarkt | 4,71 | 12,17 | 0,15 % | A | klein |
| Derivate | 28,26 | 35,03 | 0,78 % | A | klein |
| FX-Paare | 0,59 | 0,70 | 0,02 % | A | sehr klein; Stärken separat im Rohlog |
| Rohstoffpreise | 2,23 | 2,47 | 0,06 % | A | klein |
| Kryptopreise | 2,24 | 2,65 | 0,06 % | A | klein |
| Marktpsychologie explizite Phase | 0,07 | 0,16 | 0,00 % | A | sehr klein; Erwartungen außerdem im Aktienpfad |
| Portfolio-Anleihen | 0,01 | 0,01 | 0,00 % | A | Genesis-Portfolio kaum Arbeit |
| Store-Zeilen/Puffer gesamt | 19,72 | 24,09 | 0,57 % | A/I | kein Core-PoC |
| DuckDB-API an gewöhnlichen Tagen | 0,00 | 0,17 | 0,00 % | D | bereits nativ; im Pufferpfad praktisch null |
| Worker-Antwortaufbereitung | 10,82 | 15,21 | 0,31 % | I/A | kein numerischer Core-PoC |
| Worker JSON-Encode | 26,70 | 31,74 | 0,75 % | I | anderer Übergabepfad, nicht Core |
| Worker Pipe-Write | 14,06 | 68,48 | 0,82 % | H/I | nicht Core |
| Elternprozess JSON-Decode | 13,35 | 17,65 | 0,43 % | I | nicht Core |
| Proxy State-/Row-Merge | 5,54 | 6,75 | 0,16 % | I/A | nicht Core |
| UI: Historien aller Instrumente | 3.025,07 | 3.242,49 | 86,80 % | C/A/I | zuerst Algorithmus ändern |
| UI: Quote-Model-Aufbereitung | 10,24 | 13,42 | 0,31 % | F/A | kleinerer Anteil |
| UI: sichtbare Row-Signale | 0,49 | 0,59 | 0,01 % | F | kein primärer Core-Kandidat |
| UI: aktive Ansicht gesamt | 3.042,37 | 3.257,25 | 87,24 % | F/C/I | keine Simulationskern-Migration |
| Detail: Chart-Datenaufbereitung | 3,84 | 4,45 | 0,10 % | G/I/A | klein; Detailvariante |
| Detail: Zeichnungsaufbau | 4,34 | 5,55 | 0,11 % | G/F | kein Simulationskern-PoC |
| Detail: pyqtgraph Paint | 35,85 | 77,42 | 1,07 % | G/F | bereits Qt-nativ; Detailvariante |
| Flush: Store gesamt | 6.121,24 | 7.075,41 | 81,24 % | D/H/I | kein Simulationskern-PoC |
| Flush: DuckDB-API inkl. Binding | 5.175,94 | 6.118,67 | 69,02 % | D/H | bereits nativ; Batch-/SQL-Pfad untersuchen |

¹ Anteil = Summe der jeweiligen Funktionszeit / Summe der T0→T4-Zeiten innerhalb genau dieser Stichprobe. Die Werte sind nicht aus einem Quotienten separat ermittelter Mediane berechnet. Vergleichsbasis ist die reife Welt ohne Chart, außer ausdrücklich als Detail-/Flush-Variante bezeichnet.

Zusätzliche Monatsbericht-Phasen:

| Reporting-Subsystem | Median ms | p95 ms | % Reporting-Transition | Kategorie | Native-Potenzial |
| --- | --- | --- | --- | --- | --- |
| Länder/Makro/Erwartungen | 3,11 | 3,88 | 0,19 % | A/C | erst nach Detailprofil bewerten |
| Unternehmens-Fundamentals | 71,07 | 78,79 | 4,07 % | A/C | erst nach Detailprofil bewerten |
| Unternehmens-Lifecycle | 7,55 | 9,13 | 0,43 % | A/C | erst nach Detailprofil bewerten |
| monatliche Rohstoffdaten | 0,61 | 0,88 | 0,04 % | A/C | erst nach Detailprofil bewerten |
| Production einschließlich verarbeiteter Produkte/Handel | 108,57 | 118,95 | 6,18 % | A/C | erst nach Detailprofil bewerten |
| monatliche Kryptodaten | 1,04 | 1,32 | 0,06 % | A/C | erst nach Detailprofil bewerten |
| Crypto-Lifecycle | 0,06 | 0,07 | 0,00 % | A/C | erst nach Detailprofil bewerten |

Verarbeitete Produkte werden innerhalb der Produktions-/Supply-Chain-Logik berechnet und besitzen keinen separaten täglichen Aktienpreis-Timer. Erwartungen sind über Makro, Bewertung und Kursformeln verteilt. Diese Anteile werden deshalb den gemessenen übergeordneten Phasen zugeordnet und nicht als zusätzliche künstliche Summanden ausgegeben. Portfolio, Kredit-/Zins-, Settlement- und Roll-Phasen sind in den vollständigen Phasenlogs enthalten; das positionsarme Genesis-Portfolio begrenzt die Aussage für sehr große Spielerportfolios.

## 5. Worker, GIL und tatsächlich genutzte CPU

| Messreihe, normal ohne Flush | Worker: CPU/Wandzeit | Eltern + Worker CPU / T0→T4 | Worker-Hilfsthreads CPU ms |
| --- | --- | --- | --- |
| headless-year-clean | 0,97 | — | 0,00 |
| headless-mature | 0,99 | — | 0,00 |
| qt-year-clean-valid | 0,96 | 1,08 | 0,00 |
| qt-mature-none-valid | 0,92 | 1,05 | 0,00 |
| qt-mature-detail-valid | 0,91 | 1,07 | 0,00 |

CPU/Wandzeit ist eine gemessene Anzahl effektiver Kernäquivalente über das betreffende Intervall, keine Zuordnung zu konkreten physischen Kernen. Werte nahe 1 bedeuten überwiegend serielle CPU-Arbeit; ein Wert größer als 1 kann native Hilfsthreads anzeigen. Während des Simulationskerns dominieren Python-Schleifen und Objektzugriffe. Die separate Prozessarchitektur trennt den Worker-GIL vom UI-GIL bereits. Ein Wechsel von QThread zu einem weiteren Prozess würde deshalb das grundlegende Problem nicht lösen: der QThread ist hier der Kommunikationsproxy, die Simulation läuft schon außerhalb des GUI-Prozesses.

Der JSON-Reader, der Proxy-QThread und UI-Python teilen den GIL im Elternprozess. Ein gemeinsamer Request-Lock serialisiert Simulation, Save/Load und Hintergrund-History-Abfragen. Die normalen Messreihen warten vor dem Trigger auf ausstehende initiale History-Anfragen; konkurrierende Benutzeraktionen werden nicht synthetisch erzeugt. Gemessene Dispatch-, Pipe-, Decode- und Merge-Zeiten quantifizieren den üblichen Übergabepfad, aber nicht jede denkbare Lock-Kollision. Pro-Core-Sampling beziehungsweise ein nativer Stack-Sampler stand in dieser Sitzung nicht zur Verfügung. Die Zustellung an den Receiver-Thread über Queued-Slots ist in der [Qt-for-Python-Dokumentation](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html) beschrieben und im Messaufbau zusätzlich tatsächlich geprüft.

Die GIL-Einordnung stützt sich außerdem auf die [Python-3.12-Threading-Dokumentation](https://docs.python.org/3.12/library/threading.html). NumPy kann bei vielen nativen Operationen den GIL freigeben; daraus folgt ohne eine tatsächlich benutzte numerische Operation noch keine Parallelität in diesem Tick ([NumPy Thread Safety](https://numpy.org/doc/2.1/reference/thread_safety.html)).

## 6. DuckDB: Puffer, API, Batches, SQL und I/O

| API-Kommandotyp pro Flush | Aufrufe gesamt / Flushs | Median ms | p95 ms |
| --- | --- | --- | --- |
| BEGIN | 12 / 12 | 0,45 | 0,61 |
| COMMIT | 12 / 12 | 834,72 | 1.659,40 |
| COPY | 264 / 12 | 774,06 | 827,16 |
| DELETE | 537 / 12 | 369,57 | 381,99 |
| INSERT | 405 / 12 | 3.235,10 | 3.406,84 |
| SELECT | 38 / 12 | 5,45 | 7,96 |

| Tabelle | Median Batch-Zeilen / Flush | Median Feldzellen / Flush |
| --- | --- | --- |
| asset_current | 2523 | 30276 |
| asset_daily | 75690 | 908280 |
| bond_current | 1406 | 23902 |
| bond_daily | 3611 | 61395 |
| company_current | 1280 | 19200 |
| company_daily | 1280 | 19200 |
| company_output_current | 13066 | 78396 |
| company_output_daily | 13066 | 78396 |
| country_current | 20 | 420 |
| country_daily | 20 | 420 |
| country_trade_current | 2480 | 24800 |
| country_trade_daily | 2480 | 24800 |
| event_current | 0 | 0 |
| event_log | 4 | 24 |
| forex_current | 420 | 2100 |
| forex_daily | 12600 | 63000 |
| fund_allocation_current | 2357 | 11787 |
| fund_allocation_daily | 2357 | 11787 |
| global_macro_current | 22 | 66 |
| global_macro_daily | 660 | 1980 |
| news_current | 0 | 0 |
| news_events | 4 | 12 |
| phase_metric_current | 15 | 45 |
| phase_metric_daily | 460 | 1380 |
| portfolio_current | 1 | 5 |
| portfolio_daily | 30 | 150 |
| product_current | 124 | 1364 |
| product_daily | 3720 | 40920 |

Normale Tage puffern Facts und aktualisieren Python-Current-Rows. Im Headless-Normalpfad ohne Flush werden keine DuckDB-Statements ausgeführt. Der vollständige Worker-/Antwortpfad führt in den 331 normalen Tagen ohne Flush insgesamt **56 kleine SELECTs** aus `news_current`/`event_current` aus; diese gelegentlichen Current-Reads erklären die kleinen API-Ausreißer im sonst gepufferten Pfad. Im Runtime ist ein Flush nach 30 unterschiedlichen Datumswerten eingestellt. Die erste Jahresreihe enthält 12 gemessene Flushs. SQL-API-Median pro Flush: **5.175,94 ms**. Materialisierung durch `fetchone/fetchall`: **0,05 ms**. Gemessenes temporäres CSV-Volumen pro Flush: Median **16,99 MB**, p95 **17,10 MB** (dezimal).

Als Näherung für den Python-/Datei-Anteil innerhalb `_insert_rows` ergibt die Differenz zur dort aufgerufenen COPY-/INSERT-API im Median **884,29 ms**. Dieser Rest umfasst CSV-Erzeugung, temporäre Dateien, Cleanup und Wrapper; er ist keine präzise Messung des internen DuckDB-Konverters. Die DuckDB-API-Zeit wiederum umfasst Binding, Engine und Warten auf I/O. Ohne einen nativen Engine-/I/O-Trace lassen sich diese Anteile innerhalb eines API-Aufrufs nicht vollständig trennen.

| Teuerste normalisierte Statements / Flush | Median ms | p95 ms |
| --- | --- | --- |
| `INSERT INTO phase_metric_daily VALUES (?, ?, ?)` | 2.341,54 | 2.481,43 |
| `COMMIT` | 834,72 | 1.659,40 |
| `COPY asset_daily FROM '<temporary.csv>' (FORMAT CSV, HEADER FALSE, DELIM ',', QUOTE '"', ESCAPE '"', NULL '\N')` | 183,61 | 209,75 |
| `INSERT INTO phase_metric_current VALUES (?, ?, ?)` | 73,10 | 83,02 |
| `COPY bond_daily FROM '<temporary.csv>' (FORMAT CSV, HEADER FALSE, DELIM ',', QUOTE '"', ESCAPE '"', NULL '\N')` | 50,67 | 56,07 |
| `COPY company_output_current FROM '<temporary.csv>' (FORMAT CSV, HEADER FALSE, DELIM ',', QUOTE '"', ESCAPE '"', NULL '\N')` | 48,94 | 51,35 |
| ` INSERT INTO history_aggregate SELECT ?, CAST(asset_type / / ':' / / ticker AS VARCHAR) AS entity, ?, ?, ?, date_trunc('month', date)::DATE AS bucket_start, last_day(date) AS bucket_end, arg_min(price, date), max(price), min(price), arg_max` | 46,83 | 56,31 |
| `COPY forex_daily FROM '<temporary.csv>' (FORMAT CSV, HEADER FALSE, DELIM ',', QUOTE '"', ESCAPE '"', NULL '\N')` | 46,40 | 49,36 |
| `DELETE FROM asset_daily WHERE date IN (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)` | 46,18 | 50,55 |
| `COPY company_output_daily FROM '<temporary.csv>' (FORMAT CSV, HEADER FALSE, DELIM ',', QUOTE '"', ESCAPE '"', NULL '\N')` | 45,93 | 53,10 |
| `DELETE FROM forex_daily WHERE date IN (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)` | 43,40 | 51,43 |
| `COPY product_daily FROM '<temporary.csv>' (FORMAT CSV, HEADER FALSE, DELIM ',', QUOTE '"', ESCAPE '"', NULL '\N')` | 43,14 | 48,23 |

Der Flush verwendet eine Transaktion mit BEGIN/COMMIT; aktuelle Tabellen werden über DELETE plus Batch-Einfügen ersetzt, History-Aggregate werden innerhalb desselben Persistenzpfads aktualisiert. Die großen Facts gehen überwiegend als CSV/COPY hinein. News-, Event- und **Phase-Metric-Tabellen** gehen über `executemany`; gerade diese kleinen Telemetrie-Insert-Batches sind in den Messungen überraschend teuer. Der langsame Tick lässt sich deshalb nicht allein mit der Zahl wirtschaftlicher Werte erklären. Repetitive Statements und exakte Batchgrößen sind im Rohlog erhalten; dies ist keine Behauptung, dass DuckDB generell langsam sei.

Zusätzliche **unprofilierte** Import-Diagnose: drei gleiche reife Ausgangszustände, 29 reguläre Tage Vorbereitung, anschließend der bestehende Januar-Flush. Ein Observer um die vorhandene Python-Importfunktion erfasst Module, Fehlversuche und Zeit; es wird kein Modul installiert und kein SQL geändert. Dieser Flush kann außerdem die erstmals fällige jährliche History-Compaction enthalten und ist deshalb eine gesonderte Stichprobe gegenüber den zwölf Flushs des ersten Jahres.

| Modul | Median Importversuche / Flush | Median fehlgeschlagen | Median Importzeit ms | p95 ms |
| --- | --- | --- | --- | --- |
| pandas | 4260 | 4260 | 2.350,02 | 2.638,66 |

| SQL-Kontext der Importversuche | Versuche über drei Diagnosen |
| --- | --- |
| INSERT INTO phase_metric_daily VALUES (?, ?, ?) | 8280 |
| INSERT INTO history_aggregate SELECT ?, CAST(region AS VARCHAR) AS entity, ?, ?, ?, date_trunc('month', da | 432 |
| INSERT INTO history_aggregate SELECT ?, CAST(region AS VARCHAR) AS entity, ?, ?, ?, make_date(year(date), | 432 |
| INSERT INTO phase_metric_current VALUES (?, ?, ?) | 270 |
| INSERT INTO history_aggregate SELECT ?, CAST(region \|\| ':' \|\| code AS VARCHAR) AS entity, ?, ?, ?, make_da | 252 |
| INSERT INTO history_aggregate SELECT ?, CAST(code AS VARCHAR) AS entity, ?, ?, ?, date_trunc('month', date | 216 |
| INSERT INTO history_aggregate SELECT ?, CAST(code AS VARCHAR) AS entity, ?, ?, ?, make_date(year(date), 1, | 216 |
| DELETE FROM product_daily WHERE date IN (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) | 180 |

Damit ist ein erheblicher Teil der gemessenen DuckDB-API-Latenz konkret **Python-/Import-/Dateisuch-Aufwand innerhalb des Bindings**. Fehlgeschlagene optionale pandas-Imports dürfen nicht als reine native SQL-Rechenzeit ausgegeben werden. Ein späterer isolierter Test sollte den Parameter-/Batch-Pfad und diese wiederholten Importversuche prüfen. Aus dem Audit folgt noch keine gemessene Beschleunigung durch eine Installation, ein Upgrade oder eine alternative Übergabeform; solche Änderungen wurden nicht durchgeführt.

Einordnung: **A — relevante DuckDB-/Commit-/I/O-Zeit an Flush-Tagen; B — zusätzlicher relevanter Python-/CSV-/Materialisierungsaufwand; C — praktisch keine DuckDB-API-Latenz an gewöhnlichen gepufferten Tagen.** Den größten gemessenen SQL-/Batch-Aufrufen muss eine spätere Optimierung zuerst gelten. Die Python-DuckDB-API und ihre Thread-Anbindung sind in der [offiziellen Python-Dokumentation](https://duckdb.org/docs/stable/clients/python/overview) beschrieben.

## 7. NumPy und native Arbeit im Simulationskern

Der Core-Profiler der reifen Welt enthält 0,00 NumPy-Aufrufe pro Tick in den erfassten NumPy-Funktionszeilen. Native mathematische/random-C-Aufrufe besitzen zusammen 1,86 ms profilerbehaftete Self-Zeit pro Tick. Diese Zahl ist kein nativer CPU-Sample-Trace: sie bezeichnet nur die vom Python-Profiler sichtbaren C-Aufrufgrenzen und enthält weder eine komplette Engine-Aufschlüsselung noch jeden in CPython implementierten Objektzugriff.

Der aktuelle Daily-Pfad benutzt cached Index-/Momentum-Zustände und Python-Schleifen. Die vorhandene `np.mean`-Hilfsfunktion ist deshalb kein Beleg für einen bereits vektorisierten ganzen Simulationskern. Native Dictionary-/Listen-/Sortieroperationen sind zwar C-Code innerhalb CPython, bleiben aber Objekt-/Algorithmusaufwand der Kategorien A/C und sind kein zusammenhängender NumPy-Kernel. DuckDB liegt zeitlich außerhalb T1; es erhöht den nativen Anteil des Core-Pfads daher nicht.

Gut abgrenzbar wären numerische Länder-/Güter-Matrizen und Aktienpreisformeln auf vorbereiteten Spaltenarrays. Schwieriger sind die bestehende Dictionary-Topologie, lifecycle-abhängige Zustandsänderungen, heterogene Produkte und die Reihenfolge gekoppelter Updates. Eine Vektorisierung würde denselben Aufwand für Array-Aufbereitung, Rückschreiben und deterministische Zufallswerte gegen die Einsparung im numerischen Kernel messen müssen.

## 8. UI, sichtbare und unsichtbare Charts, Signale und Responsivität

| Variante | Ticks | sichtbare Plot-Aufrufe | unsichtbare Plot-Aufrufe | beobachtete Paint-Events | Median größter Tick-Heartbeat-Abstand ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| qt-year-clean-valid | 365 | 0 | 0 | 19436 | 912,21 | 1.897,65 |
| qt-mature-none-valid | 20 | 0 | 0 | 855 | 3.078,26 | 3.332,05 |
| qt-mature-detail-valid | 20 | 20 | 0 | 1692 | 3.399,63 | 3.913,13 |
| qt-mature-candle-valid | 20 | 20 | 0 | 1474 | 3.627,39 | 3.743,59 |
| qt-mature-preview-valid | 20 | 40 | 0 | 1950 | 3.593,36 | 3.951,86 |
| qt-mature-heavy-valid | 20 | 20 | 0 | 1819 | 3.598,83 | 3.722,89 |

| Variante | beobachtetes Model-Signal | Gesamt | pro Tick |
| --- | --- | --- | --- |
| qt-year-clean-valid | proxy_model.dataChanged | 2920 | 8,00 |
| qt-year-clean-valid | model.dataChanged | 2920 | 8,00 |
| qt-mature-none-valid | proxy_model.dataChanged | 160 | 8,00 |
| qt-mature-none-valid | model.dataChanged | 160 | 8,00 |
| qt-mature-detail-valid | proxy_model.dataChanged | 160 | 8,00 |
| qt-mature-detail-valid | model.dataChanged | 160 | 8,00 |
| qt-mature-candle-valid | proxy_model.dataChanged | 160 | 8,00 |
| qt-mature-candle-valid | model.dataChanged | 160 | 8,00 |
| qt-mature-preview-valid | proxy_model.dataChanged | 160 | 8,00 |
| qt-mature-preview-valid | model.dataChanged | 160 | 8,00 |
| qt-mature-heavy-valid | proxy_model.dataChanged | 160 | 8,00 |
| qt-mature-heavy-valid | model.dataChanged | 160 | 8,00 |

Die Messung zählt die vier angeschlossenen Signaltypen dataChanged, modelReset, rowsInserted und layoutChanged für Source- und Proxy-Marktmodell; außerdem MetaCall-/Timer-/Paint-Events. Ein Source-Signal und seine Proxy-Weiterleitung sind zwei beobachtete Signale, keine zwei unabhängigen Preisberechnungen. Dies ist keine globale Zählung aller internen Qt-Signale. Die aktive Tabellenansicht enthält 2.523 Source-Zeilen und initial 160 geladene Proxy-Zeilen; die lazy geladenen Zeilen sind kein Beleg für ein fehlendes Marktuniversum.

Die normalen Quote-Updates setzen die Marktmodelle nicht vollständig zurück. Die expliziten Preis-Signale sind auf die sichtbaren Zeilen begrenzt. Die bereits aufgebauten, inaktiven Ansichten bleiben im gemessenen Markets-Tick weitgehend ohne Refresh-/Plot-Aufrufe. Die Messung der Zeichenmethoden `plot_line`, `plot_lines`, `plot_candles` und `plot_long_short_heatmap` unterscheidet ausdrücklich `isVisible()`; zusätzliche Qt-Paints stehen separat. Damit ist die Aussage über unsichtbare Charts auf die erfassten Chartmethoden und die getesteten Ansichten begrenzt.

Trotzdem ruft [markets_view.py](../src/kojakstreet/ui_qt/views/markets_view.py) `_append_live_history` für alle eingehenden Marktquotes auf. Für jedes Instrument werden alle lokalen History-Punkte nach Datum identifiziert, in ein neues Dictionary gelegt, sortiert und wieder in eine Liste übernommen ([chart_series.py](../src/kojakstreet/ui_qt/chart_series.py)). Erst anschließend wird auf 520 Punkte begrenzt. Das passiert auch ohne ausgewählten Livechart. Die Komplexität hängt bis zur Begrenzung von **Instrumentzahl × History-Länge** ab; die Sortierung kann zusätzlichen Aufwand verursachen. Unsichtbare Verläufe verursachen somit Datenarbeit, ohne dass alle unsichtbaren Charts gerendert werden.

Die separat profilierte reife GUI-Variante ohne Livechart zählt pro Tick im Mittel **2.516,00 History-Merge-Aufrufe**, **923.372,00 Ordinal-Bestimmungen** und **1.846.744,00 Datumsabfragen**. Das ist tatsächlich gemessene interne Arbeit zusätzlich zu den etwa 61.600 wirtschaftlich veränderten Zahlenfeldern eines normalen Genesis-Tags. Die geladenen Simulationshistorien und die im laufenden UI erzeugten Live-Punkte können außerdem unterschiedliche Datumsrepräsentationen besitzen; der Parser behandelt diese über verschiedene Pfade. Die reife Reload-Reihe ist deshalb getrennt vom durchgehend laufenden ersten Jahr ausgewiesen.

Der Detailchart aktualisiert die sichtbare Zeichnung im aktuellen Live-Pfad direkt. Die Line-Vorschau bündelt eine Neuzeichnung über einen 48-ms-Timer; diese chartbezogene Wartezeit gehört zur Transition. Ein Preview-Candle hat dagegen einen anderen Live-Refresh-Pfad und wurde nicht mit dem vollständig live aktualisierten Detail-Candle verwechselt. Chartdaten werden außerdem über `_data_with_history` kopiert/vereinigt; ALL kann beim ersten Öffnen eine Hintergrund-History-Abfrage auslösen. Diese initiale Auswahl ist außerhalb der Tickmessung, spätere erforderliche Arbeit wird bis T4 berücksichtigt.

Die großen Heartbeat-Lücken quantifizieren die Blockade des GUI-Event-Loops durch History-/Model-Arbeit. Worker-Rechen- oder Commit-Wartezeit kann die neue Welt verspätet liefern, während die Oberfläche weiter Events bearbeitet. Beide Effekte müssen getrennt bewertet werden: „Core fertig → UI responsiv“ und „längster Event-Abstand“ stehen deshalb ausdrücklich in den Tabellen.

Für die Heartbeat-Statistik werden nur vollständig innerhalb T0→T4 liegende Abstände verwendet: der erste Heartbeat-Abstand jeder Zeile wird ausgeschlossen, weil dessen Beginn noch in der vorangegangenen Chart-/Setup-Phase liegen kann. Das beseitigt einen großen Setup-Ausreißer der Preview-Reihe. Die eigentliche T0→T4-Latenz und ihre Grenzen sind davon unverändert. Sehr kurze Abschnitte vor dem ersten Heartbeat sind dadurch in dieser ergänzenden Blockade-Kennzahl nicht vollständig erfasst.

## 9. Headless-Vergleich und deterministische Kontrolle

| Vergleich | ökonomische Signatur inklusive RNG gleich |
| --- | --- |
| headless-year-clean vs qt-year-clean-valid | ja |
| headless-year vs qt-year-valid | ja |
| headless-mature vs qt-mature-none-valid | ja |
| headless-mature vs qt-mature-detail-valid | ja |
| headless-mature vs qt-mature-heavy-valid | ja |
| headless-mature vs qt-mature-candle-valid | ja |
| headless-mature vs qt-mature-preview-valid | ja |
| control-original vs control-instrumented | ja |

Die Produktionssignatur prüft Datum, Länderwerte, Aktienpreise/Market Cap/Umsatz/FCF, Fonds, Indizes, Crypto, Bondpreise/-renditen/-rating, Portfolio sowie den Hash von Python- und NumPy-Zufallszuständen. Die vollständige Jahresreihe und die identischen reifen Vergleichsvarianten stimmen damit überein. Zusätzlich stimmen ein uninstrumentierter und ein instrumentierter 20-Tage-Genesis-Lauf überein. Dies prüft wesentliche ökonomische Ergebnisse und Zufallszustände, ist aber kein Vollvergleich sämtlicher temporärer Felder oder aller historischen Datenbank-Zeilen.

Zusätzlich wurde der offizielle öffentliche numerische Checkpoint-Inhalt vollständig gehasht: **498.200 Zahlenwerte**, identischer SHA-256-Hash `8e0fb0ed749c727cad4fae7e506e77a08784be66d8e42f4643eb8e4fcb696c6f` in Original und instrumentiertem Lauf. Private Cache-Felder, boolesche Werte und Text/Datum gehören nicht zu diesem Zahlenvergleich. Zusammen mit dem RNG-Signaturvergleich bestätigt dies, dass die Messadapter die geprüften ökonomischen Ergebnisse unverändert lassen.

Für die reife Welt beträgt der zusätzliche End-to-End-Abstand des GUI-/Prozesspfads gegenüber dem direkt ausgeführten Headless-Tick im Medianvergleich **3.316,48 ms**. Dieser Abstand ist eine Gesamtdifferenz; die exakte Zuordnung ergibt sich aus den T-Grenzen und Funktionsspans. Unterschiede der Core-Zeit zwischen separat gestarteten Läufen enthalten Cache-, Scheduling- und Messumgebungseinflüsse und dürfen nicht vollständig als Chartkosten ausgelegt werden. Der isolierte sichtbare Chartvergleich hält Seed, Startdatum und ökonomische Schritte gleich.

## 10. Speicher, GC, temporäre Objekte und Datenbewegung

| Messreihe / Tagtyp | n | Minimum ms | Median ms | Mean ms | p95 ms | Maximum ms |
| --- | --- | --- | --- | --- | --- | --- |
| Erzwungener Markets-Snapshot, reife Welt, persistenter Worker | 3 | 45.554,31 | 48.738,48 | 48.543,57 | 51.077,97 | 51.337,92 |

| Snapshot-/Step-Komponente | Median ms | p95 ms | % Step-Transition | Kategorie | Native-Core-Potenzial |
| --- | --- | --- | --- | --- | --- |
| Core | 271,54 | 314,30 | 0,56 % | A | kein primärer numerischer Core-Kandidat |
| Snapshot-Aufbau | 98,89 | 110,72 | 0,21 % | I | kein primärer numerischer Core-Kandidat |
| game_state_payload: asdict + encode | 18.098,37 | 18.451,07 | 36,61 % | I/A | kein primärer numerischer Core-Kandidat |
| JSON-Encoding | 5.368,51 | 5.796,84 | 11,18 % | I | kein primärer numerischer Core-Kandidat |
| Pipe-Write | 2.145,59 | 5.595,41 | 6,86 % | I/H | kein primärer numerischer Core-Kandidat |
| JSON-Decoding | 4.878,32 | 5.180,06 | 10,00 % | I | kein primärer numerischer Core-Kandidat |
| Rekursive State-Rekonstruktion | 9.059,85 | 9.812,50 | 19,04 % | I/A | kein primärer numerischer Core-Kandidat |
| Aktive View inklusive vollständigem History-Merge | 6.260,83 | 6.809,88 | 13,19 % | F/C/I | kein primärer numerischer Core-Kandidat |

`game_state_payload` verwendet `encode(asdict(state))`. Damit wird die angeforderte Dataclass-Struktur rekursiv kopiert und erneut in eine transportierbare Objektstruktur übersetzt. Die sichtbare Preishistorie ist zwar begrenzt, diese Grenze begrenzt nicht automatisch alle weiteren Asset-/Company-/Cache-Felder. Die normale Statusantwort vermeidet diese vollständige Struktur bereits. Beim Step-Pfad werden zusätzlich komplette Historien in die aktive View vereinigt. Die gemessenen etwa 49 Sekunden sind daher eine Daten-/Darstellungsgrenze mit einem vergleichsweise kleinen Core-Anteil.

Zur Zuordnung großer Datenstrukturen wurde der ein Jahr alte serialisierte **Checkpoint** separat nach Abschnitten vermessen. Dies ist eine Größenprojektion des Ausgangszustands, keine exakte byteweise Zerlegung der späteren 181–186-MB-Workerantwort. Die wichtigsten Abschnitte sind:

| Checkpoint-Abschnitt | JSON-Größe MB |
| --- | --- |
| aktien | 85,91 |
| derivatives | 24,81 |
| fonds | 19,34 |
| processed_products | 16,91 |
| indizes | 15,25 |
| FOREX_PAARE_HISTORIE | 10,10 |
| rohstoffe | 8,50 |
| makro | 4,56 |
| bond_market | 4,03 |
| kryptos | 2,06 |

| Aktienfeld, summiert über 1.280 Unternehmen | JSON-Größe MB |
| --- | --- |
| historie | 56,29 |
| open_interest_history | 22,48 |
| company_input_history | 1,43 |
| _company_quantity_plan | 0,96 |
| company_output_history | 0,61 |
| _momentum_cache | 0,30 |

Bei den Aktien dominieren Preis- und Open-Interest-Historien. Kleine interne Caches erklären die große Antwort daher nicht allein. Ein späterer Eingriff muss die tatsächlich benötigten Historien und den passenden Snapshot-Vertrag untersuchen; einfach den numerischen Core zu ersetzen beseitigt diese rekursiven Kopien nicht.

| Variante | Worker RSS Start MB | Worker RSS Ende MB | Eltern-RSS Start MB | Eltern-RSS Ende MB |
| --- | --- | --- | --- | --- |
| headless-year-clean | 154,01 | 2.052,24 | — | — |
| headless-mature | 1.323,20 | 1.324,82 | — | — |
| qt-year-clean-valid | 246,19 | 1.610,40 | 317,28 | 181,23 |
| qt-mature-none-valid | 1.310,79 | 1.313,84 | 1.450,00 | 1.446,03 |
| qt-mature-detail-valid | 1.320,41 | 1.290,94 | 1.455,12 | 1.371,70 |
| qt-force-snapshot-valid | 1.309,73 | 2.315,03 | 1.450,59 | 2.093,15 |

RSS ist die Windows-Working-Set-Messung pro Prozess, kein exakter Live-Objektbestand. Schwankungen enthalten Python-/Allocator-Retention, DuckDB, Qt und Betriebssystem-Effekte. Die Summe zweier Prozess-RSS-Werte kann gemeinsam abgebildete Seiten doppelt zählen. Ein langfristiger Leak ist aus der RSS-Zunahme allein nicht bewiesen.

| Variante, normal ohne Flush | Worker GC Median ms | Worker GC p95 ms | Eltern GC Median ms | Eltern GC p95 ms | Antwort Median MB | Antwort p95 MB |
| --- | --- | --- | --- | --- | --- | --- |
| qt-year-clean-valid | 12,14 | 275,67 | 0,75 | 1,30 | 1,05 | 1,08 |
| qt-mature-none-valid | 15,02 | 18,88 | 0,43 | 20,12 | 1,10 | 1,10 |
| qt-mature-detail-valid | 17,21 | 41,62 | 0,71 | 19,97 | 1,10 | 1,10 |

| Separate tracemalloc-Probe | Peak MB | Netto-Zuwachs MB | Netto-Blöcke | stark instrumentierte Wandzeit ms |
| --- | --- | --- | --- | --- |
| normal | 5,88 | 5,88 | 105614 | 9.797,76 |
| report | 7,93 | 7,92 | 128195 | 8.885,87 |
| qt-allocation-none-valid (1 Trace-Frame) | 13,27 | 13,25 | 65226 | 18.977,92 |
| qt-allocation-detail-valid (1 Trace-Frame) | 13,48 | 13,40 | 67217 | 19.799,33 |

Der Runtime deaktiviert GC während Simulation und record_day. Wieder aktivierte GC kann danach während Antwortaufbereitung/Serialization laufen; deshalb befinden sich die gemessenen GC-Pausen nicht zwingend innerhalb des numerischen Kerns. Lokale UI-History-Merges erzeugen für sehr viele Punkte kurzlebige Dictionaries, Schlüssel, Tupel und sortierte Listen. JSON erzeugt zusätzlich Text und erneut Python-Objekte auf der Empfängerseite. Die normale Statusantwort kopiert nicht jeden Tick den kompletten Welt-Snapshot, enthält aber weiterhin die geänderten aktuellen Tabellen und damit deutlich mehr als ein einzelnes Datum.

tracemalloc misst Python-Allokationen; native DuckDB-/Qt-/NumPy-Puffer sind damit nicht vollständig erfasst. Netto-Zuwachs ist keine Anzahl sämtlicher erzeugter und wieder freigegebener Objekte. Die Top-20-Allokationsstellen und exakten Byte-/Blockdifferenzen stehen in den `allocations-*.json`-Dateien. Core-Proben verwenden acht Trace-Frames, GUI-Proben einen Frame zur Begrenzung des Messaufwands. Für den UI-Objekt-Churn dienen zusätzlich die separat profilierten Funktions-/Call-Counts und RSS-Verläufe als Nachweis; es wurde keine behauptete exakte Gesamtzahl aller temporären UI-Objekte erfunden.

## 11. Top-20-Python-Hotspots: cumulative, self und Aufrufzahl

Die folgenden Zeiten sind Mittelwerte je **separatem cProfile-Tick**. Der Profiler verlangsamt vor allem viele kleine Python-Aufrufe; absolute Profilerzeiten ersetzen daher die oben gemessenen Normalzeiten nicht. Cumulative-Zeiten enthalten Kindfunktionen und überlappen. Allgemeine Audit-Wrapper bleiben sichtbar, damit die Messung nachvollziehbar ist. `~` bezeichnet eine C-/Builtin-Aufrufgrenze ohne Python-Quelldatei.

### Core: reife Welt, aufgewärmte Caches — 3 getrennt profilierte Ticks

**Top 20 nach cumulative time**

| Rang | Funktion | Quelle | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- | --- |
| 1 | advance_day | [legacy_runtime.py](../src/kojakstreet/adapters/legacy_runtime.py) | 712,52 | 0,02 | 1,00 |
| 2 | step | [day_transition_audit_support.py](../tools/day_transition_audit_support.py) | 650,05 | 0,02 | 1,00 |
| 3 | step_day | [simulation.py](../src/kojakstreet/core/simulation.py) | 650,00 | 0,06 | 1,00 |
| 4 | _phase | [simulation.py](../src/kojakstreet/core/simulation.py) | 649,19 | 0,06 | 13,00 |
| 5 | measured | [day_transition_audit_support.py](../tools/day_transition_audit_support.py) | 354,16 | 1,25 | 13,00 |
| 6 | _update_daily_production | [simulation.py](../src/kojakstreet/core/simulation.py) | 274,42 | 0,00 | 1,00 |
| 7 | update_daily_production_chain | [production_engine.py](../src/kojakstreet/core/production_engine.py) | 274,42 | 0,10 | 1,00 |
| 8 | update_production_chain | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 269,83 | 1,70 | 1,00 |
| 9 | _update_asset_market | [simulation.py](../src/kojakstreet/core/simulation.py) | 255,16 | 0,01 | 1,00 |
| 10 | update_daily_prices | [asset_market_engine.py](../src/kojakstreet/core/asset_market_engine.py) | 255,15 | 0,66 | 1,00 |
| 11 | update_markt_kurse | [market_calculations.py](../src/kojakstreet/core/market_calculations.py) | 254,49 | 30,19 | 1,00 |
| 12 | _update_country_trade_flows | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 134,95 | 30,31 | 1,00 |
| 13 | &lt;method 'get' of 'dict' objects&gt; | ~ | 129,85 | 129,85 | 434.861,67 |
| 14 | _update_derivatives | [simulation.py](../src/kojakstreet/core/simulation.py) | 94,24 | 0,01 | 1,00 |
| 15 | update_financial_products | [financial_products.py](../src/kojakstreet/core/financial_products.py) | 94,19 | 1,53 | 1,00 |
| 16 | _price_product | [financial_products.py](../src/kojakstreet/core/financial_products.py) | 85,98 | 0,40 | 566,00 |
| 17 | _update_company_utilization | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 79,11 | 18,12 | 1,00 |
| 18 | _yield_future_price | [financial_products.py](../src/kojakstreet/core/financial_products.py) | 74,12 | 0,57 | 80,00 |
| 19 | _government_bond_market_yield | [financial_products.py](../src/kojakstreet/core/financial_products.py) | 73,20 | 44,92 | 80,00 |
| 20 | record | [day_transition_audit_support.py](../tools/day_transition_audit_support.py) | 62,44 | 0,01 | 1,00 |

**Top 20 nach self time**

| Rang | Funktion | Quelle | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- | --- |
| 1 | &lt;method 'get' of 'dict' objects&gt; | ~ | 129,85 | 129,85 | 434.861,67 |
| 2 | &lt;built-in method builtins.max&gt; | ~ | 55,37 | 49,07 | 199.186,67 |
| 3 | _government_bond_market_yield | [financial_products.py](../src/kojakstreet/core/financial_products.py) | 73,20 | 44,92 | 80,00 |
| 4 | _update_country_trade_flows | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 134,95 | 30,31 | 1,00 |
| 5 | update_markt_kurse | [market_calculations.py](../src/kojakstreet/core/market_calculations.py) | 254,49 | 30,19 | 1,00 |
| 6 | &lt;method 'setdefault' of 'dict' objects&gt; | ~ | 26,21 | 26,21 | 67.776,00 |
| 7 | _record_company_quantity_history | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 44,30 | 20,37 | 1.280,00 |
| 8 | _update_company_utilization | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 79,11 | 18,12 | 1,00 |
| 9 | finish | [day_transition_audit_support.py](../tools/day_transition_audit_support.py) | 17,83 | 17,78 | 1,00 |
| 10 | append_history | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 32,08 | 17,42 | 19.900,00 |
| 11 | &lt;built-in method builtins.min&gt; | ~ | 14,46 | 14,46 | 59.685,67 |
| 12 | _bond_row_sets | [data_store.py](../src/kojakstreet/core/data_store.py) | 36,58 | 14,40 | 1,00 |
| 13 | &lt;method 'append' of 'list' objects&gt; | ~ | 13,92 | 13,92 | 50.584,67 |
| 14 | daily_asset_psychology_values | [psychology.py](../src/kojakstreet/core/psychology.py) | 44,04 | 13,26 | 1.346,00 |
| 15 | _update_open_interest | [market_calculations.py](../src/kojakstreet/core/market_calculations.py) | 49,12 | 12,49 | 1.346,00 |
| 16 | _match_country_trade | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 23,46 | 10,24 | 1,00 |
| 17 | _company_capacity | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 22,64 | 9,98 | 3.840,00 |
| 18 | _asset_return | [market_calculations.py](../src/kojakstreet/core/market_calculations.py) | 20,31 | 9,88 | 4.004,00 |
| 19 | _country_demand_weight | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 18,13 | 9,69 | 2.480,00 |
| 20 | _asset_rows | [data_store.py](../src/kojakstreet/core/data_store.py) | 20,36 | 9,36 | 1,00 |

**Top 20 nach call count**

| Rang | Funktion | Quelle | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- | --- |
| 1 | &lt;method 'get' of 'dict' objects&gt; | ~ | 129,85 | 129,85 | 434.861,67 |
| 2 | &lt;built-in method builtins.max&gt; | ~ | 55,37 | 49,07 | 199.186,67 |
| 3 | &lt;method 'setdefault' of 'dict' objects&gt; | ~ | 26,21 | 26,21 | 67.776,00 |
| 4 | &lt;built-in method builtins.min&gt; | ~ | 14,46 | 14,46 | 59.685,67 |
| 5 | &lt;built-in method builtins.len&gt; | ~ | 8,43 | 8,43 | 56.082,00 |
| 6 | &lt;method 'append' of 'list' objects&gt; | ~ | 13,92 | 13,92 | 50.584,67 |
| 7 | &lt;built-in method builtins.isinstance&gt; | ~ | 4,58 | 4,58 | 28.377,67 |
| 8 | _float | [data_store.py](../src/kojakstreet/core/data_store.py) | 5,66 | 5,66 | 26.011,00 |
| 9 | append_history | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 32,08 | 17,42 | 19.900,00 |
| 10 | &lt;built-in method builtins.abs&gt; | ~ | 3,13 | 3,13 | 18.253,33 |
| 11 | _clamp | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 10,24 | 4,96 | 11.775,00 |
| 12 | &lt;lambda&gt; | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 6,30 | 4,35 | 10.098,00 |
| 13 | _history_price | [market_calculations.py](../src/kojakstreet/core/market_calculations.py) | 7,23 | 5,62 | 9.354,00 |
| 14 | &lt;built-in method builtins.getattr&gt; | ~ | 4,58 | 3,68 | 8.209,00 |
| 15 | _clamp | [psychology.py](../src/kojakstreet/core/psychology.py) | 5,12 | 2,60 | 5.390,00 |
| 16 | &lt;method 'random' of '_random.Random' objects&gt; | ~ | 1,02 | 1,02 | 4.377,33 |
| 17 | _history_value_safe | [psychology.py](../src/kojakstreet/core/psychology.py) | 2,94 | 2,34 | 4.038,00 |
| 18 | _asset_return | [market_calculations.py](../src/kojakstreet/core/market_calculations.py) | 20,31 | 9,88 | 4.004,00 |
| 19 | _company_capacity | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 22,64 | 9,98 | 3.840,00 |
| 20 | _cached_output_mix | [production_chains.py](../src/kojakstreet/core/production_chains.py) | 7,53 | 3,13 | 3.840,00 |

### GUI: reife Welt ohne Livechart — 3 getrennt profilierte Ticks

**Top 20 nach cumulative time**

| Rang | Funktion | Quelle | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- | --- |
| 1 | measured | [day_transition_audit_support.py](../tools/day_transition_audit_support.py) | 12.914,42 | 0,13 | 7,00 |
| 2 | _apply_live_market_updates | [day_transition_audit.py](../tools/day_transition_audit.py) | 12.394,13 | 0,03 | 1,00 |
| 3 | _apply_live_market_updates | [app.py](../src/kojakstreet/ui_qt/app.py) | 12.394,08 | 0,05 | 1,00 |
| 4 | update | [day_transition_audit.py](../tools/day_transition_audit.py) | 12.385,60 | 0,02 | 1,00 |
| 5 | apply_live_quotes | [markets_view.py](../src/kojakstreet/ui_qt/views/markets_view.py) | 12.385,52 | 3,87 | 1,00 |
| 6 | _append_live_history | [markets_view.py](../src/kojakstreet/ui_qt/views/markets_view.py) | 12.344,10 | 199,14 | 1,00 |
| 7 | merge_history_by_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 12.118,46 | 1.290,61 | 2.516,00 |
| 8 | history_ordinal | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 7.545,30 | 2.985,45 | 923.372,00 |
| 9 | history_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 4.835,51 | 2.786,14 | 1.846.744,00 |
| 10 | &lt;built-in method builtins.isinstance&gt; | ~ | 1.770,52 | 1.770,52 | 11.083.223,00 |
| 11 | &lt;genexpr&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 1.117,29 | 1.117,26 | 3.673.360,00 |
| 12 | get | queue.py (Python standard library) | 766,16 | 22,85 | 5,00 |
| 13 | wait | threading.py (Python standard library) | 654,08 | 6,23 | 6,67 |
| 14 | advance | [app.py](../src/kojakstreet/ui_qt/app.py) | 557,43 | 0,05 | 1,00 |
| 15 | advance_days | [live_process.py](../src/kojakstreet/live_process.py) | 543,85 | 3,17 | 1,00 |
| 16 | _draw_items | [top_bar.py](../src/kojakstreet/ui_qt/widgets/top_bar.py) | 518,77 | 92,52 | 19,33 |
| 17 | &lt;built-in method builtins.sorted&gt; | ~ | 511,85 | 233,02 | 2.521,00 |
| 18 | _request | [live_process.py](../src/kojakstreet/live_process.py) | 508,04 | 0,04 | 1,00 |
| 19 | _wait_response | [live_process.py](../src/kojakstreet/live_process.py) | 506,14 | 0,03 | 1,00 |
| 20 | &lt;built-in method fromisoformat&gt; | ~ | 463,11 | 463,11 | 923.372,00 |

**Top 20 nach self time**

| Rang | Funktion | Quelle | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- | --- |
| 1 | history_ordinal | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 7.545,30 | 2.985,45 | 923.372,00 |
| 2 | history_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 4.835,51 | 2.786,14 | 1.846.744,00 |
| 3 | &lt;built-in method builtins.isinstance&gt; | ~ | 1.770,52 | 1.770,52 | 11.083.223,00 |
| 4 | merge_history_by_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 12.118,46 | 1.290,61 | 2.516,00 |
| 5 | &lt;genexpr&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 1.117,29 | 1.117,26 | 3.673.360,00 |
| 6 | &lt;built-in method fromisoformat&gt; | ~ | 463,11 | 463,11 | 923.372,00 |
| 7 | &lt;method 'strip' of 'str' objects&gt; | ~ | 399,86 | 399,86 | 1.846.744,00 |
| 8 | &lt;built-in method builtins.len&gt; | ~ | 280,56 | 280,56 | 1.850.731,67 |
| 9 | &lt;method 'split' of 'str' objects&gt; | ~ | 277,84 | 277,84 | 918.340,00 |
| 10 | &lt;lambda&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 272,78 | 272,78 | 923.372,00 |
| 11 | &lt;method 'drawText' of 'PySide6.QtGui.QPainter' objects&gt; | ~ | 266,96 | 266,96 | 20.184,00 |
| 12 | &lt;method 'toordinal' of 'datetime.date' objects&gt; | ~ | 241,84 | 241,84 | 923.372,00 |
| 13 | &lt;built-in method builtins.sorted&gt; | ~ | 511,85 | 233,02 | 2.521,00 |
| 14 | &lt;method 'horizontalAdvance' of 'PySide6.QtGui.QFontMetrics' objects&gt; | ~ | 204,41 | 204,41 | 20.184,00 |
| 15 | _append_live_history | [markets_view.py](../src/kojakstreet/ui_qt/views/markets_view.py) | 12.344,10 | 199,14 | 1,00 |
| 16 | _draw_items | [top_bar.py](../src/kojakstreet/ui_qt/widgets/top_bar.py) | 518,77 | 92,52 | 19,33 |
| 17 | &lt;method 'acquire' of '_thread.lock' objects&gt; | ~ | 326,91 | 56,70 | 28,67 |
| 18 | &lt;method 'get' of 'dict' objects&gt; | ~ | 39,29 | 39,29 | 81.130,33 |
| 19 | get | queue.py (Python standard library) | 766,16 | 22,85 | 5,00 |
| 20 | raw_decode | decoder.py (Python standard library) | 20,13 | 19,96 | 1,00 |

**Top 20 nach call count**

| Rang | Funktion | Quelle | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- | --- |
| 1 | &lt;built-in method builtins.isinstance&gt; | ~ | 1.770,52 | 1.770,52 | 11.083.223,00 |
| 2 | &lt;genexpr&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 1.117,29 | 1.117,26 | 3.673.360,00 |
| 3 | &lt;built-in method builtins.len&gt; | ~ | 280,56 | 280,56 | 1.850.731,67 |
| 4 | history_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 4.835,51 | 2.786,14 | 1.846.744,00 |
| 5 | &lt;method 'strip' of 'str' objects&gt; | ~ | 399,86 | 399,86 | 1.846.744,00 |
| 6 | history_ordinal | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 7.545,30 | 2.985,45 | 923.372,00 |
| 7 | &lt;lambda&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 272,78 | 272,78 | 923.372,00 |
| 8 | &lt;built-in method fromisoformat&gt; | ~ | 463,11 | 463,11 | 923.372,00 |
| 9 | &lt;method 'toordinal' of 'datetime.date' objects&gt; | ~ | 241,84 | 241,84 | 923.372,00 |
| 10 | &lt;method 'split' of 'str' objects&gt; | ~ | 277,84 | 277,84 | 918.340,00 |
| 11 | &lt;method 'get' of 'dict' objects&gt; | ~ | 39,29 | 39,29 | 81.130,33 |
| 12 | &lt;method 'drawText' of 'PySide6.QtGui.QPainter' objects&gt; | ~ | 266,96 | 266,96 | 20.184,00 |
| 13 | &lt;method 'setPen' of 'PySide6.QtGui.QPainter' objects&gt; | ~ | 15,23 | 15,23 | 20.184,00 |
| 14 | &lt;method 'horizontalAdvance' of 'PySide6.QtGui.QFontMetrics' objects&gt; | ~ | 204,41 | 204,41 | 20.184,00 |
| 15 | percent | [formatters.py](../src/kojakstreet/ui_qt/formatters.py) | 7,15 | 7,15 | 9.244,00 |
| 16 | &lt;method 'append' of 'list' objects&gt; | ~ | 0,71 | 0,71 | 2.556,67 |
| 17 | &lt;built-in method builtins.getattr&gt; | ~ | 0,42 | 0,42 | 2.542,67 |
| 18 | update_live | [chart_history_cache.py](../src/kojakstreet/ui_qt/chart_history_cache.py) | 0,98 | 0,98 | 2.523,00 |
| 19 | row_for_asset | [market_table_model.py](../src/kojakstreet/ui_qt/models/market_table_model.py) | 11,21 | 4,70 | 2.523,00 |
| 20 | &lt;built-in method builtins.sorted&gt; | ~ | 511,85 | 233,02 | 2.521,00 |

### GUI: reife Welt mit Detailchart — 3 getrennt profilierte Ticks

**Top 20 nach cumulative time**

| Rang | Funktion | Quelle | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- | --- |
| 1 | measured | [day_transition_audit_support.py](../tools/day_transition_audit_support.py) | 13.208,82 | 0,30 | 14,00 |
| 2 | _apply_live_market_updates | [day_transition_audit.py](../tools/day_transition_audit.py) | 12.649,46 | 0,02 | 1,00 |
| 3 | _apply_live_market_updates | [app.py](../src/kojakstreet/ui_qt/app.py) | 12.649,42 | 0,05 | 1,00 |
| 4 | update | [day_transition_audit.py](../tools/day_transition_audit.py) | 12.641,07 | 0,02 | 1,00 |
| 5 | apply_live_quotes | [markets_view.py](../src/kojakstreet/ui_qt/views/markets_view.py) | 12.640,96 | 4,09 | 1,00 |
| 6 | _append_live_history | [markets_view.py](../src/kojakstreet/ui_qt/views/markets_view.py) | 12.561,96 | 211,07 | 1,00 |
| 7 | merge_history_by_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 12.348,28 | 1.322,43 | 2.520,00 |
| 8 | history_ordinal | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 7.654,57 | 3.049,51 | 925.574,00 |
| 9 | history_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 4.903,24 | 2.835,19 | 1.851.515,00 |
| 10 | &lt;built-in method builtins.isinstance&gt; | ~ | 1.784,89 | 1.784,89 | 11.110.314,33 |
| 11 | &lt;genexpr&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 1.119,21 | 1.119,17 | 3.682.120,00 |
| 12 | get | queue.py (Python standard library) | 898,58 | 43,27 | 5,00 |
| 13 | wait | threading.py (Python standard library) | 640,13 | 7,97 | 5,33 |
| 14 | &lt;built-in method builtins.sorted&gt; | ~ | 552,76 | 237,53 | 2.527,67 |
| 15 | advance | [app.py](../src/kojakstreet/ui_qt/app.py) | 544,72 | 0,03 | 1,00 |
| 16 | advance_days | [live_process.py](../src/kojakstreet/live_process.py) | 544,55 | 0,02 | 1,00 |
| 17 | _draw_items | [top_bar.py](../src/kojakstreet/ui_qt/widgets/top_bar.py) | 534,57 | 96,16 | 19,33 |
| 18 | _request | [live_process.py](../src/kojakstreet/live_process.py) | 520,29 | 0,04 | 1,00 |
| 19 | _wait_response | [live_process.py](../src/kojakstreet/live_process.py) | 520,00 | 0,02 | 1,00 |
| 20 | paintEvent | [top_bar.py](../src/kojakstreet/ui_qt/widgets/top_bar.py) | 491,77 | 0,65 | 9,67 |

**Top 20 nach self time**

| Rang | Funktion | Quelle | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- | --- |
| 1 | history_ordinal | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 7.654,57 | 3.049,51 | 925.574,00 |
| 2 | history_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 4.903,24 | 2.835,19 | 1.851.515,00 |
| 3 | &lt;built-in method builtins.isinstance&gt; | ~ | 1.784,89 | 1.784,89 | 11.110.314,33 |
| 4 | merge_history_by_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 12.348,28 | 1.322,43 | 2.520,00 |
| 5 | &lt;genexpr&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 1.119,21 | 1.119,17 | 3.682.120,00 |
| 6 | &lt;built-in method fromisoformat&gt; | ~ | 471,64 | 471,64 | 925.574,00 |
| 7 | &lt;method 'strip' of 'str' objects&gt; | ~ | 408,31 | 408,31 | 1.850.781,00 |
| 8 | &lt;lambda&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 309,40 | 309,40 | 924.840,00 |
| 9 | &lt;built-in method builtins.len&gt; | ~ | 285,06 | 285,06 | 1.853.876,33 |
| 10 | &lt;method 'split' of 'str' objects&gt; | ~ | 281,58 | 281,58 | 920.530,00 |
| 11 | &lt;method 'drawText' of 'PySide6.QtGui.QPainter' objects&gt; | ~ | 259,58 | 259,58 | 20.196,67 |
| 12 | &lt;method 'toordinal' of 'datetime.date' objects&gt; | ~ | 247,50 | 247,50 | 925.574,00 |
| 13 | &lt;built-in method builtins.sorted&gt; | ~ | 552,76 | 237,53 | 2.527,67 |
| 14 | _append_live_history | [markets_view.py](../src/kojakstreet/ui_qt/views/markets_view.py) | 12.561,96 | 211,07 | 1,00 |
| 15 | &lt;method 'horizontalAdvance' of 'PySide6.QtGui.QFontMetrics' objects&gt; | ~ | 200,24 | 200,24 | 20.184,00 |
| 16 | _draw_items | [top_bar.py](../src/kojakstreet/ui_qt/widgets/top_bar.py) | 534,57 | 96,16 | 19,33 |
| 17 | get | queue.py (Python standard library) | 898,58 | 43,27 | 5,00 |
| 18 | &lt;method 'play' of 'PySide6.QtGui.QPicture' objects&gt; | ~ | 41,04 | 41,04 | 8,00 |
| 19 | &lt;method 'get' of 'dict' objects&gt; | ~ | 40,73 | 40,72 | 81.481,00 |
| 20 | &lt;method 'acquire' of '_thread.lock' objects&gt; | ~ | 227,06 | 21,43 | 23,33 |

**Top 20 nach call count**

| Rang | Funktion | Quelle | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- | --- |
| 1 | &lt;built-in method builtins.isinstance&gt; | ~ | 1.784,89 | 1.784,89 | 11.110.314,33 |
| 2 | &lt;genexpr&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 1.119,21 | 1.119,17 | 3.682.120,00 |
| 3 | &lt;built-in method builtins.len&gt; | ~ | 285,06 | 285,06 | 1.853.876,33 |
| 4 | history_date | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 4.903,24 | 2.835,19 | 1.851.515,00 |
| 5 | &lt;method 'strip' of 'str' objects&gt; | ~ | 408,31 | 408,31 | 1.850.781,00 |
| 6 | history_ordinal | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 7.654,57 | 3.049,51 | 925.574,00 |
| 7 | &lt;built-in method fromisoformat&gt; | ~ | 471,64 | 471,64 | 925.574,00 |
| 8 | &lt;method 'toordinal' of 'datetime.date' objects&gt; | ~ | 247,50 | 247,50 | 925.574,00 |
| 9 | &lt;lambda&gt; | [chart_series.py](../src/kojakstreet/ui_qt/chart_series.py) | 309,40 | 309,40 | 924.840,00 |
| 10 | &lt;method 'split' of 'str' objects&gt; | ~ | 281,58 | 281,58 | 920.530,00 |
| 11 | &lt;method 'get' of 'dict' objects&gt; | ~ | 40,73 | 40,72 | 81.481,00 |
| 12 | &lt;method 'setPen' of 'PySide6.QtGui.QPainter' objects&gt; | ~ | 15,08 | 15,08 | 20.315,67 |
| 13 | &lt;method 'drawText' of 'PySide6.QtGui.QPainter' objects&gt; | ~ | 259,58 | 259,58 | 20.196,67 |
| 14 | &lt;method 'horizontalAdvance' of 'PySide6.QtGui.QFontMetrics' objects&gt; | ~ | 200,24 | 200,24 | 20.184,00 |
| 15 | percent | [formatters.py](../src/kojakstreet/ui_qt/formatters.py) | 7,18 | 7,18 | 9.246,00 |
| 16 | &lt;method 'append' of 'list' objects&gt; | ~ | 0,92 | 0,92 | 3.373,33 |
| 17 | &lt;built-in method builtins.getattr&gt; | ~ | 0,48 | 0,48 | 2.596,00 |
| 18 | &lt;built-in method builtins.hash&gt; | ~ | 0,40 | 0,40 | 2.549,67 |
| 19 | &lt;built-in method builtins.sorted&gt; | ~ | 552,76 | 237,53 | 2.527,67 |
| 20 | __hash__ | <string> | 1,16 | 0,77 | 2.527,00 |

### Reporting-Core — Top 20 cumulative, 3 Profiler-Ticks

| Rang | Funktion | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- |
| 1 | advance_day | 1.135,79 | 0,02 | 1,00 |
| 2 | step | 955,70 | 0,02 | 1,00 |
| 3 | step_day | 955,64 | 0,06 | 1,00 |
| 4 | _phase | 954,74 | 0,05 | 12,00 |
| 5 | _run_monthly_company_report_if_due | 579,67 | 0,05 | 1,00 |
| 6 | measured | 527,63 | 1,60 | 17,00 |
| 7 | _update_monthly_production | 330,89 | 0,01 | 1,00 |
| 8 | update_production_chain | 330,89 | 1,00 | 1,00 |
| 9 | update_production_chain | 316,72 | 1,50 | 1,00 |
| 10 | _update_asset_market | 259,82 | 0,01 | 1,00 |
| 11 | update_daily_prices | 259,81 | 0,64 | 1,00 |
| 12 | update_markt_kurse | 259,18 | 28,55 | 1,00 |
| 13 | &lt;method 'get' of 'dict' objects&gt; | 208,17 | 208,17 | 690.181,00 |
| 14 | _update_monthly_companies | 206,99 | 0,00 | 1,00 |
| 15 | update_companies | 206,98 | 0,02 | 1,00 |
| 16 | update_monthly_companies | 206,92 | 11,51 | 1,00 |
| 17 | record | 180,07 | 0,01 | 1,00 |
| 18 | record_day | 180,03 | 0,74 | 1,00 |
| 19 | _update_country_trade_flows | 135,62 | 30,77 | 1,00 |
| 20 | _update_company_utilization | 115,06 | 17,95 | 1,00 |

### Flush einschließlich Persistenz — Top 20 cumulative, 3 Profiler-Ticks

| Rang | Funktion | cum ms/Tick | self ms/Tick | Calls/Tick |
| --- | --- | --- | --- | --- |
| 1 | record_day | 11.447,96 | 0,02 | 1,00 |
| 2 | flush | 10.781,98 | 0,14 | 1,00 |
| 3 | _invoke | 9.646,87 | 4.609,68 | 151,00 |
| 4 | _compact_completed_history | 8.358,81 | 0,41 | 1,00 |
| 5 | fetchone | 6.981,55 | 0,55 | 3,00 |
| 6 | _replace_buffered_rows | 6.003,37 | 25,10 | 14,00 |
| 7 | insert | 5.964,48 | 2,57 | 26,00 |
| 8 | _insert_rows | 5.960,84 | 1,14 | 26,00 |
| 9 | execute | 5.437,06 | 1,28 | 147,00 |
| 10 | _find_and_load | 4.991,73 | 48,66 | 4.260,00 |
| 11 | _find_and_load_unlocked | 4.757,19 | 23,95 | 4.260,00 |
| 12 | _find_spec | 4.731,36 | 60,63 | 4.260,00 |
| 13 | find_spec | 4.579,28 | 6,79 | 4.260,00 |
| 14 | _get_spec | 4.572,49 | 78,59 | 4.260,00 |
| 15 | find_spec | 4.461,60 | 348,77 | 38.340,00 |
| 16 | executemany | 4.211,13 | 0,03 | 4,00 |
| 17 | _path_stat | 2.471,27 | 23,82 | 38.340,00 |
| 18 | &lt;built-in method nt.stat&gt; | 2.451,63 | 2.451,12 | 38.362,00 |
| 19 | _aggregate_spec | 2.264,54 | 1,45 | 73,00 |
| 20 | _path_join | 1.554,25 | 989,77 | 191.700,00 |

Weitere getrennte Profile für normalen frühen Tag, Monatsende und 31.12. liegen vollständig in `summary.json` und den `.pstats`-Dateien vor, einschließlich ihrer jeweiligen Top-20-cumulative/self/calls-Listen. Die umfangreichen History-Dateiparsings, Dictionary-Lookups, Listenkonstruktionen und Sortierungen sind in den UI-Call-Counts sichtbar; Unternehmens-/Länder-/Marktloops in den Core-Profilen. Quellenzeilen der instrumentierten Marktloops bleiben auf die ursprünglichen Dateien bezogen.

Die ursprünglichen Core-Profile restaurieren vor jedem Sample denselben Checkpoint und zeigen damit auch kalte Referenz-/Underlying-Caches. Gerade Fonds-Unterlying-Suchen sind dort wesentlich größer als im üblichen warmen Tick. Für die oben gezeigten warmen Core-Top-20 wird die identische reife Welt zunächst fünf Tage unprofiliert weitergerechnet; anschließend werden drei normale Tage separat profiliert. Die kalte Reihe `mature_normal` bleibt vollständig in den Rohdaten erhalten. Keine kalte Profilerzeit wird als dauerhafte tägliche Fonds-Latenz ausgegeben.

## 12. Root Causes A–J und Potenzial ohne Sprachwechsel

| Kategorie | Befund / Konsequenz |
| --- | --- |
| A Python/Objekte | Aktienloop, Trade, Company-IO sowie History-Datumsparsing/Dictionaries; gemessene Self-/Call-Hotspots |
| B GIL/Parallelität | Core weitgehend seriell; Worker besitzt bereits eigenen GIL. UI-Python bleibt ein serieller Abschnitt |
| C Algorithmus | Tägliches komplettes History-Merge aller Instrumente; gleicher Arbeitsumfang wäre auch in Rust/C++ vorhanden |
| D DuckDB/SQL | Nur an Flush-/History-Pfaden große API-/Commit-Zeit; besonders Telemetrie-executemany prüfen |
| E NumPy/native | Kein großer vektorisierter NumPy-Daily-Kernel im erfassten Core; DuckDB/Qt sind bereits native Bibliotheken |
| F Qt/UI | Model-/Label-Arbeit, Queued-Zustellung, Layout/Paint; Main-Thread-History blockiert Events |
| G Charts | Sichtbare Chartdaten, Linien/Candles, pyqtgraph-Paint; Messung trennt Plot-Aufbau von Paint |
| H I/O | CSV-Dateien, COPY, COMMIT und Pipe; nicht durch einen neuen numerischen Core beseitigt |
| I Kopien/Serialization | Status/current_rows, JSON, Decode/Merge sowie History-Listen/Dictionaries |
| J Sonstiges | GC, OS-/Qt-Scheduling, Heartbeat-Abtastung und nicht separat isolierter Rest |

Priorität 1: Der gemessene `_append_live_history`-Block beansprucht in der reifen Welt ohne Chart im Median **3.025,07 ms**. Der Ansatzpunkt ist inkrementelles Einfügen/Ersetzen eines neuen Datumpunkts und bedarfsgerechte Vorbereitung sichtbarer Verläufe. Die heutige Begrenzung auf 520 Punkte begrenzt langfristig die Größe, verhindert aber das tägliche vollständige Parsing/Merge nicht. Die genannte Zeit ist der adressierbare aktuelle Block, keine bereits erreichte Einsparung.

Priorität 2: Den Flush anhand der teuersten SQL-Aufrufe zerlegen. Kleine Phase-Metric-Batches, Current-Table-Replacement, History-Compaction und COMMIT gezielt mit der bestehenden API untersuchen. Batch-/Transaction-Verhalten, CSV-Konvertierung und erforderliche Persistenzgarantien müssen dabei jeweils separat validiert werden.

Priorität 3: Übergabegröße und doppelte Datenarbeit reduzieren, sofern die UI die entsprechenden Daten wirklich benötigt. Der heutige Status-/Delta-Pfad ist bereits deutlich begrenzter als ein erzwungener Vollsnapshot; dennoch entstehen messbare JSON-/Row-Kosten. Danach erst die Core-Hotspots und gegebenenfalls Array-/Cache-Aufbereitung prüfen.

Zusatzkontrolle des vorhandenen erzwungenen Snapshot-/Step-Pfads: n=3, Median **48.738,48 ms**, p95 **51.077,97 ms**. Diese kleine gesonderte Stichprobe darf nicht mit normalen Timer-Ticks vermischt werden. Sie belegt den Unterschied der angeforderten Übergabe-/UI-Pfade, nicht den isolierten Preis einer einzelnen Kopie.

Die oben genannte Reihenfolge betrifft die normalen Timer-Ticks. **Für manuelle Einzelschritte hat der vollständige Snapshot-/Übergabepfad höchste Priorität**, weil er den dort gemessenen Gesamtwechsel dominiert. Beide Bedienpfade brauchen eigene Erfolgsmessungen: ein schnellerer Timer-Tick bestätigt noch keine Verbesserung des manuellen Steps.

## 13. Quantitatives Potenzial eines nativen Simulationskerns

| Variante | gemessener Core-Anteil | Gesamtlatenz-Ersparnis bei 2× Core¹ | bei 5× Core¹ | absolute Obergrenze bei kostenlosem Core |
| --- | --- | --- | --- | --- |
| manueller Vollsnapshot | 0,56 % | 0,28 % | 0,45 % | 0,56 % |
| erstes Jahr normal | 16,60 % | 8,30 % | 13,28 % | 16,60 % |
| reife Welt normal | 6,49 % | 3,24 % | 5,19 % | 6,49 % |
| reife Welt Detailchart | 6,57 % | 3,29 % | 5,26 % | 6,57 % |
| Flush-Tage | 3,03 % | 1,52 % | 2,43 % | 3,03 % |

¹ 2× und 5× sind ausdrücklich **Rechenszenarien**, keine gemessenen Rust-/C++-Beschleunigungen. Rechnung: ersparter Anteil = Core-Anteil × (1−1/s). Die extreme Obergrenze setzt einen kostenfreien ganzen Core ohne neue Buffer-, Copy- oder Rückschreibkosten voraus und ist praktisch nicht erreichbar. Ein kleiner PoC adressiert nur einen Teil dieses Core-Anteils. Die Messungen erlauben eine Bandbreite von null beziehungsweise bei ungünstiger Interop sogar negativer Netto-Ersparnis bis höchstens zu diesem adressierbaren Anteil; eine garantierte positive Untergrenze gibt es ohne implementierten PoC nicht.

Ein Simulationskern würde UI-History-Merge, Qt-Paint, bereits native DuckDB-Calls, CSV-/JSON-Übergaben und Commit-I/O zunächst unverändert lassen. Ein schnellerer Core allein begründet daher kein praktisch sofortiges Spielgefühl. Bereits native Funktionen erneut in einer anderen Sprache aufzurufen ist kein eigenständiger Leistungsgewinn. Ein Hybrid kann nach Beseitigung der größeren Ursachen sinnvoll werden, wenn die erneut gemessene Core-Latenz das verbleibende Ziel verhindert.

## 14. Rust versus C++ für einen isolierten Hybrid

| Aspekt | Rust | C++ |
| --- | --- | --- |
| Python-Interop | PyO3/maturin; pro Subsystem ein grober Batch-Aufruf | pybind11; ebenfalls grober Batch-Aufruf |
| NumPy/Memory Layout | Contiguous Arrays/Buffers, Ownership-/Lifetime-Regeln ausdrücklich festlegen | Buffer-Protokoll/NumPy Views; kein implizites STL-Dict/List-Copying im Hotpath |
| DuckDB | Bestehenden Python-Store zunächst weiterverwenden; keine neue Datenbankintegration nötig | Dasselbe; native DuckDB-Integration nur bei belegtem Nutzen |
| Determinismus | RNG-Reihenfolge und Float-/Summationsreihenfolge fest definieren | Dasselbe; fast-math und andere Reduktionsreihenfolgen zunächst vermeiden |
| Komplexer Zustand | Typisierung/Ownership helfen, aber gekoppelte Simulationslogik muss sauber abgegrenzt werden | Passende Strukturen leicht ausdrückbar, Lifetime-/Aliasing-Fehler eigenständig absichern |
| Multithreading/GIL | Nur abgelöste numerische Buffers ohne Python-Zugriffe parallel bearbeiten | GIL gezielt freigeben; währenddessen keine Python-Objekte anfassen |
| Memory Safety | Sichere Rust-Pfade können viele Speicherfehler verhindern; FFI bleibt Prüfgrenze | Manuelle Verantwortung für Speicher/Lifetimes; Sanitizer und klare Buffer-Verträge wichtig |
| Windows-Build/Packaging | Rust-Toolchain + passende MSVC/Python-Wheels; maturin-Verteilung testen | MSVC/CMake + pybind11/Python-Wheels; reproduzierbarer Compiler-/ABI-Pfad nötig |
| Tests/Wartbarkeit | Differenztests und Bilanzinvarianten; zusätzliche Sprache/Buildkette | Dieselben Tests/Invarianten; zusätzliche Sprache/Buildkette |
| Schrittweise Migration | Ein Kernel mit Python-Fallback, versionierter API und gemessenem Übergabeaufwand | Dasselbe |
| AI-unterstützte Entwicklung | Hilfreich für Bindings/Tests; numerische Gleichheit und Eigentumsregeln müssen belegt werden | Hilfreich für Bindings/Tests; Lifetimes/Determinismus müssen belegt werden |

Für einen neuen, kleinen numerischen PoC wäre Rust mit PyO3/maturin eine gut begründbare Option, wenn die zusätzliche Toolchain akzeptabel ist. C++/pybind11 ist ebenso tragfähig, besonders bei vorhandener C++-Erfahrung. Die Messung zeigt keinen Sprachvergleich und keine Überlegenheit bei der Netto-Latenz. PyO3 beschreibt das explizite Ablösen für parallele native Arbeit ([Parallelism](https://pyo3.rs/main/parallelism)); pybind11 gibt den GIL nicht automatisch frei ([GIL](https://pybind11.readthedocs.io/en/stable/advanced/misc.html)). Direkte Array-/Buffer-Übergaben sind dokumentiert unter [pybind11 NumPy](https://pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html); Windows-/Wheel-Verteilung unter [maturin Distribution](https://www.maturin.rs/distribution.html).

## 15. Drei abgrenzbare PoC-Kandidaten, keine Migration durchgeführt

| Priorität / Kandidat | Gemessener heutiger Bereich | Abgrenzung und Validierung |
| --- | --- | --- |
| 1. Trade-/Länder-Güter-Kernel | Median 43,57 ms im reifen GUI-Core | Spaltenarrays für Angebot, Nachfrage, Gewichte und Länder-/Produktindizes; ein Batch; Ergebnis gegen Export/Import/Netto/Shortage/Pressure und Bilanzinvarianten prüfen |
| 2. Aktienpreis-Batch | Median 72,74 ms für die gesamte bestehende Stock-Schleife | Nur numerische Preisformel nach vorhandener Fundamentals-/EMA-Aufbereitung; Python-Zufallswerte in unveränderter Reihenfolge liefern; sämtliche 1.280 Ergebnisse und RNG-Folgezustand prüfen |
| 3. Company-IO-/Auslastungs-Batch | Median 22,18 ms einschließlich Historienarbeit | Kapazitäts-/Input-/Output-Tabellen numerisch abgrenzen; History-Schreiben außerhalb halten; Inventare, Mengen und Fortschreibung vergleichen |

Bester erster nativer PoC **nach den größeren UI-/Store-Ursachen**: der Trade-/Länder-Güter-Kernel. Er ist numerisch besser abgrenzbar als ein komplett gekoppelter Company-/Market-State. Der gesamte heutige Funktionsblock ist jeweils eine Obergrenze; ein Kernel ersetzt davon nur einen Teil. Ein Batch-Aufruf muss inklusive Python→Array-Konvertierung, nativer Rechnung, Array→State-Rückschreibung, Allokationen und eventueller Synchronisation gemessen werden.

Validierung: identischer Checkpoint und Seed, Vergleich zunächst jeder Schritt-Ausgabe und des RNG-Zustands, danach normaler Tag, Bericht, Policy, jährlicher Bond-Pfad und 365-Tage-Folge. Anfangs exakte Gleichheit fordern; mögliche Float-Differenzen, Reihenfolgeänderungen und deren Ausbreitung ausdrücklich untersuchen. Akzeptierte Toleranzen dürfen erst fachlich festgelegt werden und ersetzen keine Bilanz-/Marktinvarianten. Python-Fallback behalten. Der Audit enthält weder einen implementierten nativen PoC noch einen Rewrite.

## 16. Spielgefühl und ein sinnvolles Ziel

Als Orientierung, nicht als harte Wahrnehmungsgrenze: wenige zehn Millisekunden mit weiterlaufender Event-Loop können praktisch unmittelbar oder sehr flüssig wirken. Um etwa hundert Millisekunden wird eine Zustandsverzögerung bei direkter Interaktion oft bemerkbar; derselbe Zeitraum als GUI-Blockade stört stärker. Mehrere hundert Millisekunden wirken als deutlicher Wechsel, mehrsekündige Main-Thread-Pausen als Hängen. Anzeige, Animationsdesign, Nutzereingabe, Rechnerlast und Datenmenge verändern diese Einordnung.

Als allgemeine UX-Orientierung dient hier [Jakob Nielsens Einordnung von Antwortzeiten](https://www.nngroup.com/articles/response-times-3-important-limits/). Die Übertragung auf das Spiel und die unterschiedliche Wirkung von Hintergrundrechnung und GUI-Blockade sind die Bewertung dieses Audits, keine aus der Quelle abgeleitete feste Spielgrenze.

Die gemessenen mehrsekündigen History-/Flush-Pfade erfüllen das gewünschte unmittelbare Wechselgefühl nicht. Die Hintergrundsimulation allein ist wesentlich kleiner; ihre Zeit ist jedoch noch keine Garantie für unmittelbare Sichtbarkeit. Ein geeignetes späteres Produktziel wäre eine kleine, separat gemessene Main-Thread-Blockade und eine T0→T4-Latenz im niedrigen zweistelligen bis niedrigen dreistelligen Millisekundenbereich für normale Tage, mit ausdrücklich definierter Behandlung von Persistenz und Berichtstagen. Das ist ein vorgeschlagenes Entwicklungsziel, kein bereits erreichter oder physiologisch verbindlicher Grenzwert.

## 17. Abschluss, Empfehlung, Einschränkungen und reproduzierbare Daten

**Aktuellen Ansatz behalten und Python-/History-/Übergabe-/SQL-Pfade gezielt optimieren.** Die Prozess-Worker-Architektur ist bereits geeignet, die UI während der Core-Rechnung frei zu halten. Zuerst sind die History-Verarbeitung normaler Ticks, vollständige Snapshots manueller Steps und die periodische Persistenz zu bearbeiten. Eine sofortige Native-Core-Migration oder ein vollständiger Rewrite ist aus dem Audit nicht gerechtfertigt. Ein späterer Hybrid ist eine überprüfbare Option für den isolierten Trade-PoC, wenn erneute Messungen nach den prioritären Änderungen einen verbleibenden Core-Bedarf zeigen.

Alle Zahlen gelten für diesen Rechner, die Genesis-Welt und die getesteten Ansichten/Charts. Keine Aussage über jede Handelsstrategie, mehrere gleichzeitig offene Detailfenster, extreme Portfolios, weit ältere Welten oder Benutzer-/Save-/History-Anfrage-Kollisionen. Kleine Zusatzstichproben und der operational gemessene Paint-/Heartbeat-Endpunkt sind ausdrücklich gekennzeichnet. Kein nativer CPU-Stack-Trace, keine physische Kernzuordnung und kein GPU-Present-Trace wurden vorgetäuscht. Profiler- und Allocation-Zeiten bleiben von den Baselines getrennt. Die früheren, ungültigen GUI-Läufe sind nur Debug-Artefakte und werden von der Zusammenfassung ausgeschlossen.

Eine unabhängige Kontrolle verwendet die **originale KojakStreetWindow-Klasse ohne den Audit-Abschluss-Slot**. Ihre 3 beobachteten Quote-Aktualisierungen laufen im Qt-Hauptthread: **bestanden**. Die Integritätsprüfung aller 861 GUI-Messpunkte überprüft Zeitreihenfolge, T0→T4-Arithmetik, Worker-/UI-Datum, positive Model-Zeilenzahlen, Main-Thread-Zuordnung, sauberen Abschluss und die ökonomischen Signaturvergleiche: **bestanden**.

Reproduzierbare Werkzeuge und Daten:

- [Messdriver](../tools/day_transition_audit.py)
- [Mess-Observer und instrumentierte Spans](../tools/day_transition_audit_support.py)
- [Sequenzielle vollständige Messsuite](../tools/day_transition_audit_suite.py)
- [Statistik und Profile](../tools/day_transition_audit_summary.py)
- `.cache/day-transition-audit/summary.json` (local evidence)
- `.cache/day-transition-audit/merged-results.json` (local evidence)
- `.cache/day-transition-audit/profiles.json` (local evidence)
- `.cache/day-transition-audit/allocations-normal.json` (local evidence)
- `.cache/day-transition-audit/allocations-report.json` (local evidence)
- `.cache/day-transition-audit/allocations-qt-allocation-none-valid-0.json` (local evidence)
- `.cache/day-transition-audit/allocations-qt-allocation-detail-valid-0.json` (local evidence)
- `.cache/day-transition-audit/validation.json` (local evidence)
- `.cache/day-transition-audit/production-thread-control.json` (local evidence)
- `.cache/day-transition-audit/duck-import-diagnostics-clean.json` (local evidence)
- `.cache/day-transition-audit/import-path-control.json` (local evidence)
- `.cache/day-transition-audit/production-path-check.json` (local evidence)
- `.cache/day-transition-audit/snapshot-volume.json` (local evidence)
- `.cache/day-transition-audit/qt-mature-detail-valid.png` (local evidence)
- `.cache/day-transition-audit/qt-mature-none-valid.png` (local evidence)

Aufruf über die bestehende Projekt-Python-Umgebung: `python tools/day_transition_audit_suite.py`. Die Suite erzeugt neue isolierte Audit-Verzeichnisse; bestehende Worker-Logs mit demselben Namen werden absichtlich nicht überschrieben. Für neue Wiederholungen neue Namen verwenden oder ausschließlich eigene Audit-Artefakte kontrolliert entfernen. Produktion und bestehende Spielstände werden nicht angepasst. Die Statistiken können separat mit `python tools/day_transition_audit_summary.py` und dieser Bericht mit `python tools/day_transition_audit_report.py` erneut erzeugt werden.
