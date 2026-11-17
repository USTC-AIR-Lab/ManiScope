import json
from pathlib import Path
import numpy as np
from analyze import interval
from paths import R
kin={x['id']:x for x in json.loads((R/'analyses/kinematics.json').read_text())}
futures={x['id']:x for x in json.loads((R/'analyses/future_targets_final.json').read_text())}
rows=[];norm_rows=[];audit_errors=[]
for p in sorted((R/'internal').glob('*/report.json')):
    d=json.loads(p.read_text());ident=d['id'];layout='swapped' if '_swapped_' in ident else 'original';other=ident.rsplit('_',1)[0]+'_'+d['donor_target']
    a=np.load(p.parent/'actions.npz');expected=np.load(R/'predictions'/other/'0/actions.npz')['actions'];donor_error=float(np.max(np.abs(a['donor']-expected)));assert donor_error<=1e-6
    valid=futures[other]['final_label']==d['donor_target'];informative=valid and futures[ident]['final_label'] in ('red','blue','green') and futures[ident]['final_label']!=futures[other]['final_label']
    base_label=futures[ident]['final_label'];donor_label=futures[other]['final_label'];represented=base_label in ('red','blue','green') and donor_label in ('red','blue','green') and base_label!=donor_label
    traj=np.load(R/'analyses/kinematics'/ident/'tcp.npz');initial=json.loads((R/'runs'/ident/'initial.json').read_text())['positions'];roles={'red':'target','blue':'d2','green':'d1'}
    def preference(points,a,b):
        da=np.linalg.norm(points[:16]-np.asarray(initial[roles[a]]),axis=-1).min(-1);db=np.linalg.norm(points[:16]-np.asarray(initial[roles[b]]),axis=-1).min(-1);return float(np.mean(da-db))
    b=kin[ident]['metrics']['baseline']['signed_blue_preference_m'];sign=1 if d['donor_target']=='blue' else -1
    for mode,m in d['metrics'].items():
        shift=sign*(kin[ident]['metrics'][mode]['signed_blue_preference_m']-b)
        represented_shift=preference(traj[mode],base_label,donor_label)-preference(traj['baseline'],base_label,donor_label) if represented else None
        rows.append(dict(represented_target_shift_m=represented_shift,represented_contrast=represented,id=ident,seed=d['seed'],layout=layout,recipient=d['target'],donor=d['donor_target'],mode=mode,donor_valid=valid,informative_contrast=informative,target_directed_shift_m=shift,**m))
    audit=R/'internal_norm_audit'/ident
    if layout=='original':
        assert (audit/'report.json').exists()
        aa=np.load(audit/'actions.npz');error=max(float(np.max(np.abs(aa[k]-a[k]))) for k in aa.files);assert error<=1e-6;audit_errors.append(error);norm_path=audit/'norms.json'
    else:norm_path=p.parent/'norms.json'
    norms=json.loads(norm_path.read_text())
    for mode in ('future_matched','current_matched','understanding_matched','future_scrambled'):
        ratios=[]
        for site in norms[mode]:
            for key in ('k','v'):
                ref=site[key+'_reference_future_norm']
                if ref>1e-8:ratios.append(site[key+'_applied_delta_norm']/ref)
        norm_rows.append(dict(id=ident,mode=mode,ratio_median=float(np.median(ratios)),ratio_min=float(min(ratios)),ratio_max=float(max(ratios)),fraction_within_10percent=float(np.mean(np.abs(np.asarray(ratios)-1)<=.1))))
summary={}
for stratum,predicate in [('all',lambda r:True),('valid_donor',lambda r:r['donor_valid']),('informative',lambda r:r['informative_contrast']),('represented_contrast',lambda r:r['represented_contrast'])]:
    summary[stratum]={}
    for mode in sorted({r['mode'] for r in rows}):
        subset=[r for r in rows if r['mode']==mode and predicate(r)];seeds=sorted({r['seed'] for r in subset})
        if not seeds:continue
        summary[stratum][mode]=dict(n_states=len(subset),n_scenes=len(seeds),metrics={key:interval([np.mean([r[key] for r in subset if r['seed']==s]) for s in seeds]) for key in (('target_directed_shift_m','joint_rms','represented_target_shift_m') if stratum in ('informative','represented_contrast') else ('target_directed_shift_m','joint_rms'))})
for stratum in summary.values():
    for condition in stratum.values():
        if condition['n_scenes'] < 2:
            for metric in condition['metrics'].values():
                metric['ci95']=None
                metric['interval_note']='Not estimable from one independent scene; point estimate is descriptive only.'
result=dict(n_states=len(rows)//len({r['mode'] for r in rows}),rows=rows,summary=summary,norm_audit=norm_rows,norm_audit_action_replay_max_abs=max(audit_errors,default=0),notes='Target-directed shift is commanded TCP geometry in an isolated kinematic scene, not observed execution or success. Conditional donor strata do not estimate a population-wide causal mediation effect.')
(R/'analyses/internal_summary.json').write_text(json.dumps(result,indent=2));print('internal analyzed',result['n_states'])
