"""Passive pilot traces. No reward queries, additional renders, or RNG draws."""
import json
import os
import time
from pathlib import Path
import numpy as np


def plain(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, (list, tuple)): return [plain(x) for x in value]
    if isinstance(value, dict): return {str(k): plain(v) for k, v in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)): return value
    return str(value)


def joint_mapping(robot):
    result = {}
    for side in ('left','right'):
        if not hasattr(robot, side+'_arm_joints'):continue
        joints = getattr(robot,side+'_entity').get_active_joints()
        gj,mult,offset = getattr(robot,side+'_gripper')[0]
        result[side] = {'active_joint_names':[j.get_name() for j in joints],
                        'arm_indices':[joints.index(j) for j in getattr(robot,side+'_arm_joints')],
                        'gripper_index':joints.index(gj),'gripper_multiplier':float(mult),
                        'gripper_offset':float(offset),'gripper_scale':plain(getattr(robot,side+'_gripper_scale'))}
    return result


class Trace:
    def __init__(self, env, root, task, policy, seed, instruction):
        self.env = env
        self.meta = dict(task=task, policy=policy, seed=seed, run_id=Path(root).parent.name)
        os.environ["PILOT_RUN_ID"] = Path(root).parent.name
        self.path = Path(root) / policy / task / str(seed)
        self.path.mkdir(parents=True, exist_ok=True)
        self.file = (self.path / 'trace.jsonl').open('x')
        self.original = env.take_action
        self.physics_steps = 0
        env._pilot_tick = self.tick
        env._pilot_frame = self.frame
        self.video_frames = 0
        self.actions = 0
        self.decisions = 0
        self.write('start', task=task, policy=policy, seed=seed,
                   instruction=instruction, goal=getattr(env, 'GOAL', None),
                   initial_positions=getattr(env, '_p0', None),
                   target_role=getattr(env,'TARGET','target'),
                   gripper_links=list(getattr(env.robot,'gripper_name',[])),
                   timestep=float(env.scene.get_timestep()),
                   articulation_mapping=joint_mapping(env.robot))
        def wrapped(*args, **kwargs):
            self.write('action_before', command=args, keywords=kwargs)
            result = self.original(*args, **kwargs)
            self.actions += 1
            self.write('action_after')
            return result
        env.take_action = wrapped

    def frame(self, rgb):
        frame_index = self.video_frames
        self.video_frames += 1
        self.write("video_frame", frame_index=frame_index)
        if self.meta['policy'] == 'Motus' and self.actions % 2 == 0:
            from PIL import Image
            folder = self.path/'executed_frames'/str(frame_index)
            folder.mkdir(parents=True, exist_ok=True)
            for name, value in rgb.items():
                if isinstance(value,dict) and 'rgb' in value:
                    Image.fromarray(np.asarray(value['rgb'],dtype=np.uint8)).save(folder/(name+'.png'))

    def tick(self):
        self.physics_steps += 1
        if self.physics_steps % 10 == 0:
            self.write("physics")

    def snapshot(self):
        e = self.env
        objects = {}
        for role, actor in getattr(e, '_actors', {}).items():
            p = actor.get_pose()
            objects[role] = {'p': plain(p.p), 'q': plain(p.q)}
        robot = {}
        for side in ('left', 'right'):
            entity = getattr(e.robot, side + '_entity', None)
            if entity is not None:
                robot[side] = {'qpos': plain(entity.get_qpos()), 'qvel': plain(entity.get_qvel())}
        contacts = []
        ids = {v.actor.global_id:k for k,v in getattr(e, '_actors', {}).items()}
        for contact in e.scene.get_contacts():
            entities = [b.entity for b in contact.bodies]
            if any(x.global_id in ids for x in entities) and contact.points:
                contacts.append({'entities':[ids.get(x.global_id, x.name) for x in entities],
                                 'impulse_sum':sum(float(np.linalg.norm(p.impulse)) for p in contact.points),
                                 'points':len(contact.points)})
        for side in ('left','right'):
            robot[side]['eef'] = plain(getattr(e.robot, 'get_'+side+'_ee_pose')())
            robot[side]['tcp'] = plain(getattr(e.robot, 'get_'+side+'_tcp_pose')())
        return {'objects': objects, 'robot': robot, 'contacts':contacts,
                'physics_steps':self.physics_steps, 'sim_seconds':self.physics_steps*float(e.scene.get_timestep()),
                'native_action_counter': getattr(e, 'take_action_cnt', None),
                'stage': getattr(e, 'stage', None), 'eval_success': bool(getattr(e, 'eval_success', False))}

    def write(self, event, **extra):
        if event in ('start', 'decision_before', 'decision_after', 'end') and getattr(self.env, '_actors', {}):
            from envs._placement_judge import world_bounds
            extra['collision_bounds'] = {k:plain(world_bounds(v)) for k,v in self.env._actors.items()}
            extra['max_displacements'] = plain(getattr(self.env, '_maxdisp', {}))
        row = dict(event=event, wall_time=time.time(), action_index=self.actions,
                   decision_index=self.decisions, **self.snapshot(), **extra)
        self.file.write(json.dumps(plain(row), allow_nan=False) + '\n')
        self.file.flush()

    def decision_before(self, observation=None):
        os.environ['PILOT_META'] = json.dumps(dict(self.meta, decision=self.decisions))
        if observation is not None:
            from PIL import Image
            folder=self.path/'observations'/str(self.decisions)
            folder.mkdir(parents=True, exist_ok=True)
            for name, value in observation.get('observation',{}).items():
                if isinstance(value,dict) and 'rgb' in value:
                    Image.fromarray(np.asarray(value['rgb'],dtype=np.uint8)).save(folder/(name+'.png'))
        self.write('decision_before')

    def decision_after(self):
        self.write('decision_after')
        self.decisions += 1

    def close(self, success, feedback=None):
        self.write('end', success=bool(success), feedback=feedback)
        self.env.take_action = self.original
        self.env._pilot_tick = None
        self.env._pilot_frame = None
        self.file.close()
