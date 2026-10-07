# Politics, Stability & Society – vollständiger Audit

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Stand: 2026-10-07, aktueller Arbeitsstand nach Workforce + Birth Rate V1. Der Nutzer hat den Audit mit „ja bitte“ beauftragt. Das beigefügte Dokument definiert dessen Prüfumfang. **Dieser Auftrag umfasst ausschließlich Analyse und Empfehlungen. Es wurden weder Politik noch UI implementiert und keine bestehenden Produktions- oder Testdateien geändert.**

Das Vorhaben ist als kleines, monatlich beziehungsweise ereignisbasiert betriebenes Modell technisch gut anschlussfähig. Die größten Risiken sind die breite Wirkung eines Staatsrating-Hooks, doppelt eingepreister Wirtschaftsstress, unvollständige Established-Vorgeschichte und die versehentliche Veröffentlichung versteckter Länder- und Parteienarrays. Empfohlen wird ein eigener politischer Kalender, sieben Systemtypen, keine Sitze, zwei beschreibende Ideologieachsen, ein ausgewähltes Land im neuen Tab und zunächst **höchstens ein wirtschaftlicher Hook**: ein kleiner politischer Staatsanleiheaufschlag. Dessen Aktivierung setzt insbesondere eine konsistente Coarse-/Burn-in-Abbildung voraus; der Audit allein bestätigt keine bereits getestete Sicherheit eines noch nicht vorhandenen Modells.

Begriffe im Bericht: **Befund** bezeichnet vorhandenen Code oder gemessenen Istzustand. **Empfehlung** bezeichnet einen zukünftigen Entwurf. Sämtliche neuen Formeln und Grenzen sind Kalibrierungsvorschläge, keine implementierten oder ökonomisch validierten Parameter. Quellenverzeichnis mit geprüften Funktionspositionen am Ende von Punkt 40.

## 1. Bestehender politischer und institutioneller Zustand

**Befund:** Die Länderdefinition enthält Name, Währung, Symbol, Code und Namensstil. Sie enthält weder Regierungssystem noch Parteien, Wahltermine, Regierungskoalition oder politische Stabilität. `government_debt` ist Staatsschuld, kein Regierungsmodell. Die vorhandenen Institutionen sind Zentralbank, vereinfachte Fiskalreaktionen und fundamentbasierte Kreditqualität. Die Laufzeitproben bestätigten dies für Genesis und Heterogeneous mit Seed 1729, jeweils 20 Länder und 1.280 Unternehmen. [Länder], [Makro], [Fiskal], local audit evidence

Persistenzlegende: **CP** = vollständiger Zustand im versionierten Checkpoint; **CD** = `country_daily/current` und gegebenenfalls aggregierte Historie; **WD** = Workforce-Monats-/Currenttabelle; **AD** = Asset-/Company-/Bondtabellen; **EV** = Nachrichten-/Ereignistabellen. Nicht jede CP-Variable hat eine eigene DuckDB-Zeitreihe. „RNG“ meint bestehenden Markt-Python-RNG, soweit nicht anders angegeben.

| Feld / Institution | Formel oder Quelle | Kadenz | Verbraucher | RNG | Persistenz | Politik-Kandidat? |
|---|---|---|---|---|---|---|
| `rating`, `default_probability` | Ratingleiter aus fundamentaler Zielbewertung; jährliche PD aus Tabelle | monatlicher Bericht am 15. | Bonds, Unternehmens-Regionalfaktor, sektorale Produktion, Handel, Portfoliorisiko | nein | CP; Rating CD; PD ableitbar | Rating-Hook V1 ablehnen |
| `sovereign_credit_score/target/pressure` | fünf begrenzte Beiträge aus Wachstum, Inflation, u, Debt/GDP, Zinslast; Migration bei Druck −7/+5 | monatlich, Coarse am Bucket-Ende | Ratingmigration | nein | CP; keine eigenen CD-Spalten | keine zweite Makrostress-Addition |
| `government_debt`, `debt_to_gdp` | Staatsschuld plus annualisiertes Defizit /12; Quote Schuld/GDP | monatlich | Fiskal, Rating, Bonds, CDS | nein | CP; Quote CD | nicht direkt politisch verändern |
| `fiscal_deficit` | GDP × begrenzte Defizitquote mit Stabilisatoren, Zinslast, Konsolidierung | monatlich | Finanzierung, Emissionen, CDS, Makro | nein | CP; bestehende Makrohistorie | kein Partei-Steuerprogramm V1 |
| `fiscal_adjustment`, `fiscal_impulse` | Zielkonsolidierung geglättet mit 0,18; Impuls = Defizitquote −0,025 | monatlich | Wachstum/Inflation und Bondspread | nein | CP | keine zusätzliche Stabilitätsstrafe |
| `sovereign_funding_rate`, `interest_burden` | Ziel = Policy Rate + Ratingspread + positiver Schuldenaufschlag; Glättung 0,20; Last = Quote × Funding Rate | monatlich | Defizit, Fiskalimpulse, Rating | nein | CP | eigener Rückkopplungskanal; V1 nicht zusätzlich öffnen |
| `sovereign_cash_buffer`, `bond_funding_impulse` | begrenzter Liquiditätszuwachs bei bedarfsbezogener Staatsanleiheemission | Emission, monatlich geprüft | Finanzierungspuffer | nein in Buchung; Laufzeitauswahl teilweise RNG | CP | unverändert |
| Government Bond `yield_to_maturity`, `fair_price/price` | Policy Rate + Ratingspread + Termspread + Bilanzspread; Cashflow-Barwert und Sekundärmarktglättung | täglich rotierende Auswahl, max. 120 Quotes/Tag | Bonds, Fonds, globale Kurve, Yield Futures | Quote nein; Emissionen teils RNG | CP, Bond AD | bevorzugter kleiner Hook, Bedingungen Punkt 21 |
| Bond `default_risk` | Rating-PD × Horizon-/Issuertypfaktor, begrenzt | Quote-Refresh | Risikodarstellung; realisierte Spielerabwicklung separat | Quote nein; Spielerdefault eigener RNG | CP, Bond AD | politische Prämie verändert nicht zusätzlich PD |
| `zins`, `balance_sheet` | Zentralbankziel aus Inflation/Wachstum, variable Zinsschritte; QE/QT | Monatsende | FX, Unternehmen, Kredit, globale Liquidität | nein | CP, CD, Makrohistorie | keine Regierung bestimmt Policy Rate V1 |
| `bip_prozent`, `bip_abs` | Mean Reversion, Zins-/Inflationsbremsen, QE/Fiskal/Kredit, Krisen und Rauschen; GDP × (1+g/12) | 15. | Nachfrage, FX, Fiskal, Bewertungen | ja | CP, CD | Wahlfeedback möglich, direkter Hook ablehnen |
| `arbeitslosigkeit` | natürliche u=0,052, Wachstumsabweichung, Rückführung, Krisen und kleines Rauschen | 15. | Nachfrage, CPI, Rating, Fiskal, Bevölkerung | ja | CP, CD | Wahl-/anzeigende Druckvariable, nicht nochmal ökonomisch strafen |
| `inflation` | Arbeitsmarktdruck, Mean Reversion, QE/Fiskal, Rohstoff-/Regionalpreise und Rauschen | 15. | Zinsen, FX, Rating, Erwartungen | ja | CP, CD | wie u |
| `bevoelkerung`, `population_growth`, birth/death, `workforce` | bereits implementierte jährliche Demografieraten; monatliche Bevölkerung; drei Supply/Demand/Coverage-Pools | Bevölkerung/Workforce monatlich; Roots initial | Nachfrage, Company-Workforcebeitrag; ausgewählte Society-Projektion | separate SHA256-Roots; Schritte nein | CP, WD; Population CD | nur vorhandene Gesellschaftsdaten anzeigen |
| `private_credit`, `credit_growth` | geglättetes Ziel aus Wachstum/Zins/Inflation, Kreditbestand wächst /12 | monatlich | Makro/Fiskal | nein | CP; Credit Growth CD | kein neuer Kreditvertrauensfaktor |
| `expected_*` | tägliche geglättete Ist-/Krisenziele; Reports aktualisieren Erwartungen | täglich und Reports | FX, Assets, Kalender, globale Aggregate | nein | CP; Growth/Inflation/Rate CD | bestehenden Reportkanal nicht für Wahlergebnisse umdeuten |
| `growth/inflation/unemployment/rate_surprise`, `macro_surprise_momentum` | Reportabweichung; kombinierter Impuls ±0,08; täglicher Zerfall | täglich/Report | FX, Aktien, Global Macro | nein | CP; kombinierter Impuls CD | kein Wahlereignis in GDP-Surprise schreiben |
| `market_psychology` | sechs globale Faktoren aus VIX, Liquidität, Kurve, Wachstum, CPI, u; Glättung 0,10 | täglich | Aktien, Rohstoffe, Crypto | nein | CP; kein vollständiges eigenes Psychologiearchiv | globale Ansteckung begrenzen; nicht erster Hook |
| Asset `sentiment/fear/euphoria/crowding/expectation/surprise` | Preis-/Fundamental-/Newsreaktion, Zerfall, Reversal, Volatilität | täglich; Fundamentalreport monatlich | Kurse/Volatilität | Psychologie nein; nachfolgende Preisbildung ja | CP; Preise AD | optional späterer lokaler Übergangskanal |
| Asset `news_momentum`, `fund_flow_pressure` | Unternehmensreport beziehungsweise modellierte Fondsflüsse; Preis-/Psychologieinputs | täglich/Report | Aktien-/sonstige Preise | Reportrauschen/Fonds teils ja | CP; indirekte Preise AD | mehrfach konsumiert, kein naiver Wahlimpuls |
| Fonds `underlyings`, Gewichte, AUM/Flows | Mandats-/Styleauswahl; Gewichte aus Cap/Growth/Dividend/Rating; AUM aus Performance/Target/Issuer | Rebalance bedarfsweise monatlich; Flows täglich | Fonds-NAV und Kaufdruck auf Underlyings | teils ja | CP, Allocation AD | Portfolio-Proxy, keine FDI-Buchhaltung |
| Company `company_regional_factor` | Nachfragegap, Preisdruck, Exporte, Importabhängigkeit, Rating; Band 0,78–1,18 | monatlicher Report | Result und Sector Factor, Umsatz/FCF | nein | abgeleitet; Inputs CP, Result AD | nicht zusätzlich beeinflussen V1 |
| Company `production_capacity/capacity_growth` | Engpass/Auslastung/Inputverfügbarkeit, branchenspezifischer Multiplikator | monatliche Production, tägliche Verarbeitung ohne Monatsinvestition | Angebot, Workforce Demand, Handel | nein | CP, Company AD | echte Kapazitätsanpassung, keine explizite grenzüberschreitende Investition |
| `regional_supply/demand/pressure/shortage`, trade | Produktketten, Bevölkerung, Wachstum, u, Zins, Profile, Ratingvertrauen | Tagesflüsse, strukturelle Anpassung monatlich | Unternehmen, Inflation, Handel, UI | weitgehend deterministisch | CP, Trade AD, Aggregate | zusätzliche Nachfrage-/Handelsstrafe vermeiden |
| `economic_profile.sector_focus/product_focus` | Initialisierung; fünfjähriger Fokuswechsel nach realer Hauptbranche; Outputmix nach Chancen | initial, fünfjährig / monatlicher Mix | Produktion, Nachfrage | Hash-/Initprofile, kein Politik-RNG | CP | keine ideologische Subventionierung V1 |
| `waehrungen_staerke` | Realzinsvorteil, erwartetes Wachstum/Surprise, Krisenmalus, Mean Reversion, Rauschen | täglich | sämtliche Währungsumrechnung, Fonds/Player | ja | CP, Forex AD | FX-Hook V1 ablehnen |
| `aktives_event`, `event_dauer`, `economic_shocks` | ein weltweites aktives Krisenobjekt; separater begrenzter Supply-/Demand-Schockmechanismus | täglich | Makro, Preise, Produktion, Erwartungen | Krise ja; Shock-Evaluation nein | CP, Nachrichten EV | keine Wahl in den Krisenslot |
| Steuern, Regulierung, Subventionen | keine eigenständigen entsprechenden Länderparameter oder Regierungspolitiken gefunden | — | — | — | — | nicht neu bauen V1 |
| Ländervertrauen, FDI, `capital_attractiveness` | kein eigenständiges entsprechendes Ländermodell gefunden; globale `liquidity_confidence` ist etwas anderes | — | vorhandene Proxys oben | — | — | neues Signal ohne Verbraucher vermeiden |
| politische Felder/Wahlen | nicht vorhanden | — | — | — | — | neuer kleiner Domainblock erforderlich |

