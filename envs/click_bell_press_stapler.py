from ._base_task import Base_Task
from .utils import *
import sapien
import os


class click_bell_press_stapler(Base_Task):
    """组合泛化测试场景（技能 x 技能 · 跨物体时序）。不用于训练。

    先按响铃铛（click_bell 的技能），再按下订书机（press_stapler 的技能）。
    两个物体分居左右，各由一条手臂负责。

    为什么是这一对（前两版换掉的原因都记在这）：
      * 第一版 open_microwave_put_object：微波炉是**前开口封闭腔体**，而 place_actor 从 +z
        下降接近，从上方插不进去 —— 动作原语和几何不匹配，实测开门成功但放入全部失败。
      * 第二版 adjust_bottle_put_cabinet / press_stapler_put_cabinet：前一半（扶正 / 按压）
        都稳定成功，但后一半「松手重抓 + 双臂开抽屉 + 放入」失败散布在三个步骤上。
        这和早先在 adjust_bottle_dustbin 上量到的结论一致：**松手重抓本身就不稳**。
      * 这一版把抓取和容器整个去掉：click_bell 和 press_stapler 都是**按压型原语**
        （物体静止不动、不需要抓起来），是这套环境里最稳的动作。两个技能各自都在训练的
        50 个任务里，但**从未在同一场景里被串联过**，而且是**跨物体**的时序组合
        （已有的 stapler_pad_press / adjust_bottle_dustbin 都是同物体的）。

    阶段：0 = 都没做；1 = 铃铛已按响；2 = 订书机也已按下。
    """

    def setup_demo(self, **kwags):
        super()._init_task_env_(**kwags)

    def load_actors(self):
        # 铃铛和订书机分居两侧，各由一条手臂负责，互不干扰
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
            is_static=True,       # 同 click_bell：铃铛是静态的
        )
        self.stapler_id = int(np.random.choice([0, 1, 2, 3, 4, 5, 6]))
        self.stapler = create_actor(
            scene=self,
            pose=rand_pose(xlim=[stap_x, stap_x], ylim=[-0.16, -0.06],
                           qpos=[0.5, 0.5, 0.5, 0.5], rotate_rand=True, rotate_lim=[0, np.pi, 0]),
            modelname="048_stapler",
            convex=True,
            model_id=self.stapler_id,
            is_static=True,       # 同 press_stapler：订书机是静态的（这里不需要拿起来）
        )
        self.add_prohibit_area(self.bell, padding=0.07)
        self.add_prohibit_area(self.stapler, padding=0.05)

        self.bell_arm = ArmTag("right" if self.bell.get_pose().p[0] > 0 else "left")
        self.stapler_arm = ArmTag("right" if self.stapler.get_pose().p[0] > 0 else "left")
        self._bell_close = (self.is_left_gripper_close if self.bell.get_pose().p[0] < 0
                            else self.is_right_gripper_close)
        self.stage = 0

    def play_once(self):
        # ---- 阶段 1：按铃铛（click_bell 的动作序列）----
        a = self.bell_arm
        self.move(self.grasp_actor(self.bell, arm_tag=a, pre_grasp_dis=0.1, grasp_dis=0.1, contact_point_id=0))
        self.move(self.move_by_displacement(a, z=-0.045))
        self.stage_reward()
        self.move(self.move_by_displacement(a, z=0.045))

        # ---- 阶段 2：按订书机（press_stapler 的动作序列）----
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
        """判据同 click_bell.check_success。"""
        if not self._bell_close():
            return False
        cp = self.bell.get_contact_point(0)[:3]
        for p in self.get_gripper_actor_contact_position("050_bell"):
            if np.all(np.abs(p[:2] - cp[:2]) < 0.025) and abs(p[2] - cp[2]) < 0.03:
                return True
        return False

    def _stapler_pressed(self):
        """判据同 press_stapler.check_success。"""
        cp = self.stapler.get_contact_point(2)[:3]
        for p in self.get_gripper_actor_contact_position("048_stapler"):
            if np.all(np.abs(p[:2] - cp[:2]) < 0.03) and abs(p[2] - cp[2]) < 0.03:
                return True
        return False

    def stage_reward(self):
        # stage 只升不降；stage 2 必须在 stage 1 之后才认，
        # 否则「不按铃直接按订书机」也会算成功，绕过了组合的前一半和顺序要求
        if self.stage >= 1 and self._stapler_pressed():
            self.stage = 2
        elif self.stage < 1 and self._bell_clicked():
            self.stage = 1
        return self.stage / 2.0

    def check_success(self):
        self.stage_reward()
        return self.stage >= 2
