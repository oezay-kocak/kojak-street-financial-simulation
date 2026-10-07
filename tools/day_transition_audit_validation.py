"""Independent production-window thread check and retained-record integrity checks."""
from __future__ import annotations
import json,os,sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
OUT=Path(os.environ.get('KOJAK_AUDIT_OUTPUT',str(ROOT/'.cache/day-transition-audit')))

def production_window():
    from PySide6.QtCore import QTimer,QThread
    from PySide6.QtWidgets import QApplication
    from kojakstreet.ui_qt.app import KojakStreetWindow
    from kojakstreet.ui_qt.theme import APP_STYLESHEET
    from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
    from kojakstreet.live_process import LiveSimulationProcess
    app=QApplication([]);app.setStyleSheet(APP_STYLESHEET)
    runtime=IntegratedRuntime(ROOT,data_dir=OUT/'production-thread-control',seed=1729)
    initial=runtime.snapshot_for_view('markets')
    process=LiveSimulationProcess.from_runtime(runtime,timeout_seconds=120)
    window=KojakStreetWindow(initial,process)
    observed=[]
    original=window.markets_view.apply_live_quotes
    def observe(*args,**kwargs):
        observed.append({'qt_main':QThread.currentThread()==app.thread(),'thread':threading.get_ident()})
        return original(*args,**kwargs)
    window.markets_view.apply_live_quotes=observe
    window.showMaximized();window.top_bar.run_button.setChecked(True)
    process.set_running(True);window.timer.stop()
    def next_tick():
        if len(observed)>=3:
            app.quit();return
        if not window.simulation_busy and not window._live_update_pending:
            window._request_simulation_steps(1,force_refresh=False)
    timer=QTimer();timer.timeout.connect(next_tick);timer.start(250)
    QTimer.singleShot(120000,app.quit)
    app.exec();timer.stop();window.close()
    result={'production_window_class':type(window).__name__,'ui_observations':observed,
            'passed':len(observed)==3 and all(x['qt_main'] for x in observed),
            'worker_exited':process._process.poll() is not None}
    (OUT/'production-thread-control.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
    assert result['passed']

def records():
    errors=[];total=0;guis=0
    for path in OUT.glob('qt-*-valid.json'):
        r=json.loads(path.read_text());wpath=path.with_name(path.stem+'-worker.jsonl')
        workers=[json.loads(line) for line in wpath.read_text().splitlines()]
        if not r['finished'] or r['errors'] or not r['worker_exited']:errors.append(path.stem+': completion')
        if len(workers)!=len(r['rows']):errors.append(path.stem+': worker count')
        for parent,worker in zip(r['rows'],workers):
            total+=1
            points=[parent['t0'],worker['t1'],parent['t2'],parent['t3'],parent['t4']]
            if any(b<a for a,b in zip(points,points[1:])):errors.append(path.stem+': timestamp order')
            if abs((parent['t4']-parent['t0'])*1000-parent['total_ms'])>1e-6:errors.append(path.stem+': total')
            if max(parent['heartbeat_gaps_ms'][1:],default=0)>parent['total_ms']+1e-6:errors.append(path.stem+': heartbeat outside transition')
            if parent['date']!=worker['date']:errors.append(path.stem+': date')
            if not all(parent.get(k) for k in ('request_is_qt_main','slot_is_qt_main','update_is_qt_main') if not parent['force_refresh'] or k!='update_is_qt_main'):errors.append(path.stem+': thread')
            if parent['model_rows']!=2523 or parent['proxy_rows']<=0:errors.append(path.stem+': models')
        guis+=1
    summary=json.loads((OUT/'summary.json').read_text())
    for key,value in summary['comparisons'].items():
        if not value['economic_signature_equal']:errors.append(key+': economics')
        if not value.get('public_numeric_checkpoint_equal',True):errors.append(key+': full public numbers')
    control=json.loads((OUT/'production-thread-control.json').read_text())
    if not control['passed']:errors.append('production control')
    result={'qt_samples_checked':total,'qt_runs_checked':guis,'comparisons':len(summary['comparisons']),
            'errors':errors,'passed':not errors}
    (OUT/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    assert not errors

if __name__=='__main__':
    {'production':production_window,'records':records}[sys.argv[1]]()
