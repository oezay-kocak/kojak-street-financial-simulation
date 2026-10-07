# Workforce- und Population-Audit – 7. Oktober 2026

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


**Status: Audit abgeschlossen; keine Workforce-Funktion implementiert.** Der freigegebene Auftrag ist die Bestandsaufnahme des angehängten Audit-Dokuments. Produktionsverhalten, Tests, bestehende Spielstände und Datenbanken wurden nicht verändert. Alle Vorschläge unten sind Architekturentscheidungen zur Diskussion; insbesondere wurden keine Qualifikationsanteile festgelegt.

Eine kleine Workforce-Schicht ist grundsätzlich anschlussfähig. Empfehlenswert sind eine feste Erwerbsbeteiligung, drei zunächst statische Qualifikationsanteile, monatliche Nachfrageaggregation und ein einzelner kleiner Effekt im monatlichen Unternehmensbericht. Die bestehende Gesamtarbeitslosigkeit bleibt maßgeblich. Vor einer Implementierung müssen Bedarfseinheiten, Effektstärke, alte Spielstände und die beschleunigte Established-Vorgeschichte gemeinsam festgelegt werden. Eine unveränderte Bevölkerungsgrowth-Zahl als „Birth Rate“ auszugeben wäre fachlich falsch.

## 1. Bevölkerung: Speicherung und Formeln

Der maßgebliche Bestand ist `makro[country]["bevoelkerung"]`, ein Float. `population_growth` enthält im normalen Spiel die zuletzt berechnete **monatliche Nettoänderungsrate**, keinen jährlichen Wert und keine Geburtenrate.

| Ort / Funktion | Takt | Eingaben → Ergebnis | Zufall | Weiterverwendung |
|---|---|---|---|---|
| `daten.py`, Länderinitialisierung | Neue Welt | Genesis: 20 Mio. je Land; Heterogeneous: `InitializationRoots.population`; `population_growth=0` | Genesis keine Bevölkerungsziehung; Heterogeneous eigener Seed-Stream | Konsumbasis, regionale Nachfrage, Save, Analytics |
| `production_chains.ensure_population` | Initialisierung, Laden, Produktion | fehlender Bestand → 20 Mio.; fehlende Rate → 0; bestehende Werte bleiben erhalten | keiner | nachfolgende Produktion |
| `production_chains.update_population` | normaler Monatsbericht, Tag 15 | BIP-Wachstumsrate und Arbeitslosenquote → Monatsrate und neuer Bestand; Formel Abschnitt 2 | keiner | Konsumnachfrage im selben Produktionsschritt |
| `fast_history._advance_correlated_state` | jährliche/frühere bzw. monatliche/jüngere Vorgeschichte | alter Bestand × separat gezogene Wachstumsrate × Zeitspanne; Formel Abschnitt 2 | deterministischer Hash aus Seed, Datum, Modell-/History-Version und Land | grobe History, laufender Zustand, anschließender Burn-in |
| `checkpoints.capture/restore`; `speicher.spiel_speichern/spiel_laden` | Save/Load | `makro` vollständig als Datenzustand erhalten | RNG-Zustände ebenfalls gespeichert | exakte Fortsetzung |
| `data_store._country_rows` | Tag 15; zusätzlich volle Initial-/Load-/Bundle-Snapshots | Bestand → SQL-Feld `population` | keiner | `country_current`, `country_daily`, History-Abfrage |

Normale tägliche Produktion und Initialisierungs-Warm-up übergeben ausdrücklich `advance_population=False`. Ein neuer Tag allein erzeugt also kein Bevölkerungswachstum. Die Population hat außerhalb ihrer Wachstumsformeln keine obere Bestandsgrenze. Die Initialisierungsbudgets und Klassen sind Startbedingungen, keine laufenden Grenzen.

## 2. Exaktes Bevölkerungswachstum

Für normale Tage mit Monatsbericht gilt mit jährlicher Makro-Wachstumsrate `g`, Arbeitslosenquote `u` und Bestand `P`:

```text
m = clamp((g − 0.005) × 0.025 − max(0, u − 0.08) × 0.010,
          −0.0025, +0.0035)
P_neu = max(2_000_000, P × (1 + m))
population_growth = m
```

Die Formel verwendet die **bereits aktualisierten** Makrowerte desselben Berichts. BIP-Wachstum oberhalb 0,5 % begünstigt Zunahme; Arbeitslosigkeit über 8 % bremst. Zunahme erfordert `g > 0.005 + 0.4×max(0,u−0.08)`. Unterhalb dieser Schwelle sinkt die Bevölkerung bis zur Untergrenze. An der Untergrenze kann die gespeicherte negative Rate vom tatsächlich ausbleibenden Rückgang abweichen.

Beispiele mit konstanten Eingaben: `g=1.5%, u=6%` → `m=+0.025%`, annualisiert etwa +0,3004 %. `g=0%, u=6%` → −0,0125 % monatlich. `g=−6%, u=22%` → Monatsuntergrenze −0,25 %, annualisiert etwa −2,959 %. Die positive Monatsgrenze entspricht etwa +4,282 % jährlich, wird mit dem normalen BIP-Cap von +4,5 % und nichtnegativer Arbeitslosenquote jedoch nicht erreicht; dort ist maximal +0,1 % monatlich möglich.

Die grobe Established-Vorgeschichte verwendet dagegen:

```text
dt = max(1/365, verstrichene_Tage / 365.2425)
r = clamp(0.004 + hash_uniform(seed, datum, "population:<Land>", −0.006, 0.012),
          −0.01, 0.025)
P_neu = max(100_000, P × (1 + r × dt))
```

Die tatsächlich gezogene jährliche Rate liegt zwischen −0,2 % und +1,6 %; die Clamp-Grenzen sind hier weiter als die Ziehung. Kein Bezug zu BIP oder Arbeitslosigkeit. Untergrenze 100.000 statt 2 Mio. **`population_growth` wird in diesem Pfad nicht aktualisiert** und kann bis zum nächsten normalen Monatsbericht einen alten Wert zeigen. Der isolierte Aufruf über 20 Länder bestätigt dies. Beide Formeln sind unabhängig von Geburten und Sterbefällen.

## 3. Bestehende Geburten-, Sterbe- und Migrationskonzepte

Kein demografischer Birth-/Fertility-/Death-/Migration-Zustand, keine Kohorten und keine Personenflüsse gefunden. Das gegenwärtige Modell ist abstraktes Nettowachstum. Kreditrating-Migration und Datenbankschema-Migration sind andere Konzepte. `EDU` ist eine wirtschaftliche Dienstleistung mit Inputs `REAL`, `DATA`, `SOFT`, kein Bildungsabschlussbestand und kein Qualifikationsübergang.

## 4. Empfehlung zur Birth Rate

| Option | Fachliche Bedeutung | Aufwand / Risiko | Bewertung |
|---|---|---|---|
| A: Geburtenrate als Root, einfache Sterberate | eigenständiger demografischer Treiber; Nettoänderung aus Geburten minus Sterbefällen | ersetzt/ergänzt heutige Wachstumsursache; Parameter, Floors, Versionen und beide Vorgeschichtepfade nötig | kleinste sinnvolle **echte** Birth-Rate-Option, falls ausdrücklich gewünscht |
| B: heutiges Wachstum maßgeblich, Birth Rate abgeleitet | Nettoänderung allein identifiziert Geburten nicht | abgeleitete Geburtenrate braucht wenigstens angenommene Sterberate; negatives Netto darf nicht zu negativen Geburten werden | V1 bevorzugt als ehrliche Anzeige „Population Growth“, ohne Birth Rate |
| C: Birth Rate als zusätzlicher kleiner Input | begrenzter eigener Einfluss möglich | Gefahr, bisheriges Nettowachstum und neue Demografie doppelt zu zählen; Einheiten-/Zeitbasis-Mischung | für erste Workforce-Version unnötig |

