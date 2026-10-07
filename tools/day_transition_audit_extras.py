"""Additional chart/allocation controls, sequential and isolated."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for job in [
 ['tools/day_transition_audit_diagnostics.py'],
 ['tools/day_transition_audit.py','qt','--days','20','--checkpoint','end','--name','qt-mature-heavy-valid','--chart','detail','--indicators'],
 ['tools/day_transition_audit.py','qt','--days','1','--checkpoint','end','--name','qt-allocation-none-valid','--trace-ui'],
 ['tools/day_transition_audit.py','qt','--days','1','--checkpoint','end','--name','qt-allocation-detail-valid','--trace-ui','--chart','detail','--indicators'],
 ['tools/day_transition_audit_validation.py','production'],
]:
 print('START',job,flush=True)
 subprocess.run([sys.executable,*job],cwd=ROOT,check=True)
 print('FINISHED',job,flush=True)
