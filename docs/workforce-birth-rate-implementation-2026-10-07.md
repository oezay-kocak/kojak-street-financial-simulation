# Workforce + Birth Rate – Umsetzung und Validierung

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Stand: 2026-10-07. Maßgeblich ist der vom Nutzer freigegebene Implementierungsauftrag; die Vorgaben des beigefügten Dokuments bilden den konkret geprüften Umfang.

## 1. Geänderte Dateien

Seit dem eingefrorenen Stand dieses Auftrags geändert:

- `daten.py`
- `src/kojakstreet/adapters/legacy_runtime.py`
- `src/kojakstreet/adapters/legacy_state.py`
- `src/kojakstreet/core/checkpoints.py`
- `src/kojakstreet/core/company_lifecycle.py`
- `src/kojakstreet/core/data_store.py`
- `src/kojakstreet/core/data_store_schema.py`
- `src/kojakstreet/core/established_world.py`
- `src/kojakstreet/core/fast_history.py`
- `src/kojakstreet/core/heterogeneous_start.py`
- `src/kojakstreet/core/history.py`
- `src/kojakstreet/core/production_chains.py`
- `src/kojakstreet/core/simulation.py`
- `src/kojakstreet/live_process.py`
- `src/kojakstreet/visible_state.py`
- `src/kojakstreet/world_generator.py`
- `tests/test_established_world.py`

Zusätzliches vorhandenes Prüfwerkzeug: `tools/flush_writer_probe.py` verwendet für den eigenen Windows-Crash-Kindprozess jetzt die abrupte Kernel-Beendigung. Dieses Werkzeug zählt nicht zu den 177 eingefrorenen Produktions-/Testdateien.

Neu:

- `src/kojakstreet/core/workforce.py`
- `tests/test_workforce.py`
- `tools/workforce_validation.py`
- `tools/workforce_cost.py`
- `tools/workforce_writer_crash.py`
- `tools/workforce_legacy_bundle_probe.py`
- `tools/workforce_report.py`
- `tools/process_crash.py`
- `docs/workforce-birth-rate-implementation-2026-10-07.md`

Von 177 vorher erfassten Produktions-/Testdateien blieben 160 bytegenau unverändert. Frühere lokale Änderungen wurden erhalten. Die einzige bestehende Testanpassung ist die ausdrücklich neue Generator-Strategiebezeichnung; keine Toleranz wurde erweitert und kein Test deaktiviert.

## 2. Modell und Versionen

Workforce/Demografie V1, Kalibrierung V1; Economic Model `workforce-demographics-v1`. Checkpoint 8 (Lesekompatibilität 4–8), History Schema 2, Generator 3, Fast History 3 / `fast_history_v3`. Bundle Schema 1 und Heterogeneous Initialization 1 bleiben erhalten. Versionen beschreiben die neue wirtschaftliche Bahn; alte Bundles behalten ihre ursprüngliche Identität und eine getrennte Aktivierungsprovenienz.

## 3. Participation

`PARTICIPATION = 0.65`. Verfügbare Workforce ist eine abstrakte Größe, keine Zahl belegter Stellen. Headline-Arbeitslosigkeit wird nicht abgezogen.

## 4. Anteile je Weltmodus

Genesis: Basic 40%, Skilled 40%, Highly Qualified 20%. Heterogeneous: Basic 30–50%, Skilled 32–48%, Highly Qualified 12–30%, Summe exakt 1. Established startet mit den gemeinsamen Genesis-Anteilen und entwickelt Angebot und Nachfrage tatsächlich in Vorgeschichte und Burn-in. Die Anteile selbst bleiben in V1 statisch.

## 5. Heterogeneous Seed-Design

Eigene lokale `random.Random`-Instanzen aus SHA-256 von Modellversion, Weltseed, stabilem Ländernamen und getrennten Streams `shares`, `births`, `deaths`. Basic/Skilled werden dreieckverteilt gezogen; HQ ist das exakte Residuum. Unzulässige Residuen werden neu gezogen, nicht an eine Grenze geklemmt. Markt-RNG und bestehende Heterogeneous-Budgets werden nicht konsumiert oder neu skaliert.

## 6. Die 16 Sektormixe

Sektor-ID | Basic | Skilled | Highly Qualified | Intensität
--- | ---: | ---: | ---: | ---:
AUTOMOTIVE | 0.35 | 0.45 | 0.20 | 0.764462
CHEMICALS | 0.30 | 0.45 | 0.25 | 0.871339
OIL_GAS | 0.45 | 0.40 | 0.15 | 0.990304
POWER_UTILITIES | 0.30 | 0.50 | 0.20 | 0.590021
INDUSTRIAL_MACHINERY | 0.35 | 0.45 | 0.20 | 0.814282
TELECOM | 0.15 | 0.50 | 0.35 | 0.792199
RETAIL | 0.65 | 0.30 | 0.05 | 1.419139
CONSUMER_GOODS | 0.55 | 0.35 | 0.10 | 1.133073
FINANCIALS | 0.10 | 0.45 | 0.45 | 1.126121
PRECIOUS_METALS_MINING | 0.50 | 0.40 | 0.10 | 0.928568
HEALTHCARE | 0.20 | 0.45 | 0.35 | 1.005827
TECHNOLOGY | 0.10 | 0.40 | 0.50 | 1.260106
REAL_ESTATE | 0.45 | 0.40 | 0.15 | 0.995419
TRANSPORT_LOGISTICS | 0.50 | 0.40 | 0.10 | 0.911441
DEFENSE | 0.25 | 0.45 | 0.30 | 0.952423
AGRICULTURE | 0.60 | 0.30 | 0.10 | 1.476473

## 7. Intensitätskalibrierung

Die festen positiven Intensitäten sind die kleinste quadratische Anpassung gleicher Intensitäten an den 40/40/20-Mix des realen Genesis-Kapazitätsbestands. Bereich 0,590021–1,476473, auf sechs Nachkommastellen fixiert. Der Diagnosesolver läuft nicht in der Simulation. Kalibrierungsreferenz: Ameron, Genesis Day 1, Gesamtkapazität 18.894,70849655; neutrale Skalierung 688,02331628. Der finale Faktor 575 lässt rund 20% Genesis-Spielraum. Geprüft an 20 vollständigen Heterogeneous-Starts; keine laufende Länder-Normalisierung.

