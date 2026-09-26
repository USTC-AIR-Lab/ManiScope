"""Model-level target bounds; execution subdivisions do not consume model calls."""
import math
VERSION='eef_adaptive_v4_2_orientation_tracking'
LIMITS={'transit':(.45,90.),'approach':(.12,30.),'contact':(.03,10.),'recover':(.03,0.),'gripper':(0.,0.)}
def angle(q,r):return 2*math.acos(min(1.,abs(sum(a*b for a,b in zip(q,r)))))
def slerp(q,r,t):
 dot=sum(a*b for a,b in zip(q,r))
 if dot<0:r=[-a for a in r];dot=-dot
 theta=math.acos(min(1.,dot))
 if theta<1e-8:return q[:]
 return [(math.sin((1-t)*theta)*a+math.sin(t*theta)*b)/math.sin(theta) for a,b in zip(q,r)]
def tcp(p,q):
 w,x,y,z=q
 return [p[0]+.12*(1-2*(y*y+z*z)),p[1]+.24*(x*y+w*z),p[2]+.24*(x*z-w*y)]
def bound(a,state):
 phase=a.get('phase','approach')
 if phase not in LIMITS:raise ValueError('invalid phase')
 old=state[a['arm']+'_endpose'];q=old[3:7];norm=math.sqrt(sum(x*x for x in q));q=[x/norm for x in q]
 if phase=='gripper':return {**a,'position':old[:3],'quaternion_wxyz':q,'interface_version':VERSION}
 if phase=='recover':
  a={**a,'quaternion_wxyz':q}
 dist,deg=LIMITS[phase]
 if math.dist(old[:3],a['position'])>dist+1e-6:raise ValueError(f'{phase} target exceeds {dist}m envelope')
 if math.degrees(angle(q,a['quaternion_wxyz']))>deg+1e-4:raise ValueError(f'{phase} rotation exceeds {deg} degrees')
 return {**a,'gripper':state.get(a['arm']+'_gripper',a['gripper']),'interface_version':VERSION}
