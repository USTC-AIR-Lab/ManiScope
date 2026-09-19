"""Interpolate one model target with measured tracking and contact stops."""
import math
import numpy as np
from .motion_math import slerp,angle,tcp
from . import fine_control

def execute(env,action,state):
 side=action['arm'];phase=action.get('phase','approach');start=state[side+'_endpose'];target=action['position'];q=action['quaternion_wxyz'];q0=np.asarray(start[3:7]);q0=q0/np.linalg.norm(q0)
 # Local interpolation points are not API actions. Closer to table -> denser points.
 near=min(tcp(start[:3],q0)[2],tcp(target,q)[2])<.90
 spacing=.03 if phase=='transit' and not near else (.003 if phase in ('contact','recover') else .01)
 count=max(1,math.ceil(math.dist(start[:3],target)/spacing),math.ceil(math.degrees(angle(q0,q))/5))
 if phase=='gripper':count=1
 fine_control.begin(env,phase,action,state);executed=0;reason=None;tracking_error=None
 for i in range(1,count+1):
  t=i/count;p=[a+t*(b-a) for a,b in zip(start[:3],target)];rot=slerp(q0.tolist(),q,t);values=[]
  for arm in ('left','right'):
   # Use observed other arm pose; no unobserved goal/task information.
   values.extend(p+rot if arm==side else state[arm+'_endpose']);values.append(action['gripper'] if arm==side else state[arm+'_gripper'])
  env.take_action(np.asarray(values),action_type='ee');executed+=1
  if env.eval_success or env._fine_control['stopped']:break
  obs=env.get_obs();measured=np.asarray(obs['endpose'][side+'_endpose'])
  position_error=float(np.linalg.norm(measured[:3]-np.asarray(p)))
  measured_q=measured[3:7]/np.linalg.norm(measured[3:7])
  orientation_error=math.degrees(angle(rot,measured_q.tolist()))
  tracking_error={'position_m':position_error,'orientation_deg':orientation_error}
  if position_error>.025 or orientation_error>10.+1e-4:
   fine_control.hold(env)
   reason=('tracking_residual_over_2.5cm' if position_error>.025 else 'tracking_orientation_residual_over_10deg');break
 return {'planned_segments':count,'executed_segments':executed,'tracking_stop':reason,'last_segment_tracking_error':tracking_error}
