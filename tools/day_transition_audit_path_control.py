"""Compare missing-pandas import latency on audit and production search paths."""
import importlib._bootstrap as bootstrap
import json,sys,time,os,subprocess
from pathlib import Path
import day_transition_audit as driver
import day_transition_audit_support as audit
production=list(sys.path)
environment=os.environ.copy()
source=str(driver.ROOT/'src')
environment['PYTHONPATH']=source+(os.pathsep+environment['PYTHONPATH'] if environment.get('PYTHONPATH') else '')
actual=json.loads(subprocess.check_output([sys.executable,'-c','import sys,json; print(json.dumps(sys.path))'],cwd=driver.ROOT,env=environment,text=True))
actual[0]=str(driver.ROOT)
check={'production_worker_paths':actual,'clean_headless_paths':production,'equal':actual==production}
(driver.OUT/'production-path-check.json').write_text(json.dumps(check,indent=2),encoding='utf-8')
assert check['equal']
legacy=[str(driver.ROOT/'src'),str(driver.ROOT),str(driver.ROOT/'tools'),*driver.ORIGINAL_SYS_PATH]
audit.install()
results=[]
original=bootstrap._find_and_load
active=None
def observe(name,import_):
    if active is None or audit.ACTIVE is None:return original(name,import_)
    start=time.perf_counter()
    try:return original(name,import_)
    finally:
        if name=='pandas':
            active['pandas_calls']+=1
            active['pandas_ms']+=(time.perf_counter()-start)*1000
bootstrap._find_and_load=observe
try:
    for label,paths in [('legacy',legacy),('production',production)]:
        sys.path[:]=paths
        runtime=driver.make_runtime(driver.OUT/f'path-control-{label}','end')
        try:
            for _ in range(29):runtime.advance_day()
            active={'label':label,'sys_path':paths,'pandas_calls':0,'pandas_ms':0}
            audit.begin(runtime.daten.datum.date());runtime.advance_day();row=audit.finish()
            row['total_ms']=(row['t_end']-row['t_start'])*1000
            row.update(active);active=None;results.append(row)
            print(label,row['total_ms'],row['pandas_ms'],flush=True)
        finally:runtime.close()
finally:
    bootstrap._find_and_load=original;sys.path[:]=production
(driver.OUT/'import-path-control.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