Alle CP-Daten werden als Datenobjekte gespeichert, nicht als ausführbare Objekte. Der Audit ergänzt keine neuen persistierten Spielfelder.

## 2. Ereignis- und Kriseninfrastruktur

`run_event_phase` altert das aktive Ereignis und startet bei freiem Slot mit Wahrscheinlichkeit 0,008 pro Tag eine Krise. Vorhanden sind Generalstreik & Unruhen (ein Land, 30–90 Tage, Wachstumsmalus −0,035), geopolitischer Konflikt (zwei Länder, 60–120 Tage, −0,025) und Versorgungsknappheit/Embargo (ein Land, 45–90 Tage, −0,020). Das Objekt speichert Name, Typ, Länder und GDP-Malus; die Restdauer steht separat. Das Erzeugen der Kandidaten verbraucht bereits Markt-RNG, auch für nicht ausgewählte Kandidaten. Das Energieereignis legt zusätzlich CL-/TTF-Supply-Shocks an. [Ereignisse], [Shocks]

Die Krisen wirken auf Monatsmakro, Erwartungen, Unternehmensresult, FX sowie tägliche Preis-/Volatilitätskanäle. „Civil Unrest“ und „Geopolitical“ sind die einzigen direkten politischen Konzepte; keine Wahl-, Regierungs-, Steuer- oder Regulierungslifecycle existiert. `economic_calendar.py` ist ein aus Erwartungswerten aufgebautes **Anzeigeobjekt**, kein Scheduler. Aktuell entstehen vier Makro-/Zinspositionen je Land, also 80 Positionen in beiden Proben. [Kalender], local audit evidence

Nachrichten haben eine kurze Live-Liste mit höchstens 50 Einträgen; DuckDB speichert News/Eventzeilen. Ereignistyp und Scope werden überwiegend aus Text abgeleitet. Der dauerhafte `structural_event`-Pfad akzeptiert ausdrücklich nur Default, New Company, Crypto Shutdown, Central Bank, Rating Migration, Distress und Recovery. Metadaten werden dabei aktuell als leeres JSON geschrieben. Wahlen würden weder automatisch sauber klassifiziert noch dauerhaft strukturiert archiviert. [Store], [Schema]

**Empfehlung:** Eigener deterministischer politischer Kalender je Land, parallel zu Krisen. Nachrichten und später die Kalenderanzeige wiederverwenden; Wahlergebnis, Regierungswechsel und Aktivierung als explizit typisierte, stabile Ereignisse mit Ergebnismetadata persistieren. Dafür `structural_event` kontrolliert erweitern oder eine kleine politische Ereignistabelle ergänzen. Keine Textheuristik als Wahrheit, kein Besetzen des einzigen Krisenslots, keine Wahl als Supply Shock.

## 3. Investitions- und Kapitalflussmechaniken

**Befund:** Es gibt Country/World/Sector Funds und grenzübergreifende Underlyings, tägliche modellierte AUM-Flüsse, Cash-Reinvestment und Kaufdruck. Es gibt weder eine FDI-Herkunft/Ziel-Bilanz noch konzernweite Länderallokation, Capital Account oder Migration einer Fabrik zwischen Ländern. Positive Fondsflüsse erzeugen Preis-/Newsdruck; die Issuer-Fee-Funktion ist derzeit ein No-op. Fondsflüsse sind Weltmechanik und getrennt von gewöhnlichen Spielertrades. [Fonds]

Regionale Unternehmensattraktivität wirkt über vorhandene Nachfrage-, Import-/Export- und Ratingfaktoren. Produktion baut Kapazität aus Engpass/Auslastung auf. Das ist reales Angebotswachstum, aber kein Geldfluss aus einem Investorenland in ein Empfängerland. Eine neue Oberfläche darf diese bestehenden Größen nicht als „Foreign Direct Investment“ bezeichnen. [Unternehmen], [Produktion]

**Empfehlung:** V1 ohne FDI-System und ohne zusätzlichen Capital-Attractiveness-Skalar. Ein späterer Portfolio-Hook wäre auf globale aktive Fonds begrenzt und dürfte keine passiven Indexmandate, Landesmandate oder Spielerorders verbiegen. Er wäre ein eigener weiterer wirtschaftlicher Hook und benötigt gesonderte Kalibrierung.

## 4. Staatsrisikomechanik

Der Staatsrating-Score ist exakt:

`clamp((g−0,015)×10, −1, 1) + clamp((0,045−π)×8, −2, 0,5) + clamp((0,08−u)×8, −1,5, 0,4) + clamp((0,90−debt/GDP)×3, −3, 0,6) + clamp((0,06−interest_burden)×12, −3, 0,5)`.

Grenzen von 1,60 bis −3,50 führen von AA bis CC; D bleibt realisiertem Default vorbehalten. Die Ratingmigration läuft mit akkumuliertem Druck und maximal einem Schritt pro Monatsaufruf. Der Spread ist `0,0006 + PD×0,60 + sqrt(PD)×0,018`. [Ratingziel], [Ratings]

Gemessenes Formelbeispiel: BBB+ 97,718 bp, BBB 151,456 bp, BBB− 217,177 bp. Ein bloßer Wechsel BBB→BBB− verändert den Ratingspread um rund **65,72 bp** und gleichzeitig PD von 2 auf 3 Prozent. Das liegt deutlich über dem vorgeschlagenen politischen Cap von 25 bp und erreicht außerdem Unternehmen und Handel. Ein vermeintlich „kleiner“ Ratingscore-Zuschlag nahe einer Schwelle kann daher einen großen diskreten Effekt auslösen. Die Genesis-Probe begann bei BBB, während das fundamentale Ziel A mit Score 1,4496 war; aktuelles Rating und Ziel sind nicht identisch. local audit evidence

**Empfehlung:** Staatsrating, PD und realisierte Defaults im V1 unverändert lassen. Politische Marktprämie getrennt deklarieren; keine doppelte PD- oder Ratingmigration aus derselben politischen Lage.

## 5. Psychologie und Erwartungen

Es gibt sechs globale Faktoren: Risk Appetite, Fear, Liquidity Confidence, Inflation Fear, Recession Fear, Speculation. Ziele stammen aus Liquiditätsveränderung, VIX, Kurve, GDP/CPI/u; Glättung 0,10 und Zielbegrenzung ±2. Assetzustände umfassen Fear, Euphoria, Sentiment, Crowding und Surprise. Täglicher Zerfall unter anderem 0,82/0,86/0,90/0,94; Surprise/News wirken auf Signal, Rückkehrbewegungen und Volatilität. [Psychologie]

Makroerwartungen laufen täglich und werden bei Monats-/Zinsberichten aktualisiert. Surprises zerfallen mit 0,92, kombiniertes Momentum mit 0,90. Krisen ändern erwartete Wachstum/Inflation/u-Ziele. Die täglichen Aktienpreise konsumieren `news_momentum` direkt **und** über Psychologie; für Aktien wird es mit 0,75 abgebaut. Monatsberichte überschreiben es mit dem Unternehmensresult. Ein einmaliger Wahleintrag könnte dadurch mehrfach wirken oder am gleichen Tag überschrieben werden. [Erwartungen], [Marktpreise], [Unternehmen]

**Empfehlung:** Wahlausgang und geordneter Übergang zunächst als Nachrichten und politischer Risikokomponent dokumentieren. Keine Wahl in `growth_surprise`, keine direkte Veränderung von GDP oder den makroökonomischen Erwartungszielen. Ein späterer preiswirksamer Übergangsimpuls braucht eigene Event-ID, Start/Ende und eine einzige eindeutig definierte Einspeisestelle; siehe Punkt 22.

## 6. Aktuelle Country-UI-Architektur

`MacroView` enthält eine Länderübersicht, `CountryDetailView` und eine regionale Metrikdetailseite in einem `QStackedWidget`. Der Country-Detail besitzt bereits einen stabilen `QTabWidget` mit **Overview, Production, Trade, Sectors**. Die Qt-Probe bestätigt exakt diese vier Tabs. Der bestehende Kopf zeigt Rating/Default Probability, Trade Balance, Import Dependency, Debt/GDP und Credit Growth. Overview enthält bestehende Makro-/Handelsdiagramme. [Country-UI], local audit evidence

Eine Abweichung zur Produktbeschreibung ist ausdrücklich festzuhalten: **Population ist aktuell zwar im Länderzustand vorhanden, aber weder eigene Spalte der Makrotabelle noch sichtbare Kennzahl des heutigen Country-Detailkopfs/Overview.** Die Tabelle zeigt Region, GDP, Growth, Rate, Inflation, Unemployment, Balance Sheet und Rating. Für die gewünschte künftige Front muss Population daher als kleine Headline-Kennzahl ergänzt werden; das ist kein Verschieben einer bereits existierenden Anzeige. Außerdem trägt ein Overviewchart den Titel „Growth“, verwendet aber die GDP-Levelhistorie. Dieser bestehende Bezeichnungsunterschied wird dokumentiert, im Audit nicht geändert.

`_refresh_active_tab` aktualisiert nur den gewählten Tab; für Navigation wird ein Scope `{view: macro, selection: {region, tab}}` angefordert. Production/Trade können in Produktdetails springen. App-Liveupdates unterscheiden aktive Hauptansicht und veränderte Currenttabellen. Es existiert noch kein Society-Widget und kein `society_politics`-Scope. Die bereits vorhandene `population_society`-Projektion ist ein vorbereiteter Datenpfad, **keine sichtbare fünfte Registerkarte**. [Sichtbarer Zustand], [App]

## 7. Empfohlene Regierungssysteme

Die sieben angefragten Typen reichen aus. Sie beschreiben Wahl-/Regierungsmechanik und die angezeigte Staatsstruktur. Kein Typ liefert ein Wirtschafts-, Stabilitäts-, Produktivitäts- oder Wohlstandsbonuslabel. „Democracy“, „Monarchy“ oder „One-Party“ darf in keiner wirtschaftlichen Formel als Score auftauchen.

Parliamentary und Constitutional Monarchy teilen die parlamentarische Regierungsbildung; das Staatsoberhaupt der Monarchie bleibt beschreibend. Presidential trennt Exekutivmandat vom Parlament, ohne ein zweites komplettes Spiel zu eröffnen. Semi-Presidential benötigt zusätzlich die schlanke Unterscheidung Exekutivpartei/Regierungskoalition. Absolute Monarchy und Authoritarian Republic zeigen Staatsführung ohne fingierte konkurrenzfähige Wahl. One-Party State kann eine Regierungspartei mit interner Führungserneuerung zeigen.

Keine weitere Regierungsform ist technisch nötig. Für V1 keine Junta-, Theokratie-, Failed-State- oder Dutzende Untertypen.

