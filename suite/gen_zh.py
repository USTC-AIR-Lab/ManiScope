# -*- coding: utf-8 -*-
"""生成中文版场景清单：每个场景操作什么物体、要达成什么目标、判据怎么判。"""
import os, sys, json, yaml
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scene_set import SCENES
from gen_scenes import manipulated_roles
from scenes import BASE

ZH = {
 "001_bottle": "饮料瓶", "002_bowl": "碗", "003_plate": "盘子", "008_tray": "托盘",
 "019_coaster": "杯垫", "021_cup": "杯子", "024_scanner": "扫码器", "039_mug": "马克杯",
 "040_rack": "杯架", "046_alarm-clock": "闹钟", "050_bell": "服务铃", "052_dumbbell": "哑铃",
 "057_toycar": "玩具车", "058_markpen": "马克笔", "059_pencup": "笔筒", "062_plasticbox": "塑料收纳箱",
 "071_can": "易拉罐", "072_electronicscale": "电子秤", "073_rubikscube": "魔方",
 "074_displaystand": "展示架", "080_pillbottle": "药瓶", "084_woodenmallet": "木槌",
 "090_trophy": "奖杯", "092_notebook": "笔记本", "100_seal": "印章", "105_sauce-can": "酱料罐",
 "106_skillet": "平底锅", "110_basket": "购物篮", "112_tea-box": "茶叶盒", "BOX": "方块",
 "070_paymentsign": "付款码牌", "102_roller": "擀面杖", "015_laptop": "笔记本电脑",
 "060_kitchenpot": "锅", "106_skillet": "平底锅", "062_plasticbox": "塑料收纳箱",
 "043_book": "书", "035_apple": "苹果", "047_mouse": "鼠标", "041_shoe": "鞋",
 "075_bread": "面包", "107_soap": "肥皂", "091_kettle": "水壶",
}
DESC_ZH = {
 "apple": "苹果", "apple in the bowl": "碗里那个苹果", "bell": "服务铃",
 "block behind the can": "易拉罐后面那块方块", "block in the basket": "篮子里那块方块",
 "block on the plate": "盘子上那块方块", "block on the tray": "托盘上那块方块",
 "block that is not red": "不是红色的那块方块", "blue cup": "蓝色的杯子",
 "bottle to the left of the can": "易拉罐左边那个瓶子", "can": "易拉罐", "cube": "魔方",
 "cube on the plate": "盘子上那个魔方", "cup": "杯子", "dumbbell": "哑铃",
 "empty cup": "空杯子", "green bottle": "绿色的瓶子", "leftmost block": "最左边那块方块",
 "marker": "马克笔", "medium block": "中等大小那块方块", "mug": "马克杯",
 "mug next to the bowl": "挨着碗的那个马克杯", "phone": "手机", "pill bottle": "药瓶",
 "red block": "红色的方块", "sauce can": "酱料罐", "seal": "印章",
 "second block from the left": "左数第二块方块", "smaller block": "更小的那块方块",
 "tea box": "茶叶盒", "toy car": "玩具车", "trophy": "奖杯", "wooden mallet": "木槌",
 "payment card": "付款码牌", "rolling pin": "擀面杖", "pot": "锅", "pad": "垫子",
 "both bottles": "两个瓶子", "left bottle": "左边的瓶子", "block": "方块",
}

AXIS = [("skill_x_object", "D1 技能 × 物体", "训练过的技能迁到没见过的物体：动作原语和物体解耦了没有"),
        ("skill_x_spatial", "D2 技能 × 空间", "空间关系迁到没见过的物体对：left/right/behind 是不是可组合的谓词"),
        ("attribute_binding", "D3 属性绑定", "必须解析属性词才能在干扰物中选对目标"),
        ("instruction_structure", "D4 指代结构", "干扰物外观全同，唯一线索是句法（在盘子上／左数第二个／不是红的）"),
        ("skill_x_skill_temporal", "D5 技能 × 技能（时序）", "两个训练过的技能串联，训练里从未融合过"),
        ("mixture", "D7 混合", "两条以上维度叠加")]
