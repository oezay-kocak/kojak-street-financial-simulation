# Politics V1 und Society & Politics – Umsetzung

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Stand: 7. Oktober 2026. Grundlage: freigegebener Implementierungsauftrag; Politik/UI vollständig, wirtschaftlicher Hook gemäß Freigabegate ausgeschaltet.

## 1. Geänderte Dateien

Gegen den zu Auftragsbeginn eingefrorenen Stand geändert:

- `src/kojakstreet/adapters/legacy_runtime.py`
- `src/kojakstreet/adapters/legacy_state.py`
- `src/kojakstreet/core/checkpoints.py`
- `src/kojakstreet/core/data_store.py`
- `src/kojakstreet/core/data_store_schema.py`
- `src/kojakstreet/core/established_world.py`
- `src/kojakstreet/core/fast_history.py`
- `src/kojakstreet/core/heterogeneous_start.py`
- `src/kojakstreet/core/history.py`
- `src/kojakstreet/core/simulation.py`
- `src/kojakstreet/live_process.py`
- `src/kojakstreet/ui_qt/app.py`
- `src/kojakstreet/ui_qt/views/macro_view.py`
- `src/kojakstreet/visible_state.py`
- `tests/test_workspace_views.py`

Neu:

- `src/kojakstreet/core/politics.py`
- `src/kojakstreet/ui_qt/widgets/pie_chart.py`
- `src/kojakstreet/ui_qt/widgets/society_politics_panel.py`
- `tests/test_politics.py`
- `tests/test_politics_process.py`
- `tools/politics_validation.py`
- `tools/politics_writer_crash.py`
- `tools/politics_legacy_probe.py`
- `tools/politics_report.py`
- `tools/politics_ui_closeout.py`

Andere bereits vorhandene Änderungen im Arbeitsverzeichnis wurden erhalten. Referenz: `.cache/politics-implementation/baseline`, Dateiprüfsummen: `before-hashes.json` und `closeout.json`.

## 2. Politikmodell und Version

Politics Model 1, Calibration 1; Initialisierungs-/Wahlstreams enthalten den Modellstand. Checkpoint 9, Historyschema 3, Generator 4. Wirtschaftsmodell `workforce-demographics-v1`, Fast History 3 und Bundleformat 1 bleiben erhalten: Der wirtschaftliche Hook ist aus. Die Trajektorienidentität weist Politics Model 1 separat aus.

## 3. Sieben Systeme

| System | Kalenderjahre | Mechanik |
|---|---:|---|
| Parliamentary Democracy | 4 | Wahl |
| Presidential Democracy | 4 | Wahl |
| Semi-Presidential Democracy | 5 | Wahl |
| Constitutional Monarchy | 4 | Wahl |
| Absolute Monarchy | kein Termin | Kontinuität |
| One-Party State | 5 | Review |
| Authoritarian Republic | 5 | Review |

Die Gewichte sind Produktparameter, keine Abbildung realer Staaten. Kein Regime erhält einen direkten Wirtschafts- oder Stabilitätsbonus.

## 4. Parteimodell

Kompetitive Systeme 2–7 Parteien, One-Party genau eine, Absolute Monarchy und Authoritarian Republic keine Parteien. Stabile Länder-/Parteischlüssel, feste Economic-/Social-Achsen, initiale Mandate und separat letzte tatsächlich simulierte Stimmen. Keine Sitze, Umfragen, Wahlbeteiligung oder Politiker.

## 5. Ideologie

Zwei Achsen in [−1,+1], angezeigte Regierungsachsen nach Mandatsgewichten. Wirtschaft: interventionistisch bis marktliberal; Gesellschaft: progressiv bis konservativ. Ohne wirtschaftlichen Policykanal. Kohäsion verwendet tatsächlich beteiligte Regierungsparteien.

## 6. Namen

36 neutrale Kombinationen aus neun Wörtern und vier Endungen. Ohne Wiederholung je Land aus eigenem Namensstream; unveränderliche IDs `Land:pN`. Namen sind kein Regime-/Kultur-/Wohlstandsclassifier.

