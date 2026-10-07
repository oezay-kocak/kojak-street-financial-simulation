# Heterogeneous Start World – Implementierung und Prüfung

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Stand: 07.10.2026. Auftrag nach ausdrücklicher Freigabe umgesetzt. Referenz: aktueller Produktionsstand vor diesem Auftrag.

Der dritte Startmodus ist im normalen Spielstart verfügbar. Er erhält exakt 400 Mio. Bevölkerung, 100.000 GDP-Einheiten und 1,28 Billionen Aktienkapitalisierung bei 20 Ländern und 1.280 Unternehmen. Genesis und Established bestehen die exakten Referenzvergleiche.

## 1. Geänderte Dateien

Acht Produktionsdateien wurden gegenüber dem unmittelbar vor diesem Auftrag eingefrorenen, bereits veränderten Arbeitsstand ergänzt oder geändert:

- `daten.py`
- `src/kojakstreet/adapters/legacy_runtime.py`
- `src/kojakstreet/core/checkpoints.py`
- `src/kojakstreet/core/companies.py`
- `src/kojakstreet/core/established_world.py`
- `src/kojakstreet/ui_qt/app.py`
- `src/kojakstreet/ui_qt/new_simulation.py`
- `src/kojakstreet/core/heterogeneous_start.py`

Dazu kommen `tests/test_heterogeneous_start.py` (27 neue Tests) und die vier Nachweiswerkzeuge `heterogeneous_validation.py`, `heterogeneous_closeout.py`, `heterogeneous_runtime_cost.py`, `heterogeneous_report.py`. Der frühere Genesis-Auditbericht und sein Erzeugungswerkzeug erhielten ausschließlich die sachliche Korrektur zum Berichtstag 15. Bestehende Änderungen aus früheren Aufträgen bleiben erhalten.

Die eingefrorenen Fingerprints bestätigen: Tagesengine, Preisberechnung, Produktion, Player Accounting, Live-Prozess, DuckDB und Journal-Writer wurden in diesem Auftrag nicht verändert.

## 2. Architektur des neuen Modus

`WorldMode.HETEROGENEOUS` startet am 01.01.1990 ohne einen einzigen vorgeschalteten Simulationstag. Ein einmaliger Generator erstellt Bevölkerung, GDP und Börsenkapitalisierung als Roots. Ein vorübergehender `ContextVar` übergibt sie ausschließlich während des initialen `daten`-Ladevorgangs; `finally` setzt ihn auch im Fehlerfall zurück. Danach verwenden alle Modi dieselben bestehenden Engines.

Der Generator erzeugt keine dauerhaften Größenklassen, Produktivitätsmechanik oder zusätzliche Tageszustände. `daten._initial_roots` wird nach dem Bootstrap entfernt. Im Tagespfad gibt es keinen Heterogeneous-Neuberechnungszweig.

## 3. UI-Integration

Der normale New-Simulation-Dialog bietet drei gleich gestaltete Karten: Genesis, Heterogeneous, Established. Genesis bleibt voreingestellt. Heterogeneous zeigt ausdrücklich „No prehistory (Day 1)“; 50/75/100 Jahre sind weiterhin ausschließlich für Established verfügbar. Eine zuvor gewählte Established-Dauer bleibt bei zwischenzeitlicher Heterogeneous-Auswahl erhalten.

Der Qt-Einstieg reicht die Konfiguration an den normalen Runtime-Konstruktor weiter. Established verwendet seinen bisherigen Erzeugungsdialog und Bundle-Pfad. Der tatsächliche Qt-Dialog wurde gerendert und visuell geprüft; Nachweis: `.cache/heterogeneous-start/selector-final.png`.

## 4. Save- und Persistenzrepräsentation

Heterogeneous verwendet das bereits vorhandene Checkpoint-Feld `world_generation`; Save-Version 7 und DuckDB-Schema bleiben gleich. Gespeichert werden Modus, Seed, null Vorgeschichte, Modell-/Historien-/Generatorversion, `heterogeneous_initialization_version=1` und optionaler Weltname.

Diese Identität enthält keine bei jeder Erzeugung neue Uhrzeit oder UUID. Deshalb reproduziert dieselbe Konfiguration sogar den vollständigen gespeicherten Startzustand. Restore prüft neue Modusidentitäten vor einer Mutation der laufenden Welt. Eine unbekannte Initialisierungsversion wird abgewiesen; der vorherige Zustand bleibt exakt erhalten. Genesis- und Established-Metadaten werden nicht umgeschrieben.

