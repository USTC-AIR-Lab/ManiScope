from ._base_task import Base_Task
from .utils import *
import sapien
import os


class click_bell_press_stapler(Base_Task):
    """Sequential bell and stapler pressing for evaluation. The static objects occupy opposite sides, one arm each. Stage 2 is accepted only after stage 1."""

    def setup_demo(self, **kwags):
        super()._init_task_env_(**kwags)

    def load_actors(self):
        # Bell and stapler occupy opposite sides, one arm each. Both are static as in the source press tasks.
        side = 1 if np.random.rand() < 0.5 else -1
        bell_x = float(np.random.uniform(0.12, 0.24)) * side
        stap_x = float(np.random.uniform(0.12, 0.24)) * -side

        self.bell_id = int(np.random.choice([0, 1]))
        self.bell = create_actor(
            scene=self,
            pose=rand_pose(xlim=[bell_x, bell_x], ylim=[-0.16, -0.06], qpos=[0.5, 0.5, 0.5, 0.5]),
            modelname="050_bell",
            convex=True,
            model_id=self.bell_id,
            is_static=True,
        )
        self.stapler_id = int(np.random.choice([0, 1, 2, 3, 4, 5, 6]))
        self.stapler = create_actor(
            scene=self,
            pose=rand_pose(xlim=[stap_x, stap_x], ylim=[-0.16, -0.06],
                           qpos=[0.5, 0.5, 0.5, 0.5], rotate_rand=True, rotate_lim=[0, np.pi, 0]),
            modelname="048_stapler",
            convex=True,
            model_id=self.stapler_id,
            is_static=True,
        )
        self.add_prohibit_area(self.bell, padding=0.07)
        self.add_prohibit_area(self.stapler, padding=0.05)

        self.bell_arm = ArmTag("right" if self.bell.get_pose().p[0] > 0 else "left")
        self.stapler_arm = ArmTag("right" if self.stapler.get_pose().p[0] > 0 else "left")
        self._bell_close = (self.is_left_gripper_close if self.bell.get_pose().p[0] < 0
                            else self.is_right_gripper_close)
        self.stage = 0

    def play_once(self):
        # Stage 1: click_bell action sequence.
        a = self.bell_arm
        self.move(self.grasp_actor(self.bell, arm_tag=a, pre_grasp_dis=0.1, grasp_dis=0.1, contact_point_id=0))
        self.move(self.move_by_displacement(a, z=-0.045))
        self.stage_reward()
        self.move(self.move_by_displacement(a, z=0.045))

        # Stage 2: press_stapler sequence. It must occur after stage 1; progress is monotonic.
        b = self.stapler_arm
        self.move(self.grasp_actor(self.stapler, arm_tag=b, pre_grasp_dis=0.1, grasp_dis=0.1, contact_point_id=2))
        self.move(self.close_gripper(arm_tag=b))
        self.move(self.grasp_actor(self.stapler, arm_tag=b, pre_grasp_dis=0.02, grasp_dis=0.02, contact_point_id=2))
        self.stage_reward()

        self.info["info"] = {
            "{A}": f"050_bell/base{self.bell_id}",
            "{B}": f"048_stapler/base{self.stapler_id}",
            "{a}": str(a),
            "{b}": str(b),
        }
        return self.info

    # ------------------------------------------------------------------ #
    def _bell_clicked(self):
        """Use the click_bell success predicate."""
        if not self._bell_close():
            return False
        cp = self.bell.get_contact_point(0)[:3]
        for p in self.get_gripper_actor_contact_position("050_bell"):
            if np.all(np.abs(p[:2] - cp[:2]) < 0.025) and abs(p[2] - cp[2]) < 0.03:
                return True
        return False

    def _stapler_pressed(self):
        """Use the press_stapler success predicate."""
        cp = self.stapler.get_contact_point(2)[:3]
        for p in self.get_gripper_actor_contact_position("048_stapler"):
            if np.all(np.abs(p[:2] - cp[:2]) < 0.03) and abs(p[2] - cp[2]) < 0.03:
                return True
        return False

    def stage_reward(self):


        if self.stage >= 1 and self._stapler_pressed():
            self.stage = 2
        elif self.stage < 1 and self._bell_clicked():
            self.stage = 1
        return self.stage / 2.0

    def check_success(self):
        self.stage_reward()
        return self.stage >= 2
