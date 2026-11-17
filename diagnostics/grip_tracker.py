"""Per-object gripper-state tracking: what kind of contact each object received (grasp / push / brush).

Closure is read from the physical finger position (envs/_robot_state.gripper_aperture, 1 = fully open,
0 = fully closed; an object held between the fingers stops them part-way) and counts when the aperture is
<= 0.9: a gripper that has closed part of the way on an object already shows the intent to grasp it.
Alternative sensors and thresholds are recorded alongside, see VARIANTS.

Sampled once after every environment action. For each tracked object, arm and variant:
  pinch     the object is in contact with at least two distinct gripper links of that arm, and that arm's gripper
            is closed according to the variant's sensor and threshold
A pinch run is a maximal sequence of consecutive samples with pinch on the same arm.

Class of an object over the episode, most severe first:
  grasp   some pinch run lasts >= MIN_RUN samples and (if the variant requires carry) the object moves >= CARRY_M
          within that run
  push    not grasp, and its maximum displacement from the initial pose is >= PUSH_M
  brush   not grasp or push, and some robot link touched it at some sample
  none    never touched and never displaced >= PUSH_M

`grasp` requires all of the conditions, so counting non-target grasps gives a lower bound on wrong selections:
a policy that closes on a non-target and drops it within MIN_RUN samples, or holds it with one finger against
the table, is classed as push or brush.
"""
import numpy as np

VERSION = 3
MIN_RUN = 3
CARRY_M = 0.02
PUSH_M = 0.05
PRIMARY = "ap0.9"
# name: (sensor, closed if value <= threshold, carry required)
VARIANTS = {
    "ap0.9": ("aperture", 0.9, True),
    "ap0.8": ("aperture", 0.8, True),
    "ap0.95": ("aperture", 0.95, True),
    "ap0.9_nocarry": ("aperture", 0.9, False),
    "cmd0.8": ("command", 0.8, True),     # commanded gripper value instead of finger position
}
SEVERITY = {"none": 0, "brush": 1, "push": 2, "grasp": 3}


