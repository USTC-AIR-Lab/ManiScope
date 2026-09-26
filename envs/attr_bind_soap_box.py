from ._base_task import Base_Task
from .utils import *
import sapien
import os
import json


class attr_bind_soap_box(Base_Task):
    """Joint color/category selection with a target, a same-color different-category distractor, and a same-category different-color distractor. Require the requested target under the task-specific lifting and selection guards. These are observable predicates, not latent-intention labels."""

    # Role -> (model name, model ID, color, category).
    TRIPLES = [
        {"target": ("107_soap", 0, "yellow", "soap"),
         "same_color": ("112_tea-box", 3, "yellow", "tea box"),
         "same_category": ("107_soap", 2, "blue", "soap")},
        {"target": ("112_tea-box", 3, "yellow", "tea box"),
         "same_color": ("107_soap", 0, "yellow", "soap"),
         "same_category": ("112_tea-box", 0, "green", "tea box")},
        {"target": ("107_soap", 3, "brown", "soap"),
         "same_color": ("113_coffee-box", 0, "brown", "coffee box"),
         "same_category": ("107_soap", 1, "gray", "soap")},
        {"target": ("113_coffee-box", 0, "brown", "coffee box"),
         "same_color": ("107_soap", 3, "brown", "soap"),
         "same_category": ("113_coffee-box", 5, "red", "coffee box")},
    ]
    LIFT_H = 0.10
    LOG_PATH = os.environ.get("ATTR_BIND_LOG", "")

    def setup_demo(self, **kwags):
        super()._init_task_env_(**kwags)

    def load_actors(self):
        trip = self.TRIPLES[int(np.random.randint(len(self.TRIPLES)))]
        self.target_color = trip["target"][2]
        self.target_category = trip["target"][3]

        # Use a triangular layout with the middle object farther back to provide grasp approach clearance.
        slots = [(-0.23, -0.18, -0.18, -0.12), (-0.03, 0.03, -0.06, 0.00), (0.18, 0.23, -0.18, -0.12)]
        order = np.random.permutation(3)

        self.objects, self._z0 = {}, {}
        for (role, (model, mid, _c, _k)), si in zip(trip.items(), order):
            x0, x1, y0, y1 = slots[si]
            actor = create_actor(
                scene=self,
                pose=rand_pose(xlim=[x0, x1], ylim=[y0, y1], qpos=[0.5, 0.5, 0.5, 0.5],
                               rotate_rand=True, rotate_lim=[0, np.pi, 0]),
                modelname=model, convex=True, model_id=mid,
            )
            actor.set_mass(0.05)
            self.objects[role] = actor
            self.add_prohibit_area(actor, padding=0.03)
        self.delay(4)
        for k, v in self.objects.items():
            self._z0[k] = float(v.get_pose().p[2])

        self.object = self.objects["target"]
        self.arm_tag = ArmTag("right" if self.object.get_pose().p[0] > 0 else "left")
        self._logged = False
        self._wrong_lifted = False

    def play_once(self):
        arm = self.arm_tag
        self.move(self.grasp_actor(self.object, arm_tag=arm, pre_grasp_dis=0.1))
        self.move(self.move_by_displacement(arm, z=0.15, move_axis="arm"))
        self.info["info"] = {"{A}": f"{self.target_color} {self.target_category}", "{a}": str(arm)}
        return self.info

    # ------------------------------------------------------------------ #
    def _lifted(self, role):
        return bool(self.objects[role].get_pose().p[2] - self._z0[role] > self.LIFT_H)

    def _log_once(self, role):
        if self._logged or not self.LOG_PATH:
            return
        self._logged = True
        try:
            with open(self.LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"episode": int(getattr(self, "test_num", -1)),
                                    "target": f"{self.target_color} {self.target_category}",
                                    "lifted_role": role}, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def check_success(self):
        # Remember any wrong-object lift, including before the target was lifted.
        wrong = [role for role in self.objects if role != "target" and self._lifted(role)]
        if wrong:
            self._wrong_lifted = True
            self._log_once(wrong[0])
        if getattr(self, "_wrong_lifted", False):
            return False
        if self._lifted("target"):
            self._log_once("target")
            return True
        return False
