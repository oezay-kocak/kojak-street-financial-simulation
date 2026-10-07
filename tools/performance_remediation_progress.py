"""Compact completed benchmark evidence, without altering raw records."""
import json,statistics,sys,pstats
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'.cache/performance-remediation'
for dirname in (sys.argv[1:] or ['history-after']):
    folder=root/dirname
    for path in sorted(folder.glob('qt-*.json')):
        if path.name.endswith('-valid.json'):
            data=json.loads(path.read_text(encoding='utf-8'));rows=data['rows']
            print(path.stem,'n=',len(rows),'total median=',round(statistics.median(r['total_ms'] for r in rows),2),
                  'history median=',round(statistics.median(r['parent_spans'].get('ui.markets.append_live_history',0) for r in rows),2),
                  'errors=',data['errors'])
    for path in sorted(folder.glob('ui-profile-*-0.pstats')):
        counts={key:0 for key in ['merge_history_by_date','history_date','history_ordinal','fromisoformat','sorted']}
        for (_,_,function),(_,calls,*_) in pstats.Stats(str(path)).stats.items():
            for key in counts:
                if function==key or key in ('fromisoformat','sorted') and key in function:counts[key]+=calls
        print(path.stem,counts)
    for path in sorted(folder.glob('*-worker.jsonl')):
        rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.endswith('}')]
        if rows:
            print(path.stem,'worker days=',len(rows),'last response MB=',round(rows[-1].get('response_bytes',0)/1e6,2),
                  'last worker ms=',round((rows[-1]['t_end']-rows[-1]['t_start'])*1000,2))
            if '--spans' in sys.argv:
                print({key:round(value,2) for key,value in rows[-1]['spans'].items() if value>20})
                starts={};times={}
                for event in rows[-1]['gc']:
                    gen=event['generation']
                    if event['phase']=='start':starts[gen]=event['time']
                    elif gen in starts:times[gen]=times.get(gen,0)+(event['time']-starts.pop(gen))*1000
                print('GC ms',times)