## 7. RNG-Isolation

SHA-256 → lokale Random-Instanzen für politische Roots, Namen und jede Wahlsequenz/Partei. Kein Python-/NumPy-Welt-RNG-Verbrauch. Länder und Parteien werden vor Wahl/Formation nach stabiler ID sortiert. Reorder-, Navigation-, Save/Load- und Vergleichskontrollen bestehen.

## 8. Genesis

Alle Länder starten parlamentarisch, mit vier Parteien, Mandaten 40/30/20/10 %, identischen mechanischen Achsen und S_pol 75. Die Basis kompensiert genau diese gemeinsamen Strukturkomponenten. Nächste Wahl nach vier Kalenderjahren. Kein vergangenes Ergebnis; Namen und IDs sind länderspezifisch.

## 9. Heterogeneous

Gleichgewichtete Auswahl aus sieben Systemen, bei Wettbewerb gleichgewichtete Parteienzahl 2–7, unabhängige Politik-Domainroots, normalisierte positive Mandate, zufällige Achsen und Basis 70–85. Erste fällige Wahl/Review zwischen 180 Tagen und dem 4-/5-Jahresfenster. Keine vergangenen Wahlen; vorhandene Wirtschaftsbudgets unverändert.

## 10. Established-Historie

Initialisierung am Originalstart. Jeder Jahres-/Monatsbucket verarbeitet chronologisch alle übersprungenen 15.-Monatsberichte und Wahl-/Reviewtermine. Monatsmakroinputs werden im Bucket interpoliert und als `coarse_interpolated_monthly_report` markiert. Die drei angehängten Makrowerte werden anschließend exakt auf den wirtschaftlichen Bucket-Endzustand zurückgesetzt. Parteien, Ergebnis, Regierung und Übergang laufen durch den normalen 365-Tage-Burn-in weiter; keine Enddekoration.

## 11. Kalender

Eigenes gespeichertes `politics_calendar.next_due` als rekonstruierbares O(1)-Gate; Wahrheit sind Country-Termine und Sequenzen. Kalenderjahre statt 365×Jahre, Monatsende/Schaltjahr werden geklemmt. Genau-einmal-Verarbeitung, auch auf Monatsberichtstagen. Absolute Monarchy ohne erfundenen Wahltimer.

## 12. Wahlformel und Kalibrierung

Gemeinsamer Regierungsswing: `clip(0.5 Δgrowth − 0.4 Δunemployment − 0.3 Δinflation + 0.0002 (S_pol−75), ±0.04)`. Proportionale Verteilung auf Regierung/Opposition, eigener Rohnoise ±0.01 je Partei, positive Untergrenze 0.001, genau eine Normalisierung. Diese Grenzen betreffen Rohswing/-noise; die abschließende Normalisierung verschiebt die resultierenden Einzelanteile. Inputs stammen aus dem vorher veröffentlichten Bericht, mit Datum, Quelle und alter Baseline im unveränderlichen Ergebnis.

## 13. Regierungsbildung

Höchstens 127 Subsets. Mehrheit >50 %, Economic-Spanne/2 ≤0.55. Deterministisches Ranking nach Kohäsion, Größe, bisheriger Beteiligung, Unterstützung und IDs. Andernfalls stärkste Partei mit ausreichend nahen externen Unterstützern als supported minority, sonst caretaker. Presidential: Stimmenpluralität als Exekutive. Semi-Presidential: separate Exekutive und parlamentarisches Kabinett; Kohabitation erhält keinen automatischen Malus.

## 14. Nichtkompetitive Führung

One-Party und Authoritarian Republic bestätigen Kontinuität in fünfjährigem Review. Absolute Monarchy ohne periodischen Wechsel. Keine Fake-Wahlergebnisse, keine erfundenen 100-%-Stimmen. Führungsachsen bleiben stabile politische Identität.

## 15. Stabilitätskomponenten

