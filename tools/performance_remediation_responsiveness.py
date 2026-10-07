"""Locate main-thread heartbeat gaps without changing the regression test."""
import gc,json,os,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'tools')]
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet import live_process as lp,day_delta
from kojakstreet.ui_qt.app import KojakStreetWindow
from kojakstreet.ui_qt.views.markets_view import MarketsView
OUT=ROOT/'.cache/performance-remediation';rows=[];active=False
def wrap(owner,name,label):
    original=getattr(owner,name)
    def measured(*a,**kw):
        start=time.perf_counter()
        try:return original(*a,**kw)
        finally:
            if active:rows.append({'label':label,'start':start,'end':time.perf_counter()})
    setattr(owner,name,measured)
for owner,name,label in [(lp,'prepare_day_delta','decode_delta'),(lp,'apply_day_delta','apply_delta'),
                         (day_delta._DataUnpickler,'load','unpickle_chunk'),
                         (MarketsView,'apply_live_quotes','ui_quotes'),
                         (KojakStreetWindow,'_apply_live_market_updates','ui_update')]:wrap(owner,name,label)
gc_start={}
def observe(phase,info):
    if not active:return
    if phase=='start':gc_start[info['generation']]=time.perf_counter()
    elif info['generation'] in gc_start:rows.append({'label':f"gc_{info['generation']}",'start':gc_start.pop(info['generation']),'end':time.perf_counter()})
gc.callbacks.append(observe)
app=QApplication([])
direct=IntegratedRuntime(ROOT,data_dir=OUT/'responsiveness-direct',seed=20260922,flush_interval_days=1000)
direct.advance_days(30)
direct.close()
bootstrap=IntegratedRuntime(ROOT,data_dir=OUT/'responsiveness',seed=20260922,flush_interval_days=1000)
initial=bootstrap.snapshot_for_view('markets');process=lp.LiveSimulationProcess.from_runtime(bootstrap,timeout_seconds=90)
window=KojakStreetWindow(initial,process);beats=[];timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:beats.append(time.perf_counter()))
try:
    active=True;timer.start();start=time.perf_counter();window._request_simulation_steps(30,force_refresh=False)
    while window.simulation_busy and time.perf_counter()-start<60:app.processEvents();time.sleep(.002)
    app.processEvents();timer.stop();active=False
    gaps=[]
    for before,after in zip(beats,beats[1:]):
        if after-before>.080:gaps.append({'ms':(after-before)*1000,'overlap':[{'label':r['label'],'ms':(r['end']-r['start'])*1000} for r in rows if r['start']<after and r['end']>before and r['end']-r['start']>.02]})
    result={'elapsed_ms':(time.perf_counter()-start)*1000,'busy':window.simulation_busy,'last_apply_ms':process.last_apply_ms,'gaps':gaps,'spans':rows}
    (OUT/'responsiveness.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='spans'},indent=2),flush=True)
finally:window.close();app.processEvents();process.close()
