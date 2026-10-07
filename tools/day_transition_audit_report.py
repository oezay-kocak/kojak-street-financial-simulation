"""Build the source-grounded audit report from retained measurement records."""
from __future__ import annotations
import json, statistics, collections, re
from pathlib import Path
import day_transition_audit_summary as aggregate

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.cache/day-transition-audit'
REPORT=ROOT/'docs/day-transition-performance-audit-2026-10-05.md'

def number(value):
    return f'{value:,.2f}'.replace(',','X').replace('.',',').replace('X','.')

def table(headers,rows):
    def cell(value):return re.sub(r'\s+',' ',str(value)).strip().replace('|',r'\|')
    return '\n'.join(['| '+' | '.join(map(cell,headers))+' |','| '+' | '.join(['---']*len(headers))+' |',*['| '+' | '.join(map(cell,row))+' |' for row in rows]])

def link(path,line=None,label=None):
    path=Path(path)
    return f'[{label or path.name}](<{path.as_posix()}{":"+str(line) if line else ""}>)'

def main():
    aggregate.main()
    summary=json.loads((OUT/'summary.json').read_text())
    raw=json.loads((OUT/'merged-results.json').read_text())
    env=json.loads((OUT/'environment-headless-year-clean.json').read_text())
    hardware=json.loads((OUT/'hardware.json').read_text())
    runs=summary['runs']
    parts=[]
    def add(text): parts.append(text.strip())
    def metrics(run,kind='normal_no_flush'): return runs[run]['types'][kind]
    def med(run,key,kind='normal_no_flush'): return metrics(run,kind)[key]['median_ms']
    def rows(run,kind='normal_no_flush'):
        return [r for r in raw[run]['rows'] if kind=='all' or aggregate.kind(r)==kind or kind=='normal_no_flush' and aggregate.kind(r)=='normal' and not r['spans'].get('store.flush',0) or kind=='flush' and r['spans'].get('store.flush',0)]
    def stat_table(selections):
        output=[]
        for title,run,kind in selections:
            s=metrics(run,kind)['total_ms']
            output.append([title,s['n'],*[number(s[k]) for k in ('min_ms','median_ms','mean_ms','p95_ms','max_ms')]])
        return table(['Messreihe / Tagtyp','n','Minimum ms','Median ms','Mean ms','p95 ms','Maximum ms'],output)
    full='qt-year-clean-valid'; mature='qt-mature-none-valid'; detail='qt-mature-detail-valid'
    full_rows=rows(full)
    selected=rows(mature)
    total=sum(r['total_ms'] for r in selected)
    def component(label,key,category,native,phase=False,run=mature,kind='normal_no_flush'):
        samples=rows(run,kind)
        values=[next((p['duration_ms'] for p in r.get('phases',[]) if p['phase']==key),0) if phase else r['spans'].get(key,0) for r in samples]
        s=aggregate.stats(values)
        return [label,number(s['median_ms']),number(s['p95_ms']),number(100*sum(values)/sum(r['total_ms'] for r in samples))+' %',category,native]

    add('# Kojak Street: Performance-Audit des Tageswechsels\n\nStand: 5. Oktober 2026. Messung auf dem lokalen Windows-Rechner. Untersucht wurde ausschließlich der Übergang zum nächsten Spieltag. Die absichtliche Wartezeit von 2.000 ms pro Spieltag ist ausgeschlossen. Es wurden keine Produktionsfunktionen optimiert, refaktoriert oder migriert.')
    add(f'Der bekannte Genesis-Workload umfasst **22.798.724 tatsächlich veränderte numerische Felder pro Spieljahr**, durchschnittlich etwa **1,9 Millionen pro Spielmonat** ({link(ROOT/".cache/value-count-audit/result.json",label="separate Werte-Zählung")}). Jeder Wert wurde dabei höchstens einmal pro Tag gezählt. Zwischenrechnungen, unveränderte Neuberechnungen, History-Merges, Kopien und Funktionsaufrufe sind zusätzliches, in dieser Zahl nicht enthaltenes Arbeitsvolumen. Datenbank-Feldzellen oder Profiler-Aufrufe sind deshalb andere Größen und werden im Audit getrennt ausgewiesen.')
    add(f'''Der normale Tageswechsel der vollständigen Anwendung liegt über das erste Spieljahr im Median bei **{number(med(full,'total_ms','normal'))} ms**, p95 **{number(metrics(full,'normal')['total_ms']['p95_ms'])} ms**. Ein normaler Tick ohne Oberfläche und ohne Datenbank-Flush benötigt **{number(med('headless-year-clean','total_ms'))} ms**. In der identischen, ein Jahr alten Vergleichswelt benötigt die Oberfläche ohne aktive Chart-Neuzeichnung **{number(med(mature,'total_ms'))} ms**, mit sichtbarem Detailchart **{number(med(detail,'total_ms'))} ms**.

Die Hauptbefunde sind die tägliche Verarbeitung der Historien aller Marktinstrumente im UI-Hauptthread und die periodischen DuckDB-Schreibläufe. Ein nativer Simulationskern würde diese Ursachen nur zu einem begrenzten Teil adressieren. Empfehlung: bestehenden Prozess-Worker behalten und zuerst die gemessenen History-/UI- und Persistenzpfade gezielt in Python beziehungsweise SQL verbessern. Ein vollständiger Rewrite ist aus diesen Messungen nicht begründbar.''')
    add(f'''**Zusätzlicher schwerer Befund im manuellen Step-/erzwungenen Snapshot-Pfad:** In der ein Jahr alten Welt wurden drei einzelne Schritte mit vollständigem Markets-Snapshot gemessen. Median **{number(med('qt-force-snapshot-valid','total_ms','all'))} ms**; die drei Antworten enthalten rund 181–186 MB. Hier dominieren rekursives State-Encoding, JSON und State-Decoding sowie anschließendes History-Merge. Die normalen Timer-Ticks verwenden bereits den kleineren Status-/Current-Rows-Pfad; beide Bedienpfade werden im Bericht getrennt ausgewiesen.''')

    add('## 1. Messumfang, Umgebung und Gültigkeit')
    add(table(['Merkmal','Messaufbau'],[
      ['Welt','Separate Genesis-Welt, Seed 1729, 1.280 Unternehmen, 20 Länder, 365 Kalendertage; Start 01.01.1990'],
      ['Portfolio','Genesis-Startvermögen, keine vom Audit hinzugefügten Trades oder offenen Spielerpositionen'],
      ['Marktuniversum','1.280 Aktien, 34 Rohstoffe, 90 verarbeitete Produkte, 32 Kryptowerte, 271 Fonds, 340 Indizes, 566 Derivate; 420 gerichtete FX-Paare'],
      ['Bonds','Gesamtuniversum wächst; tägliche Auffrischung ist im Code auf bis zu 120 Instrumente begrenzt'],
      ['Betriebssystem',env['platform']],['Python',env['python']],
      ['Bibliotheken',f"NumPy {env['numpy']}; DuckDB {env['duckdb']}; PySide {env['pyside']}; pyqtgraph {env['pyqtgraph']}"],
      ['CPU',f"{hardware['cpu_model']}; {env['logical_cpus']} logische CPUs"],
      ['RAM',f"{number(hardware['total_physical_bytes']/2**30)} GiB physisch"],
      ['Git-Stand',hardware['commit']],
      ['Oberfläche','Echte Windows-Qt-Plattform, maximiertes Fenster; alle neun Ansichten einmal vor der Messung aufgebaut, Markets aktiv'],
      ['Chartvergleich','20 identische Tage ab Checkpoint 01.01.1991; keine aktive Neuzeichnung / Detail-Line ALL / Detail-Candle ALL / Preview-Line ALL'],
      ['Jahresgrenze','31.12.1990 bis 03.01.1991, fünf Wiederholungen desselben Ausgangszustands'],
      ['Statistik','p95 linear interpoliert; Median und Mittelwert sind getrennt; ms sind reale Wandzeit'],
      ['Profiler','Separate cProfile- und tracemalloc-Läufe; deren Zeiten werden nicht als unverfälschte Tick-Latenz verwendet'],
      ['Isolation','Jeder Lauf besitzt eine eigene Datenbank und eigene Audit-Saves; keine gleichzeitig laufenden Benchmarks'],
    ]))
    add('Alle GUI-Messreihen mit dem Suffix `-valid` prüfen zusätzlich, dass Trigger, Abschluss-Slot und UI-Aktualisierung dem Qt-Hauptthread zugeordnet sind. Ein früherer explorativer Messaufbau mit überschriebenem Slot hatte diese Zuordnung verändert und wurde vollständig aus den berichteten GUI-Ergebnissen ausgeschlossen. Der korrigierte Observer ist ein eigenes QObject mit explizit zugestelltem Queued-Slot; er ruft die unveränderte Produktionsfunktion auf. Dieser Messadapter verursacht einen zusätzlichen beobachteten Qt-Aufruf. Initialisierung, Datenbank-Klonen, Checkpoint-Laden, Aufbau der Ansichten und Screenshots liegen außerhalb T0→T4.')
    path_control=json.loads((OUT/'import-path-control.json').read_text())
    add('Eine zweite Messkorrektur betrifft ausschließlich den Adapter: zusätzliche Audit-Suchpfade verlängerten die wiederholten erfolglosen optionalen pandas-Imports. Nach Laden der Messmodule wird nun der Suchpfad des Produktions-Workers verwendet. Beide 365-Tage-Baselines und die dreifache Import-Diagnose wurden damit neu erhoben; der Bericht verwendet hierfür die Reihen mit `clean` im Namen. Frühere Jahresmessungen bleiben als Kontrollartefakte erhalten. Die Chart-/Reload-Vergleiche stammen aus der zuvor korrigierten Qt-Reihe und enthalten keine Flushs mit dem tausendfachen Parameter-/Importpfad; gelegentliche kleine Current-Reads bleiben separat erfasst. Profilerzeiten bleiben separate Diagnosewerte.')
    assert json.loads((OUT/'production-path-check.json').read_text())['equal']
    add(table(['Kontrollierter identischer Januar-Flush, n=1 je Pfad','Importversuche','pandas-Importzeit ms','gesamter Headless-Tick ms'],[[r['label'],r['pandas_calls'],number(r['pandas_ms']),number(r['total_ms'])] for r in path_control]))
    add('Diese kleine Gegenprobe belegt einen Messaufbau-Einfluss; sie ist kein Optimierungsbenchmark des Spiels. Zeiten alter und neuer Gesamtjahre werden wegen Laufzeit-/Rechnerlastschwankungen nicht voneinander subtrahiert, um eine vermeintlich erreichte Produktionsverbesserung zu behaupten.')
    add(stat_table([('20-Tage-Kontrolle ohne Funktions-Observer','control-original','all'),('20-Tage-Kontrolle mit Funktions-Observern','control-instrumented','all')]))
    add('Die Kontrollreihen zeigen die Größenordnung des Core-Messaufwands; getrennte Laufzeiten sind keine exakte isolierte Overhead-Messung jedes GUI-/IPC-Hooks. Die GUI-Observer und der 10-ms-Heartbeat kommen zusätzlich hinzu. Der Worker zählt Antwortbytes über eine zusätzliche UTF-8-Kodierung des vorhandenen JSON-Texts. Alle instrumentierten Baselines enthalten diesen Messaufwand; insbesondere die Speicherwerte sind deshalb keine behaupteten bytegenauen Produktions-Heapwerte.')
    add('Die Checkpoint-Vergleiche klonen den passenden analytischen Store einschließlich History-ID. Historische Datensätze nach dem jeweiligen Ausgangsdatum werden vor der Messung entfernt. Die ökonomischen Zustände und Zufallszustände stammen aus dem originalen Checkpoint; die Speicherpuffer werden über den bestehenden Restore-Pfad neu aufgebaut. Damit sind die Vergleichsvarianten untereinander gleich, jedoch keine bitgleiche Fortsetzung aller ursprünglichen flüchtigen Cache-/Flush-Zustände. Das erste Spieljahr wird zusätzlich durchgehend gemessen.')

    add('## 2. Exakter Kontrollfluss und T0/T1/T2/T3/T4')
    add(f'''Der laufende Timer ruft {link(ROOT/'src/kojakstreet/ui_qt/app.py',329)} auf. `_request_simulation_steps(1, force_refresh=False)` sendet `simulation_requested` an einen persistenten QThread. Dessen `SimulationWorker.advance` ruft die Prozess-Proxy-API auf. Die eigentliche Welt und DuckDB befinden sich im separaten, persistenten `live_worker`-Prozess.

Der Worker rechnet `DailySimulation.step_day`, materialisiert die täglichen Store-Zeilen, führt gegebenenfalls den Flush aus und erzeugt eine Statusantwort plus geänderte aktuelle Tabellen. Die Antwort läuft als JSON-Zeile über stdout/stdin. Ein Reader-Thread im Elternprozess dekodiert JSON und legt das Ergebnis in eine Queue; der wartende Proxy-QThread übernimmt und vereinigt die aktuellen Tabellen. Anschließend liefert ein Queued-Slot den Abschluss an das Fenster. Der normale UI-Pfad plant `_apply_live_market_updates` für die nächste Event-Loop-Runde und aktualisiert die aktive Ansicht sowie den Ticker.''')
    add(table(['Punkt','Genaue Messgrenze'],[
      ['T0','Unmittelbar vor _request_simulation_steps; der vorherige absichtliche Timer-Abstand ist ausgeschlossen'],
      ['T1','DailySimulation.step_day ist beendet, einschließlich Portfolio, Policy und Datumsfortschritt; vor data_store.record_day'],
      ['T2','JSON dekodiert, Status und current_rows im Elternprozess durch LiveSimulationProcess._apply_result übernommen'],
      ['T3','Aktive UI-/Model-Aktualisierung beendet; beim erzwungenen Snapshot nach _refresh_active_view'],
      ['T4','Erster 10-ms-Heartbeat nach T3 und einem darauffolgenden Paint; kein laufender Simulations-, Live-Update-, History-Prefetch- oder erforderlicher Live-Chart-Timer mehr'],
    ]))
    add('`T1−T0` umfasst die kleine Dispatch-/Worker-Anlaufzeit zusätzlich zur reinen Simulation. `simulation.core` misst nur `step_day`. `T2−T1` enthält Zeilenaufbereitung, möglichen Datenbank-Flush und Datenübergabe. `T4−T2` enthält Model-/State-Arbeit, sichtbare Chartarbeit, Paint und verbleibende Event-Loop-Wartezeit. Headless endet nach `advance_day`, also ohne Transfer/UI; dort entspricht die Summe im Wesentlichen Core plus Store-Aufbereitung. Persistenz bedeutet hier, dass der für diesen Tick vorgesehene Persistenzpfad fertig ist: an gewöhnlichen Tagen bleiben Fakten absichtlich im Puffer und sind noch nicht dauerhaft committed.')
    add('T4 ist ein operationaler Responsivitätsnachweis mit etwa einer Heartbeat-Periode Auflösung. Er misst Qt-Paint und wieder bearbeitete Events, nicht den tatsächlichen Monitor-/GPU-Present-Zeitpunkt und nicht die Reaktionszeit jeder denkbaren Benutzeraktion. Ein vorhandener, aber nicht aktiv aktualisierter Previewchart bleibt in der Variante „none“ sichtbar und statisch.')
    add('```mermaid\nflowchart LR\nT0["T0: GUI-Trigger"] --> Q["Proxy-QThread"] --> P["Simulationsprozess"] --> T1["T1: Core fertig"] --> D["Store / optionaler Flush"] --> J["JSON / Pipe / Decode / Merge"] --> T2["T2: State verfügbar"] --> U["GUI-Slot / aktive Models"] --> T3["T3: UI-Daten fertig"] --> C["sichtbarer Chart / Paint / Heartbeat"] --> T4["T4: responsiv"]\n```')

    add('## 3. Vollständige Latenzstatistik je Tagtyp')
    add(stat_table([(f'Qt erstes Jahr: {label}',full,kind) for label,kind in [('alle Tage','all'),('normal, inklusive möglicher Flushs','normal'),('normal ohne Flush','normal_no_flush'),('Reporting am 15.','report'),('Monatsende, ohne 31.12.','month_end'),('31.12., Einzelbeobachtung','year_end'),('periodischer Flush','flush')]]))
    add(stat_table([(f'Headless erstes Jahr: {label}','headless-year-clean',kind) for label,kind in [('normal inkl. Flush','normal'),('normal ohne Flush','normal_no_flush'),('Reporting','report'),('Monatsende','month_end'),('31.12., Einzelbeobachtung','year_end'),('Flush','flush')]]))
    add('Normale Tage enthalten in der ersten Tabelle bewusst auch diejenigen normalen Kalendertage, an denen ein Pufferflush fällig ist. Die zusätzliche Zeile „normal ohne Flush“ trennt diesen unabhängigen Auslöser. Das Monatsende umfasst elf Tage; der 31.12. wird getrennt behandelt. Die Einzelbeobachtung des 31.12. begründet keine allgemeine Jahreswechsel-Aussage; dafür folgt die Wiederholungsmessung.')
    add(stat_table([(f'Identische reife Welt: {label}',run,'all') for label,run in [('Headless','headless-mature'),('Qt ohne aktive Chart-Neuzeichnung',mature),('Qt Detail-Line ALL',detail),('Qt Detail-Candle ALL','qt-mature-candle-valid'),('Qt Preview-Line ALL','qt-mature-preview-valid'),('Qt Detail-Line ALL + EMA 20/50/200','qt-mature-heavy-valid')]]))
    add(stat_table([(f'Jahresgrenze: {label}','qt-year-repeat-valid',kind) for label,kind in [('31.12.','year_end'),('01.01.','year_start'),('03.01., jährlicher Bond-Pfad','annual_issue')]]))
    add('Die fünf Jahresgrenzen-Wiederholungen laden jeweils denselben Checkpoint; damit wird die Kalendergrenze von wachsender Welt-/History-Größe getrennt. n=5 ist eine kleine Stichprobe: der p95 beschreibt diese Messungen und ist kein belastbarer Extremwert einer langen Spielsitzung. Jährliche Bond-Emissionen können im aktuellen Code erst nach dem 02.01. ausgelöst werden; der 31.12. allein würde diesen Pfad übersehen.')

    add('## 4. End-to-End-Zerlegung')
    boundary=[]
    for title,run,kind in [('erstes Jahr, normal ohne Flush',full,'normal_no_flush'),('reife Welt ohne Chart',mature,'normal_no_flush'),('reife Welt Detailchart',detail,'normal_no_flush'),('erstes Jahr, Flush',full,'flush')]:
        m=metrics(run,kind)
        for key,label in [('simulation_ms','T1−T0 Simulation + Dispatch'),('persistence_transfer_ms','T2−T1 Daten/Persistenz/Transfer'),('ui_ms','T4−T2 UI gesamt'),('model_ms','davon T3−T2 UI-/Model-Aufbereitung'),('paint_wait_ms','davon T4−T3 Chart/Paint/Event-Wartezeit'),('post_sim_ready_ms','T4−T1 Core fertig → responsiv')]:
            s=m[key]; boundary.append([title,label,number(s['median_ms']),number(s['p95_ms'])])
    add(table(['Variante','Grenze','Median ms','p95 ms'],boundary))
    add('Nur die drei Zeitgrenzen T1−T0, T2−T1 und T4−T2 sind disjunkt und summieren sich pro Tick exakt zu T4−T0. Mediane verschiedener Größen müssen sich nicht zum Median des Gesamtticks addieren. Die folgenden Funktions-/Subsystemzeiten sind zum Teil ineinander verschachtelt; beispielsweise enthält Production bereits Trade und Companies, und UI gesamt enthält History und Models. Sie dürfen nicht einfach aufsummiert werden.')
    components=[
      component('Simulationskern gesamt','simulation.core','A/C','Obergrenze; auch nicht numerische Logik enthalten'),
      component('Globale Makroökonomie / Regime','global_macro','A','klein',True),
      component('Production / Supply Chain gesamt','daily_production','A/C','isolierter numerischer PoC',True),
      component('Internationaler Handel / Länderflüsse','production.update_country_trade_flows','A/C','geeigneter PoC'),
      component('Unternehmenskapazitäten','production.company_capacities','A','begrenzter kleiner Anteil'),
      component('Unternehmensauslastung / IO-Historien','production.update_company_utilization','A/I','teilweise'),
      component('Aktienkurse / Fundamentals / Erwartungen','market.stock_prices','A/C','geeigneter Batch-PoC'),
      component('Fonds','market.update_funds','A/C','möglich, geringe Gesamtwirkung'),
      component('Indizes','market.update_indices_from_runtime_cache','A','klein'),
      component('Anleihemarkt','bond_market','A','klein',True),
      component('Derivate','derivatives','A','klein',True),
      component('FX-Paare','market.fx_pairs','A','sehr klein; Stärken separat im Rohlog'),
      component('Rohstoffpreise','market.commodity_prices','A','klein'),
      component('Kryptopreise','market.crypto_prices','A','klein'),
      component('Marktpsychologie explizite Phase','market.update_market_psychology','A','sehr klein; Erwartungen außerdem im Aktienpfad'),
      component('Portfolio-Anleihen','bond_portfolio','A','Genesis-Portfolio kaum Arbeit',True),
      component('Store-Zeilen/Puffer gesamt','store.record_day','A/I','kein Core-PoC'),
      component('DuckDB-API an gewöhnlichen Tagen','duckdb.native_api','D','bereits nativ; im Pufferpfad praktisch null'),
      component('Worker-Antwortaufbereitung','worker.result_prepare','I/A','kein numerischer Core-PoC'),
      component('Worker JSON-Encode','worker.json_encode','I','anderer Übergabepfad, nicht Core'),
      component('Worker Pipe-Write','worker.pipe_write','H/I','nicht Core'),
      component('Elternprozess JSON-Decode','parent.json_decode','I','nicht Core'),
      component('Proxy State-/Row-Merge','parent.apply_result','I/A','nicht Core'),
      component('UI: Historien aller Instrumente','ui.markets.append_live_history','C/A/I','zuerst Algorithmus ändern'),
      component('UI: Quote-Model-Aufbereitung','ui.model.apply_quote_rows','F/A','kleinerer Anteil'),
      component('UI: sichtbare Row-Signale','ui.markets.emit_visible_market_rows','F','kein primärer Core-Kandidat'),
      component('UI: aktive Ansicht gesamt','ui.live_update','F/C/I','keine Simulationskern-Migration'),
      component('Detail: Chart-Datenaufbereitung','ui.markets.data_with_history','G/I/A','klein; Detailvariante',run=detail),
      component('Detail: Zeichnungsaufbau','ui.StockDetailView.draw_chart','G/F','kein Simulationskern-PoC',run=detail),
      component('Detail: pyqtgraph Paint','chart.paint','G/F','bereits Qt-nativ; Detailvariante',run=detail),
      component('Flush: Store gesamt','store.flush','D/H/I','kein Simulationskern-PoC',run=full,kind='flush'),
      component('Flush: DuckDB-API inkl. Binding','duckdb.native_api','D/H','bereits nativ; Batch-/SQL-Pfad untersuchen',run=full,kind='flush'),
    ]
    add(table(['Subsystem','Median ms','p95 ms','% Transition¹','Kategorie','Native-Core-Potenzial'],components))
    add('¹ Anteil = Summe der jeweiligen Funktionszeit / Summe der T0→T4-Zeiten innerhalb genau dieser Stichprobe. Die Werte sind nicht aus einem Quotienten separat ermittelter Mediane berechnet. Vergleichsbasis ist die reife Welt ohne Chart, außer ausdrücklich als Detail-/Flush-Variante bezeichnet.')
    report_components=[]
    for key,label in [('monthly_macro','Länder/Makro/Erwartungen'),('monthly_companies','Unternehmens-Fundamentals'),('monthly_company_lifecycle','Unternehmens-Lifecycle'),('monthly_commodities','monatliche Rohstoffdaten'),('monthly_production','Production einschließlich verarbeiteter Produkte/Handel'),('monthly_crypto','monatliche Kryptodaten'),('monthly_crypto_lifecycle','Crypto-Lifecycle')]:
        report_components.append(component(label,key,'A/C','erst nach Detailprofil bewerten',True,run=full,kind='report'))
    add('Zusätzliche Monatsbericht-Phasen:')
    add(table(['Reporting-Subsystem','Median ms','p95 ms','% Reporting-Transition','Kategorie','Native-Potenzial'],report_components))
    add('Verarbeitete Produkte werden innerhalb der Produktions-/Supply-Chain-Logik berechnet und besitzen keinen separaten täglichen Aktienpreis-Timer. Erwartungen sind über Makro, Bewertung und Kursformeln verteilt. Diese Anteile werden deshalb den gemessenen übergeordneten Phasen zugeordnet und nicht als zusätzliche künstliche Summanden ausgegeben. Portfolio, Kredit-/Zins-, Settlement- und Roll-Phasen sind in den vollständigen Phasenlogs enthalten; das positionsarme Genesis-Portfolio begrenzt die Aussage für sehr große Spielerportfolios.')

    add('## 5. Worker, GIL und tatsächlich genutzte CPU')
    cpu=[]
    for run in ('headless-year-clean','headless-mature',full,mature,detail):
        rr=rows(run)
        ratios=[];parent_ratios=[];helper=[]
        for r in rr:
            w=r.get('worker',r)
            ratios.append(w['cpu_ms']/((w['t_end']-w['t_start'])*1000))
            if 'worker' in r: parent_ratios.append((r['parent_cpu_ms']+w['cpu_ms'])/r['total_ms'])
            if 'main_worker_thread_cpu_ms' in w: helper.append(max(0,w['cpu_ms']-w['main_worker_thread_cpu_ms']))
        cpu.append([run,number(statistics.median(ratios)),number(statistics.median(parent_ratios)) if parent_ratios else '—',number(statistics.median(helper)) if helper else 'nicht erfasst'])
    add(table(['Messreihe, normal ohne Flush','Worker: CPU/Wandzeit','Eltern + Worker CPU / T0→T4','Worker-Hilfsthreads CPU ms'],cpu))
    add('CPU/Wandzeit ist eine gemessene Anzahl effektiver Kernäquivalente über das betreffende Intervall, keine Zuordnung zu konkreten physischen Kernen. Werte nahe 1 bedeuten überwiegend serielle CPU-Arbeit; ein Wert größer als 1 kann native Hilfsthreads anzeigen. Während des Simulationskerns dominieren Python-Schleifen und Objektzugriffe. Die separate Prozessarchitektur trennt den Worker-GIL vom UI-GIL bereits. Ein Wechsel von QThread zu einem weiteren Prozess würde deshalb das grundlegende Problem nicht lösen: der QThread ist hier der Kommunikationsproxy, die Simulation läuft schon außerhalb des GUI-Prozesses.')
    add('Der JSON-Reader, der Proxy-QThread und UI-Python teilen den GIL im Elternprozess. Ein gemeinsamer Request-Lock serialisiert Simulation, Save/Load und Hintergrund-History-Abfragen. Die normalen Messreihen warten vor dem Trigger auf ausstehende initiale History-Anfragen; konkurrierende Benutzeraktionen werden nicht synthetisch erzeugt. Gemessene Dispatch-, Pipe-, Decode- und Merge-Zeiten quantifizieren den üblichen Übergabepfad, aber nicht jede denkbare Lock-Kollision. Pro-Core-Sampling beziehungsweise ein nativer Stack-Sampler stand in dieser Sitzung nicht zur Verfügung. Die Zustellung an den Receiver-Thread über Queued-Slots ist in der [Qt-for-Python-Dokumentation](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/signals_and_slots.html) beschrieben und im Messaufbau zusätzlich tatsächlich geprüft.')
    add('Die GIL-Einordnung stützt sich außerdem auf die [Python-3.12-Threading-Dokumentation](https://docs.python.org/3.12/library/threading.html). NumPy kann bei vielen nativen Operationen den GIL freigeben; daraus folgt ohne eine tatsächlich benutzte numerische Operation noch keine Parallelität in diesem Tick ([NumPy Thread Safety](https://numpy.org/doc/2.1/reference/thread_safety.html)).')

    add('## 6. DuckDB: Puffer, API, Batches, SQL und I/O')
    flushes=rows(full,'flush')
    sqls=[q for r in flushes for q in r['worker']['sql']]
    categories=collections.defaultdict(list)
    counts=collections.Counter()
    for r in flushes:
        command_counts=collections.Counter(q['command'] for q in r['worker']['sql'])
        for command in {q['command'] for q in sqls}:
            categories[command].append(sum(q['ms'] for q in r['worker']['sql'] if q['command']==command))
            counts[command]+=command_counts[command]
    add(table(['API-Kommandotyp pro Flush','Aufrufe gesamt / Flushs','Median ms','p95 ms'],[[key,f'{counts[key]} / {len(flushes)}',number(aggregate.stats(values)['median_ms']),number(aggregate.stats(values)['p95_ms'])] for key,values in sorted(categories.items())]))
    batches=[]
    for name in sorted({b['table'] for r in flushes for b in r['worker']['batches']}):
        rv=[sum(b['rows'] for b in r['worker']['batches'] if b['table']==name) for r in flushes]
        cv=[sum(b['cells'] for b in r['worker']['batches'] if b['table']==name) for r in flushes]
        batches.append([name,int(statistics.median(rv)),int(statistics.median(cv))])
    add(table(['Tabelle','Median Batch-Zeilen / Flush','Median Feldzellen / Flush'],batches))
    byte_values=[sum(q.get('copy_bytes') or 0 for q in r['worker']['sql']) for r in flushes]
    api_values=[r['duckdb_ms'] for r in flushes]
    materialize=[r['spans'].get('duckdb.materialize',0) for r in flushes]
    csv_residual=[r['spans'].get('store.insert_with_csv',0)-sum(q['ms'] for q in r['worker']['sql'] if q['command']=='COPY' or q['method']=='executemany') for r in flushes]
    normal_reads=[q for r in rows(full) for q in r['worker']['sql']]
    add(f'''Normale Tage puffern Facts und aktualisieren Python-Current-Rows. Im Headless-Normalpfad ohne Flush werden keine DuckDB-Statements ausgeführt. Der vollständige Worker-/Antwortpfad führt in den {len(rows(full))} normalen Tagen ohne Flush insgesamt **{len(normal_reads)} kleine SELECTs** aus `news_current`/`event_current` aus; diese gelegentlichen Current-Reads erklären die kleinen API-Ausreißer im sonst gepufferten Pfad. Im Runtime ist ein Flush nach 30 unterschiedlichen Datumswerten eingestellt. Die erste Jahresreihe enthält {len(flushes)} gemessene Flushs. SQL-API-Median pro Flush: **{number(statistics.median(api_values))} ms**. Materialisierung durch `fetchone/fetchall`: **{number(statistics.median(materialize))} ms**. Gemessenes temporäres CSV-Volumen pro Flush: Median **{number(statistics.median(byte_values)/1e6)} MB**, p95 **{number(aggregate.quantile(byte_values,.95)/1e6)} MB** (dezimal).''')
    add(f'Als Näherung für den Python-/Datei-Anteil innerhalb `_insert_rows` ergibt die Differenz zur dort aufgerufenen COPY-/INSERT-API im Median **{number(statistics.median(csv_residual))} ms**. Dieser Rest umfasst CSV-Erzeugung, temporäre Dateien, Cleanup und Wrapper; er ist keine präzise Messung des internen DuckDB-Konverters. Die DuckDB-API-Zeit wiederum umfasst Binding, Engine und Warten auf I/O. Ohne einen nativen Engine-/I/O-Trace lassen sich diese Anteile innerhalb eines API-Aufrufs nicht vollständig trennen.')
    grouped=collections.defaultdict(list)
    for r in flushes:
        local=collections.defaultdict(float)
        for q in r['worker']['sql']:
            normalized=re.sub(r"FROM '[^']+'", "FROM '<temporary.csv>'",q['sql'])
            local[normalized]+=q['ms']
        for key in {re.sub(r"FROM '[^']+'", "FROM '<temporary.csv>'",q['sql']) for q in sqls}:
            grouped[key].append(local[key])
    expensive=sorted(grouped.items(),key=lambda kv:statistics.median(kv[1]),reverse=True)[:12]
    add(table(['Teuerste normalisierte Statements / Flush','Median ms','p95 ms'],[['`'+key.replace('|',' / ')+'`',number(statistics.median(v)),number(aggregate.quantile(v,.95))] for key,v in expensive]))
    add('Der Flush verwendet eine Transaktion mit BEGIN/COMMIT; aktuelle Tabellen werden über DELETE plus Batch-Einfügen ersetzt, History-Aggregate werden innerhalb desselben Persistenzpfads aktualisiert. Die großen Facts gehen überwiegend als CSV/COPY hinein. News-, Event- und **Phase-Metric-Tabellen** gehen über `executemany`; gerade diese kleinen Telemetrie-Insert-Batches sind in den Messungen überraschend teuer. Der langsame Tick lässt sich deshalb nicht allein mit der Zahl wirtschaftlicher Werte erklären. Repetitive Statements und exakte Batchgrößen sind im Rohlog erhalten; dies ist keine Behauptung, dass DuckDB generell langsam sei.')
    imports=json.loads((OUT/'duck-import-diagnostics-clean.json').read_text())
    import_names=sorted({name for r in imports for name in r['imports']})
    import_table=[]
    for name in import_names:
        vals=[r['imports'].get(name,{}).get('ms',0) for r in imports]
        calls=[r['imports'].get(name,{}).get('calls',0) for r in imports]
        failed=[r['imports'].get(name,{}).get('failed',0) for r in imports]
        import_table.append([name,int(statistics.median(calls)),int(statistics.median(failed)),number(statistics.median(vals)),number(aggregate.quantile(vals,.95))])
    add('Zusätzliche **unprofilierte** Import-Diagnose: drei gleiche reife Ausgangszustände, 29 reguläre Tage Vorbereitung, anschließend der bestehende Januar-Flush. Ein Observer um die vorhandene Python-Importfunktion erfasst Module, Fehlversuche und Zeit; es wird kein Modul installiert und kein SQL geändert. Dieser Flush kann außerdem die erstmals fällige jährliche History-Compaction enthalten und ist deshalb eine gesonderte Stichprobe gegenüber den zwölf Flushs des ersten Jahres.')
    add(table(['Modul','Median Importversuche / Flush','Median fehlgeschlagen','Median Importzeit ms','p95 ms'],import_table))
    contexts=collections.Counter()
    for r in imports:
        for item in r['imports'].values():contexts.update(item['sql'])
    add(table(['SQL-Kontext der Importversuche','Versuche über drei Diagnosen'],contexts.most_common(8)))
    add('Damit ist ein erheblicher Teil der gemessenen DuckDB-API-Latenz konkret **Python-/Import-/Dateisuch-Aufwand innerhalb des Bindings**. Fehlgeschlagene optionale pandas-Imports dürfen nicht als reine native SQL-Rechenzeit ausgegeben werden. Ein späterer isolierter Test sollte den Parameter-/Batch-Pfad und diese wiederholten Importversuche prüfen. Aus dem Audit folgt noch keine gemessene Beschleunigung durch eine Installation, ein Upgrade oder eine alternative Übergabeform; solche Änderungen wurden nicht durchgeführt.')
    add('Einordnung: **A — relevante DuckDB-/Commit-/I/O-Zeit an Flush-Tagen; B — zusätzlicher relevanter Python-/CSV-/Materialisierungsaufwand; C — praktisch keine DuckDB-API-Latenz an gewöhnlichen gepufferten Tagen.** Den größten gemessenen SQL-/Batch-Aufrufen muss eine spätere Optimierung zuerst gelten. Die Python-DuckDB-API und ihre Thread-Anbindung sind in der [offiziellen Python-Dokumentation](https://duckdb.org/docs/stable/clients/python/overview) beschrieben.')

    add('## 7. NumPy und native Arbeit im Simulationskern')
    core_profile=summary['profiles']['warm_normal']
    native_math=[p for p in core_profile['all'] if p['file']=='~' and any(token in p['function'] for token in ('math.','_random.Random','numpy'))]
    numpy_entries=[p for p in core_profile['all'] if 'numpy' in p['file'].lower() or 'numpy' in p['function'].lower()]
    add(f'Der Core-Profiler der reifen Welt enthält {number(sum(p["calls_per_sample"] for p in numpy_entries))} NumPy-Aufrufe pro Tick in den erfassten NumPy-Funktionszeilen. Native mathematische/random-C-Aufrufe besitzen zusammen {number(sum(p["self_ms_per_sample"] for p in native_math))} ms profilerbehaftete Self-Zeit pro Tick. Diese Zahl ist kein nativer CPU-Sample-Trace: sie bezeichnet nur die vom Python-Profiler sichtbaren C-Aufrufgrenzen und enthält weder eine komplette Engine-Aufschlüsselung noch jeden in CPython implementierten Objektzugriff.')
    add('Der aktuelle Daily-Pfad benutzt cached Index-/Momentum-Zustände und Python-Schleifen. Die vorhandene `np.mean`-Hilfsfunktion ist deshalb kein Beleg für einen bereits vektorisierten ganzen Simulationskern. Native Dictionary-/Listen-/Sortieroperationen sind zwar C-Code innerhalb CPython, bleiben aber Objekt-/Algorithmusaufwand der Kategorien A/C und sind kein zusammenhängender NumPy-Kernel. DuckDB liegt zeitlich außerhalb T1; es erhöht den nativen Anteil des Core-Pfads daher nicht.')
    add('Gut abgrenzbar wären numerische Länder-/Güter-Matrizen und Aktienpreisformeln auf vorbereiteten Spaltenarrays. Schwieriger sind die bestehende Dictionary-Topologie, lifecycle-abhängige Zustandsänderungen, heterogene Produkte und die Reihenfolge gekoppelter Updates. Eine Vektorisierung würde denselben Aufwand für Array-Aufbereitung, Rückschreiben und deterministische Zufallswerte gegen die Einsparung im numerischen Kernel messen müssen.')

    add('## 8. UI, sichtbare und unsichtbare Charts, Signale und Responsivität')
    chart_rows=[]
    for run in (full,mature,detail,'qt-mature-candle-valid','qt-mature-preview-valid','qt-mature-heavy-valid'):
        rr=raw[run]['rows']; m=metrics(run,'all')
        signals=runs[run]['signal_totals']
        chart_rows.append([run,len(rr),signals['visible_chart_calls'],signals['hidden_chart_calls'],signals['paints'],number(m['heartbeat_max_ms']['median_ms']),number(m['heartbeat_max_ms']['p95_ms'])])
    add(table(['Variante','Ticks','sichtbare Plot-Aufrufe','unsichtbare Plot-Aufrufe','beobachtete Paint-Events','Median größter Tick-Heartbeat-Abstand ms','p95 ms'],chart_rows))
    signal_rows=[]
    for run in (full,mature,detail,'qt-mature-candle-valid','qt-mature-preview-valid','qt-mature-heavy-valid'):
        n=len(raw[run]['rows'])
        for name,value in runs[run]['model_signals'].items(): signal_rows.append([run,name,value,number(value/n)])
    add(table(['Variante','beobachtetes Model-Signal','Gesamt','pro Tick'],signal_rows))
    add('Die Messung zählt die vier angeschlossenen Signaltypen dataChanged, modelReset, rowsInserted und layoutChanged für Source- und Proxy-Marktmodell; außerdem MetaCall-/Timer-/Paint-Events. Ein Source-Signal und seine Proxy-Weiterleitung sind zwei beobachtete Signale, keine zwei unabhängigen Preisberechnungen. Dies ist keine globale Zählung aller internen Qt-Signale. Die aktive Tabellenansicht enthält 2.523 Source-Zeilen und initial 160 geladene Proxy-Zeilen; die lazy geladenen Zeilen sind kein Beleg für ein fehlendes Marktuniversum.')
    add('Die normalen Quote-Updates setzen die Marktmodelle nicht vollständig zurück. Die expliziten Preis-Signale sind auf die sichtbaren Zeilen begrenzt. Die bereits aufgebauten, inaktiven Ansichten bleiben im gemessenen Markets-Tick weitgehend ohne Refresh-/Plot-Aufrufe. Die Messung der Zeichenmethoden `plot_line`, `plot_lines`, `plot_candles` und `plot_long_short_heatmap` unterscheidet ausdrücklich `isVisible()`; zusätzliche Qt-Paints stehen separat. Damit ist die Aussage über unsichtbare Charts auf die erfassten Chartmethoden und die getesteten Ansichten begrenzt.')
    add(f'''Trotzdem ruft {link(ROOT/'src/kojakstreet/ui_qt/views/markets_view.py',328)} `_append_live_history` für alle eingehenden Marktquotes auf. Für jedes Instrument werden alle lokalen History-Punkte nach Datum identifiziert, in ein neues Dictionary gelegt, sortiert und wieder in eine Liste übernommen ({link(ROOT/'src/kojakstreet/ui_qt/chart_series.py',59)}). Erst anschließend wird auf 520 Punkte begrenzt. Das passiert auch ohne ausgewählten Livechart. Die Komplexität hängt bis zur Begrenzung von **Instrumentzahl × History-Länge** ab; die Sortierung kann zusätzlichen Aufwand verursachen. Unsichtbare Verläufe verursachen somit Datenarbeit, ohne dass alle unsichtbaren Charts gerendert werden.''')
    ui_functions=summary['profiles']['qt-profile-none-valid']['all']
    ordinal_calls=sum(p['calls_per_sample'] for p in ui_functions if p['function']=='history_ordinal')
    date_calls=sum(p['calls_per_sample'] for p in ui_functions if p['function']=='history_date')
    merge_calls=sum(p['calls_per_sample'] for p in ui_functions if p['function']=='merge_history_by_date')
    add(f'Die separat profilierte reife GUI-Variante ohne Livechart zählt pro Tick im Mittel **{number(merge_calls)} History-Merge-Aufrufe**, **{number(ordinal_calls)} Ordinal-Bestimmungen** und **{number(date_calls)} Datumsabfragen**. Das ist tatsächlich gemessene interne Arbeit zusätzlich zu den etwa 61.600 wirtschaftlich veränderten Zahlenfeldern eines normalen Genesis-Tags. Die geladenen Simulationshistorien und die im laufenden UI erzeugten Live-Punkte können außerdem unterschiedliche Datumsrepräsentationen besitzen; der Parser behandelt diese über verschiedene Pfade. Die reife Reload-Reihe ist deshalb getrennt vom durchgehend laufenden ersten Jahr ausgewiesen.')
    add('Der Detailchart aktualisiert die sichtbare Zeichnung im aktuellen Live-Pfad direkt. Die Line-Vorschau bündelt eine Neuzeichnung über einen 48-ms-Timer; diese chartbezogene Wartezeit gehört zur Transition. Ein Preview-Candle hat dagegen einen anderen Live-Refresh-Pfad und wurde nicht mit dem vollständig live aktualisierten Detail-Candle verwechselt. Chartdaten werden außerdem über `_data_with_history` kopiert/vereinigt; ALL kann beim ersten Öffnen eine Hintergrund-History-Abfrage auslösen. Diese initiale Auswahl ist außerhalb der Tickmessung, spätere erforderliche Arbeit wird bis T4 berücksichtigt.')
    add('Die großen Heartbeat-Lücken quantifizieren die Blockade des GUI-Event-Loops durch History-/Model-Arbeit. Worker-Rechen- oder Commit-Wartezeit kann die neue Welt verspätet liefern, während die Oberfläche weiter Events bearbeitet. Beide Effekte müssen getrennt bewertet werden: „Core fertig → UI responsiv“ und „längster Event-Abstand“ stehen deshalb ausdrücklich in den Tabellen.')
    add('Für die Heartbeat-Statistik werden nur vollständig innerhalb T0→T4 liegende Abstände verwendet: der erste Heartbeat-Abstand jeder Zeile wird ausgeschlossen, weil dessen Beginn noch in der vorangegangenen Chart-/Setup-Phase liegen kann. Das beseitigt einen großen Setup-Ausreißer der Preview-Reihe. Die eigentliche T0→T4-Latenz und ihre Grenzen sind davon unverändert. Sehr kurze Abschnitte vor dem ersten Heartbeat sind dadurch in dieser ergänzenden Blockade-Kennzahl nicht vollständig erfasst.')

    add('## 9. Headless-Vergleich und deterministische Kontrolle')
    add(table(['Vergleich','ökonomische Signatur inklusive RNG gleich'],[[k,'ja' if v['economic_signature_equal'] else '**NEIN**'] for k,v in summary['comparisons'].items()]))
    if not all(v['economic_signature_equal'] for v in summary['comparisons'].values()):
        raise AssertionError('Economic signatures differ: report must investigate before delivery')
    add('Die Produktionssignatur prüft Datum, Länderwerte, Aktienpreise/Market Cap/Umsatz/FCF, Fonds, Indizes, Crypto, Bondpreise/-renditen/-rating, Portfolio sowie den Hash von Python- und NumPy-Zufallszuständen. Die vollständige Jahresreihe und die identischen reifen Vergleichsvarianten stimmen damit überein. Zusätzlich stimmen ein uninstrumentierter und ein instrumentierter 20-Tage-Genesis-Lauf überein. Dies prüft wesentliche ökonomische Ergebnisse und Zufallszustände, ist aber kein Vollvergleich sämtlicher temporärer Felder oder aller historischen Datenbank-Zeilen.')
    numeric=raw['control-original']['public_numeric_checkpoint']
    assert numeric==raw['control-instrumented']['public_numeric_checkpoint']
    count_text=f'{numeric["count"]:,}'.replace(',','.')
    add(f'Zusätzlich wurde der offizielle öffentliche numerische Checkpoint-Inhalt vollständig gehasht: **{count_text} Zahlenwerte**, identischer SHA-256-Hash `{numeric["sha256"]}` in Original und instrumentiertem Lauf. Private Cache-Felder, boolesche Werte und Text/Datum gehören nicht zu diesem Zahlenvergleich. Zusammen mit dem RNG-Signaturvergleich bestätigt dies, dass die Messadapter die geprüften ökonomischen Ergebnisse unverändert lassen.')
    h=med('headless-mature','total_ms'); q=med(mature,'total_ms')
    add(f'Für die reife Welt beträgt der zusätzliche End-to-End-Abstand des GUI-/Prozesspfads gegenüber dem direkt ausgeführten Headless-Tick im Medianvergleich **{number(q-h)} ms**. Dieser Abstand ist eine Gesamtdifferenz; die exakte Zuordnung ergibt sich aus den T-Grenzen und Funktionsspans. Unterschiede der Core-Zeit zwischen separat gestarteten Läufen enthalten Cache-, Scheduling- und Messumgebungseinflüsse und dürfen nicht vollständig als Chartkosten ausgelegt werden. Der isolierte sichtbare Chartvergleich hält Seed, Startdatum und ökonomische Schritte gleich.')

    add('## 10. Speicher, GC, temporäre Objekte und Datenbewegung')
    add(stat_table([('Erzwungener Markets-Snapshot, reife Welt, persistenter Worker','qt-force-snapshot-valid','all')]))
    force_components=[]
    for key,label,category in [('simulation.core','Core','A'),('snapshot.copy','Snapshot-Aufbau','I'),('worker.state_encode','game_state_payload: asdict + encode','I/A'),('worker.json_encode','JSON-Encoding','I'),('worker.pipe_write','Pipe-Write','I/H'),('parent.json_decode','JSON-Decoding','I'),('parent.decode_state','Rekursive State-Rekonstruktion','I/A'),('ui.markets.refresh','Aktive View inklusive vollständigem History-Merge','F/C/I')]:
        force_components.append(component(label,key,category,'kein primärer numerischer Core-Kandidat',run='qt-force-snapshot-valid',kind='normal_no_flush'))
    add(table(['Snapshot-/Step-Komponente','Median ms','p95 ms','% Step-Transition','Kategorie','Native-Core-Potenzial'],force_components))
    add('`game_state_payload` verwendet `encode(asdict(state))`. Damit wird die angeforderte Dataclass-Struktur rekursiv kopiert und erneut in eine transportierbare Objektstruktur übersetzt. Die sichtbare Preishistorie ist zwar begrenzt, diese Grenze begrenzt nicht automatisch alle weiteren Asset-/Company-/Cache-Felder. Die normale Statusantwort vermeidet diese vollständige Struktur bereits. Beim Step-Pfad werden zusätzlich komplette Historien in die aktive View vereinigt. Die gemessenen etwa 49 Sekunden sind daher eine Daten-/Darstellungsgrenze mit einem vergleichsweise kleinen Core-Anteil.')
    volume=json.loads((OUT/'snapshot-volume.json').read_text())
    add('Zur Zuordnung großer Datenstrukturen wurde der ein Jahr alte serialisierte **Checkpoint** separat nach Abschnitten vermessen. Dies ist eine Größenprojektion des Ausgangszustands, keine exakte byteweise Zerlegung der späteren 181–186-MB-Workerantwort. Die wichtigsten Abschnitte sind:')
    add(table(['Checkpoint-Abschnitt','JSON-Größe MB'],[[name,number(value/1e6)] for name,value in sorted(volume['sections_bytes'].items(),key=lambda pair:pair[1],reverse=True)[:10]]))
    add(table(['Aktienfeld, summiert über 1.280 Unternehmen','JSON-Größe MB'],[[name,number(value/1e6)] for name,value in sorted(volume['stock_fields_bytes'].items(),key=lambda pair:pair[1],reverse=True)[:6]]))
    add('Bei den Aktien dominieren Preis- und Open-Interest-Historien. Kleine interne Caches erklären die große Antwort daher nicht allein. Ein späterer Eingriff muss die tatsächlich benötigten Historien und den passenden Snapshot-Vertrag untersuchen; einfach den numerischen Core zu ersetzen beseitigt diese rekursiven Kopien nicht.')
    memories=[]
    for run in ('headless-year-clean','headless-mature',full,mature,detail,'qt-force-snapshot-valid'):
        rr=raw[run]['rows'];workers=[r.get('worker',r) for r in rr]
        memories.append([run,number(workers[0]['rss_start']/1e6),number(workers[-1]['rss_end']/1e6),number(rr[0]['parent_rss_start']/1e6) if 'parent_rss_start' in rr[0] else '—',number(rr[-1]['parent_rss_end']/1e6) if 'parent_rss_end' in rr[-1] else '—'])
    add(table(['Variante','Worker RSS Start MB','Worker RSS Ende MB','Eltern-RSS Start MB','Eltern-RSS Ende MB'],memories))
    add('RSS ist die Windows-Working-Set-Messung pro Prozess, kein exakter Live-Objektbestand. Schwankungen enthalten Python-/Allocator-Retention, DuckDB, Qt und Betriebssystem-Effekte. Die Summe zweier Prozess-RSS-Werte kann gemeinsam abgebildete Seiten doppelt zählen. Ein langfristiger Leak ist aus der RSS-Zunahme allein nicht bewiesen.')
    gc_rows=[]
    for run in (full,mature,detail):
        m=metrics(run)
        gc_rows.append([run,number(m['worker_gc_ms']['median_ms']),number(m['worker_gc_ms']['p95_ms']),number(m['parent_gc_ms']['median_ms']),number(m['parent_gc_ms']['p95_ms']),number(m['response_bytes']['median_bytes']/1e6),number(m['response_bytes']['p95_bytes']/1e6)])
    add(table(['Variante, normal ohne Flush','Worker GC Median ms','Worker GC p95 ms','Eltern GC Median ms','Eltern GC p95 ms','Antwort Median MB','Antwort p95 MB'],gc_rows))
    alloc=[]
    for label in ('normal','report'):
        a=json.loads((OUT/f'allocations-{label}.json').read_text())
        alloc.append([label,number(a['peak_bytes']/1e6),number(a['net_bytes']/1e6),a['net_blocks'],number(a['instrumented_ms'])])
    for name in ('qt-allocation-none-valid','qt-allocation-detail-valid'):
        a=json.loads((OUT/f'allocations-{name}-0.json').read_text())
        alloc.append([name+' (1 Trace-Frame)',number(a['peak_bytes']/1e6),number(a['net_bytes']/1e6),a['net_blocks'],number(a['instrumented_ms'])])
    add(table(['Separate tracemalloc-Probe','Peak MB','Netto-Zuwachs MB','Netto-Blöcke','stark instrumentierte Wandzeit ms'],alloc))
    add('Der Runtime deaktiviert GC während Simulation und record_day. Wieder aktivierte GC kann danach während Antwortaufbereitung/Serialization laufen; deshalb befinden sich die gemessenen GC-Pausen nicht zwingend innerhalb des numerischen Kerns. Lokale UI-History-Merges erzeugen für sehr viele Punkte kurzlebige Dictionaries, Schlüssel, Tupel und sortierte Listen. JSON erzeugt zusätzlich Text und erneut Python-Objekte auf der Empfängerseite. Die normale Statusantwort kopiert nicht jeden Tick den kompletten Welt-Snapshot, enthält aber weiterhin die geänderten aktuellen Tabellen und damit deutlich mehr als ein einzelnes Datum.')
    add('tracemalloc misst Python-Allokationen; native DuckDB-/Qt-/NumPy-Puffer sind damit nicht vollständig erfasst. Netto-Zuwachs ist keine Anzahl sämtlicher erzeugter und wieder freigegebener Objekte. Die Top-20-Allokationsstellen und exakten Byte-/Blockdifferenzen stehen in den `allocations-*.json`-Dateien. Core-Proben verwenden acht Trace-Frames, GUI-Proben einen Frame zur Begrenzung des Messaufwands. Für den UI-Objekt-Churn dienen zusätzlich die separat profilierten Funktions-/Call-Counts und RSS-Verläufe als Nachweis; es wurde keine behauptete exakte Gesamtzahl aller temporären UI-Objekte erfunden.')

    add('## 11. Top-20-Python-Hotspots: cumulative, self und Aufrufzahl')
    add('Die folgenden Zeiten sind Mittelwerte je **separatem cProfile-Tick**. Der Profiler verlangsamt vor allem viele kleine Python-Aufrufe; absolute Profilerzeiten ersetzen daher die oben gemessenen Normalzeiten nicht. Cumulative-Zeiten enthalten Kindfunktionen und überlappen. Allgemeine Audit-Wrapper bleiben sichtbar, damit die Messung nachvollziehbar ist. `~` bezeichnet eine C-/Builtin-Aufrufgrenze ohne Python-Quelldatei.')
    for label,title in [('warm_normal','Core: reife Welt, aufgewärmte Caches'),('qt-profile-none-valid','GUI: reife Welt ohne Livechart'),('qt-profile-detail-valid','GUI: reife Welt mit Detailchart')]:
        profile=summary['profiles'][label]
        add(f"### {title} — {profile['samples']} getrennt profilierte Ticks")
        for key,sort_title in [('top20_cumulative','nach cumulative time'),('top20_self','nach self time'),('top20_calls','nach call count')]:
            add(f'**Top 20 {sort_title}**')
            output=[]
            for i,p in enumerate(profile[key],1):
                filename=Path(p['file'])
                source=link(filename,p['line'],filename.name) if filename.exists() and filename.is_file() else p['file'].replace('|',' / ')
                function=p['function'].replace('|',' / ').replace('<','&lt;').replace('>','&gt;')
                output.append([i,function,source,number(p['cumulative_ms_per_sample']),number(p['self_ms_per_sample']),number(p['calls_per_sample'])])
            add(table(['Rang','Funktion','Quelle','cum ms/Tick','self ms/Tick','Calls/Tick'],output))
    for label,title in [('report','Reporting-Core'),('flush','Flush einschließlich Persistenz')]:
        profile=summary['profiles'][label]
        add(f"### {title} — Top 20 cumulative, {profile['samples']} Profiler-Ticks")
        add(table(['Rang','Funktion','cum ms/Tick','self ms/Tick','Calls/Tick'],[[i,p['function'].replace('|',' / ').replace('<','&lt;').replace('>','&gt;'),number(p['cumulative_ms_per_sample']),number(p['self_ms_per_sample']),number(p['calls_per_sample'])] for i,p in enumerate(profile['top20_cumulative'],1)]))
    add('Weitere getrennte Profile für normalen frühen Tag, Monatsende und 31.12. liegen vollständig in `summary.json` und den `.pstats`-Dateien vor, einschließlich ihrer jeweiligen Top-20-cumulative/self/calls-Listen. Die umfangreichen History-Dateiparsings, Dictionary-Lookups, Listenkonstruktionen und Sortierungen sind in den UI-Call-Counts sichtbar; Unternehmens-/Länder-/Marktloops in den Core-Profilen. Quellenzeilen der instrumentierten Marktloops bleiben auf die ursprünglichen Dateien bezogen.')
    add('Die ursprünglichen Core-Profile restaurieren vor jedem Sample denselben Checkpoint und zeigen damit auch kalte Referenz-/Underlying-Caches. Gerade Fonds-Unterlying-Suchen sind dort wesentlich größer als im üblichen warmen Tick. Für die oben gezeigten warmen Core-Top-20 wird die identische reife Welt zunächst fünf Tage unprofiliert weitergerechnet; anschließend werden drei normale Tage separat profiliert. Die kalte Reihe `mature_normal` bleibt vollständig in den Rohdaten erhalten. Keine kalte Profilerzeit wird als dauerhafte tägliche Fonds-Latenz ausgegeben.')

    add('## 12. Root Causes A–J und Potenzial ohne Sprachwechsel')
    add(table(['Kategorie','Befund / Konsequenz'],[
      ['A Python/Objekte','Aktienloop, Trade, Company-IO sowie History-Datumsparsing/Dictionaries; gemessene Self-/Call-Hotspots'],
      ['B GIL/Parallelität','Core weitgehend seriell; Worker besitzt bereits eigenen GIL. UI-Python bleibt ein serieller Abschnitt'],
      ['C Algorithmus','Tägliches komplettes History-Merge aller Instrumente; gleicher Arbeitsumfang wäre auch in Rust/C++ vorhanden'],
      ['D DuckDB/SQL','Nur an Flush-/History-Pfaden große API-/Commit-Zeit; besonders Telemetrie-executemany prüfen'],
      ['E NumPy/native','Kein großer vektorisierter NumPy-Daily-Kernel im erfassten Core; DuckDB/Qt sind bereits native Bibliotheken'],
      ['F Qt/UI','Model-/Label-Arbeit, Queued-Zustellung, Layout/Paint; Main-Thread-History blockiert Events'],
      ['G Charts','Sichtbare Chartdaten, Linien/Candles, pyqtgraph-Paint; Messung trennt Plot-Aufbau von Paint'],
      ['H I/O','CSV-Dateien, COPY, COMMIT und Pipe; nicht durch einen neuen numerischen Core beseitigt'],
      ['I Kopien/Serialization','Status/current_rows, JSON, Decode/Merge sowie History-Listen/Dictionaries'],
      ['J Sonstiges','GC, OS-/Qt-Scheduling, Heartbeat-Abtastung und nicht separat isolierter Rest'],
    ]))
    add(f'''Priorität 1: Der gemessene `_append_live_history`-Block beansprucht in der reifen Welt ohne Chart im Median **{number(metrics(mature)['spans']['ui.markets.append_live_history']['median_ms'])} ms**. Der Ansatzpunkt ist inkrementelles Einfügen/Ersetzen eines neuen Datumpunkts und bedarfsgerechte Vorbereitung sichtbarer Verläufe. Die heutige Begrenzung auf 520 Punkte begrenzt langfristig die Größe, verhindert aber das tägliche vollständige Parsing/Merge nicht. Die genannte Zeit ist der adressierbare aktuelle Block, keine bereits erreichte Einsparung.

Priorität 2: Den Flush anhand der teuersten SQL-Aufrufe zerlegen. Kleine Phase-Metric-Batches, Current-Table-Replacement, History-Compaction und COMMIT gezielt mit der bestehenden API untersuchen. Batch-/Transaction-Verhalten, CSV-Konvertierung und erforderliche Persistenzgarantien müssen dabei jeweils separat validiert werden.

Priorität 3: Übergabegröße und doppelte Datenarbeit reduzieren, sofern die UI die entsprechenden Daten wirklich benötigt. Der heutige Status-/Delta-Pfad ist bereits deutlich begrenzter als ein erzwungener Vollsnapshot; dennoch entstehen messbare JSON-/Row-Kosten. Danach erst die Core-Hotspots und gegebenenfalls Array-/Cache-Aufbereitung prüfen.''')
    force=metrics('qt-force-snapshot-valid','all')['total_ms']
    add(f'Zusatzkontrolle des vorhandenen erzwungenen Snapshot-/Step-Pfads: n={force["n"]}, Median **{number(force["median_ms"])} ms**, p95 **{number(force["p95_ms"])} ms**. Diese kleine gesonderte Stichprobe darf nicht mit normalen Timer-Ticks vermischt werden. Sie belegt den Unterschied der angeforderten Übergabe-/UI-Pfade, nicht den isolierten Preis einer einzelnen Kopie.')
    add('Die oben genannte Reihenfolge betrifft die normalen Timer-Ticks. **Für manuelle Einzelschritte hat der vollständige Snapshot-/Übergabepfad höchste Priorität**, weil er den dort gemessenen Gesamtwechsel dominiert. Beide Bedienpfade brauchen eigene Erfolgsmessungen: ein schnellerer Timer-Tick bestätigt noch keine Verbesserung des manuellen Steps.')

    add('## 13. Quantitatives Potenzial eines nativen Simulationskerns')
    scenarios=[]
    for run,kind,title in [('qt-force-snapshot-valid','all','manueller Vollsnapshot'),(full,'normal_no_flush','erstes Jahr normal'),(mature,'normal_no_flush','reife Welt normal'),(detail,'normal_no_flush','reife Welt Detailchart'),(full,'flush','Flush-Tage')]:
        rr=rows(run,kind); core=sum(r['spans']['simulation.core'] for r in rr)/sum(r['total_ms'] for r in rr)
        scenarios.append([title,number(core*100)+' %',number(100*core*.5)+' %',number(100*core*.8)+' %',number(core*100)+' %'])
    add(table(['Variante','gemessener Core-Anteil','Gesamtlatenz-Ersparnis bei 2× Core¹','bei 5× Core¹','absolute Obergrenze bei kostenlosem Core'],scenarios))
    add('¹ 2× und 5× sind ausdrücklich **Rechenszenarien**, keine gemessenen Rust-/C++-Beschleunigungen. Rechnung: ersparter Anteil = Core-Anteil × (1−1/s). Die extreme Obergrenze setzt einen kostenfreien ganzen Core ohne neue Buffer-, Copy- oder Rückschreibkosten voraus und ist praktisch nicht erreichbar. Ein kleiner PoC adressiert nur einen Teil dieses Core-Anteils. Die Messungen erlauben eine Bandbreite von null beziehungsweise bei ungünstiger Interop sogar negativer Netto-Ersparnis bis höchstens zu diesem adressierbaren Anteil; eine garantierte positive Untergrenze gibt es ohne implementierten PoC nicht.')
    add('Ein Simulationskern würde UI-History-Merge, Qt-Paint, bereits native DuckDB-Calls, CSV-/JSON-Übergaben und Commit-I/O zunächst unverändert lassen. Ein schnellerer Core allein begründet daher kein praktisch sofortiges Spielgefühl. Bereits native Funktionen erneut in einer anderen Sprache aufzurufen ist kein eigenständiger Leistungsgewinn. Ein Hybrid kann nach Beseitigung der größeren Ursachen sinnvoll werden, wenn die erneut gemessene Core-Latenz das verbleibende Ziel verhindert.')

    add('## 14. Rust versus C++ für einen isolierten Hybrid')
    add(table(['Aspekt','Rust','C++'],[
      ['Python-Interop','PyO3/maturin; pro Subsystem ein grober Batch-Aufruf','pybind11; ebenfalls grober Batch-Aufruf'],
      ['NumPy/Memory Layout','Contiguous Arrays/Buffers, Ownership-/Lifetime-Regeln ausdrücklich festlegen','Buffer-Protokoll/NumPy Views; kein implizites STL-Dict/List-Copying im Hotpath'],
      ['DuckDB','Bestehenden Python-Store zunächst weiterverwenden; keine neue Datenbankintegration nötig','Dasselbe; native DuckDB-Integration nur bei belegtem Nutzen'],
      ['Determinismus','RNG-Reihenfolge und Float-/Summationsreihenfolge fest definieren','Dasselbe; fast-math und andere Reduktionsreihenfolgen zunächst vermeiden'],
      ['Komplexer Zustand','Typisierung/Ownership helfen, aber gekoppelte Simulationslogik muss sauber abgegrenzt werden','Passende Strukturen leicht ausdrückbar, Lifetime-/Aliasing-Fehler eigenständig absichern'],
      ['Multithreading/GIL','Nur abgelöste numerische Buffers ohne Python-Zugriffe parallel bearbeiten','GIL gezielt freigeben; währenddessen keine Python-Objekte anfassen'],
      ['Memory Safety','Sichere Rust-Pfade können viele Speicherfehler verhindern; FFI bleibt Prüfgrenze','Manuelle Verantwortung für Speicher/Lifetimes; Sanitizer und klare Buffer-Verträge wichtig'],
      ['Windows-Build/Packaging','Rust-Toolchain + passende MSVC/Python-Wheels; maturin-Verteilung testen','MSVC/CMake + pybind11/Python-Wheels; reproduzierbarer Compiler-/ABI-Pfad nötig'],
      ['Tests/Wartbarkeit','Differenztests und Bilanzinvarianten; zusätzliche Sprache/Buildkette','Dieselben Tests/Invarianten; zusätzliche Sprache/Buildkette'],
      ['Schrittweise Migration','Ein Kernel mit Python-Fallback, versionierter API und gemessenem Übergabeaufwand','Dasselbe'],
      ['AI-unterstützte Entwicklung','Hilfreich für Bindings/Tests; numerische Gleichheit und Eigentumsregeln müssen belegt werden','Hilfreich für Bindings/Tests; Lifetimes/Determinismus müssen belegt werden'],
    ]))
    add('Für einen neuen, kleinen numerischen PoC wäre Rust mit PyO3/maturin eine gut begründbare Option, wenn die zusätzliche Toolchain akzeptabel ist. C++/pybind11 ist ebenso tragfähig, besonders bei vorhandener C++-Erfahrung. Die Messung zeigt keinen Sprachvergleich und keine Überlegenheit bei der Netto-Latenz. PyO3 beschreibt das explizite Ablösen für parallele native Arbeit ([Parallelism](https://pyo3.rs/main/parallelism)); pybind11 gibt den GIL nicht automatisch frei ([GIL](https://pybind11.readthedocs.io/en/stable/advanced/misc.html)). Direkte Array-/Buffer-Übergaben sind dokumentiert unter [pybind11 NumPy](https://pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html); Windows-/Wheel-Verteilung unter [maturin Distribution](https://www.maturin.rs/distribution.html).')

    add('## 15. Drei abgrenzbare PoC-Kandidaten, keine Migration durchgeführt')
    add(table(['Priorität / Kandidat','Gemessener heutiger Bereich','Abgrenzung und Validierung'],[
      ['1. Trade-/Länder-Güter-Kernel',f"Median {number(metrics(mature)['spans']['production.update_country_trade_flows']['median_ms'])} ms im reifen GUI-Core",'Spaltenarrays für Angebot, Nachfrage, Gewichte und Länder-/Produktindizes; ein Batch; Ergebnis gegen Export/Import/Netto/Shortage/Pressure und Bilanzinvarianten prüfen'],
      ['2. Aktienpreis-Batch',f"Median {number(metrics(mature)['spans']['market.stock_prices']['median_ms'])} ms für die gesamte bestehende Stock-Schleife",'Nur numerische Preisformel nach vorhandener Fundamentals-/EMA-Aufbereitung; Python-Zufallswerte in unveränderter Reihenfolge liefern; sämtliche 1.280 Ergebnisse und RNG-Folgezustand prüfen'],
      ['3. Company-IO-/Auslastungs-Batch',f"Median {number(metrics(mature)['spans']['production.update_company_utilization']['median_ms'])} ms einschließlich Historienarbeit",'Kapazitäts-/Input-/Output-Tabellen numerisch abgrenzen; History-Schreiben außerhalb halten; Inventare, Mengen und Fortschreibung vergleichen'],
    ]))
    add('Bester erster nativer PoC **nach den größeren UI-/Store-Ursachen**: der Trade-/Länder-Güter-Kernel. Er ist numerisch besser abgrenzbar als ein komplett gekoppelter Company-/Market-State. Der gesamte heutige Funktionsblock ist jeweils eine Obergrenze; ein Kernel ersetzt davon nur einen Teil. Ein Batch-Aufruf muss inklusive Python→Array-Konvertierung, nativer Rechnung, Array→State-Rückschreibung, Allokationen und eventueller Synchronisation gemessen werden.')
    add('Validierung: identischer Checkpoint und Seed, Vergleich zunächst jeder Schritt-Ausgabe und des RNG-Zustands, danach normaler Tag, Bericht, Policy, jährlicher Bond-Pfad und 365-Tage-Folge. Anfangs exakte Gleichheit fordern; mögliche Float-Differenzen, Reihenfolgeänderungen und deren Ausbreitung ausdrücklich untersuchen. Akzeptierte Toleranzen dürfen erst fachlich festgelegt werden und ersetzen keine Bilanz-/Marktinvarianten. Python-Fallback behalten. Der Audit enthält weder einen implementierten nativen PoC noch einen Rewrite.')

    add('## 16. Spielgefühl und ein sinnvolles Ziel')
    add('Als Orientierung, nicht als harte Wahrnehmungsgrenze: wenige zehn Millisekunden mit weiterlaufender Event-Loop können praktisch unmittelbar oder sehr flüssig wirken. Um etwa hundert Millisekunden wird eine Zustandsverzögerung bei direkter Interaktion oft bemerkbar; derselbe Zeitraum als GUI-Blockade stört stärker. Mehrere hundert Millisekunden wirken als deutlicher Wechsel, mehrsekündige Main-Thread-Pausen als Hängen. Anzeige, Animationsdesign, Nutzereingabe, Rechnerlast und Datenmenge verändern diese Einordnung.')
    add('Als allgemeine UX-Orientierung dient hier [Jakob Nielsens Einordnung von Antwortzeiten](https://www.nngroup.com/articles/response-times-3-important-limits/). Die Übertragung auf das Spiel und die unterschiedliche Wirkung von Hintergrundrechnung und GUI-Blockade sind die Bewertung dieses Audits, keine aus der Quelle abgeleitete feste Spielgrenze.')
    add('Die gemessenen mehrsekündigen History-/Flush-Pfade erfüllen das gewünschte unmittelbare Wechselgefühl nicht. Die Hintergrundsimulation allein ist wesentlich kleiner; ihre Zeit ist jedoch noch keine Garantie für unmittelbare Sichtbarkeit. Ein geeignetes späteres Produktziel wäre eine kleine, separat gemessene Main-Thread-Blockade und eine T0→T4-Latenz im niedrigen zweistelligen bis niedrigen dreistelligen Millisekundenbereich für normale Tage, mit ausdrücklich definierter Behandlung von Persistenz und Berichtstagen. Das ist ein vorgeschlagenes Entwicklungsziel, kein bereits erreichter oder physiologisch verbindlicher Grenzwert.')

    add('## 17. Abschluss, Empfehlung, Einschränkungen und reproduzierbare Daten')
    add('**Aktuellen Ansatz behalten und Python-/History-/Übergabe-/SQL-Pfade gezielt optimieren.** Die Prozess-Worker-Architektur ist bereits geeignet, die UI während der Core-Rechnung frei zu halten. Zuerst sind die History-Verarbeitung normaler Ticks, vollständige Snapshots manueller Steps und die periodische Persistenz zu bearbeiten. Eine sofortige Native-Core-Migration oder ein vollständiger Rewrite ist aus dem Audit nicht gerechtfertigt. Ein späterer Hybrid ist eine überprüfbare Option für den isolierten Trade-PoC, wenn erneute Messungen nach den prioritären Änderungen einen verbleibenden Core-Bedarf zeigen.')
    add('Alle Zahlen gelten für diesen Rechner, die Genesis-Welt und die getesteten Ansichten/Charts. Keine Aussage über jede Handelsstrategie, mehrere gleichzeitig offene Detailfenster, extreme Portfolios, weit ältere Welten oder Benutzer-/Save-/History-Anfrage-Kollisionen. Kleine Zusatzstichproben und der operational gemessene Paint-/Heartbeat-Endpunkt sind ausdrücklich gekennzeichnet. Kein nativer CPU-Stack-Trace, keine physische Kernzuordnung und kein GPU-Present-Trace wurden vorgetäuscht. Profiler- und Allocation-Zeiten bleiben von den Baselines getrennt. Die früheren, ungültigen GUI-Läufe sind nur Debug-Artefakte und werden von der Zusammenfassung ausgeschlossen.')
    control=json.loads((OUT/'production-thread-control.json').read_text())
    validation=json.loads((OUT/'validation.json').read_text())
    add(f'Eine unabhängige Kontrolle verwendet die **originale KojakStreetWindow-Klasse ohne den Audit-Abschluss-Slot**. Ihre {len(control["ui_observations"])} beobachteten Quote-Aktualisierungen laufen im Qt-Hauptthread: **{"bestanden" if control["passed"] else "NICHT BESTANDEN"}**. Die Integritätsprüfung aller {validation["qt_samples_checked"]} GUI-Messpunkte überprüft Zeitreihenfolge, T0→T4-Arithmetik, Worker-/UI-Datum, positive Model-Zeilenzahlen, Main-Thread-Zuordnung, sauberen Abschluss und die ökonomischen Signaturvergleiche: **{"bestanden" if validation["passed"] else "NICHT BESTANDEN"}**.')
    add('Reproduzierbare Werkzeuge und Daten:')
    add('\n'.join('- '+link(path,label=label) for path,label in [
      (ROOT/'tools/day_transition_audit.py','Messdriver'),(ROOT/'tools/day_transition_audit_support.py','Mess-Observer und instrumentierte Spans'),
      (ROOT/'tools/day_transition_audit_suite.py','Sequenzielle vollständige Messsuite'),(ROOT/'tools/day_transition_audit_summary.py','Statistik und Profile'),
      (OUT/'summary.json','Zusammenfassung einschließlich weiterer Top-20-Profile'),(OUT/'merged-results.json','T0–T4-Rohdaten mit Worker-/UI-Zerlegung'),
      (OUT/'profiles.json','Separate Core-/Flush-Profiler-Messpunkte'),(OUT/'allocations-normal.json','Allokationen normal'),(OUT/'allocations-report.json','Allokationen Reporting'),
      (OUT/'allocations-qt-allocation-none-valid-0.json','UI-Allokationen ohne Livechart'),(OUT/'allocations-qt-allocation-detail-valid-0.json','UI-Allokationen Detailchart'),
      (OUT/'validation.json','Integritätsprüfung aller gültigen Messreihen'),(OUT/'production-thread-control.json','Unverändertes Produktionsfenster: Thread-Kontrolle'),
      (OUT/'duck-import-diagnostics-clean.json','Dreifache Import-Diagnose mit Produktionssuchpfad'),(OUT/'import-path-control.json','Kontrolle des Audit-Suchpfad-Einflusses'),(OUT/'production-path-check.json','Suchpfadvergleich mit originaler Worker-Umgebung'),(OUT/'snapshot-volume.json','Größenprojektion des gespeicherten Zustands'),
      (OUT/'qt-mature-detail-valid.png','Kontrollbild sichtbarer Detailchart'),(OUT/'qt-mature-none-valid.png','Kontrollbild Marktmodell ohne Live-Auswahl'),
    ]))
    add('Aufruf über die bestehende Projekt-Python-Umgebung: `python tools/day_transition_audit_suite.py`. Die Suite erzeugt neue isolierte Audit-Verzeichnisse; bestehende Worker-Logs mit demselben Namen werden absichtlich nicht überschrieben. Für neue Wiederholungen neue Namen verwenden oder ausschließlich eigene Audit-Artefakte kontrolliert entfernen. Produktion und bestehende Spielstände werden nicht angepasst. Die Statistiken können separat mit `python tools/day_transition_audit_summary.py` und dieser Bericht mit `python tools/day_transition_audit_report.py` erneut erzeugt werden.')
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text('\n\n'.join(parts)+'\n',encoding='utf-8')
    print('REPORT',REPORT)

if __name__=='__main__': main()
