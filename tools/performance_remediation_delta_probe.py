"""Profile delta preparation/application separately from economics and Qt."""
import cProfile,json,pstats,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from kojakstreet.adapters.legacy_runtime import IntegratedRuntime
from kojakstreet.day_delta import DayStateEncoder,apply_day_delta,prepare_day_delta,public_copy,state_values
from kojakstreet.core.state import GameState
OUT=ROOT/'.cache/performance-remediation'/(sys.argv[1] if len(sys.argv)>1 else 'delta-probe');OUT.mkdir(parents=True,exist_ok=True)
runtime=IntegratedRuntime(ROOT,data_dir=OUT,seed=20260922,flush_interval_days=1000)
state=runtime.snapshot();encoder=DayStateEncoder(state);receiver=GameState(**public_copy(state_values(state)));revision=0;results=[]
try:
    for iteration in range(1 if '--once' in sys.argv else 6):
        start=time.perf_counter()
        for _ in range(5):runtime.advance_day()
        core_ms=(time.perf_counter()-start)*1000
        profile=cProfile.Profile()
        if '--profile' in sys.argv:profile.enable()
        start=time.perf_counter();state=runtime.snapshot();payload=encoder.update(state);prepare_ms=(time.perf_counter()-start)*1000
        profile.disable()
        if '--profile' in sys.argv:profile.dump_stats(str(OUT/f'prepare-{iteration}.pstats'))
        start=time.perf_counter();text=json.dumps(payload,separators=(',',':'));json_encode_ms=(time.perf_counter()-start)*1000
        start=time.perf_counter();parsed=json.loads(text);json_decode_ms=(time.perf_counter()-start)*1000
        start=time.perf_counter();prepared=prepare_day_delta(parsed);decode_ms=(time.perf_counter()-start)*1000
        start=time.perf_counter();revision=apply_day_delta(receiver,prepared,revision);apply_ms=(time.perf_counter()-start)*1000
        row={'day':(iteration+1)*5,'core_ms':core_ms,'prepare_ms':prepare_ms,'profiled':'--profile' in sys.argv,'bytes':len(text.encode()),'json_encode_ms':json_encode_ms,'json_decode_ms':json_decode_ms,'decode_ms':decode_ms,'apply_ms':apply_ms,'operations':len(prepared['changes'])}
        results.append(row);print(json.dumps(row),flush=True)
    assert state_values(receiver)==public_copy(state_values(state))
    (OUT/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    if '--profile' in sys.argv:pstats.Stats(str(OUT/f'prepare-{iteration}.pstats')).strip_dirs().sort_stats('cumtime').print_stats(20)
finally:runtime.close()