## 5. RNG- und Seeding-Design

Fünf lokale Python-Random-Streams werden aus SHA-256 von Initialisierungsversion, Seed und Zweck abgeleitet: Bevölkerung, Produktivität, Länderbörsen, Unternehmensgrößen und Sektorplatzierung. Sie konsumieren weder den globalen Python- noch den NumPy-Zufallszustand.

Die bisherige Draw-Reihenfolge in Company-Erzeugung bleibt bestehen: Auch die bisherige EPS-Ziehung wird konsumiert, bevor im neuen Modus EPS konsistent abgeleitet wird. Alte Modi nehmen denselben bisherigen Pfad; der neue Generator wird dort nie ausgeführt.

## 6. Bevölkerungsalgorithmus

Die 20 Länder erhalten feste Größenklassen mit seedabhängigen Rohwerten innerhalb ihrer Intervalle. Eine begrenzte Budgetprojektion sucht einen gemeinsamen Skalierungsfaktor, respektiert Unter-/Obergrenzen und verteilt Restpersonen anhand der Nachkommarestwerte einzeln. Die Summe ist exakt 400.000.000.

Die Werte werden absteigend sortiert und die Ländernamen seeded gemischt. Monoton geordnete Intervallgrenzen erhalten die Klassen auch nach der Sortierung; überlappende Bänder führen nicht zu vertauschten Größenklassen.

## 7. Endgültige Bevölkerungsbereiche

Keine Bandkalibrierung erforderlich.

| Klasse | Länder | Inklusive Bevölkerung |
|---|---:|---:|
| Very large | 2 | 35–50 Mio. |
| Large | 4 | 24–35 Mio. |
| Medium | 7 | 15–25 Mio. |
| Small | 5 | 8–17 Mio. |
| Very small | 2 | 5–10 Mio. |

Die Budgetprojektion kann Werte an zulässige Grenzen setzen. Alle Klassen, ihre Reihenfolge und die exakte Summe sind geprüft.

## 8. GDP-/Produktivitätsalgorithmus

Jedes Land erhält einen initialen Faktor zwischen 0,70 und 1,40. GDP-Gewicht ist Bevölkerung × Faktor; die bestehenden 100.000 GDP-Einheiten werden proportional aufgeteilt. Die Projektion arbeitet in Millionstel-Einheiten, anschließend konserviert ein repräsentationsbezogener Restwert auch die normale Float-Summe des bestehenden Codes exakt.

Produktivität ist ausschließlich Generatorinformation. GDP wird vor Fiskalwerten, Erwartungen, Fonds, Anleihen und Produktionsbootstrap gesetzt; deren Werte folgen aus dem vorhandenen Modell statt aus unabhängigen Ziehungen.

## 9. GDP-Konzentrationswächter

Der Generator akzeptiert nur Produktivitätsziehungen mit mindestens 1% GDP pro Land, 10–20% für das stärkste Land und Bevölkerung/GDP-Korrelation zwischen 0,60 und 0,90. Der Mindestwert erhält die bestehende monatliche GDP-Untergrenze von 1.000 und verhindert einen späteren Floor-Rücksprung kleiner Länder.

Nach spätestens 256 Versuchen wird eine nicht erfüllbare Konfiguration ausdrücklich abgewiesen. Es gibt keinen unbeschränkten Retry und keine stille Guard-Abschwächung. Die 100 geprüften Seeds wurden akzeptiert. Inflation, Arbeitslosigkeit, Leitzinsen und Ratings werden nicht frei neu randomisiert.

## 10. Algorithmus für Unternehmenskapitalisierung

Zuerst werden die festgelegten Klassen in ihren Mindestgrößen erzeugt. Die verbleibende globale Kapitalisierung wird anhand seedabhängig gewichteter Klassen-Headrooms verteilt. Große Unternehmen werden nach verbleibendem Länderziel auf 20 Buckets verteilt; jeder hat 64 Slots, maximal zwei Mega Caps.

