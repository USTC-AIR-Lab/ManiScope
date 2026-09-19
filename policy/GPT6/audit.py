"""Evaluation-only telemetry; never passed to the model or used for control."""
import json
from pathlib import Path
import numpy as np
import cv2
from envs._placement_judge import world_bounds, touches, slow, supported_placement
from .robot_state import gripper_aperture


def install(env):
    if hasattr(env, "_gpt6_judge_trace"):
        return
    env._gpt6_judge_trace = {}
    actors=getattr(env,'_actors',None) or getattr(env,'objects',None) or {}
    env._gpt6_initial_bottom={}
    for name,obj in actors.items():
        try:env._gpt6_initial_bottom[name]=float(world_bounds(obj)[0][2])
        except Exception:pass
    for name in ("_selected_right", "_refs_stayed_put", "_goal_ok", "_grippers_open", "check_success"):
        if not hasattr(env, name):
            continue
        original = getattr(env, name)
        def observed(*args, _original=original, _name=name, **kwargs):
            result = _original(*args, **kwargs)
            key = _name + (":" + json.dumps(args[0], sort_keys=True) if _name == "_goal_ok" and args else "")
            env._gpt6_judge_trace[key] = bool(result)
            return result
        setattr(env, name, observed)


def capture(env, model, obs, phase):
    root = model.audit_dir
    root.mkdir(parents=True, exist_ok=True)
    record = {'call': model.calls, 'phase': phase, 'seed': getattr(env, 'seed', None),
              'env_success': bool(env.eval_success), 'step': int(env.take_action_cnt), 'judge_trace':dict(getattr(env,'_gpt6_judge_trace',{})),
              'stage':int(getattr(env,'stage',0)), 'audit_version':4}
    record['gripper_state']={side:{'commanded':float(obs['endpose'][side+'_gripper']),
        'actual_normalized':gripper_aperture(env.robot,side)} for side in ('left','right')}
    if all(hasattr(env, x) for x in ('_actors','_p0','_maxdisp','GOAL')):
        poses = {k: np.asarray(v.get_pose().p).tolist() for k,v in env._actors.items()}
        record.update(positions=poses, initial_positions={k:np.asarray(v).tolist() for k,v in env._p0.items()},
                      max_displacement={k:float(v) for k,v in env._maxdisp.items()},
                      selected_right=env._gpt6_judge_trace.get("_selected_right"), refs_stayed_put=env._gpt6_judge_trace.get("_refs_stayed_put"),
                      goal_ok=env._gpt6_judge_trace.get("_goal_ok:"+json.dumps(env.GOAL,sort_keys=True)), grippers_open=env._gpt6_judge_trace.get("_grippers_open"))
        if env.GOAL.get('type') in ('in','on','stack'):
            target=env._actors[env.TARGET];ref=env._actors[env.GOAL['ref']]
            try:
                record['placement_geometry']={'target_bounds':[v.tolist() for v in world_bounds(target)],
                    'reference_bounds':[v.tolist() for v in world_bounds(ref)],'touches':touches(env.scene,target,ref),
                    'slow':slow(target),'guard_pass':supported_placement(env.scene,target,ref,env.GOAL['type'])}
            except Exception as exc:
                record['geometry_error']=type(exc).__name__
        if env.GOAL.get('type') == 'in':
            p=np.asarray(poses[env.TARGET]); q=np.asarray(poses[env.GOAL['ref']])
            record.update(xy_distance=float(np.linalg.norm(p[:2]-q[:2])), target_minus_ref_z=float(p[2]-q[2]),
                          target_displacement=float(np.linalg.norm(p-env._p0[env.TARGET])),
                          reference_max_allowed=float(env.REF_MOVE_EPS))
    elif hasattr(env, 'stapler') and hasattr(env, 'pad'):
        record['cup_minus_pad']=(env.stapler.get_pose().p-env.pad.get_pose().p).tolist()
        record['grippers_open']=bool(env.robot.is_left_gripper_open() and env.robot.is_right_gripper_open())
    actors = getattr(env, '_actors', None) or getattr(env, 'objects', None) or {}
    if not actors:
        actors = {name:getattr(env,name) for name in ('object','target_object','bottle','stapler','pad','cube_on_plate','cube_on_table','bell') if hasattr(getattr(env,name,None),'get_pose')}
    try:
        record['actor_positions']={name:obj.get_pose().p.tolist() for name,obj in actors.items()}
        ids={obj.actor.global_id:name for name,obj in actors.items() if hasattr(getattr(obj,'actor',None),'global_id')}
        grasp=[]
        contact_details=[]
        for contact in env.scene.get_contacts():
            for side in (0,1):
                entity=contact.bodies[side].entity;other=contact.bodies[1-side].entity
                if entity.global_id in ids and other.name in env.robot.gripper_name:
                    grasp.append(ids[entity.global_id])
                    contact_details.append({'role':ids[entity.global_id], 'robot_link':other.name,
                        'point_count':len(contact.points),
                        'force_n':sum(float(np.linalg.norm(p.impulse)) for p in contact.points)/float(env.scene.get_timestep())})
        # Legacy field means collision pairs; it alone does not prove loaded contact.
        record['gripper_contact_roles']=sorted(set(grasp))
        record['gripper_contact_details']=contact_details
        record['gripper_touch_roles']=sorted({x['role'] for x in contact_details if x['point_count']>0})
        record['gripper_loaded_roles']=sorted({x['role'] for x in contact_details if x['force_n']>0.01})
        record['collision_bounds']={}
        record['bottom_clearance_from_first_observation']={}
        for name,obj in actors.items():
            try:
                lo,hi=world_bounds(obj);record['collision_bounds'][name]=[lo.tolist(),hi.tolist()]
                if name in getattr(env,'_gpt6_initial_bottom',{}):
                    record['bottom_clearance_from_first_observation'][name]=float(lo[2]-env._gpt6_initial_bottom[name])
            except Exception:pass
    except Exception as exc:
        record['contact_audit_error']=type(exc).__name__
    folder=root/f'{model.calls:03d}_{phase}'
    folder.mkdir(exist_ok=True)
    for name in ('head_camera','left_camera','right_camera'):
        cv2.imwrite(str(folder/(name+'.png')),cv2.cvtColor(np.asarray(obs['observation'][name]['rgb']),cv2.COLOR_RGB2BGR))
    record['frame_dir']=folder.name
    with (root/'checks.jsonl').open('a') as f: f.write(json.dumps(record)+'\n')