## 8. Regierungssystem-Matrix

Diese Matrix ist ein **Entwurf für abstrahierte Spielmechanik**, keine Behauptung über reale Staaten. Das Spiel hat keine Politiker oder Verfassungsdetails.

| System | Kompetitive Wahlen? | Parteien | Koalition? | Amtszeit / Zyklus | Übergang | Stabilitätsbetrachtung |
|---|---|---|---|---|---|---|
| Parliamentary Democracy | ja, parlamentarisches Mandat | 2–7 | ja; Einzelpartei, Mehrheit oder gestützte Minderheit | fest 4 Jahre | neue Mandatsverteilung und Regierungsbildung | Zusammenhalt, effektive Fragmentierung, gesicherte Unterstützung; kein Demokratiebonus |
| Presidential Democracy | ja, abstrahierte Exekutivwahl | 2–7 | keine Exekutivkoalition V1 | fest 4 Jahre | stärkster Wahlanteil bestimmt Exekutivpartei; bewusst einfache Pluralitätsregel | Kontinuität/Übergang; keine fingierte Parlamentsmehrheit aus Präsidentschaftsvoten |
| Semi-Presidential Democracy | ja, gemeinsamer abstrahierter Wahltermin V1 | 2–7 | parlamentarisch ja | fest 5 Jahre | Exekutivpartei und Kabinettskoalition getrennt; Kohabitation möglich | Zusammenhalt und tatsächliche Regierungskompatibilität; Kohabitation allein kein Malus |
| Constitutional Monarchy | ja, parlamentarisch | 2–7 | ja | fest 4 Jahre | Kabinettswechsel; Krone bleibt beschreibend | gleiche parlamentarische Regeln, kein Kronenbonus |
| Absolute Monarchy | nein | keine | nein | kein automatischer Wettbewerb/Amtsablauf | V1 amtierende Führung, kein simuliertes Erbfolgespiel | unabhängig erzeugte Basis, Kontinuität und vorhandene Krisen; kein Autokratiemalus |
| One-Party State | nein | genau eine Regierungspartei | nein | optionale interne Überprüfung alle 5 Jahre | Kontinuitäts-/Führungsereignis, keine Vote Shares | eigener Kontinuitätszustand; eine Partei bedeutet nicht automatisch perfekte Stabilität |
| Authoritarian Republic | nein | keine künstliche Mehrparteienlandschaft V1 | nein | optionale Führungsüberprüfung alle 5 Jahre | nichtkompetitives Führungsereignis | Kontinuität/Übergangsrisiko unabhängig von Typetikett |

**Empfehlung:** Nichtkompetitive Reviewzyklen dürfen zunächst rein beschreibend bleiben. Der Regierungswechsel selbst muss kein Zufallszwang alle fünf Jahre sein. Kalenderüberschrift „Leadership review“, niemals „Next election“, wenn keine konkurrenzfähige Wahl vorliegt.

## 9. Minimales Parteienmodell

Ein `macro['politics']`-Domainblock pro Land passt zum vorhandenen Country-Zustand. Parteien sind höchstens sieben kleine Datenobjekte. Dauerhafte Felder: `id`, `name`, `economic_axis`, `social_axis`, `mandate_share`, `latest_vote_share` nur nach echter simulierter Wahl, `in_government`. Regierungsmitgliedschaft wird aus einer autoritativen Liste von IDs abgeleitet, nicht parallel unabhängig gespeichert.

Countryblock: Modell-/Kalibrierungsversion, System, Aktivierungsdatum/Provenienz, Parteien, Regierungsparty-IDs, optional Exekutivpartei, Government Status, Supporter-IDs einer Minderheitsregierung, nächste/letzte Wahl, Election Sequence, Formation Date, strukturelle Basis, politische Stabilität, Makrodruck, sichtbare Gesamtstabilität und Übergangsdatensatz. Nur tatsächlich notwendige abgeleitete Werte speichern; nicht zugleich drei wandelbare Verteilungen für Support, Votes und Seats pflegen.

Genesis/H-Start hat eine **Start-Mandatsverteilung**, keine historische Wahl. Sie darf Regierungsbildung ermöglichen, aber weder einen vergangenen Wahltermin erfinden noch als „Latest election“ ausgegeben werden. Nach einer simulierten Wahl ist die Vote-Verteilung bis zur nächsten Wahl eingefroren. Keine laufende Meinungsumfrage. One-Party speichert eine Partei ohne fingierte 100-Prozent-Wahlbeteiligung. Absolute Monarchy speichert eine leere Parteienliste.

IDs sind namensunabhängig und stabil, zum Beispiel `country_code:p0`; Neuübersetzung oder neue Anzeigeform beeinflusst keinen Save. Parteifarben dauerhaft aus ID beziehungsweise unveränderlichem Index, ohne Rot/Grün-Regimewertung.

## 10. Entscheidung zu Sitzen

**Empfehlung: keine Sitze in V1.** Sie sind weder für das geforderte Kreisdiagramm noch für einfache Regierungsbildung notwendig. Parlamentarische Vote-/Startmandatsanteile dienen als ausdrücklich abstrahierte Unterstützung für die Regierung; eine Mehrheit bedeutet mehr als 50 Prozent dieser Modellmandate. Die UI benennt keine reale Sitzverteilung.

Dadurch entfallen Sitzzahl, Sperrklausel, Wahlkreise, Restmandate und widersprüchliche Diagrammwerte. Für Präsidialsysteme ist der stärkste Exekutiv-Wahlanteil kein parlamentarisches Mandat. Falls später Sitze gefordert werden: eine einheitliche proportionale Zuteilung, etwa 100 abstrahierte Sitze mit Largest Remainder und ID-Tiebreak; als neues explizites Modell, nicht stillschweigend in V1.

## 11. Ideologiemodell

Beide Achsen als endliche Zahlen in `[−1, +1]`: Economic −1 Interventionist, +1 Market Liberal; Social −1 Progressive, +1 Conservative. Darstellung kontinuierlich oder in fünf beschreibenden Bändern. Keine Axis→Produktivität-, Tax-, Subventions- oder Regimeprämie V1.

Partei-Roots stammen aus separaten stabilen Seeds. Namen passen lose zum wirtschaftlichen Band, ohne realen Parteikatalog; Social darf unabhängig sein. Regierungsachse = gewogenes Mittel der Regierungsparteien, Gewichte aus Mandatsanteilen **innerhalb** der Regierung auf Summe 1 normiert. Minderheits-Supportparteien bestimmen nicht automatisch Kabinettsideologie. Presidential nutzt Exekutivpartei; Semi-Presidential zeigt Exekutiv- und Kabinettsprofil bei Bedarf getrennt. Nichtparteiliche Staatsführung besitzt ein direkt gespeichertes beschreibendes Achsenpaar.

Economic-Distanz kann Regierungsbildung/Zusammenhalt leicht beeinflussen. Social bleibt beschreibend. Auch Economic bleibt ohne unmittelbaren wirtschaftspolitischen Hook; nur die Mechanik tatsächlichen Koalitionszusammenhalts darf auf die politische Risikokomponente wirken.

## 12. Wahlmodell und Regierungsbildung

Eigener `next_election_date` und monotoner `election_sequence`, Datum mit Kalenderjahresaddition; sichere Monatsende-/Schaltjahrregel. Keine `365×4`-Drift. Am festgelegten Termin genau ein Ereignis, auch wenn ein Coarse-Bucket den Termin überschreitet. Statische Systemzyklen aus Punkt 8, keine Frühwahl- oder Kampagnenmaschine.

Minimaler Wahlschritt: vorherige Mandatsanteile, ein kleiner relativer Amtsinhaberimpuls und isolierte Variation je Partei. Der Impuls darf Wachstum/u/Inflation/Stabilität nutzen, muss aber an beobachteten Änderungen seit der letzten Wahl hängen und einen gemeinsamen engen Cap, beispielsweise insgesamt ±4 Prozentpunkte Regierungsunterstützung, haben. Übergang zu Opposition gleichgewichtig nach vorhandenen Gewichten; nicht jede Regierungspartei erhält den gesamten Impuls. Variation separat, beispielsweise rohe Beiträge ±1 Prozentpunkt, anschließend positiv begrenzen und **einmal** auf Summe 1 normieren. Kein tägliches Polling, keine harten Nullanteile. Diese Werte sind vor Umsetzung zu kalibrieren.

Stabilitätsfeedback bei Wahlen nur aus verzögertem politischem Anteil, nicht nochmal aus GDP/u/Inflation-abgeleiteter Gesamtstabilität. Input-Snapshot unmittelbar vor der Wahl persistieren oder im Ergebnis referenzieren. Ereignisse vor dem Monatsbericht am selben Tag sehen den letzten veröffentlichten Monatsstand; keine Tagesreihenfolge entscheidet zufällig über Regierungsbildung.

Parlamentarische Regierungsbildung: Einzelpartei bei >50%; sonst höchstens 127 Teilmengen prüfen. Kandidaten anhand ausreichender Unterstützung, wirtschaftlicher Distanz, Zahl der Partner und Kontinuität deterministisch ordnen; IDs brechen Gleichstand. Wenn keine ausreichend zusammenhängende Mehrheit entsteht, gestützte Minderheit oder Caretaker-Status mit Datum speichern. Nicht immer alle Parteien bis 50% zusammenwürfeln. Regierungsbildung ist ein Ereignis, keine tägliche Suche. Presidency wird nach der offen benannten Pluralitätsabstraktion gebildet; Semi-Presidential speichert Exekutive/Kabinett getrennt.

Politik-RNG: SHA256 aus Politics-Version, Weltseed, Country-Code, Election Sequence, Ereignisart und Party-ID, lokales `random.Random` oder Hashvariation. Keine globalen Python-/NumPy-Aufrufe; kein Einbezug von sichtbarem Tab, Spielerportfolio oder Wallclock. Reihenfolge der Country-Dictionaries darf das Ergebnis nicht ändern.

## 13. Nichtdemokratische Führung

Absolute Monarchy benötigt keine Parteien, keinen Wahltermin und keine simulierbare Dynastie. One-Party State darf eine benannte Regierungspartei und ein neutrales inneres Reviewdatum haben. Authoritarian Republic zeigt amtierende Staatsführung und optional ein Reviewdatum. Keine künstlichen kompetitiven Ergebnisse.

Für alle drei gelten dieselben Qualitätskriterien für Kontinuität: Wechsel kann geordnet oder vorübergehend unsicher sein; Beibehaltung kann ruhig oder krisenbelastet sein. Ein Partei- oder Monarchietyp ist kein Ersatz für gespeicherte Basis-/Übergangswerte. V1 braucht keine Personen, Sterbewahrscheinlichkeit, Putsch-, Erbfolge- oder Repressionssimulation. Regierungsform bleibt über die Laufzeit konstant, außer einer ausdrücklich später modellierten Systemänderung.

## 14. Stabilitätsinputs und Trennung

Empfohlen sind drei klar benannte Komponenten:

1. **Politische Basis:** unabhängig initialisierte Kontinuitäts-/Institutionenbasis plus wenige Strukturwerte: Kabinettszusammenhalt, effektive Fragmentierung dort, wo sie die Regierung tatsächlich betrifft, gesicherte Unterstützung.
2. **Vorübergehender politischer Druck:** datierter Regierungsübergang beziehungsweise unaufgelöste Regierungsbildung. Geordnete Amtsbestätigung kann Druck 0 haben; jeder Wahltermin ist nicht automatisch eine Krise.
3. **Makrodruck nur für die Gesamtanzeige:** verzögertes Wachstum/u/Inflation und optional eindeutig betroffene aktive Krise. Staatsschuld/Rating/Zinslast nicht zusätzlich aufnehmen; sie bündeln dieselben Probleme bereits.