Länderziele werden bei Bedarf in die durch ihre Klassen tatsächlich möglichen Intervalle projiziert. Anschließend werden 64 Einzelwerte je Land begrenzt normalisiert und auf 16 × 4 Sektorslots gesetzt. Statische Schwerpunktsektoren bevorzugen größere Slots; kurzfristige Bonusintensitäten beeinflussen die strukturelle Größe nicht.

## 11. Mathematische Vereinbarkeit der Klassen

Für die gewählten 1.280 Klassenpositionen ergeben sich:

- Summe aller Untergrenzen: **1.182.440.000.000**.
- Summe aller Obergrenzen: **3.040.400.000.000**.
- Ziel: **1.280.000.000.000**, innerhalb des zulässigen Intervalls.
- Summe bei gleichförmigen Klassen-Mittelwerten: **2.111.420.000.000**, deutlich oberhalb des Ziels.

Damit sind Anteile, Bänder und Budget gemeinsam möglich. Eine gleichförmige Belegung der gesamten Bänder wäre jedoch ungeeignet. Die Rechnung wurde vor der Umsetzung der Größenverteilung durchgeführt.

## 12. Kalibrierung für exakt 1,28 Billionen

Das Weltbudget und sämtliche vorgeschlagenen absoluten Bänder bleiben unverändert. Die notwendige Kalibrierung betrifft ausschließlich die Verteilungsgewichte: Nur **97.560.000.000** Headroom oberhalb der Klassenminima werden verteilt. Daher liegen die beobachteten Größen überwiegend im unteren Teil der erlaubten Bänder.

Es wird ausdrücklich keine gleichförmige Verteilung und kein typischer 18-Milliarden-Riese versprochen. Für alle 100 geprüften Seeds konnte zusätzlich jedes gewünschte Länderbörsenbudget exakt erreicht werden: beobachtete Länderzielkalibrierung 0%. Bei anderen Seeds behält eine erforderliche Projektion Klassenbänder und globale Summe bei.

## 13. Endgültige Klassenanzahlen und Bänder

Die Anzahlen liegen innerhalb sämtlicher beauftragter Anteilsintervalle. Klassennamen sind Erzeugungsinformationen; der Tageszustand benötigt sie nicht.

| Klasse | Anzahl | Anteil | Marktkapitalisierung in Mrd. |
|---|---:|---:|---:|
| Mega Cap | 19 | 1.484375% | 8–18 |
| Large Cap | 128 | 10.000000% | 3–8 |
| Upper Mid | 256 | 20.000000% | 1,3–3 |
| Mid Cap | 384 | 30.000000% | 0,6–1,5 |
| Small Cap | 365 | 28.515625% | 0,2–0,8 |
| Micro Cap | 128 | 10.000000% | 0,08–0,30 |

Summe: 1.280 Unternehmen. Globaler Mittelwert: exakt eine Milliarde; dieser Mittelwert erzwingt keine gleichen Unternehmen.

## 14. Gewichtung der Länderbörsen

Das gewünschte Ländergewicht ist exakt 65% normalisierter GDP-Anteil + 20% normalisierte Struktur + 15% normalisierte Seedvariation. Struktur nutzt die vier bereits vorhandenen statischen Schwerpunktsektoren und deren Verhältnis FCF-Marge/Price-to-Sales. Seedvariation wird zwischen 0,60 und 1,50 gezogen.

Ein Länderziel ist höchstens 20% des Weltbörsenwerts. GDP und Börsenwert sind nicht identisch oder proportional; die Korrelation bleibt angesichts der 65%-Gewichtung allerdings hoch. Über 2.000 Länderbeobachtungen variiert Börsenwert/GDP zwischen rund 9,42 und 33,65 Mio. bestehenden Einheiten. Mega Caps können sich nicht in einem einzigen Land sammeln.

## 15. Bestehender Derived-/Bootstrap-Pfad

Company-Cap-Roots werden im vorhandenen `spawn_company` gesetzt. Aktienanzahl folgt aus Cap/Kurs; Umsatz, FCF, Cash, Debt, Rating, Spezialisierung, Kapazität und Input-/Output-Pläne verwenden bestehende Ableitungen und Ziehungen. Für Heterogeneous folgt EPS konsistent aus `max(0.1, FCF/shares)`, einschließlich previous EPS.

Die erste Namens-/Tickerzuordnung läuft vor nachgelagerten Büchern. Nur bei der anschließenden Heterogeneous-Initialisierung wird eine erneute Tickerkompaktierung übersprungen, damit bestehende Fonds-/Bond-/Derivatverweise dieselben Unternehmen behalten. Genesis behält seinen bisherigen Ablauf exakt.

