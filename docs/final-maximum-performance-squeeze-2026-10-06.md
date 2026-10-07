# Kojak Street – finaler Performance-Pass

> Dated engineering evidence for the revision described below. Test counts,
> model versions and measurements are historical unless explicitly carried
> into the [current verification record](portfolio-closeout-2026-10-08.md).
> Raw cache artifacts remain local; source links identify modules, not the
> original audit line numbers.


Stand: 2026-10-06. Messungen und exakte Regressionen gegen den frisch eingefrorenen Produktionsstand.

## 1. Frischer Ausgangspunkt

106 Produktionsdateien wurden vor der ersten Änderung eingefroren und gehasht. Referenz: `.cache/max-performance/before-source-hashes.json` (local evidence). Die Referenz enthält bereits sichtbare/on-demand Synchronisierung, UI-Kontinuität und die freigegebene Kleinanleger-Regel. Ältere Git-Stände dienen nicht als Vergleich.

Je 40 native Windows-Übergänge aus demselben reifen Checkpoint, davon 37 gewöhnliche Tage. Anforderung ungefähr alle drei Sekunden; Setup und Navigation liegen außerhalb der Tagesgrenze. T4 wartet auf aktuelle sichtbare Werte, abgeschlossene Historienanforderungen, Chart-Commit und tatsächlichen Paint. Werte sind **Median / p95 / Maximum**, Zeiten in ms; p95 linear interpoliert. Sondertage und Profiler-Läufe sind getrennt.

| Segment / Messgröße | Vorher | Danach |
| --- | --- | --- |
| T0-T1 | 180.92 / 211.09 / 241.08 | 148.18 / 191.31 / 193.13 |
| T1-T2 | 87.16 / 108.20 / 116.90 | 70.85 / 92.32 / 98.57 |
| T2-T3 | 51.93 / 65.14 / 68.90 | 33.54 / 52.13 / 69.66 |
| T3-T4 | 79.82 / 89.03 / 89.52 | 33.52 / 42.80 / 44.65 |
| T0-T4 | 398.48 / 446.56 / 473.56 | 290.67 / 352.77 / 373.74 |
| Heartbeat | 65.72 / 85.57 / 87.18 | 47.69 / 71.75 / 83.73 |
| Bytes | 522,811.00 / 524,093.00 / 524,383.00 | 522,813.00 / 524,096.20 / 524,386.00 |
| Worker CPU | 234.38 / 281.25 / 328.12 | 203.12 / 240.62 / 265.62 |
| Parent CPU | 125.00 / 190.62 / 218.75 | 78.12 / 128.12 / 156.25 |
| Worker RSS MiB | 1,250.91 / 1,251.54 / 1,251.54 | 1,249.98 / 1,250.11 / 1,250.23 |
| Parent RSS MiB | 1,315.98 / 1,316.56 / 1,316.68 | 1,318.20 / 1,318.84 / 1,319.23 |
| Worker GC | 12.38 / 18.47 / 31.15 | 10.58 / 15.81 / 25.52 |
| Parent GC | 1.60 / 2.32 / 2.80 | 1.19 / 9.38 / 38.34 |

## 2. Top-30-Profile

Verglichen werden dieselben ersten drei reifen Tage. Self-Rangfolge, Aufrufe über drei Tage, Zeiten pro Tag. Cumulative-Zeiten überlappen und dürfen nicht addiert werden. Profilierung verlangsamt die Ausführung; diese Werte sind keine Gameplay-Latenzen. Anonyme Comprehensions und Messwrapper sind für die Tabelle ausgeblendet.

### Worker

| Funktion | Aufrufe vorher (3 Tage) | Self / Cum vorher ms/Tag | Aufrufe danach (3 Tage) | Self / Cum danach ms/Tag |
| --- | --- | --- | --- | --- |
| financial_products.py::_government_bond_market_yield | 240 | 38.77 / 62.11 | 240 | 0.59 / 1.68 |
| checkpoints.py::encode | 63092 | 37.64 / 72.12 | 63092 | 18.16 / 36.15 |
| funds.py::_equity_underlyings | 121 | 26.53 / 51.17 | 121 | 4.17 / 10.67 |
| production_chains.py::_update_country_trade_flows | 3 | 24.68 / 117.02 | 3 | 26.06 / 112.06 |
| market_calculations.py::update_markt_kurse | 3 | 23.73 / 283.11 | 3 | 30.87 / 309.90 |
| live_worker.py::_execute | 3 | 17.55 / 814.76 | 3 | 22.16 / 749.77 |
| production_chains.py::_record_company_quantity_history | 3840 | 17.27 / 39.68 | 3840 | 18.50 / 43.25 |
| production_chains.py::append_history | 59700 | 15.27 / 25.99 | 59700 | 16.84 / 28.48 |
| production_chains.py::_update_company_utilization | 3 | 14.85 / 68.57 | 3 | 9.48 / 59.28 |
| data_store.py::_bond_row_sets | 3 | 11.95 / 28.08 | 3 | 12.53 / 29.82 |
| psychology.py::daily_asset_psychology_values | 4038 | 10.48 / 35.13 | 4038 | 13.53 / 44.85 |
| production_chains.py::_country_demand_weight | 7440 | 9.42 / 17.51 | 7440 | 9.33 / 17.18 |
| production_chains.py::_company_capacity | 11520 | 9.10 / 20.03 | 7680 | 6.14 / 12.97 |
| market_calculations.py::_update_open_interest | 4038 | 8.85 / 36.32 | 4038 | 11.18 / 46.05 |
| production_chains.py::_match_country_trade | 3 | 8.69 / 20.99 | 3 | 9.02 / 21.77 |
| visible_state.py::_pick | 7578 | 8.69 / 19.09 | 7578 | 9.61 / 17.46 |
| market_calculations.py::_asset_return | 12012 | 8.17 / 17.08 | 12012 | 10.56 / 21.79 |
| day_delta.py::public_copy | 55286 | 7.84 / 10.42 | 55286 | 5.06 / 7.87 |
| data_store.py::_asset_rows | 3 | 7.49 / 15.92 | 3 | 7.61 / 15.89 |
| psychology.py::_asset_price_momenta | 4038 | 7.36 / 12.84 | 4038 | 9.20 / 16.07 |
| market_calculations.py::_asset_ema_diff | 4038 | 7.25 / 11.25 | 4038 | 9.64 / 14.56 |
| funds.py::_bond_underlyings | 6 | 6.96 / 13.69 | 6 | 9.92 / 20.26 |
| ohlc.py::make_ohlc_from_move | 7569 | 5.49 / 14.87 | 7569 | 6.82 / 17.95 |
| visible_state.py::ticker_items | 3 | 5.42 / 8.65 | 3 | 6.84 / 10.98 |
| data_store.py::_float | 77758 | 4.81 / 4.81 | 77758 | 4.89 / 4.89 |
| market_calculations.py::_open_ended_daily_volatility | 4038 | 4.71 / 7.57 | 4038 | 6.11 / 9.67 |
| market_calculations.py::_history_price | 28062 | 4.68 / 6.09 | 28062 | 5.77 / 7.44 |
| production_chains.py::_company_quantity_plan | 3840 | 4.49 / 9.94 | 3840 | 5.77 / 12.23 |
| production_chains.py::_clamp | 35326 | 4.47 / 9.50 | 21427 | 3.09 / 6.79 |
| production_chains.py::_company_capacities | 3 | 4.20 / 12.92 | 3 | 3.99 / 12.93 |

