# -*- coding: utf-8 -*-
"""重构后的组合泛化场景表（声明式）。一行一个场景，直接编译成 envs/*.py。

约定：
  L / R / C  = 左 / 右 / 中 生成区，互不重叠，避免 setup 阶段的 UnStableError
  deps       = 潜在依赖的 RoboTwin 50 任务序号（用于 collect.py 的归因和依赖图）
  goal       = 终态判据，同时也是专家动作的编排来源（同源，见 _compo_scene.py）
"""
L  = [[-0.24, -0.14], [-0.15, -0.04]]
R  = [[0.14, 0.24], [-0.15, -0.04]]
C  = [[-0.05, 0.05], [-0.14, -0.04]]
LL = [[-0.26, -0.18], [-0.15, -0.05]]
RR = [[0.18, 0.26], [-0.15, -0.05]]
CB = [[-0.05, 0.05], [0.0, 0.08]]      # 中后方：容器/参照物
L3, C3, R3 = [[-0.24, -0.17], [-0.13, -0.05]], [[-0.04, 0.04], [-0.13, -0.05]], [[0.17, 0.24], [-0.13, -0.05]]

QU = [1, 0, 0, 0]          # 直立
QS = [0.5, 0.5, 0.5, 0.5]  # 侧放（篮子/盘子/铃铛常用）
QL = [0.707, 0.707, 0, 0]  # 躺姿（罐/玩具车等，不分左右）
QM = [0.707, 0.707, 0, 0]  # 杯/马克杯/玩具车的可用姿态（v1 实测）
# 躺姿瓶/罐按侧选姿态 —— 取自 adjust_bottle / attr_bind_bottle 的实测配置。
# 统一姿态两边通吃会让一侧的抓取规划返回 None（实测 0-1/8）。
LR = [[0.707, 0.0, 0.0, -0.707], [0.707, 0.0, 0.0, 0.707]]

def box(role, color, region, half=0.025, desc=None, **kw):
    d = {"role": role, "kind": "box", "color": color, "half": half, "region": region}
    if desc: d["desc"] = desc
    d.update(kw); return d

def mdl(role, model, ids, region, qpos=QU, **kw):
    d = {"role": role, "kind": "model", "model": model, "ids": ids, "region": region, "qpos": qpos}
    d.update(kw); return d

def pad(role="pad", region=C, color=(0.45, 0.45, 0.45), **kw):
    d = {"role": role, "kind": "box", "color": color, "half_size": [0.055, 0.055, 0.0005],
         "region": region, "rot": False, "zlim": [0.7415], "pad": 0.12, "desc": "pad"}
    d.update(kw)   # 允许 side / side_x 之类的槽位覆盖
    return d

RED, BLUE, GREEN, GRAY, ORANGE = (0.9,0.15,0.15), (0.15,0.3,0.9), (0.15,0.75,0.2), (0.45,0.45,0.45), (0.95,0.6,0.1)

CL = [[-0.13, -0.03], [-0.15, -0.04]]   # 落点：和 L 同侧（跨身放置规划不出来，见 _compo_scene 注释）
CBL = [[-0.10, -0.02], [-0.02, 0.06]]   # 落点：同侧偏后（容器）

def S(id, name, dim, tier, deps, ctx, instr, goal, spec, desc=None, mirror=False, note="",
      shuffle_slots=None, nearest=None):
    # shuffle_slots: 这几个 role 的生成区随机对调。属性类场景需要它 ——
    # 目标固定在同一个槽位的话，策略靠位置就能蒙对，属性词没被真正考到。
    # 序位类（最左/左数第二）**不能**用：那里位置本身就是线索。
    # nearest: 生成时校验「目标确实是离参照物最近的那一个」，不满足就重采干扰物。
    # 指代类场景的指代必须为真 —— ref_mug_next_to_bowl 上出现过干扰杯反而离碗更近。
    return dict(id=id, name=name, dim=dim, tier=tier, deps=deps, ctx=ctx, instr=instr,
                goal=goal, spec=spec, desc=desc, mirror=mirror, note=note,
                shuffle_slots=shuffle_slots, nearest=nearest)

