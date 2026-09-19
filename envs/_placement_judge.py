"""Geometry/contact guards for placement predicates; no model or control access."""
import itertools
import numpy as np


# 110_basket collision meshes: body/rim maxima along local +Y, excluding handles.
# Coordinates are unscaled asset units, model IDs 0..3. See basket_rim_audit.json.
BASKET_BODY_RIM_Y = (1.0333, 1.0416, 0.9880, 1.1079)


def container_rim_world_height(reference):
    cfg = reference.config
    if cfg.get('_placement_asset') != '110_basket':
        return None
    mid = int(cfg['_placement_model_id'])
    if mid not in range(len(BASKET_BODY_RIM_Y)):
        raise ValueError('Unannotated basket model')
    scale = np.broadcast_to(np.asarray(cfg.get('scale', 1), dtype=float), (3,))
    center = np.asarray(cfg['center'], dtype=float)
    half = np.asarray(cfg['extents'], dtype=float) / 2
    # A world-height upper bound on the whole rim tolerates small basket tilts.
    corners = np.array([[center[0] + x * half[0], BASKET_BODY_RIM_Y[mid],
                         center[2] + z * half[2]] for x, z in itertools.product((-1, 1), repeat=2)]) * scale
    pose = reference.get_pose().to_transformation_matrix()
    if pose[2, 1] < 0.9:
        raise ValueError('Basket opening is not upright')
    return float((corners @ pose[:3, :3].T + pose[:3, 3])[:, 2].max())


def world_bounds(actor):
    # Collision geometry is authoritative; metadata can use a displaced origin.
    entity=actor.actor
    components=(entity.get_components() if hasattr(entity,'get_components') else
                entity.get_links() if hasattr(entity,'get_links') else [])
    boxes=[]
    for component in components:
        if not hasattr(component,'compute_global_aabb_tight'):
            continue
        if hasattr(component,'get_collision_shapes') and not component.get_collision_shapes():
            continue
        boxes.append(np.asarray(component.compute_global_aabb_tight(),dtype=float))
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
            rim = container_rim_world_height(reference)
            top = hi[2] if rim is None else min(hi[2], rim)
            return bool(tlo[2]<top-0.003 and tlo[2]>=lo[2]-0.015 and thi[2]>lo[2])
        if kind in ('on','stack'):
            return bool(tlo[2]>=lo[2]-0.01 and tlo[2]<=hi[2]+0.015)
        return False
    except (AttributeError,KeyError,ValueError,TypeError):
        return False


def grasped_clearance(env, actor, initial_bottom, clearance):
    """Current collision geometry must be off its support and touch a gripper."""
    try:
        gap = world_bounds(actor)[0][2] - initial_bottom
        target_id=actor.actor.global_id
        names=set(env.robot.gripper_name)
        held=False
        for contact in env.scene.get_contacts():
            if not contact.points:
                continue
            a,b=(body.entity for body in contact.bodies)
            if ((a.global_id==target_id and b.name in names) or
                (b.global_id==target_id and a.name in names)):
                held=True
                break
        # 诊断要分开记：判据要的是「**被夹着的同时**离地多少」。
        # 只记 gap 不区分是否夹着，物体被撞飞时也会记到很大的值，
        # 反而看不出失败原因（grab_dumbbell 上就是这样：失败的位移比成功的还大）。
        if gap > getattr(env, "_max_clearance", -1e9):
            env._max_clearance = float(gap)
            env._clearance_thr = float(clearance)
        if held and gap > getattr(env, "_max_clearance_held", -1e9):
            env._max_clearance_held = float(gap)
        if gap <= clearance:
            return False
        return bool(held)
    except (AttributeError,KeyError,ValueError,TypeError):
        return False
