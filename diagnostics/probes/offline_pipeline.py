"""Finite remote pipeline, detached from the client; never starts paid APIs."""
import os,sys,time,json,subprocess,traceback,fcntl,hashlib,tarfile,threading
from pathlib import Path
from launch import R,REPO,TOOLS,SIM_PYTHON,python_for,env
D=R/'offline';D.mkdir(exist_ok=True)
lock=(D/'pipeline.lock').open('w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:sys.exit('Another offline pipeline is already running')
state={'pid':os.getpid(),'started':time.time(),'status':'running','stage':'preflight','completed':[],'pending_review':[]}
mu=threading.Lock();done=threading.Event()
def record(**kw):
    with mu:
        state.update(kw);state['updated']=time.time()
        tmp=D/'status.tmp';tmp.write_text(json.dumps(state,indent=2));tmp.replace(D/'status.json')
def heartbeat():
    while not done.is_set():
        record()
        with (D/'self_checks.jsonl').open('a') as f:f.write(json.dumps(dict(time=time.time(),status=state['status'],stage=state['stage'],completed=list(state['completed'])))+'\n')
        done.wait(1200)
threading.Thread(target=heartbeat,daemon=True).start()
e=env(0);py=python_for('motus')
def run(name,cmd,timeout=7200):
    record(stage=name)
    print('START',name,flush=True)
    with (D/(name+'.log')).open('a') as f:
        p=subprocess.run(cmd,env=e,cwd=REPO,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    if p.returncode:raise RuntimeError(f'{name} failed with code {p.returncode}; see offline/{name}.log')
    state['completed'].append(name);record();print('DONE',name,flush=True)
def script(name):run(name,[py,str(TOOLS/f'{name}.py')])
try:
    jobs=json.loads((R/'protocols/jobs.json').read_text())
    for j in jobs:
        assert json.loads((R/'runs'/j['id']/'result.json').read_text())['status']=='complete',j['id']
        assert json.loads((R/'controls'/j['id']/'validation.json').read_text())['pass_replay'],j['id']
    assert len(list((R/'internal').glob('*/report.json')))==80
    assert len(list((R/'internal_norm_audit').glob('*/report.json')))==40
    for name in ['analyze','validate','shortcut_patterns','future_targets','future_sheets','factorial']:script(name)
    run('forward_kinematics',[SIM_PYTHON,str(TOOLS/'forward_kinematics.py')])
    run('figures',[py,str(TOOLS/'figures.py'),'framework','paired_design','outcomes','factorial'])
    review=R/'reports/future_visual_review.json'
    if review.exists() and len(json.loads(review.read_text()))==80:
        script('finalize_future_labels');script('internal_summary')
        run('future_figure',[py,str(TOOLS/'figures.py'),'future_results'])
    else:
        state['pending_review'].append('Complete visual review of all 80 future forecasts, then finalize labels, semantic internal summary and reviewed paper document.')
    record(stage='archive')
    # Preserve raw evidence plus reproducible scripts; omit caches and runtime logs.
    roots=['protocols','tools','framework','runs','predictions','controls','internal','internal_norm_audit','analyses','figures','reports']
    files=sorted(p for name in roots for p in (R/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    manifest=[]
    for p in files:
        h=hashlib.sha256()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
        manifest.append({'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':h.hexdigest()})
    (D/'manifest.json').write_text(json.dumps(manifest,indent=2))
    tmp=D/'results.tar.gz.partial'
    with tarfile.open(tmp,'w:gz',compresslevel=1) as tar:
        for p in files:tar.add(p,arcname=str(p.relative_to(R)),recursive=False)
        tar.add(D/'manifest.json',arcname='manifest.json')
    tmp.replace(D/'results.tar.gz')
    state['completed'].append('archive')
    record(status='compute_complete_review_pending' if state['pending_review'] else 'compute_complete',stage='finished',finished=time.time(),archive=str(D/'results.tar.gz'),files=len(files))
except BaseException:
    record(status='failed',error=traceback.format_exc());traceback.print_exc();sys.exit(1)
finally:done.set()