SCENES = [
# ============================== D1 skill × object ==============================
S("D1-01","move_cup_pad","D1",1,[16],"办公桌","Move the {A} onto the pad.",
  {"type":"on","ref":"pad"},
  [mdl("target","021_cup",[0,1,2,3,4,5],L,QS), pad(region=CL)], desc="cup"),
S("D1-03","move_can_coaster","D1",1,[26,30],"床头药盒","Put the {A} on the coaster.",
  {"type":"on","ref":"coaster"},
  [mdl("target","071_can",[0,1,2],L,[0.5,0.5,0.5,0.5],rot=False),
   # 药瓶必须**竖直**摆，且不要随机旋转 —— 用 QU=[1,0,0,0] 是躺着的，夹爪一碰就滚走，
   # 抓不住。[0.5,0.5,0.5,0.5]+rotate_rand=False 取自它自己的源任务 move_pillbottle_pad。
   # 查过一遍：RoboTwin 原任务里**所有被操作物**都用 [0.5,0.5,0.5,0.5] 这个规范姿态。
   mdl("coaster","019_coaster",[0],CL,QS,static=True,pad=0.05)], desc="pill bottle"),
S("D1-05","grasp_mallet_novel","D1",2,[2,8],"工具台","Pick up the {A}.",
  # 0.08 -> 0.05 -> 0.035。最后这一档由诊断数据定：失败样本里有一半是
  # 「被夹爪夹着、确实离地 0.0355 / 0.0412」，全卡在 0.05 门槛下方一点点；
  # 另一半净空不到 1 毫米（纯粹在桌面上拖行），0.035 不会把那一类放进来。
  {"type":"lift","dz":0.035},
  [mdl("target","084_woodenmallet",[0,1,2,3,4],L,QL)], desc="wooden mallet"),
S("D1-07","place_teabox_scale","D1",1,[34],"超市称重","Put the {A} on the scale.",
  {"type":"on","ref":"scale"},
  [mdl("target","112_tea-box",[0,1,2,3,4,5],L,QU),
   mdl("scale","072_electronicscale",[0,1,2],CL,QS,static=True,pad=0.06)], desc="tea box"),
S("D1-08","place_seal_coaster","D1",2,[49,30],"厨房备餐","Put the {A} on the coaster.",
  {"type":"on","ref":"coaster"},
  [mdl("target","100_seal",[0,1,2,3],L,[0.5,0.5,0.5,0.5],rot=False),
   mdl("coaster","019_coaster",[0],CL,QS,static=True,pad=0.05)], desc="seal"),
S("D1-09","lift_trophy","D1",2,[8],"厨房备餐","Pick up the {A}.",
  {"type":"lift","dz":0.06},
  [mdl("target","090_trophy",[0,1,2,3,4],L,QU,mass=0.2)], desc="trophy"),
S("D1-10","grab_dumbbell","D1",1,[8],"健身角","Pick up the {A}.",
  {"type":"lift","dz":0.035},  # 同 grasp_mallet_novel，见那里的注释
  [mdl("target","052_dumbbell",[0,1,2,3,4,5,6],L,QL)], desc="dumbbell"),
S("D1-12","place_teabox_stand","D1",2,[35],"书架","Put the {A} on the display stand.",
  {"type":"on","ref":"stand"},
  [mdl("target","112_tea-box",[0,1,2],L,QU),
   mdl("stand","074_displaystand",[0,1,2,3,4],CL,QS,static=True,pad=0.06)], desc="tea box"),
S("D1-14","place_toycar_plasticbox","D1",2,[33,27],"玄关","Put the {A} into the plastic box.",
  {"type":"in","ref":"box","r":0.13},
  [mdl("target","057_toycar",[0,1,2,3,4,5],L,QM),
   mdl("box","062_plasticbox",[3,5],CBL,QS,mass=0.6,pad=0.05)], desc="toy car"),
S("D1-15","place_teabox_skillet","D1",2,[24],"厨房备餐","Put the {A} into the skillet.",
  # 茶叶盒边长 9.6cm、锅口大，放进去时中心可以离锅心较远（用户 ep18 实测）
  {"type":"in","ref":"skillet","r":0.16},
  [mdl("target","112_tea-box",[0,1,2,3,4],L,QU),
   mdl("skillet","106_skillet",[0,1,2,3],CBL,QS,mass=0.6,pad=0.05)], desc="tea box"),
]

