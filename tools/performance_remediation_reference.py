"""Freeze the pre-change source and audit evidence without touching game saves."""
from __future__ import annotations
import hashlib,json,subprocess,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.cache/performance-remediation'
GIT=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    destination=OUT/'reference-source.zip'
    if destination.exists():raise RuntimeError('Reference already exists; refusing to overwrite it')
    commit=subprocess.check_output([str(GIT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    subprocess.run([str(GIT),'archive','--format=zip',f'--output={destination}',commit],cwd=ROOT,check=True)
    with zipfile.ZipFile(destination) as archive:archive.extractall(OUT/'reference-source')
    with zipfile.ZipFile(OUT/'reference-audit-tools.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in (ROOT/'tools').glob('day_transition_audit*.py'):archive.write(path,path.relative_to(ROOT))
    paths=[ROOT/'.cache/day-transition-audit'/name for name in ('checkpoint-end.json','checkpoint-1990-01-15.json','checkpoint-1990-12-31.json','headless-year/kojakstreet.duckdb','summary.json','merged-results.json')]
    manifest={'commit':commit,'seed':1729,'baseline':[]}
    for path in paths:
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        manifest['baseline'].append({'path':str(path),'bytes':path.stat().st_size,'sha256':digest})
    (OUT/'reference-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