**Empfehlung: zunächst Netto-Bevölkerungswachstum anzeigen.** Soll „Birth Rate“ wirklich Teil des Produkts sein, braucht sie eine eigene nichtnegative jährliche Rate plus ausdrücklich angenommene einfache Sterberate; ohne diese ist die Bezeichnung nicht belastbar. Kein Migrationssystem, keine Altersstruktur. Bei A muss geklärt werden, ob die heutige Formel ersetzt wird oder als kleiner, klar getrennter Netto-Korrekturterm bleibt. B kann lediglich eine modellierte Geburtenrate unter dokumentierter Sterbeannahme liefern, keine beobachtete Rate.

Für die Anzeige entweder die letzte realisierte Bestandsänderung mit Datum und Intervall zeigen oder die normale Monatsrate explizit „modellierte Monatsrate“ nennen. Annualisierung `(1+m)^12−1` ist eine Hochrechnung bei konstanten Eingaben, keine gemessene Jahresänderung. Established braucht echte Intervallraten aus seinen Buckets; fehlende Historie nicht nachträglich erfinden.

## 5. Arbeitslosigkeit: Speicherung und genaue Formel

`makro[country]["arbeitslosigkeit"]` startet in Genesis und Heterogeneous bei 0,060. Im normalen Spiel wird sie monatlich durch `macro_calculations.update_makro_oekonomie` aktualisiert. Sie ist **hybrid**: eigener fortgeschriebener Makrozustand mit Startwert, abgeleiteten Wachstumseinflüssen, Zufall und Krisen; keine Rechnung aus Beschäftigten oder Arbeitsplätzen.

```text
u_event = u_alt + U(0.015, 0.030)  # nur betroffene Länder bei aktivem Event
u_neu = max(0.020,
            u_event + (0.015 − g_neu) × 0.45
                    + (0.052 − u_event) × 0.18
                    + U(−0.001, 0.001))
```

Ohne Krise ist `u_event=u_alt`. Keine ausdrückliche Obergrenze. Das bedeutet keine unbeschränkte Explosion bei den heutigen begrenzten Treibern: die Rückkehrkomponente bleibt stabilisierend; Werte aus fremden/alten Zuständen benötigen dennoch eine explizite Anzeige-/Validierungsstrategie.

Das BIP, das in die Arbeitslosigkeit eingeht, entsteht vorher aus:

```text
bremse_zins = max(0, (zins−0.035)×0.65) × (1.8 wenn zins>0.05 sonst 1)
bs_growth = (aktuelle_Bilanz−vorletzte_BS_History)/vorletzte_BS_History,
            sonst 0 bei fehlender/verwendbar positiver Basis
g_neu = clamp(g_alt + (0.035−zins)×0.25 + (0.015−g_alt)×0.22
              − bremse_zins − max(0,(inflation−0.03)×0.25)
              + U(−0.008,0.006) + event.bip_makel
              + max(0,bs_growth×0.12) + financial_growth_impulse,
              −0.060,0.045)
BIP_neu = max(1000, BIP_alt×(1+g_neu/12))
financial_growth_impulse = clamp(credit_growth×0.10 + fiscal_impulse×0.08
                               − max(0,interest_burden−0.035)×0.06,
                               −0.012,0.012)
```

RNG-Reihenfolge je Land: BIP-Rauschen, Inflationsrauschen, optional Krisen-Arbeitslosigkeit und Krisen-Inflation, anschließend Arbeitslosenrauschen. Die isolierte Beobachtung bestätigt drei bzw. fünf `uniform`-Ziehungen und die exakte Arbeitslosenformel. Neue Workforce-Ziehungen dürfen diesen Stream nicht verschieben.

Established-Coarse hat eine andere Formel:

```text
g_annual = clamp(bucket_growth / max(dt,1/12), −0.08,0.12)
target = clamp(0.052 + (0.015−g_annual)×0.45, 0.02,0.22)
a = 1−exp(−0.18×max(1,dt×12))
u_neu = clamp(u_alt+(target−u_alt)×a
              + hash_normal(seed,datum,"unemployment:<Land>",0,0.0015)×sqrt(dt),
              0.02,0.22)
```

Hier gibt es eine 22%-Obergrenze, andere Rückkehrdynamik und Hash-RNG. Anschließend übernimmt der normale tägliche Burn-in wieder die normale Monatsformel.

## 6. Ursachen und Verbraucher der Arbeitslosigkeit

Unter 1,5 % BIP-Wachstum erhöht der Wachstumsterm die Quote, darüber senkt er sie. Über 5,2 % wirkt die Rückkehrkomponente senkend, darunter erhöhend. Krisen erhöhen die Quote direkt und über das BIP; Zufall kann in beide Richtungen wirken. Zins, Inflation, Bilanz, Fiskalpolitik und Kredit wirken über das zuvor berechnete BIP. Produktion, Bevölkerung und Firmen sind **kein direkter Arbeitsplatz-Zähler**. Indirekte Rückkopplungen bestehen über Rohstoff-/Produktpreise, CPI, regionale Nachfrage und Unternehmensentwicklung.

| Verbraucher | Funktion / Wirkung | Takt |
|---|---|---|
| Inflation | `update_makro_oekonomie`: Arbeitsmarktdruck `(0.048−u)×0.25`; zusätzlich CPI-Ziel, Bilanz-, Kredit-, Rohstoff- und Zufallsimpulse | monatlich |
| Bevölkerung | `update_population`: Abzug oberhalb 8 % | monatlich |
| Landesnachfrage | `_country_demand_weight`: `max(.65,1−max(0,u−.05)×2)`; wesentliche Güter mindestens .90 | tägliche Produktion |
| Staatsfinanzen | `fiscal.update_country_financials`: automatische Stabilisatoren `max(0,u−.052)×.42` plus Rezessionsterm | monatlich |
| Staatsrating | `sovereign_rating_target`: begrenzter Scorebeitrag aus `(0.08−u)×8`; weiter zu Zinsaufschlägen/Bonds | Ratingaktualisierung |
| Globale Makrolage | `global_macro._country_aggregates`: BIP-gewichtete Quote; VIX-Stressterm oberhalb 7 % | täglich |
| Marktregime | `market_regime.update_market_regime`: ungewichteter Landesmittelwert; Credit-Stress oberhalb 7,5 % | Regimeaktualisierung |
| Psychologie | `psychology`: Rezessionsfurcht oberhalb 7 %; weiter zu Asset-Erwartungen | Marktaktualisierung |
| Erwartungen | `expectations.update_daily_expectations`, `record_macro_report`: erwartete Quote, Krisenziel, Überraschung; Arbeitslosenüberraschung mit Faktor −2,2 | täglich / Monatsbericht |
| Veröffentlichung | Monatsbericht, `economic_calendar` mit tatsächlicher/erwarteter Quote und `country_ALO`, Makroanalytik / Labor Stress über 8 % | Bericht / sichtbare UI |
| Persistenz | `MAKRO_HISTORIE` ALO, Checkpoint, SQL `unemployment` | Bericht / Save |

Die Monats-CPI-Formel lautet `clamp(inflation_nach_Event + (0.048−u_neu)×.25 + (0.020−inflation_nach_Event)×.28 + bs_growth×.22 + financial_inflation_impulse + commodity_CPI_impulse + U(−.003,.003), −.08,.12)`. Der Policy-Entscheid am Monatsende nutzt Wachstum und Inflation, Arbeitslosigkeit damit indirekt.

## 7. Bereits vorhandene Workforce-nahe Konzepte

Keine Beschäftigten, Jobs, Staffing-Bestände, Erwerbsbeteiligung, Löhne, Human-Capital-Pools oder qualifikationsabhängigen Arbeitsengpässe gefunden. Vorhanden sind Arbeitslosigkeit, Auslastung, Inputverfügbarkeit, Lieferengpass, Produktionsscore, Kapazität, Revenue Growth und regionale Branchenprofile. Sie sind ökonomische Signale und dürfen nicht noch einmal als eigener Arbeitskräftemangel gezählt werden.

