import sys,time,json,subprocess
from pathlib import Path
from launch import R,REPO,TOOLS,SIM_PYTHON,python_for,env
gpu=int(sys.argv[1]);lane=gpu-4;jobs=json.loads((R/'protocols'/f'lane_{gpu}.json').read_text())
while not all((R/'controls'/j['id']/'validation.json').exists() for j in jobs):time.sleep(15)
pid=json.loads((R/'logs'/f'service_{gpu}.json').read_text())['pid']
while Path(f'/proc/{pid}/cmdline').exists() and Path(f'/proc/{pid}/cmdline').read_bytes():time.sleep(2)
with open(R/'logs'/f'norm_audit_{gpu}.log','w') as f:
    proc=subprocess.Popen([python_for('motus'),str(TOOLS/'norm_audit.py'),str(lane)],env=env(gpu),stdout=f,stderr=subprocess.STDOUT)
    (R/'logs'/f'norm_audit_{gpu}.json').write_text(json.dumps(dict(pid=proc.pid,gpu=gpu,start=time.time())))
    assert proc.wait(timeout=7200)==0,'Norm audit failed'
print('NORM_AUDIT_COMPLETE',gpu,flush=True)