Basis B; C als mandatgewichtete Economic-Abweichung in der Regierung; F = clip((1/Σshare²−1)/6); M = clip((0.5−gesicherte Unterstützung)/0.5). F/M/C werden dort verwendet, wo parlamentarische Unterstützung tatsächlich relevant ist. Makro-/Krisendruck separat, ohne Debt, Rating oder Funding.

## 16. Endgültige Stabilitätsformel

`target = clip(B−10C−6F−8M,0,100)`; monatlich nähert sich der Strukturwert mit 25 % an. `S_pol = clip(structure−dated_transition,0,100)`. Übergang: geordneter Wechsel 3, caretaker 6, sonst 0; linear datiert über 92 Tage. `P_macro = min(12,max(0,−g)×80 + max(0,u−.08)×40 + max(0,π−.04)×40)`; betroffene Krise +6, insgesamt max18. `S_display = clip(S_pol−P_macro,0,100)`. Gleichartige mechanische Inputs erzeugen unabhängig vom Regimenamen dieselbe Formelantwort.

## 17. Kadenz und Reihenfolge

Fällige Politik vor dem Makrobericht, mit zuvor veröffentlichten Inputs; danach bestehender Monatsmakrobericht und eingefrorene Politikkomponenten, anschließend Unternehmen/Produktion/Workforce. Gewöhnliche Tage prüfen nur den nächsten Termin. Krisenstart/-ende aktualisiert nur den Anzeigedruck für tatsächlich betroffene Länder; auch eine Wahl zwischen Reports erhält vorhandenen Krisendruck. Keine täglichen Parteiscans, Normalisierungen, Koalitionen oder politischen Historykopien.

## 18. Politische Ereignisse

Typisierte Aktivierung, election_result, government_formed, incumbent_confirmed, minority_government, formation_pending, leadership_review und reine Anzeigeereignisse macro_pressure_changed beim Krisenstart/-ende. IDs aus Land, Seed, Modell, Ereignissequenz, Art und Datum. Ergebnis mit Inputs und Aktien-unabhängiger Regierungsbildung. Neutrale Nachricht ohne Momentum-/Preisimpuls; Krise bleibt ein getrenntes Ereignis.

## 19. Entscheidung zum wirtschaftlichen Hook

**Deaktiviert.** Das vorhandene Coarseverfahren schreibt historische Staatsanleihequotes, Emissionen, Bondfonds-NAV und Yield Futures nicht gemeinsam entlang politischer Prämienrevisionen fort. Beim Handoff wird das aktive Bondset neu aufgebaut. Die geforderte Freigabebedingung ist damit nicht belegt; das Dokument erlaubt ausdrücklich die vollständige Politics-/UI-Auslieferung mit ausgeschaltetem Hook. Kein Ersatzkanal wurde eingebaut.

## 20. Prämienformel und Cap

Nur unbenutzter, getesteter Kandidat: `.0025 × clip((75−S_pol)/50,0,1)`, maximal 25 Basispunkte. Alle tatsächlich gespeicherten und laufenden Prämien sind 0; eingeschaltete oder von 0 abweichende Prämien werden beim Laden abgewiesen. Makro-Anzeigedruck ist kein Input.

## 21. Government-Bond-Integration

Kein laufender Spreadinput; Bondberechnung unverändert gegenüber dem Auftragsstart. Keine PD-, Rating-, Corporate-, Fiskal-, Nachfrage-, FX- oder Psychologieeinspeisung. Die Datei-Prüfsummen der maßgeblichen Preis-/Fiskal-/Accountingmodule sind unverändert.

## 22. Quote-Revisionen

Keine politischen Quote-Refreshes, keine gemischten neuen Quote-Revisionen, weil Premium aus ist. Der Politikblock hat eigene State-/Premiumrevision; die Premiumrevision bestätigt ausschließlich den Nullstand. Eine Freigabe des wirtschaftlichen Hooks benötigt weiterhin einen kohärenten Eventrefresh aller betroffenen Staatsquotes.

## 23. Globale Kurve und Yield Futures

