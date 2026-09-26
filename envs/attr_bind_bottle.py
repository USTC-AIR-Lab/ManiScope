from ._base_task import Base_Task
from ._placement_judge import world_bounds, grasped_clearance
from .utils import *
import sapien
import os
import json


class attr_bind_bottle(Base_Task):
    """Color-selection evaluation with same-category brown and green bottles. Randomize target identity and side. Record target/distractor displacement separately from the native lifting predicate; movement alone is not lifting."""

    # (model ID, color).
    VARIANTS = [(13, "brown"), (16, "green")]
    # Legacy origin-height threshold retained for compatibility; origin rise alone cannot distinguish upright adjustment from lifting off the support.


    LIFT_H = float(os.environ.get("ATTR_LIFT_H", "0.18"))
    # Displacement provides a target-selection diagnostic separate from lift clearance.

    MOVED_EPS = float(os.environ.get("ATTR_MOVED_EPS", "0.05"))
    LOG_PATH = os.environ.get("ATTR_BIND_LOG", "")

    def setup_demo(self, **kwags):
        super()._init_task_env_(**kwags)

    def load_actors(self):
        # Randomize target identity and side; use the source task side-dependent lying quaternions.
        ti = int(np.random.randint(2))
        target_id, self.target_color = self.VARIANTS[ti]
        other_id, self.other_color = self.VARIANTS[1 - ti]


        qposes = [[0.707, 0.0, 0.0, -0.707], [0.707, 0.0, 0.0, 0.707]]
        xlims = [[-0.22, -0.14], [0.14, 0.22]]
        t_side = int(np.random.randint(2))

        self.objects, self._z0 = {}, {}
        for role, mid, side in (("target", target_id, t_side), ("distractor", other_id, 1 - t_side)):
            actor = rand_create_actor(
                self,
                xlim=xlims[side],
                ylim=[-0.15, -0.05],
                zlim=[0.752],
                rotate_rand=True,
                rotate_lim=(0, 0, 0.4),
                qpos=qposes[side],
                modelname="001_bottle",
                convex=True,
                model_id=mid,
            )
            self.objects[role] = actor
            self.add_prohibit_area(actor, padding=0.08)
        self.delay(4)
        self._p0 = {}
        for k, v in self.objects.items():
            p0 = np.asarray(v.get_pose().p, dtype=float)
            self._z0[k] = float(p0[2])
            self._p0[k] = p0.copy()
        self._bottom0 = {k:float(world_bounds(v)[0][2]) for k,v in self.objects.items()}
        self._maxdz = {k: 0.0 for k in self.objects}
        self._maxdisp = {k: 0.0 for k in self.objects}

        self.object = self.objects["target"]
        self.qpose_tag = t_side
        self.arm_tag = ArmTag("right" if t_side == 1 else "left")
        self._logged = False

    def play_once(self):
        arm = self.arm_tag
        self.move(self.grasp_actor(self.object, arm_tag=arm, pre_grasp_dis=0.1))
        self.move(self.move_by_displacement(arm_tag=arm, z=0.15, move_axis="arm"))
        self.info["info"] = {"{A}": f"{self.target_color} bottle", "{a}": str(arm)}
        return self.info

    # ------------------------------------------------------------------ #
    def _lifted(self, role):
        return bool(self.objects[role].get_pose().p[2] - self._z0[role] > self.LIFT_H)

    def _update_stats(self):
        """Track each bottle maximum rise and displacement for later threshold analysis."""
        for k, v in self.objects.items():
            p = np.asarray(v.get_pose().p, dtype=float)
            self._maxdz[k] = max(self._maxdz[k], float(p[2] - self._z0[k]))
            self._maxdisp[k] = max(self._maxdisp[k], float(np.linalg.norm(p - self._p0[k])))

    def _log_once(self, role, reason):
        # Log only evaluated rollouts, excluding expert feasibility runs.

        if self._logged or not self.LOG_PATH or not getattr(self, "eval_mode", False):
            return
        self._logged = True
        try:
            with open(self.LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "episode": int(getattr(self, "test_num", -1)),
                    "target_color": self.target_color,
                    "went_for": role,          # Track target versus distractor displacement as the selection signal.
                    "reason": reason,
                    "max_dz": {k: round(v, 4) for k, v in self._maxdz.items()},
                    "max_disp": {k: round(v, 4) for k, v in self._maxdisp.items()},
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def check_success(self):
        """Require correct color selection and lifting. Displacement remains a diagnostic; native success also requires collision geometry at least 2 cm above initial support while touching a gripper. LIFT_H is not used because upright adjustment can raise the origin without lifting."""
        self._update_stats()
        dt = self._maxdisp["target"]
        dd = self._maxdisp["distractor"]
        if not self._logged:
            moved = [(k, self._maxdisp[k]) for k in self.objects if self._maxdisp[k] > self.MOVED_EPS]
            if moved:
                self._log_once(max(moved, key=lambda x: x[1])[0], "moved")
        # Keep the original selection signal, and require the instructed pickup.
        return bool(dt > self.MOVED_EPS and dt > dd and
                    grasped_clearance(self, self.objects["target"], self._bottom0["target"], 0.02))
