"""Build final comparison tables only from retained, validated measurements."""
from __future__ import annotations

import json
import statistics
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import day_transition_audit_summary as aggregate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.cache/performance-remediation'
BASE = ROOT / '.cache/day-transition-audit'
REPORT = ROOT / 'docs/performance-remediation-2026-10-05.md'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def num(value):
    return f'{value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def table(headers, rows):
    def cell(value):
        return str(value).replace('|', r'\|').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows]])


def main():
    summary = read(OUT / 'reaudit/summary.json')
    old = read(BASE / 'summary.json')
    raw = read(OUT / 'reaudit/merged-results.json')
    validation = read(OUT / 'reaudit/validation.json')
    deterministic = read(OUT / 'determinism-comparison.json')
    suite = ET.parse(OUT / 'final-tests.xml').getroot().find('testsuite')
    assert suite is not None and int(suite.attrib['failures']) == int(suite.attrib['errors']) == 0
    assert validation['passed'] and not deterministic['mismatches']
    assert all(item['economic_signature_equal'] for item in summary['comparisons'].values())
    manifest = read(OUT / 'release-source-manifest.json')
    for path in (OUT / 'reaudit').glob('environment-*.json'):
        assert read(path)['source_sha256'] == manifest, path.name
    parts = []
    def add(value): parts.append(value)
    def m(run, metric='total_ms', kind='all', source=summary):
        return source['runs'][run]['types'][kind][metric]
    def median(run, metric='total_ms', kind='all', source=summary):
        return m(run, metric, kind, source)['median_bytes' if metric == 'response_bytes' else 'median_ms']
    add('## Finaler Re-Audit')
    add('Alle folgenden Latenzreihen wurden nach den drei Änderungen erneut und nacheinander gemessen. '
        'Einrichtung, Laden und die absichtliche Spielpause sind ausgeschlossen. cProfile und tracemalloc '
        'laufen separat. Mediane verschachtelter Teilzeiten sind nicht additiv. MB bedeutet 1.000.000 Bytes. '
        'Die Messumgebung und Definitionen des ursprünglichen Audits gelten weiter; T2 umfasst jetzt auch '
        'das Einlesen und Anwenden des expliziten Tages-Deltas.')
    add(f"**Gesamte Suite: {suite.attrib['tests']} Tests bestanden**, {num(float(suite.attrib['time']))} s. "
        f"**365-Tage-Vergleich: {deterministic['fields_per_day']} Signaturfelder je Tag**, "
        f"{deterministic['database_tables']} Datenbanktabellen, keine Abweichung. "
        'Die vollständigen Checkpoints an Tag 15, 31, 181 und 365 sowie der abschließende Checkpoint '
        'stimmen einschließlich Historien, Reihenfolge und RNG exakt überein. Diese Checkpoints verwenden '
        'den bestehenden Save-Vertrag mit seinen Grenzen für lokale Anzeigehistorien; die vollständige '
        'persistente History wird zusätzlich durch den Datenbankvergleich geschützt. In der Datenbank werden nur '
        'die zufällige History-ID und gemessene Telemetrie-Laufzeiten aus dem Wertvergleich ausgenommen; '
        'Tabelleninhalte, Zeilenzahlen, ökonomische Zahlen und restliche Metadaten bleiben einbezogen. '
        f"Der Audit prüft zusätzlich {validation['qt_samples_checked']} Qt-Tagesmessungen in "
        f"{validation['qt_runs_checked']} Reihen auf Abschluss, Reihenfolge der Zeitpunkte, Hauptthread, "
        'Modelle und Worker-Beendigung. Ein unverändertes Produktionsfenster bestätigt den Hauptthread separat.')
    add('### Abschließender Vorher/Nachher-Vergleich')
    chart_names = {'none': 'Ohne Chart', 'detail': 'Detail Line ALL', 'candle': 'Detail Candle ALL',
                   'preview': 'Preview ALL', 'heavy': 'Detail ALL + EMA 20/50/200'}
    comparisons = {}
    chart_rows = []
    for key, label in chart_names.items():
        name = f'qt-mature-{key}-valid'
        before = median(name, source=old)
        after = median(name)
        assert read(BASE / f'{name}.json')['signature'] == raw[name]['signature'], name
        comparisons[name] = {'same_economic_rng_signature': True, 'before_ms': before, 'after_ms': after}
        chart_rows.append([label, 20, num(before), num(after), num(before / after) + '×',
                           num(m(name)['p95_ms']), num(m(name, 'heartbeat_max_ms')['max_ms'])])
    add(table(['Reife Welt', 'n', 'Vorher T0→T4 ms', 'Final T0→T4 ms', 'Faktor', 'Final p95 ms',
               'Größter Heartbeat-Abstand ms'], chart_rows))
    add('Der finale Timer-Vertrag aktualisiert gegenüber dem alten reinen Quote-Pfad zusätzlich alle '
        'öffentlichen Unternehmens-, Länder-, Portfolio- und Historienfelder. Deshalb ist Phase 1 als '
        'isolierter History-Gewinn getrennt ausgewiesen. Der abschließende Wert ist die tatsächlich '
        'ausgelieferte Kombination aller Änderungen, einschließlich dieses vollständigeren Zustandsvertrags.')

    before_step = aggregate.load_run(OUT / 'step-before/qt-manual-step-valid.json')
    after_step = aggregate.load_run(OUT / 'step-after/qt-manual-step-valid.json')
    after_heavy = aggregate.load_run(OUT / 'step-after/qt-manual-heavy-valid.json')
    for run in (after_step, after_heavy):
        assert len(run['rows']) == 20 and not run['errors']
        assert all(not row['force_refresh'] for row in run['rows'])
        assert all(row['worker']['calls'].get('worker.day_delta') == 1 for row in run['rows'])
    for path in (OUT / 'step-after').glob('environment-*.json'):
        assert read(path)['source_sha256'] == manifest, path.name
    assert before_step['rows'][0]['date'] == after_step['rows'][0]['date']
    assert after_step['signature'] == raw['headless-mature']['signature'] == after_heavy['signature']
    step_rows = []
    def row_median(rows, key): return statistics.median(row[key] for row in rows)
    for label, rows in [('Vor Phase 3, gleiche ersten 3 Tage', before_step['rows']),
                        ('Nach Phase 3, gleiche ersten 3 Tage', after_step['rows'][:3]),
                        ('Nach Phase 3, alle 20 Tage', after_step['rows']),
                        ('Nach Phase 3, Heavy/EMA, 20 Tage', after_heavy['rows'])]:
        step_rows.append([label, len(rows), num(row_median(rows, 'total_ms')),
                          num(row_median(rows, 'response_bytes') / 1e6),
                          num(max(row['heartbeat_max_ms'] for row in rows))])
    add(table(['Manueller Benutzer-Step', 'n', 'Median T0→T4 ms', 'Median Antwort MB',
               'Größter Heartbeat-Abstand ms'], step_rows))
    step_spans = [
        ('Worker State-Encoding: vorher Vollstate, nachher Status', 'worker.state_encode'),
        ('Worker Tages-Diff + Datenkörper', 'worker.day_delta'),
        ('JSON encode', 'worker.json_encode'),
        ('Pipe write', 'worker.pipe_write'),
        ('JSON decode', 'parent.json_decode'),
        ('Datenkörper decode', 'parent.decode_day_delta'),
        ('State-Rekonstruktion: vorher Vollstate, nachher Status', 'parent.decode_state'),
        ('Tagesänderungen anwenden', 'parent.apply_day_delta'),
        ('Markt-Vollrefresh einschließlich History-Normalisierung', 'ui.markets.refresh'),
        ('Inkrementelle Markt-/Quote-Aktualisierung', 'ui.markets.apply_live_quotes'),
    ]
    span_rows = []
    for label, key in step_spans:
        values = [statistics.median(r['spans'].get(key, 0) for r in rows)
                  for rows in [before_step['rows'], after_step['rows'][:3], after_step['rows']]]
        span_rows.append([label, *map(num, values)])
    for label, key in [('UI T3−T2', 'model_ms'), ('UI/Chart/Paint T4−T2', 'ui_ms')]:
        span_rows.append([label, *[num(row_median(rows, key)) for rows in
                                 [before_step['rows'], after_step['rows'][:3], after_step['rows']]]])
    add(table(['Step-Teilzeit ms, verschachtelt', 'Vorher n=3', 'Nachher gleiche 3', 'Nachher n=20'], span_rows))
    add('Der gemeinsame Helfer `game_state_payload` wird weiterhin für den kleinen Statuskopf '
        'verwendet. Seine verbleibende minimale Laufzeit bedeutet keinen Vollsnapshot. '
        'Alle 40 abschließenden Benutzer-Steps fordern `force_refresh=False` an und erzeugen '
        'jeweils genau ein Tages-Delta. Der Code wählt hierfür ausdrücklich das Statusprofil; '
        'die zusätzlichen aktuellen Felder und neuen Historienpunkte stehen im Tages-Delta. '
        'Die fehlende-Delta-Fehlerprüfung verhindert einen stillen Vollsnapshot-Ersatz.')
    add('Beim alten Benutzer-Step steckt die History-Normalisierung im vollständigen '
        'Markt-Refresh. Ihre Einzelzeit wurde in dieser Step-Reihe nicht separat isoliert. '
        'Ein nicht aufgerufener Live-Append-Hook würde hier fälschlich nach null History-Aufwand '
        'aussehen. Die Tabelle zeigt deshalb den gesamten Refresh einschließlich dieser Arbeit; '
        'die getrennten History-Aufrufzahlen stehen in Phase 1 und im finalen UI-Profil.')
    comparisons['manual_step'] = {'before_3_ms': row_median(before_step['rows'], 'total_ms'),
                                  'after_same_3_ms': row_median(after_step['rows'][:3], 'total_ms'),
                                  'after_20_ms': row_median(after_step['rows'], 'total_ms'),
                                  'after_20_bytes': row_median(after_step['rows'], 'response_bytes'),
                                  'same_economic_rng_signature_as_timer': True}

    add('### Alle Tagtypen und Jahresgrenze')
    latency_rows = []
    selections = []
    for name, label in [('headless-year-clean', 'Headless erstes Jahr'),
                        ('qt-year-clean-valid', 'Qt erstes Jahr')]:
        for kind, title in [('all', 'alle Tage'), ('normal_no_flush', 'normal ohne Flush'),
                            ('report', 'Reporting'), ('month_end', 'Monatsende ohne 31.12.'),
                            ('year_end', '31.12.'), ('flush', 'Flush')]:
            selections.append((name, kind, f'{label}: {title}'))
    for kind, title in [('year_end', '31.12.'), ('year_start', '01.01.'), ('annual_issue', '03.01. / Bond-Pfad')]:
        selections.append(('qt-year-repeat-valid', kind, f'Identische Jahresgrenze: {title}'))
    selections.append(('headless-mature', 'all', 'Headless reife Welt'))
    for name, kind, label in selections:
        stats = m(name, kind=kind)
        latency_rows.append([label, stats['n'], *[num(stats[k]) for k in
                             ('min_ms', 'median_ms', 'mean_ms', 'p95_ms', 'max_ms')]])
    add(table(['Reihe / Tagtyp', 'n', 'Min ms', 'Median ms', 'Mittel ms', 'p95 ms', 'Max ms'], latency_rows))
    year_rows = []
    for kind, title in [('all', 'Alle 365 Tage'), ('normal_no_flush', 'Normal ohne Flush'),
                        ('report', 'Reporting'), ('month_end', 'Monatsende'), ('flush', 'Flush')]:
        before = median('qt-year-clean-valid', kind=kind, source=old)
        after = median('qt-year-clean-valid', kind=kind)
        year_rows.append([title, num(before), num(after), num(before / after) + '×'])
    add(table(['Erstes Qt-Jahr: Original gegen endgültigen Stand', 'Vorher Median ms',
               'Nachher Median ms', 'Faktor'], year_rows))
    year_before_seconds = m('qt-year-clean-valid', source=old)['mean_ms'] * 365 / 1000
    year_after_seconds = sum(row['total_ms'] for row in raw['qt-year-clean-valid']['rows']) / 1000
    add(f'Die Summe der 365 gemessenen Tagesübergänge beträgt '
        f'**{num(year_before_seconds)} → {num(year_after_seconds)} Sekunden** '
        f'({num((year_after_seconds / year_before_seconds - 1) * 100)} % länger). '
        'Einrichtung, Laden und die absichtliche Spielpause sind in dieser Summe nicht enthalten. '
        'Damit verbessert die Kombination den reifen Zustand und den manuellen Step deutlich, '
        'beschleunigt aber den hier gemessenen kompletten ersten Jahreslauf nicht.')
    add('Der Vergleich des ersten Jahres ergänzt die reife Welt: Kleine Historien bieten weniger '
        'Einsparpotenzial. Der vollständigere öffentliche Tageszustand verursacht gleichzeitig '
        'zusätzliche Vergleiche und Übertragung. Ein Faktor unter 1 in dieser Tabelle bedeutet '
        'eine Verlangsamung dieses Tagtyps; die isolierten History-Gewinne dürfen deshalb nicht '
        'als pauschale Beschleunigung jeder Spielsituation gelesen werden.')
    gc_before = aggregate.load_run(OUT / 'reaudit-exploratory-delta-gc/qt-year-clean-valid.json')
    assert gc_before['signature'] == raw['qt-year-clean-valid']['signature']
    gc_rows = []
    for label, rows in [('Delta-Prototyp vor Worker-GC-Korrektur', gc_before['rows']),
                        ('Endgültiger Stand', raw['qt-year-clean-valid']['rows'])]:
        normal = [row for row in rows if aggregate.kind(row) == 'normal' and not row['spans'].get('store.flush', 0)]
        gc_rows.append([label, len(normal), num(statistics.median(r['total_ms'] for r in normal)),
                        num(statistics.median(r['spans'].get('worker.day_delta', 0) for r in normal)),
                        num(statistics.median(r['worker_gc_ms'] for r in normal))])
    add(table(['Zusätzliche Langlaufkorrektur, normale Tage ohne Flush', 'n', 'T0→T4 Median ms',
               'Delta-Erzeugung Median ms', 'Worker GC Median ms'], gc_rows))
    add('Der erste vollständige Qt-Jahreslauf deckte im Delta-Prototyp einen neuen Engpass auf: '
        'Während der Erzeugung kurzlebiger Operationslisten und Pickle-Memos wurden diese Objekte '
        'in ältere GC-Generationen verschoben. Vollständige Sammlungen scannten dadurch wiederholt '
        'den immer größeren Weltzustand; am Ende lagen einzelne solche Sammlungen über drei Sekunden. '
        'Der Encoder gibt jetzt seine temporären Listen vor einer gezielten jungen Sammlung frei '
        'und stellt die automatische Speicherbereinigung unmittelbar wieder her. Die Wirtschaft '
        'bleibt unberührt. Der endgültige komplette Re-Audit wurde danach wiederholt; der erste Lauf '
        'ist separat als Diagnose archiviert. Auch die anfänglichen Step-Messungen mit irrtümlicher '
        'Modell-Neuerstellung durch überlappende Ticker sind ausschließlich als Diagnose erhalten.')

    boundary_rows = []
    ui_selections = [(f'qt-mature-{key}-valid', 'all', label) for key, label in chart_names.items()]
    ui_selections += [(name, kind, label) for name, kind, label in selections if name.startswith('qt')]
    ui_selections.append(('qt-manual-step-valid', 'all', 'Manueller Step, finale Wiederholung'))
    for name, kind, label in ui_selections:
        boundary_rows.append([label, *[num(median(name, key, kind)) for key in
                              ('simulation_ms', 'persistence_transfer_ms', 'model_ms', 'paint_wait_ms', 'total_ms')]])
    add(table(['Zeitgrenzen, Median ms', 'T1−T0', 'T2−T1', 'T3−T2', 'T4−T3', 'T4−T0'], boundary_rows))

    add('### Finaler History-Aufwand und Aktualisierung der Oberfläche')
    counts = []
    for key, label in chart_names.items():
        profile = summary['profiles'][f'qt-profile-{key}-valid']
        result = []
        for function in ('_append_live_history', 'merge_history_by_date', 'history_date', 'history_ordinal', 'fromisoformat', 'sorted'):
            result.append(num(sum(row['calls_per_sample'] for row in profile['all']
                                  if row['function'] == function or function in ('fromisoformat', 'sorted') and function in row['function'])))
        counts.append([label, profile['samples'], *result])
    add(table(['Separates UI-Profil', 'n', 'Append-Aufrufe', 'Merges', 'history_date', 'history_ordinal', 'fromisoformat', 'sorted'], counts))
    paint_rows = []
    for key, label in chart_names.items():
        name = f'qt-mature-{key}-valid'
        run = summary['runs'][name]
        paint_rows.append([label, run['samples'], run['signal_totals']['visible_chart_calls'],
                           run['signal_totals']['hidden_chart_calls'], run['signal_totals']['paints'],
                           num(median(name, 'heartbeat_max_ms')), num(m(name, 'heartbeat_max_ms')['p95_ms']),
                           num(median(name, 'response_bytes') / 1e6)])
    add(table(['20 reife Tage', 'n', 'Sichtbare Chart-Aufrufe', 'Verborgene Chart-Aufrufe', 'Paints',
               'Max-Gap je Tick Median ms', 'Max-Gap je Tick p95 ms', 'Antwort MB Median'], paint_rows))
    add('Die finalen Bilder `qt-mature-detail-valid.png`, `qt-mature-candle-valid.png`, '
        '`qt-mature-preview-valid.png` und `qt-mature-heavy-valid.png` '
        'wurden zusätzlich visuell geprüft: ALL-Zeitachse, Line beziehungsweise Candle mit '
        'Höchst-/Tiefstwerten, aktueller Kurs, Positionierungsanzeige und die drei EMA-Linien '
        'in der Heavy-Variante sind vorhanden. '
        'Die numerische History-Gleichheit wird durch die automatisierten Vergleiche geprüft; '
        'die Bildkontrolle ergänzt diese um die tatsächliche Darstellung.')

    add('### Verbleibende Zeitanteile und Profile')
    mature = summary['runs']['qt-mature-none-valid']['types']['normal_no_flush']
    span_names = ['simulation.core', 'store.record_day', 'store.flush', 'worker.day_delta',
                  'worker.state_encode', 'worker.json_encode', 'worker.pipe_write', 'parent.json_decode',
                  'parent.decode_day_delta', 'parent.apply_day_delta', 'parent.apply_result',
                  'ui.markets.append_live_history']
    add(table(['Reife normale Tage ohne Flush: Teilzeit', 'Median ms', 'p95 ms'],
              [[key, num(mature['spans'].get(key, {'median_ms': 0})['median_ms']),
                num(mature['spans'].get(key, {'p95_ms': 0})['p95_ms'])] for key in span_names]))
    add(table(['Core-Phasen, reife normale Tage', 'Median ms', 'p95 ms'],
              [[key, num(value['median_ms']), num(value['p95_ms'])]
               for key, value in sorted(mature['phases'].items(), key=lambda item: item[1]['median_ms'], reverse=True)]))
    for label in ('normal', 'report', 'month_end', 'year_end', 'mature_normal', 'flush'):
        profile = summary['profiles'].get(label)
        if not profile:
            continue
        add(f"#### cProfile {label}, {profile['samples']} Läufe, getrennte Diagnosezeiten")
        for category, title in [('top20_cumulative', 'Kumulativ'), ('top20_self', 'Eigenzeit')]:
            add(table([title + ': Funktion', 'Aufrufe/Lauf', 'Eigenzeit ms', 'Kumulativ ms'],
                      [[f"{Path(row['file']).name}:{row['line']} {row['function']}", num(row['calls_per_sample']),
                        num(row['self_ms_per_sample']), num(row['cumulative_ms_per_sample'])]
                       for row in profile[category]]))

    add('### Speicherdiagnose und Prozessorbelegung')
    allocation_rows = []
    for path in sorted((OUT / 'reaudit').glob('allocations-*.json')):
        value = read(path)
        allocation_rows.append([value['label'], num(value['net_bytes'] / 1e6),
                                value['net_blocks'], num(value['peak_bytes'] / 1e6),
                                num(value['instrumented_ms'])])
    add(table(['Separater tracemalloc-Lauf', 'Netto MB', 'Netto Blöcke', 'Peak MB',
               'Instrumentierte Zeit ms'], allocation_rows))
    add('tracemalloc verfolgt Python-Allokationen ab Messbeginn und erfasst weder den gesamten '
        'vorhandenen Heap noch alle nativen Qt-/DuckDB-Allokationen. Seine stark erhöhten Laufzeiten '
        'sind keine normalen Tageslatenzen. Detailquellen der Allokationen stehen in den zugehörigen JSON-Dateien.')
    add(table(['Reife normale Tage', 'Worker CPU / Wandzeit, Median Kerne',
               'Worker GC Median ms', 'Parent GC Median ms'],
              [[label, num(m(f'qt-mature-{key}-valid', 'cpu_core_equivalents', 'normal_no_flush')['median_cores']),
                num(median(f'qt-mature-{key}-valid', 'worker_gc_ms', 'normal_no_flush')),
                num(median(f'qt-mature-{key}-valid', 'parent_gc_ms', 'normal_no_flush'))]
               for key, label in chart_names.items()]))
    memory_rows = []
    for name in ('headless-year-clean', 'qt-year-clean-valid', 'qt-mature-none-valid',
                 'qt-mature-heavy-valid', 'qt-manual-step-valid'):
        rows = raw[name]['rows']
        workers = [row.get('worker', row) for row in rows]
        memory_rows.append([name, num(workers[0]['rss_start'] / 1e6),
                            num(workers[-1]['rss_end'] / 1e6),
                            num(rows[0]['parent_rss_start'] / 1e6) if 'parent_rss_start' in rows[0] else '–',
                            num(rows[-1]['parent_rss_end'] / 1e6) if 'parent_rss_end' in rows[-1] else '–'])
    add(table(['Working Set / RSS, MB', 'Worker Start', 'Worker Ende', 'Parent Start', 'Parent Ende'], memory_rows))

    add('### Bewertung, Grenzen und nächste Engpässe')
    normal_rows = [row for row in raw['qt-mature-none-valid']['rows']
                   if aggregate.kind(row) == 'normal' and not row['spans'].get('store.flush', 0)]
    core_fraction = sum(row['spans'].get('simulation.core', 0) for row in normal_rows) / sum(row['total_ms'] for row in normal_rows)
    add(f"Der Python-Simulationskern beansprucht in den reifen normalen Qt-Tagen ohne Chart "
        f"**{num(core_fraction * 100)} % der gemessenen Gesamtzeit** (Summenverhältnis über alle diese Tage). "
        f"Selbst ein hypothetisch kostenloser kompletter Kern könnte diesen Pfad damit höchstens um "
        f"**{num(1 / (1 - core_fraction))}×** beschleunigen. Das ist eine obere Schranke ohne "
        'Integrationskosten, keine Prognose für Rust. Für schnelle Headless-Langläufe ist der Core '
        'weiter relevant; in der Oberfläche verdienen Delta-Erzeugung, Darstellung und periodische '
        'Persistenz weiterhin eigene Aufmerksamkeit. Ein Full Rewrite ist aus diesen Daten nicht '
        'begründbar. Ein späterer isolierter nativer PoC wäre allenfalls für gemessene numerische '
        'Production-/Handelsflüsse sinnvoll, mit identischem RNG und exakten Zustandsvergleichen. '
        'Er hat nach diesem Audit keine Priorität vor den verbleibenden Datenübergabekosten.')
    add('Der neue Worker behält eine getrennte öffentliche Vergleichsrepräsentation. Das kostet Speicher '
        'und Zeit für Feldvergleiche; der Gewinn liegt darin, unveränderte Historien nicht fortlaufend '
        'zu serialisieren und im Hauptthread neu aufzubauen. Rückdatierte Korrekturen dürfen die betroffene '
        'Serie erneut übertragen. Start, Load und ausdrücklich angeforderte Vollsnapshots bleiben '
        'gewichtige Operationen. Die kurze Steuerung der Python-Speicherbereinigung ist auf den '
        'Encoder und Decoder begrenzt und stellt den vorherigen Aktivierungszustand wieder her; automatische volle '
        'Sammlungen sind weiterhin möglich und in den Heartbeat-/GC-Messwerten enthalten.')
    add('Commit, Datenbank-I/O und Compaction bleiben messbare Flush-Kosten. Die verbleibenden kleinen '
        'gebundenen DuckDB-Abfragen wurden nicht pauschal umgebaut. Es wurden keine Transaktionen, '
        'Historien, Chart-Zeiträume oder Persistenzgarantien entfernt. Savegame-Format, Wirtschaftscode '
        'und RNG-Reihenfolge bleiben erhalten. Die 20-Tage- und fünf Jahresgrenzen-Wiederholungen '
        'beschreiben diese Zustände auf diesem Rechner; sie sind keine Garantie für beliebige '
        'Langzeitwelten, Portfolios oder parallele Rechnerlast. Einzelne Maximalwerte und Flush-Zeiten '
        'schwanken stärker als normale Mediane.')
    add('Die frühere Werte-Zählung bleibt die fachliche Größenordnung: **22.798.724 tatsächlich '
        'veränderte numerische Felder pro Spieljahr**, durchschnittlich **1.899.893,67 pro Spielmonat** '
        'im untersuchten Genesis-Jahr. Dies zählt je Feld höchstens eine Änderung pro Tag und '
        'umfasst keine unveränderten Neuberechnungen, Zwischenrechnungen oder Datenkopien. '
        'Die Optimierungen reduzieren den technischen Zusatzaufwand; der ökonomische Jahresverlauf '
        'wurde unverändert nachgewiesen.')
    workload = read(ROOT / '.cache/value-count-audit/result.json')
    labels = {'companies': 'Unternehmen einschließlich Aktienkurs und Input/Output',
              'countries': 'Länder einschließlich Produktion und Handel',
              'commodities': 'Rohstoffe', 'products': 'Verarbeitete Produkte', 'crypto': 'Krypto',
              'funds': 'Fonds', 'indices': 'Indizes', 'derivatives': 'Derivate', 'bonds': 'Bonds',
              'fx': 'FX-Paare', 'currency_strength': 'Währungsstärken', 'global': 'Globale Makrodaten',
              'psychology': 'Marktpsychologie'}
    add(table(['Fachliche Werteänderungen, Referenzjahr', 'Pro Spieljahr', 'Durchschnitt pro Spielmonat'],
              [[labels[key], f'{value:,}'.replace(',', '.'), num(value / 12)]
               for key, value in workload['year_changed'].items()]))

    add('### Nachweise und Reproduzierbarkeit')
    add('Rohmessungen: `.cache/performance-remediation/reaudit/summary.json`, `merged-results.json`, '
        'einzelne Qt-/Headless-JSONs, Worker-JSONL, cProfile-Dateien und Speicherdiagnosen. '
        'Phasenvergleiche: `history-comparison.json`, `duckdb-comparison.json`, `step-before/`, '
        '`step-after/`. Fachlicher Vergleich: `determinism-reference.json`, `determinism-final.json`, '
        '`determinism-comparison.json`. Tests: `final-tests.xml`; Ablauf und Rückgabecodes: '
        '`final-stages.json`. Der Abschlussnachweis `closeout-validation.json` bestätigt außerdem '
        'die unveränderten Produktionsdateien gegenüber dem Release-Manifest. Die Quellreferenz '
        'und die Ausgangsmessungen sind separat gesichert. Die Befehle und Einstellungen stehen '
        'in `tools/performance_remediation_final.py`, `performance_remediation_closeout.py`, '
        '`performance_remediation_finish.py` und `performance_remediation_benchmark.py` im '
        '`tools/`-Verzeichnis. Alle Benchmarks werden sequenziell ausgeführt.')
    text = REPORT.read_text(encoding='utf-8').split('\n## Finaler Re-Audit')[0]
    completed = datetime.now(timezone.utc).astimezone().strftime('%d.%m.%Y %H:%M %Z')
    text = text.replace('Arbeitsstand: Umsetzung und Messungen laufen. Dieser Bericht wird mit den abgeschlossenen Nachweisen ergänzt.',
                        f'Abgeschlossen: drei Optimierungsphasen, Regression und vollständiger Re-Audit. Messreihen ab 5. Oktober 2026; Abschluss: {completed}.')
    text = text.replace('Die abschließenden Benchmarktabellen, deterministischen Vergleiche, Save/Load-Prüfungen und die vollständige Testsuite werden nach Abschluss aller drei Phasen hier ergänzt.',
                        'Die abschließenden Nachweise und Messwerte folgen unten; der ursprüngliche Auditbericht bleibt als Referenz erhalten.')
    marker_start, marker_end = '<!-- final-overview -->', '<!-- /final-overview -->'
    if marker_start in text:
        start, tail = text.split(marker_start, 1)
        text = start.rstrip() + '\n\n' + tail.split(marker_end, 1)[1].lstrip()
    overview = (f'{marker_start}\n'
                f'**Ergebnis:** Der Tageswechsel in der reifen Welt ohne Chart sinkt im Median '
                f'von {num(median("qt-mature-none-valid", source=old) / 1000)} auf '
                f'{num(median("qt-mature-none-valid") / 1000)} Sekunden. Der echte manuelle Step '
                f'sinkt für dieselben ersten drei Tage von {num(row_median(before_step["rows"], "total_ms") / 1000)} '
                f'auf {num(row_median(after_step["rows"][:3], "total_ms") / 1000)} Sekunden; '
                f'die Antwort von {num(row_median(before_step["rows"], "response_bytes") / 1e6)} '
                f'auf {num(row_median(after_step["rows"][:3], "response_bytes") / 1e6)} MB. '
                f'{suite.attrib["tests"]} Tests bestehen; der 365-Tage-Vergleich zeigt keine fachliche Abweichung.\n\n'
                f'**Trade-off:** Normale Tage ohne Flush im ersten Qt-Jahr liegen bei '
                f'{num(median("qt-year-clean-valid", kind="normal_no_flush", source=old) / 1000)} → '
                f'{num(median("qt-year-clean-valid", kind="normal_no_flush") / 1000)} Sekunden. '
                'Der vollständigere aktuelle UI-Zustand kostet zusätzliche Arbeit. Save/Load bleibt '
                f'ein schwergewichtiger Vollzustands-Pfad.\n{marker_end}')
    text = text.replace('\n## Referenz und Messverfahren', '\n' + overview + '\n\n## Referenz und Messverfahren', 1)
    REPORT.write_text(text.rstrip() + '\n\n' + '\n\n'.join(parts) + '\n', encoding='utf-8')
    (OUT / 'final-comparison.json').write_text(json.dumps(comparisons, indent=2), encoding='utf-8')
    print(json.dumps(comparisons, indent=2))


if __name__ == '__main__':
    main()
