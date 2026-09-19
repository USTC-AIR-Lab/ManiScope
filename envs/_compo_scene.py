"""组合泛化场景共享基类：按 SPEC 声明式摆放 actor + 按 GOAL 声明式终态判据。
只服务于测评/渲染，不用于训练。

判据分两层，缺一不可：

  1) 选对 —— EXCLUSIVE：目标位移必须严格大于所有干扰物。
     这层保证「不解析指令」的策略拿不到分，是语言 steerability 的守门员。
  2) 做对 —— GOAL：任务名承诺的那个终态真的达成了。

历史教训（这次重构的起因）：旧版只有第 1 层（位移 > 5cm 且大于干扰物），于是
place_book_stand 不检查书有没有上架、stack_cups_two 不检查有没有叠上、
scan_then_basket 不检查扫没扫码 —— 32 个场景的名字和它实际测的东西对不上，
L1 和 L3 的判据完全一样，难度梯度是假的。GOAL 就是补上第 2 层。

SPEC 每项:
  role:  唯一名; 一个必须叫 TARGET(默认 "target")
  kind:  "box" | "model"
  box:   color=(r,g,b), half=0.02
  model: model=名称, ids=[可用id], static=False, mass=0.05
  region:[xlim,ylim]  绝对生成区(默认居中); 用左右/前后分区避免重叠
  qpos / rot / rotlim / zlim
  rel:   另一个 role 名, offset=[dx,dy,dz]  (相对摆放,如"在书上"/"在篮里")
  pad:   prohibit padding
  desc:  box 的语言描述("red block")

GOAL 声明（type 必填，其余带默认值）:
  {"type":"moved"}                          位移判据。**只允许 L1 纯抓取场景用**，且必须显式写出来。
  {"type":"lift",  "dz":0.10}               当前几何底部离开初始支撑面 dz，且接触夹爪
  {"type":"on",    "ref":R, "dz":None, "eps":[0.035,0.035,0.03]}
                                            落在 R 上方（垫子/盘子/秤/展示架）
  {"type":"stack", "ref":R, "dz":0.05, "eps":[0.03,0.03,0.02]}
                                            叠在 R 上（on 的特例，dz 默认一块方块高）
  {"type":"in",    "ref":R, "r":0.10}       进容器：接触容器且低速、几何底部低于口沿、已离开原位
  {"type":"rel",   "ref":R, "dir":"left|right|front|behind", "gap":[0.04,0.30], "lat":0.12}
                                            摆到 R 的某一侧，且横向不跑偏
  {"type":"between","refs":[A,B], "lat":0.09}  摆在 A、B 连线中点附近
  {"type":"press", "ref":R, "model":M, "cp":0} 按到了 R（夹爪接触点判据，且物体没被搬走）
  {"type":"seq",   "stages":[g1, g2, ...]}  阶段序：必须**依次**达成，只升不降（写 self.stage）

坐标约定（和 RoboTwin 各任务的 arm_tag 逻辑一致）：
  x < 0 = 左侧，x > 0 = 右侧；y 增大 = 远离机器人（behind），y 减小 = 靠近机器人（front）。
"""
from ._base_task import Base_Task
from ._placement_judge import supported_placement, world_bounds, grasped_clearance
from .utils import *
from .utils.create_actor import UnStableError
import os
from copy import deepcopy
import numpy as np
import sapien



# ---- 物体足迹（用来做生成期的重叠检查）--------------------------------------
# 每个物体在各自生成区里**独立**采样，add_prohibit_area 只是记录禁区、
# 并不会让后续采样避开已放好的物体 —— 所以两个生成区一重叠就会架在一起。
# 用户在总览图上逮到 5 处：擀面杖架在盘子上、笔记本架在铃上、篮子架在秤上、篮子侧翻…
_EXT_CACHE = {}


def _model_radius(model, mid):
    """物体在桌面上的水平半径（m）。读 model_data*.json 的 extents*scale。
    读不到就退到一个保守值 —— 宁可摆得开一点，也不要叠在一起。"""
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
            # 取**最长边**的一半，保守。物体平躺时最长边就在水平面上（擀面杖 23cm、
            # 木槌 23cm），按「两个最小边」算会低估一个数量级，重采检查等于没做。
            r = dims[2] / 2.0
    except Exception:
        pass
    _EXT_CACHE[key] = r
    return r