class GripTracker:
    def __init__(self, env, actors):
        """actors: {role: actor wrapper with get_pose(), get_name() and .actor (the sapien entity)}"""
        self.env = env
        self.actors = dict(actors)
        robot = env.robot
        self.side_links = {}
        self.ap_index = {}
        for side in ("left", "right"):
            links = set(getattr(robot, side + "_fix_gripper_name", []) or [])
            for joint, _, _ in getattr(robot, side + "_gripper"):
                links.add(joint.child_link.get_name())
            self.side_links[side] = links
            entity = getattr(robot, side + "_entity")
            self.ap_index[side] = entity.get_active_joints().index(getattr(robot, side + "_gripper")[0][0])
        self.robot_links = set()
        for ent in (robot.left_entity, robot.right_entity):
            self.robot_links.update(l.get_name() for l in ent.get_links())
        # Match contacts by entity identity, not by name: two objects built from the same model share a name
        # (e.g. the two tea boxes), and matching by name credits both objects' contacts to one of them.
        self.names = {role: a.get_name() for role, a in self.actors.items()}
        self.by_id = {self._eid(getattr(a, "actor", a)): role for role, a in self.actors.items()}
        if len(self.by_id) != len(self.actors):
            raise ValueError("tracked objects do not have distinct entities")
        self.p0 = {r: self._pos(r) for r in self.actors}
        self.n = 0
        self.state = {}
        for r in self.actors:
            self.state[r] = dict(maxdisp=0.0, maxrise=0.0, touched=False, first_touch=None,
                                 min_cmd_two_fingers=1.0, min_ap_two_fingers=1.0,
                                 v={k: dict(grasp=False, first_grasp=None, grasp_arm=None, pinch_samples=0,
                                            best_run_len=0, best_run_move=0.0,
                                            run={s: None for s in ("left", "right")}) for k in VARIANTS})

    @staticmethod
    def _eid(entity):
        return int(entity.per_scene_id)

    def _pos(self, role):
        return np.asarray(self.actors[role].get_pose().p, dtype=float).copy()

    def _cmd(self, side):
        return float(getattr(self.env.robot, side + "_gripper_val"))

    def _aperture(self, side):
        """Same computation as envs/_robot_state.gripper_aperture, with the joint index cached."""
        robot = self.env.robot
        _, multiplier, offset = getattr(robot, side + "_gripper")[0]
        q = (float(getattr(robot, side + "_entity").get_qpos()[self.ap_index[side]]) - offset) / multiplier
        closed, opened = map(float, getattr(robot, side + "_gripper_scale"))
        return min(1.0, max(0.0, (q - closed) / (opened - closed)))

    def sample(self):
        self.n += 1
        touching = {r: set() for r in self.actors}
        for c in self.env.scene.get_contacts():
            ea, eb = c.bodies[0].entity, c.bodies[1].entity
            for obj, other in ((ea, eb), (eb, ea)):
                role = self.by_id.get(self._eid(obj))
                if role is not None and other.name in self.robot_links and len(c.points) > 0:
                    touching[role].add(other.name)
        sensor = {s: dict(command=self._cmd(s), aperture=self._aperture(s)) for s in ("left", "right")}
        for role, st in self.state.items():
            p = self._pos(role)
            st["maxdisp"] = max(st["maxdisp"], float(np.linalg.norm(p - self.p0[role])))
            st["maxrise"] = max(st["maxrise"], float(p[2] - self.p0[role][2]))
            if touching[role] and not st["touched"]:
                st["touched"], st["first_touch"] = True, self.n
            for side in ("left", "right"):
                two_fingers = len(touching[role] & self.side_links[side]) >= 2
                if two_fingers:
                    st["min_cmd_two_fingers"] = min(st["min_cmd_two_fingers"], sensor[side]["command"])
                    st["min_ap_two_fingers"] = min(st["min_ap_two_fingers"], sensor[side]["aperture"])
                for k, v in st["v"].items():
                    kind, thr, carry = VARIANTS[k]
                    pinch = two_fingers and sensor[side][kind] <= thr
                    run = v["run"][side]
                    if pinch:
                        v["pinch_samples"] += 1
                        if run is None:
                            run = v["run"][side] = dict(start=self.n, p=p, length=0, move=0.0)
                        run["length"] += 1
                        run["move"] = max(run["move"], float(np.linalg.norm(p - run["p"])))
                        v["best_run_len"] = max(v["best_run_len"], run["length"])
                        v["best_run_move"] = max(v["best_run_move"], run["move"])
                        if (run["length"] >= MIN_RUN and (not carry or run["move"] >= CARRY_M)
                                and not v["grasp"]):
                            v["grasp"], v["first_grasp"], v["grasp_arm"] = True, run["start"], side
                    else:
                        v["run"][side] = None

    def _cls(self, st, k):
        if st["v"][k]["grasp"]:
            return "grasp"
        if st["maxdisp"] >= PUSH_M:
            return "push"
        return "brush" if st["touched"] else "none"

    def summary(self):
        out = {}
        for role, st in self.state.items():
            v = st["v"][PRIMARY]
            out[role] = dict(cls=self._cls(st, PRIMARY), cls_by_variant={k: self._cls(st, k) for k in VARIANTS},
                             maxdisp=round(st["maxdisp"], 4), maxrise=round(st["maxrise"], 4),
                             first_touch=st["first_touch"], first_grasp=v["first_grasp"], grasp_arm=v["grasp_arm"],
                             pinch_samples=v["pinch_samples"], best_run_len=v["best_run_len"],
                             best_run_move=round(v["best_run_move"], 4),
                             min_cmd_two_fingers=round(st["min_cmd_two_fingers"], 3),
                             min_ap_two_fingers=round(st["min_ap_two_fingers"], 3))
        return dict(samples=self.n, objects=out, names=self.names,
                    params=dict(VERSION=VERSION, MIN_RUN=MIN_RUN, CARRY_M=CARRY_M, PUSH_M=PUSH_M, PRIMARY=PRIMARY,
                                VARIANTS={k: list(v) for k, v in VARIANTS.items()}))
