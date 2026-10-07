"""Run independent measurements sequentially so they do not compete for CPU."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
jobs=[
 ['headless','--days','365','--name','headless-year'],
 ['headless','--days','365','--name','headless-year-clean'],
 ['headless','--days','20','--checkpoint','end','--name','headless-mature'],
 ['qt','--days','365','--name','qt-year-clean-valid'],
 ['qt','--days','20','--checkpoint','end','--name','qt-mature-none-valid'],
 ['qt','--days','20','--checkpoint','end','--name','qt-mature-detail-valid','--chart','detail'],
 ['qt','--days','20','--checkpoint','end','--name','qt-mature-candle-valid','--chart','candle'],
 ['qt','--days','20','--checkpoint','end','--name','qt-mature-preview-valid','--chart','preview'],
 ['qt','--days','20','--checkpoint','1990-12-31','--name','qt-year-repeat-valid','--repeat-span','4'],
 ['profiles','--name','profiles'],
 ['qt','--days','3','--checkpoint','end','--name','qt-profile-none-valid','--profile-ui'],
 ['qt','--days','3','--checkpoint','end','--name','qt-profile-detail-valid','--profile-ui','--chart','detail'],
 ['qt','--days','3','--checkpoint','end','--name','qt-force-snapshot-valid','--force-refresh'],
 ['headless','--days','20','--name','control-original','--uninstrumented'],
 ['headless','--days','20','--name','control-instrumented'],
]
for job in jobs:
 print('START',job,flush=True)
 subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/day_transition_audit.py'),*job],cwd=ROOT,check=True)
 print('FINISHED',job,flush=True)
for job in [['tools/day_transition_audit_extras.py'],['tools/day_transition_audit_path_control.py'],['tools/day_transition_audit_snapshot_volume.py'],['tools/day_transition_audit_summary.py'],['tools/day_transition_audit_validation.py','records'],['tools/day_transition_audit_report.py']]:
 subprocess.run([sys.executable,'-X','utf8',*job],cwd=ROOT,check=True)