SCENES += [
# ============================== D2 skill × spatial ==============================
S("D2-01","place_a2b_left_novel","D2",1,[21],"通用桌面","Put the {A} to the left of the mug.",
  {"type":"rel","ref":"ref","dir":"left","gap":[0.05,0.24],"lat":0.13},
  [mdl("target","073_rubikscube",[0,1,2],L,QU),
   mdl("ref","039_mug",[0,1,2,3],CL,QS,static=True,pad=0.06)], desc="cube"),
S("D2-02","place_a2b_right_novel","D2",1,[22],"通用桌面","Put the {A} to the right of the mug.",
  {"type":"rel","ref":"ref","dir":"right","gap":[0.05,0.24],"lat":0.13},
  [mdl("target","073_rubikscube",[0,1,2],LL,QU),
   mdl("ref","039_mug",[0,1,2,3],[[-0.15,-0.09],[-0.15,-0.04]],QS,static=True,pad=0.06)], desc="cube"),
S("D2-05","place_between_bowls","D2",3,[21,22,48],"餐桌摆盘","Put the {A} between the two bowls.",
  {"type":"between","refs":["b1","b2"],"lat":0.10},
  [mdl("target","073_rubikscube",[0,1,2],[[-0.24,-0.18],[-0.15,-0.08]],QU),
   mdl("b1","002_bowl",[1,2,3],[[-0.16,-0.12],[-0.04,0.02]],QS,static=True,pad=0.05),
   mdl("b2","002_bowl",[4,5,6],[[-0.02,0.02],[-0.04,0.02]],QS,static=True,pad=0.05)], desc="cube"),
S("D2-06","place_cube_right_of_plate","D2",2,[21,22,28],"餐桌摆盘","Put the {A} to the right of the plate.",
  # gap 下界必须大于盘子半径(约 0.10)，否则「落在盘内偏右」也算成功。
  # 用户实测指出：只有和盘子基本不重合时才该算「放到盘子右边」。
  {"type":"rel","ref":"plate","dir":"right","gap":[0.14,0.26],"lat":0.13},
  [mdl("target","073_rubikscube",[0,1,2],LL,QU),
   mdl("plate","003_plate",[0],[[-0.16,-0.10],[-0.14,-0.04]],QS,static=True,pad=0.05)], desc="cube"),
S("D2-08","put_toycar_left_basket","D2",2,[33,21],"家务分拣","Put the {A} into the left basket.",
  {"type":"in","ref":"basket_l","r":0.12},
  [mdl("target","057_toycar",[0,1,2,3,4,5],LL,[0.707,0.707,0,0]),
   mdl("basket_l","110_basket",[0,1],[[-0.14,-0.08],[0.0,0.06]],QS,mass=0.5,pad=0.05),
   # 右篮再往右推：默认槽位 ±0.165 会让它落在 [0.12,0.21]，夹小车时手会碰到它
   mdl("basket_r","110_basket",[2,3],[[0.10,0.16],[0.0,0.06]],QS,mass=0.5,pad=0.05,
       side=1,side_x=0.195)], desc="toy car"),
S("D2-10","place_can_right_of_plasticbox","D2",2,[27,21],"仓储上架","Put the {A} to the right of the plastic box.",
  # upright：用户实测第一条 success 的罐子是**倒在**右边的。rel 判据原来只看位置，
  # 推倒滚过去也算过 —— 那测的就不是「放置」了。要求罐子局部 z 轴和世界 z 轴夹角小。
  {"type":"rel","ref":"pbox","dir":"right","gap":[0.05,0.24],"lat":0.14,"upright":True},
  [mdl("target","071_can",[0,1,2,3],L,QU,rot=False,half=0.035),
   mdl("pbox","062_plasticbox",[3,5],[[-0.04,0.02],[-0.06,0.02]],QS,static=True,pad=0.06,side=-1)],
  desc="can",
  note="方向从 left 翻成 right：收纳箱在最右、往左放时落点跨度最大，专家稳定 0/8"
       "（可达范围 |x|<=0.22 放不下）。翻成收纳箱在左、往右放，语义等价但几何可行。"),
S("D2-11","place_teabox_front_of_skillet","D2",2,[24,21],"厨房备餐","Put the {A} in front of the skillet.",
  {"type":"rel","ref":"skillet","dir":"front","gap":[0.05,0.22],"lat":0.14},
  [mdl("target","112_tea-box",[0,1,2,3,4],[[-0.24,-0.16],[-0.02,0.06]],QU),
   mdl("skillet","106_skillet",[0,1,2,3],[[-0.16,-0.06],[-0.02,0.06]],QS,static=True,pad=0.06)], desc="tea box"),
]

