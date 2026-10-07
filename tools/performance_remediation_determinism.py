"""Cross-version economic, RNG, checkpoint-history and persisted-row evidence."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.cache/performance-remediation'

def canonical(value):
    if isinstance(value,dict):
        result={k:canonical(v) for k,v in value.items()}
        if value.get('__type__')=='set':result['items'].sort(key=lambda x:json.dumps(x,sort_keys=True))
        return result
    if isinstance(value,list):return [canonical(v) for v in value]
    return value

def digest(value):
    from kojakstreet.core.checkpoints import encode
    encoded=canonical(encode(value))
    return hashlib.sha256(json.dumps(encoded,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def current(value):
    if isinstance(value,dict):
        return {k:current(v) for k,v in value.items() if not str(k).startswith('_') and 'histor' not in str(k).lower()}
    if isinstance(value,(tuple,list)):return [current(v) for v in value]
    return value

def current_signature(runtime):
    from kojakstreet.core.checkpoints import FIELDS
    from kojakstreet.live_process import economic_signature
    return {**{name:digest(current(getattr(runtime.daten,name))) for name in sorted(FIELDS)
              if hasattr(runtime.daten,name) and 'histor' not in name.lower()},
            'rng':economic_signature(runtime.daten)['rng']}

def database_signature(runtime):
    connection=runtime.data_store._connection
    result={}
    for (table,) in connection.execute('SHOW TABLES').fetchall():
        columns=[row[1] for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()]
        if table.startswith('phase_metric_'):columns.remove('duration_ms')
        projection=', '.join('"'+name+'"' for name in columns)
        where=" WHERE key <> 'history_id'" if table=='history_metadata' else ''
        cursor=connection.execute(f'SELECT {projection} FROM "{table}"{where} ORDER BY ALL')
        hasher=hashlib.sha256();count=0
        while batch:=cursor.fetchmany(4096):
            for row in batch:hasher.update(repr(row).encode());hasher.update(b'\n');count+=1
        result[table]={'rows':count,'sha256':hasher.hexdigest()}
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('label');parser.add_argument('--reference',action='store_true');parser.add_argument('--days',type=int,default=365)
    args=parser.parse_args()
    source=OUT/'reference-source' if args.reference else ROOT
    sys.path[:0]=[str(source/'src'),str(source)]
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.core.checkpoints import capture
    runtime=IntegratedRuntime(source,data_dir=OUT/args.label,seed=1729)
    result={'source':str(source),'seed':1729,'days':[],'checkpoints':{}}
    try:
        for index in range(args.days):
            runtime.advance_day()
            result['days'].append(current_signature(runtime))
            if index+1 in {15,31,181,365}:result['checkpoints'][str(index+1)]=digest(capture(runtime.daten))
            if (index+1)%30==0:print(args.label,index+1,flush=True)
        result['final_checkpoint']=digest(capture(runtime.daten))
        runtime.data_store.flush()
        result['database']=database_signature(runtime)
        (OUT/f'{args.label}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    finally:runtime.close()
    print(args.label,'COMPLETE',flush=True)

if __name__=='__main__':main()
