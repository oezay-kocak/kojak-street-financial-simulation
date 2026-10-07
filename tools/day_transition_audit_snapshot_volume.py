"""Attribute encoded checkpoint volume without running or modifying the world."""
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.cache/day-transition-audit'
source=OUT/'checkpoint-end.json'
print('READING RETAINED CHECKPOINT',flush=True)
world=json.loads(source.read_text(encoding='utf-8'))['checkpoint']
def encoded_bytes(value):
    return len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
books={key:encoded_bytes(value) for key,value in world.items()}
fields=Counter()
for asset in world['aktien'].values():
    for key,value in asset.items():
        fields[key]+=encoded_bytes({key:value})-2
result={'source':str(source),'source_bytes':source.stat().st_size,
        'method':'Encoded checkpoint sections; not exact attribution of a later worker response',
        'sections_bytes':books,'stock_fields_bytes':dict(fields)}
(OUT/'snapshot-volume.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('SECTIONS',sorted(books.items(),key=lambda x:x[1],reverse=True)[:12],flush=True)
print('STOCK FIELDS',fields.most_common(15),flush=True)