Wichtig: wirtschaftlicher Hook liest **nur Komponente 1+2**, nicht den GDP/u/Inflation/Krisenanteil aus Komponente 3. Parteienzahl allein reicht nicht: sieben Parteien mit konsistentem Mehrheitskabinett können stabil sein; zwei Parteien mit ungelöster Regierungsbildung können instabil sein. Mehrheits-/Koalitionsinput nur bei Systemen verwenden, in denen er sachlich existiert; fehlende Mechanik bedeutet neutraler Beitrag, keine erfundene 100%-Mehrheit.

## 15. Formelempfehlung für Stabilität

Ein transparenter, kleiner Kalibrierungsentwurf, nicht Produktionscode:

`B`: getrennt erzeugte Struktur-/Kontinuitätsbasis, z.B. 70–85, ohne Wohlstands-/Systemetikett. `C ∈ [0,1]`: gewichtete Economic-Distanz innerhalb der Regierung. `F ∈ [0,1]`: effektive parlamentarische Fragmentierung `(1/sum(q²)−1)/6`, begrenzt; nur wenn sie Regierungsbildung betrifft. `M ∈ [0,1]`: fehlende gesicherte Unterstützung, keine reine Minderheitslabel-Strafe. Bei nicht einschlägigen Inputs 0.

`political_target = clamp(B − 10C − 6F − 8M − transition_pressure, 0, 100)`.

`S_pol_new = clamp(S_pol_old + 0,25 × (political_target − S_pol_old), 0, 100)` bei jedem Monatsreport. Bei tatsächlichem Übergang kann dessen einmaliger datierter Druck unmittelbar ausgewiesen werden; er darf nicht zusätzlich monatlich immer wieder vom alten Score subtrahiert werden. Alternativ Basisglättung und direkte, analytisch datierte Übergangskomponente getrennt speichern. Diese zweite Variante ist für exakte Eventzeitpunkte vorzuziehen.

Anzeige-Makrodruck, Beispiel: `P_macro = min(12, max(0,−g)×80 + max(0,u−0,08)×40 + max(0,π−0,04)×40)`; eindeutig betroffene Krise zusätzlich höchstens 6 Punkte, gemeinsam auf 18 begrenzt. `S_display = clamp(S_pol − P_macro, 0, 100)`. Keine Schuld-, Rating- oder Fundingkomponente. Krisendruck erklärt die sichtbare Lage, erzeugt **keinen zusätzlichen** Politikeffekt auf Märkte.

Übergangsdruck 0–8 Punkte, gespeicherter Start/Ende, Auslaufen z.B. über drei Monatsberichte; fortbestehende Caretaker-Situation eigener Strukturwert statt nie endender Wahlpanik. Ganze Formel benötigt Szenariotests und Seedkalibrierung. Die UI erklärt knapp „Stability: continuity and current pressure“ und kann die zwei Anteile im Tooltip aufzeigen; keine irreführende wissenschaftliche Präzision.

## 16. Stabilitätskadenz und Tagesreihenfolge

**Monatlich am 15.** harmoniert mit Makro-/Workforce-Berichten und verhindert einen zusätzlichen alltäglichen Länder-Scan. Quartalsweise wäre möglich, reagiert aber spät auf reale Berichtsdaten. Basis/Parteien/System/Ideologie nur initial oder bei Ereignis; politischer Übergang beim Ereignis plus spätere monatliche Abnahme.

Empfohlene Reihenfolge: (a) fällige politische Termine mit vorherigem veröffentlichtem Makrosnapshot abwickeln; (b) vorhandenen Monatsmakrobericht ausführen; (c) sichtbaren Makrodruck/Stabilität aktualisieren; (d) existierende Unternehmen/Produktion/Workforce wie bisher; (e) Bond-Quotes verwenden den eingefrorenen politischen Spread. Keine politische Funktion liest Player Accounting. Save/Load speichert Marker und Eventsequenz, damit weder Report noch Wahl wiederholt werden.

Alltägliche Arbeit: O(1)-Datumsgate auf den nächsten politischen Termin; an einem Termin nur betroffene Länder. Keine tägliche Parteiennormalisierung, Koalitionssuche oder Historykopie. Ein Scheduler-Cache ist rekonstruierbar aus gespeicherten Terminen; autoritativ bleiben die Countrydaten.

## 17. Wirtschaftliche Hook-Matrix

Alle Vorschläge dieser Matrix sind zukünftig. Performanceangaben sind Komplexitätsabschätzungen, keine gemessenen neuen Produktionskosten.

| Hook | Aktuelle Formel | Vorgeschlagener Stabilitätsinput | Kadenz | Ausbreitung | Doppelzählungsrisiko / Kosten | Empfehlung |
|---|---|---|---|---|---|---|
| Sovereign Rating / Default Risk | fünfteiliger Makro-/Fiskalscore; Migration; Rating→PD | keiner V1 | monatlich | Funding, Bonds, Company-Regionalfaktor, Sektorkapazität, Handel/Trust, Player-Risiko | sehr hoch; Schwellen verstärken kleine Inputs; O(20) selbst billig | ablehnen V1 |
| Government Bond Yield / Spread | Rate + Ratingspread + Term + Bilanz; Barwert und Preisglättung | ausschließlich politischer Anteil `S_pol`; ein eingefrorener Premiumskalar | Berechnung monatlich/Übergang; Quotes vorhandene Kadenz | Staatsbonds, NAV von Bondfonds, beobachtete globale Kurve, Yield Futures, nachgelagerte Psychologie | mittel, wenn Gesamt-S benutzt; ein Add im bestehenden Quote; Eventrefresh gesondert | ein bevorzugter Hook unter Punkt-21-Bedingungen |
| Foreign-/Cross-Country Fund Allocation | Mandatsfilter, Cap/Growth/Dividend/Ratinggewicht; AUM-Flüsse | kein Input V1 | Monatsrebalance / tägliche Flows | NAV, Underlying-Kaufdruck, News/Preise | hoch bei zusätzlichem Spread/Rating; mit countrymandates semantisch falsch; kein FDI-Bestand | verschieben |
| Company Regional Investment / Growth | regionaler Faktor 0,78–1,18; Ergebnisbeitrag ×0,18 und Sector Factor | kein Input V1 | monatlich | Umsatz, FCF, Finanzierung/Rating, Kapazität, Workforce Demand | hoch; mehrere Einspeisungen aus demselben Faktor; O(1.280) | ablehnen V1 |
| Psychology / Expectations | News/Surprise→Sentiment/Fear/Signal/Vola; mehrfacher Newsverbrauch | optional datierter lokaler Übergang, keine dauerhafte Gesamt-S-Strafe | Ereignis, vorhandene Tagesdecays | Aktienkurse, Crowding, Fonds, später Makro indirekt | hoch bei zusätzlichem globalem Fear; Events O(64 Aktien/Land), bestehender Consumer täglich | Nachricht ohne Preisimpuls V1; maximal zweiter späterer Hook |
| FX | Realzins×0,014 + Growth/Surprise×0,006 + Krise + Mean Reversion + Noise | keiner | täglich | gesamte Umrechnung, FX-Trades, Fonds, Derivate/Player | sehr hoch; Krisen-/Makrokanäle existieren; O(20) aber breite Bilanzwirkung | ablehnen V1 |
| Country Demand | Population×Growth×u-Drag×Rate-Drag×Product Focus | keiner | laufende Production | Mengen, Knappheit, CPI, Companyresult, Kapazität | sehr hoch, direkter Makro-/Krisen-Doppelpfad | ablehnen V1 |
| Sector Focus / Capital Formation | fünfjähriger Fokuswechsel; Kapazitätswachstum aus Auslastung/Input/Shortage | keiner | Fokus fünfjährig, Kapazität monatlich | langlebige Struktur und Arbeitskräftebedarf | hoch, auf 50 Jahre kumulativ; viele Länder-/Sektor-/Firmenpfade | ablehnen V1 |

Die Beschränkung auf eine Einspeisestelle bedeutet nicht, dass nur eine Anlageklasse betroffen bleibt: bestehende abhängige Preis-/Kurvenkanäle müssen in Regression und Kalibrierung einbezogen werden.

## 18. Doppelzählung und Rückkopplungen

Bereits vorhanden: Krise→GDP/u/Inflation **und** Companyresult **und** Erwartungen **und** FX; GDP/u/Inflation→Rating und Fiskal; Rating→Funding/Bonds und Unternehmens-Regionalfaktor sowie Handelsvertrauen; Finanzierung/Zinslast→Fiskal→Makro→Rating. Asset-News beeinflussen direkt Kurswahrscheinlichkeit und zusätzlich Psychologie. Deshalb keine zusätzliche Voll-S-Strafe in all diesen Formeln.

Die vorgeschlagene Trennung `S_pol`/`P_macro` verhindert den neuen Pfad „Rezession→Stabilität→Spread“ zusätzlich zum bestehenden „Rezession→Rating→Spread“. Makrodruck darf Wahlergebnisse beeinflussen, aber nicht gleichzeitig nochmals über aus Makro abgeleitete Stabilität in deren Eingänge gelangen. Für Wahlfeedback nur verzögertes `S_pol` plus explizite Makroinputs verwenden.

Keine Krise erneut in den politischen Premiumskalar übernehmen. Regierungsbildung ist eigenes politisches Ereignis; es kann zusammen mit einer Wirtschaftskrise auftreten, erhält aber keine Kopie deren GDP-Malus. Spread bleibt eine Prämie ohne zusätzliche PD-Änderung. Bei künftigem Fiscal-Funding-Hook wäre dies eine bewusst zusätzliche Modellkopplung, nicht eine kostenlose Konsistenzkorrektur.

Auch ein einziger Spreadhook kann über die bestehende globale Yield Curve und Psychologie rückwirken. Diese Rückwirkung wird nicht mit einem weiteren direkten globalen Sentimentimpuls verstärkt. Typwechsel bei identischen komponentweisen Inputs muss identische Prämie erzeugen. Preis-/Wirtschaftsidentität zwischen allen Systemen ist nur für gleiche Mechanikeingänge testbar, nicht für völlig verschiedene Koalitions-/Übergangsverläufe.

## 19. Empfohlener Umfang: maximal ein Hook im V1

**Empfehlung:** Politisches Modell/UI plus ein kleiner Government-Bond-Premiumkanal. Nachrichtendarstellung allein ist kein zweiter ökonomischer Hook. Parteiennamen, Ideologie und Regierungslabel bleiben beschreibend; das System bestimmt Struktur und Termine.

Startentwurf: `premium = 0,0025 × clamp((75−S_pol)/50, 0, 1)`. Das sind 0–25 Basispunkte, keine pauschale Renditeverschiebung um 25 Prozent und keine jährliche zusätzliche GDP-Strafe. Bei `S_pol ≥ 75` neutral; keine zusätzliche „stabile-Regierung“-Subvention. Beispiel: 65→5 bp, 50→12,5 bp, 25→25 bp. Cap und Schwellen sind zu kalibrieren. Keine wirtschaftliche Abfrage des Regierungssystemstrings.

Freigabebedingungen für spätere Implementierung: keine Makro-/Krisenanteile im Premium; quote-/derivativekonsistente Publikation; geschlossener Coarse/Burn-in-Kanal; exaktes Save/Load und Legacy-Neutralaktivierung; Rückwirkungen auf globale Kurve gemessen. Wenn diese Anforderungen im Implementierungsdurchlauf nicht mit kleinem Umfang erreichbar sind, bleibt der ökonomische Hook deaktiviert und das Hindernis wird ausdrücklich berichtet. Ein zweiter Hook für Übergangspsychologie ist V1 nicht erforderlich.

