"""Geometry/contact guards for placement predicates; no model or control access."""
import itertools
import numpy as np


def world_bounds(actor):
    # Collision geometry is authoritative; metadata can use a displaced origin.
    boxes = [np.asarray(c.compute_global_aabb_tight(), dtype=float)
             for c in actor.actor.get_components() if hasattr(c, 'compute_global_aabb_tight')]
    if boxes:
        return np.min([b[0] for b in boxes], axis=0), np.max([b[1] for b in boxes], axis=0)
    cfg=actor.config
    half=np.asarray(cfg['extents'],dtype=float)*np.asarray(cfg.get('scale',1),dtype=float)/2
    center=np.asarray(cfg.get('center',[0,0,0]),dtype=float)*np.asarray(cfg.get('scale',1),dtype=float)
    corners=center+np.array(list(itertools.product((-1,1),repeat=3)))*half
    pose=actor.get_pose().to_transformation_matrix()
    points=corners@pose[:3,:3].T+pose[:3,3]
    return points.min(axis=0),points.max(axis=0)


def touches(scene,a,b):
    ids={a.actor.global_id,b.actor.global_id}
    for contact in scene.get_contacts():
        if {c.entity.global_id for c in contact.bodies}==ids and contact.points:
            return True
    return False


def slow(actor):
    for component in actor.actor.get_components():
        if hasattr(component,'linear_velocity'):
            return bool(np.linalg.norm(component.linear_velocity)<0.08 and
                    np.linalg.norm(component.angular_velocity)<1.0)
    return True  # Static references have no dynamic velocity component.


def supported_placement(scene,target,reference,kind):
    """Reject hovering, outside-container origins and unsupported placements.

    Bounding metadata describes the outer shape, not a certified inner cavity.
    Contact and the rim-height test reduce false positives but do not replace
    a per-asset cavity annotation for unusual concave/handled containers.
    """
    try:
        lo,hi=world_bounds(reference);tlo,thi=world_bounds(target)
        if not touches(scene,target,reference) or not slow(target):
            return False
        if kind=='in':
            pose=reference.get_pose().to_transformation_matrix();rot=pose[:3,:3]
            vertical=int(np.argmax(np.abs(rot[2,:])))
            if abs(rot[2,vertical])<0.9:
                return False  # A tipped container is not an upright receptacle.
            cfg=reference.config;scale=np.asarray(cfg.get('scale',1),dtype=float)
            center=np.asarray(cfg.get('center',[0,0,0]))*scale
            half=np.asarray(cfg['extents'])*scale/2
            local=rot.T@((tlo+thi)/2-pose[:3,3])
            horizontal=[k for k in range(3) if k!=vertical]
            if any(abs(local[k]-center[k])>=half[k]-0.003 for k in horizontal):
                return False
            return bool(tlo[2]<hi[2]-0.003 and tlo[2]>=lo[2]-0.015 and thi[2]>lo[2])
        if kind in ('on','stack'):
            return bool(tlo[2]>=lo[2]-0.01 and tlo[2]<=hi[2]+0.015)
        return False
    except (AttributeError,KeyError,ValueError,TypeError):
        return False
