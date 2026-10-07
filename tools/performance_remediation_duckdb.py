"""Isolated batch candidates and actual flush/import diagnostics (no pandas install)."""
import argparse, csv, importlib._bootstrap as bootstrap, json, os, sys, tempfile, time
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('candidates','before','after'));args=parser.parse_args()
OUT=ROOT/'.cache/performance-remediation'/f'duckdb-{args.mode}';OUT.mkdir(parents=True,exist_ok=True)
os.environ['KOJAK_AUDIT_OUTPUT']=str(OUT)
if args.mode=='before':os.environ['KOJAK_AUDIT_PROJECT_ROOT']=str(ROOT/'.cache/performance-remediation/reference-source')
import day_transition_audit as driver
import day_transition_audit_support as audit
driver.production_import_paths()
import duckdb

original=bootstrap._find_and_load
imports=defaultdict(lambda: {'calls':0,'failed':0,'ms':0.,'sql':defaultdict(int)})
def observe(name,import_):
    if name!='pandas' or args.mode!='candidates' and audit.ACTIVE is None:
        return original(name,import_)
    started=time.perf_counter();failed=False
    try:return original(name,import_)
    except ImportError:failed=True;raise
    finally:
        row=imports[name];row['calls']+=1;row['failed']+=int(failed);row['ms']+=(time.perf_counter()-started)*1000
        row['sql'][(audit.ACTIVE or {}).get('last_sql','candidate')[:180]]+=1

def safe_copy(connection,table,rows):
    path=None
    try:
        with tempfile.NamedTemporaryFile('w',newline='',encoding='utf-8',suffix='.csv',delete=False) as f:
            path=Path(f.name)
            for row in rows:
                f.write(','.join('\\N' if value is None else '"'+str(value).replace('"','""')+'"' for value in row)+'\n')
        connection.execute(f"COPY {table} FROM '{str(path).replace(chr(39),chr(39)*2)}' (FORMAT CSV, HEADER FALSE, NULL '\\N', ALLOW_QUOTED_NULLS FALSE)")
    finally:
        if path:path.unlink(missing_ok=True)

bootstrap._find_and_load=observe
try:
    results=[]
    if args.mode=='candidates':
        connection=duckdb.connect(str(OUT/'candidates.duckdb'))
        connection.execute('CREATE OR REPLACE TABLE metrics(date DATE, phase VARCHAR, duration_ms DOUBLE)')
        probes=[]
        for value in [None,True,1,1.5,'phase',float('nan'),float('inf')]:
            imports.clear();value_result=connection.execute('SELECT ?', [value]).fetchone()
            probes.append({'type':type(value).__name__,'value':repr(value),'result':repr(value_result),'imports':dict(imports)})
        for count in [15,460]:
            rows=[('1991-01-30',f'phase_{i%15}',float(i)/7) for i in range(count)]
            for method in ['executemany','safe_copy','unnest']:
                for repetition in range(5):
                    connection.execute('DELETE FROM metrics');imports.clear();started=time.perf_counter()
                    connection.execute('BEGIN')
                    if method=='executemany':connection.executemany('INSERT INTO metrics VALUES (?,?,?)',rows)
                    elif method=='safe_copy':safe_copy(connection,'metrics',rows)
                    else:
                        columns=list(zip(*rows))
                        connection.execute('INSERT INTO metrics SELECT unnest(?::DATE[]),unnest(?::VARCHAR[]),unnest(?::DOUBLE[])',[list(c) for c in columns])
                    connection.execute('COMMIT');elapsed=(time.perf_counter()-started)*1000
                    obtained=connection.execute('SELECT * FROM metrics ORDER BY ALL').fetchall()
                    assert [(str(a),b,c) for a,b,c in obtained]==sorted(rows)
                    results.append({'rows':count,'method':method,'repetition':repetition,'ms':elapsed,'imports':dict(imports)})
                print('CANDIDATE',count,method,round(results[-1]['ms'],2),flush=True)
        for method in ['bound_compaction_constants','literal_compaction_constants']:
            for repetition in range(5):
                imports.clear();started=time.perf_counter()
                for _ in range(80):
                    if method=='bound_compaction_constants':
                        connection.execute('SELECT ?::VARCHAR, ?::VARCHAR, ?::VARCHAR, ?::VARCHAR WHERE ?::DATE > ?::DATE',
                                           ['asset_daily','price','level','monthly','1990-12-31','0001-01-01']).fetchall()
                    else:
                        connection.execute("SELECT 'asset_daily','price','level','monthly' WHERE DATE '1990-12-31' > DATE '0001-01-01'").fetchall()
                results.append({'rows':80,'method':method,'repetition':repetition,'ms':(time.perf_counter()-started)*1000,'imports':dict(imports)})
            print('CANDIDATE',method,round(results[-1]['ms'],2),flush=True)
        connection.close();(OUT/'type-probes.json').write_text(json.dumps(probes,indent=2),encoding='utf-8')
    else:
        audit.install()
        from kojakstreet.core.data_store import EconomicDataStore
        audit.wrap(EconomicDataStore,'_replace_current_rows','store.current_table_replace')
        audit.wrap(EconomicDataStore,'_aggregate_spec','store.aggregate_spec')
        audit.wrap(EconomicDataStore,'_write_parameter_csv','csv.parameter_rows')
        original_writer=csv.writer
        class CsvTimer:
            def __init__(self,*values,**kwargs):self.raw=original_writer(*values,**kwargs)
            def __getattr__(self,key):return getattr(self.raw,key)
            def writerows(self,rows):
                with audit.span('csv.writerows'):return self.raw.writerows(rows)
        csv.writer=CsvTimer
        for repetition in range(3):
            runtime=driver.make_runtime(OUT/f'flush-{repetition}','end')
            try:
                for _ in range(29):runtime.advance_day()
                imports.clear();audit.begin(runtime.daten.datum.date())
                runtime.advance_day();row=audit.finish();row['total_ms']=(row['t_end']-row['t_start'])*1000
                row['imports']=json.loads(json.dumps(imports));results.append(row)
                print('FLUSH',args.mode,repetition,round(row['total_ms'],2),dict(imports).get('pandas',{}).get('calls',0),flush=True)
            finally:runtime.close()
    (OUT/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
finally:bootstrap._find_and_load=original
