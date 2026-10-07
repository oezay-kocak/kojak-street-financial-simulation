"""Small structured source/data inspection helper for the remediation audit."""
import argparse, re, json
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('pattern');parser.add_argument('root');parser.add_argument('--json',action='store_true');args=parser.parse_args()
root=Path(args.root)
if args.json:
    data=json.loads(root.read_text(encoding='utf-8'))
    print(json.dumps(data,indent=2)[:30000])
else:
    regex=re.compile(args.pattern)
    paths=[root] if root.is_file() else root.rglob('*.py')
    for path in paths:
        for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
            if regex.search(line): print(f'{path}:{i}: {line}')