Zum Schluss werden globale Aggregate und beobachtete Gov-Yields aus den fertigen Büchern abgeleitet und Derivate einmal mit der vorhandenen Preisformel bewertet. Die Zentralbankbilanzsumme beträgt dadurch konsistente 20.000 und Net Liquidity 108.000; es wird weder ein Tag simuliert noch Prehistory erzeugt.

## 16. Ressourcen und Produktion

Ressourcen, 90 Produkte/Services, Spezialisierungen, Country-Fokus, rotierende Boni und beide bisherigen Initialisierungs-Bootstraps bleiben im bestehenden Modell. Heterogene Unternehmens-Roots erzeugen ihre Kapazitäten über denselben Pfad.

20 vollständige Starts erfüllen positive Supply/Demand, nichtnegative Bestände und die vorhandenen Versorgungskorridore. Die neue Prüfroutine berücksichtigt ausschließlich bis zu vier Float-ULPs an bereits geglätteten Korridorgrenzen; exakte Budgets und bestehende Testtoleranzen bleiben unverändert.

NEWC, UX und TEXT haben weiterhin keinen expliziten Unternehmensproduzenten. Ihre Versorgung stammt aus dem vorhandenen Fallback. Das ist eine Grenze des bestehenden Modells, keine neu behauptete vollständige physische Produktionsabdeckung.

## 17. Tag 1 → Tag 2

Für Seed 1729 ergibt der echte erste Tageswechsel:

| Größe | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Aktienkurs | -1.2394% | 0.2646% | 1.6891% |
| Indexkurs | -1.0821% | 0.0255% | 1.0462% |
| Fondskurs | -1.9754% | 0.0347% | 3.6559% |
| Umsatz | 0.0000% | 0.0000% | 0.0000% |
| EPS | 0.0000% | 0.0000% | 0.0000% |
| Produktionskapazität | 0.2816% | 0.2816% | 0.2816% |
| Rohstoffversorgung | 0.0000% | 1.8700% | 1.8700% |
| Produkt-/Serviceversorgung | 0.0000% | 1.8700% | 1.8700% |

GDP und Aktienanzahl bleiben exakt erhalten; Bond-Yields ändern sich am ersten Tag nicht. Net Liquidity verändert sich von 108.000 auf 107994.986111, ohne den bisherigen aggregativen Startkorrektursprung. GLI bewegt sich von 15420.000000 auf 15419.332720. Die Kapazitätsänderung und die maximal 1,87% Versorgungsänderung stammen aus den unveränderten täglichen Wachstums-/Glättungsregeln.

Auch Derivate werden bereits an Tag 1 mit ihrer tatsächlichen Formel bewertet. Das stärkste Optionsplus ist 71,55% beim Uran-Put OUXP1001 (3,12895 → 5,36768): 1,56013 neuer intrinsischer Wert plus 3,80755 Zeitwert. Der zugrunde liegende Uranpreis bewegt sich um −1,56013%; dies ist die bestehende Optionssensitivität, kein Reset von einem falschen Startkurs.

EMA/Momentum starten über den bestehenden neutralen, leeren Kurshistorienpfad. Drei Runtime-Seeds prüfen zusätzlich den ersten wirklichen Monatsbericht am **15.01.1990**: GDP folgt exakt der bisherigen Monatsformel, previous Fundamentals referenzieren echte vorherige Werte. Der frühere Audittext zum vermeintlichen Monatsbericht am 01.01. wurde sachlich korrigiert.

## 18. Indexregression

Alle 20 Länder besitzen ihren breiten Index und 16 Sektorindizes: insgesamt 340 sichtbare Index-Quotes. Jeder breite Index referenziert exakt die 64 tatsächlichen Aktien seines Landes; Marktkapitalisierung und Werte werden aus diesen Mitgliedern abgeleitet.

Die vorhandenen Typ-/Symbol-/Mitgliederreparaturen wurden nicht erneut verändert. Tests decken neue Größenverteilungen, Tag 2, aktuelle Live-Markets nach verborgenem Fortschritt und Save/Load ab. Am Jahresende bleiben 340 Indizes erhalten.

## 19. Exakte Genesis-Regression

