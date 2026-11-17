"""Run only after this GPU's primary lane has finished; never interleave policy state."""
import json,gzip,copy,sys,time
from pathlib import Path
import requests,numpy as np
from paths import R
gpu=int(sys.argv[1]);jobs=json.loads((R/'protocols'/f'lane_{gpu}.json').read_text());out=R/'controls';out.mkdir(exist_ok=True)
for job in jobs:
    assert (R/'runs'/job['id']/'result.json').exists()
    dest=out/job['id'];dest.mkdir(exist_ok=False)
    with gzip.open(R/'runs'/job['id']/'model_io/0.json.gz','rt') as f:io=json.load(f)
    records={}
    conditions=[('replay',17),('noise',29)]+([('please',17)] if job['layout']=='original' else [])
    for condition,seed in conditions:
        body=copy.deepcopy(io['request']);body.update(save_id=condition+'_'+job['id'],diagnostic_rng_seed=seed)
        if condition=='please':body['observation']['prompt']='Please '+body['observation']['prompt'][0].lower()+body['observation']['prompt'][1:]
        requests.post(job['url']+'/v1/reset',timeout=30).raise_for_status()
        res=requests.post(job['url']+'/v1/infer',json=body,timeout=600);res.raise_for_status();data=res.json()
        (dest/(condition+'.json')).write_text(json.dumps(data));records[condition]=np.asarray(data['actions'])
    error=float(np.max(np.abs(records['replay']-np.asarray(io['response']['actions']))))
    report=dict(id=job['id'],replay_max_abs=error,pass_replay=error<=1e-6)
    (dest/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    if error>1e-6:raise RuntimeError('Replay failed; investigate before interpreting paired differences')