# dz=0.06 而不是 0.10：001_bottle 躺着时中心离桌面 0.034，光「扶正」就升到 0.124，
# 0.10 的阈值扶正就能过；但阈值再往上顶又会顶到专家自己都够不着（实测真抓起来才 0.148），
# expert_check 会无限拒种子。0.06 配合 EXCLUSIVE 那层（位移必须大于干扰物）才是有效判据。
LIFT = {"type": "lift", "dz": 0.06}

SCENES += [
# ========================= D3 属性绑定：5 类属性 × 4 类动作 =========================
S("D3-02","attr_color_block_3way","D3",2,[45,9],"积木码垛","Pick up the {A}.", LIFT,
  [box("target",RED,L3,desc="red block"), box("d1",GREEN,C3), box("d2",BLUE,R3)],
  desc="red block", shuffle_slots=['target', 'd1', 'd2'], mirror=True, note="三路颜色干扰，随机基线 33%"),
S("D3-04","attr_size_block_pick","D3",2,[4,45],"积木码垛","Pick up the {A}.", LIFT,
  [box("target",GRAY,LL,half=0.016,desc="smaller block"),
   box("distractor",GRAY,[[-0.24,-0.18],[-0.02,0.06]],half=0.030)],
  desc="smaller block", mirror=True,
  note="尺寸属性。用裸方块 + lift 判据：方块能抓能举，但过不了 place_actor(实测 0-1/10)，"
       "所以尺寸这一维只能做纯抓取；容器动作那一维由 D3-05/D3-11 承担"),
S("D3-05","attr_category_can_plasticbox","D3",2,[27,19],"仓储上架","Put the {A} into the plastic box.",
  {"type":"in","ref":"pbox","r":0.13},
  [mdl("target","071_can",[0,1,2,3],LL,QL,desc="can"),
   mdl("distractor","001_bottle",[13,16],[[-0.24,-0.18],[-0.02,0.06]],QL),
   mdl("pbox","062_plasticbox",[3,5],CBL,QS,mass=0.6,pad=0.05)],
  desc="can", note="类别属性 + 容器动作"),
S("D3-08","attr_size_rank_middle","D3",3,[4,28],"家务分拣","Pick up the {A}.", LIFT,
  [box("target",GRAY,C3,half=0.023,desc="medium block"),
   box("small",GRAY,L3,half=0.015), box("big",GRAY,R3,half=0.031)],
  shuffle_slots=['target', 'd1', 'd2'], desc="medium block", note="尺寸序位（三选一的中间档），比二选一的大/小难一级"),
S("D3-10","attr_category_press_bell","D3",1,[6,5],"前台服务","Press the {A}.",
  {"type":"press","ref":"target","model":"050_bell","cp":0},
  [mdl("target","050_bell",[0,1],L,QS,mass=0.3,pad=0.1,desc="bell"),
   mdl("distractor","046_alarm-clock",[0,1,2],R,QS,mass=0.3,pad=0.1)],
  desc="bell", mirror=True,
  note="按压型动作上的属性绑定 —— 不涉及抓取，语言信号最干净"),

# ===================== D4 指代结构：嵌套/序位/序数/邻接/否定 =====================
S("D4-01","ref_block_on_plate","D4",1,[28],"餐桌收拾","Pick up the {A}.", LIFT,
  [mdl("plate","003_plate",[0],L,QS,static=True,pad=0.03),
   {"role":"target","kind":"box","color":ORANGE,"half":0.025,"rel":"plate","offset":[0,0,0.035],
    "desc":"block on the plate"},
   box("distractor",ORANGE,R)], desc="block on the plate", mirror=True,
  note="两块外观全同，唯一线索是「在盘子上」这个关系"),
# ref_block_in_basket 已按用户要求删除：篮子里的方块取不出来（夹爪进不去，
# 逐变体实测过 id2/id3 能过是**专家**能过，策略侧不可解）。改由新场景补位。
S("D4-03","ref_block_behind_can","D4",2,[21,22],"通用桌面","Pick up the {A}.", LIFT,
  [mdl("can","071_can",[0,1,2],[[-0.20,-0.14],[-0.14,-0.08]],[0.5,0.5,0.5,0.5],rot=False,static=True,pad=0.03),
   {"role":"target","kind":"box","color":ORANGE,"half":0.025,"rel":"can","offset":[0,0.11,-0.02],
    "desc":"block behind the can"},
   box("distractor",ORANGE,R)], desc="block behind the can", mirror=True),
S("D4-04","ref_second_from_left","D4",2,[3,45],"积木码垛","Pick up the {A}.", LIFT,
  [box("d1",ORANGE,L3), box("target",ORANGE,C3,desc="second block from the left"), box("d2",ORANGE,R3)],
  desc="second block from the left", note="序位；MIRROR 必须关，镜像会改答案"),
S("D4-05","ref_leftmost_of_four","D4",2,[3,45],"积木码垛","Pick up the {A}.", LIFT,
  [box("target",ORANGE,[[-0.26,-0.22],[-0.13,-0.05]],desc="leftmost block"),
   box("d1",ORANGE,[[-0.13,-0.09],[-0.13,-0.05]]), box("d2",ORANGE,[[0.00,0.04],[-0.13,-0.05]]),
   box("d3",ORANGE,[[0.13,0.17],[-0.13,-0.05]])], desc="leftmost block",
  note="四选一的序位，比三选一难一级"),
S("D4-06","ref_mug_next_to_bowl","D4",2,[11,48],"餐桌收拾","Pick up the {A}.", LIFT,
  # 旧配置里这句指代**可能是假的**：gen_scenes 会把 rel 锚点(碗)夹到 x in [-0.06,0.06]，
  # 碗最右到 0.06、干扰杯最左到 0.15 —— 干扰杯离碗只有 0.09，比目标杯的 0.10 还近。
  # 「挨着碗的那个」指到了干扰杯身上，判据却认另一个，怎么做都是错的。
  # 现在：目标 offset 收到 -0.09，干扰杯推到右后角，碗压在近前 —— 两者到碗的距离
  # 拉开到 ~2 倍。mirror 关掉：offset 不参与镜像，翻过去会把两个杯子挤到同一侧。
  [mdl("bowl","002_bowl",[1,2,3],[[-0.18,-0.12],[-0.12,-0.04]],QS,static=True,pad=0.03),
   {"role":"target","kind":"model","model":"039_mug","ids":[0,1,2],"rel":"bowl","offset":[-0.10,0,0],
    "qpos":QS,"desc":"mug next to the bowl"},
   mdl("distractor","039_mug",[0,1,2],[[0.15,0.22],[-0.14,-0.04]],QS)], desc="mug next to the bowl",
  mirror=True, nearest={"who":"target","ref":"bowl","rivals":["distractor"],"ratio":1.6}),
S("D4-07","ref_not_the_red_one","D4",2,[3],"积木码垛","Pick up the {A}.", LIFT,
  [box("target",BLUE,L,desc="block that is not red"), box("distractor",RED,R)],
  desc="block that is not red", mirror=True, note="否定式指代 —— 旧套件完全没有这一类"),
S("D4-08","ref_cup_on_tray","D4",2,[25],"快餐取餐","Pick up the {A}.", LIFT,
  [mdl("tray","008_tray",[0,1,2,3],L,QS,static=True,pad=0.03),
   {"role":"target","kind":"box","color":ORANGE,"half":0.025,"rel":"tray","offset":[0,0,0.035],
    "desc":"block on the tray"},
   box("distractor",ORANGE,R)], desc="block on the tray", mirror=True),
]