class CompoScene(Base_Task):
    SPEC = []
    TARGET = "target"

    # ---- 判据 ----
    GOAL = {"type": "moved"}   # 子类必须显式声明；保留 moved 作为 L1 抓取场景的合法选项
    MIRROR = False             # True = 每条 episode 以 50% 概率整体左右镜像。
                               # 选择类场景（属性绑定/指代结构）必须开，否则目标恒在一侧，
                               # 「永远抓左边」就能刷分；空间关系类和序位类必须关，镜像会改答案。
    EXCLUSIVE = True           # 目标位移是否必须大于所有干扰物（语言 steerability 守门员）
    MOVED_EPS = 0.05
    DISTRACTORS = None         # None = 自动：除 TARGET 和 GOAL 引用到的 role 之外的全部

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

    # ------------------------------------------------------------------ 描述
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

    # ------------------------------------------------------------------ 摆放
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
        """和已放好的任何物体在水平面上重叠？留 1.5cm 余量。"""
        for (oxy, orad) in getattr(self, "_placed", []):
            if float(np.hypot(xy[0] - oxy[0], xy[1] - oxy[1])) < (r + orad * 0.8 + 0.01):
                return True
        return False

    def _place(self, s):
        qpos = s.get("qpos", [1, 0, 0, 0])
        # 躺姿的瓶/罐必须按左右侧换姿态，否则夹爪从错误的一侧接近，抓取规划返回 None。
        # 取自 adjust_bottle / attr_bind_bottle 的实测配置：左 [0.707,0,0,-0.707]，
        # 右 [0.707,0,0,0.707]。用一个统一姿态两边通吃是不行的（实测 0-1/8）。
        if s.get("qpos_lr") and "rel" not in s:
            reg = self._mx(s.get("region", [[-0.2, 0.2], [-0.15, -0.05]]))
            qpos = s["qpos_lr"][1 if (reg[0][0] + reg[0][1]) / 2.0 > 0 else 0]
        if "rel" in s:
            base = self._actors[s["rel"]].get_pose().p
            off = s.get("offset", [0, 0, 0])
            pose = sapien.Pose([float(base[0] + off[0]), float(base[1] + off[1]), float(base[2] + off[2])], qpos)
        else:
            region = self._mx(s.get("region", [[-0.22, 0.22], [-0.15, -0.02]]))
            # 重采到不和已放好的物体重叠为止。没有这一步，两个生成区一重叠
            # 物体就会架在一起（擀面杖架在盘子上、笔记本架在铃上…）。
            # 重采到不和已放好的物体重叠为止，**渐进降级**：
            # 先按完整足迹要求，挤不下就逐步放宽到 0.75 / 0.5 / 0.35 倍。
            # 桌面就这么大、可达范围又只有 |x|<=0.22，某些组合（擀面杖 23cm + 盘子）
            # 严格不重叠是解不出来的；宁可稍微靠近，也比直接架在一起强。
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
                # 所有降级都躲不开：回退到**生成区中心**，而不是最后一次候选。
                # 用最后一次候选会把物体留在被污染的位置 —— 初始状态守卫重摆时
                # _placed 未清空，重叠检查恒为真，物体被推到 x=0.36 这种桌外坐标
                # （place_cube_right_of_plate 实测）。宁可摆在中心稍微挤一点。
                cx = (region[0][0] + region[0][1]) / 2.0
                cy = (region[1][0] + region[1][1]) / 2.0
                pose = rand_pose(xlim=[cx, cx], ylim=[cy, cy], zlim=s.get("zlim", [0.79]),
                                 qpos=qpos, rotate_rand=False)
        if s["kind"] == "urdf":
            # 铰接物体（laptop / switch / cabinet / microwave / pot）走 urdf 通道，
            # 它们没有 model_data*.json，create_actor 那条路走不通。
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

    # 干扰物被移动多少算「选错了」。默认与 MOVED_EPS 同阈值：擦碰不算，
    # 真把它挪走了就算。场景可覆盖（比如干扰物本来就挡在必经之路上）。
    WRONG_EPS = 0.05

    # 指代校验：{"who":..., "ref":..., "rivals":[...], "ratio":1.6}
    # 「挨着碗的那个杯子」这句话必须是真的 —— 生成完如果干扰杯离碗更近，
    # 指代就指到了干扰物身上，策略怎么做都是错的（判据认的是另一个）。
    NEAREST = None

    REPLACE_TRIES = 25          # 初始状态已满足判据时，最多挪多少次被操作物

    def _enforce_nearest(self):
        """重采干扰物，直到目标确实是离参照物最近的那一个。

        只挪干扰物，不碰目标和参照物 —— 抓取规划只对「目标相对参照物」的
        位置敏感（ref_mug_next_to_bowl 上把 offset 收 1.5cm 就 0/20 了）。
        """
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
                # Actor 是包装类，set_pose 在它包着的 entity 上（同 296 行的初始守卫）。
                getattr(self._actors[rv], "actor", self._actors[rv]).set_pose(rand_pose(
                    xlim=reg[0], ylim=reg[1], zlim=sp.get("zlim", [0.79]),
                    qpos=sp.get("qpos", [1, 0, 0, 0]), rotate_rand=sp.get("rot", True),
                    rotate_lim=sp.get("rotlim", [0, 0, 0.4])))
                self.delay(1)

    def load_actors(self):
        self._first_moved = None
        self._min_contact_d = 1e9        # 每条 episode 重置
        self._contact_thr = None
        self._load_actors_once()
        self._enforce_nearest()
        if not getattr(self, "_init_satisfied", False):
            return
        # 初始状态已经满足终态判据 —— 策略什么都不做也可能被判成功。
        # 解决办法是**挪动被操作物**，而不是把整场重摆一遍：
        # scene.remove_actor() 在这套 sapien 里删不掉（异常被 try 吞掉），
        # 重摆会不断往场景里叠加物体，十几个副本互相挤，把目标推到桌外
        # （place_cube_right_of_plate 实测被推到 x=0.36）。
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

    SHUFFLE_SLOTS = None        # 例：["target","d1","d2"] —— 这几个 role 的生成区随机对调

    def _load_actors_once(self):
        # Do not mutate class-level layout across expert/eval resets.
        self.SPEC = deepcopy(type(self).SPEC)
        self._flip = bool(self.MIRROR and np.random.rand() < 0.5)
        # 槽位轮换：不轮换的话目标永远在同一个位置（比如三色方块里红色总在最左或最右），
        # 策略可以靠位置蒙对，属性词就没被真正考到（用户指出）。
        if self.SHUFFLE_SLOTS:
            roles = [r for r in self.SHUFFLE_SLOTS
                     if any(sp["role"] == r and "region" in sp for sp in self.SPEC)]
            regs = [next(sp for sp in self.SPEC if sp["role"] == r)["region"] for r in roles]
            perm = np.random.permutation(len(regs))
            for r, k in zip(roles, perm):
                next(sp for sp in self.SPEC if sp["role"] == r)["region"] = regs[int(k)]
        self._actors, self._p0, self._model_of, self._half_of = {}, {}, {}, {}
        self._placed = []          # [(xy, 半径)] 已放好的物体，供重叠检查用
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
        # --- 初始状态不许已经满足终态判据 -------------------------------------
        # 用户在 place_cube_right_of_plate / place_between_bowls / phone_right_of_laptop
        # 上逮到：魔方一开始就在盘子右边、马克杯一开始就在两碗中间、手机一开始就在
        # 电脑右边 —— 策略什么都不做也可能被判成功，整条场景失去意义。
        # 这里在摆完场景后自检一次，已满足就重摆（最多 REPLACE_TRIES 次）。
        self._init_satisfied = False
        try:
            if self._goal_ok(self.GOAL):
                self._init_satisfied = True
            # min_start：起始离参照物太近也要挪开。初始守卫只保证「不满足判据」，
            # 但物体可能刚好卡在 gap 边界外一点点、视觉上仍贴着参照物 ——
            # 那样「放到右边」这个动作几乎不用做（用户在 card_right_of_scanner 上指出）。
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

    # ------------------------------------------------------- 专家：按 GOAL 编排
    # 判据升级成终态判据之后，专家也必须真的把物体放到位 —— 否则专家自己过不了判据，
    # eval_policy 的 expert_check 会无限拒绝种子（这个坑在 attr_bind_bottle 上踩过，
    # 空转 28 分钟）。所以 play_once 也按 GOAL 声明式编排，和 check_success 同源。

    def _ref_pose(self, role, fp=None):
        """容器/参照物的落点。优先 functional_point（篮子/杯垫/展示架都有），否则用 pose。"""
        a = self._actors[role]
        if fp is not None:
            try:
                return np.asarray(a.get_functional_point(fp), dtype=float)[:3]
            except Exception:
                pass
        return np.asarray(a.get_pose().p, dtype=float)

    def _place_target(self, g):
        """把 GOAL 翻译成 place_actor 的 target_pose（7 元）；None = 这一步不需要放置。"""
        t = g.get("type", "moved")
        if t in ("moved", "lift", "press", "seq", "qpos"):
            return None
        who = g.get("who", self.TARGET)
        half = self._half_of.get(who, 0.02)
        if t in ("on", "stack"):
            q = self._ref_pose(g["ref"])
            # 放置高度和判据高度是两个量，不能混用：move_stapler_pad 的约定是 target_pose
            # 直接给垫子的位置（dz=0），由 place_actor 自己算物体的停放高度；GOAL 里的 dz
            # 是「落好之后中心该比参照物高多少」，用它当放置高度会让物体悬空。
            # 放置高度：优先 place_dz，其次沿用判据的 dz。实测 dz=0 会让 place_actor
            # 把物体往桌面里塞，规划直接失败（probe_on 0/8）；用判据的 dz 是 2/3。
            dz = g.get("place_dz")
            if dz is None:
                dz = g.get("dz")
            if dz is None:
                dz = 0.05 if t == "stack" else 0.03
            # 落点姿态默认 [1,0,0,0] + constrain="free"。试过照抄 move_stapler_pad 的
            # [0.707,0,0,0.707] + constrain="align"，规划直接全灭（probe_on 2/3 -> 0/8）：
            # 那套是给有固定抓取朝向的订书机用的，随机绕 z 转过的方块对不上对齐约束。
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
            # 要求直立时，落点姿态沿用物体**自己的站立姿态**（SPEC 里的 qpos），
            # 不写死任何四元数：写死 [1,0,0,0] 会把长轴是 y 的罐子放倒，
            # 写死 [0.5,0.5,0.5,0.5] 又只对长轴恰好是 y 的资产成立。
            # 实测：落点姿态给 [1,0,0,0] 时放置几何最好（6 个种子里 2 个位置全对）；
            # 改成沿用物体自己的站立姿态 [0.5,0.5,0.5,0.5] 反而让横向偏移全部超标
            # （0.14~0.21 > lat 0.14）、夹爪也不松手。罐子站不站得住由它自身姿态决定，
            # place_actor 并不会因为这个四元数把它放倒 —— 实测 up_cos 前后不变。
            dq = [1, 0, 0, 0]
            return [float(q[0] + dx), float(q[1] + dy), float(q[2] + half + 0.005)] + g.get("quat", dq)
        if t == "between":
            a, b = [self._ref_pose(r) for r in g["refs"]]
            m = (a + b) / 2.0
            return [float(m[0]), float(m[1]), float(max(a[2], b[2]) + half + 0.005)] + g.get("quat", [1, 0, 0, 0])
        return None

    def _do_press(self, g):
        """按压型原语：不抓取，夹爪对准 contact_point 压下去再抬起（click_bell 的做法）。"""
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
        """叠放：照搬 stack_blocks_two —— 用底块的 functional_point(1) 当落点，
        自己用 functional_point(0) 对齐。create_box 建出来的方块是有功能点的。"""
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
        """进容器：照搬 place_object_basket —— 取最近的功能点、按手别给接近姿态，
        先不松手放到位，再显式松手抬臂。通用 place_actor 直接丢 target_pose 成功率只有 1/8。"""
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
            # 规划不出来时的兜底：抬高绕过容器边缘再下降松手（place_object_basket 的同款兜底）
            self.plan_success = True
            place[0] += -0.15 if arm == "left" else 0.15
            place[2] += 0.15
            self.move(self.move_to_pose(arm_tag=arm, target_pose=place.tolist()))
            place[2] -= 0.05
            self.move(self.move_to_pose(arm_tag=arm, target_pose=place.tolist()))
        self.move(self.open_gripper(arm_tag=arm))
        self.move(self.move_by_displacement(arm_tag=arm, z=0.08))

    def _do_beat(self, g):
        """用锤子敲指定的方块（照搬 beat_block_hammer 的动作序列）。

        判据和动作同源：锤子的 functional_point 0 落到目标方块的 functional_point 1 上。
        方块是 static 的，敲中了也不会移动 —— 所以「选对了没有」不能靠位移比大小，
        只能靠这个落点比对，见 _needs_move / _goal_ok 里 beat 的分支。
        """
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
        """两个物体各一条手臂同时抓起。照搬 pick_dual_bottles：self.move(a, b) 就是并行双臂，
        不需要任何新原语 —— 基类之前只是没用上。"""
        who, w2 = g.get("who", self.TARGET), g["who2"]
        a, b = self._actors[who], self._actors[w2]
        # 左手拿左边那个，右手拿右边那个
        if self._p(who)[0] > self._p(w2)[0]:
            a, b = b, a
        self.move(self.grasp_actor(a, arm_tag=ArmTag("left"), pre_grasp_dis=g.get("pre_grasp", 0.08)),
                  self.grasp_actor(b, arm_tag=ArmTag("right"), pre_grasp_dis=g.get("pre_grasp", 0.08)))
        self.move(self.move_by_displacement(arm_tag=ArmTag("left"), z=g.get("lift", 0.12)),
                  self.move_by_displacement(arm_tag=ArmTag("right"), z=g.get("lift", 0.12)))
        return ArmTag("left")

    def _do_dual_carry(self, g):
        """单个物体双臂各抓一个把手抬起（lift_pot 的做法：先半合夹爪，再分别抓 cp0/cp1）。"""
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
        """双臂抬起再一起送到 ref 上方松手（lift_pot 的组合版）。

        抬起那一段完全复用 _do_dual_carry；差别只在抬起后按 xy 差量平移两条手臂、
        再同时松手。用 move_by_displacement 而不是 place_actor：place_actor 是单臂
        原语，双臂各自规划到自己的落点会把锅拧着走。
        """
        self._do_dual_carry(g)
        l, r = ArmTag("left"), ArmTag("right")
        who = g.get("who", self.TARGET)
        # 先核实锅真的被抬起来了。没抬起来还继续横move，等于把锅推着在桌面上滑
        # （探针实测：2/5 的种子就是这样"滑"到垫子上的，抬升恒为 0）。
        self._track()
        if (self._maxz[who] - float(self._p0[who][2])) <= g.get("dz", 0.06):
            return l
        p, q = self._p(who), self._p(g["ref"])
        dx, dy = float(q[0] - p[0]), float(q[1] - p[1])
        # 一次规划到位。分成「平移 -> 下降」两步反而更容易失败：中间那个位姿
        # 双臂各自解 IK，任一条解不出来整段就废了，而且下降那一步会把锅底压向
        # 垫子再规划，直接撞上。垫子只有 0.5mm 厚，从抬起高度松手落差很小。
        # 拆成两小步：单步位移越小，双臂各自的 IK 越容易同时解出来。
        # 一步到位时实测会欠程（抬起成功的那个种子只挪到离垫子 0.104）。
        for _ in range(2):
            self.move(self.move_by_displacement(l, x=dx / 2.0, y=dy / 2.0),
                      self.move_by_displacement(r, x=dx / 2.0, y=dy / 2.0))
        self.move(self.open_gripper(l), self.open_gripper(r))
        return l

    def _do_goal(self, g):
        """执行单个 GOAL 对应的专家动作，返回用到的 arm_tag。"""
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
        # 手臂按**落点**选，不按物体选。放置是这条链上更紧的约束：左臂抓左边的物体没问题，
        # 但把它放到 x=+0.2 就规划不出来（实测 plan=False，物体一直举在手里，stack 0/8）。
        # 场景侧的配套约束：source 和 destination 必须在同一侧半区（见 table.py 的 L/R 分区）。
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
            tp = self._place_target(g)   # 抓取后参照物可能被碰动，重算一次落点
            # upright 场景必须 constrain="align"：free 模式下 place_actor 会自选朝向，
            # 我给的竖直落点姿态被忽略，罐子还是躺着放下（实测 up_cos=-0.001）。
            # upright 场景用 constrain="auto"：get_place_pose 里 auto 分支会自己
            # 带上 align_axis（左臂 [1,1,0] / 右臂 [-1,1,0]）。
            # 之前只传 constrain="align" 不传 align_axis，约束等于没加，
            # 罐子还是躺着放下（实测 up_cos=-0.001）。
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
                # 每段结束显式锁 stage。stage_reward 一次只升一级（这是 eval 里保证
                # 「第 n 段必须在第 n-1 段之后」的机制），而专家侧 check_success 只在
                # 最后被调一次，不在这里锁就永远停在 stage 1 —— stapler_pad_press
                # 踩过同一个坑，处理方式一致。
                self.check_success()
            arm = arms[0] if arms else self.arm_tag
        else:
            arm = self._do_goal(goal)
        self.arm_tag = arm
        # 目标达成了就把 plan_success 收回来。中途某一步规划失败会把它永久置 False，
        # 而 eval_policy / expert_smoke 要求 plan_success AND check_success 才接受种子 ——
        # 于是「专家绕了个弯但确实做成了」的种子会被误杀。实测 place_trophy_coaster 的
        # seed1 判据是 ok=True 却因为 plan_success=False 被丢掉。_do_in 里本来就有同款
        # 兜底(规划失败后重置再走恢复路径)，这里只是把它推广到所有 GOAL 类型。
        if not self.plan_success and self.check_success():
            self.plan_success = True
        self.info["info"] = {"{A}": self._target_desc(), "{a}": str(arm)}
        return self.info

    # ------------------------------------------------------------ 判据：工具
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
        """GOAL 用到的**工具**（目前只有敲击类的锤子）。

        工具和参照物必须分开：工具既不算干扰物（它必然要被拿起来，算进去的话
        「碰过干扰物就锁死」会直接毙掉整个场景），也不受 _refs_stayed_put
        「参照物不许动」的约束（拿起来移动正是它的用途）。
        第一版把它塞进 _refs_of，结果两条规则同时套上去，场景永远判负。
        """
        out = set()
        if not isinstance(g, dict):
            return out
        if g.get("tool"):
            out.add(g["tool"])
        for sub in (g.get("stages") or []):
            out |= self._tools_of(sub)
        return out

    def _is_upright(self, role, thr=0.75):
        """物体的**长轴**是否朝上。长轴按 extents 取，不假设是局部 z 轴。"""
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
        """这个场景是不是接触型（press / beat）—— 是的话每条 episode 都要记距离，
        包括「全程没碰到」的情况，否则「差一点」和「没靠近」在日志里长得一样。"""
        def has(g):
            if not isinstance(g, dict):
                return False
            if g.get("type") in ("press", "beat"):
                return True
            return any(has(x) for x in (g.get("stages") or []))
        return has(self.GOAL)

    def _refs_of(self, g):
        """GOAL 递归引用到的 role —— 这些不算干扰物。"""
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

    # 参照物允许的最大位移。放东西进去时容器会被轻微推动（篮子会晃、锅会滑一点），
    # 所以不是 0，但必须远小于「把容器搬到物体旁边」的量级。
    REF_MOVE_EPS = 0.05

    def _refs_stayed_put(self):
        """GOAL 引用到的参照物/容器必须基本没被搬动。

        没有这一条的话，「把茶叶盒放进平底锅」可以被这样骗过：先把茶叶盒推开 5cm
        （满足 moved），再把**锅**端到茶叶盒旁边（满足 xy 距离）—— 判据全过，
        画面上却是锅在茶叶盒后面，根本没放进去。用户在 place_teabox_skillet 的
        success 视频里逮到的就是这个。
        _distractor_roles() 又把 GOAL 引用的容器排除在「选对」检查外，所以搬容器
        既不违反排他性、也不违反终态 —— 两个口子叠在一起才让它漏过去。
        """
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

    # ------------------------------------------------------------ 判据：GOAL
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
                    # 没给精确高度：只要求落在 ref 正上方一个合理的薄层里
                    ok_z = 0.0 <= (p[2] - q[2]) <= g.get("zmax", 0.12)
                else:
                    ok_z = abs((p[2] - q[2]) - dz) < eps[2]
                return (abs(p[0] - q[0]) < eps[0] and abs(p[1] - q[1]) < eps[1]
                        and ok_z and (g.get("_retained", False) or self._grippers_open())
                        and supported_placement(self.scene,self._actors[who],self._actors[g["ref"]],t))

            if t == "in":
                p, q = self._p(who), self._p(g["ref"])
                # 场上有多个同类容器时，目标必须**明确更靠近**指定的那个。
                # 用户在 put_toycar_left_basket 上逮到：小车停在两个篮子中间也算成功，
                # 那等于「左」这个词没被考到 —— 这条轴就白测了。
                rivals = [k for k, mo in self._model_of.items()
                          if k != g["ref"] and k != who and mo == self._model_of.get(g["ref"])]
                for rv in rivals:
                    dq = float(np.linalg.norm(p[:2] - self._p(rv)[:2]))
                    if dq <= float(np.linalg.norm(p[:2] - q[:2])) + g.get("margin", 0.05):
                        return False
                r = g.get("r", 0.07)
                moved = np.linalg.norm(p - self._p0[who]) > g.get("min_move", 0.05)
                # 必须**高于容器原点**，而不是「不低于容器口减 3cm」——后者连躺在
                # 容器旁边的桌面上都算过。
                return (float(np.linalg.norm(p[:2] - q[:2])) < r
                        and p[2] > (q[2] + g.get("zmin", 0.0))
                        and moved and (g.get("_retained", False) or self._grippers_open())
                        and supported_placement(self.scene,self._actors[who],self._actors[g["ref"]],"in"))

            if t == "rel":
                p, q = self._p(who), self._p(g["ref"])
                if g.get("upright"):
                    # 必须**站着**送到位，倒了不算。
                    # 关键是量哪一根轴：不能假设「局部 z 轴 = 物体的竖直轴」。
                    # 071_can 的 extents=[1.42,1.93,1.42]，长轴是局部 y；它站着的时候
                    # 局部 z 是横的，用 R[:,2] 量出来恒为 0，判据永远不过（实测 0/20，
                    # 起始 up_cos 就是 0.002）。按 extents 取最长轴才是资产无关的写法，
                    # 和 adjust_bottle_dustbin._is_upright_on_left 一致。
                    if not self._is_upright(who, g.get("up_cos", 0.75)):
                        return False
                # 同上：场上有同类参照物时，别让「放在左边那个旁边」被「放在中间」蒙混过去
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
                # 按压型：夹爪接触点落在物体的 contact_point 上，且物体没被搬走
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
                # 同上：记录夹爪接触点到按压点的最近水平距离
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
                # 抬到过（过程量）+ 最终落在 ref 上方 + 松手
                if (self._maxz[who] - float(self._p0[who][2])) <= g.get("dz", 0.06):
                    return False
                p, q = self._p(who), self._p(g["ref"])
                eps = g.get("eps", [0.09, 0.09])
                return (abs(p[0] - q[0]) < eps[0] and abs(p[1] - q[1]) < eps[1]
                        and p[2] > q[2] and self._grippers_open())

            if t == "beat":
                # 锤头(fp0)落在目标方块的敲击点(fp1)上，且真的接触到了。
                # 与 beat_block_hammer.check_success 同口径。
                tool = self._actors[g.get("tool", "hammer")]
                blk = self._actors[who]
                hp = np.asarray(tool.get_functional_point(0, "pose").p, dtype=float)
                bp = np.asarray(blk.get_functional_point(1, "pose").p, dtype=float)
                eps = g.get("eps", [0.02, 0.02])
                # 记录整条 episode 的最近距离，供事后核对（头部相机分不出差几毫米）
                dmax = max(abs(hp[0] - bp[0]), abs(hp[1] - bp[1]))
                if dmax < getattr(self, "_min_contact_d", 1e9):
                    self._min_contact_d = float(dmax)
                    self._contact_thr = float(min(eps))
                if not (abs(hp[0] - bp[0]) < eps[0] and abs(hp[1] - bp[1]) < eps[1]):
                    return False
                return bool(self.check_actors_contact(tool.get_name(), blk.get_name()))

            if t == "qpos":
                # 铰接物体的关节状态（开笔记本 / 拨开关）：归一化到 [0,1] 后过阈值
                a = self._actors[g["ref"]]
                lim = a.get_qlimits()[0]
                cur = float(a.get_qpos()[g.get("joint", 0)])
                frac = (cur - lim[0]) / max(1e-6, (lim[1] - lim[0]))
                return frac > g.get("thr", 0.7)

            if t == "dual_lift":
                # 两个物体各用一条手臂**同时**抓起（pick_dual_bottles 的形态）
                dz = g.get("dz", 0.06)
                w2 = g["who2"]
                return ((self._maxz[who] - float(self._p0[who][2])) > dz
                        and (self._maxz[w2] - float(self._p0[w2][2])) > dz)

            if t == "dual_carry":
                # 单个物体双臂各抓一个把手抬起（lift_pot 的形态）
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

    # ------------------------------------------------------------ 判据：入口
    def _track(self):
        for k, v in self._actors.items():
            p = np.asarray(v.get_pose().p, dtype=float)
            self._maxdisp[k] = max(self._maxdisp[k], float(np.linalg.norm(p - self._p0[k])))
            self._maxz[k] = max(self._maxz[k], float(p[2]))
        # 记下**第一个**发生实质位移的 role。排他性判的是「先动了谁」，
        # 不是「碰没碰过谁」—— 见 _selected_right。
        if getattr(self, "_first_moved", None) is None:
            movers = [k for k, d in self._maxdisp.items() if d > self.MOVED_EPS]
            if movers:
                # 同一帧里多个都超阈值时，取位移最大的那个当「先动的」
                self._first_moved = max(movers, key=lambda k: self._maxdisp[k])

    def stage_reward(self):
        """seq 型 GOAL 的阶段机：只升不降，第 n 阶段必须在第 n-1 阶段之后才认。"""
        if self.GOAL.get("type") != "seq":
            self.stage = 1 if self._goal_ok(self.GOAL) else 0
            return float(self.stage)
        stages = self.GOAL["stages"]
        if self.stage < len(stages) and self._goal_ok(stages[self.stage]):
            self.stage += 1
        return self.stage / float(len(stages))

    def _needs_move(self, g):
        """这个 GOAL 要求目标发生位移吗？按压型不要求（物体必须留在原地）。"""
        t = g.get("type")
        if t == "seq":
            return any(self._needs_move(s) for s in g["stages"])
        return t not in ("press", "qpos", "beat")

    def _selected_right(self):
        """第 1 层：选对了没有。"""
        if not self.EXCLUSIVE:
            return True
        others = [self._maxdisp[k] for k in self._distractor_roles()]
        omax = max(others) if others else 0.0
        if not self._needs_move(self.GOAL):
            # 纯按压场景：目标本来就不该动，选没选对由 press 判据的位置比对负责，
            # 这里只要求干扰物没被碰飞（碰飞了说明手伸错了地方）。
            return omax < self.MOVED_EPS
        # 「先动的必须是目标」。原来只比最终位移大小，于是「先把红色那块拿起来、
        # 发现不对再去拿蓝色那块」也算成功（用户在 ref_not_the_red_one 上逮到）。
        # 指代/属性这一路考的就是**第一次就选对**，试错不该给分。
        #
        # 注意不能写成「全程没碰过干扰物」（第一版就是那么写的）：专家在正常完成
        # 任务时也会蹭到旁边的物体，于是**专家自己先被判负**，eval 找不到可解种子、
        # 连试 100 个就抛异常退出 —— 实测已经有 6 个场景栽在这上面。
        # 用户要的是顺序不是接触，所以只看第一个动的是谁。
        fm = getattr(self, "_first_moved", None)
        if fm is not None and fm != self.TARGET and fm in self._distractor_roles():
            return False
        return self._maxdisp[self.TARGET] > self.MOVED_EPS and self._maxdisp[self.TARGET] > omax

    def check_success(self):
        self._track()
        self.stage_reward()
        # 三层：选对（位移大于干扰物）× 做对（终态）× 没作弊（参照物没被搬过来）
        return bool(self._selected_right() and self._refs_stayed_put() and self._goal_ok(self.GOAL))
