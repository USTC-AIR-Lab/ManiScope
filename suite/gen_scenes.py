# -*- coding: utf-8 -*-
"""把 table.py 的声明式场景表编译成 envs/*.py + description/task_instruction/*.json。
场景表是唯一事实来源；改场景改 table.py，不要直接改生成出来的文件。"""
import json, os, pprint, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from table import SCENES
from scenes import BASE

OUT_ENV = "out/envs"; OUT_INS = "out/task_instruction"
os.makedirs(OUT_ENV, exist_ok=True); os.makedirs(OUT_INS, exist_ok=True)

DIMNAME = {"D1": "skill x object", "D2": "skill x spatial", "D3": "attribute binding",
           "D4": "instruction structure", "D5": "skill x skill (temporal)", "D7": "mixture"}
pp = pprint.PrettyPrinter(width=108, sort_dicts=False)

def fmt(obj, indent):
    txt = pp.pformat(obj)
    pad = " " * indent
    return ("\n" + pad).join(txt.splitlines())

# 这三个名字在仓库里已经有**手写且判据完整**的版本（不是 CompoScene 退化判据），
# 生成版会把它们覆盖掉、还会丢掉已有的 DM05 基线，所以跳过，沿用现存实现。
KEEP_EXISTING = {"move_cup_pad", "place_a2b_left_novel", "place_a2b_right_novel"}


# --- 生成期硬校验：被操作的物体必须有 contact_points ---------------------------
# 没有 contact_points 的模型进不了 grasp_actor（choose_grasp_pose 直接
# TypeError: 'NoneType' object is not subscriptable，整条场景 0/8）。
# 静态参照物（垫子/秤/展示架/挂架）不会被抓，不受这条限制。
# graspable.json 由 assets/objects/*/model_data*.json 扫出来，见 README。
GRASPABLE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "graspable.json")))
# 元数据里有 contact_points 不代表规划器抓得起来。TESTED 是**实测**白名单：
# 每个物体单独摆在桌面中央、goal=lift 跑 8 个种子(suite/diag 的 gp_* 探针)。
# 075_bread 是最好的反例 —— contact_points 齐全，实测 0/10；
# 换成罐子同一套流程立刻 3/3。所以被操作的物体必须在这张表里。
TESTED = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tested.json")))
OKGRASP = set(TESTED["ok"]) | set(TESTED["side_only"]) | set(TESTED["marginal"])

def manipulated_roles(goal):
    """GOAL 会去抓的 role：目标本身，加上每个 stage 的 who。press 型不抓。"""
    out = set()
    if goal.get("type") == "seq":
        for st in goal["stages"]:
            out |= manipulated_roles(st)
        return out
    if goal.get("type") in ("press", "qpos"):
        return out
    if goal.get("type") == "beat":
        # 敲击型被抓的是**锤子**，方块只是被敲的对象、全程不动（static）。
        # 不把方块算进来，否则「裸方块不可抓」这条守卫会把敲击场景全部拦掉。
        out.add(goal.get("tool", "hammer"))
        return out
    out.add(goal.get("who", "target"))
    return out

def check(sc):
    roles = manipulated_roles(sc["goal"])
    by_role = {p["role"]: p for p in sc["spec"]}
    bad = []
    for r in roles:
        p = by_role.get(r)
        if p is None:
            bad.append("%s: GOAL 引用了不存在的 role %r" % (sc["name"], r)); continue
        if p["kind"] != "model":
            if p["kind"] == "box":
                bad.append("%s: role %r 是 create_box 的裸方块，place/grasp 原语对它成功率极低"
                           " (实测 0-1/10 vs 真实模型 3/3)" % (sc["name"], r))
            continue
        # 020_hammer 在单物体探针里是 0/8，但那个探针用的是通用的规范姿态。
        # beat_block_hammer 这个原任务本身就抓得起来 —— 它用的是固定姿态
        # [0,0,0.995,0.105] + pre_grasp_dis=0.12 + grasp_dis=0.01。
        # 之前 bread/shoe/mouse 也是这样被探针误判的（5/8 都是姿态问题）。
        # 所以这里按「照抄原任务配置」放行，能不能用交给烟测判。
        if p["model"] == "020_hammer" and sc["goal"].get("type") == "beat":
            continue
        if p["model"] not in OKGRASP:
            bad.append("%s: %s 实测抓不起来(单物体探针 0/8)，不能当被操作物；当干扰物/参照物可以"
                       % (sc["name"], p["model"]))
            continue
        ids = GRASPABLE.get(p["model"])
        if ids is None:
            bad.append("%s: %s 没有 contact_points，grasp_actor 会直接 TypeError" % (sc["name"], p["model"]))
        else:
            miss = [i for i in p["ids"] if i not in ids]
            if miss:
                bad.append("%s: %s 的 id %s 没有 contact_points" % (sc["name"], p["model"], miss))
    return bad


