"""Sequential production-import-path baselines; old observations retained."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
driver=ROOT/'tools/day_transition_audit.py'
for mode,name in [('headless','headless-year-clean'),('qt','qt-year-clean-valid')]:
 subprocess.run([sys.executable,'-X','utf8',str(driver),mode,'--name',name,'--days','365'],cwd=ROOT,check=True)
subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/day_transition_audit_diagnostics.py')],cwd=ROOT,check=True)
