from ._base_task import Base_Task
from ._placement_judge import world_bounds, grasped_clearance
from .utils import *
import sapien
import os
import json


class attr_bind_bottle(Base_Task):
    """组合泛化测试场景（属性绑定 · 颜色）。不用于训练。

    桌上两个**同类别、不同颜色**的瓶子：
        001_bottle/base13  棕色可乐瓶（红盖）
        001_bottle/base16  绿色雪碧瓶
    指令形如「拿起绿色的瓶子」。两者类别相同，**唯一的消歧线索就是颜色** ——
    模型必须真的解析颜色词才能选对，随机选是 50%。

    为什么用瓶子（前两版的教训）：
      * attr_bind_cup_mug 用 021_cup / 039_mug，专家产出率始终 1/8。逐步探针定位到
        **第 1 步抓取**就挂，不是放置。改间距、改三角形分布、把任务简化成「拿起」都没用；
        同样是「拿起」，魔方能 8/8 —— 说明是杯子/马克杯本身难抓。
      * attr_bind_soap_box 换成肥皂/茶叶盒，能凑出颜色x类别的三元组，但探针没跑出结果。
      * 这一版用 001_bottle 的两个变体：adjust_bottle 这个任务 DM05 实测 **1.00**，
        所以这两个瓶子的可抓性是**已经被数据确认过**的，不用再赌。
      * 代价：两个瓶子类别相同，所以只测**颜色**这一个属性，测不了「颜色x类别」的
        联合绑定。但作为语言 steerability 的基础指标（能不能按颜色词选对），它是干净的。

    生成姿态和位置沿用 adjust_bottle（躺姿、左右各一侧），保证抓取在分布内。

    诊断：成功率分不清「颜色绑错」和「抓不准」，所以每条 episode 把**实际被拿起的是哪一个**
    写进 ATTR_BIND_LOG 指定的文件。
    """

    # (model_id, 颜色词)
    VARIANTS = [(13, "brown"), (16, "green")]
    # 「拿起来」的阈值。首轮用 0.10 是错的：001_bottle 长 0.248、直径 0.069，
    # 躺着时中心离桌面约 0.034，**扶正立在桌上**就到约 0.124 —— 光扶正就抬高了约 9cm，
    # 正好卡在 10cm 阈值边缘。模型执行的是它学过的 adjust_bottle 行为（扶正），
    # 于是 50 条里 28 条「什么都没举起来」，实际上是举了但没够着阈值。
    # 0.18 明显高于「站在桌上」的 0.124，只有真的离开桌面才算。
    # 高度阈值已弃用（保留仅为兼容）。实测：专家 move_by_displacement(z=0.15) 只抬升
    # 约 0.148，而「扶正立在桌上」约 +0.113 —— 两者只差 0.035，用高度根本分不开；
    # 而且阈值一旦高于 0.148，expert_check 会因为专家自己过不了判据而**无限拒绝种子**，
    # 评测直接死循环（实测发生过）。
    LIFT_H = float(os.environ.get("ATTR_LIFT_H", "0.18"))
    # 「动过」的阈值：用来判断策略**去够的是哪一个瓶子**，与举多高无关。
    # 这才是属性绑定要的信号 —— 拿对拿错，不该被抬升高度的问题污染。
    MOVED_EPS = float(os.environ.get("ATTR_MOVED_EPS", "0.05"))
    LOG_PATH = os.environ.get("ATTR_BIND_LOG", "")

    def setup_demo(self, **kwags):
        super()._init_task_env_(**kwags)

    def load_actors(self):
        # 目标随机，避免模型靠「总拿某一个」蒙对
        ti = int(np.random.randint(2))
        target_id, self.target_color = self.VARIANTS[ti]
        other_id, self.other_color = self.VARIANTS[1 - ti]

        # 目标随机落在左侧或右侧，另一个在对面。姿态沿用 adjust_bottle 的躺姿：
        # qpose_tag 0 -> 左侧用 [0.707,0,0,-0.707]，1 -> 右侧用 [0.707,0,0,0.707]
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
        """跟踪每个瓶子的最大抬升和最大位移，供事后按不同阈值重算。"""
        for k, v in self.objects.items():
            p = np.asarray(v.get_pose().p, dtype=float)
            self._maxdz[k] = max(self._maxdz[k], float(p[2] - self._z0[k]))
            self._maxdisp[k] = max(self._maxdisp[k], float(np.linalg.norm(p - self._p0[k])))

    def _log_once(self, role, reason):
        # 只在正式 rollout 记录。首轮忘了这个，expert_check 阶段的专家运行也写进了日志
        # （专家必然拿对目标），导致 50 条 episode 出现 70 条记录、target 被严重高估。
        if self._logged or not self.LOG_PATH or not getattr(self, "eval_mode", False):
            return
        self._logged = True
        try:
            with open(self.LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "episode": int(getattr(self, "test_num", -1)),
                    "target_color": self.target_color,
                    "went_for": role,          # 策略去够的是哪一个 —— 属性绑定的核心信号
                    "reason": reason,
                    "max_dz": {k: round(v, 4) for k, v in self._maxdz.items()},
                    "max_disp": {k: round(v, 4) for k, v in self._maxdisp.items()},
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def check_success(self):
        """同时要求颜色选择正确和完成拿起。

        保留原最大位移选择信号作为诊断，但位移不能证明离开桌面。
        完整成功还要求当前碰撞几何底部高于初始支撑面2cm，且接触夹爪。
        原LIFT_H不参与此检查，避免把扶正引起的原点升高当成抬起。
        """
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
