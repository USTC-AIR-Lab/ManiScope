# -*- coding: utf-8 -*-
"""生成场景目标清单：每个场景要做成什么、判据怎么判、依赖哪些 RoboTwin 任务。
维度/难度/生活场景/依赖 全部从 scenes_v2.yaml 出（唯一事实来源）；
生成场景的达成条件由 table.py 的 GOAL 翻译，手写场景用它自己的 note。"""
import os, sys, yaml
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scene_set import SCENES
from scenes import BASE

AXIS = [("skill_x_object", "D1 技能×物体", "训练过的技能迁到没见过的物体"),
        ("skill_x_spatial", "D2 技能×空间", "空间关系迁到没见过的物体对"),
        ("attribute_binding", "D3 属性绑定", "必须解析属性词才能在干扰物中选对"),
        ("instruction_structure", "D4 指代结构", "必须解析指代结构才能锁定目标"),
        ("skill_x_skill_temporal", "D5 技能×技能(时序)", "两个训练过的技能串联，训练里从未融合"),
        ("mixture", "D7 混合", "两条以上维度叠加")]


def goal_zh(g, spec):
    def role(r):
        for p in spec:
            if p["role"] == r:
                return p.get("desc") or (p.get("model", "").split("_", 1)[-1]
                                         if p["kind"] == "model" else "方块")
        return r
    t = g.get("type")
    who = role(g.get("who", "target"))
    if t == "lift":
        return "把目标抬离桌面 >%.2fm" % g.get("dz", 0.06)
    if t == "moved":
        return "目标位移 >%.2fm" % g.get("eps", 0.05)
    if t in ("on", "stack"):
        e = g.get("eps", [0.035, 0.035, 0.03])
        v = "叠在" if t == "stack" else "落在"
        return "%s %s「%s」上方（xy 容差 ±%.03gm），双爪张开" % (who, v, role(g["ref"]), e[0])
    if t == "in":
        return "%s 落进「%s」内（xy 距中心 <%.02fm、不低于容器口），双爪张开" % (
            who, role(g["ref"]), g.get("r", 0.12))
    if t == "rel":
        d = {"left": "左", "right": "右", "front": "前", "behind": "后"}[g.get("dir", "left")]
        lo, hi = g.get("gap", [0.05, 0.22])
        return "%s 落在「%s」的%s侧（间距 %.02f–%.02fm，横向不跑偏），双爪张开" % (
            who, role(g["ref"]), d, lo, hi)
    if t == "between":
        a, b = g["refs"]
        return "%s 落在「%s」「%s」连线中点附近（<%.02fm），双爪张开" % (
            who, role(a), role(b), g.get("lat", 0.09))
    if t == "press":
        return "夹爪按到「%s」的按压点上，且物体没被搬走（位移 <%.02fm）" % (
            role(g.get("ref", "target")), g.get("max_move", 0.04))
    if t == "seq":
        return " **→** ".join("①②③"[i] + goal_zh(x, spec) for i, x in enumerate(g["stages"]))
    return str(t)


def main():
    y = yaml.safe_load(open(os.path.join(HERE, "scenes_v2.yaml"), encoding="utf-8"))
    by_name = {s["name"]: s for s in SCENES}
    out = ["# 组合泛化场景 · 目标清单", "",
           "对应总览图 `compo_v2_overview.png`，编号一致。", "",
           "**判据分两层，缺一不可**：",
           "1. **选对** — 目标位移必须严格大于所有干扰物（不解析指令的策略拿不到分）；",
           "2. **做对** — 下表「达成条件」列，即任务名承诺的那个终态。", "",
           "`专家` 是专家产出率（`script/collect_data.py` 口径），≥ 2/8 才进这张表；",
           "`未跑` 的是 v1 沿用的手写场景，判据本来就完整。", ""]
    n = 0
    for key, title, desc in AXIS:
        scs = (y["axes"].get(key) or {}).get("scenes") or []
        if not scs:
            continue
        out += ["", "## %s" % title, "", "> %s" % desc, "",
                "| # | 场景 | 生活场景 | 难度 | 指令 | 达成条件 | 依赖的 RoboTwin 任务 | 专家 |",
                "|---|---|---|---|---|---|---|---|"]
        for sc in scs:
            n += 1
            name = sc["name"]
            deps = ", ".join("%d %s" % (d, BASE[d - 1]) for d in (sc.get("deps") or []))
            t = by_name.get(name)
            if sc.get("source") == "handwritten" or t is None:
                instr = "见 `envs/%s.py`" % name
                cond = sc.get("note") or "手写判据"
            else:
                instr = t["instr"].replace("{A}", t.get("desc") or "target").replace("{a}", "指定手臂")
                cond = goal_zh(t["goal"], t["spec"])
            out.append("| %d | `%s` | %s | L%s | %s | %s | %s | %s |" % (
                n, name, sc.get("context", ""), sc.get("tier", "?"), instr, cond, deps, sc.get("smoke", "")))

    pend = (y.get("pending") or {}).get("scenes") or []
    if pend:
        out += ["", "---", "", "## pending（专家产出率 < 2/8，暂不进评测清单）", "",
                "代码都还在 `envs/` 下。改 `suite/table.py` 的物体/生成区/判据松紧后重跑",
                "`suite/smoke_par.sh`，达标了 `gen_yaml.py` 会自动把它挪回上面的表。", "",
                "| 场景 | 维度 | 难度 | 专家 | 卡在哪 |", "|---|---|---|---|---|"]
        for s in sorted(pend, key=lambda x: (x.get("dim", ""), x["name"])):
            err = s.get("smoke_err", "")
            err = "抓取规划挑不出可达位姿" if "target_pose cannot be None" in err else (err or "跑完但判据不过")
            out.append("| `%s` | %s | L%s | %s | %s |" % (
                s["name"], s.get("dim", ""), s.get("tier", "?"), s.get("smoke", ""), err))

    open(os.path.join(HERE, "SCENE_GOALS.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("写出 %d 个正式场景 + %d 个 pending -> SCENE_GOALS.md" % (n, len(pend)))


if __name__ == "__main__":
    main()