`worker`/Live Worker bezeichnet den Simulationsprozess und den Persistenz-Writer. Fonds-`skill` ist Managerfähigkeit. Heterogeneous-`productivity` ist ein **temporärer Initialisierungsfaktor** für die Verteilung des BIP, keine laufende Arbeitseffizienz oder persistierte Qualifikation. Die Suchbelege liegen in `.cache/workforce-audit/source-search.txt` und `labor-search.txt`.

## 8. Die exakt 16 kanonischen Sektoren

`core/companies.py:BRANCHEN` ist das Startuniversum; `core/label_codes.py:SECTOR_CODES` enthält stabile IDs und historische Label-Aliase. Display und kanonischer Branchenname sind die folgenden deutschen Namen. Anfangs vier Unternehmen je Land und Sektor, insgesamt `20×16×4=1.280`; Lifecycle/IPO können die spätere Anzahl verändern.

| Name / Display | Stabile ID |
|---|---|
| Automobil | AUTOMOTIVE |
| Chemie | CHEMICALS |
| Öl und Gas | OIL_GAS |
| Stromerzeuger | POWER_UTILITIES |
| Maschinenbau | INDUSTRIAL_MACHINERY |
| Telekommunikation | TELECOM |
| Einzelhandel | RETAIL |
| Konsumgüter | CONSUMER_GOODS |
| Finanzen | FINANCIALS |
| Edelmetallförderer | PRECIOUS_METALS_MINING |
| Gesundheit | HEALTHCARE |
| Technologie | TECHNOLOGY |
| Immobilien | REAL_ESTATE |
| Transport und Logistik | TRANSPORT_LOGISTICS |
| Verteidigung | DEFENSE |
| Landwirtschaft | AGRICULTURE |

Die [vollständige Sektorinventur](workforce-sector-inventory-2026-10-07.md) enthält alle Output-Codes, gewichteten Input-Codes, Bewertungs-/FCF-/Dividendenprofile, Kapazitätsmodifikatoren und die Länderfokus-Zuordnung. Dies sind gelesene Istwerte, keine neu vorgeschlagenen Workforce-Prozentsätze.

## 9. Wirtschaftliche Rolle und qualitative Workforce-Tendenzen

LOW / MEDIUM / HIGH sind **Diskussionsvorschläge**, keine Anteile und keine neuen Konstanten. „Monatsresultat“ meint den in Abschnitt 11 beschriebenen einzigen künftigen Unternehmens-Hook. Sektorunterschiede entstehen später aus einem kleinen Mix, nicht aus 16 separaten Mechaniken.

| Sector | Category | Current economic role | Existing size/capacity driver | Basic tendency | Skilled tendency | Highly Qualified tendency | Recommended workforce hook |
|---|---|---|---|---|---|---|---|
| Automobil | industrial | Fahrzeuge, Komponenten, Batterien | Umsatz → Kapazität; cyclical ×1,14 | MEDIUM | HIGH | MEDIUM | Monatsresultat, Skilled-Engpass |
| Chemie | industrial | Grundstoffe, Kunststoffe, Wirkstoffe | Umsatz → Kapazität; industrial ×1,00 | MEDIUM | HIGH | HIGH | Monatsresultat, Skilled/HQ |
| Öl und Gas | resource extraction | Öl, Gas, Kraftstoffe | Umsatz → Kapazität; industrial ×1,00 | HIGH | HIGH | LOW | Monatsresultat, Basic/Skilled |
| Stromerzeuger | industrial | Strom, Wärme, Wasserstoff | Umsatz → Kapazität; essential ×0,72 | MEDIUM | HIGH | MEDIUM | Monatsresultat, Skilled |
| Maschinenbau | industrial | Metalle, Maschinen, Anlagen, Verkehrsmittel | Umsatz → Kapazität; industrial ×1,00 | MEDIUM | HIGH | MEDIUM | Monatsresultat, Skilled |
| Telekommunikation | knowledge-tech | Mobilfunk, Daten, Kommunikation | Umsatz → Kapazität; essential ×0,72 | LOW | HIGH | HIGH | Monatsresultat, Skilled/HQ |
| Einzelhandel | consumer-service | Handel über Logistik-/Zahl-/Lagerdienste | Umsatz → Kapazität; industrial ×1,00 | HIGH | MEDIUM | LOW | Monatsresultat, Basic |
| Konsumgüter | industrial / consumer-service | Lebensmittel, Kleidung, Haushalt, Luxus | Umsatz → Kapazität; discretionary ×0,92 | HIGH | MEDIUM | LOW | Monatsresultat, Basic/Skilled |
| Finanzen | finance | Kredit, Versicherung, Anlage, Risiko | Umsatz → Kapazität; discretionary ×0,92 | LOW | HIGH | HIGH | Monatsresultat, Skilled/HQ |
| Edelmetallförderer | resource extraction | auch Industrie-/Spezialmetalle und Mineralien | Umsatz → Kapazität; industrial ×1,00 | HIGH | HIGH | LOW | Monatsresultat, Basic/Skilled |
| Gesundheit | knowledge-tech / consumer-service | Medizin, Versorgung, EDU-Dienstleistung | Umsatz → Kapazität; essential ×0,72 | MEDIUM | HIGH | HIGH | Monatsresultat, Skilled/HQ |
| Technologie | knowledge-tech | Chips, Hardware, Software, Cloud, Forschung | Umsatz → Kapazität; cyclical ×1,14 | LOW | HIGH | HIGH | Monatsresultat, HQ/Skilled |
| Immobilien | industrial / consumer-service | Baustoffe und Immobiliendienstleistung | Umsatz → Kapazität; industrial ×1,00 | HIGH | HIGH | MEDIUM | Monatsresultat, Basic/Skilled |
| Transport und Logistik | consumer-service | Fracht, Lager, Verkehr, Entsorgung | Umsatz → Kapazität; industrial ×1,00 | HIGH | HIGH | LOW | Monatsresultat, Basic/Skilled |
| Verteidigung | industrial / knowledge-tech | Rüstung, Legierungen, Elektronik, Fahrzeuge | Umsatz → Kapazität; cyclical ×1,14 | MEDIUM | HIGH | HIGH | Monatsresultat, Skilled/HQ |
| Landwirtschaft | resource extraction | Agrar-/Tierprodukte, Nahrung, Saatgut | Umsatz → Kapazität; essential ×0,72 | HIGH | MEDIUM | LOW | Monatsresultat, Basic |

Das Spiel modelliert Produkte breiter als Branchenüberschriften suggerieren: „Edelmetallförderer“ umfasst auch Eisenerz, Kupfer und seltene Erden; „Einzelhandel“ produziert hier Logistik-/Zahl-/Verpackungsdienste. Workforce-Mixe müssen diesen tatsächlichen Rollen folgen.

## 10. Unternehmensproduktion, Kapazität und Wachstum

Normaler Monatsbericht: **Makro → Unternehmen → Insolvenz/Replacement → Rohstoffe → Produktion einschließlich Bevölkerung → Crypto → Crypto-Lifecycle**. An anderen Tagen läuft tägliche Produktion. Am Berichtstag wird tägliche Produktion übersprungen; es gibt keinen zweiten Kapazitätsschritt desselben Tages.

`_company_capacity` bildet `B=max(12,sqrt(max(1,revenue))/95 × (1+clamp(fcf_margin,−.35,.45)))` und dann `C=max(8,.75×bestehende_Kapazität+.25×B)`. `_company_capacities` schreibt C zurück und verteilt sie nach `output_mix` auf Produkte. Das ist eine täglich wiederkehrende, umsatzbezogene Rückführung, kein linearer Beschäftigtenbestand.

Globale Produktnachfrage: Haushaltsbasket aus Weltbevölkerung/1 Mio.; sektorale Aktivität `Σ C×(.45+.25×utilization+1.4×max(0,clamp(revenue_growth,−.08,.12)))`; Nutzerbranchen- und gewichtete Inputnachfrage. `_product_demand` summiert Haushaltsbedarf, bei allgemeinen Nutzern `total_activity×.020`, für benannte Nutzerbranchen jeweils `activity×.085` und sektoralen Inputbedarf `×.38`; nach produktspezifischer Textur mindestens `initial_demand×.28`. Rohstoffnachfrage ist mindestens 18, sonst `primary_usage×.55 + consumer_base×Rohstoffgewicht`. Damit vergrößert Population unmittelbar die Konsumbasis, nicht die Unternehmensbeschäftigung.