Gesamte Worker-Aufrufe: 4,939,763 → 3,669,543.

### UI / Parent

| Funktion | Aufrufe vorher (3 Tage) | Self / Cum vorher ms/Tag | Aufrufe danach (3 Tage) | Self / Cum danach ms/Tag |
| --- | --- | --- | --- | --- |
| market_data_service.py::_book | 181692 | 39.41 / 72.08 | 36 | 0.01 / 0.03 |
| checkpoints.py::decode | 63092 | 17.96 / 25.09 | 63092 | 16.69 / 23.33 |
| market_data_service.py::asset_books | 30282 | 15.79 / 87.88 | 6 | 0.01 / 0.03 |
| market_table_model.py::apply_quote_rows | 3 | 14.21 / 25.36 | 3 | 14.74 / 26.48 |
| market_data_service.py::quote | 7569 | 10.73 / 119.72 | 0 | 0.00 / 0.00 |
| decoder.py::raw_decode | 3 | 7.17 / 7.21 | 3 | 7.08 / 7.12 |
| markets_view.py::apply_live_quotes | 3 | 5.09 / 36.97 | 3 | 5.11 / 38.25 |
| market_data_service.py::get | 15138 | 3.97 / 48.03 | 0 | 0.00 / 0.00 |
| market_data_service.py::asset_type | 15138 | 3.12 / 46.92 | 0 | 0.00 / 0.00 |
| market_data_service.py::region | 7569 | 2.89 / 50.41 | 0 | 0.00 / 0.00 |
| formatters.py::regional_money | 7575 | 2.41 / 3.62 | 7575 | 2.42 / 3.69 |
| chart_series.py::history_date | 4918 | 2.21 / 3.66 | 4918 | 2.26 / 3.84 |
| top_bar.py::_identity | 9477 | 2.11 / 2.84 | 9477 | 2.21 / 2.88 |
| market_data_service.py::quotes | 3 | 1.90 / 122.24 | 3 | 3.99 / 25.98 |
| formatters.py::percent | 8619 | 1.71 / 1.71 | 8619 | 1.72 / 1.72 |
| top_bar.py::_calculate_content_width | 3 | 1.44 / 9.16 | 3 | 1.29 / 8.81 |
| live_process.py::asset_quote_rows | 3 | 1.32 / 123.58 | 3 | 17.99 / 43.99 |
| market_table_model.py::data | 1323 | 1.10 / 1.87 | 1323 | 0.88 / 1.50 |
| AxisItem.py::generateDrawSpecs | 6 | 1.06 / 4.85 | 4 | 0.45 / 2.35 |
| market_table_model.py::mapToSource | 1323 | 1.00 / 4.49 | 1323 | 0.84 / 3.90 |
| top_bar.py::_signature | 2094 | 0.89 / 4.85 | 2094 | 0.75 / 4.58 |
| formatters.py::currency_symbol_for_region | 7575 | 0.81 / 1.20 | 7575 | 0.87 / 1.26 |
| top_bar.py::_draw_items | 84 | 0.70 / 4.37 | 74 | 0.72 / 4.04 |
| chart_series.py::merge_history_by_date | 7 | 0.69 / 4.75 | 7 | 0.68 / 4.98 |
| Point.py::__init__ | 562 | 0.63 / 0.84 | 374 | 0.31 / 0.42 |
| chart_series.py::history_ordinal | 2264 | 0.61 / 2.25 | 2264 | 0.62 / 2.33 |
| top_bar.py::_adopt_offscreen | 3 | 0.60 / 12.13 | 3 | 0.56 / 11.72 |
| top_bar.py::paintEvent | 42 | 0.53 / 5.78 | 37 | 0.51 / 5.40 |
| app.py::_apply_live_market_updates | 3 | 0.42 / 177.18 | 3 | 0.50 / 98.43 |
| zero_flicker_benchmark.py::observed | 3 | 0.34 / 15.82 | 3 | 0.30 / 15.30 |

Gesamte Parent-Aufrufe: 1,472,667 → 573,902. Thread-Wartefunktionen sind keine gemessenen GUI-Blockaden und wurden aus der UI-Hotspot-Rangfolge entfernt. Die vollständigen Rohprofile und 40-Tage-Sondertagprofile liegen in `.cache/max-performance` und `.cache/visible-ui-sync`.

## 3. Produktion und Lieferketten

Die Firmenauslastung liest unveränderte Marktgrößen einmal pro Markt und Aufruf. Bei Alias zwischen Markt- und Firmenobjekt wird nicht gecacht. Länder-/Sektorboni gelten nur während der unveränderten Firmenaggregation. Ein bereits vorhandener Produktionskapazitätswert vermeidet die zuvor trotzdem ausgewertete Fallback-Funktion. Gewichtete Additionen, Multiplikationen, Reihenfolge, Inventare und Historien bleiben exakt gleich. Zwei separate reife Fünf-Tage-Vergleiche bestätigen vollständige Checkpoints und Datenbankinhalt.

## 4. Asset-Markt und Fonds