## 8. Nachfrageskala und Einheit

Eine reguläre Kapazitätseinheit erzeugt `575 × sector_intensity` Workforce-Äquivalente an Nachfrage, verteilt über den festen Mix. Alle Länder benutzen dieselbe abstrakte Einheit. Keine realen Headcounts, Lohnkosten oder GDP-pro-Kopf-Normalisierung werden behauptet.

## 9. Angebot

`L_c = 0.65 × P_c`; `S_c,p = L_c × share_c,p`. Die Teilnahmequote und Anteile werden nicht durch Headline-Arbeitslosigkeit oder Konjunktur verändert. Konjunktur wirkt nur über die bereits vorhandenen Kapazitäten und die gesonderte, reduzierte Bevölkerungsformel.

## 10. Nachfrage

`D_c,p = Σ(company.production_capacity × 575 × intensity_sector × mix_sector,p)`. Verwendet wird die zuletzt gültige reguläre Firmenkapazität. IPOs, Defaults und Ersatzfirmen gehen beim nächsten vollständigen monatlichen Aggregat ein. Keine täglichen Job-/Mitarbeiterobjekte und keine pro Firma gespeicherten Poolhistorien.

## 11. Coverage und Shortage

Bei positiver Nachfrage: `coverage = S/D`, `shortage = max(0,D-S)/max(1e-12,D)`. Ohne Nachfrage: Coverage 1, Shortage 0. Überangebot darf Coverage >1 anzeigen, gibt aber keinen wirtschaftlichen Bonus. Pro Land genau drei Supply/Demand/Coverage/Shortage-Werte.

## 12. Der einzige Workforce-Hook

`weighted_shortage = Σ(pool_shortage × sector_mix)`; `δ_result = -0.01 × weighted_shortage²`. Der eingefrorene Term wird genau einmal vor `update_stock_fundamentals` dem monatlichen `company_result` hinzugefügt. Bestehende Health-, Umsatz-, Margen-, Finanzierungs- und Repricing-Formeln propagieren ihn weiter. Kein zusätzlicher GDP-, Arbeitslosen-, Sektorfaktor-, täglicher Preis- oder unabhängiger Kapazitäts-Hook. News Momentum erhält keinen zusätzlichen Workforce-Term.

## 13. Finale Begrenzung und verworfene Kalibrierung

Finale absolute Grenze −0,01, ausreichendes Angebot exakt 0. Bei 1% gewichteter Knappheit −0,000001, bei 50% −0,0025. Der erste Versuch mit −0,03 wurde nicht freigegeben: Established enthielt nicht endliche historische Kurswerte. Zusätzlich wurde eine tatsächliche Doppelzählung der Margenebene in Coarse gefunden und behoben: die Workforce-Marge darf nicht zur nächsten zufälligen Basismarge werden. Ein 24-Monats-Regressionstest schützt das. Finale Established-Generierung und Save/Load bestehen mit unverändert strikter JSON-/Persistenzprüfung; keine Werte werden beim Speichern gelöscht oder ersetzt.

## 14. Monatliche Reihenfolge

Am regulären Berichtstag 15: bestehendes Macro → Firmenbericht mit vorher eingefrorenem δ → Firmen-Lifecycle → Population/Produktion → einmalige Workforce-Aggregation → δ für den nächsten Bericht einfrieren. Der bestehende Monatsmarker verhindert Wiederholung. Genesis/Legacy erhalten zunächst ein Initialaggregat aus dem aktuellen Bestand; es wird nicht als bereits beobachtete Demografiehistorie ausgegeben.

## 15. Headline-Arbeitslosigkeit

Die bestehenden Macro-/Krisen-/Inflations-/Psychologie-/Rating-Formeln bleiben unverändert. Arbeitslosigkeit beeinflusst weiter den reduzierten wirtschaftlichen Bevölkerungsterm und bestehende Nachfrage-/Finanzierungsmechanismen. Es gibt keinen direkten Workforce-Abzug oder Workforce-Arbeitslosenbonus. Änderungen in gemessenen Arbeitslosenquoten entstehen als bestehende Rückkopplungen der neuen wirtschaftlichen Bahn.

## 16. Birth Rate

`birth_rate` ist ein realer jährlicher Anteil der Bevölkerung: 0,012 bedeutet 1,2% pro Jahr. Kein monatlicher Nettozuwachs und keine Geburtenzahl pro Tag. Heterogeneous-Bereich 0,008–0,016.

## 17. Death Rate

`death_rate` ist ein realer jährlicher Anteil: 0,0085 bedeutet 0,85% pro Jahr. Heterogeneous-Bereich 0,006–0,011. Beide Wurzeln bleiben in V1 statisch; keine Alterskohorten werden vorgetäuscht.

## 18. Birth-/Death-Initialisierung

Genesis und neue Established-Welten: gemeinsame Mittelpunkte 0,012 / 0,0085. Heterogeneous: eigene reproduzierbare Dreiecksverteilungen mit separaten Streams, auf sieben Nachkommastellen fixiert. Alte Spielstände erhalten die gemeinsamen Wurzeln bei Aktivierung; historische Wurzeln werden nicht rekonstruiert.

## 19. Alte Bevölkerungsformeln

Live monatlich: `m_old = clamp((g-0.005)*0.025 - max(0,u-0.08)*0.010, -0.0025, 0.0035)`; `P'=max(2m,P*(1+m_old))`. Coarse zuvor unabhängig: `r=0.004+U_hash(-0.006,0.012)`, `P'=max(100k,P*(1+r*dt))`, ohne Aktualisierung von `population_growth`. Die alte Coarse-Populationszufallsrate wird entfernt, nicht mit Birth/Death addiert.

## 20. Neue Bevölkerungsformel

`natural_annual = birth_rate - death_rate`; `economic_annual = clamp(m_old*12*0.25,-0.006,0.003)`; `net_annual=clamp(natural_annual+economic_annual,-0.01,0.015)`; `P'=max(floor,P*exp(log1p(net_annual)*years))`. Live `years=1/12`, Coarse tatsächliche Bucketdauer in Jahren. `population_growth=P'/P-1` ist der realisierte Intervallwert inklusive Floor, nicht eine unverändert stehenbleibende Startzahl.

## 21. Natürlicher und wirtschaftlicher Anteil

