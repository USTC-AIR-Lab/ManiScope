"""All denominators include no-selection; bootstrap resamples scene clusters."""
import json,math,collections,gzip
from pathlib import Path
import numpy as np
from paths import R
ROLE_COLOR={'target':'red','d1':'green','d2':'blue'}
def distance(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
def analyze(job):
    dest=R/'runs'/job['id'];p=next(dest.glob('telemetry/*/*/*/trace.jsonl'))
    first=None;approach=None;hold=None;hold_since={};approach_since={};initial=None;maxlift={k:0. for k in ROLE_COLOR};firsts={str(t):None for t in (.01,.1,1.)}
    for line in p.open():
        e=json.loads(line)
        if e['event']=='start':
            initial=e;links=set(e['gripper_links']);initdist={(arm,k):distance(e['robot'][arm]['tcp'][:3],e['objects'][k]['p']) for arm in ('left','right') for k in ROLE_COLOR}
        if e['event']!='physics':continue
        t=e['sim_seconds'];loaded={}
        for threshold in (.01,.1,1.):
            selected={}
            for c in e['contacts']:
                roles=[k for k in c['entities'] if k in ROLE_COLOR]
                if roles and links.intersection(c['entities']) and c['impulse_sum']/initial['timestep']>=threshold:
                    for k in roles:selected.setdefault(k,set()).update(links.intersection(c['entities']))
            if selected and firsts[str(threshold)] is None:firsts[str(threshold)]=dict(colors=sorted(ROLE_COLOR[k] for k in selected),sim_s=t,decision=e['decision_index'])
            if threshold==.1:loaded=selected
        first=firsts['0.1']
        qualifies=set()
        for arm in ('left','right'):
            ds=sorted((distance(e['robot'][arm]['tcp'][:3],e['objects'][k]['p']),k) for k in ROLE_COLOR);d,k=ds[0]
            if d<=.12 and ds[1][0]-d>=.02 and initdist[(arm,k)]-d>=.03:qualifies.add(k)
        for k in list(approach_since):
            if k not in qualifies:del approach_since[k]
        for k in qualifies:approach_since.setdefault(k,t)
        established=sorted(ROLE_COLOR[k] for k in qualifies if t-approach_since[k]>=.2)
        if approach is None and established and (first is None or t<first['sim_s']):approach=dict(colors=established,sim_s=t)
        for k in ROLE_COLOR:
            lift=e['objects'][k]['p'][2]-initial['objects'][k]['p'][2];maxlift[k]=max(maxlift[k],lift)
            held=lift>=.02 and any({prefix+'7',prefix+'8'}<=loaded.get(k,set()) for prefix in ('fl_link','fr_link'))
            if held:
                hold_since.setdefault(k,t)
                if hold is None and t-hold_since[k]>=.2:hold=dict(color=ROLE_COLOR[k],sim_s=t)
            else:hold_since.pop(k,None)
    result=json.loads((dest/'result.json').read_text())
    def label(x):return 'none' if not x else (x['colors'][0] if len(x['colors'])==1 else 'ambiguous')
    return dict(**job,**result,first_contact=first,contact_label=label(first),contact_correct=label(first)==job['target'],approach=approach,approach_label=label(approach),approach_correct=label(approach)==job['target'],first_hold=hold,hold_correct=bool(hold and hold['color']==job['target']),max_lift_m={ROLE_COLOR[k]:v for k,v in maxlift.items()},contact_sensitivity=firsts,trace=str(p))
def interval(values):
    a=np.asarray(values,dtype=float);rng=np.random.default_rng(9023);means=a[rng.integers(0,len(a),(20000,len(a)))].mean(1)
    return dict(mean=float(a.mean()),ci95=np.quantile(means,[.025,.975]).tolist(),n_scenes=len(a),scene_values=a.tolist())
def main():
    jobs=json.loads((R/'protocols/jobs.json').read_text());rows=[analyze(j) for j in jobs if (R/'runs'/j['id']/'result.json').exists()]
    out=R/'analyses';out.mkdir(exist_ok=True);(out/'episodes.json').write_text(json.dumps(rows,indent=2))
    summary={};lookup={(x['policy'],x['seed'],x['layout'],x['target']):x for x in rows}
    for pol in ('Pi05','Motus'):
        scene=[]
        for seed in range(200000,200020):
            cells=[lookup.get((pol,seed,l,t)) for l in ('original','swapped') for t in ('red','blue')]
            if any(x is None for x in cells):continue
            v={k:float(np.mean([x[k] for x in cells])) for k in ('success','contact_correct','approach_correct','hold_correct')}
            v['language_switch_pair']=np.mean([lookup[pol,seed,l,'red']['contact_correct'] and lookup[pol,seed,l,'blue']['contact_correct'] for l in ('original','swapped')])
            v['layout_tracking_pair']=np.mean([lookup[pol,seed,'original',t]['contact_correct'] and lookup[pol,seed,'swapped',t]['contact_correct'] for t in ('red','blue')])
            v['all_four_correct']=all(x['contact_correct'] for x in cells)
            v['contact_coverage']=np.mean([x['contact_label'] not in ('none','ambiguous') for x in cells]);scene.append(v)
        if scene:summary[pol]={k:interval([v[k] for v in scene]) for k in scene[0]}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(dict(episodes=len(rows),complete_scenes={k:v['success']['n_scenes'] for k,v in summary.items()})))
if __name__=='__main__':main()