# --- 布局归一化：把可达性约定编进编译器，别手写 64 组坐标 --------------------
# 依据 v1 里几何跑得通的那批场景（pick_block_on_plate / pick_mug_next_to_bowl /
# place_between_two ...）反推出来的约定：
#   * |x| <= 0.22，y 在 [-0.15, 0.08]。超出去 grasp_actor 挑不出可达的抓取位姿，
#     报 AssertionError('target_pose cannot be None for move action.')，整条 0/8。
#     第一轮 61 个场景里 24 个栽在这上面 —— 我原来用到了 |x|=0.28。
#   * 放置类场景：被操作物放**中间**（两臂都够得着），参照物和干扰物分居两侧。
#   * 选择类场景（lift/press）：目标和干扰物分居两侧，靠 MIRROR 随机左右。
XMAX, YMIN, YMAX = 0.22, -0.15, 0.08
CENTER = [[-0.05, 0.05], [-0.15, -0.06]]

def clamp(region):
    (x0, x1), (y0, y1) = region
    x0, x1 = max(-XMAX, min(XMAX, x0)), max(-XMAX, min(XMAX, x1))
    if x1 - x0 < 0.04:                       # 夹完别把生成区压没了
        c = (x0 + x1) / 2
        c = max(-XMAX + 0.03, min(XMAX - 0.03, c))
        x0, x1 = c - 0.03, c + 0.03
    y0, y1 = max(YMIN, min(YMAX, y0)), max(YMIN, min(YMAX, y1))
    if y1 - y0 < 0.04:
        c = max(YMIN + 0.03, min(YMAX - 0.03, (y0 + y1) / 2))
        y0, y1 = c - 0.03, c + 0.03
    return [[round(x0, 3), round(x1, 3)], [round(y0, 3), round(y1, 3)]]

# 杯/马克杯的可用姿态是 [0.707,0.707,0,0]（v1 的 pick_mug_next_to_bowl / place_between_two
# 都用这个）；[0.5,0.5,0.5,0.5] 那套是给篮子/盘子这类容器的，套在杯子上抓不起来。
CUP_QPOS = {"021_cup": [0.707, 0.707, 0, 0], "039_mug": [0.707, 0.707, 0, 0]}

def normalize(sc):
    # beat / dual_carry_to 不是「放置类」：
    #   beat 被抓的是锤子，方块全程静止，它们是被敲的对象不是落点参照物；
    #   dual_carry_to 的垫子必须留在锅附近，双臂横搬 16cm 规划不出来。
    # 算成放置类的话，下面的「参照物只能去左右两个槽位」会把三个方块塞进两个槽
    # （实测 target 和 d2 拿到完全相同的 region，必然重叠），也会把垫子推到边上。
    placement = sc["goal"]["type"] not in (
        "lift", "moved", "press", "qpos", "beat", "dual_carry_to")
    manip = manipulated_roles(sc["goal"])
    for p in sc["spec"]:
        if p.get("model") in CUP_QPOS and not p.get("static"):
            p["qpos"] = CUP_QPOS[p["model"]]
        if "region" not in p:                # rel 摆放的不需要生成区
            continue
        if p.get("model") in TESTED["side_only"] and p["role"] in manip:
            # 躺姿瓶只有配合左右姿态才抓得动，挪到中间两套姿态都不对 —— 保持侧面。
            p["region"] = clamp(p["region"])
            continue
        if placement and p["role"] in manip and not p.get("fixed") and not p.get("rel"):
            p["region"] = list(CENTER)       # 被操作物挪到中间
        else:
            p["region"] = clamp(p["region"])
    # 中间被占了就把和它冲突的参照物推到侧面
    # 被操作物如果是 rel 摆放的（放在盘子上/篮子里/碗边上），它的锚点必须留在中间 ——
    # v1 里 pick_block_on_plate / pick_mug_next_to_bowl 都是把容器摆中间、干扰物摆侧面，
    # 把锚点推到侧面会连带把目标推出可达范围（实测 0/8）。
    anchors = {p["rel"] for p in sc["spec"] if p.get("rel") and p["role"] in manip}
    for p in sc["spec"]:
        if p["role"] in anchors and "region" in p:
            p["region"] = [[-0.06, 0.06], clamp(p["region"])[1]]
    if placement:
        used = []
        for p in sc["spec"]:
            if "region" not in p or p["role"] in manip or p["role"] in anchors:
                continue
            r = p["region"]
            # 参照物推到侧面，但**留在可达的 y 带上**。
            # 试过把它们退到远端 y 带 [0.00,0.08] 前后分开，实测放置规划够不着，
            # 8 个代表场景里 5 个从 2/x 掉到 0/8 —— 可达性比不重叠更硬。
            # 所以这里只在 x 上分槽，重叠由 _compo_scene 的采样期重采来解决
            # （半径改成按最长边算之后，那个检查才真正起作用）。
            # spec 里写 side=+1/-1 可以强制参照物落在右/左半区。
            # 需要它是因为「把 A 放到 B 的左边」时，B 自己必须**足够靠右**，
            # 否则落点会落到 x<-0.26 这种超出可达范围(|x|<=0.22)的地方 ——
            # place_can_left_of_plasticbox 就是这样，几何上根本做不到，必然 0.00。
            side = p.get("side")
            if side is None:
                side = -1 if len([u for u in used if u < 0]) <= len([u for u in used if u > 0]) else 1
            used.append(side)
            # side_x 可以调槽位离中线的距离。容器离得太远时策略要横跨整张桌子，
            # 画面上也总在同一侧（用户在 attr_color_bottle_basket 上提的）。
            mag = float(p.get("side_x", 0.165))
            p["region"] = [[mag * side - 0.045, mag * side + 0.045], clamp(r)[1]]


