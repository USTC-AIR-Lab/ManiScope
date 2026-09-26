"""Declarative evaluation-scene engine. SPEC defines actor roles and geometry; GOAL defines physical predicates and expert actions. Success combines target-selection guards, the physical goal, and reference stability. Moved targets must exceed the configured displacement threshold and distractor motion; press/beat goals use their contact-location conditions. Sequence stages advance monotonically. Lifting, placement, containment, relations, tool use and articulated states have task-specific predicates. Tools are neither distractors nor fixed references. See each predicate implementation for exact thresholds and exceptions."""
from ._base_task import Base_Task
from ._placement_judge import supported_placement, world_bounds, grasped_clearance
from .utils import *
from .utils.create_actor import UnStableError
import os
from copy import deepcopy
import numpy as np
import sapien


# Object footprints for overlap rejection. add_prohibit_area records regions but does not itself prevent subsequent overlapping samples.


_EXT_CACHE = {}


def _model_radius(model, mid):
    """Estimate horizontal footprint radius from asset extents and scale; use a conservative fallback if metadata is unavailable."""
    key = (model, int(mid))
    if key in _EXT_CACHE:
        return _EXT_CACHE[key]
    r = 0.06
    try:
        import json as _json
        f = os.path.join("assets", "objects", model, "model_data%d.json" % int(mid))
        d = _json.load(open(f, encoding="utf-8"))
        e, sc = d.get("extents"), d.get("scale")
        if e and sc:
            sc = sc if isinstance(sc, list) else [sc] * 3
            dims = sorted(abs(float(e[i]) * float(sc[i])) for i in range(3))
            # Use half the longest extent conservatively; smaller extents underestimate lying objects such as rollers.

            r = dims[2] / 2.0
    except Exception:
        pass
    _EXT_CACHE[key] = r
    return r