## 20. Empfehlung zur Auslandsinvestition

Kein FDI-System bauen und keine Fonds-NAV-Bewegung als FDI verkaufen. V1 braucht auch kein `capital_attractiveness`, dessen einziger Zweck ein ungenutzter UI-Wert wäre. Bestehende Realproduktion und Portfolios reichen aus, um die Wirtschaft darzustellen.

Falls später ein Investmentfeature gewünscht wird, zunächst globale aktive Aktienfonds beim ohnehin fälligen Rebalance betrachten: kleine relative Gewichtsänderung über `S_pol`, anschließend Normalisierung, keine Kapitalerzeugung, keine Verdopplung über AUM-Flows und Companygrowth. Passive Indizes und strikt gebundene Fonds bleiben mandatsgetreu. Das wäre ein separater Auftrag mit Herkunft/Ziel- und Preisfolgenklärung.

## 21. Empfehlung zu Staatsrisiko und Anleihen

Politisches Premium ausschließlich zur Staatsanleihe-Markt-Yield addieren, vor Barwert/Glättung, **nicht** zusätzlich zu Rating/PD, Balance Spread, Companyspread oder Tagesrendite. Corporate Bonds übernehmen es nicht automatisch. Als explizite Komponente speicher-/anzeigbar, Coupon bestehender Anleihen bleibt unverändert. Für neue Staatsanleihen muss entschieden werden, ob der Ausgabecoupon die Prämie enthalten soll; empfohlen ja, als Konsistenz desselben Preis-/Emissionskanals, ohne neue Staatsschuld aus dem Premium zu buchen. [Anleihen]

`_refresh_symbol_slice` rotiert bei begrenztem Refresh. Damit nicht ein Teil der Staatsbonds vorübergehend mit alter und ein anderer mit neuer Prämie handelt, an Monats-/Regierungsereignissen betroffene Government Quotes gemeinsam aktualisieren oder einen konsistenten politischen Quoterevisionsmechanismus einführen. Normaltage behalten die vorhandene 120er-Auswahl; kein täglicher zusätzlicher Vollscan aller Firmenbonds. Eventkosten messen, nicht als „kostenlos“ ausgeben.

`_observed_government_yields` aggregiert reale Staatsbondquotes zur globalen Kurve; `_government_bond_market_yield` liest die nächsten drei Laufzeiten für Derivate. Bei Eventrefresh müssen diese Verbraucher denselben publizierten Stand sehen. Heute läuft Global Macro vor Bond Market; deshalb ist eine einheitliche Festlegung „neue Quote heute, Kurve erst nächster Global-Macro-Schritt“ oder eine kleine zusätzliche eventbezogene Kurvenaktualisierung erforderlich. Beides muss konsistent dokumentiert und getestet sein. Keine stille Mischung unterschiedlicher politischer Revisionen. [Globale Kurve], [Yield-Derivate], [Tagesablauf]

V1-Empfehlung: Prämie als **Markt-Risikoprämie**, ohne neuen Fiscal-Funding-/Debt-Mechanismus. Es gibt heute keine vollständige Staatsanleihe-Emissions-/Haushaltsbuchhaltung, die jeden Marktyield exakt in Staatszinsaufwand überführt. Das bestehende `sovereign_funding_rate`-Ziel separat mit Politik zu erweitern würde die Makrorückkopplung öffnen und zusätzliche Coarse-Fiskaltests verlangen. Diese Variante nicht beiläufig als zweiten Consumer hinzufügen.

## 22. Empfehlung zu Psychologie und Nachrichten

Wahlen/Regierungswechsel gehören in die Nachrichten und einen politischen Ereignisverlauf mit Datum, Ergebnis und Status. Eine geordnete Wahl ist kein GDP-Schock und nicht automatisch eine schlechte Nachricht. Meldungen beschreiben „majority coalition formed“, „incumbent confirmed“, „minority government supported“, „leadership review completed“, „formation pending“ neutral.

V1 ohne zusätzlichen Preisimpuls in `news_momentum` und ohne `global_market_psychology.fear += ...`. Bei einem späteren zweiten Hook nur einen lokal adressierten Impuls mit ID und Ablaufdatum einsetzen; denselben Impuls nicht direkt in Preisrichtung **und** erneut in Psychologie buchen. Unternehmensberichte dürfen ihn nicht überschreiben. Save/Load vor/nach Event und Coarse-Handoff müssen Restdauer und bereits konsumierte Eventrevision erhalten. Diese Bedingungen sind im bestehenden Nachrichtenstring-/Momentumkanal allein nicht erfüllt.

## 23. Genesis-Initialisierung

Genesis erhält dieselben wirtschaftlich relevanten Politikroots für alle Länder: identische Basis, Parteienzahl, Mandatsanteile, Economic-/Social-Achsen, Regierungsunterstützung, Termine und neutralen Premiumstand. Als transparenter Ausgangspunkt gemeinsames parlamentarisches System mit vier Parteien und festem Startmandat; Namen/IDs können länderspezifisch sein. Kein vergangener Wahleintrag. Basis so wählen, dass identische Strukturkomponenten identische Anfangsstabilität ergeben, z.B. politisch 75.

Die Symmetrieprüfung umfasst GDP, Bevölkerung, Debt/Funding/Rating, Produktion/Kapazität, Workforce und Initialpreise. Politikinitialisierung liest und verändert keinen Markt-/Player-RNG. Unterschiedliche regime labels bei gleichen Wirtschaftsroots wäre eine Alternative, erhöht aber das spätere Driftpotenzial durch abweichende Kalender/Regierungsmechanik. Für strikt symmetrisches Genesis ist die gemeinsame Mechanik die einfachere Empfehlung. Heterogene politische Identität gehört in H oder eine ausdrücklich optionale spätere Einstellung.

## 24. Heterogeneous-Initialisierung

Politische Roots aus separatem Domainseed, unabhängig von den H-Budget-/Wealthroots und Workforce-RNG. Regierungssystem, Parteienzahl/-lage, Initialmandat, Basisstabilität und Zyklusoffset unabhängig erzeugen. Kein `country.style → real-world regime`, kein `GDP per capita → democracy`, keine ärmeren Länder systematisch instabil.

Die Verteilungen sind konfigurierte Produktgewichte, keine Behauptung über globale Regimehäufigkeiten. Ein zufälliger Seed muss nicht alle sieben Typen enthalten; Tests erzwingen Systemfälle unabhängig. Mehrseeds prüfen Verteilungen und unbeabsichtigte Korrelationen mit Population/GDP/Wealth. Bestehende festen H-Weltbudgets bleiben unverändert. Initiale Wahl-/Reviewtermine innerhalb des nächsten 4-/5-Jahresfensters verteilen, ohne vergangene Ergebnisse vorzutäuschen. Für reproduzierbare Saves H-Provenienz um eine getrennte Politics-Initialization-Version ergänzen, nicht vorhandene Economic-Roots überschreiben.

## 25. Established-Integration

**Befund:** `fast_history.py` erzeugt frühe Jahresbuckets und die letzten 19 Jahre Monatsbuckets vor einem echten täglichen Burn-in von 365 Tagen. Workforce führt bereits eigene monatliche Featureunterteilungen innerhalb Coarse-Buckets aus. Der normale Coarsepfad erzeugt Makro/Firmen-/Assetzustand, aber keinen kompletten historisch fortgeschriebenen Anleihequote-/Emissionenpfad. Beim Handoff werden aktive Bonds neu gebaut, zahlreiche Asset-Psychologiewerte auf 0 gesetzt. Eine politische Nachdekoration am Ende wäre daher keine korrekte ökonomische Vorgeschichte. [Coarse], [Handoff]

**Erforderlicher künftiger Ablauf:** Politik am Originalstart initialisieren. Chronologisch monatliche Stability-Schritte und sämtliche fälligen Wahl-/Regierungsereignisse innerhalb jedes Coarse-Buckets abwickeln; kein einmaliger Jahreswahlschritt. Ereignisse vor/zwischen Monatsgrenzen korrekt anordnen. Interpolierte Coarse-Makrowerte als solche verwenden und im Verlauf nicht als echte Tagesberichte verkaufen. Kabinett, letzte Wahlergebnisse, Sequence, Datum, Druck und Basis bis zum Handoff erhalten.

Beim bevorzugten Bondhook reicht reines Fortschreiben der politischen Werte nicht: dessen wirtschaftliche Verbraucher in Coarse müssen ebenfalls berücksichtigt werden. Mindestens politischer Prämienverlauf, daraus konsistent abgeleitete historische Government-Yield-/Kurvenproxies, Bondfonds-/Yield-Future-Auswirkungen und gegebenenfalls nachgelagerte Psychologie müssen mit dem bestehenden Coarseverfahren vereinbart werden. Keine vollständige tägliche Weltwiederholung nötig; featurebezogene Monats-/Eventschritte und dokumentierte Aggregation reichen, **wenn** sie tatsächlich in die relevanten bestehenden Coarse-Verbraucher eingespeist werden. Aktuell fehlt diese Integration.

Handoff: letzte politische Werte und unerledigter Übergang bleiben erhalten, neu aufgebaute aktuelle Staatsbonds tragen dieselbe Prämie; kein doppelt applizierter Wahlimpuls. Burn-in verwendet exakt die normalen Tages-/Monatshooks. Neue Wahlgeschichte reicht nur bis zu tatsächlich simulierten Terminen zurück. Politik-/Preisgeschichte muss gegenseitig konsistent sein. Die bereits validierten 50-Jahres-Workforce-Läufe sind kein Beweis für noch nicht implementierte Politics-Integration.

## 26. Save, Legacy und Versionierung

Aktuell Checkpointversion **8**, unterstützt 4–8; Historiaschema **2**, Wirtschaftsmodell **workforce-demographics-v1**, Generator **3**, Fast History **3**, Bundle-Schema **1**. Ältere Bundles mit `economic-integrity-v1`/History 1 werden kontrolliert akzeptiert. Workforce besitzt bereits Aktivierungs-/Legacy-Provenienz und Validierung vor Zustandsmutation. [Checkpoint], [Historie], [Bundles]

Zukünftig neuer Politics-Modell-/Initialisierungs-/Kalibrierungsstand; Checkpointversion erhöhen, alte Versionen weiter explizit validieren. JSON-Länderblock wird über `makro` mitgespeichert, braucht aber vollständige Vorabvalidierung: Systeme, endliche Werte, Achsen, Sharesumme, eindeutige IDs, Government-Referenzen, sinnvolle Datumsreihenfolge, Sequenz, Ereignisstatus. RNG-Objekte nicht speichern; Hashsequenzdaten genügen.

Neue Wirtschaftsversion nötig bei aktiviertem Hook; Generator-/Historyschemaänderung, wenn politische Tabellen/Coarsepfade hinzukommen. **Versionsänderungen verändern heute auch den Coarse-Hashsalt**, weil `_unit` Economic Model und Fast History Version einbezieht. Wirtschaftsvorher/nachher allein ist daher keine reine Hookwirkung. Zusätzlich Gegenlauf bei identischen neuen Versionssalts und deaktiviertem Hook verlangen.

Legacyaktivierung am geladenen aktuellen Datum: deterministic current structure, neutraler Premium 0, keine Änderung vorhandener Preise, Holdings, Debt/GDP/u/Population, Historie oder Markt-/Player-RNG. Keine rückdatierten Wahlen/Politicszeilen. Erste neue Stability-Beobachtung am nächsten tatsächlichen Monatsreport; politischer Next Election erst in der Zukunft. „Initial allocation at activation“ ausweisen. Vorherige History-ID und Originalmodell-/Schema-Provenienz erhalten; Origin nicht auf neue Generatorversion umlabeln.