Natürlicher jährlicher Nettoanteil plus stark reduzierter, begrenzter wirtschaftlicher Anteil werden vor der Zeitumrechnung kombiniert. Bei g=1%, u=6%: natürlich +0,35% jährlich, wirtschaftlich +0,0375%, insgesamt +0,3875%. Metadata `natural_growth` ist der natürliche Intervallwert, `economic_population_adjustment` der jährliche wirtschaftliche Parameter; ihre Einheiten sind verschieden. Die Gesamtänderung wird nur einmal angewendet.

## 22. Floors und Caps

Bestehender Live-Floor 2 Millionen, Coarse-Floor 100.000. Annual-Net-Guard −1% bis +1,5%; innerhalb der vorgesehenen Rootbereiche tatsächlich −0,9% bis +1,3%. Population und normalisierte Wachstumsrate sind am Floor realisiert, also z.B. beide 0 bei verhinderter Schrumpfung. Keine Anpassung der Startpopulation beim Laden oder am Handoff.

## 23. Stale Growth in Established

Jeder Coarse-Bucket setzt den tatsächlichen `population_growth`, Intervalllänge und Intervallende neu. Zusätzlich wird `population_growth_annualized = expm1(log1p(realized)/years)` als vergleichbare Rate gespeichert. Monats-/Jahreslevel werden nicht als identische rohe Monatsrate gemischt; Deep History verwendet die normalisierte Rate mit Rate-Semantik.

## 24. Coarse-Integration

Nur der Feature-Anteil wird in monatlichen Teilabschnitten fortgeschrieben. Existing Coarse-Pfade für Bevölkerung, Umsatz und Kapazität werden zeitlich interpoliert; der letzte Teilabschnitt kann gebrochen sein. Health: `h'=δ+(h-δ)*0.78^step`, mit geometrischem Mittel der monatlichen Health-Level für die Umsatzintegration. Umsatz erhält denselben inkrementellen `.18*(.35*δ+.65*h)`-Beitrag; Kapazität folgt der bestehenden Coarse-Umsatzrelation. Nach jedem Teilabschnitt wird Nachfrage neu aggregiert und δ für den folgenden eingefroren. Marge verwendet eine getrennte Coarse-Basismarge plus den aktuellen `.06*δ+.16*h`-Level, keine wiederholte Addition vergangener Workforce-Margen. Cash verwendet die bestehende Gleichung mit angepasst gültigem Umsatz/FCF. Keine 12 vollständigen Welt-/Marktreplays oder Zusatz-RNG-Aufrufe.

## 25. Burn-in und Handoff

Finale Established-Prüfung: 50 Jahre, 258 echte Coarse-Buckets und 365 tägliche Produktionsschritte. Handoff überträgt Health genau einmal nach `operating_health`, entfernt Coarse-Hilfswerte und erhält Population sowie gültiges eingefrorenes Aggregat. Danach normale Berichte. Zusätzlich bestehen die vorhandene 50-Jahre-/10-Tage-Burn-in-Prüfung mit 30 Live-Tagen und Save/Load sowie der konstante Monats-/Jahres-Rekurrenztest.

## 26. Legacy-Verhalten

Aktivierung ab Ladezeitpunkt, erste Firmenwirkung ab dem nächsten Bericht. Geprüft an echtem v7-/Generator2-/Schema1-Established-Bundle in einer Kopie: Aktivierung 2040-01-01T00:00:00; Wirtschaft, Population, Spielerbücher und RNG exakt erhalten, 20 Current-Rootzeilen, 0 nacherfundene Workforce-Historienzeilen. Ursprüngliche Generation/Economic Model bleibt in `world_generation`; aktive Modellversion und Aktivierungsdatum kommen separat hinzu. History ID bleibt erhalten; Schema-/Modellherkunft steht im Manifest. Legacy-Save an Tag 14 bestätigt zusätzlich die erste neue Beobachtung am Berichtstag 15.

## 27. Persistenz und Schema

Neue kleine Tabellen `country_workforce_monthly` und `country_workforce_current`, je 23 Skalare pro Land: Datum, Version/Aktivierung, P, Birth/Death, realisierte und normalisierte Growth samt Intervall und 12 Poolmetriken. Shares und eingefrorene Sektorbeiträge bleiben exakt im Country-Checkpoint. Birth/Death in Monatszeilen dokumentieren die für diese Beobachtung verwendeten Raten; V1 erzeugt dafür keine zusätzlichen Deep-History-Serien. Bestehende Tabellenpositionen bleiben stabil. Writer bekommt immutable RowBatch-Daten; NULL-Growth vor erster Beobachtung wird über die bereits bewährte quoted-CSV-/unquoted-NULL-Strecke exakt transportiert.

## 28. Historienkadenz

Neue Live-Fakten nur monatlich am Berichtstag: Genesis-Jahr 240 Workforce-Zeilen, 20 Current-Zeilen. Initiale Wurzeln und zwischenzeitliche Full-Save/Load-Refreshes erzeugen keine erfundenen Monatsbeobachtungen. 13 Country-Metriken in vorhandener monatlicher/jährlicher Deep-History-Kompaktion; Coarse-Capture enthält echte Feature-Bucketwerte. Keine Company×Pool×Day-Daten, keine täglichen Workforce-Historien und kein zweiter Writer.

## 29. Künftige UI-Projektion

On-demand Scope `macro` + ausgewähltes Land + `area=population_society` liefert P, jährliche Birth/Death, beobachtete Growth/Intervall, Headline-u und drei Poolmetriken. Vor erster Demografiebeobachtung sind Growth-Werte ausdrücklich unbekannt (`None`). Nur dieses Land; keine unnötigen Handels-/Chart-Historien oder Firmencopies. Roots werden aus allgemeinen Country-Projektionen ausgeschlossen. Separates `workforce_history_points` ermöglicht ausgewählte Metriken aus sparse History. Kein neuer Tab/Widget. Gemessener ausgewählter Payload: 2,685 Bytes.

## 30. Genesis-Ergebnis

Same-seed Start-RNG exakt gleich, gemeinsame 40/40/20-Wurzeln und gemeinsame Birth/Death. Kein anfänglicher Umsatz-/Kapazitäts-/GDP-/Preis-/Accounting-Neuberechnungseffekt. 365-Tage-Paar, Seed 1729:

Messgröße | Vorher | Nachher | Änderung
--- | ---: | ---: | ---:
population | 400,489,099.643 | 401,524,577.147 | +0.2586%
gdp | 101,063.112 | 101,060.623 | -0.0025%
revenue | 910,914,971,428.115 | 911,337,435,627.519 | +0.0464%
fcf | 97,265,279,974.228 | 97,379,546,521.887 | +0.1175%
market_cap | 1,184,626,715,510.696 | 1,184,879,939,456.695 | +0.0214%
production | 480,629.869 | 480,550.079 | -0.0166%
unemployment, Ländermittel | 8.07578% | 8.09689% | +0.02111 Prozentpunkte
inflation, Ländermittel | 1.93425% | 1.83953% | -0.09472 Prozentpunkte
Retired Companies / Insolvenzen | 0 | 0 | keine zusätzliche Insolvenz

Alle Workforce-Beiträge im gemessenen Genesis-Jahr sind 0; damit stammt die kleine wirtschaftliche Änderung hier aus Demografie und bestehenden Rückkopplungen.

## 31. Heterogeneous Multi-Seed-Ergebnis

2000 Rootprüfungen aus 100 Seeds × 20 Ländern, exakte Wiederholung und Grenzen/Summen; 20 vollständige Initialisierungen Seeds 0–19. Worst Pool Shortage 0.667134, Worst initialer Sektorbeitrag -0.00353162; Median Pool Shortage und typische Beiträge 0. 6–11 Länder je Welt haben irgendeinen Poolengpass: keine generelle Vollunterdeckung aller Pools oder harten Produktionsstopps. Knappheit tritt besonders bei kleinen Ländern auf und bleibt durch die weiche Kurve begrenzt. Es werden keine Grenzwerte angeklebt und keine Budgets nachträglich verschoben.

## 32. Established-Ergebnis

Vorher/nachher nach 50 Jahren einschließlich 365-Tage-Burn-in:

Messgröße | Vorher | Nachher | Änderung
--- | ---: | ---: | ---:
population | 566,315,571.651 | 496,963,384.365 | -12.2462%
gdp | 261,485.421 | 273,637.590 | +4.6474%
revenue | 2,199,555,913,432.489 | 2,321,317,384,277.390 | +5.5357%
fcf | 228,173,012,328.852 | 251,651,687,423.449 | +10.2899%
market_cap | 3,796,956,606,435.765 | 6,087,033,171,791.735 | +60.3135%
production | 746,341.169 | 764,826.582 | +2.4768%
unemployment, Ländermittel | 7.69060% | 4.06214% | -3.62846 Prozentpunkte
inflation, Ländermittel | 1.43241% | 2.57899% | +1.14658 Prozentpunkte
Retired Companies / Insolvenzen | 0 | 0 | keine zusätzliche Insolvenz

Dieser Vergleich enthält die entfernte alte Coarse-Zufallsdemografie, die neue Bevölkerungskurve und versionsbedingt andere Coarse-Zufallssignale: die bestehende Hashfunktion salzt bereits mit Economic Model und Fast History Version. Deren ausdrückliche Versionierung bleibt erhalten. Deshalb ist dieser Vergleich kein isolierter Workforce-Effekt. Die zusätzliche Kontrolle unter identischen neuen Versionen und gleicher Demografie trennt den result-Term in Abschnitt 33. Große Unterschiede einzelner Preis-/Regimegrößen dürfen nicht als direkte Workforce-Koeffizienten interpretiert werden.

## 33. 365-Tage-Paare und isolierte Wirkung

Heterogeneous Seed 1729:

Messgröße | Vorher | Nachher | Änderung
--- | ---: | ---: | ---:
population | 400,786,147.374 | 401,603,689.657 | +0.2040%
gdp | 101,195.170 | 101,063.904 | -0.1297%
revenue | 958,572,516,545.274 | 954,929,317,822.531 | -0.3801%
fcf | 102,134,775,778.048 | 101,919,729,579.472 | -0.2106%
market_cap | 1,546,534,011,607.810 | 1,448,137,939,506.324 | -6.3624%
production | 429,283.603 | 428,197.099 | -0.2531%
unemployment, Ländermittel | 6.74339% | 7.20512% | +0.46173 Prozentpunkte
inflation, Ländermittel | 1.92744% | 1.62163% | -0.30581 Prozentpunkte
Retired Companies / Insolvenzen | 0 | 0 | keine zusätzliche Insolvenz

Heterogeneous Seed 42:

Messgröße | Vorher | Nachher | Änderung
--- | ---: | ---: | ---:
population | 400,896,205.861 | 401,600,408.485 | +0.1757%
gdp | 101,349.795 | 101,336.946 | -0.0127%
revenue | 959,386,058,722.153 | 960,782,198,317.636 | +0.1455%
fcf | 98,727,122,314.489 | 100,083,274,992.365 | +1.3736%
market_cap | 1,549,314,132,737.310 | 1,573,430,036,421.877 | +1.5566%
production | 425,145.101 | 429,008.109 | +0.9086%
unemployment, Ländermittel | 6.24308% | 6.19607% | -0.04701 Prozentpunkte
inflation, Ländermittel | 1.85443% | 1.82807% | -0.02636 Prozentpunkte
Retired Companies / Insolvenzen | 0 | 0 | keine zusätzliche Insolvenz

Kontrolle mit gleicher neuer Demografie, aber ausgeschaltetem Workforce-result-Term, Seed 1729 (zusätzliche Diagnose, keine Produktionsoption):

Messgröße | Vorher | Nachher | Änderung
--- | ---: | ---: | ---:
population | 401,666,613.861 | 401,603,689.657 | -0.0157%
gdp | 101,195.185 | 101,063.904 | -0.1297%
revenue | 958,583,721,622.304 | 954,929,317,822.531 | -0.3812%
fcf | 102,137,463,602.582 | 101,919,729,579.472 | -0.2132%
market_cap | 1,546,490,294,698.647 | 1,448,137,939,506.324 | -6.3597%
production | 429,297.070 | 428,197.099 | -0.2562%
unemployment, Ländermittel | 6.74333% | 7.20512% | +0.46179 Prozentpunkte
inflation, Ländermittel | 1.92738% | 1.62163% | -0.30575 Prozentpunkte
Retired Companies / Insolvenzen | 0 | 0 | keine zusätzliche Insolvenz