Regionale Nachfragegewichte verwenden `max(.10,(P/20 Mio.)×growth_factor×unemployment_drag×rate_drag×product_focus)`: `growth_factor=1+clamp(g×3,−.20,.25)`, `rate_drag=max(.70,1−max(0,zins−.035)×4)`, `unemployment_drag=max(.65,1−max(0,u−.05)×2)`. Für discretionary zusätzlich `growth_factor×(1+max(−.15,g×4))`, `rate_drag×.95`; für essential `unemployment_drag≥.90`, `rate_drag≥.92`. Globale Nachfrage wird proportional zu diesen Gewichten über Länder verteilt. Keine neue Einwohnerziehung.

Produzierte Menge für verarbeitete Produkte:

```text
capacity = max(initial_supply×.72, aggregierte_Firmenkapazität, Nachfrage×.88)
potential_supply = capacity × input_availability
supply = clamp(potential_supply, Nachfrage×Profiluntergrenze,
                               Nachfrage×Profilobergrenze)
```

Rohstoffe nutzen mindestens `initial_supply×.76` und entsprechende Angebotskorridore; gemeinsame Schocks wirken zusätzlich. Inventar, Glättung, Shortage und Preisdruck werden weitergeschrieben. Unternehmensauslastung ist der outputgewichtete Wert `clamp(demand/supply,.35,1.25)`, kein Anteil wirklich beschäftigter Arbeitnehmer. Firmenoutput-History und SQL `company_output` zeigen **Kapazität×Outputanteil**, keine strikt auf einzelne Firmen verteilte tatsächliche globale Produktionsmenge.

`_update_company_utilization` erzeugt täglich:

```text
pricing_power = clamp(weighted_price_pressure−.10,−.35,.45)
score = clamp(.03 + (utilization−.70)×.35 + pricing_power×.25
                  − shortage×.20 + (input_availability−.75)×.15,−.35,.35)
wenn shortage>.20:
    growth = min(.18, (shortage×.13 + max(0,utilization−.90)×.05)
                     × (.55+min(.45,input_availability×.45)) × sector_multiplier)
sonst wenn utilization<.50: growth=−.006
sonst: growth=.005
C_nachher = max(8,C×(1+growth))
```

Die Kapazität wird am nächsten Produktionstag wieder in Richtung Umsatzbasis gemischt. Ein Modifier am persistenten C verändert damit einen Rückkopplungspfad. Produktkorridore, Mindestangebot und Nachfrage-Floor können kleine Änderungen zugleich überdecken.

Monatliche Unternehmensentwicklung: `result` enthält `U(−.18,.18)`, Auslastung, Produktionsscore, Lieferengpass nach Input-Hedge, Refinanzierung, Region und Krisen. `sector_factor` enthält Energie/Metalle, regionalen Faktor und Hedge-Abschwächung. In `update_stock_fundamentals`:

```text
health = clamp(.78×health_alt+.22×result,−.50,.50)
effective_result = .35×result+.65×health
monthly_growth = clamp(g/12+.18×effective_result+.10×(sector_factor−1),−.12,.12)
revenue_neu = max(1,revenue_alt×(1+monthly_growth))
margin = clamp(Sektorgrundmarge+.06×result+.16×health+.05×(sector_factor−1),−.08,.35)
FCF = revenue_neu×margin
EPS = max(.1,FCF/Anzahl_Aktien)
dividend_yield = clamp(Sektorgrunddividende+.08×margin−.08×max(monthly_growth,0),0,.08)
```

Finanzen buchen FCF/12 mit Sektorfaktor, Zinsaufwand, Cash, Schulden und Kapitalrückführung; Hedge kann FCF anschließend anpassen. Rating, Repricing und Dividenden folgen. Insolvenz benötigt unter anderem mindestens neun Distress-Monate, sehr wenig Cash, hohe Verschuldung, schwache Cash-Erzeugung und Default-Rating/Score; `fill_company_universe` ersetzt Ausfälle. IPO-/Produktionssignale verwenden Kapazitätswachstum und Knappheit, keinen Arbeitsmarkt.

Länderboni: `_country_sector_bonus = sector_focus × clamp(1.05−default_probability×.75,.72,1.08)`. Sie verteilen regionale Angebotsanteile; diese werden auf das globale Angebot normalisiert. Sie erhöhen nicht einfach das globale Firmenangebot. `company_regional_factor` verbindet lokale Lücken, Preisdruck, Import-/Exportposition und Rating, begrenzt .78–1.18. Anfangsfokus hat vier Branchen; `_maybe_rebalance_country_profiles` verschiebt ihn nach mindestens fünf Kalenderjahren. Kein separater aggregierter Sektor-Wachstumsbestand und keine Beschäftigungsbilanz.

## 11. Kandidaten für einen kleinen Workforce-Hook

| Hook / exakte Funktion | Takt / RNG | Weiterwirkung | Doppelzählung und technische Kosten | Urteil |
|---|---|---|---|---|
| effektive, temporäre Kapazität in `_company_capacities` / `update_production_chain` | täglich, zusätzlicher Faktor ohne RNG | Angebot → Preise, Inputs, Handel, Unternehmen | Kapazitätsgrundzustand trennen; Country- und Firmenmengen konsistent halten; Floors können Wirkung maskieren; O(N) täglich | später möglich, größerer Änderungsumfang |
| persistentes Kapazitätswachstum in `_update_company_utilization` | täglich, ohne neue Ziehung | kumulierte Kapazität und alle Produktionskanäle | bestehendes Growth-/Umsatz-Rebaseline; wiederholter Faktor kann aufschaukeln; O(N) | für V1 vermeiden |
| kleiner additiver Unternehmensresultat-Beitrag in `update_monthly_companies` | einmal pro Bericht, ohne RNG | über `update_stock_fundamentals` zu Umsatz, Marge, FCF, Cash, Rating, künftig Kapazität | getrennt von Güterknappheit; nicht zusätzlich in Score, Kapazität oder u buchen; konstante Cache-Abfrage pro Firma | **bevorzugter V1-Hook** |
| Modifier an `sector_factor` in `update_monthly_companies` | monatlich, ohne RNG | Wachstum, Marge **und** Cashflow-Finanzfaktor | Sektor-Hedge würde Arbeitsmangel mitabsichern; mehrfache Anwendung möglich | weniger sauber als separater Resultat-Beitrag |
| direkter BIP-/u-Zuschlag in `update_makro_oekonomie` | monatlich, ohne RNG | sofort zahlreiche Makrokanäle | bewirkt weitere Effekte über Inflation, Fiskalpolitik und Bevölkerung | zusätzlich zum Firmen-Hook vermeiden |

Der bevorzugte Beitrag muss nach einer eindeutig definierten Umrechnung der Länder-/Sektormismatchs entstehen und als eigene kleine Größe vor dem Fundamentaldatenaufruf eingehen. Er ist keine weitere Güterknappheit und wird nicht durch Unternehmens-Hedge neutralisiert. Ein `result`-Beitrag von .01 bedeutet **einen Indexpunkt von 0,01**, nicht direkt 1 % zusätzliche Produktion. Werte und Limits müssen deshalb nach Abschnitt 17 kalibriert werden. Für Established-Coarse ist ein entsprechender einmaliger, zeitnormalisierter Fundamentals-Beitrag nötig, nicht allein der Live-Hook.

## 12. Empfohlene Angebotsbasis

Heutige Bevölkerung bedeutet Gesamtbewohner / abstrakte Verbrauchergröße. Sie ist weder Working-Age Population noch Labour Force. A: Gesamtpopulation direkt aufteilen ist am kleinsten, behauptet aber implizit volle Erwerbsbeteiligung. B: `L=P×participation`, dann drei Anteile, ist fast ebenso billig und semantisch sauberer. C: vorhandene Beschäftigung wiederverwenden ist unmöglich, weil es keinen solchen Bestand gibt.