Save/Load/Close bleiben Writer-Barrieren. Politische aktuelle Zeilen und typisierte Ereignisse laufen mit denselben sequenzierten Journal-/Transaktionsbatches wie übrige Weltpersistenz. Der vorhandene Writer nimmt nur skalare Rows; Partyarrays nicht als mutable Referenzen hineinreichen. Party-/Ergebnis-JSON muss vor Übergabe finaler String oder kleine skalare Partytabelle sein. Kein zweiter Writer, kein schwächerer fsync, keine best-effort Wahlergebnisaufzeichnung. [Writer]

## 27. Historykadenz und Semantik

Empfehlung: eine `country_politics_current`-Zeile je Land, eine monatliche Stability-Zeile pro Land, typisierte Wahl-/Regierungs-/Leadership-/Activation-Events. Parteienverteilung nur initial beziehungsweise nach Wahl ändern und als Snapshot im Ereignis archivieren. Ideologie/System nur bei Änderungen. Keine tägliche Politik- oder Partyhistory.

Stability, `S_pol`, Macro Pressure, Premium sind Levels/Rates mit Endpunkt und optional Mean/Min/Max, keine summierten Flows. Wahlresultat ist ein unveränderlicher Event-Snapshot, kein Monatsmittel zwischen zwei Regierungen. Historische UI darf Ereignisverteilungen nur mit Datum/Provenienz darstellen, nicht Prozentwerte aus mehreren Wahlen mitteln.

20×12 = **240 Stabilityzeilen pro Jahr**, zusätzlich mindestens 20 Initial-/Aktivierungsereignisse pro Welt. Obergrenze für regelmäßige kompetitive Vierjahreswahlen: durchschnittlich 5 Elections/Jahr, plus bis zu 5 Government-Formation-Events; einzelne Kalenderjahre können alle 20 Wahlen enthalten. Bei separaten Partyrows maximal 35 Election-Partyrows/Jahr im langfristigen Vierjahresmittel. One-Party-/Leadership-Review kann zusätzliche seltene Events ergeben, nicht zusätzliche tägliche Fakten. Über 50 Jahre 12.000 monatliche Beobachtungen und höchstens rund 250 reguläre Wahlen bei durchgehend kompetitiven Vierjahressystemen. Monatsgeschichte politikseitig auch in den frühen Jahres-Coarsebuckets erhalten; wirtschaftliche Datenauflösung nicht versehentlich hochsetzen.

## 28. Architektur des Society & Politics-Tabs

Genau ein neuer Tab hinter Sectors, kein eigener Hauptnavigationspunkt. Bestehende Overview-Kennzahlen und vier Tabs bleiben; Population wird gemäß Produktziel zusätzlich als Headline angezeigt, da sie dort heute fehlt. Neues `SocietyPoliticsPanel` einmal im CountryDetail anlegen, stable widget identity über Länder-/Datumswechsel. Zwei Bereiche: Society mit bestehenden Demografie-/Workforcegrößen und Politics mit System, Stabilität, Regierung, Status, Ideologie, Termin und Verteilung.

Society: Population, annual Birth Rate, Population Growth mit klarer Intervallbezeichnung, headline u und Tabelle Basic/Skilled/HQ Supply/Demand/Coverage. Population Growth heute tatsächlich realisierter Intervallwert; Anzeige „since last monthly report“ oder ausdrücklich „annualized observed growth“ mit entsprechendem Feld. Vor erstem Report `None` als „not yet observed“. Birth Rate ist annualisiert und nicht mit Monatswachstum gleichzusetzen. „Supply“ ist verfügbare Workforce-Äquivalente, keine gezählte beschäftigte Personengruppe; u reduziert sie nicht nochmals.

Politics: descriptive System/Government, 0–100 Stability plus Tooltip zu Komponenten, Coalition/Single/Minority/Caretaker beziehungsweise Noncompetitive, Economic/Social-Label, Next Election oder Leadership Review beziehungsweise kein Termin. Bei Semi-Presidential schlanke separate Executive/Cabinet-Zeile. Fehlende Legacyhistorie zeigt „available since …“. Keine technischen Versions-/RNGfelder in normalen Produktansichten.

## 29. Workforce-Kreisdiagramm

**Genau drei Slices:** Basic, Skilled, Highly Qualified. Bevorzugt **Supply Composition**: `S_pool / sum(S_pools)`. Weil gemeinsame Participation 0,65 gilt, entspricht das den vorhandenen Qualifikationsshares; Titel „Workforce supply mix“. Tooltip mit Anteil und absoluten Workforce-Äquivalenten. Keine Vermischung mit Nachfrage, keine vierte Unemployment-Scheibe. Headline u und Coverage bleiben eigene Zahlen.

Die bestehende Projektion liefert absolute Supply, Demand, Coverage und Shortage je Pool; Shares kann die ausgewählte Darstellung daraus ableiten, ohne Unternehmen zu scannen. Fehlende/Null-/ungültige Gesamtsupply: drei feste Legendeneinträge und Empty State, keine durch UI ausgedachten Drittel. Percentage-Rundung nur Anzeige; Winkel aus autoritativen endlichen Anteilen.

Population verändert absolute Supply monatlich, normalerweise nicht die Qualifikationszusammensetzung. Pie-Geometrie daher nur bei tatsächlicher Anteilsänderung/Landwechsel patchen. Tooltips/absolute Legendewerte dürfen monatlich aktualisiert werden, auch wenn Geometrie gleich bleibt.

## 30. Politisches Kreisdiagramm

**Eine einzige reguläre Quantity: Latest simulated election vote share.** Keine Seats, keine aktuellen Umfragen, kein Mix mit Regierungsmacht. Titel und Unterzeile nennen Wahltyp und Datum. Presidential zeigt Exekutiv-Vote Shares; parlamentarische Systeme parlamentarische Vote Shares. Semi-Presidential muss die V1-Wahlabstraktion ausdrücklich benennen und darf das Diagramm nicht gleichzeitig als Präsidial- und Parlamentsresultat behaupten.

Vor der ersten simulierbaren Wahl: statt Election-Pie Text „Initial mandate allocation – no election recorded“. Optional Startmandatsliste anzeigen, aber keine identisch beschriftete „latest election“-Torte. Das erfüllt ehrliche Datenwiedergabe; die gewünschte politische Torte erscheint nach vorhandenem echtem Wahlergebnis. Wer unbedingt bereits am Start eine Torte möchte, muss die Produktentscheidung für eine klar als Initialmandat beschriftete **separate** Darstellungsart treffen; der Audit empfiehlt die Textalternative.

2–7 echte Parteislices, feste ID-Farben, Legend mit Name/Share; Regierungsmitgliedschaft als Icon/Text im Legend, kein Umdeuten der Share. Keine ausgeblendeten Kleinparteien oder unbeschriftete „Others“-Scheibe im V1. Verteilung bis nächster Wahl unverändert; Government-Wechsel kann Legendestatus ändern, ohne Pie-Geometrie zu ändern. Tooltips und Tastatur-/Tabellenalternative für Zugänglichkeit.

## 31. Nichtkompetitive Alternativdarstellung

Absolute Monarchy: Staatsführungs-/Kontinuitätskarte, „No competitive party election“, kein Kreisdiagramm. Authoritarian Republic entsprechend. One-Party State: Regierungspartei als Label mit Ideologie und ggf. Reviewtermin; keine künstliche 100%-Votes-Scheibe. Constitutional Monarchy erhält das parlamentarische Wahldiagramm, nicht eine Machtverteilung Monarch/Parteien.

Fehlendes Ergebnis in Demokratie: Startmandat-/Aktivierungsinformation statt 0%-Torte. Fehlerhafte/fehlende Shares: „Result unavailable“, kein UI-Normalisieren kaputter Persistenzdaten zur scheinbar gültigen Wahl. Sichtbare Government-Daten bleiben nutzbar, Pie wird nur mit validiertem Snapshot angezeigt. Layout hält denselben reservierten Bereich; kein Komplett-Neuaufbau beim Wechsel zwischen kompetitiv und nichtkompetitiv.

## 32. Wiederverwendung von Chartkomponenten

**Befund:** `FastChartView` basiert auf PyQtGraph, bietet Linien, Candles, Datum-/Valueachsen, Hover und Legend. Es patched bereits bestehende Series bei gleicher Schemaidentität. Qt nutzt `QPainter` unter anderem für LegendSwatch/Candles. Im aktuellen Qt-Code kein vorhandener Pie-/Donutpfad (`drawPie`, `QPieSeries`, Pie/Donut-Komponente) gefunden. [Charts]

Empfehlung: kleiner wiederverwendbarer Qt-`QWidget` mit `QPainter` für höchstens sieben Slices; existierendes Theme, Typografie, Farben und Widget-/Legendmuster nutzen. Keine Matplotlib-, Browser-, Plotly- oder zusätzliche QtCharts-Abhängigkeit nur für zwei Torten. Linienhistorie für Stability kann vorhandenen FastChartView nutzen, falls überhaupt als zusätzliche optionale Ansicht gefordert; die zwei Pies sind keine Zeitreihen und passen nicht in Candle-/EMA-Abstraktionen.

Einmalige Widgets; `set_data` berechnet nur bei neuer ID/Share-Signatur Winkel. Stable Legendzeilen in ID-Reihenfolge, Labels patchen; Namenwechsel darf Farbe/Identität nicht ändern. Hover trifft Winkel/Slice nur innerhalb des Kreises; Tooltip ist aktueller Datenstand. Keine dauerhaft laufende Animation, kein eigener Timertick. Rendering noch nicht implementiert oder visuell validiert.

## 33. On-demand-Design und Publikation

Bestehender Bereich `selection.area='population_society'` liefert nur das ausgewählte Land, keine Aktien-/Produktbücher und keine Makrohistories. Detail kostet in den zwei Istproben etwa 0,05 ms, zusätzlich zu bestehendem globalem Status/Ticker. Normale Markets erhalten leere Länderwerte und keine Workforcearrays. [Sichtbarer Zustand], local audit evidence

Neue aktive Selection: `{view:'macro', selection:{region:'Ameron', area:'society_politics'}}`. Der Tabindex 4 wird in der UI auf diese semantische Area abgebildet. Beide Projektionsteile aus autoritativem Countryblock lesen: `population_society` wiederverwenden plus `politics`. Der neue frühe Scopezweig muss wie der vorhandene Societyzweig **vor** allgemeinem Macro-/Produktpfad liegen. Nur ein Countryblock; kein versteckter Payload für die anderen 19 Länder. Kein Deep History ohne ausdrückliche sichtbare Anforderung.

Wichtig: `_current` kopiert heute alle öffentlichen Makroskalare und Broad Snapshot `_copy_macro_mapping` entfernt nur bekannte Workforcefelder. Politik deshalb in einem verschachtelten Block halten und in **beiden** Broad-Snapshot-/Projectionpfaden explizit ausschließen. Nicht `next_election`, `stability`, `parties` als zwanzig öffentliche Rootfelder einführen. Selected Projection ist die einzige Detailed-UI-Veröffentlichung. Checkpoint-/Debug-Signaturen dürfen volle Daten haben, normale Tagesupdates nicht.

Store-Delta-/Currentrouting heute kennt `country_current`; `country_workforce_current` ist nicht in der zentralen `CURRENT_METHODS`-UI-Liste. Ein Wahlereignis zwischen Monatsreports muss den aktiven Society-Tab trotzdem aktualisieren. Daher bei Politik-/Workforceänderung ausgewählten Scope invalidieren beziehungsweise eine spezifische Revision im bestehenden Visible-State-Ergebnis verwenden. Keine Übertragung sämtlicher Politikcurrentrows zur Lösung. Alte spätere Workerantworten für vorheriges Land/Tab anhand Scope/Requestversion verwerfen; Navigation wie vorhandene Async-/Busy-Regeln behandeln. [Worker], [App]

