import json,gzip,hashlib
from pathlib import Path
import numpy as np
from paths import R
jobs=json.loads((R/'protocols/jobs.json').read_text());checks=[];manifest=[]
for seed in range(200000,200020):
    initial={}
    for p in ('pi05','motus'):
        for l in ('original','swapped'):
            for t in ('red','blue'):
                ident=f'{p}_{seed}_{l}_{t}';d=R/'runs'/ident
                if not (d/'result.json').exists():continue
                result=json.loads((d/'result.json').read_text());assert result['status']=='complete'
                a=json.loads((d/'initial.json').read_text());initial[p,l,t]=a
                with gzip.open(d/'model_io/0.json.gz','rt') as f:body=json.load(f)
                assert body['request']['observation']['prompt']==f'Pick up the {t} block.'
                assert body['request']['diagnostic_rng_seed']==17
                assert all(np.isfinite(body['response']['actions']).ravel())
                trace=next(d.glob('telemetry/*/*/*/trace.jsonl'))
                with trace.open() as f:start=json.loads(next(f))
                assert start['target_role']==('target' if t=='red' else 'd2')
                manifest.append(dict(id=ident,seed=seed,policy=p,layout=l,target=t,result=result,initial_image_sha256=a['image_sha256'],trace=str(trace),video=str(d/'execution.mp4'),first_model_io=str(d/'model_io/0.json.gz')))
    if len(initial)!=8:continue
    for l in ('original','swapped'):
        ref=initial['pi05',l,'red']
        for p in ('pi05','motus'):
            for t in ('red','blue'):
                x=initial[p,l,t];assert ref['image_sha256']==x['image_sha256'],(seed,p,l,t,'image')
                assert ref['snapshot']['robot']==x['snapshot']['robot'],(seed,p,l,t,'robot')
                assert ref['positions']==x['positions']
    a=initial['pi05','original','red'];b=initial['pi05','swapped','red']
    assert a['snapshot']['robot']==b['snapshot']['robot']
    assert a['positions']['target']==b['positions']['d2'] and a['positions']['d2']==b['positions']['target'] and a['positions']['d1']==b['positions']['d1']
    checks.append(dict(seed=seed,pass_all=True))
(R/'reports').mkdir(exist_ok=True);(R/'reports/pairing_validation.json').write_text(json.dumps(dict(complete_episodes=len(manifest),complete_scenes=len(checks),checks=checks,full_pass=len(manifest)==160 and len(checks)==20),indent=2))
(R/'reports/episode_index.json').write_text(json.dumps(manifest,indent=2));print('paired validation',len(manifest),len(checks))