**B empfohlen:** ein fester, globaler Beteiligungsparameter ohne Altersstruktur. `Supply_k=L×share_k`, Anteile summieren sich zu 1. Kein zusätzlicher Faktor `(1−u)` vor einer eigenen Arbeitslosigkeitsberechnung: verfügbarer Erwerbspool und tatsächlich Beschäftigte müssen unterschieden werden. Keine Beteiligungszahl oder Anteile werden hier festgelegt.

## 13. Empfohlene Unternehmensnachfragebasis

Marktkapitalisierung schwankt mit Kursen und ist als Arbeitsplatzbedarf ungeeignet. Tatsächliche Produktion fällt bereits bei Inputmangel und würde Arbeitsbedarf prozyklisch wegdefinieren. Revenue ist verständlich und monatlich, aber mit sektorabhängiger Kapitalintensität und Preisbasis belastet. Size Tier ist grob und nach dem Start nicht überall maßgeblich. Sektor allein ignoriert Firmengröße.

**Beste vorhandene V1-Basis: letzte reguläre Produktionskapazität × Sektor-Arbeitsintensität × Sektor-Mix**, monatlich eingefroren. Kapazität ist bereits umsatzgebunden und unterdrückt kurzfristige Kursvolatilität. Ihre sqrt(Umsatz)-Skalierung macht sie jedoch zu einem abstrakten Bedarfproxy, **nicht zu Menschen oder Jobs**. Für echte Kopfzahlen wäre eine separate Umsatz-/Produktivitätskalibrierung notwendig.

Supply und Demand brauchen gemeinsame Einheiten: ein versionierter, fester Referenzmaßstab für Workforce-Äquivalente, nicht „Millionen Einwohner gegen Produktmengen“. Nicht monatlich jedes Land auf perfekte Deckung renormalisieren; das würde Engpässe löschen. Vor Kalibrierung keine präzisen Beschäftigtenzahlen im UI versprechen. Die vorhandenen Heterogeneous- und Established-Verteilungen müssen beim globalen Maßstab berücksichtigt werden.

Konkreter Diagnosebefund: Das Verhältnis der höchsten zur niedrigsten Länder-Kapazität pro Einwohner ist im untersuchten Genesis-Start 1,00, im Heterogeneous-Start bereits **4,74**. Ein pauschaler Maßstab ohne Sättigung könnte daher allein aus Startgröße große Engpässe erzeugen. Diese Beobachtung stammt aus einem Seed, ist keine allgemeine Verteilungsgarantie und begründet weitere Kalibrierung statt automatischer Gleichmachung.

## 14. Länderaggregation und Ablage

Ein Durchlauf über Unternehmen: `Demand[c,k]=Σ proxy_company×intensity_sector×mix_sector,k`. Angebot aus P/Beteiligung/Anteilen. Pro Pool `gap=Supply−Demand`, `shortage=max(0,Demand−Supply)/max(epsilon,Demand)` und `surplus=max(0,Supply−Demand)`; „Mismatch“ sollte ausdrücklich diese Angebots-/Bedarfsrelation meinen. Positiver Überschuss ist kein Beweis für tatsächliche Arbeitslosigkeit.

Persistieren: Modellversion, Länderanteile, Referenzparameter bzw. deren stabile Konfigurationsidentität, letztes Berechnungsdatum und **die bis zum nächsten Bericht wirksamen eingefrorenen Resultat-Beiträge**, soweit für exakte Fortsetzung erforderlich. Abgeleitete aktuelle Summen möglichst nur kleiner Runtime-Cache; keine pro-Firma Workforcespiegel oder umfangreichen History-Dictionaries. Fehlende Cachewerte kontrolliert rekonstruieren. Eine Rekonstruktion aus inzwischen täglich veränderter Kapazität darf niemals den zuvor eingefrorenen Monatsbeitrag ersetzen.

## 15. Vergleich Arbeitslosigkeit A/B/C

| Modell | Vorteil | Problem |
|---|---|---|
| A: Mismatch schiebt heutige Gesamtquote | eigener Arbeitsmarktimpuls sichtbar | Gesamtquote wirkt schon stark; zusätzlich Firmenmalus kann denselben Mismatch zweimal wirksam machen |
| B: Poolquoten aus Supply/Demand, Gesamtquote gewichtetes Ergebnis | scheinbar konsistente neue Beschäftigungsbilanz | heutige Bedarfgrößen sind keine Jobs; Austausch der Makroformel verändert Inflation, Population, Fiskal-/Marktregime und historische Welten |
| C: Gesamtquote bleibt, Poolquoten werden darum verteilt | bestehende Makromechanik erhalten, kleine Darstellung | ein normierter Verteilungsalgorithmus nötig; Poolquoten sind modellierte Allokation, keine aus echten Jobs abgeleiteten Statistiken |

## 16. Empfehlung zur Arbeitslosenintegration

**C als spätere optionale Anzeige; für die kleinste V1 zunächst Gesamtquote plus Pool-Mismatch.** Kein Workforce-Zuschlag auf die maßgebliche Quote, wenn bereits der Unternehmens-Hook verwendet wird.

Falls Kategoriequoten angezeigt werden: qualifikationsgewichteter Mittelwert muss exakt der gültigen Gesamtquote entsprechen. Mismatch nur zur relativen Verschiebung verwenden, dann unter `0≤u_k≤1` mit Erhaltung der gewichteten Summe projizieren. Naives Clamping nach Zentrierung verletzt diese Summe. Bei leerem Pool keine Division; bei ungültiger Gesamtquote ausdrücklich keine vorgetäuschte konsistente Zerlegung. Gesamtzahl verfügbarer Erwerbspersonen nicht mit beschäftigten Personen vermischen. Diese zusätzliche Allokation ist für V1 verzichtbar.

## 17. Effektstärke und Stabilität

Die Diagnose verwendet unveränderte Produktionsfunktionen ausschließlich auf Kopien; sie ersetzt keinen gekoppelten Simulationslauf. Drei verschiedene Einbauarten haben sehr unterschiedliche Bedeutung:

| Betrag | persistenter Level-Faktor täglich, 365 Anwendungen | Level-Faktor monatlich, 12 Anwendungen | `sector_factor` + Betrag: Wachstum / Marge im Monat | `result` + Betrag: Wachstum / Marge im ersten Monat |
|---|---|---|---|---|
| 1 % / .01 | ×37,78 | ×1,127 | +0,10 / +0,05 Prozentpunkte | +0,08874 / +0,0952 Prozentpunkte |
| 3 % / .03 | ×48.482,72 | ×1,426 | +0,30 / +0,15 Prozentpunkte | +0,26622 / +0,2856 Prozentpunkte |
| 5 % / .05 | rund ×54 Mio. | ×1,796 | +0,50 / +0,25 Prozentpunkte | +0,44370 / +0,4760 Prozentpunkte |
| 10 % / .10 | rund ×1,28×10^15 | ×3,138 | +1,00 / +0,50 Prozentpunkte | +0,88740 / +0,9520 Prozentpunkte |

Die Level-Spalten zeigen reine Wiederholungsmultiplikation als Gefahr, **nicht** die gemessene Kapazitätsentwicklung im Spiel: dort dämpft zusätzlich die .75/.25-Umsatz-Rückführung. Negative Faktoren können entsprechend einen dauerhaften Schwund verursachen. Ein temporärer Faktor auf effektive Kapazität kumuliert selbst nicht, kann aber wegen Produktionsfloors teilweise wirkungslos bleiben.