Pieupdates: Workforceanteile/Land als Geometriesignatur, Politik Vote-Snapshot-ID/Partyshares als Geometriesignatur; Governmentstatus, Tooltipwerte und Monatsstabilität separat patchen. Versteckte Tabs erzeugen keine Datenanfrage, keine Historyquery und keine Renderupdates. Beim Öffnen volle aktuelle ausgewählte Daten neu lesen; keine 20-Länder-Shadowkopie pflegen.

## 34. UI-Datenvertrag und Payloadabschätzung

Vorgeschlagener ausgewählter Country-Detailvertrag: `region`, `population_society` wie vorhanden und `politics` mit System/Status/Stability/Ideologie/Terminen und höchstens sieben Parteien. Zusätzlich `distribution_kind`, `distribution_date`, `distribution_provenance` und unveränderliche Ergebnis-ID. Growthfelder behalten Intervall/Annualisierung. UI-unabhängige Domainversion darf im Vertrag enthalten sein, wird im Produkt nicht angezeigt.

| Feld | Scope | Aktualisierung | History? | Nur bei sichtbarem Tab? |
|---|---|---|---|---|
| Headline GDP/Inflation/u/Policy Rate | bestehende Overview/Ländertabelle | vorhandene Monats-/Policykadenz | bestehende Reihen | vorhandener Vertrag bleibt |
| Population-Headline | zukünftig Overview/Detailkopf ergänzen; Scalar vorhanden, Anzeige fehlt | vorhandene Monatskadenz | bestehende Populationreihe | wie bestehende sichtbare Headlineansicht; keine Partyarrays |
| Society Population | ausgewähltes Land | Monat | bestehende Populationhistory auf separate Anforderung | detaillierter Societyblock ja |
| Birth Rate / optional Death Rate | ausgewähltes Land | Root/Änderung | keine neue tägliche Reihe | ja |
| Population Growth, interval end/years, annualized observed | ausgewähltes Land | Monat | bestehende Workforce-Monatsdaten | ja |
| Headline u im Societyblock | ausgewähltes Land | Monat | bestehende u-Reihe nur angefordert | ja |
| Basic/Skilled/HQ Supply, Demand, Coverage, Shortage | ausgewähltes Land, 3 feste Pools | monatlich | vorhandene WD, keine automatische Query | ja |
| Workforce-Pieanteile | ausgewähltes Land, 3 Slices | tatsächliche Compositionänderung/Landwechsel | keine eigene neue Reihe | ja |
| Government System | ausgewähltes Land | initial/echte Systemänderung | Event | ja |
| Gesamtstabilität / politischer Anteil / Makrodruck | ausgewähltes Land | Monat und definierter Übergang | neue monatliche Levels, optional angeforderte Serie | ja |
| Regierung / Executive / Coalition / Supporterstatus | ausgewähltes Land | Regierungsereignis | typisierter Event | ja |
| Government Economic/Social ideology | ausgewähltes Land | Regierungswechsel | Event | ja |
| Next Election / Leadership Review | ausgewähltes Land | Zyklusereignis | Ereignisdatum | ja; keine täglichen Countdowns im Worker |
| Party IDs, Namen, Achsen | ausgewähltes Land, ≤7 | initial/Änderung | Ergebnis-/Änderungsevent | ja |
| Latest vote shares und Ergebnismetadaten | ausgewähltes Land, ≤7 | Wahl | unveränderliches Resultat | ja |
| Government-Markierung im Legend | ausgewähltes Land | Regierungswechsel | aus Governmentevent | ja |
| Wahl-/Stability-Historypage | ausgewähltes Land, harte limit/cursor | explizite sichtbare Historyanforderung | ja, Eventdaten/Monatswerte | ja, nur zusätzlich angefordert |
| Politics-Revision / Scopeversion | aktueller ausgewählter Scope | relevante Änderung | keine Spielhistory | ja |
| Weltdatum / Ticker / allgemeiner Status | vorhandene globale UI | vorhandener Tagespfad | bestehender Vertrag | außerhalb Tab wie bisher |

**Gemessener Istzustand**, kompaktes UTF-8-JSON nur der benannten Teilobjekte, nicht gesamte IPC-Nachricht: Genesis ausgewähltes Macroobjekt 1.471 B, darin Workforce-Detail 621 B; H 1.513 B/646 B. Markets-Macroobjekt 262 B für leere 20 Länder, keine Societydaten. Macro Overview 16.856/17.430 B plus separat vorhandene Commodity-/Productdaten. Unterschied zu älteren Workforcebericht-Payloadzahlen: hier wird kompakt nur der Macro-/Detailteil gezählt, nicht derselbe Gesamttransport. local audit evidence

**Synthetische Byteabschätzung**, kein implementiertes Politicsobjekt: Schemafixture mit sieben Parteien 1.532 B, zwei Parteien 767 B; 60 monatliche `[date, stability]`-Punkte 1.201 B. Zwei-Parteienfixture dient nur der Feld-/Byteabschätzung, nicht einer Wahlvalidierung. Der komplette Society-Detailblock dürfte mit Metadaten etwa **3–5 KB** ohne History bleiben; ein explizit angeforderter 60-Punkteverlauf etwa +1,2 KB. IPC-Rahmen/Status/Ticker kommen hinzu. Nicht alle 20 Parteienblöcke übertragen; siebenparteiliger Politikzusatz ist ein Selected-Country-Zusatz, kein Weltsnapshot.

## 35. Fiktive Parteinamen

Die Länder besitzen schon kulturelle **Namensstile** für Firmen; das ist keine politische Festlegung. V1 neutrale gemeinsame englische Namen passen zum englischen Produkt-UI: Civic Alliance, Liberal Union, Conservative Movement, Social Labor Party, Reform Alliance, Democratic Union, Progressive Party, National Civic Movement. Kein realer Parteiimport, keine historischen Führernamen, keine Realstaat-Zuordnung.

Templates aus neutralen Wörtern wie Civic/Liberal/Conservative/Social/Labor/Reform/Democratic/National/Progressive plus Alliance/Union/Movement/Party. Deterministisch aus getrenntem Names-Seed, eindeutige Namen je Land ohne Reroll im Markt-RNG; bei Kollision stabiles zweites Template oder Countrykürzel. „Democratic“ im Namen ist keine Systemeigenschaft und kein Stabilitätsinput. „National“ ist kein automatischer Social-Extremwert. Sprache/Name nicht als Formelinput verwenden.

Party ID bleibt stabil, Anzeige übersetzbar. Bei One-Party neutral etwa Civic Union oder National Reform Party, ohne 100%-Wählerzahl zu erfinden. Namen nicht an vorhandene Country-Style-Pseudorealpolitik binden.

## 36. Performanceabschätzung und Auditmessungen

Politikdomain maximal 20 Länder×7 Parteien=140 kleine Objekte. Monatlich 20 Stabilityberechnungen, bei Wahl ≤7 Parteiupdates. Koalitionssuche ≤127 Teilmengen mit höchstens sieben Mitgliedern je fälligem parlamentarischen Land, nur alle vier/fünf Jahre. Selbst wenn alle 20 Länder gleichzeitig abstimmen, höchstens 2.540 Subsets statt täglicher Welt- oder Firmenscans. Monats-/Eventterminiterator läuft über 50 Jahre ungefähr 12.000 Country-Months, unabhängig von 1.280 Firmen.

Normaltag ein Scheduler-Datumsgate plus vorhandener Quoteconsumer, keine neue History-/Party-/Koalitionsarbeit. Ein eingefrorener Premiumwert addiert sich nur beim ohnehin stattfindenden Governmentquote-Refresh. Ausgewählte UI höchstens drei/seven Slices; Winkelberechnung O(7). Neue Monatszeilen nur 240/Jahr. Writerdaten im kleinen KB-Bereich pro Monatsbatch; bestehender Queue-/Durabilityvertrag genügt, eigener Hintergrundprozess nicht nötig.

Ziele für spätere Messung: keine messbare Ordinary-Day-Regression außerhalb normalen Messrauschens, Politikmonat deutlich unter 1 ms als isoliertes Ziel auf diesem Rechner, UI-Detailzusatz unter 5 KB ohne History. **Diese Zielzeiten sind keine erbrachten Benchmarks.** Eventquote-Refresh und Established-Kurvenintegration separat messen; diese können mehr kosten als die Parteienlogik.

Istproben: je 16 echte Tage Genesis/H, inklusive 15.-Bericht, bis 17.01.1990; keine Politicsphase vorhanden. Projection auf CP/RNG-Identität vor/nachher geprüft, Quellhashes unverändert. Society-Detailberechnung rund 0,050 ms als zwei Einzelproben, kein belastbares p95. Existierender allgemeiner Status-/Tickerpfad rund 2,2–2,9 ms in diesen Proben. Paralleler Testlauf beeinflusste Wallzeiten, daher Tagesdauern aus Roh-Evidenz nicht als Performancevergleich des noch nicht existierenden Modells interpretieren.

## 37. Voraussichtliche Implementierungsdateien und Funktionen

| Datei / Boundary | Erforderliche spätere Arbeit |
|---|---|
| neues `core/politics.py` | roots, state validation, systems, calendar advance, elections/formation, Stabilitykomponenten, Projection; keine Qt-/Playerabhängigkeit |
| `adapters/legacy_runtime.py` und Initialisierungsboundary | Init nach vorhandenen ökonomischen Roots; Legacyactivation/load; ausgewählte Historymethoden |
| `core/simulation.py:DailySimulation._prepare_world_day/_run_monthly_company_report_if_due` | eindeutige Event-/Monatsreihenfolge, Datumsgate, einzelne neue Phasetimings |
| `core/bonds.py:_refresh_bond_quote/_coupon_for/update_dynamic_bond_market` | ein begrenzter Government-Premiumconsumer, Eventquote-Konsistenz; vorhandene Coupons nicht nachträglich verändern |
| `core/global_macro.py:_observed_government_yields` und `financial_products.py:_government_bond_market_yield` | gleiche Quote-/Revisionbasis; keine zweite additive Politikprämie |
| `core/fast_history.py:generate_coarse_history/_advance_correlated_state/_capture_bucket/_rebaseline_handoff_state` | monatliche/ereignisgenaue Politicsgeschichte und tatsächlich konsumierte wirtschaftliche Coarseabbildung; Handoff ohne Reset politischer Zustände |
| `world_generator.py`, `core/established_world.py`, `history.py` | Version-/Identity-/Bundlegates, Politics-Sanity, Historiasemantik, Originversion erhalten |
| `core/checkpoints.py:restore/capture` | neue Version und vollständige Vorabvalidierung; Datenblock einschließlich Marker exakt |
| `core/data_store_schema.py`, `data_store.py` | sparsame Current/Monthly/Eventrows, typisierte Metadaten, Event-ID/Idempotenz, Journal-/Restoreintegration |
| `visible_state.py:project_visible_state/_current` und `adapters/legacy_state.py:_copy_macro_mapping` | Society-Politicsscope, selected-only nested payload, broad Ausschluss |
| `live_worker.py:_runtime_result`, `live_process.py` | relevante ausgewählte Revisionen, exakte Debugsignatur, kein globales Politics-Mirror |
| `ui_qt/views/macro_view.py:CountryDetailView._refresh_active_tab` | fünften Tab einmal anlegen, semantischen Scope wählen, vorhandene vier Wege erhalten |
| neues `ui_qt/widgets/society_politics_panel.py` und kleines `pie_chart.py` | Datenpatch, drei Workforce-/≤7 Vote-Slices, Alternate State, Tooltip/Legend, Visibilitygates |
| `ui_qt/app.py` Live-/Navigationrouting | Monats- und Wahlereignisse für aktiven Tab ohne Fullrefresh, keine Hidden-Renderarbeit |
| neue featurebezogene Tests/isolierte Tools | Punkt 38; kein Verändern bestehender Testtoleranzen als Ersatz für korrekte Integration |

