from ._base_task import Base_Task
from .utils import *
import sapien
import os
import sys
import json
import random


class stapler_pad_press(Base_Task):
    """组合泛化：先把订书机放到垫子上（move_stapler_pad），再按下去（press_stapler）。

    两个技能都在训练集里单独出现过，这个场景只做「串起来」的组合泛化测试，不用来训练。

    选这一对的理由（对比之前 adjust_bottle + put_bottles_dustbin 那次失败）：
      * **接口干净**：move_stapler_pad 的 check_success 强制要求双爪张开，所以第一阶段
        一定以「物体已放下、双手空闲」结束；press_stapler 也正是从「订书机静止在台面上」
        开始的。瓶子那次的失败根因就是 adjust_bottle 以「握着」结束、而投桶技能从
        「伸手去抓桌上的瓶子」开始，两者之间根本不存在衔接状态。
      * 物体完全一致：都是 048_stapler，model_id 都是 [0..6]。
      * 生成四元数一致：都是 [0.5,0.5,0.5,0.5] + 绕 y 随机。
      * 选臂规则一致（x>0 用右，否则左），且垫子生成在订书机同侧，两阶段同一条手臂。
      * 两个源任务都用默认桌面偏置，不需要像 put_bottles_dustbin 那样把桌子挪 0.3。

    生成区的取舍（两处都取**子集**，不引入任何分布外）：
      * 订书机：沿用 move_stapler_pad 的原始范围 x∈[-0.25,0.25] (|x|>0.05), y∈[-0.2,0]，
        第一阶段完全在分布内。
      * 垫子：收窄到 press_stapler 的范围 ∩ 同侧 = |x|∈[0.05,0.2], y∈[-0.1,0]。
        垫子的位置决定了第一阶段结束后订书机停在哪，收窄它就保证第二阶段的**起始状态**
        落在 press_stapler 的训练区间里。这是 press_stapler 的 x∈[-0.2,0.2]、y∈[-0.1,0.05]
        与 move_stapler_pad 垫子区 y∈[-0.2,0] 的交集，两边都是子集。

    已知的唯一残余差异：press_stapler 训练时订书机是 is_static=True，而这里必须是动态的
    （第一阶段要抓起来）。外观一致，物理不同 —— 按压时它可能被推动。这是这个组合固有的，
    没法两全。

    阶段（stage_reward / self.stage）：
      0 = 还没放到垫子上
      1 = 订书机已放到垫子上且松手（判据同 move_stapler_pad.check_success）
      2 = 已按下（判据同 press_stapler.check_success）
    """

    # ---- 分阶段 instruction（机制同 adjust_bottle_dustbin，前缀换成 STAPLER_） ---- #
    # stage 0 -> move_stapler_pad 的模板；stage>=1 -> press_stapler 的模板。
    # 这次不用自己造模板：两个源任务的 json 各有 50 seen / 10 unseen，占位符也对得上
    # （move_stapler_pad 用 {A}{B}{a}，press_stapler 用 {A}{a}），直接复用。
    #
    # 注意：切换信号是 self.stage，即仿真的特权状态 —— 测的是「给对指令能不能接上」，
    # 不是端到端能力。报数时要标注是 oracle 切换。
    STAGED_INSTRUCTION = os.environ.get("STAPLER_STAGED_INSTRUCTION", "1") == "1"
    # move  = 第一阶段说 move_stapler_pad 的话（默认）
    # same  = 整条 episode 只说 press_stapler 的话，完全不提放垫子。
    #         这一档没有阶段切换、不读 stage，是唯一**不含 oracle 成分**的设置。
    STAGE1_TEMPLATE = os.environ.get("STAPLER_STAGE1_TEMPLATE", "move")
    # seen | unseen，默认和 policy/WLA/deploy_policy.yml 的 instruction_type 一致
    INSTRUCTION_TYPE = os.environ.get("STAPLER_INSTRUCTION_TYPE", "unseen")
    # 调试时把语言这一维的方差摁掉：每条 episode 都用同一句（物体描述也固定）
    INSTRUCTION_PIN = os.environ.get("STAPLER_INSTRUCTION_PIN", "0") == "1"

    def setup_demo(self, **kwags):
        # 两个源任务都是默认偏置，不挪桌子
        super()._init_task_env_(**kwags)

    def load_actors(self):
        # ---- 订书机：move_stapler_pad 的原始生成区 ----
        def sample_stapler():
            return rand_pose(
                xlim=[-0.25, 0.25],
                ylim=[-0.2, 0.0],
                qpos=[0.5, 0.5, 0.5, 0.5],
                rotate_rand=True,
                rotate_lim=[0, np.pi, 0],
            )

        rand_pos = sample_stapler()
        for _ in range(100):
            if abs(rand_pos.p[0]) >= 0.05:
                break
            rand_pos = sample_stapler()

        self.stapler_id = np.random.choice([0, 1, 2, 3, 4, 5, 6], 1)[0]
        # 这里**不能** is_static=True（press_stapler 那边是静态的），第一阶段要抓起来
        self.stapler = create_actor(
            scene=self,
            pose=rand_pos,
            modelname="048_stapler",
            convex=True,
            model_id=self.stapler_id,
        )

        # ---- 垫子：收窄到 press_stapler 的区间 ∩ 订书机同侧 ----
        xlim = [0.05, 0.2] if rand_pos.p[0] > 0 else [-0.2, -0.05]

        def sample_pad():
            return rand_pose(xlim=xlim, ylim=[-0.1, 0.0], qpos=[1, 0, 0, 0], rotate_rand=False)

        target_rand_pose = sample_pad()
        # 原任务这里是无界 while，范围收窄后有空转风险，加上限；兜底把垫子推到 x 区间远端
        for _ in range(200):
            d = np.sqrt((target_rand_pose.p[0] - rand_pos.p[0])**2 + (target_rand_pose.p[1] - rand_pos.p[1])**2)
            if d >= 0.1:
                break
            target_rand_pose = sample_pad()
        else:
            far_x = xlim[1] if abs(xlim[1] - rand_pos.p[0]) > abs(xlim[0] - rand_pos.p[0]) else xlim[0]
            target_rand_pose = sapien.Pose([far_x, -0.05, target_rand_pose.p[2]], [1, 0, 0, 0])

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
        self.color_name, self.color_value = color_items[np.random.choice(len(color_items))]

        self.pad = create_box(
            scene=self.scene,
            pose=target_rand_pose,
            half_size=[0.055, 0.03, 0.0005],
            color=self.color_value,
            name="box",
        )
        self.add_prohibit_area(self.stapler, padding=0.1)
        self.add_prohibit_area(self.pad, padding=0.15)

        self.pad_pose = self.pad.get_pose().p.tolist() + [0.707, 0, 0, 0.707]
        # 两阶段同一条手臂（两个源任务的选臂规则本来就一致）
        self.arm_tag = ArmTag("right" if rand_pos.p[0] > 0 else "left")
        self.stage = 0

        # 分阶段 instruction 的占位符取值。不能等 play_once 去填 self.info：
        # eval 的正式 rollout 不跑 play_once（只有 expert_check 那一遍跑），
        # 而 load_actors 每次 setup_demo 都会走到。
        self._stapler_asset = f"048_stapler/base{self.stapler_id}"
        self._stage_instructions = None

    # ------------------------------------------------------------------ #
    # 专家演示：eval 前的 expert_check 会跑这个来确认种子可用
    # ------------------------------------------------------------------ #
    def play_once(self):
        arm_tag = self.arm_tag

        # ---- 阶段 1：放到垫子上（move_stapler_pad 的动作序列） ----
        self.move(self.grasp_actor(self.stapler, arm_tag=arm_tag, pre_grasp_dis=0.1))
        self.move(self.move_by_displacement(arm_tag, z=0.1, move_axis="arm"))
        self.move(
            self.place_actor(
                self.stapler,
                target_pose=self.pad_pose,
                arm_tag=arm_tag,
                pre_dis=0.1,
                dis=0.0,
                constrain="align",
            ))
        # 抬手离开：place_actor 默认松手，但要让手离开订书机上方，
        # 第二阶段的 grasp_actor 才好从头规划（也让 stage 1 的判据稳定成立）
        self.move(self.move_by_displacement(arm_tag, z=0.1))

        # 在这里显式锁 stage 1。eval 里 check_success 每步都调、自然会锁上，但
        # collect_data / expert_check 只在 play_once **结束后**调一次 —— 那一刻夹爪
        # 正按在订书机上（闭合），_on_pad 要求的「双爪张开」不成立，stage 就永远停在 0，
        # stage 2 的门槛会把所有种子判死。
        #
        # 采样两次并中间沉降：_on_pad 是瞬时判据，松手瞬间物体还在动，实测见过
        # 「终点位置明明在容差内、也确实按下去了，但 stage 没锁上」的假阴性。
        self.stage_reward()
        self.delay(4)
        self.stage_reward()

        # ---- 阶段 2：按下去（press_stapler 的动作序列） ----
        self.move(
            self.grasp_actor(self.stapler, arm_tag=arm_tag, pre_grasp_dis=0.1, grasp_dis=0.1, contact_point_id=2))
        self.move(self.close_gripper(arm_tag=arm_tag))
        self.move(
            self.grasp_actor(self.stapler, arm_tag=arm_tag, pre_grasp_dis=0.02, grasp_dis=0.02, contact_point_id=2))

        self.info["info"] = {
            "{A}": self._stapler_asset,
            "{B}": self.color_name,
            "{a}": str(arm_tag),
        }
        return self.info

    # ------------------------------------------------------------------ #
    # 判定
    # ------------------------------------------------------------------ #
    def _on_pad(self):
        """订书机已放到垫子上并松手 —— 判据与 move_stapler_pad.check_success 一致。"""
        stapler_pose = self.stapler.get_pose().p
        stapler_qpose = np.abs(self.stapler.get_pose().q)
        target_pos = self.pad.get_pose().p
        # 容差按**垫子实际尺寸**（half_size=[0.055, 0.03]），不再用和垫子无关的 ±2cm。
        # 用户实测：视频里明明放上去了却判失败，就是位置偏了一两厘米被这个小方框卡掉。
        # 朝向项也去掉：move_stapler_pad 原判据要求订书机落在一个特定朝向上，
        # 但这里第一段的目的是「放到垫子上」，朝向不该成为门槛（第二段按压才是重点）。
        eps = np.array([0.055, 0.035, 0.02])
        return bool(
            np.all(np.abs(stapler_pose - target_pos) < eps)
            and self.robot.is_left_gripper_open()
            and self.robot.is_right_gripper_open())

    def _pressed(self):
        """已按下 —— 判据与 press_stapler.check_success 一致。"""
        stapler_pose = self.stapler.get_contact_point(2)[:3]
        eps = [0.03, 0.03]
        for position in self.get_gripper_actor_contact_position("048_stapler"):
            if (np.all(np.abs(position[:2] - stapler_pose[:2]) < eps) and abs(position[2] - stapler_pose[2]) < 0.03):
                return True
        return False

    def stage_reward(self):
        # stage 只升不降。stage 2 必须在 stage 1 之后才认：否则在订书机原地就按一下
        # 也会被判成功，那就绕过了「先搬到垫子上」这一半。
        if self.stage >= 1 and self._pressed() and np.all(
                np.abs(self.stapler.get_pose().p - self.pad.get_pose().p) < np.array([0.055, 0.035, 0.02])):
            self.stage = 2
        elif self.stage < 1 and self._on_pad():
            self.stage = 1
        return self.stage / 2.0

    def check_success(self):
        self.stage_reward()
        return self.stage >= 2

    # ------------------------------------------------------------------ #
    # 分阶段 instruction
    # ------------------------------------------------------------------ #
    @staticmethod
    def _instruction_gen():
        """拿到 description/utils/generate_episode_instructions。

        eval_policy.py 自己会 sys.path.append("./description/utils")，但那依赖调用方
        的 cwd；这里按 __file__ 定位，collect_data / 单跑探针也能用。
        """
        utils_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "description", "utils")
        if utils_dir not in sys.path:
            sys.path.append(utils_dir)
        from generate_episode_instructions import generate_episode_descriptions
        return generate_episode_descriptions

    @staticmethod
    def _repo_root():
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _pick_object_desc(self, asset, rng):
        """给资产 id 挑一句自然语言描述，返回带冠词的形式。

        本来 replace_placeholders 会自己去 objects_description 里抽，但那是两个阶段
        各抽各的 —— 同一条 episode 里同一个订书机，前后可能被叫成两个名字。
        所以描述在这里一次性定好，再以字面串传进去（值里不带 '/' 就不会再被当路径查表）。
        """
        path = os.path.join(self._repo_root(), "description", "objects_description", asset + ".json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pool = data.get(self.INSTRUCTION_TYPE) or data.get("seen") or []
        return f"the {rng.choice(pool)}" if pool else "the stapler"

    def _build_stage_instructions(self):
        """给两个阶段各生成一句 instruction，整条 episode 固定不变。

        不能每个控制周期现抽 —— get_instruction 是每步都调的，现抽会让指令逐帧抖动。
        """
        gen = self._instruction_gen()
        rng = random.Random(0) if self.INSTRUCTION_PIN else random.Random()
        if self.INSTRUCTION_PIN:
            # filter_instructions 内部用的是全局 random.shuffle，得连它一起摁住
            random.seed(0)

        stapler = self._pick_object_desc(self._stapler_asset, rng)
        arm = str(self.arm_tag)
        # 占位符集合必须和模板精确匹配（{a} 可缺省）
        stage2 = ("press_stapler", {"{A}": stapler, "{a}": arm})
        stage1 = (("move_stapler_pad", {"{A}": stapler, "{B}": self.color_name, "{a}": arm})
                  if self.STAGE1_TEMPLATE != "same" else stage2)

        def one(task_name, params):
            cands = gen(task_name, [params], 100)
            pool = cands[0].get(self.INSTRUCTION_TYPE, []) if cands else []
            if not pool:  # unseen 为空就退回 seen
                pool = cands[0].get("seen", []) if cands else []
            if not pool:
                return None
            return pool[0] if self.INSTRUCTION_PIN else str(rng.choice(pool))

        if self.STAGE1_TEMPLATE == "same":
            # 真的只有一句：两个阶段返回同一个字符串
            only = one(*stage2)
            return None if only is None else (only, only)

        first, second = one(*stage1), one(*stage2)
        return None if (first is None or second is None) else (first, second)

    def set_instruction(self, instruction=None):
        # 仍然把 eval_policy 传进来的复合句存下来（日志/回退用）
        super().set_instruction(instruction=instruction)
        self._stage_instructions = None
        if not self.STAGED_INSTRUCTION:
            return
        try:
            self._stage_instructions = self._build_stage_instructions()
        except Exception as e:
            print(f"[stapler_pad_press] 分阶段 instruction 生成失败，回退复合句: {e}")
            self._stage_instructions = None

    def get_instruction(self, instruction=None):
        if not self.STAGED_INSTRUCTION or not self._stage_instructions:
            return super().get_instruction(instruction=instruction)
        self.stage_reward()  # 刷新 self.stage（只升不降）
        return self._stage_instructions[0 if self.stage < 1 else 1]