class CompoScene(Base_Task):
    SPEC = []
    TARGET = "target"

    # Subclasses must declare their goal predicate explicitly; moved remains a supported option.
    GOAL = {"type": "moved"}
    MIRROR = False             # Optional 50% left/right mirroring prevents fixed-side shortcuts. Disable it where spatial or ordinal wording would change its answer.


    EXCLUSIVE = True           # Require target displacement to exceed distractor displacement. Infer distractors from roles other than targets and GOAL references unless explicitly overridden.
    MOVED_EPS = 0.05
    DISTRACTORS = None

    A_DESC = None
    NOUN = {"021_cup": "cup", "039_mug": "mug", "002_bowl": "bowl", "071_can": "can",
            "001_bottle": "bottle", "035_apple": "apple", "043_book": "book", "057_toycar": "toy car",
            "058_markpen": "marker", "110_basket": "basket", "024_scanner": "barcode", "081_playingcards": "card",
            "050_bell": "bell", "003_plate": "plate", "019_coaster": "coaster", "059_pencup": "pen holder",
            "011_dustbin": "trash", "040_rack": "rack", "088_wineglass": "wine glass", "092_notebook": "notebook",
            "080_pillbottle": "pill bottle", "112_tea-box": "tea box", "107_soap": "soap", "047_mouse": "mouse",
            "048_stapler": "stapler", "072_electronicscale": "scale", "074_displaystand": "display stand",
            "062_plasticbox": "plastic box", "066_vinegar": "vinegar bottle", "052_dumbbell": "dumbbell",
            "102_roller": "roller", "018_microphone": "microphone", "015_laptop": "laptop", "041_shoe": "shoe",
            "007_shoe-box": "shoe box", "060_kitchenpot": "pot", "067_steamer": "steamer", "008_tray": "tray",
            "105_sauce-can": "sauce can", "075_bread": "bread", "076_breadbasket": "bread basket",
            "106_skillet": "skillet", "077_phone": "phone", "078_phonestand": "phone stand", "099_fan": "fan",
            "056_switch": "switch", "100_seal": "seal", "046_alarm-clock": "alarm clock", "020_hammer": "hammer",
            "084_woodenmallet": "wooden mallet", "073_rubikscube": "cube", "063_tabletrashbin": "desk bin",
            "022_cup-with-liquid": "cup of water", "036_cabinet": "cabinet", "044_microwave": "microwave"}

    # Descriptions.
    def _desc_of(self, role):
        for s in self.SPEC:
            if s["role"] == role:
                if s.get("desc"):
                    return s["desc"]
                if s["kind"] == "box":
                    return "block"
                return self.NOUN.get(s["model"], "object")
        return "object"

    def _target_desc(self):
        return self.A_DESC or self._desc_of(self.TARGET)

    # Actor placement: lying bottle/can orientation depends on side (left and right use opposite quaternion signs).
    def setup_demo(self, **kwags):
        super()._init_task_env_(**kwags)

    def _mx(self, region):
        if not getattr(self, "_flip", False):
            return region
        x = region[0]
        return [[-x[1], -x[0]], region[1]]

    def _my_radius(self, s, mid=None):
        if s["kind"] == "box":
            hs = s.get("half_size")
            if hs:
                return max(float(hs[0]), float(hs[1]))
            return float(s.get("half", 0.02))
        if s["kind"] == "urdf":
            return float(s.get("radius", 0.12))
        return _model_radius(s["model"], mid if mid is not None else s["ids"][0])

    def _overlaps(self, xy, r):
        """Check footprint overlap against placed actors with a 1.5 cm margin."""
        for (oxy, orad) in getattr(self, "_placed", []):
            if float(np.hypot(xy[0] - oxy[0], xy[1] - oxy[1])) < (r + orad * 0.8 + 0.01):
                return True
        return False

    def _place(self, s):
        qpos = s.get("qpos", [1, 0, 0, 0])


        if s.get("qpos_lr") and "rel" not in s:
            reg = self._mx(s.get("region", [[-0.2, 0.2], [-0.15, -0.05]]))
            qpos = s["qpos_lr"][1 if (reg[0][0] + reg[0][1]) / 2.0 > 0 else 0]
        if "rel" in s:
            base = self._actors[s["rel"]].get_pose().p
            off = s.get("offset", [0, 0, 0])
            pose = sapien.Pose([float(base[0] + off[0]), float(base[1] + off[1]), float(base[2] + off[2])], qpos)
        else:
            region = self._mx(s.get("region", [[-0.22, 0.22], [-0.15, -0.02]]))
            # Resample to avoid overlap with actors already placed.

            # Relax footprint separation progressively to 0.75, 0.5, and 0.35 when full separation cannot fit the reachable workspace.


            rad = self._my_radius(s)
            pose = cand = None
            for shrink in (1.0, 0.75, 0.5, 0.35):
                for _ in range(s.get("place_tries", 40)):
                    cand = rand_pose(xlim=region[0], ylim=region[1], zlim=s.get("zlim", [0.79]),
                                     qpos=qpos, rotate_rand=s.get("rot", True),
                                     rotate_lim=s.get("rotlim", [0, 0, 0.4]))
                    if not self._overlaps((float(cand.p[0]), float(cand.p[1])), rad * shrink):
                        pose = cand
                        break
                if pose is not None:
                    break
            if pose is None:
                # If all attempts fail, use the spawn-region center rather than a rejected candidate outside the intended workspace.


                cx = (region[0][0] + region[0][1]) / 2.0
                cy = (region[1][0] + region[1][1]) / 2.0
                pose = rand_pose(xlim=[cx, cx], ylim=[cy, cy], zlim=s.get("zlim", [0.79]),
                                 qpos=qpos, rotate_rand=False)
        if s["kind"] == "urdf":
            # Load articulated objects through URDF rather than model_data JSON.

            region = self._mx(s.get("region", [[-0.05, 0.05], [-0.1, 0.05]]))
            a = rand_create_sapien_urdf_obj(
                scene=self, modelname=s["model"], modelid=int(np.random.choice(s["ids"])),
                xlim=region[0], ylim=region[1], zlim=s.get("zlim", [0.741]),
                rotate_rand=s.get("rot", True), rotate_lim=s.get("rotlim", [0, 0, 0.4]),
                qpos=s.get("qpos", [0.7, 0, 0, 0.7]), fix_root_link=s.get("fix_root", True))
            if s.get("qpos_init") is not None:
                lim = a.get_qlimits()[0]
                a.set_qpos([lim[0] + (lim[1] - lim[0]) * float(s["qpos_init"])])
            a.set_mass(s.get("mass", 0.01))
            try:
                a.set_properties(1, 0)
            except Exception:
                pass
            self._model_of[s["role"]] = s["model"]
            self._half_of[s["role"]] = s.get("half", 0.02)
            return a
        if s["kind"] == "box":
            h = s.get("half", 0.02)
            hs = s.get("half_size", [h, h, h])
            a = create_box(scene=self, pose=pose, half_size=hs, color=s.get("color", (0.5, 0.5, 0.5)),
                           name="box", is_static=s.get("static", False))
        else:
            mid = int(np.random.choice(s["ids"]))
            a = create_actor(scene=self, pose=pose, modelname=s["model"], convex=True,
                             model_id=mid, is_static=s.get("static", False))
            if s["model"] == "110_basket":
                a.config['_placement_asset'] = s["model"]
                a.config['_placement_model_id'] = mid
            a.set_mass(s.get("mass", 0.05))
        self._model_of[s["role"]] = s.get("model") if s["kind"] == "model" else "box"
        self._half_of[s["role"]] = s.get("half", 0.02)
        return a

    # Distractor displacement tolerance defaults to MOVED_EPS; scenes may override it. Incidental contact is not itself a selection error.

    WRONG_EPS = 0.05

    # Validate nearest-reference descriptions by resampling rivals until the target is sufficiently nearer to the named reference.


    NEAREST = None

    REPLACE_TRIES = 25          # Bound initial-goal replacement attempts. Set pose on the entity wrapped by Actor.

    def _enforce_nearest(self):
        """Resample rivals until the target is nearer to its reference. Keep the target/reference geometry unchanged to preserve grasp reachability."""
        n = self.NEAREST
        if not n:
            return
        who, ref = n.get("who", self.TARGET), n["ref"]
        ratio = float(n.get("ratio", 1.6))
        spec = {p["role"]: p for p in self.SPEC}
        for rv in n.get("rivals", []):
            if rv not in self._actors or rv not in spec:
                continue
            for _ in range(30):
                q = self._p(ref)
                d_t = float(np.linalg.norm(self._p(who)[:2] - q[:2]))
                d_r = float(np.linalg.norm(self._p(rv)[:2] - q[:2]))
                if d_r > d_t * ratio:
                    break
                sp = spec[rv]
                reg = self._mx(sp.get("region", [[-0.22, 0.22], [-0.15, -0.02]]))

                getattr(self._actors[rv], "actor", self._actors[rv]).set_pose(rand_pose(
                    xlim=reg[0], ylim=reg[1], zlim=sp.get("zlim", [0.79]),
                    qpos=sp.get("qpos", [1, 0, 0, 0]), rotate_rand=sp.get("rot", True),
                    rotate_lim=sp.get("rotlim", [0, 0, 0.4])))
                self.delay(1)

    def load_actors(self):
        self._first_moved = None
        self._min_contact_d = 1e9        # Reset per episode.
        self._contact_thr = None
        self._load_actors_once()
        self._enforce_nearest()
        if not getattr(self, "_init_satisfied", False):
            return
        # If the goal is initially satisfied, reposition manipulated actors rather than recreating the scene and leaving duplicate actors.


        manip = [sp for sp in self.SPEC
                 if sp["role"] in self._refs_of(self.GOAL) or sp["role"] == self.TARGET]
        tgt = next((sp for sp in self.SPEC if sp["role"] == self.TARGET), None)
        if tgt is None or "rel" in tgt:
            raise UnStableError("Initial goal satisfied; cannot resample this target")
        region = self._mx(tgt.get("region", [[-0.22, 0.22], [-0.15, -0.02]]))
        a = self._actors[self.TARGET]
        for _ in range(self.REPLACE_TRIES):
            cand = rand_pose(xlim=region[0], ylim=region[1], zlim=tgt.get("zlim", [0.79]),
                             qpos=tgt.get("qpos", [1, 0, 0, 0]),
                             rotate_rand=tgt.get("rot", True),
                             rotate_lim=tgt.get("rotlim", [0, 0, 0.4]))
            # Actor wraps a SAPIEN entity and does not expose set_pose itself.
            getattr(a, "actor", a).set_pose(cand)
            self.delay(1)
            self._p0 = {k: np.asarray(v.get_pose().p,dtype=float).copy() for k,v in self._actors.items()}
            self._maxdisp = {k:0.0 for k in self._actors}
            self._maxz = {k:float(v[2]) for k,v in self._p0.items()}
            self._bottom0 = {k:float(world_bounds(v)[0][2]) for k,v in self._actors.items()}
            self.stage = 0
            self._pressed_roles = set()
            too_close = False
            if self.GOAL.get("min_start") and self.GOAL.get("ref") in self._actors:
                too_close = np.linalg.norm(self._p(self.TARGET)[:2]-self._p(self.GOAL["ref"])[:2]) < self.GOAL["min_start"]
            if not self._goal_ok(self.GOAL) and not too_close:
                self._init_satisfied = False
                return
        raise UnStableError("Unable to sample an initially unsatisfied goal")

    SHUFFLE_SLOTS = None        # Randomly permute role spawn slots to avoid target-location shortcuts, e.g. [target, d1, d2].

    def _load_actors_once(self):
        # Do not mutate class-level layout across expert/eval resets.
        self.SPEC = deepcopy(type(self).SPEC)
        self._flip = bool(self.MIRROR and np.random.rand() < 0.5)


        if self.SHUFFLE_SLOTS:
            roles = [r for r in self.SHUFFLE_SLOTS
                     if any(sp["role"] == r and "region" in sp for sp in self.SPEC)]
            regs = [next(sp for sp in self.SPEC if sp["role"] == r)["region"] for r in roles]
            perm = np.random.permutation(len(regs))
            for r, k in zip(roles, perm):
                next(sp for sp in self.SPEC if sp["role"] == r)["region"] = regs[int(k)]
        self._actors, self._p0, self._model_of, self._half_of = {}, {}, {}, {}
        self._placed = []          # Already placed (xy, radius) footprints for overlap checks.
        for s in self.SPEC:
            a = self._place(s)
            self._actors[s["role"]] = a
            try:
                pp = a.get_pose().p
                self._placed.append(((float(pp[0]), float(pp[1])), self._my_radius(s)))
            except Exception:
                pass
            if not s.get("static", False):
                try:
                    self.add_prohibit_area(a, padding=s.get("pad", 0.08))
                except Exception:
                    pass
        self.delay(2)
        for k, v in self._actors.items():
            self._p0[k] = np.asarray(v.get_pose().p, dtype=float)
        self._maxdisp = {k: 0.0 for k in self._actors}
        self._maxz = {k: float(self._p0[k][2]) for k in self._actors}
        self._bottom0 = {k:float(world_bounds(v)[0][2]) for k,v in self._actors.items()}
        self.stage = 0
        self._pressed_roles = set()
        # Reject an initially satisfied goal by repositioning actors, up to REPLACE_TRIES attempts.


        self._init_satisfied = False
        try:
            if self._goal_ok(self.GOAL):
                self._init_satisfied = True
            # min_start also requires meaningful initial separation from the reference, not merely being just outside goal tolerance.


            ms = self.GOAL.get("min_start")
            if ms and self.GOAL.get("ref") in self._actors:
                d = float(np.linalg.norm(self._p(self.TARGET)[:2]
                                         - self._p(self.GOAL["ref"])[:2]))
                if d < float(ms):
                    self._init_satisfied = True
        except Exception:
            pass
        tp = self._actors[self.TARGET].get_pose().p
        self.arm_tag = ArmTag("right" if tp[0] > 0 else "left")

    # Compose expert actions from GOAL so expert feasibility and final success refer to the same physical requirement.


    def _ref_pose(self, role, fp=None):
        """Use a reference functional point when available, otherwise its pose."""
        a = self._actors[role]
        if fp is not None:
            try:
                return np.asarray(a.get_functional_point(fp), dtype=float)[:3]
            except Exception:
                pass
        return np.asarray(a.get_pose().p, dtype=float)

    def _place_target(self, g):
        """Convert GOAL to a seven-component placement pose; return None for non-placement actions."""
        t = g.get("type", "moved")
        if t in ("moved", "lift", "press", "seq", "qpos"):
            return None
        who = g.get("who", self.TARGET)
        half = self._half_of.get(who, 0.02)
        if t in ("on", "stack"):
            q = self._ref_pose(g["ref"])
            # Expert placement height and final predicate offset are distinct quantities; place_actor computes object parking height.


            # Prefer place_dz, otherwise use the goal dz as the placement offset.

            dz = g.get("place_dz")
            if dz is None:
                dz = g.get("dz")
            if dz is None:
                dz = 0.05 if t == "stack" else 0.03
            # Default to a free placement orientation; stapler-specific alignment constraints need not be feasible for other objects.


            return [float(q[0]), float(q[1]), float(q[2] + dz)] + g.get("quat", [1, 0, 0, 0])
        if t == "in":
            q = self._ref_pose(g["ref"], fp=g.get("fp", 0))
            return [float(q[0]), float(q[1]), float(q[2] + g.get("dz", 0.04))] + g.get("quat", [1, 0, 0, 0])
        if t == "rel":
            q = self._ref_pose(g["ref"])
            lo, hi = g.get("gap", [0.04, 0.30])
            d = g.get("dir", "left")
            off = g.get("place_gap", (lo + min(hi, lo + 0.10)) / 2.0)
            dx = {"left": -off, "right": off}.get(d, 0.0)
            dy = {"behind": off, "front": -off}.get(d, 0.0)
            # For upright goals, derive the standing orientation from the asset SPEC rather than a universal quaternion.


            # Retain the tested target pose; evaluate uprightness from the asset axis instead of inferring it from the placement quaternion alone.


            dq = [1, 0, 0, 0]
            return [float(q[0] + dx), float(q[1] + dy), float(q[2] + half + 0.005)] + g.get("quat", dq)
        if t == "between":
            a, b = [self._ref_pose(r) for r in g["refs"]]
            m = (a + b) / 2.0
            return [float(m[0]), float(m[1]), float(max(a[2], b[2]) + half + 0.005)] + g.get("quat", [1, 0, 0, 0])
        return None

    def _do_press(self, g):
        """Press at the contact point with the gripper, then retreat, following click_bell."""
        ref = g.get("ref", self.TARGET)
        arm = ArmTag("right" if self._p(ref)[0] > 0 else "left")
        self.move(self.grasp_actor(self._actors[ref], arm_tag=arm,
                                   pre_grasp_dis=g.get("pre", 0.1), grasp_dis=g.get("pre", 0.1),
                                   contact_point_id=g.get("cp", 0)))
        self.move(self.move_by_displacement(arm, z=-g.get("push", 0.045)))
        self.check_success()
        self.move(self.move_by_displacement(arm, z=g.get("push", 0.045)))
        self.check_success()
        return arm

    def _do_stack(self, g, a, arm):
        """Stack by aligning actor functional point 0 to reference point 1, as in stack_blocks_two."""
        try:
            tp = self._actors[g["ref"]].get_functional_point(1)
            self.move(self.place_actor(a, target_pose=tp, arm_tag=arm, functional_point_id=0,
                                       pre_dis=0.05, dis=0.0, pre_dis_axis="fp"))
        except Exception:
            q = self._ref_pose(g["ref"])
            tp = [float(q[0]), float(q[1]), float(q[2] + g.get("dz", 0.05)), 0, 1, 0, 0]
            self.move(self.place_actor(a, target_pose=tp, arm_tag=arm, pre_dis=0.05, dis=0.0))
        self.move(self.move_by_displacement(arm_tag=arm, z=0.07))

    def _do_in(self, g, a, arm):
        """Insert using the nearest container functional point and an arm-specific approach; place before explicitly releasing and retreating."""
        c = self._actors[g["ref"]]
        try:
            f0 = np.array(c.get_functional_point(0), dtype=float)
            try:
                f1 = np.array(c.get_functional_point(1), dtype=float)
            except Exception:
                f1 = f0
            pa = self._p(g.get("who", self.TARGET))
            place = f0 if np.linalg.norm(f0[:2] - pa[:2]) <= np.linalg.norm(f1[:2] - pa[:2]) else f1
            place = place.astype(float).copy()
        except Exception:
            q = self._ref_pose(g["ref"])
            place = np.array([q[0], q[1], q[2] + g.get("dz", 0.04), 1, 0, 0, 0], dtype=float)
        place[3:] = (-1, 0, 0, 0) if arm == "left" else (0.05, 0, 0, 0.99)
        self.move(self.place_actor(a, arm_tag=arm, target_pose=place.tolist(),
                                   dis=g.get("dis", 0.02), is_open=False))
        if not self.plan_success:
            # Fallback: raise above the container rim, descend, then release.
            self.plan_success = True
            place[0] += -0.15 if arm == "left" else 0.15
            place[2] += 0.15
            self.move(self.move_to_pose(arm_tag=arm, target_pose=place.tolist()))
            place[2] -= 0.05
            self.move(self.move_to_pose(arm_tag=arm, target_pose=place.tolist()))
        self.move(self.open_gripper(arm_tag=arm))
        self.move(self.move_by_displacement(arm_tag=arm, z=0.08))

    def _do_beat(self, g):
        """Execute the beat_block_hammer sequence. Align hammer point 0 with target point 1. The stationary target is checked by contact, not displacement."""
        who = g.get("who", self.TARGET)
        tool = self._actors[g.get("tool", "hammer")]
        blk = self._actors[who]
        arm = ArmTag("left" if self._p(who)[0] < 0 else "right")
        self.move(self.grasp_actor(tool, arm_tag=arm, pre_grasp_dis=0.12, grasp_dis=0.01))
        self.move(self.move_by_displacement(arm, z=0.07, move_axis="arm"))
        self.move(self.place_actor(tool, target_pose=blk.get_functional_point(1, "pose"),
                                   arm_tag=arm, functional_point_id=0,
                                   pre_dis=0.06, dis=0, is_open=False))
        return arm

    def _do_dual_lift(self, g):
        """Lift two objects concurrently, one per arm, using move(a, b)."""
        who, w2 = g.get("who", self.TARGET), g["who2"]
        a, b = self._actors[who], self._actors[w2]
        # Use the left arm for the left object and the right arm for the right object.
        if self._p(who)[0] > self._p(w2)[0]:
            a, b = b, a
        self.move(self.grasp_actor(a, arm_tag=ArmTag("left"), pre_grasp_dis=g.get("pre_grasp", 0.08)),
                  self.grasp_actor(b, arm_tag=ArmTag("right"), pre_grasp_dis=g.get("pre_grasp", 0.08)))
        self.move(self.move_by_displacement(arm_tag=ArmTag("left"), z=g.get("lift", 0.12)),
                  self.move_by_displacement(arm_tag=ArmTag("right"), z=g.get("lift", 0.12)))
        return ArmTag("left")

    def _do_dual_carry(self, g):
        """Lift one handled object with both arms, following lift_pot."""
        who = g.get("who", self.TARGET)
        a = self._actors[who]
        l, r = ArmTag("left"), ArmTag("right")
        self.move(self.close_gripper(l, pos=0.5), self.close_gripper(r, pos=0.5))
        self.move(self.grasp_actor(a, l, pre_grasp_dis=g.get("pre_grasp", 0.035), contact_point_id=0),
                  self.grasp_actor(a, r, pre_grasp_dis=g.get("pre_grasp", 0.035), contact_point_id=1))
        dz = g.get("lift", 0.12)
        self.move(self.move_by_displacement(l, z=dz), self.move_by_displacement(r, z=dz))
        return l

    def _do_dual_carry_to(self, g):
        """Lift with both arms, translate both end effectors by the reference xy offset, and release together. Use coordinated displacements rather than single-arm place_actor."""
        self._do_dual_carry(g)
        l, r = ArmTag("left"), ArmTag("right")
        who = g.get("who", self.TARGET)
        # Verify the pot was lifted before translating; sliding it onto the pad is not a lift.

        self._track()
        if (self._maxz[who] - float(self._p0[who][2])) <= g.get("dz", 0.06):
            return l
        p, q = self._p(who), self._p(g["ref"])
        dx, dy = float(q[0] - p[0]), float(q[1] - p[1])
        # Plan the coordinated transfer without an extra descent into the thin pad.


        # Use two smaller translations to improve simultaneous dual-arm IK reachability.

        for _ in range(2):
            self.move(self.move_by_displacement(l, x=dx / 2.0, y=dy / 2.0),
                      self.move_by_displacement(r, x=dx / 2.0, y=dy / 2.0))
        self.move(self.open_gripper(l), self.open_gripper(r))
        return l

    def _do_goal(self, g):
        """Execute expert actions for one GOAL and return the selected arm tag."""
        t = g.get("type", "moved")
        if t == "press":
            return self._do_press(g)
        if t == "dual_lift":
            return self._do_dual_lift(g)
        if t == "dual_carry":
            return self._do_dual_carry(g)
        if t == "beat":
            return self._do_beat(g)
        if t == "dual_carry_to":
            return self._do_dual_carry_to(g)
        who = g.get("who", self.TARGET)
        a = self._actors[who]
        if t in ("lift", "moved"):
            g = dict(g); g.setdefault("lift", 0.15)
        tp = self._place_target(g)
        # Choose the arm by destination, which is the tighter constraint. Source and destination must remain in a compatible half-workspace.


        anchor = tp[0] if tp is not None else self._p(who)[0]
        arm = ArmTag("right" if anchor > 0 else "left")
        self.move(self.grasp_actor(a, arm_tag=arm, pre_grasp_dis=g.get("pre_grasp", 0.1)))
        self.move(self.move_by_displacement(arm_tag=arm, z=g.get("lift", 0.10), move_axis="arm"))
        if t == "stack":
            self._do_stack(g, a, arm)
            return arm
        if t == "in":
            self._do_in(g, a, arm)
            return arm
        if tp is not None:
            tp = self._place_target(g)   # Recompute the destination if grasping displaced the reference.
            # Upright placement requires an orientation constraint rather than free placement.

            # Use auto constraints so get_place_pose also supplies the arm-specific align_axis.


            _kw = {}
            if g.get("upright"):
                _kw["constrain"] = "auto"
            elif g.get("constrain"):
                _kw["constrain"] = g["constrain"]
            else:
                _kw["constrain"] = "free"
            self.move(self.place_actor(a, target_pose=tp, arm_tag=arm,
                                       pre_dis=g.get("pre_dis", 0.1), dis=g.get("dis", 0.0),
                                       **_kw))
            self.move(self.move_by_displacement(arm_tag=arm, z=0.06, move_axis="arm"))
        return arm

    def play_once(self):
        goal = self.GOAL
        if goal.get("type") == "seq":
            arms = []
            for g in goal["stages"]:
                arms.append(self._do_goal(g))
                # Observe placement after physical settling before the next stage.
                self.delay(1)
                # Latch each expert stage explicitly; runtime stage checks advance only one stage at a time and must preserve ordering.


                self.check_success()
            arm = arms[0] if arms else self.arm_tag
        else:
            arm = self._do_goal(goal)
        self.arm_tag = arm
        # If recovery reaches the actual goal, restore plan_success so successful recovered expert trajectories are not rejected solely by a prior planning failure.


        if not self.plan_success and self.check_success():
            self.plan_success = True
        self.info["info"] = {"{A}": self._target_desc(), "{a}": str(arm)}
        return self.info

    # Predicate helpers: permit small incidental reference motion, but not moving the container to the target.
    def _p(self, role):
        return np.asarray(self._actors[role].get_pose().p, dtype=float)

    def _grippers_open(self):
        try:
            from ._robot_state import gripper_aperture
            return bool(self.is_left_gripper_open() and self.is_right_gripper_open() and
                        gripper_aperture(self.robot, 'left') > 0.8 and
                        gripper_aperture(self.robot, 'right') > 0.8)
        except Exception:
            return False

    def _tools_of(self, g):
        """Return tool roles used by GOAL. Tools are excluded from both distractor selection guards and fixed-reference constraints because they must move."""
        out = set()
        if not isinstance(g, dict):
            return out
        if g.get("tool"):
            out.add(g["tool"])
        for sub in (g.get("stages") or []):
            out |= self._tools_of(sub)
        return out

    def _is_upright(self, role, thr=0.75):
        """Check whether the asset longest axis points upward; do not assume local z is the long axis."""
        try:
            a = self._actors[role]
            cfg = a.config
            ext = np.asarray(cfg["extents"], dtype=float) * np.asarray(cfg.get("scale", 1), dtype=float)
            axis = int(np.argmax(ext))
            R = a.get_pose().to_transformation_matrix()[:3, :3]
            return bool(abs(float(R[2, axis])) >= thr)
        except Exception:
            return False

    def wants_contact_log(self):
        """Identify contact tasks so each episode records distance, including trajectories with no contact."""
        def has(g):
            if not isinstance(g, dict):
                return False
            if g.get("type") in ("press", "beat"):
                return True
            return any(has(x) for x in (g.get("stages") or []))
        return has(self.GOAL)

    def _refs_of(self, g):
        """Recursively collect GOAL roles excluded from distractors."""
        out = set()
        if not isinstance(g, dict):
            return out
        if g.get("ref"):
            out.add(g["ref"])
        for r in (g.get("refs") or []):
            out.add(r)
        for sub in (g.get("stages") or []):
            out |= self._refs_of(sub)
        return out


    REF_MOVE_EPS = 0.05

    def _refs_stayed_put(self):
        """Require reference/container displacement below the configured tolerance. Moving a container toward a displaced target must not satisfy a placement task."""
        for r in self._refs_of(self.GOAL):
            if r not in self._maxdisp:
                continue
            if self._maxdisp[r] > self.REF_MOVE_EPS:
                return False
        return True

    def _distractor_roles(self):
        if self.DISTRACTORS is not None:
            return list(self.DISTRACTORS)
        skip = {self.TARGET} | self._refs_of(self.GOAL) | self._tools_of(self.GOAL)
        return [k for k in self._actors if k not in skip]

    # GOAL predicates: without a specified height, require the target within a thin region above the reference.
    def _goal_ok(self, g):
        t = g.get("type", "moved")
        who = g.get("who", self.TARGET)
        try:
            if t == "moved":
                return self._maxdisp[who] > g.get("eps", self.MOVED_EPS)

            if t == "lift":
                return grasped_clearance(self, self._actors[who], self._bottom0[who], g.get("dz", 0.10))

            if t in ("on", "stack"):
                p, q = self._p(who), self._p(g["ref"])
                eps = g.get("eps", [0.03, 0.03, 0.02] if t == "stack" else [0.035, 0.035, 0.03])
                dz = g.get("dz")
                if dz is None:
                    dz = 0.05 if t == "stack" else None
                if dz is None:

                    ok_z = 0.0 <= (p[2] - q[2]) <= g.get("zmax", 0.12)
                else:
                    ok_z = abs((p[2] - q[2]) - dz) < eps[2]
                return (abs(p[0] - q[0]) < eps[0] and abs(p[1] - q[1]) < eps[1]
                        and ok_z and (g.get("_retained", False) or self._grippers_open())
                        and supported_placement(self.scene,self._actors[who],self._actors[g["ref"]],t))

            if t == "in":
                p, q = self._p(who), self._p(g["ref"])
                # With multiple similar containers, require the target to be clearly closer to the requested one.


                rivals = [k for k, mo in self._model_of.items()
                          if k != g["ref"] and k != who and mo == self._model_of.get(g["ref"])]
                for rv in rivals:
                    dq = float(np.linalg.norm(p[:2] - self._p(rv)[:2]))
                    if dq <= float(np.linalg.norm(p[:2] - q[:2])) + g.get("margin", 0.05):
                        return False
                r = g.get("r", 0.07)
                moved = np.linalg.norm(p - self._p0[who]) > g.get("min_move", 0.05)
                # Containment requires the target above the container origin, not lying alongside it on the table.

                return (float(np.linalg.norm(p[:2] - q[:2])) < r
                        and p[2] > (q[2] + g.get("zmin", 0.0))
                        and moved and (g.get("_retained", False) or self._grippers_open())
                        and supported_placement(self.scene,self._actors[who],self._actors[g["ref"]],"in"))

            if t == "rel":
                p, q = self._p(who), self._p(g["ref"])
                if g.get("upright"):
                    # Uprightness uses the longest asset extent, not necessarily local z. This handles cans whose long axis is local y.


                    if not self._is_upright(who, g.get("up_cos", 0.75)):
                        return False
                # Require unambiguous proximity to the requested reference when similar references exist.
                rivals = [k for k, mo in self._model_of.items()
                          if k != g["ref"] and k != who and mo == self._model_of.get(g["ref"])]
                for rv in rivals:
                    if float(np.linalg.norm(p[:2] - self._p(rv)[:2])) <= \
                       float(np.linalg.norm(p[:2] - q[:2])) + g.get("margin", 0.05):
                        return False
                lo, hi = g.get("gap", [0.04, 0.30])
                lat = g.get("lat", 0.12)
                d = g.get("dir", "left")
                if d in ("left", "right"):
                    s = (q[0] - p[0]) if d == "left" else (p[0] - q[0])
                    side_ok = lo < s < hi and abs(p[1] - q[1]) < lat
                else:
                    s = (p[1] - q[1]) if d == "behind" else (q[1] - p[1])
                    side_ok = lo < s < hi and abs(p[0] - q[0]) < lat
                return side_ok and abs(p[2] - q[2]) < g.get("dzmax", 0.10) and (g.get("_retained", False) or self._grippers_open())

            if t == "between":
                a, b = [self._p(r) for r in g["refs"]]
                p = self._p(who)
                mid = (a[:2] + b[:2]) / 2.0
                span = float(np.linalg.norm(a[:2] - b[:2]))
                return (float(np.linalg.norm(p[:2] - mid)) < g.get("lat", 0.09)
                        and span > g.get("min_span", 0.12)
                        and abs(float(p[2] - (a[2]+b[2])/2)) <= g.get("dzmax", 0.12)
                        and (g.get("_retained", False) or self._grippers_open()))

            if t == "press":
                # Pressing requires gripper proximity at the contact point and limited object displacement; record minimum horizontal distance.
                ref = g.get("ref", who)
                if ref in self._pressed_roles:
                    return True
                model = g.get("model") or self._model_of.get(ref)
                if not model or model == "box":
                    return False
                try:
                    if not self.check_arm_function():
                        return False
                except Exception:
                    pass
                cp = np.asarray(self._actors[ref].get_contact_point(g.get("cp", 0))[:3], dtype=float)
                eps = g.get("eps", [0.03, 0.03])

                for _pos in self.get_gripper_actor_contact_position(model):
                    _p = np.asarray(_pos, dtype=float)
                    _d = max(abs(_p[0] - cp[0]), abs(_p[1] - cp[1]))
                    if _d < getattr(self, "_min_contact_d", 1e9):
                        self._min_contact_d = float(_d)
                        self._contact_thr = float(min(eps))
                for pos in self.get_gripper_actor_contact_position(model):
                    pos = np.asarray(pos, dtype=float)
                    if (abs(pos[0] - cp[0]) < eps[0] and abs(pos[1] - cp[1]) < eps[1]
                            and abs(pos[2] - cp[2]) < g.get("epsz", 0.03)):
                        if self._maxdisp[ref] < g.get("max_move", 0.04):
                            self._pressed_roles.add(ref)
                            return True
                return False

            if t == "dual_carry_to":
                # Require prior lift, final placement above the reference, and gripper release.
                if (self._maxz[who] - float(self._p0[who][2])) <= g.get("dz", 0.06):
                    return False
                p, q = self._p(who), self._p(g["ref"])
                eps = g.get("eps", [0.09, 0.09])
                return (abs(p[0] - q[0]) < eps[0] and abs(p[1] - q[1]) < eps[1]
                        and p[2] > q[2] and self._grippers_open())

            if t == "beat":
                # Hammer functional point 0 must align with target point 1 and contact it, matching beat_block_hammer. Record minimum distance for diagnostics.

                tool = self._actors[g.get("tool", "hammer")]
                blk = self._actors[who]
                hp = np.asarray(tool.get_functional_point(0, "pose").p, dtype=float)
                bp = np.asarray(blk.get_functional_point(1, "pose").p, dtype=float)
                eps = g.get("eps", [0.02, 0.02])

                dmax = max(abs(hp[0] - bp[0]), abs(hp[1] - bp[1]))
                if dmax < getattr(self, "_min_contact_d", 1e9):
                    self._min_contact_d = float(dmax)
                    self._contact_thr = float(min(eps))
                if not (abs(hp[0] - bp[0]) < eps[0] and abs(hp[1] - bp[1]) < eps[1]):
                    return False
                return bool(self.check_actors_contact(tool.get_name(), blk.get_name()))

            if t == "qpos":
                # Threshold normalized articulated joint state in [0, 1].
                a = self._actors[g["ref"]]
                lim = a.get_qlimits()[0]
                cur = float(a.get_qpos()[g.get("joint", 0)])
                frac = (cur - lim[0]) / max(1e-6, (lim[1] - lim[0]))
                return frac > g.get("thr", 0.7)

            if t == "dual_lift":
                # Lift two objects concurrently, one per arm.
                dz = g.get("dz", 0.06)
                w2 = g["who2"]
                return ((self._maxz[who] - float(self._p0[who][2])) > dz
                        and (self._maxz[w2] - float(self._p0[w2][2])) > dz)

            if t == "dual_carry":
                # Lift one object using both handles and arms.
                return (self._maxz[who] - float(self._p0[who][2])) > g.get("dz", 0.08)

            if t == "seq":
                if self.stage < len(g["stages"]):
                    return False
                # A later press does not consume the preceding placement.
                # Keep only each object's last pose-changing obligation.
                last = {}
                for sub in g["stages"]:
                    if sub.get("type") not in ("press", "qpos"):
                        last[sub.get("who", self.TARGET)] = sub
                return all(self._goal_ok(dict(sub, _retained=True)) for sub in last.values()
                           if sub.get("type") in ("in", "on", "stack", "rel", "between"))
        except Exception:
            return False
        raise ValueError("unknown GOAL type: %r" % t)

    # Success entry: latch the first role with substantive displacement; break same-frame ties by greatest displacement.
    def _track(self):
        for k, v in self._actors.items():
            p = np.asarray(v.get_pose().p, dtype=float)
            self._maxdisp[k] = max(self._maxdisp[k], float(np.linalg.norm(p - self._p0[k])))
            self._maxz[k] = max(self._maxz[k], float(p[2]))


        if getattr(self, "_first_moved", None) is None:
            movers = [k for k, d in self._maxdisp.items() if d > self.MOVED_EPS]
            if movers:

                self._first_moved = max(movers, key=lambda k: self._maxdisp[k])

    def stage_reward(self):
        """Advance sequence stages monotonically; stage n must occur after stage n-1."""
        if self.GOAL.get("type") != "seq":
            self.stage = 1 if self._goal_ok(self.GOAL) else 0
            return float(self.stage)
        stages = self.GOAL["stages"]
        if self.stage < len(stages) and self._goal_ok(stages[self.stage]):
            self.stage += 1
        return self.stage / float(len(stages))

    def _needs_move(self, g):
        """Return whether this GOAL requires target displacement; pressing does not."""
        t = g.get("type")
        if t == "seq":
            return any(self._needs_move(s) for s in g["stages"])
        return t not in ("press", "qpos", "beat")

    def _selected_right(self):
        """Evaluate target-selection guards."""
        if not self.EXCLUSIVE:
            return True
        others = [self._maxdisp[k] for k in self._distractor_roles()]
        omax = max(others) if others else 0.0
        if not self._needs_move(self.GOAL):
            # Press-only goals do not require target displacement; the press geometry identifies the target while distractor displacement stays bounded.

            return omax < self.MOVED_EPS
        # The first substantively displaced role must be the target. Use displacement order, not a ban on incidental distractor contact.


        #


        fm = getattr(self, "_first_moved", None)
        if fm is not None and fm != self.TARGET and fm in self._distractor_roles():
            return False
        return self._maxdisp[self.TARGET] > self.MOVED_EPS and self._maxdisp[self.TARGET] > omax

    def check_success(self):
        self._track()
        self.stage_reward()
        # Combine target-selection, physical-goal, and reference-stability predicates.
        return bool(self._selected_right() and self._refs_stayed_put() and self._goal_ok(self.GOAL))