`fiscal.py`, `production_chains.py`, `company_lifecycle.py`, `funds.py`, FX- und Player-Accountingformeln benötigen nach der bevorzugten V1-Empfehlung **keine neuen direkten Politikinputs**. Indirekte Folgen vorhandener Quote-/Kurvenconsumer trotzdem testen.

## 38. Validierungsplan und geprüfter Istzustand

**Im Audit tatsächlich durchgeführt:** Quellinventar und Funktions-/Feldsuchen; Qt-Instanziierung des heutigen MacroView im Offscreenmodus; beiden Modusproben je 16 Tage; ausgewählte und breite Projektionen; unveränderter Checkpoint inklusive Markt-Python-/NumPy-RNG vor/nach UI-Abfragen; Payload-Bytefixtures; aktuelle Ratingformeln. Keine neue Politikfunktion, keine neue Politik-/UItest-Suite, kein behaupteter 50-Jahre-Politiklauf. [Auditwerkzeug], local audit evidence

**Bestehende Regression: 169 Tests bestanden, 0 Fehler/Fehlschläge/Skips, 154,07 Sekunden.** Ausgeführt wurden `test_psychology.py`, `test_macro_analytics.py`, `test_global_macro.py`, `test_visible_state.py`, `test_workforce.py` und `test_qt_shell.py`, mit eigenem temporärem Test-/Cacheverzeichnis. Darin enthalten sind bestehende Workforce-Save-/Load-/Crash-Recovery- und Legacytests sowie UI-/Visible-Scope-Regressionen. Dies sichert die untersuchten vorhandenen Grenzen; es validiert keine zukünftige Wahl- oder Premiumformel. local regression evidence

**Später erforderliche Tests**, jeweils echte Verhaltensinvarianten:

- Alle sieben Systeme: richtige Termin-/Parteien-/Koalitionsoption, keine fingierten Votes für nichtkompetitive Führung, politische Basis unabhängig vom Label.
- Parties/Names: 2–7 oder genau 1/0 nach Typ; eindeutige stabile IDs/Namen; endliche Axes/Shares, exakte Normalisierung, deterministic Tiebreaks.
- Regierungsbildung: Einzelmehrheit, gut passende Coalition, fragmentiertes Parlament, gestützte Minority, Caretaker, Presidential Exekutivmandat, Semi-Presidential Kohabitation ohne automatischen Strafwert.
- Kalender: vier/fünf Kalenderjahre, Leap-/Monatsende, Bucket über mehrere Termine, same-day Wahl/Report, genau einmalige Sequence/Result/Eventrow. Simultane Wahl plus bestehende Krise darf beide erhalten.
- Stabilität: Bounds, geordneter Wechsel, ungelöste Bildung, stabile Monarchie/One-Party, instabile Demokratie; identische mechanische Inputs trotz anderer Label identische Formelergebnisse.
- Wirtschaftsstress: recession/u/inflation nur Anzeige-/Wahlfeedback; isolierte Änderung dieser Werte bei festem politischem Zustand darf politischen Premiumwert nicht verändern. Krise beeinflusst existierende Wirtschaft wie bisher, nicht zusätzlich diesen Hook.
- Hookisolation: bei Politikpremium 0 exakt bestehende Wirtschaft, Playerholdings unabhängig; kein PD/Rating/Company-/Demand-/FXdirektinput; Coupons bestehender Bonds unverändert; Eventquotes, global Curve und Yield Futures konsistent. Maximal 25 bp im Kandidaten, keine Addition desselben Signals zweimal.
- Save/Load: unmittelbar vor/nach Wahl, Regierungsbildung, Monatsreport, ablaufendem Transition; genaue Welt-/Player-/Politics-/RNG-Digests und next-day Resultate; invalid Politicspayload vor jeder Zustandsmutation zurückweisen.
- Persistenz: atomarer Monat+Eventbatch; Crash vor Journal/SQL-Commit und nach ACK; Recovery/Replay genau einmal mit Ergebnis-IDs; Save/Closebarriere und Queue-Backpressure; originale Historiaprovenienz erhalten.
- Established: 5/20/50 Jahre, vollständiger 365-Tageburn-in, Party/Government/Termine/Score/Premiumhistory und wirkliche ökonomische Verbraucher; Handoff active transition; gleicher Seed deterministisch. Gleichversioniger Nullhook-Gegenlauf zusätzlich zum Versionsvorher/nachher.
- Legacy: unterstützte alten Checkpoints/Workforce-Bundles sowie ältestes weiterhin akzeptiertes Modell; heutiges Aktivierungsdatum, keine fake elections/backfill; Player, Wirtschaft, Markt-RNG und Original-History-ID bei Aktivierung exakt erhalten.
- RNG: getrennte Names/Roots/Election-Seeds; veränderte Country-/Party-Iterationsreihenfolge, UI-Navigation, Savefrequenz und Flushbatching ändern Politikresultate nicht; Politikinit/Updates verbrauchen keinen globalen Markt-RNG.
- UI: fünfter Tab, Overview/Production/Trade/Sectors Regression; genau drei Workforce-Slices; ehrliche Vote-Quantity und Datum; Alternate State, Nullhistory; legend/tooltip/countrywechsel; stable widget und Farbe; Änderungen zwischen Monatsreports werden sichtbar.
- Visible Scope: keine Party-/Workforcearrays bei Markets/Overview/anderen Tabs; ausgewählter Tab nur ein Land, kein Product-/Company-/Historyballast; hidden tabs keine Render/Query; stale Workerantwort nicht in falsches Land einspielen.
- Performance: matched seeds/modes, warm ordinary/report/election days, CPU+Wall median/p95 und max; Payloads, RSS und Writerqueue; 50-Jahre-Generatorkosten separat; nicht aus zwei Einzelproben Sicherheitsgarantie ableiten.

## 39. Ausdrücklich nicht bauen

Keine Politiker, Kandidaten, Persönlichkeiten, Wahlkreise, Kampagnen, Umfragen, Sitze im V1, Wahlbeteiligungs-/Repressionsmodell, dynastische Erbfolgen, Putsche, Ideologiepolitik-Budget, Regimetyp-Wirtschaftsmultiplikatoren, tägliche Parteireihen, FDI-/Capital-Account-System, Fabrikmigration, neue UI-Hauptansicht, tägliche versteckte Tortenberechnung, 20-Länder-Politics-Snapshot, schweres Diagrammframework oder eigener Persistencewriter.

Kein impliziter Echtstaatvergleich aus Country-Style, kein Fakewahlresultat am Anfang/Legacyload, kein finaler dekorativer Established-Politicsblock mit rückwirkend behaupteter Wirkung. Keine Änderung gewöhnlicher Spielertrades/-Holdings zur Weltpreisbildung. Player Accounting, PnL, Margin, Settlements und Durability bleiben vollständig erhalten.

## 40. Offene Produktentscheidungen und Quellen

Es ist kein weiterer Auditumfang offen. Vor einer **separat beauftragten Implementierung** sind folgende Produktentscheidungen sinnvoll; jeweils steht die begründete Empfehlung bereits im Bericht:

| Entscheidung | Empfehlung |
|---|---|
| Ökonomische V1-Kopplung | genau ein Government-Bond-Premium, separat von Rating/PD; Aktivierung nur mit vollständigem Coarse-/Quotevertrag |
| Genesis politische Vielfalt versus strikte gemeinsame Startmechanik | gemeinsame mechanische Politikroots; unterschiedliche Namen, heterogene Systeme in H |
| Startverteilung im politischen Chart | ehrliche Startmandatsliste/Empty State, Vote-Pie erst nach simulierter Wahl |
| Presidential/Semi-Presidential Abstraktion | simples Exekutivmandat; Semi getrennte Executive-/Cabinetstatuszeile, keine zweite vollständige Wahl-/Sitzzählung |
| Leadershipzyklen ohne kompetitive Wahlen | optionale 5-Jahre-Reviews als Kontinuitätsevent, kein zwingender Regierungswechsel; absolute Monarchie ohne Countdown |
| Stability-Gewichte/Premiumcap | transparente kleinen Kandidaten aus Punkt 15/19, anschließend Szenario-/Seedkalibrierung; 25 bp als Startcap, keine angebliche empirische Gewissheit |
| Zusätzliche Stability-Zeitreihe in UI | zuerst KPIs/Tabellen/zwei Pies; History nur sichtbar ausdrücklich angefordert |
| Emissionscoupon bei neuem Governmentpaper | politische Prämie als Teil desselben Ausgabekanals; bestehende Coupons unverändert |

Quellen: gegen den aktuellen Arbeitsstand geprüft, einschließlich bestehender uncommitteter früherer Änderungen. Prüfwerkzeug und Report sind die einzigen neuen Auftragdateien außerhalb isolierter Audit-/Testartefakte. Konkrete Produktionsanker und Regressionnachtrag folgen unten.

[Länder]: ../src/kojakstreet/core/countries.py
[Makro]: ../src/kojakstreet/core/macro_calculations.py
[Fiskal]: ../src/kojakstreet/core/fiscal.py
[Ereignisse]: ../src/kojakstreet/core/events.py
[Shocks]: ../src/kojakstreet/core/shocks.py
[Kalender]: ../src/kojakstreet/core/economic_calendar.py
[Ratingziel]: ../src/kojakstreet/core/macro_calculations.py
[Ratings]: ../src/kojakstreet/core/ratings.py
[Psychologie]: ../src/kojakstreet/core/psychology.py
[Erwartungen]: ../src/kojakstreet/core/expectations.py
[Marktpreise]: ../src/kojakstreet/core/market_calculations.py
[Unternehmen]: ../src/kojakstreet/core/company_lifecycle.py
[Produktion]: ../src/kojakstreet/core/production_chains.py
[Fonds]: ../src/kojakstreet/core/funds.py
[Country-UI]: ../src/kojakstreet/ui_qt/views/macro_view.py
[Sichtbarer Zustand]: ../src/kojakstreet/visible_state.py
[App]: ../src/kojakstreet/ui_qt/app.py
[Store]: ../src/kojakstreet/core/data_store.py
[Schema]: ../src/kojakstreet/core/data_store_schema.py
[Anleihen]: ../src/kojakstreet/core/bonds.py
[Globale Kurve]: ../src/kojakstreet/core/global_macro.py
[Yield-Derivate]: ../src/kojakstreet/core/financial_products.py
[Tagesablauf]: ../src/kojakstreet/core/simulation.py
[Coarse]: ../src/kojakstreet/core/fast_history.py
[Handoff]: ../src/kojakstreet/core/fast_history.py
[Checkpoint]: ../src/kojakstreet/core/checkpoints.py
[Historie]: ../src/kojakstreet/core/history.py
[Bundles]: ../src/kojakstreet/core/established_world.py
[Writer]: ../src/kojakstreet/core/persistence_writer.py
[Charts]: ../src/kojakstreet/ui_qt/widgets/qt_chart.py
[Worker]: ../src/kojakstreet/live_worker.py
[Auditwerkzeug]: ../tools/politics_ui_audit.py
Local audit evidence: evidence.json (not published).
Local regression evidence: regression-v1.xml (not published).