Vorhandene Beobachtungs- und Derivatepfade unverändert. Exakte Kontrollläufe vergleichen auch diese Bücher und RNG-Zustände. Keine separate direkte Stabilitätseinspeisung. Der nicht implementierte historische Prämienverbrauch bleibt Freigabeblocker.

## 24. Emissionen und Coupons

Vorhandene Emissions- und Couponmechanik unverändert. Bestehende Coupons und Spieleranleihebücher sind Teil der exakten Kontroll-/Legacyvergleiche. Keine Neuemission oder Repricing durch Legacy-Aktivierung.

## 25. Coarse-Prämienintegration

Keine Prämienwirkung in Coarse oder Burn-in. Politikgeschichte ist kohärent fortgeschrieben, wirtschaftliche Geschichte bleibt der identische Nullhook-Kontrollpfad. Wirtschafts-/Fast-History-Hashsalts sind unverändert; Generator-/Historyversion und politische Identität sind separat versioniert.

## 26. Legacy-Verhalten

Echter versiegelter Checkpoint 8 / History 2 / Generator 3 geladen. Aktivierung 2040-01-01, S_pol 75, Nullprämie, keine Vergangenheit, nur zukünftige Termine. Wirtschaft, Spielerbücher, Coupons, Datum und Python-/NumPy-RNG exakt erhalten. Originalkonfiguration und History-ID bleiben erhalten; die ursprüngliche Historyschema-Version wird als Herkunft gespeichert. Versiegelte Quelle wurde ausschließlich kopiert und bleibt byteidentisch. Zusätzlich Metadata-only-Aktivierung im Live-Save getestet.

## 27. Persistenz und Versionierung

Vorabvalidierung der Featureversionen, Systeme, Partei-IDs/-Namen, Achsen, endlichen Shares, Summen, Regierungsreferenzen, Kalender, Vergangenheitsdaten, Ergebnisse, Übergänge und begrenzten Events vor Restore-Mutation. Checkpoint 4–9 unterstützt. Bestehender einzelner Ordered Writer und sein Journal unverändert; neue Tabellen nutzen dieselbe Transaktion. Gebündelter Identitäts-Upsert per Event-ID bzw. (Datum,Land) verhindert Verlust anderer Länder und doppelte Replayzeilen.

## 28. Historienkadenz

20 aktuelle vollständige Länderblöcke; monatlich genau 240 skalare Zeilen/Jahr; datierte Ereignisse und unveränderliche Wahlinputs. Keine täglichen Parteien-, Polling- oder Stabilityarrays. Letzte 32 Ereignisse als begrenzter State; vollständige Ereignishistorie in DuckDB. Die neue UI fragt keine versteckten Historien ab.

## 29. Population im Overview

Ein zusätzlicher kleiner Population-KPI in der vorhandenen Länder-Kopfzeile. Bestehende Karten, Typografie und Zahlenformatierung; kein Overview-Redesign.

## 30. Tab-Architektur

Genau ein fünfter Tab nach Sectors. Panel, Karten, Modelle und beide Diagramme einmal aufgebaut; aktive Updates patchen Inhalte. Executive/Cabinet im semi-präsidentiellen Fall getrennt beschriftet. Scrollbarer Inhalt hält schmale Fenster bedienbar; reservierte Diagramm-/Tabellenflächen bleiben auch in leeren Zuständen erhalten.

## 31. Wiederverwendete UI

Vorhandenes APP_STYLESHEET, KpiCard, DetailValue, SectionTitle, Muted, EmptyState, QTableView, SimpleTableModel und Table-Performance-Konfiguration. Unveränderte vorhandene vier Detailtabs als Referenz vor/nachher aufgenommen. Keine neue Navigation, Palette oder Chartbibliothek.

## 32. Workforce-Donut

Genau Basic, Skilled, Highly Qualified als Supply Mix. Tabelle nennt Prozent, Supply, Demand und Coverage; Einheiten workforce equivalents. Keine Arbeitslosen- oder Demand-Slices. Stabile Farben, Hovertext und zugängliche Textalternative. Wachstum vor erstem beobachteten Intervall ehrlich Not yet observed, danach annualisiert mit Intervalltooltip.

