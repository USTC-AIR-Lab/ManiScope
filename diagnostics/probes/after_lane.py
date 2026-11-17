"""Finite experiment stages, keyed to completed jobs; no policy-result selection."""
import os,sys,time,json,subprocess,signal
from pathlib import Path
from launch import R,REPO,TOOLS,SIM_PYTHON,python_for,env
gpu=int(sys.argv[1]);jobs=json.loads((R/'protocols'/f'lane_{gpu}.json').read_text())
while not all((R/'runs'/j['id']/'result.json').exists() for j in jobs):
    failures=[j['id'] for j in jobs if (R/'runs'/j['id']/'error.txt').exists()]
    if failures:raise RuntimeError('Primary infrastructure errors: '+repr(failures))
    time.sleep(15)
e=env(gpu);kind='pi05' if gpu<4 else 'motus'
with open(R/'logs'/f'controls_{gpu}.log','w') as f:
    p=subprocess.Popen([python_for(kind),str(TOOLS/'noise_controls.py'),str(gpu)],env=e,stdout=f,stderr=subprocess.STDOUT)
    (R/'logs'/f'controls_{gpu}.json').write_text(json.dumps(dict(pid=p.pid,gpu=gpu,started=time.time())))
    assert p.wait(timeout=3600)==0,'noise controls failed'
service=json.loads((R/'logs'/f'service_{gpu}.json').read_text());pid=service['pid'];cmd=Path(f'/proc/{pid}/cmdline').read_bytes();assert str(TOOLS/'service.py').encode() in cmd
os.kill(pid,signal.SIGTERM)
if gpu<4 and (R/'logs'/f'early_probe_{gpu}.json').exists():
    required=[f'motus_{s}_original_{t}' for s in range(200000+gpu,200020,4) for t in ('red','blue')]
    while not all((R/'internal'/j/'report.json').exists() for j in required):time.sleep(15)
elif gpu<4:
    required=[f'motus_{s}_original_{t}' for s in range(200000+gpu,200020,4) for t in ('red','blue')]
    while not all((R/'runs'/j/'result.json').exists() for j in required):time.sleep(15)
    with open(R/'logs'/f'probe_{gpu}.log','w') as f:
        p=subprocess.Popen([python_for('motus'),str(TOOLS/'directional_probe.py'),str(gpu)],env=e,stdout=f,stderr=subprocess.STDOUT)
        (R/'logs'/f'probe_{gpu}.json').write_text(json.dumps(dict(pid=p.pid,gpu=gpu,started=time.time())))
        assert p.wait(timeout=7200)==0,'directional probe failed'
print('ALL_STAGES_COMPLETE',gpu,flush=True)