Established-Kontrolle nach 50 Jahren mit gleicher neuer Demografie und ohne Workforce-result-Term:

Messgröße | Vorher | Nachher | Änderung
--- | ---: | ---: | ---:
population | 496,894,642.841 | 496,963,384.365 | +0.0138%
gdp | 273,201.973 | 273,637.590 | +0.1594%
revenue | 2,437,476,197,158.083 | 2,321,317,384,277.390 | -4.7655%
fcf | 259,118,042,324.572 | 251,651,687,423.449 | -2.8814%
market_cap | 5,600,448,465,555.220 | 6,087,033,171,791.735 | +8.6883%
production | 782,580.262 | 764,826.582 | -2.2686%
unemployment, Ländermittel | 4.82130% | 4.06214% | -0.75916 Prozentpunkte
inflation, Ländermittel | 2.35335% | 2.57899% | +0.22565 Prozentpunkte
Retired Companies / Insolvenzen | 0 | 0 | keine zusätzliche Insolvenz

In dieser letzten Kontrolle ist GDP nur gering verändert, Umsatz über 50 Jahre moderat vermindert und keine zusätzliche Insolvenz sichtbar. Preis- und Quotenabweichungen bleiben stochastische Rückkopplungen; behauptet wird keine tickgenaue Preisgleichheit zwischen absichtlich unterschiedlichen Modellen.


Die Tabellen verwenden die vorhandenen Simulationsfelder und deren numerische Einheiten; monetäre Summen enthalten keine zusätzliche FX-Neubewertung. `population_growth` ist der zuletzt beobachtete Intervallwert, Birth/Death sind jährliche Anteile. Alle Länder/Unternehmen gehen in die Verteilungen ein, nicht nur Stichproben.

### Genesis 365 Tage: Verteilungen

Messgröße | Vorher: Min / Median / p95 / Max | Nachher: Min / Median / p95 / Max
--- | --- | ---
population | 1.992535e+07 / 2.004039e+07 / 2.006174e+07 / 2.006207e+07 | 2.005157e+07 / 2.008044e+07 / 2.0085e+07 / 2.008644e+07
population_growth | -0.0025 / -0.0002601397 / 0.0003116782 / 0.0007672628 | -0.0002085724 / 0.0002327968 / 0.0003672522 / 0.0004319289
gdp | 5001.652 / 5058.926 / 5076.904 / 5077.186 | 5002.215 / 5060.119 / 5075.511 / 5080.371
growth | -0.06 / -0.002530029 / 0.01746713 / 0.03569051 | -0.05865798 / -0.0007987633 / 0.01721252 / 0.02760637
unemployment | 0.0562076 / 0.07244324 / 0.1266423 / 0.1737425 | 0.05335885 / 0.06869107 / 0.1269285 / 0.1761767
inflation | -0.01653779 / 0.02281688 / 0.03342758 / 0.03382752 | -0.0126236 / 0.02302956 / 0.02953101 / 0.03542981
revenue | 1.346752e+08 / 6.842374e+08 / 1.271546e+09 / 1.454672e+09 | 1.342151e+08 / 6.814175e+08 / 1.272588e+09 / 1.439976e+09
fcf | -871833.2 / 6.66585e+07 / 1.625987e+08 / 2.492918e+08 | 1.297128e+07 / 6.690005e+07 / 1.593646e+08 / 2.533162e+08
market_cap | 2.589249e+08 / 9.119173e+08 / 1.327622e+09 / 1.814237e+09 | 2.320708e+08 / 9.067842e+08 / 1.321913e+09 / 2.202694e+09
production | 21.96 / 3461.746 / 9268.188 / 14950.79 | 21.96 / 3467.268 / 9242.183 / 14949.93
birth_rate | nicht modelliert | 0.012 / 0.012 / 0.012 / 0.012
death_rate | nicht modelliert | 0.0085 / 0.0085 / 0.0085 / 0.0085
coverage | nicht modelliert | 1.123989 / 1.135805 / 1.22515 / 1.230546
shortage | nicht modelliert | 0 / 0 / 0 / 0
contribution | nicht modelliert | 0 / 0 / 0 / 0

### Genesis 365 Tage: alle 16 Sektoren

Sektor | Umsatz Δ | FCF Δ | Market Cap Δ | Kapazität Δ
--- | ---: | ---: | ---: | ---:
Automobil | +0.4771% | +8.9120% | +2.5612% | +0.6033%
Chemie | +0.0846% | -0.2994% | +0.0988% | -0.0027%
Öl und Gas | -0.0166% | +0.9334% | +0.4674% | +0.1215%
Stromerzeuger | -0.0266% | -0.3458% | -1.5380% | -0.0340%
Maschinenbau | +0.3174% | +2.4651% | -0.1276% | +0.3509%
Telekommunikation | -0.1287% | -1.4103% | +0.2747% | -0.1785%
Einzelhandel | +0.0287% | +0.5756% | +0.1563% | +0.0581%
Konsumgüter | -0.0208% | -0.1173% | -0.6482% | -0.0265%
Finanzen | -0.0312% | -0.1761% | +1.4255% | -0.0355%
Edelmetallförderer | -0.2184% | -1.7976% | -2.0094% | -0.3099%
Gesundheit | -0.0936% | -0.6345% | +0.0535% | -0.1217%
Technologie | -0.2030% | -0.5797% | +0.3318% | -0.1623%
Immobilien | +0.0903% | +0.4179% | -0.5442% | +0.1260%
Transport und Logistik | -0.0452% | -2.2575% | +0.9856% | -0.1786%
Verteidigung | +0.0380% | +0.3590% | +0.0261% | +0.0523%
Landwirtschaft | -0.0504% | -2.7467% | -1.1565% | -0.1947%

### Heterogeneous 1729, 365 Tage: Verteilungen