Referenz ist der vor diesem Auftrag eingefrorene Produktionsstand einschließlich der bereits abgeschlossenen Indexreparatur. Für Seeds 7, 42 und 2307 wurden jeweils 31 echte Tage vor/nach dem Eingriff verglichen.

Vollständige offizielle Checkpoints an Tag 1 und Tag 2, spätere Checkpoint-/RNG-Signaturen und wirtschaftliche Inhalte sämtlicher DuckDB-Tabellen stimmen exakt überein. Keine Wirtschafts-, Float-, RNG- oder Historienfelder wurden aus dem Checkpointvergleich entfernt.

Beim Tabellenvergleich sind ausschließlich die unabhängig vergebene `history_id` und diagnostische Phasenlaufzeiten ausgenommen. Dies ist logische Zeilenidentität, keine Behauptung identischer DuckDB-Dateibytes. Nachweis: `.cache/heterogeneous-start/genesis-equivalence.json`.

## 20. Established-Regression

Beide vorhandenen Generatorpfade wurden mit Seed 7 gegen die eingefrorene Referenz geprüft: 31 tatsächliche Daily-Diagnosetage sowie die vorhandene 50-Jahre-Hybridstrategie `fast_history_v2` mit 270 Coarse-Buckets und anschließend zwei Daily-Burn-in-Tagen.

Welt, vollständiger RNG und logische Tabelleninhalte sind exakt gleich. Aus Checkpoint-Metadaten wurden ausschließlich unabhängig erzeugte `world_id` und `created_at` entfernt; bei Tabellen gelten dieselben History-ID-/Timing-Ausnahmen wie oben. Der Vergleich behauptet weder 50 Jahre tägliche Simulation noch einen hier neu gemessenen standardmäßigen 365-Tage-Burn-in. Produktionsgenerator, Historienstrategie und deren Versionsnummern bleiben unverändert.

## 21. Determinismus desselben Seeds

Zwei unabhängige Heterogeneous-Runtimes für Seed 1729 reproduzieren die vollständigen offiziellen Tag-1- und Tag-2-Checkpoints exakt, einschließlich aller Python-/NumPy-RNG-Werte und der gespeicherten Konfiguration; keinerlei Ausschlüsse.

Zusätzlich prüft die Testsuite für 20 Seeds die identischen Root-Ergebnisse wiederholter Erzeugung und die Nichtveränderung globaler RNG-Zustände durch den Root-Generator. Nachweis: `.cache/heterogeneous-start/established-and-determinism.json`.

## 22. Variation zwischen Seeds

Population, GDP, Länderbörsen und Unternehmensplatzierungen unterscheiden sich bei den separat geprüften sechs Test-Seeds. In der 100-Seed-Auswertung sind alle 100 vollständigen Bevölkerungsrangfolgen und alle 100 GDP-Rangfolgen unterschiedlich.

Die Anzahl und Bänder der Klassen bleiben absichtlich konstant. Es handelt sich um kontrollierte wirtschaftliche Größendiversität; tiefere zufällige Inflation-/Rating-/Zinsregime wurden nicht eingeführt.

## 23. Statistiken für mehr als 20 Seeds

100 Root-Generator-Seeds (0–99) und 20 vollständige Runtime-Welten (0–19), jeweils mit anschließendem ersten Tageswechsel:

| Weltkennzahl | Minimum über Seeds | Median über Seeds | Maximum über Seeds |
|---|---:|---:|---:|
| Größter GDP-Anteil | 10.0559% | 11.7159% | 15.7863% |
| Größter Länderbörsenanteil | 7.8984% | 9.4783% | 12.2344% |
| Korrelation Bevölkerung/GDP | 0.8291 | 0.8870 | 0.9000 |
| Korrelation GDP/Börsenwert | 0.9737 | 0.9887 | 0.9960 |

| Unternehmenskonzentration | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Top 1 | 0.6975% | 0.7111% | 0.7217% |
| Top 10 | 6.7590% | 6.8764% | 6.9831% |
| Top 50 | 20.9655% | 21.1229% | 21.3558% |

Bevölkerung: beobachtete Hülle 5,000,000 bis 48,797,447; Median der Ländermediane 18528565. GDP: 1007.693619 bis 15786.294481; Median der Mediane 4552.251531. Company-Cap: 80000000 bis 9238208660; Median der Mediane 636077431.