Aktien-, FX-, Rohstoff-, Krypto-, Psychologie-, NPC-Positionierungs- und Squeeze-Formeln bleiben erhalten. Beim Rebalancing werden Aktien einmal nach Land/Sektor gruppiert. Die Listen behalten die ursprüngliche Buchreihenfolge; jeder Fonds bewertet die aktuellen Asset-Objekte mit unveränderten Scores, Sortierung, Gewichten und Zufallsaufrufen. Der Index wird nur bei Bedarf aufgebaut und nach dem laufenden Fonds-Update verworfen. Fonds-Flow wird weiterhin zum bisherigen Zeitpunkt angewendet. Im separaten Kontrolllauf sank der Rebalancing-Aufwand am ersten Monatstag von etwa 67 auf 41 ms; das Profil bestätigt die entfernten Universumsscans.

## 5. Derivate, Bonds und kleinere Phasen

Zins-Futures teilen innerhalb eines Derivate-Updates ein Länderverzeichnis der Staatsanleihen. Positive Renditen, Laufzeitabstand, stabile Sortierung bei Gleichstand, Auswahl der drei nächsten Anleihen und Summationsreihenfolge bleiben erhalten. Standalone-Aufrufe haben den bisherigen vollständigen Suchpfad. Der Index wird täglich neu aufgebaut. Weitere Bond-, Makro-, Ereignis- und Settlement-Mechaniken wurden unverändert gelassen.

## 6. Persistenz, Projektion und IPC

Der Checkpoint-Encoder erkennt unveränderte einfache Python-Typen früh; NumPy-Werte, Arrays, Datumswerte, Tupel, Sets, gemischte Mapping-Schlüssel und Subklassen behalten ihren bisherigen Protokollpfad. Keine Felder wurden aus Payloads entfernt. Aktuelle Tabellen bleiben sichtbarkeitsgebunden; Historien, Flush, Transaktion und Haltbarkeit sind unverändert. Tests prüfen insbesondere NumPy-Typen, Tags, Save/Load und Checkpoint-Caches.

## 7. Sichtbare UI-Aktualisierung

Die Kursliste löst Buchzugehörigkeit und Symbolpriorität einmal pro synchronem Lesezugriff auf. Mehrfach vorhandene Symbole, numerische Schlüssel, erste Buchpriorität, Währungsregeln und Originaldaten-Identität bleiben erhalten. Es gibt keinen Cache über Tages- oder Buchwechsel hinweg. Dadurch entfallen die pro Kurs mehrfach wiederholten Buch-/Typ-/Regionsauflösungen. Tabellen-/Widgetstruktur, Selektion, Scrollen und Fokus verwenden weiterhin die etablierte inkrementelle Aktualisierung.

## 8. Paint und Render

Der Live-Linienchart bündelt bereits wartende Updates im nächsten Qt-Durchlauf anstelle einer zusätzlichen festen 48-ms-Wartezeit. Er zeichnet weiterhin die neuesten Punkte und dazugehörigen Daten. Ein Regressionstest prüft zwei wartende Updates, genau einen Commit und die neueste Historie. Charts und Achsen werden wiederverwendet; der Ticker läuft unverändert weiter. T4 wartet auch nach der Änderung auf Chart-Commit und korrekten Paint.

## 9. Hauptthread und Event-Loop

Separate Stack-Sampler erfassen den Qt-Hauptthread während T0–T4. Vorher sind wiederholte `_book → asset_books → asset_type/region/quote`-Aufrufe sichtbar, daneben Ticker-Textmessung, Tabellenformatierung und PyQtGraph-Achsen/Paint. Danach bleiben Formatierung, Chart- und Qt-Zeichenarbeit. Die gemessenen Heartbeat-Werte stehen oben. Seltene längere Pausen bleiben; eine Garantie unter 25 ms wäre durch die Messungen nicht gedeckt. Messobserver (`findChildren`, RSS-Abfrage) verursachen ebenfalls Aufwand und werden nicht als Produktions-Hotspots ausgegeben.

## 10. GC und Allokationen

GC-Zeit und Prozess-Working-Set sind in der Haupttabelle gemessen. Separate Tracemalloc-Läufe zählen temporäre und verbleibende Allokationen einschließlich der Diagnosebuchhaltung; sie beeinflussen Laufzeit und sind von den Gameplay-Latenzen ausgeschlossen. Quellen/Blockzahlen liegen in den Allocation-JSONs.

| Prozess | Traced Peak MiB | Netto MiB | Netto Blöcke |
| --- | --- | --- | --- |
| Worker | 7.88 / 8.44 / 8.51 | 7.18 / 7.75 / 7.81 | 118,434.00 / 137,133.30 / 139,211.00 |
| Parent | 5.05 / 5.14 / 5.15 | 4.22 / 4.28 / 4.29 | 50,489.00 / 51,465.50 / 51,574.00 |

Keine globale GC-Deaktivierung oder Verschiebung von notwendiger Arbeit hinter T4 wurde ergänzt. Die bereits vorhandene begrenzte GC-Behandlung des Simulation-Cores bleibt erhalten. Ein außerhalb T0–T4 untersuchter geschlossener Bootstrap-Store hielt nur 124 Produkt-Historienzeilen und aktuelle Tabellen; eine zusätzliche Cache-Löschmechanik wäre damit keine begründete Lösung für die seltenen längeren GC-Pausen. Working-Set ist kein Nachweis eines neuen Welt-Mirrors und umfasst auch native/Allocator-Speicher.

## 11. Verworfene Optimierungen

Nicht umgesetzt: erneute Precomputation, Welt-Mirror, neue IPC-Architektur/Codec, Rust/C++, ausgelassene Historien oder Berechnungen, spätere unsichtbare Nacharbeit, Näherungen für Finanzformeln und monospaced Textbreiten, veränderte RNG-Reihenfolge, GC-Schwellenverschiebung, vorgezogener/asynchroner Flush. Weitere kleine Country-/Branch-Lookup-Caches und Formatter-Spezialisierungen würden überwiegend einzelne Millisekunden sparen und zusätzliche Invalidierungs-/Darstellungsregeln einführen. Die verbleibende große Arbeit besteht aus realer täglicher Modellberechnung, erforderlichen Historien, Serialisierung und korrekter Qt-Darstellung.

## 12. Dateien dieses Passes

