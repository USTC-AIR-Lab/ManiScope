"""Map commanded qpos to TCP positions in a separate scene, never a running trial.
These are commanded kinematics, not realized execution or contact predictions.
"""
import os,sys,json,gzip
from pathlib import Path
import numpy as np
from run_episode import configuration,attr_color_block_3way,ROOT as R
from pilot_telemetry import joint_mapping
env=attr_color_block_3way();env.setup_demo(now_ep_num=0,seed=199999,is_test=True,**configuration());mapping=joint_mapping(env.robot)
def setq(qs):
    for side in ('left','right'):getattr(env.robot,side+'_entity').set_qpos(np.asarray(qs[side],np.float32))
def tcp():return np.asarray([getattr(env.robot,'get_'+side+'_tcp_pose')()[:3] for side in ('left','right')])
def trajectory(actions,initial):
    q={s:np.asarray(initial['robot'][s]['qpos']).copy() for s in ('left','right')};points=[]
    for a in actions:
        for side,lo in [('left',0),('right',7)]:q[side][mapping[side]['arm_indices']]=a[lo:lo+6]
        setq(q);points.append(tcp())
    return np.asarray(points)
rows=[]
for job in json.loads((R/'protocols/jobs.json').read_text()):
    if not (R/'runs'/job['id']/'result.json').exists():continue
    initial=json.loads((R/'runs'/job['id']/'initial.json').read_text())['snapshot'];setq({s:initial['robot'][s]['qpos'] for s in ('left','right')})
    actual=tcp();expected=np.asarray([initial['robot'][s]['tcp'][:3] for s in ('left','right')]);error=float(np.max(np.abs(actual-expected)));assert error<1e-5,(job['id'],error)
    source={};source['baseline']=np.load(R/'predictions'/job['id']/'0/actions.npz')['actions']
    internal=R/'internal'/job['id']/'actions.npz'
    if internal.exists():source.update(dict(np.load(internal)))
    noise=R/'controls'/job['id']/'noise.json'
    if noise.exists():source['noise']=np.asarray(json.loads(noise.read_text())['actions'])
    out=R/'analyses/kinematics'/job['id'];out.mkdir(parents=True,exist_ok=True)
    traj={k:trajectory(a,initial) for k,a in source.items()};np.savez_compressed(out/'tcp.npz',**traj)
    objects={color:np.asarray(initial['objects'][role]['p']) for color,role in [('red','target'),('green','d1'),('blue','d2')]}
    metrics={}
    for mode,points in traj.items():
        ds={color:np.linalg.norm(points-p,axis=-1) for color,p in objects.items()}
        # Minimum over arms, average over common first 16 commands. Positive means closer to blue.
        signed=float(np.mean(np.min(ds['red'][:16],axis=-1)-np.min(ds['blue'][:16],axis=-1)))
        minima={color:float(d[:16].min()) for color,d in ds.items()}
        metrics[mode]=dict(signed_blue_preference_m=signed,closest_commanded_distance_m=minima,last_command_distances_m={color:d[min(15,len(d)-1)].tolist() for color,d in ds.items()})
    rows.append(dict(id=job['id'],policy=job['policy'],seed=job['seed'],layout=job['layout'],target=job['target'],initial_tcp_replay_max_abs=error,metrics=metrics))
(R/'analyses/kinematics.json').write_text(json.dumps(rows,indent=2));env.close_env();print('kinematic rows',len(rows))