Alle einzelnen Länder-, Produktivitäts-, GDP-pro-Kopf-, Länderbörsen-, Klassen- und Sektorwerte stehen in `.cache/heterogeneous-start/plausibility-v2/root-statistics.json`; vollständige Produktions-/Indexresultate in `world-statistics.json`.

## 24. Ausreißer und Guards

Keine der 100 Root-Konfigurationen und 20 vollständigen Welten wird als ungültig markiert. Alle exakten Weltbudgets, Klassenanzahlen, Ländergrößenbänder, Unternehmensbänder, 64 × 20 Unternehmensslots und 4 × 16 Sektorslots je Land sind erhalten.

Kein Land überschreitet die Konzentrationsgrenze; höchster beobachteter Sektoranteil am Weltbörsenwert: 10.0776%. Kein Unternehmen dominiert die Weltbörse; Mega-Cap-Platzierung ist auf zwei pro Land begrenzt. Infeasible Budget und falsche Universumsgröße werden ausdrücklich getestet und abgewiesen. Guards laufen einmalig bei der Initialisierung.

## 25. 365-Tage-Ergebnis

Seed 1729 durchläuft 365 tatsächliche DailySimulation-Schritte vom 01.01. bis zum verarbeiteten 31.12.1990; danach ist das Live-Datum 01.01.1991. Alle 365 Termine sind lückenlos; zwölf Monatsberichte wurden persistiert.

Jahresende: 20 Länder, 1.280 Aktien, 340 Indizes, 34 Rohstoffe, 90 Produkte/Services, 32 Kryptos, 271 Fonds, 566 Derivate. Alle aktuellen numerischen DB-Felder sind endlich; Supply/Demand bleiben positiv, Bestände nichtnegativ; keine ungültigen Fonds-Aktienreferenzen.

Bevölkerung 400786147.373593, GDP 101195.169533, Börsenkapitalisierung 1541959421679.723633. Die **Start**budgets werden im folgenden Spiel nicht künstlich festgehalten; Wirtschaft und Preise dürfen regulär wachsen. Der inaktive Kleinanleger behält 25.000 Cash und Net Worth ohne Positionen. Vollständige Checkpointhashes liegen für Schritte 1, 31, 181 und 365 vor.

## 26. Save/Load und Pause/Resume

Unmittelbar an Tag 1 reproduziert Save/Load den vollständigen offiziellen Welt-/Spieler-/Historien-/Python-/NumPy-Zustand exakt. Der nächste Tageswechsel nach Load ist ebenfalls exakt gleich. Pause/Resume verändert ausschließlich den erwarteten Pausenstatus.

Der echte Live-Worker testet zusätzlich Save/Load nach Fortschritt und Spielertrade: wirtschaftliche Signatur einschließlich RNG, Indizes und Spielerportfolio stimmen exakt überein. Aktien werden gegen die tatsächliche gespeicherte Darstellung vollständig verglichen. Bestehende zweipunktige Retention bestimmter Anzeige-Input-/Output-Historien im Save wird respektiert; dies ist keine neu eingeführte Verkürzung der vollständigen Rechenkurshistorien oder DuckDB-Zeilen.

Alle neun Views werden im tatsächlichen Qt-/Live-Prozess besucht. Ein normaler Aktienkauf verändert das Spielerportfolio, während Weltaktien und Makro unverändert bleiben. Die bestehenden PnL-, Margin-, Settlement- und Writer-Tests laufen als Teil der vollständigen Suite.

## 27. DB, Checkpoints und Historien

Heterogeneous startet mit leeren handelbaren Kurshistorien. Nur die schon benötigten technischen Bootstrap-Punkte tragen das aktuelle Startdatum; es existiert kein erfundener wirtschaftlicher Verlauf vor 1990.

Der Jahreslauf persistiert 31 Tabellen, darunter 920.895 Asset-Daily-Zeilen und 45.260 Produkt-Daily-Zeilen. Asset-Historientermine beginnen am 01.01.1990 und enthalten exakt 365 verarbeitete Tage. Alle 13 Writer-Sequenzen wurden committed; Queue-Tiefe höchstens zwei.

