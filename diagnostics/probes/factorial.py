import json,gzip
from pathlib import Path
import numpy as np
from analyze import interval
from paths import R
joints=[0,1,2,3,4,5,7,8,9,10,11,12]
def rms(x):return float(np.sqrt(np.mean(x*x)))
def mae(x):return float(np.abs(x).mean())
rows=[]
for policy in ('Pi05','Motus'):
 for seed in range(200000,200020):
    ids=[f'{policy.lower()}_{seed}_{l}_{t}' for l in ('original','swapped') for t in ('red','blue')]
    if not all((R/'controls'/i/'validation.json').exists() for i in ids):continue
    acts=[];noise=[];frames=[];noisyframes=[]
    for ident in ids:
        v=json.loads((R/'controls'/ident/'validation.json').read_text());assert v['pass_replay']
        acts.append(np.load(R/'predictions'/ident/'0/actions.npz')['actions'][:16,joints])
        noise.append(np.asarray(json.loads((R/'controls'/ident/'noise.json').read_text())['actions'])[:16,joints])
        if policy=='Motus':
            frames.append(np.load(R/'predictions'/ident/'0/future.npz')['frames'][0,:,7,12:252].astype(float))
            noisyframes.append(np.load(R/'predictions'/('noise_'+ident)/'0/future.npz')['frames'][0,:,7,12:252].astype(float))
    a,b,c,d=acts
    row=dict(policy=policy,seed=seed,action_language_rms=np.mean([rms(a-b),rms(c-d)]),action_visual_rms=np.mean([rms(a-c),rms(b-d)]),action_noise_rms=np.mean([rms(x-y) for x,y in zip(acts,noise)]),action_interaction_rms=rms(a-b-c+d))
    if frames:
        a,b,c,d=frames;row.update(video_language_mae=np.mean([mae(a-b),mae(c-d)]),video_visual_mae=np.mean([mae(a-c),mae(b-d)]),video_noise_mae=np.mean([mae(x-y) for x,y in zip(frames,noisyframes)]),video_interaction_mae=mae(a-b-c+d))
    rows.append(row)
summary={}
for policy in ('Pi05','Motus'):
    group=[r for r in rows if r['policy']==policy]
    if group:summary[policy]={k:interval([r[k] for r in group]) for k in group[0] if k not in ('policy','seed')}
(R/'analyses/factorial.json').write_text(json.dumps(dict(rows=rows,summary=summary),indent=2));print('factorial scenes',len(rows))