Beim Resultat-Hook wandert der Beitrag über Operating Health weiter: bei dauerhaftem `δ` konvergiert dessen Differenz zu δ; damit ΔMonatswachstum zu `.18δ` und ΔMarge zu `.22δ`, solange Caps nicht greifen. Die zwölfmonatige isolierte Wiederholung bei `g=.015`, neutralem Ausgangsresultat und Sektorfaktor 1 ergibt Umsatzunterschiede von +1,778 %, +5,422 %, +9,184 % bzw. +19,134 % für δ=.01/.03/.05/.10. Das ist eine Schattenrechnung ohne Markt-, Insolvenz- oder Makrorückkopplung. Der monatliche Zufallsresultatbereich ist ±.18; ±.01–.03 ist klein daneben, aber über viele Monate trotzdem sichtbar. Ein dauerhafter Bonus bei bloßem Überangebot würde langfristig alle Firmen aufblasen. Deshalb einen gesättigten Mismatch-Term mit neutraler Deckung und kleiner bzw. zunächst ausschließlich negativer Engpasswirkung bevorzugen; Überschuss nicht unbegrenzt belohnen.

**Bewertung:** ±1–3 % temporäre Effizienz oder Resultat-Beiträge im Bereich ±.01–.03 sind geeignete Diagnosebereiche, keine garantierte sichere Kalibrierung. ±5 % merklich und für V1 nur nach gekoppeltem Nachweis; ±10 % kein kleiner Default. Kein täglich wiederholter direkter Kapazitäts-Level-Faktor. Vor tatsächlicher Freigabe mindestens gepaarte Genesis/Heterogeneous-Jahresläufe, Rezession/Knappheit, Save/Load-Fortsetzung und Established-Coarse/Burn-in-Handoff samt Langfristverteilung prüfen. Dieser Audit ändert keine dieser Pfade.

## 18. Optionen für Workforce-Entwicklung

Feste Anteile: geringster Zustand, volle Reproduzierbarkeit; P verändert trotzdem Poolgröße und Firmen verändern Bedarf. Langsame nachfragegerichtete Drift: kleiner Zustand, aber Rückkopplung zur eigenen Firmenentwicklung und nötige Trägheit/Bounds. Basic→Skilled→HQ: braucht Übergangsraten und Flusserhaltung; behauptet faktisch Qualifizierungsprozesse. BIP-/Produktivitätsdrift: Gefahr, Konjunktur als Ausbildung zu behandeln; H-Produktivität ist nur Startroot. Sektorstruktur: vorhandene Informationen, aber zyklischer Bedarf ist keine gesicherte langfristige Qualifikation.

## 19. Empfohlene V1-Entwicklung

**Statische Qualifikationsanteile**, Poolgrößen verändern sich mit Bevölkerung. Monatlich dynamische Nachfrage/Mismatchs liefern bereits wirtschaftliche Veränderung. Sehr langsame anteilserhaltende Drift erst später, falls die statische Version zu wenig Unterschiede zeigt; keine Schulen/Trainings oder implizit schnelle Umschulung bei einem Engpass.

## 20. Genesis

20 Länder × 20 Mio. = 400 Mio.; gleiche Arbeitslosenquote 6 %. Gemeinsamer Mix und gemeinsamer Beteiligungsparameter sind plausibel. 64 Unternehmen je Land, aber verschiedene Branchenprofile, Outputs und Länderfokus. Workforce-Zustand vor erster Produktion initialisieren; Initial-/Load-Warm-up darf keinen Monatsfortschritt buchen. Bestehender Genesis-RNG muss exakt weiterlaufen; neue Featureversion verändert erwartungsgemäß die Wirtschaft, darf aber keine versteckten Zufallsziehungen hinzufügen.

## 21. Heterogeneous

400 Mio. verteilt über fünf bestehende Klassen: 2 sehr große (35–50 Mio.), 4 große (24–35), 7 mittlere (15–25), 5 kleine (8–17), 2 sehr kleine (5–10). `generate_roots` erzeugt Population über separaten Seed-Stream; BIP wird aus Population × Faktor .70–1.40 unter Budget- und Konzentrationsgrenzen abgeleitet. Firmen bleiben anfangs 4 je Land/Sektor; Größen und Ländergewichte sind heterogen.

Kleine deterministische Mixvariation wäre möglich, sollte aber im ersten Schritt optional bleiben. Falls Produktivitätsbezug: nur beim Start aus dem tatsächlich vorliegenden Root ableiten und versioniert speichern, **nicht** später einen angeblichen Skill-Wert aus aktuellem BIP/Population zurückrechnen. Das würde Konjunktur und Wissen vermischen. Ein eigener Feature-Seed-Stream darf die fünf vorhandenen Start-Streams und Simulations-RNG nicht beeinflussen. Keine tägliche Sondermechanik für diesen Modus. Selbst bei gemeinsamen Anteilen entstehen durch unterschiedliche Poolgrößen und Firmenkapazitäten bereits unterschiedliche Mismatchs.

## 22. Established

Der Standardgenerator nutzt `fast_history_v2`: frühe Jahresbuckets, jüngere Monatsbuckets über ungefähr 19 Jahre, danach **365 echte tägliche Burn-in-Tage**. Zusätzlich gibt es `production_equivalent` bzw. Diagnosepfade mit ausschließlich täglichen Schritten. Die vorhandene Hybrid-Diagnosewelt hat nur zwei Burn-in-Tage; sie beweist keinen vollständigen 365-Tage-Handoff.

Ein nur in `update_monthly_companies` eingebauter Effekt wäre im Großteil der Standardvorgeschichte inaktiv. Sichere Integration braucht den tatsächlichen `_advance_correlated_state`-Pfad: je Bucket echten Supply/Demand aus dessen damaligem Zustand bestimmen, einmalige Wirkung entsprechend dt anwenden und passende Bucketwerte erfassen. Ein Monats-Effekt darf weder einmal pro Jahr unterdosiert noch zwölfmal ohne Zeitbasis überdosiert werden. Die Coarse-Firmenformel skaliert Revenue und Kapazität mit `revenue_factor`; dort ist das Äquivalent des Hooks separat zu definieren.

Am Handoff einmal die nötigen laufenden/monatlichen Featurezustände rebaselinen, anschließend normales Monatsverhalten. Keine fertig dekorierten Poolzahlen am Ende und keine erfundenen historischen Reihen. Neue Economic-/Generator-/Fast-History-Identität erforderlich, sofern Workforce wirtschaftlich wirkt; gespeicherte alte Bundles dürfen nicht als mit Workforce vorhistorisiert gelten. Entweder kompatibler Legacy-Modus oder explizite Aktivierung ab Ladezeitpunkt mit Provenienz.

## 23. UI-Empfehlung

`ui_qt/views/macro_view.py`: Länderübersicht zeigt Arbeitslosigkeit; `CountryDetailView` hat Overview, Production, Trade und Sectors. `CountryOverviewPanel` enthält u.a. einen Unemployment-Chart mit `_ALO`/History-Provider. **Eine sichtbare Population-Kennzahl oder Birth-/Population-Growth-Anzeige ist derzeit in der Qt-Länderansicht nicht vorhanden**, obwohl SQL Population bereits enthält. Der Chart „Growth“ verwendet dort `gdp`/BIP-Niveau, nicht Population Growth; das ist bei neuen Beschriftungen zu unterscheiden.

Kleinste Erweiterung: kompakter Block im bestehenden Overview, Population, zuletzt realisierte/korrekt bezeichnete Wachstumsrate, Gesamtarbeitslosigkeit, darunter drei Zeilen Basic/Skilled/HQ mit Angebot, Bedarf und begrenztem Mismatch-Indikator. Bei abstrakten Einheiten ausdrücklich „Workforce-Äquivalente“ oder relative Deckung; kein scheinbar exakter Beschäftigtenstand. Kein zusätzlicher Haupttab und nicht alle Charts automatisch laden. Optional auf Auswahl ein Population-Chart aus vorhandenem `country_history("population")` und eine monatliche Poolreihe.

`visible_state` lädt Details nur für gewähltes Land und aktiven Tab. `_current` übernimmt skalare Makrowerte, ein verschachtelter Workforce-Cache würde **nicht** automatisch sichtbar: diesen gezielt im Overview-Scope auswählen. Liste und globale Screens bekommen nur benötigte Skalare. Keine kopierten 1.280 Firmen zur Anzeige von drei Länderwerten; vorhandenen Cache verwenden. Existing detail/history query Infrastruktur und `FastChartView` wiederverwenden.

## 24. History-Takt

