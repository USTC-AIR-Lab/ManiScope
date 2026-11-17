"""Task-specific video readout for the colored-cube validation fixture.
Reports visible gripper proximity, not intended goal or future task success.
"""
import json
from pathlib import Path
import numpy as np
import cv2
from paths import R
def components(mask,min_area):
    n,lab,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'),8)
    keep=[i for i in range(1,n) if stats[i,cv2.CC_STAT_AREA]>=min_area]
    return np.isin(lab,keep)
def readout(frame):
    im=np.asarray(frame,dtype=np.float32)[12:252]
    r,g,b=im.transpose(2,0,1);h,w=r.shape;yy,xx=np.mgrid[:h,:w]
    area=(yy>=70)&(yy<=215)
    dark=(im.max(-1)<.35)&(im.max(-1)-im.min(-1)<.15)&area
    dark=components(dark,25)
    if not dark.any():return dict(label='none',distances_px={},reason='no visible dark gripper region')
    dt=cv2.distanceTransform((~dark).astype('uint8'),cv2.DIST_L2,cv2.DIST_MASK_PRECISE)
    colors={'red':(r>.4)&(r>g*1.5)&(r>b*1.5),'green':(g>.35)&(g>r*1.4)&(g>b*1.25),'blue':(b>.4)&(b>r*1.3)&(b>g*1.12)}
    distances={};areas={}
    for color,mask in colors.items():
        mask=components(mask&area,35);areas[color]=int(mask.sum())
        if mask.any():distances[color]=float(np.min(dt[mask]))
    ordered=sorted((d,c) for c,d in distances.items())
    if len(ordered)!=3:label='ambiguous';reason='missing or occluded colored object'
    elif ordered[0][0]>12:label='none';reason='no close visible approach'
    elif ordered[1][0]-ordered[0][0]<6:label='ambiguous';reason='multiple candidate targets'
    else:label=ordered[0][1];reason='unique visible gripper proximity'
    return dict(label=label,distances_px=distances,color_pixels=areas,reason=reason)
rows=[]
for job in json.loads((R/'protocols/jobs.json').read_text()):
    if job['policy']!='Motus':continue
    f=R/'predictions'/job['id']/'0/future.npz'
    if not f.exists():continue
    frames=np.load(f)['frames'][0].transpose(1,2,3,0);all_frames=[readout(x) for x in frames]
    rows.append(dict(id=job['id'],seed=job['seed'],layout=job['layout'],target=job['target'],last_frame=all_frames[-1],frames=all_frames,correct=all_frames[-1]['label']==job['target'],method='Fixed RGB rule, final predicted head frame after 16 actions; inspect all contact sheets.'))
(R/'analyses').mkdir(exist_ok=True);(R/'analyses/future_targets_rule.json').write_text(json.dumps(rows,indent=2));print('future readouts',len(rows))