HAND = {
 "move_cup_pad": ("杯子 + 彩色垫子", "把杯子移到垫子上",
                  "杯子中心落在**垫子 footprint 内**（垫子 11×6 cm）并松开双爪。"
                  "原判据是和垫子无关的 ±2 cm 方框，比垫子本身还小 —— 已按用户要求放宽，宽严双记录"),
 "place_a2b_left_novel": ("一对训练里没成对出现过的物体（杯/马克杯/碗）", "把 A 放到 B 的左边",
                          "判据与 place_a2b_left **逐字相同**，只换了物体池"),
 "place_a2b_right_novel": ("一对训练里没成对出现过的物体（杯/马克杯/碗）", "把 A 放到 B 的右边",
                           "判据与 place_a2b_right **逐字相同**，只换了物体池"),
 "attr_bind_bottle": ("两个只差颜色的饮料瓶（棕色可乐 / 绿色雪碧）", "拿起指定颜色的那个瓶子",
                      "目标位移 > 0.05m 且大于干扰物（判「去够的是哪一个」，不判高度）"),
 "attr_bind_soap_box": ("肥皂 / 茶叶盒 三件套：目标、同色异类、同类异色", "拿起「黄色的肥皂」",
                        "目标抬升 > 0.10m。只看颜色 50%，只看类别 50%，必须同时绑定才稳"),
 "move_cube_on_plate_to_pad": ("盘子上一个魔方 + 桌面一个外观完全相同的魔方 + 垫子",
                               "把「盘子上的那个」魔方移到垫子上",
                               "目标魔方抬升 > 0.10m；先抬错的直接判负"),
 "adjust_bottle_dustbin": ("躺着的饮料瓶 + 垃圾桶", "先把瓶子扶正，再投进垃圾桶",
                           "瓶子进桶即可（不要求先扶正，两段 stage 判据）"),
 "click_bell_press_stapler": ("服务铃 + 订书机（分居左右，各由一条手臂负责）", "先按响铃铛，再按下订书机",
                              "stage ≥ 2，且 stage2 必须发生在 stage1 之后"),
 "stapler_pad_press": ("订书机 + 垫子", "先把订书机放到垫子上，再按下去",
                       "stage ≥ 2，且 stage2 必须在 stage1 之后"),
}

def zh(m):
    return ZH.get(m, m)

def obj_zh(sc):
    """被操作物 / 其它物体，都翻成中文。"""
    man = manipulated_roles(sc["goal"])
    tgt, others = [], []
    for p in sc["spec"]:
        nm = zh(p["model"]) if p.get("kind") == "model" else ("垫子" if p["role"] in ("pad", "mat") else zh("BOX"))
        d = p.get("desc")
        dz = DESC_ZH.get(d, d) if d else None
        label = nm if (not dz or dz == nm) else "%s（%s）" % (nm, dz)
        (tgt if p["role"] in man else others).append(label)
    return "、".join(tgt) or "—", "、".join(others) or "—"

def goal_zh(g, spec):
    def role(r):
        for p in spec:
            if p["role"] == r:
                if p.get("kind") == "model":
                    return zh(p["model"])
                return "垫子" if p["role"] in ("pad", "mat") else zh("BOX")
        return r
    t = g.get("type")
    if t == "lift":
        return "把目标**拿离桌面** %.0f cm 以上" % (g.get("dz", 0.06) * 100)
    if t == "on":
        e = g.get("eps", [0.035, 0.035, 0.03])
        return "把目标**放到「%s」上面**（水平偏差 ±%.1f cm 内），并**松开双爪**" % (role(g["ref"]), e[0] * 100)
    if t == "in":
        return "把目标**放进「%s」里**（水平距容器中心 %.0f cm 内、不低于容器口），并**松开双爪**" % (
            role(g["ref"]), g.get("r", 0.12) * 100)
    if t == "rel":
        d = {"left": "左", "right": "右", "front": "前", "behind": "后"}[g.get("dir", "left")]
        lo, hi = g.get("gap", [0.05, 0.22])
        return "把目标**放到「%s」的%s边**（间距 %.0f–%.0f cm，横向不跑偏），并**松开双爪**" % (
            role(g["ref"]), d, lo * 100, hi * 100)
    if t == "press":
        return "**按下「%s」**（夹爪触到按压点），且物体不能被搬走（位移 < %.0f cm）" % (
            role(g.get("ref", "target")), g.get("max_move", 0.04) * 100)
    if t == "seq":
        return "　→　".join("**第%d步**：%s" % (i + 1, goal_zh(x, spec)) for i, x in enumerate(g["stages"]))
    return t