def seq(*g): return {"type": "seq", "stages": list(g)}
def ON(ref, who=None, dz=0.03, eps=(0.05,0.05,0.035)):
    d = {"type":"on","ref":ref,"dz":dz,"eps":list(eps)}
    if who: d["who"]=who
    return d
def IN(ref, who=None, r=0.12):
    d = {"type":"in","ref":ref,"r":r}
    if who: d["who"]=who
    return d
def PRESS(ref, model, cp=0):
    return {"type":"press","ref":ref,"model":model,"cp":cp}
def REL(ref, dir, who=None, gap=(0.05,0.22), lat=0.14):
    d = {"type":"rel","ref":ref,"dir":dir,"gap":list(gap),"lat":lat}
    if who: d["who"]=who
    return d
BELL = lambda region=[[-0.06,0.00],[0.02,0.08]]: mdl("bell","050_bell",[0,1],region,QS,mass=0.3,pad=0.08)

SCENES += [
# ============= D5 skill × skill 时序：两段有真实先后依赖，第二段各不相同 =============
S("D5-02","serve_teabox_then_ring","D5",2,[23,6],"厨房备餐",
  "Put the {A} into the basket, then press the bell.",
  seq(IN("breadbasket"), PRESS("bell","050_bell")),
  [mdl("target","112_tea-box",[0,1,2,3],LL,QU,desc="tea box"),
   mdl("breadbasket","110_basket",[0,1,2,3],[[-0.14,-0.08],[-0.02,0.05]],QS,mass=0.5,pad=0.05),
   BELL()], desc="tea box", note="上餐后按铃叫号"),
S("D5-06","pack_toycar_then_ring","D5",3,[33,27,6],"玄关",
  "Put the {A} into the plastic box, then press the bell.",
  seq(IN("box", r=0.13), PRESS("bell","050_bell")),
  [mdl("target","057_toycar",[0,1,2,3,4,5],LL,QM,desc="toy car"),
   mdl("box","062_plasticbox",[3,5],[[-0.14,-0.08],[-0.02,0.05]],QS,mass=0.6,pad=0.05),
   BELL()], desc="toy car"),

# ================================ D7 mixture ================================
S("D7-06","attr_teabox_basket_then_ring","D7",3,[23,6,19],"厨房备餐",
  "Put the {A} into the basket, then press the bell.",
  seq(IN("breadbasket"), PRESS("bell","050_bell")),
  [mdl("target","112_tea-box",[0,1,2],[[-0.28,-0.23],[-0.14,-0.07]],QU,desc="tea box"),
   mdl("distractor","035_apple",[0,1],[[-0.28,-0.23],[0.01,0.07]],QU),
   mdl("breadbasket","110_basket",[0,1,2,3],[[-0.16,-0.10],[-0.02,0.05]],QS,mass=0.5,pad=0.05),
   BELL([[-0.02,0.04],[0.02,0.08]])], desc="tea box", note="属性 × 时序"),

# ===== 用户后补场景（2026-09-07）=====
# 均已实测物体可抓性；open_microwave+放面包 因微波炉是前开口腔体、place_actor 从 +z
# 下降插不进去（v1 已踩过），按用户意见不加。
  S("D1-16","roller_to_plate","D1",2,[8,28],"厨房备餐","Put the {A} on the plate.",
    {"type":"on","ref":"plate"},
    [mdl("target","102_roller",[0,1,2],C,[0.5,0.5,0.5,0.5],rot=False),
     mdl("plate","003_plate",[0],CL,QS,static=True,pad=0.05)], desc="rolling pin",
    note="grab_roller 的技能 + 放到盘子上。擀面杖实测 2/3（规范姿态）"),

  S("D2-12","card_right_of_scanner","D2",2,[41,42,22],"超市结账",
    "Put the {A} to the right of the barcode scanner.",
    {"type":"rel","ref":"scanner","dir":"right","gap":[0.05,0.22],
     # 起始必须离扫码器足够远：初始守卫只保证「不满足判据」，
     # 卡片可能刚好卡在 gap 边界外一点点、视觉上仍贴着。min_start 要求
     # 初始距离至少这么大，不够就重新摆。
     "min_start":0.18},
    [mdl("target","070_paymentsign",[0,1,2],C,[0.5,0.5,0.5,0.5],rot=False),
     mdl("scanner","024_scanner",[0,1,2,3,4],CL,[0,0,0.707,0.707],static=True,pad=0.08)],
    desc="payment card",
    note="rotate_qrcode 的物体 + 空间关系。rotate_qrcode 此前零覆盖"),

  S("D2-13","phone_right_of_laptop","D2",2,[17,36,22],"办公桌",
    "Put the {A} to the right of the laptop.",
    {"type":"rel","ref":"laptop","dir":"right","gap":[0.05,0.22]},
    # laptop 必须排在 phone **前面**：phone 用 rel 挂在它上面，摆 phone 时 laptop 得已存在
    # （顺序颠倒会 KeyError('laptop')）。手机初始放在电脑上，成功=移到右边且不再重叠 ——
    # 按用户建议改的：原来手机一开始就在电脑右边，策略不动也可能判成功。
    [{"role":"laptop","kind":"urdf","model":"015_laptop","ids":[0],
      "region":[[-0.16,-0.06],[-0.06,0.04]],"qpos":[0.7,0,0,0.7],"rot":False,
      "fix_root":True,"mass":1.0,"pad":0.08},
     {"role":"target","kind":"model","model":"077_phone","ids":[0,1,2,3],
      "rel":"laptop","offset":[0,0,0.07],"qpos":[0.5,0.5,0.5,0.5],"desc":"phone"}],
    desc="phone",
    note="用户提的 open_laptop+放手机。开盖需要关节开度判据(暂无)，先做空间关系版"),


  # lift_pot_dual（只抬起）已按用户要求删除：RoboTwin 本身就有 lift_pot，
  # 组合场景必须加上「放到垫子上」那一步才有增量，见下面的 lift_pot_to_pad。

# ---------------------------------------------------------------- 敲击类（新增）
# 用户要求补的两个场景。原话提到 dump_bin_bigbin，但那个任务是把桌面小垃圾桶
# **倒进**大垃圾桶，动作里没有「敲击」；「敲击方块」是 beat_block_hammer。
# 所以这两个建在 beat_block_hammer 上，判据与它同口径（锤头 fp0 落到方块 fp1 且接触）。
# 方块全部 static：敲中了也不会移动，所以「选对了没有」不靠位移比大小，只看落点。
S("D3-12","attr_color_beat_block","D3",2,[2,45],"积木码垛",
  "Beat the {A} with the hammer.",
  {"type":"beat","tool":"hammer"},
  [mdl("hammer","020_hammer",[0],[[-0.02,0.02],[-0.08,-0.04]],[0,0,0.995,0.105],
       rot=False,zlim=[0.783],mass=0.001),
   # 三段互不相邻：块半宽 0.025，两块中心至少差 0.11 才不会因为随机旋转蹭到一起
   box("target",(0.55,0.20,0.75),[[-0.22,-0.17],[0.01,0.07]],half=0.025,static=True,zlim=[0.76],desc="purple block"),
   box("d1",(0.10,0.65,0.62),[[-0.03,0.03],[0.01,0.07]],half=0.025,static=True,zlim=[0.76]),
   box("d2",(0.92,0.82,0.15),[[0.17,0.22],[0.01,0.07]],half=0.025,static=True,zlim=[0.76])],
  desc="purple block", shuffle_slots=["target","d1","d2"],
  note="颜色选紫/青/黄 —— 训练集里方块基本是红/蓝/绿，少见色更能考「按词选」而不是按先验蒙"),
S("D3-13","attr_size_beat_smaller","D3",2,[2,4],"积木码垛",
  "Beat the {A} with the hammer.",
  {"type":"beat","tool":"hammer"},
  [mdl("hammer","020_hammer",[0],[[-0.02,0.02],[-0.08,-0.04]],[0,0,0.995,0.105],
       rot=False,zlim=[0.783],mass=0.001),
   box("target",(0.10,0.65,0.62),[[-0.24,-0.16],[0.01,0.07]],half=0.020,static=True,zlim=[0.76],desc="smaller block"),
   box("d1",(0.10,0.65,0.62),[[0.16,0.24],[0.01,0.07]],half=0.038,static=True,zlim=[0.76])],
  desc="smaller block", shuffle_slots=["target","d1"],
  note="同色异尺寸，唯一线索是大小"),
S("D5-11","lift_pot_to_pad","D5",3,[12,16],"厨房备餐",
  "Lift the {A} with both arms and put it on the pad.",
  {"type":"dual_carry_to","ref":"pad","dz":0.06,"eps":[0.09,0.09]},
  # fix_root=False 是关键：_place 的 urdf 分支默认把根链接焊死，锅就抬不起来了。
  [{"role":"target","kind":"urdf","model":"060_kitchenpot","ids":[0,1],"fix_root":False,
    # 锅的生成区必须逐字照抄原任务 lift_pot：往前挪 5cm 双臂抓取就规划不出来(实测 0/12)
    "region":[[-0.05,0.05],[-0.05,0.05]],"qpos":[0.704141,0,0,0.71006],"rot":True,"rotlim":[0,0,0.39]},
   # 垫子拉近：一步搬 16cm 双臂 IK 解不出来，实测抬起后只挪到离垫子 0.104
   pad(region=[[0.09,0.13],[-0.05,0.05]])], desc="pot",
  note="用户提的 lift_pot 组合版：双臂各抓一个把手抬起，再一起送到垫子上松手"),
]