Messgröße | Vorher: Min / Median / p95 / Max | Nachher: Min / Median / p95 / Max
--- | --- | ---
population | 5751585 / 1.871183e+07 / 3.507415e+07 / 3.704886e+07 | 5759941 / 1.87608e+07 / 3.518071e+07 / 3.70678e+07
population_growth | -0.0006653082 / -3.905639e-05 / 0.0003474234 / 0.0006241629 | -8.127411e-05 / 0.0002838384 / 0.0005268969 / 0.0005989508
gdp | 1695.537 / 4704.101 / 10192.08 / 11155.49 | 1696.59 / 4654.713 / 10186.01 / 11169.59
growth | -0.01486609 / 0.003546087 / 0.01889694 / 0.02996651 | -0.02402914 / 0.002839479 / 0.01628692 / 0.04088024
unemployment | 0.02449836 / 0.06692226 / 0.0886838 / 0.09686561 | 0.02551483 / 0.06789261 / 0.09602086 / 0.1491375
inflation | 0.008146261 / 0.02011544 / 0.02703403 / 0.03248895 | -0.02696483 / 0.01771435 / 0.02760474 / 0.02970485
revenue | 1.456241e+07 / 3.337202e+08 / 3.009828e+09 / 1.010839e+10 | 1.400508e+07 / 3.307052e+08 / 2.981554e+09 / 1.111046e+10
fcf | 3894805 / 4.19568e+07 / 2.772969e+08 / 1.445048e+09 | 3884424 / 4.140065e+07 / 2.717453e+08 / 1.382579e+09
market_cap | 6.704557e+07 / 7.260338e+08 / 4.031367e+09 / 1.385689e+10 | 1.597875e+07 / 6.905362e+08 / 3.792259e+09 / 1.519435e+10
production | 21.95993 / 2881.193 / 7896.618 / 13396.03 | 21.9599 / 2889.002 / 7860.639 / 13357.08
birth_rate | nicht modelliert | 0.0088775 / 0.0118057 / 0.0145123 / 0.0148294
death_rate | nicht modelliert | 0.0065869 / 0.00822935 / 0.0100874 / 0.0102091
coverage | nicht modelliert | 0.3271655 / 1.247845 / 2.237556 / 2.355374
shortage | nicht modelliert | 0 / 0 / 0.5431882 / 0.6728345
contribution | nicht modelliert | -0.003208795 / 0 / 0 / 0

### Heterogeneous 1729, 365 Tage: alle 16 Sektoren

Sektor | Umsatz Δ | FCF Δ | Market Cap Δ | Kapazität Δ
--- | ---: | ---: | ---: | ---:
Automobil | -0.4192% | -1.1895% | -7.8064% | -0.2343%
Chemie | -1.4302% | -0.3677% | -3.1022% | -0.4164%
Öl und Gas | -1.0764% | -1.9656% | -7.4248% | -0.4034%
Stromerzeuger | -0.0266% | -1.0994% | -2.3757% | -0.0990%
Maschinenbau | -1.2244% | +0.4969% | -3.7780% | -0.1200%
Telekommunikation | +0.9465% | +3.6755% | -4.6229% | +0.4959%
Einzelhandel | +0.8793% | +6.6982% | -4.6926% | +0.2285%
Konsumgüter | +0.0036% | -2.7865% | -7.2743% | -0.4592%
Finanzen | +0.1886% | +0.8974% | -5.3591% | -0.0513%
Edelmetallförderer | -0.8419% | -2.3082% | -9.6902% | -0.4984%
Gesundheit | -0.6665% | -0.8044% | -8.2608% | -0.7163%
Technologie | +0.1830% | -1.0881% | -7.4435% | -0.4135%
Immobilien | -0.1434% | -0.1654% | -3.9443% | +0.2047%
Transport und Logistik | -0.3646% | -0.0236% | -6.8373% | -0.1858%
Verteidigung | -1.7238% | -4.5111% | -7.9442% | -0.9130%
Landwirtschaft | +0.2335% | +3.8496% | -8.7114% | +0.0620%

### Heterogeneous 42, 365 Tage: Verteilungen

Messgröße | Vorher: Min / Median / p95 / Max | Nachher: Min / Median / p95 / Max
--- | --- | ---
population | 5019988 / 1.829596e+07 / 4.025814e+07 / 4.55537e+07 | 4997355 / 1.829923e+07 / 4.037586e+07 / 4.552808e+07
population_growth | -0.0008655621 / 3.788117e-05 / 0.0005825394 / 0.001 | -0.0001077742 / 0.0003007067 / 0.0005275515 / 0.000620175
gdp | 1493.299 / 4598.921 / 8743.691 / 12666.26 | 1494.712 / 4597.992 / 8739.697 / 12665.25
growth | -0.02816268 / 0.006515247 / 0.02830158 / 0.045 | -0.01632703 / 0.006702632 / 0.02368412 / 0.04456611
unemployment | 0.04154788 / 0.0601922 / 0.08364951 / 0.08384895 | 0.04458773 / 0.05818225 / 0.08331278 / 0.08370976
inflation | -0.007428478 / 0.01996521 / 0.02772294 / 0.02801866 | -0.00539089 / 0.02054589 / 0.02751234 / 0.03042775
revenue | 1.443551e+07 / 3.310579e+08 / 3.123437e+09 / 1.142972e+10 | 1.48553e+07 / 3.275375e+08 / 3.211763e+09 / 1.08937e+10
fcf | 1945005 / 4.129054e+07 / 2.758667e+08 / 1.386299e+09 | 3609210 / 4.178504e+07 / 2.778683e+08 / 1.510302e+09
market_cap | 7.097167e+07 / 7.40524e+08 / 4.230678e+09 / 1.730667e+10 | 7.928149e+07 / 7.745372e+08 / 4.147723e+09 / 1.52727e+10
production | 21.96 / 2924.08 / 7683.554 / 11935.91 | 21.96 / 2938.655 / 7691.482 / 13442.83
birth_rate | nicht modelliert | 0.0083473 / 0.01239855 / 0.014128 / 0.0147994
death_rate | nicht modelliert | 0.0067905 / 0.00895775 / 0.010218 / 0.0107146
coverage | nicht modelliert | 0.3990347 / 1.236316 / 2.122327 / 2.540068
shortage | nicht modelliert | 0 / 0 / 0.4298999 / 0.6009653
contribution | nicht modelliert | -0.003481636 / 0 / 0 / 0

### Heterogeneous 42, 365 Tage: alle 16 Sektoren

