import os,sys,json,time,subprocess,urllib.request,traceback
from pathlib import Path
from launch import R,REPO,TOOLS,SIM_PYTHON,python_for,env
gpu=int(sys.argv[1]);jobs=json.loads((R/'protocols'/f'lane_{gpu}.json').read_text());e=env(gpu)
for job in jobs:
    dest=R/'runs'/job['id']
    if (dest/'result.json').exists():continue
    if dest.exists():raise RuntimeError('Incomplete run exists; inspect before retry: '+str(dest))
    jobfile=R/'protocols'/(job['id']+'.json');jobfile.write_text(json.dumps(job,indent=2))
    with open(R/'logs'/(job['id']+'.log'),'w') as log:
        result=subprocess.run([SIM_PYTHON,str(TOOLS/'run_episode.py'),str(jobfile)],cwd=REPO,env=e,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
    if result.returncode:raise RuntimeError('Episode failed: '+job['id'])
    print('COMPLETE',job['id'],flush=True)
print('LANE_COMPLETE',gpu,flush=True)
