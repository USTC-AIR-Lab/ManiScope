from ._base_task import Base_Task
from .utils import *
import sapien
import os
import random
import sys
import json


class adjust_bottle_dustbin(Base_Task):
    """组合泛化任务：先把躺着的瓶子扶正（adjust_bottle），再投进垃圾桶（put_bottles_dustbin）。

    两个技能都在训练集里单独出现过，这个场景只做「串起来」的组合泛化测试，不用来训练。

    与两个原任务的对齐关系（改之前先看这里）：
      * 瓶子：001_bottle（adjust_bottle 用的那个），躺姿、model_id 13/16 —— 和 adjust_bottle
        完全一致。put_bottles_dustbin 用的是 114_bottle，所以「投垃圾桶」这一段面对的是
        没见过的瓶型，这正是要测的组合泛化的一部分。设 COMBO_BOTTLE=114_bottle 可以换成
        另一侧的配置。
      * 生成位置固定在**左侧**（原 adjust_bottle 是左右各一半概率）。垃圾桶在 x=-0.45，
        左手扶正后不用换手就能直接投，右手那一支在这个组合里没有意义。
      * 桌子用 put_bottles_dustbin 的 table_xy_bias=[0.3, 0]，否则垃圾桶放不下。
        注意这让桌面相对 adjust_bottle 训练时平移了，属于这个组合场景固有的分布偏移。

    阶段（stage_reward / self.stage）：
      0 = 还没扶正
      1 = 瓶子在左侧被扶正；默认允许继续持瓶，不要求松手后自立
      2 = 瓶子在垃圾桶里（判据同 put_bottles_dustbin）
    """

    # 扶正后是否松手再重新抓。默认 **不松手**。
    #
    # 落点从 y=-0.12 挪到 y=+0.10 后，重抓的规划成功率确实大幅改善（12 个种子里
    # plan=False 从 10 个降到 3 个），但专家演示整体仍然不稳：collect_data 跑 5 条
    # 需要 17 次尝试，而不松手是 5/5。失败集中在松手后的重抓 —— 要么规划不出来，
    # 要么抓空/把瓶子碰飞（实测见过瓶子被推到桌沿 y=+0.35 甚至掉到地上）。
    #
    # 这对评测是有害的：eval_policy.py:316 只接受 plan_success 且专家 check_success
    # 的种子，29% 的产出率意味着种子集会被筛成「恰好重抓得动」的那一小撮，引入选择偏差。
    #
    # 所以默认关掉。想测「松手-重抓」那一版（技能交接更干净，投桶段起始状态更贴近
    # put_bottles_dustbin 的训练分布）就 COMBO_RELEASE_AFTER_ADJUST=1，但先修重抓。
    RELEASE_AFTER_ADJUST = os.environ.get("COMBO_RELEASE_AFTER_ADJUST", "0") == "1"
    BOTTLE_MODEL = os.environ.get("COMBO_BOTTLE", "001_bottle")
    # 桌上放哪一个瓶子。原来是 np.random.choice([13, 16])，13=可乐（棕色红盖），
    # 16=绿瓶（雪碧）。固定成 13 可以把「瓶型」这一维的方差摁掉，也让
    # 「垃圾桶里已经有几个瓶子」那个设定读起来自洽（可乐是最后丢的那个）。
    # 想恢复随机就 COMBO_BOTTLE_ID=random。
    BOTTLE_ID = os.environ.get("COMBO_BOTTLE_ID", "13")

    # 垃圾桶里预先放几个瓶子。
    #
    # put_bottles_dustbin 是连丢三个，所以它「丢最后一个」时的画面是：桶里已经躺着
    # 两个瓶子、桌上只剩一个。而本任务原来是空桶 + 一个瓶子 —— 对投桶技能来说，
    # 桶里的内容物是视野中很显眼的一块，空桶属于分布外。预放 2 个（用
    # put_bottles_dustbin 的 114_bottle，id 1/2）就把画面对齐到「丢第三个」那一帧。
    #
    # 这些瓶子只是布景：不参与 check_success（判定只看 self.bottle），
    # 也不进 prohibit area（它们在 x=-0.45，离瓶子生成区 [-0.12,-0.08] 很远）。
    DUSTBIN_PREFILL = int(os.environ.get("COMBO_DUSTBIN_PREFILL", "2"))

    # ---- 分阶段 instruction ----------------------------------------------- #
    # 组合任务自己的 instruction 是复合句（"Stand the fallen {A} up, then throw it
    # away into {B}."），这种句式两个源任务的训练集里都没有 —— 语言这一路也是 OOD，
    # 和视觉/位姿的 OOD 叠在一起。开着这个开关就按 stage 下发单技能指令：
    #   stage 0（还没扶正） -> adjust_bottle 的模板
    #   stage >=1（已扶正） -> 单瓶版投桶模板（_combo_stage_dustbin.json）
    # 两边都是模型训练时见过的句式。
    #
    # 注意：切换信号用的是 self.stage，也就是仿真的特权状态。所以这测的是「给对
    # 指令能不能接上」，不是端到端能力（策略自己判断该换阶段了）。报数时要说清楚
    # 是 oracle 切换。想关掉退回复合句就 COMBO_STAGED_INSTRUCTION=0。
    STAGED_INSTRUCTION = os.environ.get("COMBO_STAGED_INSTRUCTION", "1") == "1"
    # seen | unseen，默认和 policy/WLA/deploy_policy.yml 的 instruction_type 一致
    INSTRUCTION_TYPE = os.environ.get("COMBO_INSTRUCTION_TYPE", "unseen")
    # 调试时把语言这一维的方差摁掉：每条 episode 都用同一句（物体描述也固定）。
    # 不开的话每条 episode 随机抽模板 + 随机抽物体描述，50 条里语言的方差会盖掉信号。
    INSTRUCTION_PIN = os.environ.get("COMBO_INSTRUCTION_PIN", "0") == "1"

    # 第二阶段用哪套措辞：
    #   hold  = 搬运措辞（drop/put/place/move/transfer），不蕴含抓取动作（默认）
    #   throw = 丢弃措辞（throw/toss/discard/dispose/dump），语义最直白
    #   grasp = 忠实移植 put_bottles_dustbin 的单瓶版，含 Pick up / Grab / Take
    #
    # 默认 hold 的理由：策略进入 stage 2 时瓶子已经在手里，而 grasp 版会把它送回
    # put_bottles_dustbin 的**抓取段** —— 那些瓶子生成在 y in [+0.03, +0.23]（靠前），
    # 于是策略伸手向前去抓一个已经在自己手里的瓶子，抓空且不松手。实测现象就是这个。
    #
    # hold 与 throw 的取舍：hold 的每个动词都能在 put_bottles_dustbin 的训练模板里
    # 找到（drop / put / place / move / transfer 都出现过）；throw 里除了 toss
    # （只在 unseen 出现过一次）之外，discard / dispose / dump / get rid of 训练时
    # **一次都没见过**，只出现在 adjust_bottle_dustbin.json 这个从未参与训练的
    # 组合任务 json 里。throw 版语义更直白，但措辞离训练分布更远 —— 值得 A/B，别默认。
    STAGE2_TEMPLATE = os.environ.get("COMBO_STAGE2_TEMPLATE", "hold")

    # 第一阶段（还没扶正时）说什么：
    #   adjust = adjust_bottle 的模板，即「把瓶子扶正拿起来」（默认）
    #   same   = 和第二阶段同一句，也就是**整条 episode 只有一句「放进垃圾桶」**，
    #            完全不提扶正，看模型会不会自己补上扶正这一步
    #
    # same 模式下没有任何阶段切换，也就不再依赖仿真的 stage 信号 —— 这是这里唯一
    # **不含 oracle 成分**的指令设置，端到端可比性最好。
    #
    # 配 same 用哪套 STAGE2_TEMPLATE：此时瓶子还躺在桌上、需要被抓起来，所以语义上
    # 对得上的是 grasp（"Pick up {A} and toss it into {B}."），它也最接近
    # put_bottles_dustbin 训练时的原话。hold / throw 那两套预设瓶子已在手里，
    # 配 same 会在开头就自相矛盾。
    STAGE1_TEMPLATE = os.environ.get("COMBO_STAGE1_TEMPLATE", "adjust")
    _STAGE2_TASKS = {
        "hold": "_combo_stage_dustbin_hold",
        "throw": "_combo_stage_dustbin_throw",
        "grasp": "_combo_stage_dustbin",
    }

    # ---- stage 1->2 的脚本桥接 --------------------------------------------- #
    # 扶正完成时末端的 x / y / 姿态实测已经落在 put_bottles_dustbin 搬运段起点的
    # 分布内（x -0.30~-0.19, y -0.31~+0.07, quat 命中 (0.70,0,0,0.71) 那一簇），
    # 只有 z 偏高 0.02~0.10（那边 0.92~0.945，这边 0.963~1.045）。
    # 开着这个就在交接时把末端**保持 xy 和姿态不变**、单独降到 BRIDGE_Z，
    # 再把控制权交回策略。默认关。
    #
    # 这是 oracle 干预（用了仿真的 stage 信号，动作也是脚本而非策略产生的），
    # 报数时必须和端到端结果分开写。
    STAGE2_BRIDGE = os.environ.get("COMBO_STAGE2_BRIDGE", "0") == "1"
    BRIDGE_Z = float(os.environ.get("COMBO_BRIDGE_Z", "0.93"))

    def setup_demo(self, **kwags):
        # 和 put_bottles_dustbin 一致：桌子往 +x 挪，给左边的垃圾桶留位置。
        # 0.3 -> 0.38：用户实测「每次释放 bottle 的位置都打到桌子」。垃圾桶固定在
        # x=-0.45，桌沿离它太近，策略在桶上方松手时瓶子先磕到桌角再弹开。
        # table_xy_bias 只移动桌子本身（_base_task.py:308），瓶子/垃圾桶都是世界坐标，
        # 所以这一步纯粹是把桌沿往右让开，不改变机器人和物体的相对关系。
        super()._init_task_env_(table_xy_bias=[float(os.environ.get("COMBO_TABLE_BIAS", "0.38")), 0], **kwags)

    def load_actors(self):
        # 躺姿 + 左侧，对应 adjust_bottle 里 qpose_tag == 0 的那一支
        self.qpose_tag = 0
        self.model_id = (int(np.random.choice([13, 16]))
                         if self.BOTTLE_ID == "random" else int(self.BOTTLE_ID))
        self.bottle = rand_create_actor(
            self,
            xlim=[-0.12, -0.08],
            ylim=[-0.13, -0.08],
            zlim=[0.752],
            rotate_rand=True,
            qpos=[0.707, 0.0, 0.0, -0.707],
            modelname=self.BOTTLE_MODEL,
            convex=True,
            rotate_lim=(0, 0, 0.4),
            model_id=self.model_id,
        )
        self.delay(4)
        self.add_prohibit_area(self.bottle, padding=0.15)

        self.dustbin = create_actor(
            self.scene,
            pose=sapien.Pose([-0.45, 0, 0], [0.5, 0.5, 0.5, 0.5]),
            modelname="011_dustbin",
            convex=True,
            is_static=True,
        )
        self.delay(2)

        # 桶里预先躺着的瓶子（布景，见 DUSTBIN_PREFILL 注释）
        #
        # 必须是 **static**：动态瓶子在桶里会一直缓慢滚动，而 check_stable 会遍历场景
        # 里所有 actor、对最后 200 帧做姿态差检查（>3 度就判不稳），实测 5/5 个种子
        # 全部 UnStableError，任务直接跑不了。它们只是布景，不需要能动。
        #
        # 高度按实测选：put_bottles_dustbin 真丢进去的瓶子静止后 p[2] 落在 0.20~0.33。
        # 114_bottle 横躺时长 1.799*0.12 = 0.216 m，直径 0.576*0.12 = 0.069 m。
        self.prefill_bottles = []
        for i in range(max(0, self.DUSTBIN_PREFILL)):
            b = create_actor(
                self.scene,
                pose=sapien.Pose([-0.45 + 0.05 * i, 0.07 - 0.14 * i, 0.22 + 0.05 * i],
                                 [0.707, 0.0, 0.707, 0.0]),   # 横躺
                modelname="114_bottle",
                convex=True,
                model_id=i + 1,                               # 和 put_bottles_dustbin 的 id 一致
                is_static=True,
            )
            self.prefill_bottles.append(b)

        # 扶正的落点。原值是 adjust_bottle 的 [-0.25, -0.12, 0.95]。
        #
        # 注意这个量**只影响专家演示**（play_once），而 play_once 在 eval 里只用来过
        # expert_check 筛种子，正式 rollout 不跑。所以改它动不了策略的行为，只会换掉
        # 被接受的种子集合。曾经以为改这里能把「投桶段的起始状态」拉回分布内 —— 那是
        # 错的，策略把瓶子放在哪是 adjust_bottle 训练出来的，env 改不动。
        #
        # 实测（各 4 个种子，量的是末端位姿而不是瓶子生成位置）：
        #   put_bottles_dustbin 搬运段起点  x -0.30~-0.19  y -0.31~+0.07  z 0.92~0.945
        #   本任务扶正完成时                x -0.22        y -0.035~-0.07 z 0.963~1.045
        # x / y / 姿态本来就在分布内，只有 z 偏高 —— 见 maybe_bridge_to_stage2。
        self.left_target_pose = [-0.22, 0.10, 0.95, 0, 1, 0, 0]
        # 垃圾桶上方的松手位姿：抄 put_bottles_dustbin 的 left_end_action
        self.dustbin_drop_action = [-0.35, -0.1, 0.93, 0.65, -0.25, 0.25, 0.65]
        self.stage = 0

        # 分阶段 instruction 用的占位符取值。不能等 play_once 去填 self.info：
        # eval 的正式 rollout 不跑 play_once（只有 expert_check 那一遍跑），
        # 而 load_actors 每次 setup_demo 都会走到。
        # stage 1 用 adjust_bottle 的模板，占位符是 {A}（{a} 可选）；
        # stage 2 用 _combo_stage_dustbin 的模板，占位符是 {A}{B}。
        # filter_instructions 要求占位符集合精确匹配（{a} 可缺省），所以两边分开给。
        self._bottle_asset = f"{self.BOTTLE_MODEL}/base{self.model_id}"
        self._dustbin_asset = "011_dustbin/base0"
        self._stage_instructions = None
        self._bridged = False

    # ------------------------------------------------------------------ #
    # 专家演示：eval 前的 expert_check 会跑这个来确认种子可用
    # ------------------------------------------------------------------ #
    def play_once(self):
        arm_tag = ArmTag("left")

        # ---- 阶段 1：扶正（adjust_bottle 的动作序列） ----
        self.move(self.grasp_actor(self.bottle, arm_tag=arm_tag, pre_grasp_dis=0.1))
        self.move(self.move_by_displacement(arm_tag=arm_tag, z=0.1, move_axis="arm"))
        self.move(
            self.place_actor(
                self.bottle,
                target_pose=self.left_target_pose,
                arm_tag=arm_tag,
                functional_point_id=0,
                pre_dis=0.0,
                is_open=False,
            ))

        # Expert mode does not poll check_success at every physics step.
        # Observe the completed first stage before starting the second.
        self.stage_reward()

        if self.RELEASE_AFTER_ADJUST:
            # 松手 + 抬手离开，让瓶子真的自己立在桌面上，再按「投垃圾桶」那套重新抓
            self.move(self.open_gripper(arm_tag))
            self.move(self.move_by_displacement(arm_tag=arm_tag, z=0.1))
            self.move(self.grasp_actor(self.bottle, arm_tag=arm_tag, pre_grasp_dis=0.1))
            self.move(self.move_by_displacement(arm_tag=arm_tag, z=0.1))

        # ---- 阶段 2：投垃圾桶（put_bottles_dustbin 的左臂分支） ----
        self.move((arm_tag, [Action("left", "move", self.dustbin_drop_action)]))
        self.move(self.open_gripper(arm_tag))

        self.info["info"] = {
            "{A}": f"{self.BOTTLE_MODEL}/base{self.model_id}",
            "{B}": "011_dustbin/base0",
            "{a}": str(arm_tag),
        }
        return self.info

    # ------------------------------------------------------------------ #
    # 判定
    # ------------------------------------------------------------------ #
    def _is_upright_on_left(self):
        """保留左侧位置要求，并直接检查瓶子长轴朝上。"""
        pose = self.bottle.get_functional_point(0)
        # Bottle asset geometry is elongated along its local neck axis.
        # Functional point 0 is near the grasp center, not the bottle cap.
        extents=np.asarray(self.bottle.config['extents'])*np.asarray(self.bottle.config.get('scale',1))
        axis=int(np.argmax(extents))
        rotation=self.bottle.get_pose().to_transformation_matrix()[:3,:3]
        return bool(pose[0] < -0.15 and pose[2] > 0.9 and rotation[2,axis] > 0.85)

    def _is_in_dustbin(self):
        """瓶子在垃圾桶里 —— 判据与 put_bottles_dustbin.check_success 一致。"""
        target_pose = [-0.45, 0]
        eps = np.array([0.221, 0.325])
        p = self.bottle.get_pose().p
        return bool(np.all(np.abs(p[:2] - target_pose) < eps) and 0.2 < p[2] < 0.7)

    # ------------------------------------------------------------------ #
    # 分阶段 instruction
    # ------------------------------------------------------------------ #
    @staticmethod
    def _instruction_gen():
        """拿到 description/utils/generate_episode_instructions。

        eval_policy.py 自己会 sys.path.append("./description/utils")，但那依赖调用方
        的 cwd；这里按 __file__ 定位，collect_data / 单跑探针也能用。
        """
        utils_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "description", "utils")
        if utils_dir not in sys.path:
            sys.path.append(utils_dir)
        from generate_episode_instructions import generate_episode_descriptions
        return generate_episode_descriptions

    @staticmethod
    def _repo_root():
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _pick_object_desc(self, asset, rng):
        """给一个资产 id 挑一句自然语言描述，返回带冠词的形式（"the brown bottle"）。

        本来 replace_placeholders 会自己去 objects_description 里抽，但那是两个阶段
        各抽各的 —— 同一条 episode 里同一个瓶子，扶正前后可能被叫成两个名字。
        所以描述在这里一次性定好，再以字面串传进去（值里不带 '/' 就不会再被当路径查表）。
        """
        path = os.path.join(self._repo_root(), "description", "objects_description", asset + ".json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pool = data.get(self.INSTRUCTION_TYPE) or data.get("seen") or []
        return f"the {rng.choice(pool)}" if pool else "the object"

    def _build_stage_instructions(self):
        """给两个阶段各生成一句 instruction，整条 episode 固定不变。

        不能每个控制周期现抽 —— get_instruction 是每步都调的，现抽会让指令逐帧抖动。
        """
        gen = self._instruction_gen()
        rng = random.Random(0) if self.INSTRUCTION_PIN else random.Random()
        if self.INSTRUCTION_PIN:
            # filter_instructions 内部用的是全局 random.shuffle，得连它一起摁住
            random.seed(0)

        bottle = self._pick_object_desc(self._bottle_asset, rng)
        dustbin = self._pick_object_desc(self._dustbin_asset, rng)

        stage2_task = self._STAGE2_TASKS.get(self.STAGE2_TEMPLATE, self._STAGE2_TASKS["hold"])
        # 占位符集合必须和模板精确匹配（{a} 可缺省），所以按 task 给对应的参数
        stage2 = (stage2_task, {"{A}": bottle, "{B}": dustbin})
        stage1 = (("adjust_bottle", {"{A}": bottle, "{a}": "left"})
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
            # 真的只有一句：两个阶段返回同一个字符串，而不是从同一个池子里各抽一句
            only = one(*stage2)
            return None if only is None else (only, only)

        first, second = one(*stage1), one(*stage2)
        return None if (first is None or second is None) else (first, second)

    def set_instruction(self, instruction=None):
        # 仍然把 eval_policy 传进来的复合句存下来（日志/回退用），但分阶段开着时
        # get_instruction 返回的是下面这两句
        super().set_instruction(instruction=instruction)
        self._stage_instructions = None
        if not self.STAGED_INSTRUCTION:
            return
        try:
            self._stage_instructions = self._build_stage_instructions()
        except Exception as e:
            # 生成失败不该让整轮评测挂掉，退回复合句
            print(f"[adjust_bottle_dustbin] 分阶段 instruction 生成失败，回退复合句: {e}")
            self._stage_instructions = None

    def maybe_bridge_to_stage2(self):
        """扶正完成后、交给投桶那一段之前，把末端降到分布内的高度。

        由 policy/WLA/deploy_policy.py 的 eval() 每步调一次，整条 episode 只触发一次。
        故意不修正 xy 和姿态 —— 实测那两项本来就在分布内，动了反而是引入偏移。
        """
        if not self.STAGE2_BRIDGE or self._bridged:
            return False
        self.stage_reward()
        if self.stage < 1:
            return False
        self._bridged = True  # 失败也不重试，免得每步都试一遍
        try:
            pose = list(np.asarray(self.get_arm_pose(ArmTag("left")), dtype=float)[:7])
            if pose[2] <= self.BRIDGE_Z:
                return False
            pose[2] = self.BRIDGE_Z
            self.move((ArmTag("left"), [Action("left", "move", pose)]))
            return True
        except Exception as e:
            print(f"[adjust_bottle_dustbin] stage2 桥接失败，按原样交回策略: {e}")
            return False

    def get_instruction(self, instruction=None):
        if not self.STAGED_INSTRUCTION or not self._stage_instructions:
            return super().get_instruction(instruction=instruction)
        self.stage_reward()  # 刷新 self.stage（只升不降）
        return self._stage_instructions[0 if self.stage < 1 else 1]

    def stage_reward(self):
        # stage 只升不降：中途扶正过就算完成过第一阶段，方便区分
        # 「adjust 都没做到」和「adjust 成功但没投进」
        if self.stage >= 1 and self._is_in_dustbin():
            self.stage = 2
        elif self.stage < 1 and self._is_upright_on_left():
            self.stage = 1
        return self.stage / 2.0

    def check_success(self):
        self.stage_reward()
        return self.stage >= 2 and self._is_in_dustbin()