Produktionsänderungen gegenüber dem frischen Freeze:

- [src/kojakstreet/core/checkpoints.py](../src/kojakstreet/core/checkpoints.py)
- [src/kojakstreet/core/financial_products.py](../src/kojakstreet/core/financial_products.py)
- [src/kojakstreet/core/funds.py](../src/kojakstreet/core/funds.py)
- [src/kojakstreet/core/market_data_service.py](../src/kojakstreet/core/market_data_service.py)
- [src/kojakstreet/core/production_chains.py](../src/kojakstreet/core/production_chains.py)
- [src/kojakstreet/ui_qt/widgets/asset_chart_panel.py](../src/kojakstreet/ui_qt/widgets/asset_chart_panel.py)

Neue Regressionstests: `test_market_quote_batch.py`, `test_yield_pricing_scope.py`, `test_checkpoint_scalars.py`, `test_live_chart_commit.py`, `test_fund_candidate_scope.py`. Reproduktionswerkzeuge: `max_performance_benchmark.py`, `max_performance_matrix.py`, `max_performance_validate.py`, `max_performance_evidence.py`, `max_performance_report.py`. Der Diff dieses Passes liegt unter `.cache/max-performance/production-changes.diff` (local evidence); ältere uncommittete Änderungen wurden nicht zurückgesetzt.

## 13. Core vorher / danach

T0→T1: **180.92 / 211.09 / 241.08 → 148.18 / 191.31 / 193.13 ms**. Phasen aus denselben gewöhnlichen Übergängen; `daily_production_chain_core` ist in `daily_production` enthalten.

| Phase | Vorher ms | Danach ms |
| --- | --- | --- |
| monthly_report | 0.00 / 0.01 / 0.01 | 0.00 / 0.00 / 0.02 |
| events | 0.00 / 0.01 / 0.01 | 0.01 / 0.01 / 0.04 |
| global_macro | 2.67 / 3.04 / 3.42 | 2.58 / 3.08 / 3.23 |
| daily_crypto_inputs | 1.27 / 1.59 / 1.84 | 1.19 / 1.60 / 1.80 |
| daily_production_chain_core | 68.50 / 81.99 / 84.11 | 58.21 / 79.32 / 85.24 |
| daily_production | 69.92 / 83.51 / 85.36 | 59.40 / 80.85 / 86.67 |
| bond_market | 3.42 / 8.06 / 10.33 | 3.39 / 8.21 / 11.13 |
| asset_market | 78.66 / 93.71 / 126.02 | 73.75 / 95.47 / 110.55 |
| derivatives | 20.73 / 26.29 / 28.80 | 6.44 / 8.30 / 9.79 |
| derivative_rolls | 0.65 / 0.96 / 1.17 | 0.48 / 0.82 / 0.98 |
| credit_interest | 0.01 / 0.01 / 0.01 | 0.01 / 0.01 / 0.01 |
| spot_derivative_settlements | 0.00 / 0.00 / 0.01 | 0.00 / 0.00 / 0.16 |
| future_settlements | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| perpetuals | 0.00 / 0.01 / 0.06 | 0.00 / 0.00 / 0.00 |
| bond_portfolio | 0.00 / 0.01 / 0.01 | 0.00 / 0.01 / 0.01 |

## 14. T1→T2 vorher / danach

**87.16 / 108.20 / 116.90 → 70.85 / 92.32 / 98.57 ms**. Enthält Tagespersistenz, sichtbare Extraktion, Encoder, JSON, Pipe, Antwortannahme und Snapshot-Decodierung. Kein persistenter Welt-Diff oder versteckter Voll-Sync wurde ergänzt.

## 15. UI-Patch vorher / danach

T2→T3: **51.93 / 65.14 / 68.90 → 33.54 / 52.13 / 69.66 ms**. Der Hauptgewinn kommt aus der einmaligen Kursauflösung. Alle sichtbaren Modelle erhalten aktuelle Zahlen.

## 16. Korrekte Darstellung vorher / danach

T3→T4: **79.82 / 89.03 / 89.52 → 33.52 / 42.80 / 44.65 ms**. Diese Zeit enthält die tatsächliche Event-Loop-/Paint-Bereitschaft und ist nicht die Summe überlappender Paint-Spans.

## 17. Gesamter Übergang vorher / danach

T0→T4: **398.48 / 446.56 / 473.56 → 290.67 / 352.77 / 373.74 ms**. Die längeren 40-Tage-Messungen sind maßgeblich; kurze Zwischenkontrollen lagen teils niedriger und ersetzen die Abschlussmessung nicht.

## 18. Heartbeat vorher / danach

Pro Übergang längster gemessener Heartbeat-Abstand: **65.72 / 85.57 / 87.18 → 47.69 / 71.75 / 83.73 ms**. Der Median verbessert sich; seltene lange Pausen verschwinden nicht vollständig. Native Messung mit 10-ms-Prüftimer und kontinuierlichem Ticker.

## 19. Payload vorher / danach

**522,811.00 / 524,093.00 / 524,383.00 → 522,813.00 / 524,096.20 / 524,386.00 Bytes**. Der wirtschaftliche Inhalt und die sichtbaren Felder bleiben gleich; wenige Bytes Variation kommen aus Laufzeit-/Antwortmetadaten. Keine Payload-Reduktion durch das Weglassen erforderlicher Werte.

## 20. Junge Welt

| Fall | N gewöhnlich | T0→T1 | T1→T2 | T2→T3 | T3→T4 | T0→T4 | Heartbeat | Bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Jung vorher | 11 | 144.29 / 153.20 / 155.14 | 66.90 / 102.37 / 120.92 | 44.02 / 46.75 / 47.60 | 74.86 / 81.80 / 83.37 | 330.02 / 360.32 / 367.46 | 56.25 / 60.97 / 63.01 | 523,976.00 / 524,321.00 / 524,397.00 |
| Jung danach, gleiche 12 Tage | 11 | 131.70 / 147.26 / 148.30 | 61.13 / 101.15 / 127.06 | 31.67 / 51.85 / 66.32 | 29.69 / 34.83 / 35.67 | 250.81 / 309.13 / 334.85 | 43.80 / 66.23 / 79.07 | 523,975.00 / 524,321.50 / 524,397.00 |
| Jung danach, alle 20 Tage | 19 | 133.57 / 146.42 / 148.30 | 60.00 / 80.42 / 127.06 | 31.16 / 66.77 / 70.88 | 32.20 / 36.22 / 38.55 | 251.39 / 309.86 / 334.85 | 43.80 / 79.63 / 84.64 | 524,141.00 / 524,688.50 / 525,242.00 |