Heute: `MAKRO_HISTORIE` ALO monatlich, begrenzt 520 und am gleichen Datum dedupliziert. Population ist kein eigener MAKRO_HISTORIE-Schlüssel, sondern `country_daily.population`; `population_growth` ist nur im Checkpoint, **keine SQL-Spalte**. Country-Facts trotz Tabellenname im normalen Spiel am Berichtstag; volle Snapshots sind zusätzliche Ausnahmen. Produkt-/Firmenmengen-Runtimehistories sind täglich, bis 900; Population wird dort nicht als eigene Reihe geführt. Established-Coarse erfasst Population und u als Level bzw. Rate in `history_aggregate`.

Neue Root-Anteile: current-only, bei statischer V1 keine tägliche Reihe. Supply/Demand/Mismatch: maximal Monatsbericht, nur Länderwerte; keine Firma×Pool×Tag-Facts. Wachstumsrate: Monats-/Bucketintervall plus Datum für korrekte Anzeige; optional realisierte Änderung statt zusätzlichem Root. Kategoriearbeitslosigkeit nur bei tatsächlichem UI-Bedarf. Für Charts Monatswerte aus vorhandener Historyarchitektur; keine daily Füllzeilen für unveränderte Größen.

## 25. Persistenz und Schema

Ist: Checkpoint v7, direkte Unterstützung v4–v7; ältere Legacy-Payloads durch `save_migrations`. `makro` ist erlaubtes Top-Level-Feld; verschachtelte zusätzliche Datenfelder sind serialisierbar. Unbekannte **Top-Level**-Felder werden abgewiesen. History-Schema v1, Economic Model `economic-integrity-v1`, Generator v2, Fast History v2, Bundle Schema v1, Heterogeneous Initialization v1. Das sind getrennte Identitäten, keine austauschbaren Versionsnummern.

Die Diagnose bestätigt exakten `makro`-Roundtrip samt vorhandener Population/u für vier bestehende Checkpoints; sie ist kein Migrationstest eines noch nicht implementierten Features. Für V1 kleiner Länder-Unterblock mit Featureversion/Roots/Datum/eingefrorenem Beitrag geeignet. Reiner abgeleiteter Cache kann unpersistiert bleiben, sofern er exakt aus den gespeicherten maßgeblichen Eingaben rekonstruiert wird.

Wenn monatliche Workforce-Charts gewünscht sind: kleine separate `country_workforce_monthly`-Fact-/Current-Struktur oder sorgfältige Erweiterung bestehender Country-Tupel. Separate Struktur vermeidet unbeabsichtigte Verschiebung der vielen positional Row-Mappings. Sie muss aber vollständig in `CURRENT_TABLE_SOURCES`, Schema/Migration, immutable Batch, History-Semantik, Read-Projektion und Recoverypfad eingebunden werden. Nicht als ungeprüfte neue Tabelle an den Writer senden. Noch keine Schemaänderung vorgenommen.

Der einzelne Hintergrund-Writer akzeptiert eingefrorene skalare Rows, nicht Live-Weltobjekte. Journal, Commit-/Save-Barrieren, Recovery und Backpressure bleiben maßgeblich; kleine Workforce-Rows in dieselbe exakte Transaktions-/Journalspur aufnehmen. Kein zweiter Writer, kein separater Thread für drei Pools.

## 26. Kompatibilität bestehender Spielstände

`ensure_population` setzt lediglich fehlende Population/Rate; direkte Checkpoint-Restoration ruft diesen Helper nicht selbst auf, die Runtime-Warm-up-Schicht tut es. Neuer Helper muss daher in **alle** New-/Load-/Bundle-Pfade gelangen, nicht nur in die Legacy-Migration.

Alte Saves: keine Pooldaten als vorhandene Historie behandeln. Fehlende Anteile deterministisch mit gemeinsamem V1-Mix und Provenienz „ab Aktivierung“ ergänzen; vorhandene Bevölkerung/u/Geldpositionen nicht neu würfeln oder rückwirkend ändern. Featuremodell aktiviert wirtschaftlichen Einfluss entweder ausdrücklich ab jetzt oder lässt Legacy-Trajektorie erhalten; das ist eine Produktentscheidung. Datums-/Monatsmarker verhindern doppelte Anwendung beim Laden am Tag 15. Defaults für neue Analyticsfelder NULL/„nicht verfügbar“, nicht Null-Arbeitskräfte und dadurch Vollengpass. H-Bundle-Identität/Seedvalidierung nicht umgehen.

Für eine Umsetzung erforderlich: alle drei Modi speichern/laden, identische aktive Monatsbeiträge und RNG, Tage 14/15/16 sowie Coarse/Burn-in-Handoff, alte Saves ohne Felder, alte DB ohne neue Tabelle und Writer-Recovery mit neuen Row-Batches. Unvollständige Ableitungen beim Save verhindern. Keine fake rückwirkende Workforce-History.

## 27. Performanceabschätzung

Ein monatlicher Scan: 1.280 Firmen × 3 Poolakkumulationen = 3.840 Summierungen, dazu O(1.280) Proxy-/Sektortabellenzugriffe. Angebots-/Gaprechnung 20×3 = 60 Pools; optional 320 Länder-Sektoren für eingefrorene Beiträge. Keine Produktschleife für jeden Pool nötig.

Die isolierte Microbenchmark mit tatsächlichen Heterogeneous-Firmen und drei neutralen Akkumulatoren misst ungefähr **0,5–0,6 ms pro Aggregation** auf diesem Rechner. Das ist nur ein Rechenkern, kein Modell-/UI-/Writer- oder Tagesbenchmark. Konkrete Messwerte stehen in `diagnostics.json`; keine Hochrechnung als garantierte Live-Latenz. Ein kleiner monatlicher Durchlauf spart gegenüber täglichen Scans ~30-fache Frequenz. Monatlich 20 Länderrows → 240 Jahresrows; selbst eine Long-Form mit drei Pools nur 720, statt 1.280×3×365 = 1.401.600 Firmen-Pool-Tagesrows.

Derived Cache bleibt O(20×3), optionale Beitragsmatrix O(20×16). History auf Monatsniveau. Die vorhandenen Jahresstores enthalten je 240 Country-Facts mit zwölf Terminen am 15.; das darf durch das Feature nicht versehentlich wieder zu täglichen Country-Snapshots werden.

## 28. Empfohlener Rechentakt und Reihenfolge

Initial-/Load-Snapshot ohne Fortschritt. Auf Tag 15: Makro aktualisieren; den bisherigen Workforce-Monatsbeitrag genau einmal für Firmen nutzen; Lifecycle durchführen; Population/Produktion aktualisieren; danach aus der nun gültigen Population und Firmenkapazität den **Beitrag für den nächsten Bericht** berechnen und einfrieren. Dies respektiert die bestehende Reihenfolge und verhindert zirkuläre gleichzeitige Nachfrage/Outputeffekte.

Alternativ Aggregation vor Firmenupdate für denselben Bericht möglich, dann wären Population und Kapazität vor dem Bericht die definierten Eingaben. Beide sind kohärent; nicht versehentlich alte Population mit neuen Firmenzahlen mischen. Bevorzugt klare Einmonatsverzögerung mit berechneter Startbasis. Coarse braucht analoge dokumentierte Bucketreihenfolge.

Ein Monats-Scan genügt: zusätzliche materielle-Änderungs-Threshold-Caches pro Firma würden erstmal mehr Signaturen, Invalidierung und Save-Risiko erzeugen als sparen. IPO/Default werden spätestens in der nachgelagerten Monatsaggregation aufgenommen. Wenn das später nicht genügt, nur Universe-/Größenänderungsflag setzen, keinen neuen täglichen Firmenscan. Im normalen Tagespfad nur vorhandenen Beitrag lesen, niemals Roots verändern oder historische Monatswirkungen neu berechnen.

## 29. Wahrscheinliche Implementierungsorte