# --- 容器/参照物的静置位姿：全部取自 RoboTwin 原任务，别自己猜 --------------------
# 三个坑一起踩过：
#   a) 姿态用错 —— 008_tray / 106_skillet / 074_displaystand / 024_scanner 的正确姿态
#      各不相同，统一套 [0.5,0.5,0.5,0.5] 会让托盘和锅是斜的（总览图上肉眼可见）。
#   b) rot 默认开着 —— rand_pose 的随机旋转作用在**局部**轴上，容器的局部 z 不是世界竖直，
#      于是随机一转就倾斜。容器一律 rot=False。
#   c) zlim 默认 0.79，比桌面(0.741)高 5cm。非静态的会掉下来settle，
#      static=True 的**永远悬空**。容器一律贴桌面。
TABLE_Z = 0.741
CONTAINER_POSE = {
    "003_plate":          [0.5, 0.5, 0.5, 0.5],
    "008_tray":           [0.706527, 0.706483, -0.0291356, -0.0291767],
    "106_skillet":        [0, 0, 0.707, 0.707],
    "072_electronicscale":[0.5, 0.5, 0.5, 0.5],
    "019_coaster":        [0.5, 0.5, 0.5, 0.5],
    "074_displaystand":   [0.707, 0.707, 0.0, 0.0],
    "024_scanner":        [0, 0, 0.707, 0.707],
    "110_basket":         [0.5, 0.5, 0.5, 0.5],
    "002_bowl":           [0.5, 0.5, 0.5, 0.5],
    "062_plasticbox":     [0.5, 0.5, 0.5, 0.5],
    "059_pencup":         [0.5, 0.5, 0.5, 0.5],
    "076_breadbasket":    [0.5, 0.5, 0.5, 0.5],
    "060_kitchenpot":     [0.5, 0.5, 0.5, 0.5],
    "011_dustbin":        [0.5, 0.5, 0.5, 0.5],
    "078_phonestand":     [0.707, 0.707, 0.0, 0.0],
    "040_rack":           [-0.22, -0.22, 0.67, 0.67],
}

def fix_containers(sc):
    """被操作物之外的模型：套原任务的静置位姿、关掉随机旋转、贴桌面。"""
    manip = manipulated_roles(sc["goal"])
    for p in sc["spec"]:
        if p.get("kind") != "model" or p["role"] in manip or "rel" in p:
            continue
        q = CONTAINER_POSE.get(p["model"])
        if q is None:
            continue
        p["qpos"] = list(q)
        p["rot"] = False
        # zlim 只给**静态**容器设。静态物体不受物理驱动，默认 zlim=0.79 会让它永远悬在
        # 桌面上方 5cm（总览图里盘子/托盘的「不水平」就有这一份）。
        # 非静态容器千万别动：它们本来是自由下落、自行 settle 的，强行贴桌面会和桌面
        # 穿插再被物理推开 —— 实测把 8 个原本达标的场景打到 0-1/8（33 -> 27）。
        if p.get("static"):
            p.setdefault("zlim", [TABLE_Z])