Startcheckpoint 1990-01-10. Der erste gemeinsame 12-Tage-Ausschnitt ist zusätzlich paarweise ausgewertet; 20 Tage im endgültigen jungen Lauf.

## 21. Reife Welt und neun Ansichten

Reifer Abschlusslauf: 37 gewöhnliche Übergänge aus 40, gleiche Termine und Startzustände wie die Referenz. Zusätzlich drei native Übergänge je Ansicht und Weltalter, mit aktuellen sichtbaren Kursen, GUI-Thread-Prüfung, unverändertem Ticker und abgeschlossener Worker-Beendigung.

| Welt / Ansicht | N | T0→T1 | T1→T2 | T2→T3 | T3→T4 | T0→T4 | Heartbeat | Bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| jung / bondmarket | 3 | 134.64 / 136.57 / 136.79 | 101.25 / 104.63 / 105.01 | 17.19 / 17.41 / 17.44 | 1.00 / 1.04 / 1.04 | 254.25 / 259.41 / 259.98 | 23.99 / 26.79 / 27.10 | 1,417,424.00 / 1,417,609.40 / 1,417,630.00 |
| jung / forex | 3 | 131.20 / 146.08 / 147.73 | 33.33 / 35.47 / 35.71 | 15.14 / 17.18 / 17.41 | 8.61 / 9.41 / 9.50 | 188.28 / 208.14 / 210.35 | 30.16 / 32.53 / 32.79 | 150,786.00 / 151,309.80 / 151,368.00 |
| jung / global_macro | 3 | 126.63 / 126.98 / 127.02 | 24.10 / 26.59 / 26.87 | 22.61 / 23.31 / 23.38 | 15.98 / 15.99 / 16.00 | 190.48 / 191.47 / 191.58 | 43.86 / 44.22 / 44.26 | 73,369.00 / 80,449.30 / 81,236.00 |
| jung / macro | 3 | 138.06 / 202.68 / 209.86 | 27.59 / 47.59 / 49.81 | 12.18 / 12.85 / 12.92 | 22.61 / 22.78 / 22.79 | 200.43 / 284.92 / 294.31 | 40.44 / 42.86 / 43.12 | 127,787.00 / 127,971.50 / 127,992.00 |
| jung / markets | 3 | 147.62 / 147.74 / 147.75 | 64.56 / 69.87 / 70.46 | 32.16 / 33.26 / 33.38 | 26.95 / 37.03 / 38.15 | 267.43 / 284.63 / 286.54 | 44.93 / 51.15 / 51.85 | 523,972.00 / 524,217.70 / 524,245.00 |
| jung / news | 3 | 134.77 / 152.91 / 154.92 | 34.14 / 61.54 / 64.59 | 14.97 / 15.81 / 15.91 | 46.85 / 50.45 / 50.85 | 255.82 / 260.63 / 261.17 | 55.56 / 73.38 / 75.36 | 103,086.00 / 106,384.50 / 106,751.00 |
| jung / portfolio | 3 | 133.37 / 135.15 / 135.35 | 22.24 / 22.28 / 22.29 | 10.74 / 12.00 / 12.14 | 1.20 / 1.24 / 1.24 | 168.26 / 168.93 / 169.00 | 15.68 / 15.99 / 16.02 | 39,018.00 / 39,172.80 / 39,190.00 |
| jung / supply_chain | 3 | 127.46 / 134.13 / 134.87 | 27.60 / 36.71 / 37.72 | 16.25 / 16.38 / 16.39 | 26.73 / 29.74 / 30.07 | 197.29 / 216.88 / 219.05 | 46.43 / 48.62 / 48.86 | 148,164.00 / 148,525.80 / 148,566.00 |
| jung / trade_map | 3 | 133.76 / 135.60 / 135.80 | 76.79 / 162.44 / 171.96 | 13.68 / 13.73 / 13.74 | 10.77 / 10.97 / 11.00 | 236.71 / 319.03 / 328.18 | 24.64 / 40.65 / 42.43 | 895,217.00 / 899,024.90 / 899,448.00 |
| reif / bondmarket | 3 | 175.68 / 179.49 / 179.92 | 119.48 / 121.66 / 121.90 | 26.55 / 55.17 / 58.34 | 1.36 / 10.03 / 11.00 | 335.14 / 344.21 / 345.21 | 26.86 / 57.82 / 61.26 | 1,575,011.00 / 1,578,903.50 / 1,579,336.00 |
| reif / forex | 3 | 158.50 / 159.56 / 159.68 | 44.37 / 49.04 / 49.56 | 17.88 / 19.21 / 19.36 | 7.84 / 8.40 / 8.46 | 230.69 / 234.53 / 234.96 | 32.21 / 35.87 / 36.27 | 174,452.00 / 174,907.40 / 174,958.00 |
| reif / global_macro | 3 | 145.40 / 154.83 / 155.87 | 35.50 / 35.92 / 35.97 | 23.75 / 26.45 / 26.75 | 15.66 / 18.40 / 18.70 | 220.17 / 235.58 / 237.29 | 46.68 / 46.71 / 46.72 | 83,143.00 / 83,274.40 / 83,289.00 |
| reif / macro | 3 | 157.22 / 201.90 / 206.86 | 39.26 / 55.04 / 56.80 | 12.68 / 14.74 / 14.96 | 25.15 / 26.19 / 26.30 | 235.94 / 291.68 / 297.88 | 37.79 / 40.07 / 40.32 | 129,042.00 / 129,606.30 / 129,669.00 |
| reif / markets | 3 | 185.86 / 254.91 / 262.59 | 94.32 / 116.42 / 118.87 | 32.15 / 33.40 / 33.54 | 35.21 / 37.50 / 37.75 | 339.00 / 440.12 / 451.36 | 62.02 / 64.41 / 64.67 | 523,030.00 / 524,207.20 / 524,338.00 |
| reif / news | 3 | 164.43 / 165.64 / 165.77 | 37.34 / 38.06 / 38.14 | 17.14 / 17.70 / 17.76 | 44.42 / 46.31 / 46.52 | 262.84 / 264.57 / 264.76 | 66.74 / 71.16 / 71.66 | 138,937.00 / 139,374.40 / 139,423.00 |
| reif / portfolio | 3 | 141.56 / 166.39 / 169.15 | 36.18 / 41.25 / 41.81 | 13.41 / 20.88 / 21.71 | 1.33 / 3.87 / 4.16 | 203.60 / 217.53 / 219.08 | 18.97 / 25.86 / 26.63 | 57,634.00 / 57,645.70 / 57,647.00 |
| reif / supply_chain | 3 | 150.86 / 157.80 / 158.57 | 38.62 / 39.61 / 39.72 | 16.20 / 16.84 / 16.91 | 27.29 / 27.58 / 27.61 | 233.30 / 241.26 / 242.15 | 46.92 / 48.01 / 48.13 | 149,224.00 / 149,367.10 / 149,383.00 |
| reif / trade_map | 3 | 166.30 / 166.31 / 166.31 | 99.99 / 109.63 / 110.70 | 13.94 / 14.06 / 14.08 | 11.20 / 11.42 / 11.44 | 289.83 / 299.36 / 300.42 | 29.52 / 29.86 / 29.89 | 889,212.00 / 889,854.60 / 889,926.00 |

