"""Build the required 47-point closeout from completed, asserted evidence."""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/politics-implementation"
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]


def read(label):
    return json.loads((OUT / label / "result.json").read_text(encoding="utf-8"))


def main():
    from kojakstreet.core.politics import SYSTEMS
    before = read('cost-before-closed')
    after = read('cost-after-closed')
    assert before['economic_digest'] == after['economic_digest']
    histories = [(years, read(f'established-before-{years}y-'+('v2' if years == 20 else 'v1')),
                  read(f'established-after-{years}y-closed')) for years in (5, 20, 50)]
    for _, old, new in histories:
        assert old['coarse_economic_digest'] == new['coarse_economic_digest']
        assert old['economic_digest'] == new['economic_digest']
        assert len(new['days']) == 365
        assert new['country_politics_current_rows'] == 20
    distributions = read('distributions-v1')
    legacy = json.loads((OUT / 'legacy-established-reader-final-v2/probe-result.json').read_text(encoding='utf-8'))
    assert legacy['passed']
    full = ET.parse(OUT / 'full-suite-verified.xml').getroot().find('testsuite')
    assert int(full.attrib['failures']) == 1 and int(full.attrib['errors']) == 0
    assert int(full.attrib['skipped']) == 0
    resolved = ET.parse(OUT / 'workspace-closed.xml').getroot().find('testsuite')
    assert int(resolved.attrib['failures']) == int(resolved.attrib['errors']) == int(resolved.attrib['skipped']) == 0
    identity = lambda case: (case.attrib['classname'], case.attrib['name'])
    failed = [case for case in full.findall('testcase') if case.find('failure') is not None]
    assert [identity(case) for case in failed] == [('tests.test_workspace_views', 'test_macro_view_live_rows_refresh_open_country_detail')]
    original_cases = {identity(case) for case in full.findall('testcase')}
    verified_cases = {identity(case) for case in full.findall('testcase') if case.find('failure') is None}
    verified_cases.update(identity(case) for case in resolved.findall('testcase'))
    assert original_cases == verified_cases and len(verified_cases) == int(full.attrib['tests'])
    ui = ET.parse(OUT / 'ui-process-final.xml').getroot().find('testsuite')
    assert int(ui.attrib['failures']) == int(ui.attrib['errors']) == 0
    focused = ET.parse(OUT / 'feature-verified.xml').getroot().find('testsuite')
    assert int(focused.attrib['failures']) == int(focused.attrib['errors']) == 0
    assert int(focused.attrib['skipped']) == 0
    frozen = json.loads((OUT / 'release-source-hashes.json').read_text(encoding='utf-8'))
    changed = [p for p, digest in frozen.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest() != digest]
    assert changed == ['tests/test_workspace_views.py'], 'Unexpected production/test source changes during verification'
    closed = json.loads((OUT / 'closed-source-hashes.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == digest for p, digest in closed.items())
    shell = read('ui-shell-theme-closed')
    assert shell['passed'] and shell['world_player_rng_unchanged']
    assert shell['maximum_bytes'] < 5000 and shell['max_party_count'] == 7
    original = json.loads((OUT / 'before-hashes.json').read_text(encoding='utf-8'))
    hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in original}
    modified = sorted(p for p in original if original[p] != hashes[p])
    unchanged = ['bond_calculations.py', 'financial_products.py', 'funds.py', 'fiscal.py',
                 'persistence_writer.py', 'player_accounting.py']
    assert all(original['src/kojakstreet/core/'+p] == hashes['src/kojakstreet/core/'+p] for p in unchanged)
    added = ['src/kojakstreet/core/politics.py', 'src/kojakstreet/ui_qt/widgets/pie_chart.py',
             'src/kojakstreet/ui_qt/widgets/society_politics_panel.py', 'tests/test_politics.py',
             'tests/test_politics_process.py', 'tools/politics_validation.py', 'tools/politics_writer_crash.py',
             'tools/politics_legacy_probe.py', 'tools/politics_report.py', 'tools/politics_ui_closeout.py']
    (OUT / 'closeout.json').write_text(json.dumps({'passed': True, 'modified_from_task_baseline': modified,
        'added': added, 'pricing_writer_player_sources_unchanged': unchanged,
        'exact_economic_controls': [0, 5, 20, 50], 'legacy': legacy,
        'full_suite_initial': full.attrib, 'focused_suite': focused.attrib, 'ui_process_suite': ui.attrib,
        'post_correction_workspace_suite': resolved.attrib, 'verified_suite_case_count': len(verified_cases),
        'updated_existing_test': changed, 'production_and_other_tests_unchanged': True,
        'heterogeneous_ui_shell': shell}, indent=2), encoding='utf-8')
    systems = '\n'.join(f'| {name} | {cycle or "kein Termin"} | {"Wahl" if competitive else "Review" if cycle else "Kontinuität"} |'
                        for name, cycle, competitive in SYSTEMS.values())
    rows = '\n'.join(f'| {years} | {old["coarse_seconds"]:.2f} / {new["coarse_seconds"]:.2f} s | '
                     f'{old["daily_seconds"]:.2f} / {new["daily_seconds"]:.2f} s | '
                     f'{new["country_politics_monthly_rows"]:,} | {new["politics_events_rows"]} |'
                     for years, old, new in histories)
    ordinary = '\n'.join(f'| {label} | {before["ordinary"]["wall_ms"][key]:.2f} ms | {after["ordinary"]["wall_ms"][key]:.2f} ms |'
                         for label, key in [('Median','median'),('p95','p95'),('Maximum einschließlich Startaufbau','max')])
    parts = []

    def section(n, title, text):
        parts.append(f'## {n}. {title}\n\n{text}\n')

    section(1, 'Geänderte Dateien', 'Gegen den zu Auftragsbeginn eingefrorenen Stand geändert:\n\n'+
            '\n'.join('- `'+p+'`' for p in modified)+'\n\nNeu:\n\n'+'\n'.join('- `'+p+'`' for p in added)+
            '\n\nAndere bereits vorhandene Änderungen im Arbeitsverzeichnis wurden erhalten. Referenz: `.cache/politics-implementation/baseline`, Dateiprüfsummen: `before-hashes.json` und `closeout.json`.')
    section(2, 'Politikmodell und Version', 'Politics Model 1, Calibration 1; Initialisierungs-/Wahlstreams enthalten den Modellstand. Checkpoint 9, Historyschema 3, Generator 4. Wirtschaftsmodell `workforce-demographics-v1`, Fast History 3 und Bundleformat 1 bleiben erhalten: Der wirtschaftliche Hook ist aus. Die Trajektorienidentität weist Politics Model 1 separat aus.')
    section(3, 'Sieben Systeme', '| System | Kalenderjahre | Mechanik |\n|---|---:|---|\n'+systems+'\n\nDie Gewichte sind Produktparameter, keine Abbildung realer Staaten. Kein Regime erhält einen direkten Wirtschafts- oder Stabilitätsbonus.')
    section(4, 'Parteimodell', 'Kompetitive Systeme 2–7 Parteien, One-Party genau eine, Absolute Monarchy und Authoritarian Republic keine Parteien. Stabile Länder-/Parteischlüssel, feste Economic-/Social-Achsen, initiale Mandate und separat letzte tatsächlich simulierte Stimmen. Keine Sitze, Umfragen, Wahlbeteiligung oder Politiker.')
    section(5, 'Ideologie', 'Zwei Achsen in [−1,+1], angezeigte Regierungsachsen nach Mandatsgewichten. Wirtschaft: interventionistisch bis marktliberal; Gesellschaft: progressiv bis konservativ. Ohne wirtschaftlichen Policykanal. Kohäsion verwendet tatsächlich beteiligte Regierungsparteien.')
    section(6, 'Namen', '36 neutrale Kombinationen aus neun Wörtern und vier Endungen. Ohne Wiederholung je Land aus eigenem Namensstream; unveränderliche IDs `Land:pN`. Namen sind kein Regime-/Kultur-/Wohlstandsclassifier.')
    section(7, 'RNG-Isolation', 'SHA-256 → lokale Random-Instanzen für politische Roots, Namen und jede Wahlsequenz/Partei. Kein Python-/NumPy-Welt-RNG-Verbrauch. Länder und Parteien werden vor Wahl/Formation nach stabiler ID sortiert. Reorder-, Navigation-, Save/Load- und Vergleichskontrollen bestehen.')
    section(8, 'Genesis', 'Alle Länder starten parlamentarisch, mit vier Parteien, Mandaten 40/30/20/10 %, identischen mechanischen Achsen und S_pol 75. Die Basis kompensiert genau diese gemeinsamen Strukturkomponenten. Nächste Wahl nach vier Kalenderjahren. Kein vergangenes Ergebnis; Namen und IDs sind länderspezifisch.')
    section(9, 'Heterogeneous', 'Gleichgewichtete Auswahl aus sieben Systemen, bei Wettbewerb gleichgewichtete Parteienzahl 2–7, unabhängige Politik-Domainroots, normalisierte positive Mandate, zufällige Achsen und Basis 70–85. Erste fällige Wahl/Review zwischen 180 Tagen und dem 4-/5-Jahresfenster. Keine vergangenen Wahlen; vorhandene Wirtschaftsbudgets unverändert.')
    section(10, 'Established-Historie', 'Initialisierung am Originalstart. Jeder Jahres-/Monatsbucket verarbeitet chronologisch alle übersprungenen 15.-Monatsberichte und Wahl-/Reviewtermine. Monatsmakroinputs werden im Bucket interpoliert und als `coarse_interpolated_monthly_report` markiert. Die drei angehängten Makrowerte werden anschließend exakt auf den wirtschaftlichen Bucket-Endzustand zurückgesetzt. Parteien, Ergebnis, Regierung und Übergang laufen durch den normalen 365-Tage-Burn-in weiter; keine Enddekoration.')
    section(11, 'Kalender', 'Eigenes gespeichertes `politics_calendar.next_due` als rekonstruierbares O(1)-Gate; Wahrheit sind Country-Termine und Sequenzen. Kalenderjahre statt 365×Jahre, Monatsende/Schaltjahr werden geklemmt. Genau-einmal-Verarbeitung, auch auf Monatsberichtstagen. Absolute Monarchy ohne erfundenen Wahltimer.')
    section(12, 'Wahlformel und Kalibrierung', 'Gemeinsamer Regierungsswing: `clip(0.5 Δgrowth − 0.4 Δunemployment − 0.3 Δinflation + 0.0002 (S_pol−75), ±0.04)`. Proportionale Verteilung auf Regierung/Opposition, eigener Rohnoise ±0.01 je Partei, positive Untergrenze 0.001, genau eine Normalisierung. Diese Grenzen betreffen Rohswing/-noise; die abschließende Normalisierung verschiebt die resultierenden Einzelanteile. Inputs stammen aus dem vorher veröffentlichten Bericht, mit Datum, Quelle und alter Baseline im unveränderlichen Ergebnis.')
    section(13, 'Regierungsbildung', 'Höchstens 127 Subsets. Mehrheit >50 %, Economic-Spanne/2 ≤0.55. Deterministisches Ranking nach Kohäsion, Größe, bisheriger Beteiligung, Unterstützung und IDs. Andernfalls stärkste Partei mit ausreichend nahen externen Unterstützern als supported minority, sonst caretaker. Presidential: Stimmenpluralität als Exekutive. Semi-Presidential: separate Exekutive und parlamentarisches Kabinett; Kohabitation erhält keinen automatischen Malus.')
    section(14, 'Nichtkompetitive Führung', 'One-Party und Authoritarian Republic bestätigen Kontinuität in fünfjährigem Review. Absolute Monarchy ohne periodischen Wechsel. Keine Fake-Wahlergebnisse, keine erfundenen 100-%-Stimmen. Führungsachsen bleiben stabile politische Identität.')
    section(15, 'Stabilitätskomponenten', 'Basis B; C als mandatgewichtete Economic-Abweichung in der Regierung; F = clip((1/Σshare²−1)/6); M = clip((0.5−gesicherte Unterstützung)/0.5). F/M/C werden dort verwendet, wo parlamentarische Unterstützung tatsächlich relevant ist. Makro-/Krisendruck separat, ohne Debt, Rating oder Funding.')
    section(16, 'Endgültige Stabilitätsformel', '`target = clip(B−10C−6F−8M,0,100)`; monatlich nähert sich der Strukturwert mit 25 % an. `S_pol = clip(structure−dated_transition,0,100)`. Übergang: geordneter Wechsel 3, caretaker 6, sonst 0; linear datiert über 92 Tage. `P_macro = min(12,max(0,−g)×80 + max(0,u−.08)×40 + max(0,π−.04)×40)`; betroffene Krise +6, insgesamt max18. `S_display = clip(S_pol−P_macro,0,100)`. Gleichartige mechanische Inputs erzeugen unabhängig vom Regimenamen dieselbe Formelantwort.')
    section(17, 'Kadenz und Reihenfolge', 'Fällige Politik vor dem Makrobericht, mit zuvor veröffentlichten Inputs; danach bestehender Monatsmakrobericht und eingefrorene Politikkomponenten, anschließend Unternehmen/Produktion/Workforce. Gewöhnliche Tage prüfen nur den nächsten Termin. Krisenstart/-ende aktualisiert nur den Anzeigedruck für tatsächlich betroffene Länder; auch eine Wahl zwischen Reports erhält vorhandenen Krisendruck. Keine täglichen Parteiscans, Normalisierungen, Koalitionen oder politischen Historykopien.')
    section(18, 'Politische Ereignisse', 'Typisierte Aktivierung, election_result, government_formed, incumbent_confirmed, minority_government, formation_pending, leadership_review und reine Anzeigeereignisse macro_pressure_changed beim Krisenstart/-ende. IDs aus Land, Seed, Modell, Ereignissequenz, Art und Datum. Ergebnis mit Inputs und Aktien-unabhängiger Regierungsbildung. Neutrale Nachricht ohne Momentum-/Preisimpuls; Krise bleibt ein getrenntes Ereignis.')
    section(19, 'Entscheidung zum wirtschaftlichen Hook', '**Deaktiviert.** Das vorhandene Coarseverfahren schreibt historische Staatsanleihequotes, Emissionen, Bondfonds-NAV und Yield Futures nicht gemeinsam entlang politischer Prämienrevisionen fort. Beim Handoff wird das aktive Bondset neu aufgebaut. Die geforderte Freigabebedingung ist damit nicht belegt; das Dokument erlaubt ausdrücklich die vollständige Politics-/UI-Auslieferung mit ausgeschaltetem Hook. Kein Ersatzkanal wurde eingebaut.')
    section(20, 'Prämienformel und Cap', 'Nur unbenutzter, getesteter Kandidat: `.0025 × clip((75−S_pol)/50,0,1)`, maximal 25 Basispunkte. Alle tatsächlich gespeicherten und laufenden Prämien sind 0; eingeschaltete oder von 0 abweichende Prämien werden beim Laden abgewiesen. Makro-Anzeigedruck ist kein Input.')
    section(21, 'Government-Bond-Integration', 'Kein laufender Spreadinput; Bondberechnung unverändert gegenüber dem Auftragsstart. Keine PD-, Rating-, Corporate-, Fiskal-, Nachfrage-, FX- oder Psychologieeinspeisung. Die Datei-Prüfsummen der maßgeblichen Preis-/Fiskal-/Accountingmodule sind unverändert.')
    section(22, 'Quote-Revisionen', 'Keine politischen Quote-Refreshes, keine gemischten neuen Quote-Revisionen, weil Premium aus ist. Der Politikblock hat eigene State-/Premiumrevision; die Premiumrevision bestätigt ausschließlich den Nullstand. Eine Freigabe des wirtschaftlichen Hooks benötigt weiterhin einen kohärenten Eventrefresh aller betroffenen Staatsquotes.')
    section(23, 'Globale Kurve und Yield Futures', 'Vorhandene Beobachtungs- und Derivatepfade unverändert. Exakte Kontrollläufe vergleichen auch diese Bücher und RNG-Zustände. Keine separate direkte Stabilitätseinspeisung. Der nicht implementierte historische Prämienverbrauch bleibt Freigabeblocker.')
    section(24, 'Emissionen und Coupons', 'Vorhandene Emissions- und Couponmechanik unverändert. Bestehende Coupons und Spieleranleihebücher sind Teil der exakten Kontroll-/Legacyvergleiche. Keine Neuemission oder Repricing durch Legacy-Aktivierung.')
    section(25, 'Coarse-Prämienintegration', 'Keine Prämienwirkung in Coarse oder Burn-in. Politikgeschichte ist kohärent fortgeschrieben, wirtschaftliche Geschichte bleibt der identische Nullhook-Kontrollpfad. Wirtschafts-/Fast-History-Hashsalts sind unverändert; Generator-/Historyversion und politische Identität sind separat versioniert.')
    section(26, 'Legacy-Verhalten', f'Echter versiegelter Checkpoint 8 / History 2 / Generator 3 geladen. Aktivierung {legacy["activation_date"]}, S_pol 75, Nullprämie, keine Vergangenheit, nur zukünftige Termine. Wirtschaft, Spielerbücher, Coupons, Datum und Python-/NumPy-RNG exakt erhalten. Originalkonfiguration und History-ID bleiben erhalten; die ursprüngliche Historyschema-Version wird als Herkunft gespeichert. Versiegelte Quelle wurde ausschließlich kopiert und bleibt byteidentisch. Zusätzlich Metadata-only-Aktivierung im Live-Save getestet.')
    section(27, 'Persistenz und Versionierung', 'Vorabvalidierung der Featureversionen, Systeme, Partei-IDs/-Namen, Achsen, endlichen Shares, Summen, Regierungsreferenzen, Kalender, Vergangenheitsdaten, Ergebnisse, Übergänge und begrenzten Events vor Restore-Mutation. Checkpoint 4–9 unterstützt. Bestehender einzelner Ordered Writer und sein Journal unverändert; neue Tabellen nutzen dieselbe Transaktion. Gebündelter Identitäts-Upsert per Event-ID bzw. (Datum,Land) verhindert Verlust anderer Länder und doppelte Replayzeilen.')
    section(28, 'Historienkadenz', '20 aktuelle vollständige Länderblöcke; monatlich genau 240 skalare Zeilen/Jahr; datierte Ereignisse und unveränderliche Wahlinputs. Keine täglichen Parteien-, Polling- oder Stabilityarrays. Letzte 32 Ereignisse als begrenzter State; vollständige Ereignishistorie in DuckDB. Die neue UI fragt keine versteckten Historien ab.')
    section(29, 'Population im Overview', 'Ein zusätzlicher kleiner Population-KPI in der vorhandenen Länder-Kopfzeile. Bestehende Karten, Typografie und Zahlenformatierung; kein Overview-Redesign.')
    section(30, 'Tab-Architektur', 'Genau ein fünfter Tab nach Sectors. Panel, Karten, Modelle und beide Diagramme einmal aufgebaut; aktive Updates patchen Inhalte. Executive/Cabinet im semi-präsidentiellen Fall getrennt beschriftet. Scrollbarer Inhalt hält schmale Fenster bedienbar; reservierte Diagramm-/Tabellenflächen bleiben auch in leeren Zuständen erhalten.')
    section(31, 'Wiederverwendete UI', 'Vorhandenes APP_STYLESHEET, KpiCard, DetailValue, SectionTitle, Muted, EmptyState, QTableView, SimpleTableModel und Table-Performance-Konfiguration. Unveränderte vorhandene vier Detailtabs als Referenz vor/nachher aufgenommen. Keine neue Navigation, Palette oder Chartbibliothek.')
    section(32, 'Workforce-Donut', 'Genau Basic, Skilled, Highly Qualified als Supply Mix. Tabelle nennt Prozent, Supply, Demand und Coverage; Einheiten workforce equivalents. Keine Arbeitslosen- oder Demand-Slices. Stabile Farben, Hovertext und zugängliche Textalternative. Wachstum vor erstem beobachteten Intervall ehrlich Not yet observed, danach annualisiert mit Intervalltooltip.')
    section(33, 'Politischer Donut', 'Nur nach tatsächlich ausgeführter kompetitiver Wahl: 2–7 reale Stimmenanteile, stabile Parteifarben, Namen, Regierungsmarker, Datum und Wahlauswertungstyp. Zuvor Initial mandate allocation – no election recorded mit Mandatsliste und sichtbarem Leerzustand. Kein Others-Bucket, kein erfundener Wahlkreis.')
    section(34, 'Nichtkompetitive Darstellung', 'Führung/Kontinuität statt Wahlgrafik. One-Party nennt Partei, Ideologie und Review mit No vote recorded. Absolute Monarchy und Authoritarian Republic zeigen Führungshinweise ohne Fake-Parteien. Reservierte Flächen wechseln zwischen bestehenden EmptyState-Karten und Diagramm/Tabelle.')
    section(35, 'On-demand-Vertrag', '`{view:"macro",selection:{region,area:"society_politics"}}`: ein Land mit wiederverwendetem population_society und kleinem Politikblock. Breite Snapshots entfernen Politik explizit; keine 20-Länder-Parteiarrays oder neuen Root-Skalare. Länder-/Tabwechsel setzen Scope, spätes Ergebnis eines alten Scope wird abgewiesen. Sichtbare lokale/Worker-Ansicht zeigt Wahlereignisse zwischen Monatsberichten; versteckte Tabs erhalten keine Pieupdates.')
    section(36, 'Gemessene Payload', f'Ausgewählter Makroblock {after["selected_macro_bytes"]:,} Bytes; serialisierte GameState-Payload des ausgewählten Workerscope {after["selected_payload_bytes"]:,} Bytes, ohne History. Nach Established 5 Jahren {histories[0][2]["selected_payload_bytes"]:,} Bytes. Alle 20 Länder einer echten heterogenen Startwelt einzeln projiziert: maximal {shell["maximum_bytes"]:,} Bytes, einschließlich sieben Parteien. Welt-/Spieler-/RNG-Zustand nach Projektion und Navigation exakt unverändert. Projektion Median {after["selected_projection_ms"]["median"]:.3f} ms / p95 {after["selected_projection_ms"]["p95"]:.3f} ms. Ziel ~5 KB eingehalten.')
    section(37, 'Aufnahmen und Sichtprüfung', 'Alle neun verlangten Szenarien sowie die vier vorhandenen Tabs und ergänzende untere Scrollpositionen im vollständigen Produktionsfenster erfasst. Vorher-Aufnahmen unter readable-before-shell-closed; nachher unter readable-after-shell-closed. Ein reiner Offscreen-Artefakt der separaten Detail-Widget-Aufnahmen wurde durch Aufnahme im tatsächlichen App-Fenster beseitigt. Vergleich bei 1400×1200; schmal 1080×720, groß 1920×1400. Offscreen lädt dieselben Windows-Segoe-UI-Schriften explizit. Initiale Mandate, sieben Parteien, Presidential, Semi-Cohabitation, drei nichtkompetitive Fälle, kleine/große Fenster manuell auf Abstände, Schrift, Farben, Tabellen, Leerzustände und Scrollzugänglichkeit geprüft. Galerie: `politics-v1-ui-captures-2026-10-07.md`. Die Regimeaufnahmen sind gezielte Simulator-/Regierungsfixtures; sie behaupten keine nicht simulierte Weltgeschichte.')
    section(38, 'Gewöhnliche Tage', '| Kennzahl | Vorher | Nachher |\n|---|---:|---:|\n'+ordinary+'\n\nIsolierte 90-Tage-Kontrolle mit Seed 1729 und gleicher Wirtschaftsversion, Writer aktiv; nachher eine zusätzliche Wahl. Maximum enthält den vorhandenen Start-/Journalaufbau. CPU-Median vorher '+f'{before["ordinary"]["cpu_ms"]["median"]:.2f}'+' ms, nachher '+f'{after["ordinary"]["cpu_ms"]["median"]:.2f}'+' ms. Kein Hinweis auf eine materielle gewöhnliche Tagesregression; Differenzen nicht als Politik-Beschleunigung ausgelegt.')
    section(39, 'Berichte, Wahlen und UI', f'Berichtstag-Median vorher {before["reports"]["median"]:.2f} ms, nachher {after["reports"]["median"]:.2f} ms. Politikphase monatlich Median {after["monthly_politics_ms"]["median"]:.3f} ms, max {after["monthly_politics_ms"]["max"]:.3f} ms. Wahlphase {after["event_phase_ms"]["median"]:.3f} ms; vollständiger Wahltag {after["elections"]["median"]:.2f} ms (ein Eventtag). Koalitionssuche Median {after["coalition_ms"]["median"]:.3f} ms. UI-Patchmessung in `readable-after-shell-closed/patch-cost.json`; keine Animation/Timer. Government-Quote-Refresh entfällt wegen ausgeschaltetem Hook.')
    section(40, 'Established-Generierung', '| Jahre | Coarse vorher / nachher | 365 Tage vorher / nachher | Politik-Monatszeilen | Events |\n|---|---:|---:|---:|---:|\n'+rows+'\n\nAlle Kontrollen wirtschaftlich und im RNG exakt identisch, sowohl direkt nach Coarse als auch nach Burn-in. Diese langen Laufzeiten entstanden neben der vollständigen Testsuite und teilweise Save-/Legacy-Prüfungen; Host-/Writerkonkurrenz beeinflusst Wall/CPU und Startmaxima. Sie sind Vollständigkeits-/Kostenmessungen, keine isolierte kleine Prozent-Regressionsmessung. Die isolierte Tagesmessung steht in Punkt 38. 5/20 sind gezielte Kern-Generatorproben; die vorhandene Produktauswahl 50/75/100 Jahre wurde nicht erweitert.')
    section(41, 'Speicher und Writer', f'90-Tage-Prozess-Peak vorher {before["peak_rss_bytes"]/1024**2:.1f} MiB, nachher {after["peak_rss_bytes"]/1024**2:.1f} MiB. Gemessene Queue-Tiefe {after["writer_queue_depth"]}, bestehende Queue-Kapazität {after["writer_capacity"]}; gleiche zwei Journalslots und Backpressure. Langlauf maximal zwei wartende Batches; bestehende historische Kompaktion/Writerwartezeiten sind auch in der unveränderten Referenz vorhanden. Nach 50 Jahren umfassen alle 20 Current-JSONblöcke zusammen {histories[2][2]["politics_current_json_bytes"]:,} Bytes. Lange Probe-Peaks stehen in den Result-JSONs; vollständige Kontroll-Serialisierung beeinflusst sie stark. Politikdaten sind begrenzte Current-Blöcke plus sparse Facts; kein zweiter Writer. Neue sparse Upserts löschen alle betroffenen Identitäten gebündelt. Kanonische interne Datumswerte und korrekt escapte Textschlüssel vermeiden den gemessenen DuckDB-Konvertierungsaufwand großer Python-Listen; danach unveränderte transaktionale COPY-Persistenz. 2.400 Monatszeilen werden wiederholt exakt geprüft, einschließlich fremder Länder, Apostrophen, JSON und DOUBLE-Werten.')
    section(42, 'Testsuite', f'**Alle {len(verified_cases)} Testfälle erfolgreich verifiziert**, mit getrennten, unveränderten XML-Nachweisen. Vollständiger Lauf: {full.attrib["tests"]} Fälle, {int(full.attrib["tests"])-1} bestanden, eine veraltete Erwartung von vier Detailtabs, Dauer {float(full.attrib["time"]):.2f} s. Der Auftrag verlangt ausdrücklich den fünften Tab. Diese Erwartung wurde auf genau fünf Tabs angepasst und zusätzlich um die exakten Namen und die Reihenfolge aller fünf Tabs verschärft. Danach bestehen alle {resolved.attrib["tests"]} Tests des betroffenen Workspace-Moduls. Die Testidentitäten werden gegen den Vollsuite-Lauf abgeglichen: jeder ursprüngliche Fall hat einen erfolgreichen Nachweis. Es gab keinen zweiten vollständigen Lauf; Produktionscode und alle anderen Tests sind gegenüber dem vollständigen Lauf per SHA-256 unverändert. Abschließende Politics-/UI-/Workerprüfung: **{focused.attrib["tests"]} bestanden**, einschließlich echtem Worker-Scopefall. Zusätzlicher UI-Prozesslauf {ui.attrib["tests"]} bestanden. Keine Toleranzen erweitert und keine Tests deaktiviert. Ruff für alle neuen Dateien bestanden. Der vorhandene UP017-Hinweis im bestehenden Workspace-Test ist unverändert geblieben. XML-Evidence in `.cache/politics-implementation`.')
    section(43, 'Save/Load und Crash-Recovery', 'Save/Load vor/nach Wahl sowie gleichzeitigem Monatsbericht und laufendem Regierungsübergang reproduziert den Featurestate exakt. Aktueller JSONblock und historische DOUBLE-Werte werden ohne Rundungsabweichung verglichen. Fehlerhafte Featurepayloads werden vor Buchmutation abgewiesen. Vier reale Windows-Prozessabbrüche: vor Transaktion, vor Commit, nach Commit, nach Acknowledge; zweimaliges Wiederöffnen/replay bleibt genau einmal. Alte veränderte Testbundle-Datei wurde korrekt per Prüfsumme abgewiesen; unveränderter versiegelter Referenzbundle besteht den eigentlichen Legacytest. Durability nicht gelockert.')
    section(44, 'Multi-Seed-Verteilungen und Korrelationen', f'200 Seeds ×20 Länder = {distributions["sample_count"]:,} Roots. Systeme: '+', '.join(f'{SYSTEMS[k][0]} {v}' for k,v in distributions['systems'].items())+f'. Maximaler absoluter Pearsonwert über Systemindikatoren/Parteienzahl/Basis/Stability/Achsen gegen Population, GDP-pro-Kopf-Proxy, Birth/Death und Qualified-Share: {distributions["maximum_absolute_correlation"]:.4f}. Kein auffälliger systematischer Wealth-/Demografie-/Workforcezusammenhang. Eine Stichprobe beweist keine perfekte statistische Unabhängigkeit; die getrennten Domainstreams sichern den strukturellen Ausschluss.')
    section(45, 'Langfristiges Verhalten', 'Alle sieben Systeme über 50 politische Kalenderjahre in Featuretests: genau 600 Berichte pro Land, keine Terminauslassungen, kompetitive tatsächliche Wahlergebnisse und nichtkompetitive Reviews ohne Fake-Wahlen. Stabilität bleibt endlich und begrenzt; Premium 0. Zusätzlich komplette Welt-Coarse-/365-Tage-Läufe für 5/20/50 Jahre mit dauerhaft gespeicherten Wahl- und Regierungsereignissen sowie sparsamen Krisen-Anzeigeereignissen. Der langfristige politische Pfad beeinflusst die Kontrollwirtschaft nicht.')
    section(46, 'Verbleibende Grenzen', 'Bondprämie absichtlich aus; ihre Freigabe verlangt historische Quote-/Kurven-/Fonds-/Derivateintegration und gemeinsame Revisionsprüfungen. Mandate sind die dokumentierte V1-Unterstützungsabstraktion, keine Sitze/Turnout. Reviews bestätigen Kontinuität ohne Dynastien/Coups. Stabilität ist ein kalibrierter Spielindikator. Coarse-Wahlinputs sind interpolierte Monatsproxies mit Provenienz. Keine Regimewechsel, Politiker, Umfragen, FDI, neuen Fiskalpfade oder politische Chart-History-UI.')
    section(47, 'Urteil', 'Politics V1 schafft datierte politische Länderidentität, tatsächliche Wahlergebnisse, nachvollziehbare Regierungen und getrennte sichtbare Stabilität. Exakte wirtschaftliche Nullhook-Kontrollen und erhaltenes Accounting verhindern eine neue wirtschaftliche Rückkopplung. Der aktive Scope bleibt klein, gewöhnliche Tage bleiben am Datumsgate, Persistenz nutzt die bestehende sichere Pipeline. Die fünfte Ansicht verwendet sichtbar Kojak Streets vorhandene Gestaltung. Freigegeben: Politics, sparse History und Society & Politics. Nicht freigegeben: wirtschaftlicher Bondhook.')
    report = ROOT / 'docs/politics-v1-society-politics-implementation-2026-10-07.md'
    report.write_text('# Politics V1 und Society & Politics – Umsetzung\n\nStand: 7. Oktober 2026. Grundlage: freigegebener Implementierungsauftrag; Politik/UI vollständig, wirtschaftlicher Hook gemäß Freigabegate ausgeschaltet.\n\n'+'\n'.join(parts), encoding='utf-8')
    captures = OUT / 'readable-after-shell-closed'
    assert len(list(captures.glob('0[1-9]-*.png'))) >= 9
    assert len(list((OUT / 'readable-before-shell-closed').glob('*.png'))) == 4
    gallery = ['# Society & Politics – geprüfte UI-Aufnahmen\n', 'Gezielte Simulatorzustände, vorhandenes Kojak-Street-Theme; je nach Fensterhöhe ergänzende untere Scrollposition.\n']
    gallery.append('## Vorhandene Detailtabs vor der Änderung\n')
    for p in sorted((OUT / 'readable-before-shell-closed').glob('*.png')):
        gallery.append(f'### Vorher: {p.stem}\n\n![{p.stem}](<{p.as_posix()}>)\n')
    gallery.append('## Ausgelieferter Stand\n')
    for p in sorted(captures.glob('*.png')):
        gallery.append(f'## {p.stem}\n\n![{p.stem}](<{p.as_posix()}>)\n')
    gallery.append('## Vollständiges App-Fenster\n\nEchte heterogene Startwelt; gleiche App-Styles und Schrift. Bei 1080×720 ist die bestehende horizontale Workspace-Scrollleiste erforderlich; bei 1360×860 und 1920×1400 nicht. Vertikales Scrollen erschließt die unteren Inhalte.\n')
    for p in sorted((OUT / 'ui-shell-theme-closed').glob('*.png')):
        gallery.append(f'### {p.stem}\n\n![{p.stem}](<{p.as_posix()}>)\n')
    (ROOT / 'docs/politics-v1-ui-captures-2026-10-07.md').write_text('\n'.join(gallery), encoding='utf-8')
    print(str(report))


if __name__ == '__main__':
    main()
