"""Trajectory pacing and contact feedback using robot state/physical contacts only."""
import numpy as np
import time

def hold(env):
 for side in ('left','right'):
  q=getattr(env.robot,'get_'+side+'_arm_real_jointState')()[:-1]
  env.robot.set_arm_joints(q,np.zeros(len(q)),side)

def install(env):
 if hasattr(env,'_fine_control'):return
 env._fine_control={'phase':'approach','peak_contact_force_n':0.,'stopped':False,'reason':None}
 robot_ids=set()
 for side in ('left','right'):
  for link in getattr(env.robot,side+'_entity').get_links():robot_ids.add(link.entity.global_id)
 fingers=set(env.robot.gripper_name)
 for side in ('left','right'):
  name=side+'_plan_path';original=getattr(env.robot,name)
  def paced(*args,_original=original,**kwargs):
   result=_original(*args,**kwargs)
   if result.get('status')!='Success':return result
   if env._fine_control["phase"]=="transit":return result
   pos=np.asarray(result['position']);n=len(pos)
   if n<2:return result
   # Twice as many physics targets and half feed-forward velocity.
   x=np.linspace(0,n-1,2*n-1);out=dict(result)
   for k in ('position','velocity'):
    v=np.asarray(result[k]);out[k]=np.stack([np.interp(x,np.arange(n),v[:,i]) for i in range(v.shape[1])],axis=1)
   out['velocity']*=.5
   return out
  setattr(env.robot,name,paced)
 def contact_guard():
  state=env._fine_control;dt=float(env.scene.get_timestep())
  if time.monotonic() >= getattr(env,'_soft_eval_deadline',float('inf')):
   state.update(stopped=True,reason='evaluation_wall_budget')
   for side in ('left','right'):
    q=getattr(env.robot,'get_'+side+'_arm_real_jointState')()[:-1]
    env.robot.set_arm_joints(q,np.zeros(len(q)),side)
   return True
  state['guard_steps']=state.get('guard_steps',0)+1
  for c in env.scene.get_contacts():
   a,b=[body.entity for body in c.bodies]
   ar=a.global_id in robot_ids;br=b.global_id in robot_ids
   if ar==br:continue
   link=a if ar else b
   impulse=sum(float(np.linalg.norm(point.impulse)) for point in c.points)
   force=impulse/dt;state['peak_contact_force_n']=max(force,state['peak_contact_force_n'])
   # Intentional finger contact allowed only in explicit contact/gripper phases.
   threshold=2.5 if link.name in fingers else 5.
   pair=tuple(sorted((a.global_id,b.global_id)))
   existing_grasp=link.name in fingers and pair in getattr(env,'_fine_initial_contacts',set())
   recovery_allowed=False
   baseline=getattr(env,'_fine_initial_forces',{}).get(pair)
   if state.get('recovery_requested') and baseline is not None and baseline<=20.:
    # Only contacts present at the start get a bounded chance to disengage.
    # Stop force growth or a prolonged contact that is not easing; new contacts
    # still use normal thresholds. There is no exemption for arbitrary transport.
    ceiling=min(20.,max(threshold,baseline*1.15+1.))
    improving=force<=max(threshold,baseline*.9)
    recovery_allowed=force<=ceiling and (state['guard_steps']<=160 or improving)
    if recovery_allowed and force>threshold:
     state['recovery_contact_allowed']=True
   unsafe=force>threshold and not existing_grasp and (link.name not in fingers or state['phase'] in ('transit','approach','recover'))
   # Recovery must also monitor existing grasp contacts rather than exempt them.
   if state.get('recovery_requested') and force>threshold:
    # Opening must still release an ordinary firm finger grasp. The force cap
    # protects exceptional wrist/arm recovery, not normal finger release.
    releasing_grasp=state['phase']=='gripper' and existing_grasp
    if releasing_grasp:
     release_ceiling=max(threshold,(baseline or 0.)*(1.5 if state['guard_steps']<=8 else 1.3)+2.)
     unsafe=force>release_ceiling
    else:
     unsafe=True
   if unsafe and not recovery_allowed:
    state.update(stopped=True,reason='unexpected_robot_contact',contact_link=link.name,contact_force_n=force,initial_contact_force_n=baseline,was_initial_contact=baseline is not None)
    # Hold measured joint positions instead of retaining the previous target.
    for side in ('left','right'):
     q=getattr(env.robot,'get_'+side+'_arm_real_jointState')()[:-1]
     env.robot.set_arm_joints(q,np.zeros(len(q)),side)
    return True
  return False
 env._fine_step_guard=contact_guard

def begin(env,phase,action=None,measured=None):
 contacts=env.scene.get_contacts()
 env._fine_initial_contacts={tuple(sorted(body.entity.global_id for body in c.bodies)) for c in contacts}
 env._fine_initial_forces={}
 if contacts:
  dt=float(env.scene.get_timestep())
  for c in contacts:
   pair=tuple(sorted(body.entity.global_id for body in c.bodies))
   env._fine_initial_forces[pair]=env._fine_initial_forces.get(pair,0.)+sum(float(np.linalg.norm(p.impulse)) for p in c.points)/dt
 opening=bool(action and measured and phase=='gripper' and action['gripper']>measured.get(action['arm']+'_gripper_actual',measured[action['arm']+'_gripper'])+.01)
 env._fine_control={'phase':phase,'peak_contact_force_n':0.,'stopped':False,'reason':None,
                    'recovery_requested':opening or phase=='recover','recovery_contact_allowed':False,'guard_steps':0}