Journal, Flush-Schwellen, Crash-Recovery, Backpressure, Transaktionen und Durability-Regeln wurden nicht verändert. Die kontinuierliche Messschleife ist schneller als der normale UI-Takt: deshalb entstehen kumuliert 28.775 s Backpressure (Genesis 26.342 s), mit einzelnen vorhandenen Writer-Compaction-Spitzen bis 45.744 s. Dies wird offen ausgewiesen; es wurden keine Zeilen, Prüfungen oder Durability-Verpflichtungen zur Performanceverbesserung entfernt.

## 28. Vollständige Tests

**507 bestanden, null Fehler, null Fehlschläge, null ausgelassene Tests**, Laufzeit 1524.54 s. Vorherige Suite: 480; hinzugekommen: 27 Heterogeneous-Tests. Bestehende Tests und deren Toleranzen wurden nicht abgeschwächt oder deaktiviert.

Abdeckung: Root-Budgets/Klassen/Guards, lokale RNG-Isolation, Variation, drei echte Start-/Monatsübergänge, vollständiger unmittelbarer Save/Load, Pause, Versionsablehnung ohne Mutation, alle neun Live-Views, 340 Live-Indizes, Retail-Trade sowie gesamte bestehende Regression einschließlich Player Accounting und Persistenz.

Nach der abschließenden expliziten Länderobergrenze im Initialisierungsprojektor wurden zusätzlich 100 Roots exakt gegen die aufgezeichneten Bevölkerung-/GDP-/Länderbörsenwerte geprüft und alle 30 Heterogeneous-/Selector-Tests erneut bestanden. Diese Konzentrationsabsicherung verändert keinen der gemessenen Seedzustände; Nachweis: `post-guard-gate.xml`.

Nachweis: `.cache/heterogeneous-start/full-suite.xml` und `full-suite.log`. Ruff-Prüfung der neuen Dateien und geänderten Produktionsdateien besteht; im bestehenden Checkpoint-Code bleiben lediglich vorbestehende, nicht in diesem Auftrag eingeführte Lintbefunde außerhalb der Änderung bestehen.

## 29. Weltgenerierungsperformance

Frische, getrennte Prozesse; Seed 1729; gemessen wird der Runtime-Konstruktor einschließlich Initialisierung und erster DB-Erfassung, nach den Python-Imports:

| Größe | Genesis | Heterogeneous |
|---|---:|---:|
| Konstruktion | 1.5282 s | 1.5206 s |
| Quote-Batch Median, 100 Messungen | 7.1479 ms | 7.2620 ms |
| Quote-Batch p95 | 8.3467 ms | 10.1534 ms |

Beide Batches enthalten die 340 Indizes und den kompletten übrigen Quote-Bestand. Zusätzlich misst die Kontrollserie ausschließlich alle 340 typisierten Index-Quotes, je Prozess 100 Batches nach fünf Warm-ups: Median der drei Prozessmediane Genesis 1.0062 ms, Heterogeneous 1.0172 ms. Damit werden tatsächliche Index-Identitäten und nicht möglicherweise kollidierende Aktien-Symbole gemessen.

Ein einzelnes Konstruktionspaar belegt Größenordnung, keine belastbare Beschleunigung. Dies ist keine Messung des vollständigen kalten Desktopstarts oder eines nativen Paint-Zyklus.

## 30. Normale Tageskosten vor/nach Einführung

Im kontinuierlichen 365-Tage-Lauf werden je 331 normale Tage ausgewertet; Monatsbericht, Monatsend-Policy und Writer-Handoff-Tage sind getrennt. Genesis-Median 146.230 ms, Heterogeneous 153.217 ms (+4.78%); p95 165.081 bzw. 210.561 ms. Dieser seriell gemessene Jahresvergleich zeigt einen kleinen Medianunterschied und höhere Heterogeneous-Ausreißer.

Zusätzliche separate Kontrollserie ohne gleichzeitig laufende Tests oder Benchmarks: sechs getrennte Prozesse, drei gleiche Seeds, jeweils 60 Tage, fünf Warm-up-Tage, normale Tage ohne Monatsbericht/Policy. Commit sämtlicher Zeilen erfolgt nach dem Messbereich; dies ist ausschließlich Messisolierung und keine alternative Produktionspersistenz.

| Seed | Genesis-Median | Heterogeneous-Median |
|---|---:|---:|
| 1729 | 133.762 ms | 135.765 ms |
| 7 | 132.779 ms | 157.663 ms |
| 42 | 137.365 ms | 132.866 ms |

