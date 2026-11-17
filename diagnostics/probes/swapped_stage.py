import sys,time,json,subprocess
from pathlib import Path
from launch import R,REPO,TOOLS,SIM_PYTHON,python_for,env
lane=int(sys.argv[1]);info=R/'logs'/f'early_probe_{lane}.json'
if not info.exists():info=R/'logs'/f'probe_{lane}.json'  # written by after_lane.py
required=[f'motus_{s}_original_{t}' for s in range(200000+lane,200020,4) for t in ('red','blue')]
while not all((R/'internal'/i/'report.json').exists() for i in required):
    p=json.loads(info.read_text())['pid']
    if not Path(f'/proc/{p}/cmdline').exists():raise RuntimeError('Original-layout probe ended before completing all states')
    time.sleep(15)
# Allow the first model process to release its CUDA context before loading another.
pid=json.loads(info.read_text())['pid']
while Path(f'/proc/{pid}/cmdline').exists() and Path(f'/proc/{pid}/cmdline').read_bytes():time.sleep(2)
with open(R/'logs'/f'probe_swapped_{lane}.log','w') as f:
    proc=subprocess.Popen([python_for('motus'),str(TOOLS/'directional_probe_swapped.py'),str(lane)],env=env(lane),stdout=f,stderr=subprocess.STDOUT)
    (R/'logs'/f'probe_swapped_{lane}.json').write_text(json.dumps(dict(pid=proc.pid,lane=lane,start=time.time())))
    assert proc.wait(timeout=7200)==0,'Swapped probe failed'
print('SWAPPED_STAGE_COMPLETE',lane,flush=True)