| Welt / Ansicht | Worker CPU ms | Parent CPU ms | Worker RSS MiB | Parent RSS MiB | Worker GC ms | Parent GC ms |
| --- | --- | --- | --- | --- | --- | --- |
| jung / bondmarket | 203.12 / 217.19 / 218.75 | 78.12 / 78.12 / 78.12 | 294.21 / 332.29 / 336.52 | 374.19 / 374.24 / 374.25 | 6.19 / 7.63 / 7.79 | 0.38 / 0.68 / 0.71 |
| jung / forex | 171.88 / 171.88 / 171.88 | 78.12 / 78.12 / 78.12 | 287.66 / 324.32 / 328.39 | 372.86 / 372.90 / 372.91 | 5.58 / 9.20 / 9.60 | 1.11 / 1.35 / 1.37 |
| jung / global_macro | 140.62 / 140.62 / 140.62 | 46.88 / 60.94 / 62.50 | 311.82 / 348.46 / 352.53 | 372.84 / 372.84 / 372.84 | 4.74 / 6.14 / 6.30 | 0.20 / 0.45 / 0.48 |
| jung / macro | 156.25 / 240.62 / 250.00 | 46.88 / 46.88 / 46.88 | 302.50 / 339.25 / 343.33 | 372.83 / 372.84 / 372.84 | 5.22 / 8.39 / 8.74 | 0.73 / 0.78 / 0.79 |
| jung / markets | 187.50 / 201.56 / 203.12 | 125.00 / 125.00 / 125.00 | 287.59 / 317.93 / 321.30 | 372.85 / 372.89 / 372.89 | 7.42 / 15.16 / 16.02 | 0.82 / 0.88 / 0.89 |
| jung / news | 140.62 / 182.81 / 187.50 | 109.38 / 123.44 / 125.00 | 315.38 / 352.07 / 356.15 | 372.84 / 372.85 / 372.85 | 5.28 / 6.62 / 6.77 | 0.65 / 33.34 / 36.97 |
| jung / portfolio | 156.25 / 156.25 / 156.25 | 31.25 / 45.31 / 46.88 | 295.03 / 334.88 / 339.31 | 372.83 / 372.89 / 372.89 | 4.54 / 5.95 / 6.11 | 0.00 / 0.00 / 0.00 |
| jung / supply_chain | 156.25 / 170.31 / 171.88 | 78.12 / 78.12 / 78.12 | 287.59 / 320.23 / 323.86 | 372.85 / 372.89 / 372.90 | 4.91 / 14.78 / 15.88 | 0.13 / 0.13 / 0.13 |
| jung / trade_map | 187.50 / 229.69 / 234.38 | 78.12 / 92.19 / 93.75 | 309.49 / 345.97 / 350.02 | 372.84 / 372.84 / 372.84 | 5.06 / 58.40 / 64.32 | 0.18 / 35.10 / 38.98 |
| reif / bondmarket | 250.00 / 250.00 / 250.00 | 93.75 / 107.81 / 109.38 | 1,252.41 / 1,252.42 / 1,252.43 | 1,322.12 / 1,324.22 / 1,324.46 | 9.23 / 10.55 / 10.70 | 1.74 / 36.40 / 40.26 |
| reif / forex | 171.88 / 200.00 / 203.12 | 78.12 / 106.25 / 109.38 | 1,250.91 / 1,250.92 / 1,250.92 | 1,320.10 / 1,322.62 / 1,322.89 | 12.66 / 13.71 / 13.83 | 1.26 / 1.31 / 1.31 |
| reif / global_macro | 171.88 / 185.94 / 187.50 | 46.88 / 46.88 / 46.88 | 1,250.88 / 1,251.01 / 1,251.02 | 1,322.36 / 1,322.90 / 1,322.96 | 9.81 / 10.62 / 10.71 | 0.23 / 0.47 / 0.50 |
| reif / macro | 171.88 / 242.19 / 250.00 | 62.50 / 90.62 / 93.75 | 1,250.88 / 1,250.90 / 1,250.91 | 1,320.68 / 1,322.73 / 1,322.95 | 11.34 / 12.43 / 12.55 | 0.11 / 0.38 / 0.41 |
| reif / markets | 265.62 / 335.94 / 343.75 | 140.62 / 154.69 / 156.25 | 1,250.91 / 1,250.91 / 1,250.91 | 1,320.06 / 1,322.61 / 1,322.89 | 12.61 / 33.99 / 36.36 | 1.23 / 1.31 / 1.32 |
| reif / news | 187.50 / 187.50 / 187.50 | 140.62 / 168.75 / 171.88 | 1,250.91 / 1,251.01 / 1,251.02 | 1,322.37 / 1,322.90 / 1,322.96 | 9.00 / 9.75 / 9.84 | 0.24 / 0.34 / 0.35 |
| reif / portfolio | 187.50 / 187.50 / 187.50 | 46.88 / 60.94 / 62.50 | 1,250.87 / 1,250.90 / 1,250.91 | 1,320.67 / 1,322.72 / 1,322.95 | 10.02 / 13.34 / 13.71 | 0.53 / 1.74 / 1.87 |
| reif / supply_chain | 187.50 / 187.50 / 187.50 | 93.75 / 93.75 / 93.75 | 1,250.91 / 1,250.92 / 1,250.92 | 1,320.09 / 1,322.61 / 1,322.89 | 10.59 / 12.60 / 12.82 | 0.14 / 0.37 / 0.40 |
| reif / trade_map | 234.38 / 248.44 / 250.00 | 78.12 / 106.25 / 109.38 | 1,251.73 / 1,251.85 / 1,251.87 | 1,322.38 / 1,322.90 / 1,322.96 | 13.91 / 16.62 / 16.92 | 0.35 / 0.60 / 0.63 |

