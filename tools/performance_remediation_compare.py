"""Fail on changed economic/RNG signatures; render compact phase comparisons."""
import json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'.cache/day-transition-audit'
OUT=ROOT/'.cache/performance-remediation'

def read(path):return json.loads(path.read_text(encoding='utf-8'))

def history():
    result={}
    for chart in ['none','detail','candle','preview','heavy']:
        name=f'qt-mature-{chart}-valid'
        old=read(BASE/f'{name}.json');new=read(OUT/'history-after'/f'{name}.json')
        assert old['signature']==new['signature'],name
        assert [r['date'] for r in old['rows']]==[r['date'] for r in new['rows']],name
        result[chart]={'identical_signature':True,'n':len(new['rows'])}
        for title,key in [('total','total_ms'),('history',None),('t3_t2',None),('t4_t2',None)]:
            def value(row):
                if title=='history':return row['parent_spans'].get('ui.markets.append_live_history',0)
                if title=='t3_t2':return (row['t3']-row['t2'])*1000
                if title=='t4_t2':return (row['t4']-row['t2'])*1000
                return row[key]
            before=statistics.median(value(r) for r in old['rows']);after=statistics.median(value(r) for r in new['rows'])
            result[chart][title]={'before_ms':before,'after_ms':after,'speedup':before/after if after else None}
    (OUT/'history-comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

def determinism():
    before=read(OUT/'determinism-reference.json');after=read(OUT/'determinism-final.json')
    mismatches=[]
    for index,(old,new) in enumerate(zip(before['days'],after['days'],strict=True),1):
        for key in old.keys()|new.keys():
            if old.get(key)!=new.get(key):mismatches.append({'day':index,'field':key})
    for section in ('checkpoints','database'):
        for key in before[section].keys()|after[section].keys():
            if before[section].get(key)!=after[section].get(key):mismatches.append({'section':section,'key':key})
    if before['final_checkpoint']!=after['final_checkpoint']:mismatches.append({'section':'final_checkpoint'})
    result={'days':len(before['days']),'fields_per_day':len(before['days'][0]),'database_tables':len(before['database']),'mismatches':mismatches}
    (OUT/'determinism-comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2));assert not mismatches

if __name__=='__main__':globals()[sys.argv[1]]()