def instr_zh(sc):
    """把英文指令模板转成中文说法。"""
    t = sc["goal"]["type"]
    man = manipulated_roles(sc["goal"])
    a = DESC_ZH.get(sc.get("desc"), sc.get("desc")) or next((zh(p["model"]) if p.get("kind") == "model" else zh("BOX")
                                for p in sc["spec"] if p["role"] in man), "目标")
    def rn(r):
        for p in sc["spec"]:
            if p["role"] == r:
                if p.get("kind") == "model":
                    return zh(p["model"])
                return "垫子" if p["role"] in ("pad", "mat") else zh("BOX")
        return r
    g = sc["goal"]
    if t == "lift":
        return "拿起%s" % a
    if t == "on":
        return "把%s放到%s上" % (a, rn(g["ref"]))
    if t == "in":
        return "把%s放进%s里" % (a, rn(g["ref"]))
    if t == "rel":
        d = {"left": "左", "right": "右", "front": "前", "behind": "后"}[g.get("dir", "left")]
        return "把%s放到%s的%s边" % (a, rn(g["ref"]), d)
    if t == "press":
        return "按一下%s" % rn(g.get("ref", "target"))
    if t == "seq":
        return "，再".join(instr_zh({"goal": s, "spec": sc["spec"], "desc": sc.get("desc")})
                           for s in g["stages"])
    return a

def main():
    y = yaml.safe_load(open(os.path.join(HERE, "scenes_v2.yaml"), encoding="utf-8"))
    by = {s["name"]: s for s in SCENES}
    out = ["# 组合泛化场景 · 中文任务清单", "",
           "对应总览图 `compo_v2_overview.png`。**判据分两层，缺一不可**：",
           "1. **选对** —— 目标物体的位移必须严格大于所有干扰物（不解析指令的策略拿不到分）；",
           "2. **做对** —— 下表「达成条件」，即任务名承诺的那个终态。", "",
           "`专家` = 专家演示的产出率，≥ 2/8 才进这张表。", ""]
    n = 0
    for key, title, desc in AXIS:
        scs = (y["axes"].get(key) or {}).get("scenes") or []
        if not scs:
            continue
        out += ["", "## %s" % title, "", "> %s" % desc, "",
                "| # | 场景 | 难度 | 操作的物体 | 场上其它物体 | 指令 | 达成条件 | 生活场景 | 专家 |",
                "|---|---|---|---|---|---|---|---|---|"]
        for sc in scs:
            n += 1
            name = sc["name"]
            t = by.get(name)
            if t is None or sc.get("source") == "handwritten":
                o, gl, cond = HAND.get(name, ("见 `envs/%s.py`" % name, "—", "手写判据"))
                out.append("| %d | `%s` | L%s | %s | — | %s | %s | %s | %s |" % (
                    n, name, sc.get("tier", "?"), o, gl, cond, sc.get("context", ""), sc.get("smoke", "")))
                continue
            tgt, others = obj_zh(t)
            out.append("| %d | `%s` | L%s | %s | %s | %s | %s | %s | %s |" % (
                n, name, sc.get("tier", "?"), tgt, others, instr_zh(t), goal_zh(t["goal"], t["spec"]),
                sc.get("context", ""), sc.get("smoke", "")))
    open(os.path.join(HERE, "场景清单_中文.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("写出 %d 个场景 -> 场景清单_中文.md" % n)

if __name__ == "__main__":
    main()