Gepoolter Median dieser Kontrollmessung: Genesis 133.752 ms; Heterogeneous 136.750 ms (+2.24%). Die Tagesengine-/Produktions-/Markt-/Writer-Dateien sind gegenüber der eingefrorenen Referenz bytegleich; es gibt keinen zusätzlich ausgeführten Modusgenerator oder Moduszweig. Unterschiede der Zahlenwerte und fortschreitenden Wirtschaft sowie Rechnerstreuung bleiben sichtbar; die Messung wird nicht als garantierte Gleichheit aller Laufzeiten ausgegeben.

Wegen des auffälligen ersten Seed-7-Paars wurde ausschließlich dieses Paar wiederholt, ohne den ersten Versuch auszublenden: Heterogeneous 130.944 ms, Genesis 135.248 ms. Der vermeintliche Aufschlag reproduziert sich nicht. Über **alle acht** Läufe einschließlich des Ausreißers: Genesis 134.128 ms, Heterogeneous 134.052 ms (-0.06%). Gemeinsam mit unverändertem Tagescode ergibt sich kein belegter bedeutender, durch neue Modusmechanik verursachter laufender Aufwand. Keine Tagesperformance-Toleranz wurde erhöht.

Die Jahres-Phasenmesswerte werden aus den tatsächlich persistierten `phase_metric_daily`-Zeilen ausgewertet. Ein anfänglicher Formfehler des reinen Diagnoseexporters (`dict` auf einer Liste von Dictionaries) wurde korrigiert, ohne Simulationsdaten zu verändern.

## 31. Speicherauswirkung und Persistenzpayload

Peak-Prozessspeicher direkt nach Day-1-Konstruktion und vor der Evidence-Serialisierung: Genesis 99.102 MiB; Heterogeneous 98.922 MiB. Kein messbarer zusätzlicher Größenordnungssprung; einmalige Interpreter-/Allocatorstreuung ist enthalten.

Lesbarer offizieller Tag-1-Checkpoint-JSON-Export mit identischer Einrückung: Genesis 27,855,030 Bytes; Heterogeneous 27,977,671 Bytes (+0.440%). Das ist ein vergleichbarer Persistenzpayload, keine Behauptung über komprimierte Bundlegröße.

DuckDB nach Jahr/Flush: Genesis 90.012 MiB; Heterogeneous 93.262 MiB. Unterschiede enthalten echte unterschiedliche Zahlen, Fondsallokationen und Bonds; Schema, Zeilenpräzision und Historienregeln bleiben gleich. Initialisierungsklassen und Produktivitätslisten werden nicht dauerhaft mit jeder Tagespayload übertragen.

## 32. Verbleibende Grenzen und mögliche spätere Abstimmung

Die vorgegebenen Produktivitätsbänder erlauben in dieser kontrollierten Population eine weiterhin starke positive GDP-Korrelation (beobachtet 0,829–0,900). Die 65%-GDP-Börsengewichtung erzeugt ebenfalls eine hohe Korrelation (0,974–0,996), obwohl die Länder nicht mechanisch proportional sind. Eine wesentlich unabhängigere Wirtschaft wäre eine neue Produkt-/Kalibrierungsentscheidung.

Das exakte 1,28-Billionen-Budget bei den gewünschten Klassenanteilen legt die Größenverteilung nahe an die Untergrenzen; Mega Caps liegen in den geprüften Seeds höchstens bei rund 9,24 Mrd., nicht typischerweise bei 18 Mrd. Die Bänder werden eingehalten, aber nicht gleichförmig ausgefüllt. Der Generator ist Version 1; spätere Parameteränderungen benötigen eine neue Initialisierungsversion und dürfen bestehende Saves nicht still neu erzeugen.

Produktions-Fallbacks, vereinfachte Optionsvolatilität, bestehende technische Bootstrap-/Anzeigehistorien und die schnelle Schleifen-Backpressure bleiben Modell-/Persistenzeigenschaften des aktuellen Produkts. Eine Native-UI-FPS-Messung und lange aktive Spielerstrategien sind in diesem Auftrag nicht neu benchmarked. Alle beauftragten funktionalen Gates und der echte Jahreslauf sind abgeschlossen; es wurde keine zweite Wirtschaftsengine und keine wiederkehrende Heterogeneous-Sondermechanik eingebaut.
