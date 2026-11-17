"""Exploratory first-decision controls. No closed-loop claims."""
from future_targets import readout,R
from analyze import interval
import numpy as np,json
joints=[0,1,2,3,4,5,7,8,9,10,11,12];rows=[]
for job in json.loads((R/'protocols/jobs.json').read_text()):
 ident=job['id'];base=np.load(R/'predictions'/ident/'0/actions.npz')['actions'][:16,joints]
 v=json.loads((R/'controls'/ident/'validation.json').read_text());assert v['pass_replay']
 for control in ['noise','please']:
  p=R/'controls'/ident/(control+'.json')
  if not p.exists():continue
  acts=np.array(json.loads(p.read_text())['actions'])[:16,joints]
  row=dict(id=ident,seed=job['seed'],policy=job['policy'],layout=job['layout'],target=job['target'],control=control,action_rms=float(np.sqrt(np.mean((acts-base)**2))))
  if job['policy']=='Motus':
   f=R/'predictions'/(control+'_'+ident)/'0/future.npz'
   frame=np.load(f)['frames'][0,:,7].transpose(1,2,0)
   row['future_rule_label']=readout(frame)['label'];row['future_rule_correct']=row['future_rule_label']==job['target']
  rows.append(row)
summary={}
for pol in ['Pi05','Motus']:
 for ctrl in ['noise','please']:
  g=[x for x in rows if x['policy']==pol and x['control']==ctrl];assert len(g)==(80 if ctrl=='noise' else 40)
  seeds=sorted({x['seed'] for x in g});s={'n_states':len(g),'n_scenes':len(seeds),'action_rms':interval([np.mean([x['action_rms'] for x in g if x['seed']==seed]) for seed in seeds])}
  if pol=='Motus':
   s['future_rule_correct_count']=sum(x['future_rule_correct'] for x in g);s['future_rule_readable_count']=sum(x['future_rule_label'] in ['red','blue','green'] for x in g)
   pairs={(x['seed'],x['layout']):[] for x in g}
   for x in g:pairs[x['seed'],x['layout']].append(x)
   s['future_rule_switch_pair_count']=sum(len(v)==2 and all(x['future_rule_correct'] for x in v) for v in pairs.values());s['n_pairs']=len(pairs)
  summary[pol+'_'+ctrl]=s
(R/'analyses/auxiliary_summary.json').write_text(json.dumps(dict(summary=summary,rows=rows,notes='Exploratory fixed-rule future readouts, not independently visually reviewed. First decision only; no execution or success measurement.'),indent=2));print({k:{a:b for a,b in v.items() if a!='action_rms'} for k,v in summary.items()})