| Datei / Funktion | Künftiger Zweck |
|---|---|
| neuer kleiner `core/workforce.py` | versionierte Roots, reine Supply/Demand-Aggregation, begrenzter Beitrag; keine Personenobjekte |
| `daten.py`; `adapters/legacy_runtime._ensure_market_fundamentals` | New-/Load-Initialisierung ohne Fortschritt |
| `company_lifecycle.update_monthly_companies` | einziger normaler Wirtschaftseffekt |
| `simulation._run_monthly_company_report_if_due` | definierter monatlicher Aggregationszeitpunkt nach Population/Produktion |
| `production_chains` | vorhandene Kapazitäts-/Populationdaten lesen; keine zusätzliche tägliche Workforce-Simulation |
| `heterogeneous_start.generate_roots` | nur falls eigener Seed-Mix tatsächlich beschlossen; Initversion erhalten bzw. bewusst versionieren |
| `fast_history._advance_correlated_state`, `_capture_bucket`, Handoff | echte Integration in grobe Vorgeschichte und Übergang |
| `checkpoints`, `save_migrations`, `established_world`, `history` | Versionen, Defaults, aktive Beiträge, Provenienz, Bundle-/History-Identität |
| `data_store_schema`, `data_store`, History-Mappings | nur benötigte monatliche Country-Analytics; alle Row-/Current-/Aggregate-Mappings konsistent |
| `visible_state`, ggf. `adapters/legacy_state` | nur sichtbare Country-Skalare und ausgewählter Overview-Block |
| `ui_qt/views/macro_view` | kleiner Länderblock / gewählte Chartabfrage |
| `live_process.economic_signature` und Featuretests | Signatur umfasst heute Population/Workforce nicht; neue Fortsetzungsnachweise vollständige Roots/Beiträge/RNG vergleichen |

Die vorhandene Signatur allein wäre kein ausreichender Beweis für Workforce-Determinismus. Checkpointvergleiche müssen den neuen Zustand ausdrücklich einschließen.

## 30. Minimale V1-Architektur

Ein fester Beteiligungsparameter, drei feste Anteile je Land, eine 16-Sektoren-Mix-/Intensitätstabelle mit stabilen IDs, ein global versionierter Bedarfmaßstab. Ein monatlicher Aggregator liest vorhandene Firmengröße und Population, liefert 60 Poolrelationen und begrenzte Länder-Sektor-Beiträge. Genau ein Resultat-Hook im monatlichen Firmenbericht. Gesamtarbeitslosigkeit bleibt maßgeblich; keine zusätzliche Makrostrafe.

Wirksame Monatsbeiträge, Datum und Roots sind exakter Save-Zustand; aktuelle Summen kleine abgeleitete Caches. Country-Overview bekommt nur seine drei Zeilen plus Population/Nettoänderung/u. Nur bei gewünschtem Chart monatliche Analytics. Die grobe Established-Vorgeschichte berechnet denselben Featurezusammenhang mit expliziter dt-Umrechnung aus damaligem Zustand. Crash-/Save-Barrieren benutzen den bestehenden Writer.

## 31. Was ausdrücklich nicht gebaut werden soll

Keine Berufe, Arbeitnehmerobjekte, Haushalte, Alterskohorten, Ausbildungseinrichtungen, Schulsysteme, Studienplätze, Lohnverhandlungen, Gewerkschaften, Migration, zusätzliche Qualifikationsstufen oder harte Produktionsstopps. Keine täglichen Pool-Firmenspiegel, kein zweiter Hintergrundprozess, keine unsichtbaren UI-Charts, keine Lockerung der Persistenz. Kein eigenständiger Bonus zugleich in Output, Wachstum, BIP und Gesamtarbeitslosigkeit. Kein EDU→Qualifikationsautomatismus. Keine Marktkapitalisierung als direktes Jobangebot. Keine rückwirkend erfundenen Geburten oder Workforce-Reihen.

## 32. Offene Entscheidungen

1. V1 nur ehrliche „Population Growth“-Anzeige (empfohlen) oder echte Birth Rate mit einfacher Sterbeannahme und eigener Modelländerung?
2. Feste Beteiligung und zunächst gemeinsamer Mix (empfohlen); kleine Heterogeneous-Seedvariation schon V1 oder später?
3. Abstrakte Workforce-Äquivalente mit fester globaler Kalibrierung (empfohlen) oder ausdrücklich modellierte Personenbedarfe, die zusätzliche Kalibrierung benötigen?
4. Einziger kleiner Monatsresultat-Hook (empfohlen): nur begrenzte Engpassstrafe oder auch kleiner Überschussbonus? Endgültige Intensitäten, Mixanteile und Effektlimits erst anhand gepaarter Läufe festlegen.
5. Gesamtquote plus Mismatch (empfohlen) oder zusätzlich drei normiert verteilte Kategoriequoten?
6. Bestehende Saves wirtschaftlich unverändert weiterführen oder Workforce explizit ab Aktivierungsdatum ergänzen? Keine rückwirkende Neubewertung.
7. Current-only-Pools für erste UI (empfohlen) oder drei zusätzliche Monatscharts? Die Entwicklung der Population ist bereits historisch abfragbar.

Keine dieser Entscheidungen wurde durch diesen Audit als Implementierungsfreigabe behandelt.

## Nachweise und Grenzen

Reproduzierbar mit `.venv/Scripts/python.exe tools/workforce_population_audit.py`. Ergebnis `.cache/workforce-audit/diagnostics.json`: sechs Bevölkerungsfälle samt Floors und unverändertem RNG; beobachtete Makroformel mit/ohne Krise; echter isolierter Coarse-Aufruf für 20 Länder; vier exakte bestehende Makro-Checkpoint-Roundtrips; zwei vorhandene 365-Tage-Stores read-only, deren Populationsfolgen die Monatsformel ohne Restfehler bestätigen; Sensitivitätsrechnungen auf Kopien und Aggregations-Microbenchmark.

Die vier gespeicherten Zustände umfassen Genesis/Heterogeneous Day 1, eine Hybrid-Established-Diagnose und einen täglichen Established-Diagnosepfad. Die Jahresläufe wurden für diesen Audit **gelesen, nicht neu erzeugt**. Es wurde kein vollständiger neuer Langfristlauf, UI-Interaktionstest, neuer Feature-Crashtest oder kompletter Regressionstest behauptet; ein noch nicht gebautes Feature kann diese Nachweise nicht haben. 177 bestehende Produktions-/Testdateien stimmen mit dem Audit-Beginn bytegenau überein. Änderungen dieses Auftrags beschränken sich auf diesen Bericht, Sektorinventur, Diagnosetool und Auditbelege.

Wichtige Bestandsbefunde für spätere Umsetzung: unterschiedliche Coarse-/Live-Bevölkerungsformeln und Untergrenzen; stale `population_growth` im Coarse-Pfad; monatliche Country-Persistenz trotz `country_daily`-Namen; tatsächliche globale Produktion ≠ Firmen-Kapazitätsoutput; kein aktueller Population-UI-Block; kompakte Signatur deckt Population nicht ab. Diese wurden dokumentiert, nicht im Rahmen eines reinen Audits repariert.

Zentrale nachlesbare Quellen:

- [Normale Populationformel](../src/kojakstreet/core/production_chains.py)
- [Makro- und Arbeitslosenformel](../src/kojakstreet/core/macro_calculations.py)
- [Monatlicher Unternehmensbericht](../src/kojakstreet/core/company_lifecycle.py)
- [Umsatz und Margen](../src/kojakstreet/core/fundamentals.py)
- [Tagesreihenfolge und Report-Sperre](../src/kojakstreet/core/simulation.py)
- [Grobe Established-Vorgeschichte](../src/kojakstreet/core/fast_history.py)
- [Sparse Country-Persistenz](../src/kojakstreet/core/data_store.py)
- [Country-Overview und Chartfelder](../src/kojakstreet/ui_qt/views/macro_view.py)
- [Gezielte Country-Projektion](../src/kojakstreet/visible_state.py)
- [Checkpoint-Felder und Restore](../src/kojakstreet/core/checkpoints.py)
- `.cache/workforce-audit/diagnostics.json` (local evidence)