# --- 被操作物的规范初始姿态：同样取自 RoboTwin 原任务 ------------------------
# 全表审计（suite/audit_pose.py）发现 29 处不一致：我建表时给被操作物随手用了
# [1,0,0,0]（模型原始朝向）或 [0.707,0.707,0,0]，而原任务里**一律**是
# [0.5,0.5,0.5,0.5]。后果不只是「不好看」：
#   * 酱料罐/药瓶/奖杯躺着 -> 夹爪一碰就滚走，抓不住（用户实测指出）
#   * 印章躺着 -> 原任务里它是立着盖章的，躺着语义就不对了
#   * 姿态不在训练分布内 -> 测出来的失败归因不到「组合泛化」，而是「姿态没见过」
# 001_bottle 不在此列：它在原任务里本来就有三种姿态（adjust_bottle 的躺姿是刻意的），
# 由 qpos_lr（按左右侧换姿态）单独处理。
CANON_POSE = {
    "112_tea-box":   [0.5, 0.5, 0.5, 0.5],
    "100_seal":      [0.5, 0.5, 0.5, 0.5],
    "071_can":       [0.5, 0.5, 0.5, 0.5],
    "021_cup":       [0.5, 0.5, 0.5, 0.5],
    "105_sauce-can": [0.5, 0.5, 0.5, 0.5],
    "080_pillbottle":[0.5, 0.5, 0.5, 0.5],
    # 090_trophy 不在 RoboTwin 50 个任务里，没有权威姿态可依。我猜了 [0.5,0.5,0.5,0.5]，
    # 结果 lift_trophy 从 2/2 掉到 0/8 —— 撤回，用表里原本实测可行的姿态。
    "050_bell":      [0.5, 0.5, 0.5, 0.5],
}

def canon_pose(sc):
    """被操作物用原任务的规范姿态，并关掉随机旋转（原任务都是 rotate_rand=False）。
    场景里显式写 keep_pose=True 的可以豁免（目前只有刻意用躺姿的瓶子场景）。"""
    manip = manipulated_roles(sc["goal"])
    for p in sc["spec"]:
        if p.get("kind") != "model" or p["role"] not in manip:
            continue
        if p.get("keep_pose") or p.get("qpos_lr"):
            continue
        q = CANON_POSE.get(p["model"])
        if q is None:
            continue
        p["qpos"] = list(q)
        p["rot"] = False


# --- D7 混合维度：从已有场景派生 -------------------------------------------
# 用户的思路：拿几个典型任务（属性绑定类除外，那类本来就有干扰物），
# 放一个语义无关的干扰物 + 一点背景变化即可。
# 好处是归因干净：mix 场景和源场景只差一个干扰物，分差就是这一维的代价。
# 干扰物一律放在**远离目标和落点**的另一侧，且不进 GOAL 引用，
# 所以它会被计入「选对」的排他性检查 —— 碰它就扣分。
# 派生源不能用 KEEP_EXISTING 里的手写场景：派生走的是表里的 spec，
# 而手写场景的真实生成区写在 envs/*.py 里、表里那份不作数 ——
# place_a2b_left_novel_mix 就因此把参照物摆到最左，"放左边"落点 x≈-0.26 无解（0/8）。
MIX_SRC = [
    ("move_cup_pad",           "071_can",        [0, 1, 2],       "办公桌上多一个易拉罐"),
    ("place_teabox_skillet",   "073_rubikscube", [0, 1, 2],       "灶台上多一个魔方"),
    ("roller_to_plate",        "112_tea-box",    [0, 1, 2, 3],    "备餐台上多一个茶叶盒"),
    ("ref_block_on_plate",     "057_toycar",     [0, 1, 2, 3],    "桌上多一个玩具车"),
    ("card_right_of_scanner",  "071_can",        [0, 1, 2],       "收银台上多一个易拉罐"),
    ("put_toycar_left_basket", "112_tea-box",    [0, 1, 2, 3],    "地上多一个茶叶盒"),
]

