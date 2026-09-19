"""组合泛化测试场景（技能 x 空间关系）。

从 place_a2b_left 克隆，**只改物体池**，其余全部保持一致。不用于训练。
"""
import glob
from ._base_task import Base_Task
from .utils import *
import sapien
import math
from ._GLOBAL_CONFIGS import *
from copy import deepcopy
import numpy as np


class place_a2b_left_novel(Base_Task):

    def setup_demo(self, **kwags):
        super()._init_task_env_(**kwags)

    def load_actors(self):

        def get_available_model_ids(modelname):
            asset_path = os.path.join("assets/objects", modelname)
            json_files = glob.glob(os.path.join(asset_path, "model_data*.json"))

            available_ids = []
            for file in json_files:
                base = os.path.basename(file)
                try:
                    idx = int(base.replace("model_data", "").replace(".json", ""))
                    available_ids.append(idx)
                except ValueError:
                    continue
            return available_ids

        # 组合泛化 · 技能 x 空间关系：
        # 「把 A 放到 B 左边」这个技能在训练里见过，但只在下面这 12 个物体上见过：
        #   047_mouse 048_stapler 050_bell 057_toycar 073_rubikscube 075_bread
        #   077_phone 081_playingcards 086_woodenblock 112_tea-box 113_coffee-box 107_soap
        # 这里换成与之**完全不相交**的一组，其余逻辑（生成区、动作、判据）一字不动，
        # 所以唯一变化的变量就是物体身份 —— 测的是空间关系能否迁移到没见过的物体。
        # 收窄后的池子：首轮用 10 个物体时专家只有 5/35（14%），失败集中在
        # 抓取点配置不全的物体上。这里只保留 contact_points_pose/group/mask 三件套
        # 齐全的物体和变体 —— 仍与原任务的 12 个物体完全不相交，测试性质不变。
        object_list = ["039_mug", "021_cup", "002_bowl"]
        GOOD_IDS = {"039_mug": [0, 1, 10, 11, 12, 2, 3, 4, 5, 6, 7, 8, 9], "021_cup": [0, 1, 2, 3, 4, 5], "002_bowl": [1, 2, 3, 4, 5, 6, 7]}

        try_num, try_lim = 0, 100
        while try_num <= try_lim:
            rand_pos = rand_pose(
                xlim=[-0.22, 0.22],
                ylim=[-0.2, 0.0],
                qpos=[0.5, 0.5, 0.5, 0.5],
                rotate_rand=True,
                rotate_lim=[0, 3.14, 0],
            )
            # B（参照物）**永远摆在右边**：任务是「把 A 放到 B 的左边」，
            # 左边才留得下空间。和 place_a2b_right_novel 是镜像的同一处修正。
            xlim = [0.10, 0.20]
            target_rand_pose = rand_pose(
                xlim=xlim,
                ylim=[-0.2, 0.0],
                qpos=[0.5, 0.5, 0.5, 0.5],
                rotate_rand=True,
                rotate_lim=[0, 3.14, 0],
            )
            while (np.sqrt((target_rand_pose.p[0] - rand_pos.p[0])**2 + (target_rand_pose.p[1] - rand_pos.p[1])**2)
                   < 0.1) or (np.abs(target_rand_pose.p[1] - rand_pos.p[1]) < 0.1):
                target_rand_pose = rand_pose(
                    xlim=xlim,
                    ylim=[-0.2, 0.0],
                    qpos=[0.5, 0.5, 0.5, 0.5],
                    rotate_rand=True,
                    rotate_lim=[0, 3.14, 0],
                )
            try_num += 1

            distance = np.sqrt(np.sum((rand_pos.p[:2] - target_rand_pose.p[:2])**2))

            if distance > 0.19 or rand_pos.p[0] > target_rand_pose.p[0]:
                break

        if try_num > try_lim:
            raise "Actor create limit!"

        self.selected_modelname_A = np.random.choice(object_list)

        available_model_ids = GOOD_IDS[self.selected_modelname_A]
        if not available_model_ids:
            raise ValueError(f"No available model_data.json files found for {self.selected_modelname_A}")

        self.selected_model_id_A = np.random.choice(available_model_ids)
        self.object = create_actor(
            scene=self,
            pose=rand_pos,
            modelname=self.selected_modelname_A,
            convex=True,
            model_id=self.selected_model_id_A,
        )

        self.selected_modelname_B = np.random.choice(object_list)
        while self.selected_modelname_B == self.selected_modelname_A:
            self.selected_modelname_B = np.random.choice(object_list)

        available_model_ids = GOOD_IDS[self.selected_modelname_B]
        if not available_model_ids:
            raise ValueError(f"No available model_data.json files found for {self.selected_modelname_B}")

        self.selected_model_id_B = np.random.choice(available_model_ids)

        self.target_object = create_actor(
            scene=self,
            pose=target_rand_pose,
            modelname=self.selected_modelname_B,
            convex=True,
            model_id=self.selected_model_id_B,
        )
        self.object.set_mass(0.05)
        self.target_object.set_mass(0.05)
        self.add_prohibit_area(self.object, padding=0.05)
        self.add_prohibit_area(self.target_object, padding=0.1)
        self._reference_start = self.target_object.get_pose().p.copy()

    def play_once(self):
        # Determine which arm to use based on object's x position
        arm_tag = ArmTag("right" if self.object.get_pose().p[0] > 0 else "left")

        # Grasp the object with specified arm
        self.move(self.grasp_actor(self.object, arm_tag=arm_tag, pre_grasp_dis=0.1))
        # Lift the object upward by 0.1 meters along z-axis using arm movement
        self.move(self.move_by_displacement(arm_tag=arm_tag, z=0.1, move_axis="arm"))

        # Get target pose and adjust x position to place object to the left of target
        target_pose = self.target_object.get_pose().p.tolist()
        target_pose[0] -= 0.13

        # Place the object at the adjusted target position
        self.move(self.place_actor(self.object, arm_tag=arm_tag, target_pose=target_pose))

        # Record task information including object IDs and used arm
        self.info["info"] = {
            "{A}": f"{self.selected_modelname_A}/base{self.selected_model_id_A}",
            "{B}": f"{self.selected_modelname_B}/base{self.selected_model_id_B}",
            "{a}": str(arm_tag),
        }
        return self.info

    def check_success(self):
        object_pose = self.object.get_pose().p
        target_pos = self.target_object.get_pose().p
        distance = np.sqrt(np.sum((object_pose[:2] - target_pos[:2])**2))
        if abs(object_pose[2] - target_pos[2]) > 0.10:
            return False
        if np.linalg.norm(target_pos - self._reference_start) > 0.05:
            return False
        return np.all(distance < 0.2 and distance > 0.08 and object_pose[0] < target_pos[0]
                      and abs(object_pose[1] - target_pos[1]) < 0.09 and self.robot.is_left_gripper_open()
                      and self.robot.is_right_gripper_open())