Die kurzen Ansichtsserien enthalten gegebenenfalls Sondertage und sind Korrektheits-/Breitenkontrollen, keine 30-Tage-Schätzung pro Ansicht.

## 22. Firmen-Chart, Übersicht und Supply

| Fall | N | T0→T1 | T1→T2 | T2→T3 | T3→T4 | T0→T4 | Heartbeat | Bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| chart vorher | 6 | 175.16 / 235.02 / 246.62 | 76.32 / 120.00 / 129.78 | 60.58 / 87.37 / 92.73 | 2.10 / 2.33 / 2.36 | 327.82 / 421.91 / 443.45 | 64.84 / 93.80 / 100.10 | 523,619.00 / 524,478.50 / 524,608.00 |
| chart danach | 6 | 148.09 / 182.76 / 182.76 | 71.37 / 82.41 / 85.85 | 39.52 / 72.63 / 82.12 | 1.96 / 18.83 / 24.36 | 282.42 / 312.25 / 313.26 | 41.46 / 73.07 / 81.98 | 523,618.50 / 524,484.50 / 524,615.00 |
| overview vorher | 6 | 170.84 / 217.53 / 229.04 | 79.47 / 87.13 / 87.38 | 47.92 / 77.79 / 82.80 | 2.59 / 2.92 / 2.97 | 302.28 / 362.41 / 366.47 | 54.84 / 80.30 / 85.17 | 525,085.50 / 526,051.00 / 526,212.00 |
| overview danach | 6 | 154.48 / 178.42 / 184.28 | 69.70 / 79.98 / 81.91 | 32.10 / 59.75 / 68.46 | 2.76 / 10.21 / 11.81 | 265.35 / 297.49 / 304.97 | 34.90 / 62.58 / 71.14 | 525,084.50 / 526,048.25 / 526,209.00 |
| supply vorher | 6 | 177.18 / 226.10 / 235.36 | 85.74 / 101.70 / 101.87 | 60.98 / 80.41 / 81.79 | 13.48 / 16.12 / 16.42 | 337.74 / 408.58 / 414.38 | 76.74 / 94.12 / 95.17 | 570,721.50 / 571,670.75 / 571,830.00 |
| supply danach | 6 | 141.31 / 208.26 / 222.29 | 71.62 / 107.71 / 119.12 | 33.28 / 65.06 / 70.88 | 12.79 / 15.63 / 15.87 | 257.64 / 385.01 / 404.86 | 50.53 / 84.02 / 90.99 | 570,725.00 / 571,670.25 / 571,828.00 |

Je sechs native Übergänge mit derselben tatsächlich ausgewählten Firma. Die Endsignaturen einschließlich Welt-RNG stimmen exakt mit den jeweiligen Referenzläufen überein.

## 23. Report, Monatsende und Jahresgrenze

| Fall | Startdatum | T0→T1 | T1→T2 | T2→T3 | T3→T4 | T0→T4 | Heartbeat | Bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vorher | 1991-01-15 | 246.12 / 246.12 / 246.12 | 108.54 / 108.54 / 108.54 | 48.95 / 48.95 / 48.95 | 63.67 / 63.67 / 63.67 | 467.29 / 467.29 / 467.29 | 68.64 / 68.64 / 68.64 | 526,252.00 / 526,252.00 / 526,252.00 |
| vorher | 1991-01-30 | 158.43 / 158.43 / 158.43 | 3,552.00 / 3,552.00 / 3,552.00 | 55.17 / 55.17 / 55.17 | 80.01 / 80.01 / 80.01 | 3,845.60 / 3,845.60 / 3,845.60 | 70.85 / 70.85 / 70.85 | 522,440.00 / 522,440.00 / 522,440.00 |
| vorher | 1991-01-31 | 161.19 / 161.19 / 161.19 | 87.68 / 87.68 / 87.68 | 57.01 / 57.01 / 57.01 | 81.71 / 81.71 / 81.71 | 387.59 / 387.59 / 387.59 | 78.10 / 78.10 / 78.10 | 522,652.00 / 522,652.00 / 522,652.00 |
| danach | 1991-01-15 | 204.17 / 204.17 / 204.17 | 89.17 / 89.17 / 89.17 | 30.62 / 30.62 / 30.62 | 18.97 / 18.97 / 18.97 | 342.93 / 342.93 / 342.93 | 46.13 / 46.13 / 46.13 | 526,258.00 / 526,258.00 / 526,258.00 |
| danach | 1991-01-30 | 157.71 / 157.71 / 157.71 | 3,434.83 / 3,434.83 / 3,434.83 | 39.20 / 39.20 / 39.20 | 19.21 / 19.21 / 19.21 | 3,650.96 / 3,650.96 / 3,650.96 | 54.87 / 54.87 / 54.87 | 522,441.00 / 522,441.00 / 522,441.00 |
| danach | 1991-01-31 | 136.81 / 136.81 / 136.81 | 66.04 / 66.04 / 66.04 | 37.78 / 37.78 / 37.78 | 25.37 / 25.37 / 25.37 | 266.00 / 266.00 / 266.00 | 58.06 / 58.06 / 58.06 | 522,652.00 / 522,652.00 / 522,652.00 |
| Jahresgrenze danach | 1990-12-31 | 173.26 / 173.26 / 173.26 | 93.72 / 93.72 / 93.72 | 31.10 / 31.10 / 31.10 | 37.62 / 37.62 / 37.62 | 335.70 / 335.70 / 335.70 | 45.43 / 45.43 / 45.43 | 523,602.00 / 523,602.00 / 523,602.00 |
| Jahresgrenze danach | 1991-01-01 | 224.17 / 224.17 / 224.17 | 77.89 / 77.89 / 77.89 | 35.92 / 35.92 / 35.92 | 35.33 / 35.33 / 35.33 | 373.31 / 373.31 / 373.31 | 51.77 / 51.77 / 51.77 | 524,602.00 / 524,602.00 / 524,602.00 |

