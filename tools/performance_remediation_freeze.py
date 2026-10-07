"""Freeze a measured intermediate source phase, without touching Git or saves."""
import hashlib,json,shutil,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.cache/performance-remediation'
label=sys.argv[1];destination=OUT/label
if destination.exists():raise RuntimeError(f'Already frozen: {destination}')
with zipfile.ZipFile(OUT/'reference-source.zip') as archive:archive.extractall(destination)
shutil.copytree(ROOT/'src',destination/'src',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for path in ROOT.glob('*.py'):shutil.copy2(path,destination/path.name)
manifest={str(path.relative_to(destination)):hashlib.sha256(path.read_bytes()).hexdigest()
          for path in (destination/'src').rglob('*.py')}
(OUT/f'{label}-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(destination)
