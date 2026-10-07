"""Summarize independent DuckDB candidates and matched real flush samples."""
import json,statistics
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'.cache/performance-remediation'
output={}
for phase in ('candidates','before','after'):
    path=ROOT/f'duckdb-{phase}'/'results.json'
    if not path.exists():continue
    data=json.loads(path.read_text(encoding='utf-8'))
    if phase=='candidates':
        groups=defaultdict(list)
        for row in data:groups[(row['method'],row['rows'])].append(row)
        output[phase]={f'{method}/{count}':{'median_ms':statistics.median(r['ms'] for r in rows),
                            'pandas_calls':statistics.median(r['imports'].get('pandas',{}).get('calls',0) for r in rows)}
                        for (method,count),rows in groups.items()}
    else:
        groups=defaultdict(list)
        for row in data:
            sql=row['sql'];imp=row['imports'].get('pandas',{})
            metrics={'transition_ms':row['total_ms'],'pandas_calls':imp.get('calls',0),'pandas_ms':imp.get('ms',0),
                     'sql_api_calls':len(sql),'submitted_statements':sum(r['rows'] if r['method']=='executemany' else 1 for r in sql),
                     'csv_bytes':sum(r.get('copy_bytes') or 0 for r in sql),
                     **row['spans']}
            for command in ('BEGIN','INSERT','COPY','DELETE','COMMIT'):
                metrics[command+'_ms']=sum(r['ms'] for r in sql if r['command']==command)
            metrics['executemany_ms']=sum(r['ms'] for r in sql if r['method']=='executemany')
            for table in ('phase_metric_daily','phase_metric_current'):
                metrics[table+'_ms']=sum(r['ms'] for r in sql if table in r['sql'] and r['command'] in ('INSERT','COPY'))
            for key,value in metrics.items():groups[key].append(value)
        output[phase]={key:statistics.median(values) for key,values in groups.items()}
(ROOT/'duckdb-comparison.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
print(json.dumps(output,indent=2))