def build_mix():
    import copy as _copy
    by = {sc["name"]: sc for sc in SCENES}
    out = []
    for src, dmodel, dids, note in MIX_SRC:
        base = by.get(src)
        if base is None:      # 源场景可能是手写的，不在表里
            continue
        sc = _copy.deepcopy(base)
        sc["name"] = src + "_mix"
        sc["dim"] = "D7"
        sc["tier"] = min(4, base["tier"] + 1)
        sc["note"] = "混合维度：源场景 %s + 一个语义无关的干扰物（%s）。%s。" \
                     "判据/指令/依赖全部继承源场景，只多干扰物 —— " \
                     "和源场景的分差就是「干扰物 + 背景变化」这一维的代价。" % (src, dmodel, note)
        # 干扰物放在目标和落点的对侧
        used = []
        for sp in sc["spec"]:
            r = sp.get("region")
            if r:
                used.append((r[0][0] + r[0][1]) / 2.0)
        side = 1 if (sum(used) / max(1, len(used))) < 0 else -1
        sc["spec"] = sc["spec"] + [{
            "role": "mix_distractor", "kind": "model", "model": dmodel, "ids": dids,
            "region": [[0.14 * side - 0.04, 0.14 * side + 0.04], [-0.14, -0.04]],
            "qpos": [0.5, 0.5, 0.5, 0.5], "rot": False, "pad": 0.06,
        }]
        out.append(sc)
    return out

SCENES.extend(build_mix())


# --- rel/between 场景的布局规则（用户给的通用规则）---------------------------
# 「把 A 放到 B 的右边」这类任务，光靠初始守卫（不满足判据就挪）是不够的，
# 还得满足两条：
#   1) **B 要靠向目标方向的反侧**，右边才留得下空间 —— 否则落点会顶到可达边界
#      甚至无解（place_can_left_of_plasticbox 曾经就是无解的）。
#   2) **A 不能一开始就在目标侧**，否则「移过去」几乎不用动
#      （card_right_of_scanner / place_cube_right_of_plate 都是这个毛病）。
# 实现：把 A 放到**垂直于目标方向的那一轴**上远离 B —— 左右任务就让 A 靠前，
# 前后任务就让 A 靠边。这样 rel 判据的 lat（横向不跑偏）一开始就不满足，
# 而且 A 仍在可达范围内（试过把 B 整体后移到 y>=0，放置规划够不着，5/8 场景崩掉）。
NEAR_Y = [-0.19, -0.14]      # A 的近侧带（靠机器人）
FAR_Y  = [-0.05, 0.03]       # B 的远侧带

def rel_layout(sc):
    """只做 **Y 方向**的分离，X 完全沿用 normalize 的结果。

    用户的要求是对的：B 要留出目标侧空间、A 不能一开始就在目标侧。
    但我第一版把 X 也重排了（B 强制推到反侧、A 跟着挪），专家直接崩：
      place_can_left_of_plasticbox 2/4 -> 0/8（罐子举在半空放不下，plan=False）
      place_cube_right_of_plate    2/3 -> 1/8
    原因是 X 一动，抓取点和落点的相对关系就变了，place_actor 规划不出来。
    所以这里只动 Y：A 压到近侧带、B 留在远侧带，两者 y 差 >= lat，
    rel 判据的「横向不跑偏」一开始就不满足 —— 既达到「初始不在目标侧」的效果，
    又不碰 X，专家的抓取/放置路径原样保留。剩下的边界情况交给初始守卫兜底。
    """
    g = sc["goal"]
    t = g.get("type")
    if t not in ("rel", "between"):
        return
    manip = manipulated_roles(g)
    tgt = next((p for p in sc["spec"] if p["role"] in manip and "rel" not in p), None)
    if tgt is None or "region" not in tgt:
        return
    refs = list(g.get("refs") or ([g["ref"]] if g.get("ref") else []))
    d = g.get("dir")
    if d == "behind":
        # 前后任务不能照搬左右任务的 Y 分离。原来 B 被推到 FAR_Y=[-0.05,0.03]，
        # 而「放到 B 后面」要求落点 y >= B.y + gap_lo(0.05)，桌面 y 上限只有 0.08 ——
        # B 在 0.03 时落点得 >=0.08，正好压在边界上，几何上几乎无解。
        # （用户报的就是这个：「b 的初始位置要靠前一点点，方便后面还能放」。）
        # 所以 B 压到近前带，A 放在 B 更前面，往后放才有 10cm 以上的余量。
        # 参照物的 y 带：曾经按用户「b 再靠前一点」的要求从 [-0.11,-0.07] 挪到
        # [-0.13,-0.09]，结果专家产出率从 3/16(19%) 掉到 2/30(6.7%) —— 参照物往前挪
        # 会把目标的落点区间挤向桌沿，放置规划挑不出位姿。退回原值。
        # 「后面留更多空间」这个诉求改由缩小 A 的起始带来满足（A 更靠前，往后可走的距离更长）。
        tgt["region"] = [tgt["region"][0], [-0.16, -0.13]]   # 逐字照抄实测 19% 的那一版，别再微调
        for p in sc["spec"]:
            if p["role"] in refs and "region" in p:
                p["region"] = [p["region"][0], [-0.11, -0.07]]
        return
    tgt["region"] = [tgt["region"][0], list(NEAR_Y)]
    for p in sc["spec"]:
        if p["role"] in refs and "region" in p:
            p["region"] = [p["region"][0], list(FAR_Y)]


