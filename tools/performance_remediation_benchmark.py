"""Isolated sequential phase and complete day-transition measurements."""
import argparse,os,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.cache/performance-remediation'
CHARTS=[('none',[]),('detail',['--chart','detail']),('candle',['--chart','candle']),('preview',['--chart','preview']),('heavy',['--chart','detail','--indicators'])]

def run_job(env,job):
    print('START',job,flush=True)
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/day_transition_audit.py'),*job],cwd=ROOT,env=env,check=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('history-before','history-after','step-before','step-after','reaudit'));args=parser.parse_args()
    env=os.environ.copy();env['KOJAK_AUDIT_OUTPUT']=str(OUT/args.phase)
    if args.phase=='history-before':
        env['KOJAK_AUDIT_PROJECT_ROOT']=str(OUT/'reference-source')
        for label,options in CHARTS:
            run_job(env,['qt','--checkpoint','end','--days','1','--profile-ui','--name',f'qt-profile-{label}-valid',*options])
    elif args.phase=='history-after':
        for label,options in CHARTS:
            run_job(env,['qt','--checkpoint','end','--days','20','--name',f'qt-mature-{label}-valid',*options])
            run_job(env,['qt','--checkpoint','end','--days','1','--profile-ui','--name',f'qt-profile-{label}-valid',*options])
    elif args.phase in ('step-before','step-after'):
        if args.phase=='step-before':
            env['KOJAK_AUDIT_PROJECT_ROOT']=str(OUT/'step-reference-source')
            run_job(env,['qt','--checkpoint','end','--days','3','--manual-step','--name','qt-manual-step-valid'])
        else:
            run_job(env,['qt','--checkpoint','end','--days','20','--manual-step','--name','qt-manual-step-valid'])
            run_job(env,['qt','--checkpoint','end','--days','20','--manual-step','--chart','detail','--indicators','--name','qt-manual-heavy-valid'])
    else:
        for mode,name,days,extra in [
            ('headless','headless-year-clean',365,[]),('headless','headless-mature',20,['--checkpoint','end']),
            ('headless','control-original',20,['--checkpoint','end','--uninstrumented']),
            ('headless','control-instrumented',20,['--checkpoint','end']),
            ('qt','qt-year-clean-valid',365,[]),('qt','qt-year-repeat-valid',20,['--checkpoint','1990-12-31','--repeat-span','4']),
        ]:run_job(env,[mode,'--name',name,'--days',str(days),*extra])
        for label,options in CHARTS:
            run_job(env,['qt','--checkpoint','end','--days','20','--name',f'qt-mature-{label}-valid',*options])
            run_job(env,['qt','--checkpoint','end','--days','3','--profile-ui','--name',f'qt-profile-{label}-valid',*options])
        run_job(env,['qt','--checkpoint','end','--days','20','--manual-step','--name','qt-manual-step-valid'])
        run_job(env,['profiles','--name','profiles'])
        for label,options in [('none',[]),('detail',['--chart','detail','--indicators'])]:
            run_job(env,['qt','--checkpoint','end','--days','1','--trace-ui','--name',f'qt-allocation-{label}-valid',*options])
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tools/day_transition_audit_summary.py')],cwd=ROOT,env=env,check=True)

if __name__=='__main__':main()