## 33. Politischer Donut

Nur nach tatsächlich ausgeführter kompetitiver Wahl: 2–7 reale Stimmenanteile, stabile Parteifarben, Namen, Regierungsmarker, Datum und Wahlauswertungstyp. Zuvor Initial mandate allocation – no election recorded mit Mandatsliste und sichtbarem Leerzustand. Kein Others-Bucket, kein erfundener Wahlkreis.

## 34. Nichtkompetitive Darstellung

Führung/Kontinuität statt Wahlgrafik. One-Party nennt Partei, Ideologie und Review mit No vote recorded. Absolute Monarchy und Authoritarian Republic zeigen Führungshinweise ohne Fake-Parteien. Reservierte Flächen wechseln zwischen bestehenden EmptyState-Karten und Diagramm/Tabelle.

## 35. On-demand-Vertrag

`{view:"macro",selection:{region,area:"society_politics"}}`: ein Land mit wiederverwendetem population_society und kleinem Politikblock. Breite Snapshots entfernen Politik explizit; keine 20-Länder-Parteiarrays oder neuen Root-Skalare. Länder-/Tabwechsel setzen Scope, spätes Ergebnis eines alten Scope wird abgewiesen. Sichtbare lokale/Worker-Ansicht zeigt Wahlereignisse zwischen Monatsberichten; versteckte Tabs erhalten keine Pieupdates.

## 36. Gemessene Payload

Ausgewählter Makroblock 3,038 Bytes; serialisierte GameState-Payload des ausgewählten Workerscope 3,506 Bytes, ohne History. Nach Established 5 Jahren 3,568 Bytes. Alle 20 Länder einer echten heterogenen Startwelt einzeln projiziert: maximal 3,227 Bytes, einschließlich sieben Parteien. Welt-/Spieler-/RNG-Zustand nach Projektion und Navigation exakt unverändert. Projektion Median 1.798 ms / p95 2.870 ms. Ziel ~5 KB eingehalten.

## 37. Aufnahmen und Sichtprüfung

Alle neun verlangten Szenarien sowie die vier vorhandenen Tabs und ergänzende untere Scrollpositionen im vollständigen Produktionsfenster erfasst. Vorher-Aufnahmen unter readable-before-shell-closed; nachher unter readable-after-shell-closed. Ein reiner Offscreen-Artefakt der separaten Detail-Widget-Aufnahmen wurde durch Aufnahme im tatsächlichen App-Fenster beseitigt. Vergleich bei 1400×1200; schmal 1080×720, groß 1920×1400. Offscreen lädt dieselben Windows-Segoe-UI-Schriften explizit. Initiale Mandate, sieben Parteien, Presidential, Semi-Cohabitation, drei nichtkompetitive Fälle, kleine/große Fenster manuell auf Abstände, Schrift, Farben, Tabellen, Leerzustände und Scrollzugänglichkeit geprüft. Galerie: `politics-v1-ui-captures-2026-10-07.md`. Die Regimeaufnahmen sind gezielte Simulator-/Regierungsfixtures; sie behaupten keine nicht simulierte Weltgeschichte.

## 38. Gewöhnliche Tage

| Kennzahl | Vorher | Nachher |
|---|---:|---:|
| Median | 158.09 ms | 161.30 ms |
| p95 | 222.82 ms | 204.33 ms |
| Maximum einschließlich Startaufbau | 2722.83 ms | 2695.31 ms |

Isolierte 90-Tage-Kontrolle mit Seed 1729 und gleicher Wirtschaftsversion, Writer aktiv; nachher eine zusätzliche Wahl. Maximum enthält den vorhandenen Start-/Journalaufbau. CPU-Median vorher 156.25 ms, nachher 156.25 ms. Kein Hinweis auf eine materielle gewöhnliche Tagesregression; Differenzen nicht als Politik-Beschleunigung ausgelegt.