for sc in SCENES:
    normalize(sc)
    rel_layout(sc)
    fix_containers(sc)
    canon_pose(sc)

problems = []
# 指令模板必须含 {A} 占位符。generate_episode_descriptions 靠 {A} 和 play_once 写进
# info 的字段做匹配，模板里把物体名写死就匹配不上，返回空列表 ->
#   "Episode 0: No valid instructions found" -> IndexError，整个场景直接崩。
# ref_not_the_red_one / dual_pick_two_bottles / lift_pot_dual 都栽过这个坑，
# 而且是跑到评测阶段才暴露（烟测用的是另一条路径，不会报）。
for _sc in SCENES:
    if "{A}" not in _sc.get("instr", ""):
        problems.append("%s: 指令模板缺 {A} 占位符 —— 会导致 eval 阶段 IndexError"
                        % _sc["name"])

for sc in SCENES:
    if sc["name"] in KEEP_EXISTING:
        continue
    if sc["goal"]["type"] == "lift" or sc["goal"]["type"] == "moved":
        # 纯抓起类：裸方块是可以的（历史上 attr_bind_block_* 都跑得好好的），只查 contact_points
        problems += [b for b in check(sc) if "裸方块" not in b]
    else:
        problems += check(sc)
if problems:
    print("=== 生成前校验不通过 ===")
    for p in problems:
        print("  " + p)
    raise SystemExit(1)
print("校验通过：%d 个场景的被操作物都可抓" % len(SCENES))

for sc in SCENES:
    if sc["name"] in KEEP_EXISTING:
        continue
    deps = ", ".join("%d %s" % (d, BASE[d - 1]) for d in sc["deps"])
    head = ['"""%s · %s · L%d · %s' % (sc["id"], DIMNAME[sc["dim"]], sc["tier"], sc["ctx"])]
    if sc["note"]:
        head.append("")
        head.append(sc["note"])
    head += ["",
             "依赖的 RoboTwin 基础任务: " + deps,
             "由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。",
             '"""']
    body = ["from ._compo_scene import CompoScene", "", "",
            "class %s(CompoScene):" % sc["name"],
            '    A_DESC = %r' % sc["desc"]]
    if sc["mirror"]:
        body.append("    MIRROR = True")
    if sc.get("shuffle_slots"):
        body.append("    SHUFFLE_SLOTS = %r" % (sc["shuffle_slots"],))
    if sc.get("nearest"):
        body.append("    NEAREST = %r" % (sc["nearest"],))
    body.append("    GOAL = " + fmt(sc["goal"], 11))
    body.append("    SPEC = " + fmt(sc["spec"], 11))
    body.append("")
    open(os.path.join(OUT_ENV, sc["name"] + ".py"), "w", encoding="utf-8").write(
        "\n".join(head) + "\n" + "\n".join(body))

    i = sc["instr"]
    ins = {"seen": [i, i.replace("Put", "Place").replace("Pick up", "Grab"), i[:-1] + " with {a}."],
           "unseen": [i, "Please " + i[0].lower() + i[1:]],
           "_note": "%s %s L%d;判据=%s;由 suite/table.py 生成" % (
               sc["id"], DIMNAME[sc["dim"]], sc["tier"], sc["goal"]["type"])}
    ins["seen"] = list(dict.fromkeys(ins["seen"]))
    json.dump(ins, open(os.path.join(OUT_INS, sc["name"] + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

print("generated %d envs + %d instruction files" % (len(os.listdir(OUT_ENV)), len(os.listdir(OUT_INS))))