Sektor | Umsatz Δ | FCF Δ | Market Cap Δ | Kapazität Δ
--- | ---: | ---: | ---: | ---:
Automobil | +0.6951% | +5.6310% | +6.1445% | +0.2740%
Chemie | +0.8939% | +5.8381% | -0.1591% | +0.8495%
Öl und Gas | +1.1706% | +3.5351% | +2.4563% | +0.3076%
Stromerzeuger | +0.3604% | +5.2485% | +6.4071% | +0.6157%
Maschinenbau | -0.4092% | -1.1620% | +2.6201% | -0.0540%
Telekommunikation | -0.0225% | +0.1530% | +3.9422% | +0.1683%
Einzelhandel | -0.6761% | -4.4911% | +5.4204% | -0.5884%
Konsumgüter | +0.2206% | -4.2738% | -3.5110% | -0.2854%
Finanzen | -0.0241% | +0.1575% | -2.7631% | +0.0262%
Edelmetallförderer | -0.6222% | -0.3692% | +3.6517% | -0.1839%
Gesundheit | -0.7390% | -0.3623% | +5.6831% | -0.1908%
Technologie | -0.7721% | -1.5011% | +1.5544% | -0.1915%
Immobilien | -0.0470% | -0.0852% | +0.9294% | +0.0145%
Transport und Logistik | -0.5018% | +2.7976% | -4.6610% | +0.1504%
Verteidigung | -0.2456% | +1.4441% | +1.3880% | +0.2332%
Landwirtschaft | +0.8330% | +2.1787% | +0.5128% | +0.6645%

### Established nach 50 Jahren: Verteilungen

Messgröße | Vorher: Min / Median / p95 / Max | Nachher: Min / Median / p95 / Max
--- | --- | ---
population | 2.678658e+07 / 2.840919e+07 / 2.943543e+07 / 2.947234e+07 | 2.465917e+07 / 2.482405e+07 / 2.499474e+07 / 2.520847e+07
population_growth | -0.0025 / 0.0002184478 / 0.0009508887 / 0.0009902344 | -6.807001e-05 / 0.0003678009 / 0.0004579579 / 0.0005011774
gdp | 10911.58 / 13074.78 / 14778.32 / 16127.33 | 12112.82 / 13438.35 / 15155.25 / 16948.4
growth | -0.05708011 / 0.01387092 / 0.04303555 / 0.04460937 | -0.03479474 / 0.01730068 / 0.03179144 / 0.03874313
unemployment | 0.05358256 / 0.06081411 / 0.188363 / 0.1902346 | 0.02 / 0.0341679 / 0.0631032 / 0.1243976
inflation | -0.0255254 / 0.02017803 / 0.02539569 / 0.02651519 | 0.01259126 / 0.02700997 / 0.03293823 / 0.03373091
revenue | 2.971458e+08 / 1.637881e+09 / 3.145482e+09 / 3.943124e+09 | 3.208528e+08 / 1.749012e+09 / 3.441514e+09 / 4.187743e+09
fcf | -3.203583e+07 / 1.591914e+08 / 3.514706e+08 / 5.667857e+08 | 2.486155e+07 / 1.722296e+08 / 4.234465e+08 / 6.749529e+08
market_cap | 7.904338e+08 / 2.828034e+09 / 4.754256e+09 / 7.601685e+09 | 1.274042e+09 / 4.59107e+09 / 7.577468e+09 / 1.142814e+10
production | 21.95998 / 5260.609 / 14618.35 / 22199.66 | 21.96 / 5321.501 / 14034.29 / 22987.3
birth_rate | nicht modelliert | 0.012 / 0.012 / 0.012 / 0.012
death_rate | nicht modelliert | 0.0085 / 0.0085 / 0.0085 / 0.0085
coverage | nicht modelliert | 0.855875 / 0.8997281 / 0.9242815 / 0.9285961
shortage | nicht modelliert | 0.07140393 / 0.1002719 / 0.1215702 / 0.144125
contribution | nicht modelliert | -0.0002040714 / -9.861196e-05 / -5.70084e-05 / -5.342056e-05

### Established nach 50 Jahren: alle 16 Sektoren

Sektor | Umsatz Δ | FCF Δ | Market Cap Δ | Kapazität Δ
--- | ---: | ---: | ---: | ---:
Automobil | +7.7825% | +7.3182% | +86.1187% | +3.8301%
Chemie | +5.9435% | +14.6911% | +60.9766% | +3.6271%
Öl und Gas | +17.4535% | +23.6452% | +89.4130% | +9.2352%
Stromerzeuger | +7.6175% | +16.9004% | +69.6416% | +4.4726%
Maschinenbau | +5.8649% | +9.5043% | +66.0223% | +3.2049%
Telekommunikation | +11.8930% | +17.1194% | +74.8214% | +6.3279%
Einzelhandel | +1.4481% | +9.7416% | +60.8952% | +1.2242%
Konsumgüter | +0.4310% | +3.8290% | +70.2113% | +0.6105%
Finanzen | +9.3555% | +10.4839% | +70.0628% | +4.9041%
Edelmetallförderer | -1.7176% | +4.0604% | +38.8972% | +0.0250%
Gesundheit | -13.1785% | -11.1264% | +21.5787% | -6.3879%
Technologie | +1.4472% | +3.6686% | +46.1193% | +1.1589%
Immobilien | -9.0339% | -7.4507% | +11.0755% | -4.2219%
Transport und Logistik | +18.4580% | +24.4029% | +101.1525% | +9.2764%
Verteidigung | +6.0716% | +11.8812% | +65.1960% | +3.6829%
Landwirtschaft | -11.2537% | -6.3929% | +26.7221% | -5.4351%

## 34. Stressprüfungen

Rezession g=−8%, u=40%; Hochwachstum g=12%, u=2%; zusätzliche u=80%-Angebotsprüfung; starke Workforce-Knappheit, Überangebot, Populationsfloor und 100-Jahre-Komposition. Keine automatische Verringerung des Angebots durch u, 0 Bonus im Überangebot und beschränkter result-Term. Echter erzwungener Default entfernt die Firma, ersetzt sie per vorhandener IPO-Logik und aktualisiert den Bedarf im nächsten Aggregat. Monats-/Jahreskomposition bei konstantem Macro stimmt mit enger Float-Toleranz, Coarse-Margenlevel werden 24 Monate gegen die tatsächliche Baseline-Rekurrenz geprüft.

## 35. Save/Load und Berichtstage

