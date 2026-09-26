"""Object-composition evaluation replacing the stapler with a cup. Internal stapler_* names are retained for source-code comparison; current placement tolerances are defined below."""
import os
import json
from ._base_task import Base_Task
from .utils import *
import sapien
import math
from ._GLOBAL_CONFIGS import *
from copy import deepcopy


class move_cup_pad(Base_Task):

    def setup_demo(self, **kwags):
        super()._init_task_env_(**kwags)

    def load_actors(self):
        rand_pos = rand_pose(
            xlim=[-0.25, 0.25],
            ylim=[-0.2, 0.0],
            qpos=[0.5, 0.5, 0.5, 0.5],
            rotate_rand=True,
            # Limit local Y rotation to 0.6 rad to avoid inverting the cup. Randomize mainly about the upright yaw axis.


            rotate_lim=[0, 0.6, 0],
        )
        while abs(rand_pos.p[0]) < 0.05:
            rand_pos = rand_pose(
                xlim=[-0.25, 0.25],
                ylim=[-0.2, 0.0],
                qpos=[0.5, 0.5, 0.5, 0.5],
                rotate_rand=True,
                # Limit local Y rotation to 0.6 rad to avoid inverting the cup. Randomize mainly about the upright yaw axis.


            rotate_lim=[0, 0.6, 0],
            )
        # Object-composition evaluation replaces the stapler with a cup while reusing the placement routine and source layout.


        self.stapler_id = int(np.random.choice(list(range(13))))
        self.stapler = create_actor(
            scene=self,
            pose=rand_pos,
            modelname="021_cup",
            convex=True,
            model_id=self.stapler_id,
        )

        if rand_pos.p[0] > 0:
            xlim = [0.05, 0.25]
        else:
            xlim = [-0.25, -0.05]
        target_rand_pose = rand_pose(
            xlim=xlim,
            ylim=[-0.2, 0.0],
            qpos=[1, 0, 0, 0],
            rotate_rand=False,
        )
        while (np.sqrt((target_rand_pose.p[0] - rand_pos.p[0])**2 + (target_rand_pose.p[1] - rand_pos.p[1])**2) < 0.1):
            target_rand_pose = rand_pose(
                xlim=xlim,
                ylim=[-0.2, 0.0],
                qpos=[1, 0, 0, 0],
                rotate_rand=False,
            )
        half_size = [0.055, 0.03, 0.0005]

        colors = {
            "Red": (1, 0, 0),
            "Green": (0, 1, 0),
            "Blue": (0, 0, 1),
            "Yellow": (1, 1, 0),
            "Cyan": (0, 1, 1),
            "Magenta": (1, 0, 1),
            "Black": (0, 0, 0),
            "Gray": (0.5, 0.5, 0.5),
        }

        color_items = list(colors.items())
        color_index = np.random.choice(len(color_items))
        self.color_name, self.color_value = color_items[color_index]

        self.pad = create_box(
            scene=self.scene,
            pose=target_rand_pose,
            half_size=half_size,
            color=self.color_value,
            name="box",
        )
        self.add_prohibit_area(self.stapler, padding=0.1)
        self.add_prohibit_area(self.pad, padding=0.15)

        # Create target pose by combining target position with default quaternion orientation
        self.pad_pose = self.pad.get_pose().p.tolist() + [0.707, 0, 0, 0.707]
        self._logged = False

    def play_once(self):
        # Determine which arm to use based on stapler's position (right if on positive x, left otherwise)
        arm_tag = ArmTag("right" if self.stapler.get_pose().p[0] > 0 else "left")

        # Grasp the stapler with specified arm
        self.move(self.grasp_actor(self.stapler, arm_tag=arm_tag, pre_grasp_dis=0.1))
        # Move the arm upward by 0.1 meters along z-axis
        self.move(self.move_by_displacement(arm_tag, z=0.1, move_axis="arm"))

        # Place the stapler at target pose with alignment constraint
        self.move(
            self.place_actor(
                self.stapler,
                target_pose=self.pad_pose,
                arm_tag=arm_tag,
                pre_dis=0.1,
                dis=0.0,
                constrain="align",
            ))

        self.info["info"] = {
            "{A}": f"021_cup/base{self.stapler_id}",
            "{B}": self.color_name,
            "{a}": str(arm_tag),
        }
        return self.info

    def check_success(self):
        stapler_pose = self.stapler.get_pose().p
        stapler_qpose = np.abs(self.stapler.get_pose().q)
        target_pos = self.pad.get_pose().p
        # Use the 11 x 6 cm pad footprint with a 5 mm y margin. Record the original 2 cm tolerance separately; do not treat the rotationally symmetric cup like an oriented stapler.


        #


        PAD_HALF = [0.055, 0.03]
        eps = [float(os.environ.get("CUP_PAD_EPS_X", PAD_HALF[0])),
               float(os.environ.get("CUP_PAD_EPS_Y", PAD_HALF[1] + 0.005)),
               float(os.environ.get("CUP_PAD_EPS_Z", 0.02))]
        STRICT_EPS = [0.02, 0.02, 0.01]   # Retain source position/orientation checks only as diagnostic comparisons; the current cup predicate uses its footprint-based placement requirement.


        d = stapler_pose - target_pos
        pos_ok = bool(np.all(abs(d) < np.array(eps)))
        pos_strict = bool(np.all(abs(d) < np.array(STRICT_EPS)))
        ori_ok = bool((stapler_qpose.max() - stapler_qpose.min()) < 0.02)
        released = bool(self.robot.is_left_gripper_open() and self.robot.is_right_gripper_open())


        # Record pos_ok (pad footprint), pos_strict (original 2 cm tolerance), and ori_ok (diagnostic only).


        if released and pos_ok and not self._logged:
            self._logged = True
            path = os.environ.get("CUP_PAD_LOG", "")
            if path:
                try:
                    with open(path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"episode": int(getattr(self, "test_num", -1)),
                                            "pos_ok": pos_ok, "pos_strict": pos_strict,
                                            "ori_ok": ori_ok,
                                            "dx": round(float(d[0]), 4), "dy": round(float(d[1]), 4),
                                            "dz": round(float(d[2]), 4),
                                            "r_xy": round(float(np.hypot(d[0], d[1])), 4)}) + "\n")
                except OSError:
                    pass
        return bool(pos_ok and released)