40 separate profilierte reife Übergänge decken Report, Monatsende und Flush ab; zusätzlich gibt es ein Profil der Jahresgrenze. Veröffentlichung, Weltfortschritt und Player-Accounting bleiben in derselben Reihenfolge.

## 24. Dauerhafter Flush

Der Flush bleibt ein längerer Übergang, mit unveränderter Transaktion, vollständigen Tabellen und Historienaggregation. Gemessene native Datenbank-Aufrufzeiten sind Teil des Flush, keine zusätzliche Summanden der Gesamtlatenz.

| SQL-Gruppe | Native Gesamtzeit ms im Flush |
| --- | --- |
| COMMIT | 1068.42 |
| DELETE | 746.99 |
| COPY | 657.73 |
| INSERT | 96.35 |
| SELECT | 10.28 |
| BEGIN | 0.32 |

Datenbank- oder Publication-Arbeit wurde weder ausgelassen noch hinter T4 verschoben. Die Rohprofile unterscheiden CSV-Schreiben, native Datenbankaufrufe, Aggregation und Commit.

## 25. Vollständige Tests

**441 Tests bestanden**, keine Fehler, Fehlschläge oder übersprungenen Tests. Laufzeit 1747.08 s. Nachweis: `.cache/max-performance/full-final.xml` (local evidence). Zusätzlich wurden die Änderungen schrittweise mit fokussierten Tests und exakten reifen Vergleichen geprüft. Alle neuen Dateien bestehen Ruff; in den sechs Produktionsdateien wurden gegenüber dem Freeze keine neuen Linter-Befunde eingeführt (12 bestehende Befunde unverändert).

## 26. 365 Tage exakt

365 Tage mit Seed 1729 aus frischen Welten: tägliche Zustands-/RNG-Signaturen, volle Checkpoints an Tag 15/31/181/365, finaler vollständiger Checkpoint sowie 1,609,129 dauerhaft geschriebene Zeilen in 31 Tabellen einschließlich Historien stimmen exakt überein. Keine wirtschaftliche Toleranz oder Versionsnormalisierung. Nachweis: `.cache/max-performance/final-exact.json` (local evidence).

## 27. Kleinanleger und Player-Accounting

64 Aktions-/Datumsfälle, je ein bis zwei Tage: Aktienkauf/-verkauf, Fonds, Rohstoffe, Krypto, FX, Long, Short/Schließen, Futures, Option, CDS, Bond, Kredit, Margin Call und Liquidation an gewöhnlichem Tag, Report, Monatsende und Jahresgrenze. Die vollständigen Checkpoints einschließlich Player-Accounting, PnL, Margin, Settlements und Player-RNG stimmen vor/nach diesem Pass überein. Die separate bestehende Retail-Testsuite prüft weiterhin die Unabhängigkeit der Welt von gewöhnlichen Spieler-Trades/Holdings. Nachweis: `.cache/max-performance/players-exact.json` (local evidence).

## 28. RNG, Checkpoints, Historien und Datenbank

Python-/NumPy-Welt-RNG und Player-RNG sind erhalten. Numerische Werte werden ohne Rundung verglichen. Datenbankhashes schließen ausschließlich nichtwirtschaftliche Laufzeitmessungen (`phase_metric_*.duration_ms`) und die pro neuem Store unabhängige UUID `history_metadata.history_id` aus; Tabelleninhalte, Zeilenzahlen, wirtschaftliche Historien und Aggregationen bleiben vollständig im Vergleich. Checkpoints werden einschließlich Version 7 und vorhandener computational caches verglichen.

## 29. Save/Load und Pause

Native Navigation: 94 geprüfte Wechsel/Detailfälle über alle neun Ansichten und mehrere Asset-Typen; Save/Load mit exakter Signatur nach zwischenzeitlich weitergelaufenen Tagen bestanden. Die vollständige Testsuite umfasst Pause/Resume, direkt vor der Tagesgrenze ausgeführte Trades, Margin-Stopp, abgeschlossene World-/Player-Publikation und Save/Replay. Sichtbare Charts/Historien und Ticker-Kontinuität bleiben erhalten.

## 30. Verbleibende Hotspots

Die Aktienpreisberechnung, Produktions-/Handelsabschluss und das erforderliche Schreiben begrenzter Historien dominieren den Core. Danach verbleiben persistente Tageszeilen, sichtbare Projektion/JSON, Tabellenformatierung, Ticker-Textmessung und Qt-/PyQtGraph-Paint. Seltene GC-Pausen und der dauerhafte Flush beeinflussen die Spitzen. Weitere Eingriffe benötigen neue Belege für einen großen sicheren Gewinn; eine neue Architektur wurde nicht begonnen.

## 31. Gemessene praktische Unterkante

Der schnellste gewöhnliche reife Übergang in der endgültigen 40-Tage-Serie betrug **249.24 ms**. Das ist eine beobachtete Unterkante auf diesem Rechner, kein Beweis einer absoluten mathematischen Grenze. Core, Übertragung/Aufbereitung und korrekte Darstellung bleiben notwendige Kosten. Ein sicherer Weg unter 200 ms wurde in diesem Pass nicht nachgewiesen.

## 32. Urteil zur Spiel-Flüssigkeit

Die korrekte sichtbare Tagesaktualisierung wird spürbar früher fertig und die typische zusammenhängende Hauptthread-Belastung fällt. Die vertrauenswürdige sequentielle Architektur, alle neun Ansichten, Kleinanleger-Regel und Player-Accounting bleiben erhalten. Seltene längere Pausen und Flush-Tage bleiben reale Einschränkungen. Unter 200 ms oder vollständig unter 25-ms-Blockaden wird nicht behauptet; der Pass endet nach Entfernung der nachgewiesenen großen redundanten Arbeit.