Tag 14, 15 und 16: kompletter Checkpoint inklusive Markt-RNG, Population, Roots und eingefrorener Beiträge vor/nach Load exakt gleich; anschließend ein kompletter Simulationstag exakt gleich. Tests prüfen auch 0/20 Monatszeilen, den richtigen Aggregationstag und die unbekannte Rate vor erster Beobachtung. Ungültige Feature-Checkpoints werden vor Live-Mutation abgelehnt. Zusätzliche Jahres-/Established-Paare vergleichen vollständige Checkpoint-Digests und nächste Tagesfortsetzung; alle bestehen.

## 36. Writer und Recovery

Neue Workforce-Rows durchlaufen den bestehenden einzelnen Writer, keine zusätzliche Thread- oder Verbindungsbesitzlogik. Tests: Freeze/Mutationstrennung, NULL-Current-Row, persistenter Journal-Replay, echte Prozessabbrüche vor Transaktion, während COPY, vor COMMIT, während COMMIT, nach COMMIT und nach ACK. Sichtbar ist atomar entweder der alte oder ganze neue Zustand; Replay liefert exakt eine Monats-/Current-Zeile und bleibt beim zweiten Öffnen idempotent. Vorhandene Queue-/Backpressure-, Barrieren-, Fehler- und Retail-Writer-Tests sind Teil der vollständigen Suite. Fsync, COMMIT, Journalgrenzen und Speicherbarrieren werden nicht abgeschwächt.

## 37. Vollständige Testsuite

635 bestanden, 0 Fehler, 0 Fehlschläge, 0 übersprungen; 1589.34 Sekunden. JUnit: `.cache/workforce-implementation/full-suite-final-v4.xml`. Neue Feature-Datei deckt 128 Testfälle ab. Zusätzlicher Coarse-/Established-Regressionslauf: 2 bestanden. Neue Dateien lint-clean; eingeführte Importsortierungsfehler korrigiert. Bestehende fremde Lintbefunde wurden nicht pauschal umgebaut. Der vorherige Gesamtversuch hatte 634 erfolgreiche Tests und einen nativen Windows-Exit 0xC0000005 statt des geplanten Exit 91 im bestehenden Crash-nach-ACK-Test. Unabhängige Prüfung seiner Artefakte fand beide Tabellen vollständig committed und das Journal bestätigt/leer; Einzelwiederholung bestand. Tests und Exit-Anforderungen wurden nicht erweitert oder deaktiviert. Beide Crash-Prüfwerkzeuge verwenden jetzt für den eigenen Windows-Kindprozess `TerminateProcess` statt CRT-Exit; auf anderen Plattformen bleibt `os._exit`. Das testet einen abrupten Prozessabbruch ohne native Aufräumphase und ohne DB-Close. 146 Writer-/Feature-Prüfungen wurden damit zusätzlich wiederholt. Zwischenläufe mit verworfener Marge/Kalibrierung werden nicht als finale Freigabe gezählt.

## 38. Normal-Day-Performance

Separater 90-Tage-Vergleich desselben Genesis-Seeds: je 87 normale Tage. Median Wall vorher 138.720 ms, nachher 137.033 ms; Prozess-CPU-Median beide 140.625 ms. Ein eigener Test verbietet Aggregation auf normalen Tagen. Kein zusätzlicher Firmenscan, keine neue tägliche Historie. Host-Last/CPU-Zeitauflösung begrenzen die Genauigkeit; die Messung zeigt keinen relevanten Normal-Day-Rückschritt.

## 39. Report-Day und Aggregation

Je drei Reporttage im Kostenlauf: Wall-Median vorher 220.425 ms, nachher 215.170 ms; CPU-Median beide 218.750 ms. Aggregation isoliert 100 Wiederholungen: Median 1.331 ms, p95 1.875 ms. Wenige ganze Reporttage sind kein hochpräziser Benchmark; der direkt gemessene Feature-Anteil ist klein.

## 40. Established-Generierungskosten

Gemessene 50-Jahre-Gesamtzeit vorher 171.644 s, nachher 179.234 s (+4.42%). Beide mit 365 Produktions-Burn-in-Tagen. Feature macht monatliche Unterintegration auch in alten Jahres-Buckets; dieser begrenzte Mehrbedarf ist bewusst. Parallel laufende Prüfungen und große Checkpoint-/Kompressionskosten beeinflussen Wall-Zeiten; keine behauptete präzise Einzelkostenattribution der Gesamtzeit.

## 41. Speicher- und Payload-Auswirkung

90-Tage-Checkpoint vorher 64,293,123, nachher 64,319,068 Bytes (Δ 25,945); Feature-Country-Daten allein 26,414 Bytes. Markt-Payload beide exakt 527,044 Bytes. Peak RSS vorher 868.59, nachher 872.14 MiB; dieser Unterschied umfasst Allocator-/Laufstreuung. Keine täglich wachsenden Feature-Pools. Established-Store vorher 142,880,768, nachher 147,861,504 Bytes; Kompaktions-/Wirtschaftsverlauf beeinflussen die Differenz.

## 42. Verbleibende Grenzen

Abstrakte Workforce-Äquivalente statt echter Stellen, keine Löhne, Kohorten, Migration, Ausbildung oder dynamische Shares. Headline-u bleibt ein anderes Macro-Signal. Established ist weiterhin eine versionierte Multi-Resolution-Näherung mit echtem Burn-in; keine Gleichheit mit 50 Jahren vollständigem Daily-Replay wird behauptet. 20 Startwelten plus zwei Heterogeneous-Jahrespaare und ein Established-Paar sind belastbare Prüfungen, kein Beweis für jeden Seed oder unbegrenzte Horizonte. Quoten/Preise besitzen stochastische Rückkopplungen. Ein späterer UI-Bereich und neue Mechaniken sind nicht Bestandteil dieses Auftrags.

## 43. Abschließendes Urteil

Freigegeben für diesen Implementierungsumfang: Die finale Kalibrierung ergänzt begrenzte Länder-/Sektorunterschiede, Geburt und Tod haben klare jährliche Semantik, Coarse und Live behandeln den Workforce-Beitrag zeitlich konsistent und die zuvor gefundene Margen-Doppelzählung ist behoben. Kein zusätzlicher Insolvenzfall in den Jahres-/Established-Paaren, keine neue globale Workforce-GDP-Formel, keine täglichen Feature-Scans und vollständige Persistenz-/Fortsetzungsprüfungen. Die anfängliche fehlerhafte Variante wurde verworfen; die Freigabe gilt dem korrigierten finalen Stand.