## 39. Berichte, Wahlen und UI

Berichtstag-Median vorher 283.44 ms, nachher 292.86 ms. Politikphase monatlich Median 0.263 ms, max 0.325 ms. Wahlphase 0.403 ms; vollständiger Wahltag 136.44 ms (ein Eventtag). Koalitionssuche Median 0.037 ms. UI-Patchmessung in `readable-after-shell-closed/patch-cost.json`; keine Animation/Timer. Government-Quote-Refresh entfällt wegen ausgeschaltetem Hook.

## 40. Established-Generierung

| Jahre | Coarse vorher / nachher | 365 Tage vorher / nachher | Politik-Monatszeilen | Events |
|---|---:|---:|---:|---:|
| 5 | 7.84 / 7.44 s | 112.36 / 123.71 s | 1,200 | 63 |
| 20 | 26.24 / 24.19 s | 124.60 / 124.40 s | 4,800 | 182 |
| 50 | 30.59 / 31.02 s | 123.75 / 119.61 s | 12,000 | 502 |

Alle Kontrollen wirtschaftlich und im RNG exakt identisch, sowohl direkt nach Coarse als auch nach Burn-in. Diese langen Laufzeiten entstanden neben der vollständigen Testsuite und teilweise Save-/Legacy-Prüfungen; Host-/Writerkonkurrenz beeinflusst Wall/CPU und Startmaxima. Sie sind Vollständigkeits-/Kostenmessungen, keine isolierte kleine Prozent-Regressionsmessung. Die isolierte Tagesmessung steht in Punkt 38. 5/20 sind gezielte Kern-Generatorproben; die vorhandene Produktauswahl 50/75/100 Jahre wurde nicht erweitert.

## 41. Speicher und Writer

90-Tage-Prozess-Peak vorher 980.1 MiB, nachher 981.6 MiB. Gemessene Queue-Tiefe 1, bestehende Queue-Kapazität 3; gleiche zwei Journalslots und Backpressure. Langlauf maximal zwei wartende Batches; bestehende historische Kompaktion/Writerwartezeiten sind auch in der unveränderten Referenz vorhanden. Nach 50 Jahren umfassen alle 20 Current-JSONblöcke zusammen 269,515 Bytes. Lange Probe-Peaks stehen in den Result-JSONs; vollständige Kontroll-Serialisierung beeinflusst sie stark. Politikdaten sind begrenzte Current-Blöcke plus sparse Facts; kein zweiter Writer. Neue sparse Upserts löschen alle betroffenen Identitäten gebündelt. Kanonische interne Datumswerte und korrekt escapte Textschlüssel vermeiden den gemessenen DuckDB-Konvertierungsaufwand großer Python-Listen; danach unveränderte transaktionale COPY-Persistenz. 2.400 Monatszeilen werden wiederholt exakt geprüft, einschließlich fremder Länder, Apostrophen, JSON und DOUBLE-Werten.

## 42. Testsuite

**Alle 732 Testfälle erfolgreich verifiziert**, mit getrennten, unveränderten XML-Nachweisen. Vollständiger Lauf: 732 Fälle, 731 bestanden, eine veraltete Erwartung von vier Detailtabs, Dauer 2087.72 s. Der Auftrag verlangt ausdrücklich den fünften Tab. Diese Erwartung wurde auf genau fünf Tabs angepasst und zusätzlich um die exakten Namen und die Reihenfolge aller fünf Tabs verschärft. Danach bestehen alle 12 Tests des betroffenen Workspace-Moduls. Die Testidentitäten werden gegen den Vollsuite-Lauf abgeglichen: jeder ursprüngliche Fall hat einen erfolgreichen Nachweis. Es gab keinen zweiten vollständigen Lauf; Produktionscode und alle anderen Tests sind gegenüber dem vollständigen Lauf per SHA-256 unverändert. Abschließende Politics-/UI-/Workerprüfung: **97 bestanden**, einschließlich echtem Worker-Scopefall. Zusätzlicher UI-Prozesslauf 3 bestanden. Keine Toleranzen erweitert und keine Tests deaktiviert. Ruff für alle neuen Dateien bestanden. Der vorhandene UP017-Hinweis im bestehenden Workspace-Test ist unverändert geblieben. XML-Evidence in `.cache/politics-implementation`.

