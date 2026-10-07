"""Resolve cold-cache and Python-import costs without changing production work."""
import importlib._bootstrap as bootstrap
import json,time
from collections import defaultdict
from pathlib import Path
import day_transition_audit as driver
import day_transition_audit_support as audit

OUT=driver.OUT
audit.install()
runtime=driver.make_runtime(OUT/'profile-warm-normal','end')
try:
    for _ in range(5):runtime.advance_day()
    profiles=[]
    for i in range(3):
        audit.begin(runtime.daten.datum.date(),OUT/f'profile-warm_normal-{i}.pstats')
        runtime.advance_day();row=audit.finish();row['label']='warm_normal';profiles.append(row)
    (OUT/'warm-profiles.json').write_text(json.dumps(profiles),encoding='utf-8')
    print('WARM PROFILES COMPLETE',flush=True)
finally:runtime.close()

original=bootstrap._find_and_load
imports=defaultdict(lambda:{'calls':0,'ms':0.,'failed':0,'sql':defaultdict(int)})
def observe(name,import_):
    if audit.ACTIVE is None:return original(name,import_)
    start=time.perf_counter();failed=False
    try:return original(name,import_)
    except ImportError:
        failed=True
        raise
    finally:
        row=imports[name];row['calls']+=1;row['ms']+=(time.perf_counter()-start)*1000
        row['failed']+=int(failed)
        row['sql'][audit.ACTIVE.get('last_sql','outside API')[:150]]+=1
bootstrap._find_and_load=observe
results=[]
try:
    for repetition in range(3):
        imports.clear()
        runtime=driver.make_runtime(OUT/f'duck-import-diagnostic-{repetition}','end')
        try:
            for _ in range(29):runtime.advance_day()
            audit.begin(runtime.daten.datum.date())
            runtime.advance_day();row=audit.finish()
            row['total_ms']=(row['t_end']-row['t_start'])*1000
            row['imports']={name:dict(value,sql=dict(value['sql'])) for name,value in imports.items()}
            results.append(row)
            print('IMPORT DIAGNOSTIC',repetition+1,
                  sorted(((name,value['calls'],round(value['ms'],2),value['failed']) for name,value in imports.items()),key=lambda x:x[2],reverse=True)[:8],flush=True)
        finally:runtime.close()
finally:bootstrap._find_and_load=original
(OUT/'duck-import-diagnostics-clean.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
