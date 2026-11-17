import json,time,os,datetime,urllib.request
from pathlib import Path
from paths import R
jobs=json.loads((R/'protocols/jobs.json').read_text());counts={};errors=[];progress=[]
for job in jobs:
    p=R/'runs'/job['id'];key=job['policy'];counts.setdefault(key,{'planned':0,'complete':0,'success':0,'started':0})
    c=counts[key];c['planned']+=1;c['started']+=p.exists()
    if (p/'result.json').exists():
        a=json.loads((p/'result.json').read_text());c['complete']+=a['status']=='complete';c['success']+=a.get('success',False)
    elif (p/'error.txt').exists():errors.append(dict(id=job['id'],error=(p/'error.txt').read_text()[-1500:]))
    elif p.exists():
        files=list(p.glob('model_io/*.json.gz'));progress.append(dict(id=job['id'],decisions=len(files)))
alive=[]
for f in sorted((R/'logs').glob('lane_*.json')):
    m=json.loads(f.read_text());pid=m['pid'];cmd=Path(f'/proc/{pid}/cmdline');alive.append(dict(**m,alive=cmd.exists() and b'lane.py' in cmd.read_bytes()))
control_reports=list((R/'controls').glob('*/validation.json'));probe_reports=list((R/'internal').glob('*/report.json'))
phases=[]
for pattern in ('early_probe_*.json','probe_swapped_*.json','controls_*.json'):
    for f in sorted((R/'logs').glob(pattern)):
        m=json.loads(f.read_text());cmd=Path('/proc/'+str(m['pid'])+'/cmdline');phases.append(dict(file=f.name,pid=m['pid'],alive=cmd.exists() and bool(cmd.read_bytes())))
result=dict(controls_complete=len(control_reports),internal_states_complete=len(probe_reports),phases=phases,time=datetime.datetime.now().astimezone().isoformat(),counts=counts,errors=errors,active=progress,lanes=alive,api_cost=0)
if '--record' in __import__('sys').argv:
    (R/'reports').mkdir(exist_ok=True)
    with (R/'reports/self_checks.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
print(json.dumps(result,indent=2))