## 43. Save/Load und Crash-Recovery

Save/Load vor/nach Wahl sowie gleichzeitigem Monatsbericht und laufendem Regierungsübergang reproduziert den Featurestate exakt. Aktueller JSONblock und historische DOUBLE-Werte werden ohne Rundungsabweichung verglichen. Fehlerhafte Featurepayloads werden vor Buchmutation abgewiesen. Vier reale Windows-Prozessabbrüche: vor Transaktion, vor Commit, nach Commit, nach Acknowledge; zweimaliges Wiederöffnen/replay bleibt genau einmal. Alte veränderte Testbundle-Datei wurde korrekt per Prüfsumme abgewiesen; unveränderter versiegelter Referenzbundle besteht den eigentlichen Legacytest. Durability nicht gelockert.

## 44. Multi-Seed-Verteilungen und Korrelationen

200 Seeds ×20 Länder = 4,000 Roots. Systeme: Parliamentary Democracy 573, Absolute Monarchy 573, One-Party State 553, Presidential Democracy 571, Authoritarian Republic 579, Semi-Presidential Democracy 592, Constitutional Monarchy 559. Maximaler absoluter Pearsonwert über Systemindikatoren/Parteienzahl/Basis/Stability/Achsen gegen Population, GDP-pro-Kopf-Proxy, Birth/Death und Qualified-Share: 0.0369. Kein auffälliger systematischer Wealth-/Demografie-/Workforcezusammenhang. Eine Stichprobe beweist keine perfekte statistische Unabhängigkeit; die getrennten Domainstreams sichern den strukturellen Ausschluss.

## 45. Langfristiges Verhalten

Alle sieben Systeme über 50 politische Kalenderjahre in Featuretests: genau 600 Berichte pro Land, keine Terminauslassungen, kompetitive tatsächliche Wahlergebnisse und nichtkompetitive Reviews ohne Fake-Wahlen. Stabilität bleibt endlich und begrenzt; Premium 0. Zusätzlich komplette Welt-Coarse-/365-Tage-Läufe für 5/20/50 Jahre mit dauerhaft gespeicherten Wahl- und Regierungsereignissen sowie sparsamen Krisen-Anzeigeereignissen. Der langfristige politische Pfad beeinflusst die Kontrollwirtschaft nicht.

## 46. Verbleibende Grenzen

Bondprämie absichtlich aus; ihre Freigabe verlangt historische Quote-/Kurven-/Fonds-/Derivateintegration und gemeinsame Revisionsprüfungen. Mandate sind die dokumentierte V1-Unterstützungsabstraktion, keine Sitze/Turnout. Reviews bestätigen Kontinuität ohne Dynastien/Coups. Stabilität ist ein kalibrierter Spielindikator. Coarse-Wahlinputs sind interpolierte Monatsproxies mit Provenienz. Keine Regimewechsel, Politiker, Umfragen, FDI, neuen Fiskalpfade oder politische Chart-History-UI.

## 47. Urteil

Politics V1 schafft datierte politische Länderidentität, tatsächliche Wahlergebnisse, nachvollziehbare Regierungen und getrennte sichtbare Stabilität. Exakte wirtschaftliche Nullhook-Kontrollen und erhaltenes Accounting verhindern eine neue wirtschaftliche Rückkopplung. Der aktive Scope bleibt klein, gewöhnliche Tage bleiben am Datumsgate, Persistenz nutzt die bestehende sichere Pipeline. Die fünfte Ansicht verwendet sichtbar Kojak Streets vorhandene Gestaltung. Freigegeben: Politics, sparse History und Society & Politics. Nicht freigegeben: wirtschaftlicher Bondhook.
