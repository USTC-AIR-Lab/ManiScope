# -*- coding: utf-8 -*-
"""导出 50 个组合场景对 RoboTwin 50 基础任务的潜在依赖，供依赖图可视化用。

deps 的来源有三处，按优先级合并：
  1) suite/table.py 里 S(...) 的 deps 字段（v2 重构后的场景，权威）
  2) suite/scenes.py 的 v1 表（v1 沿用、没进 table.py 的场景）
  3) RENAMED —— v1 改名后 1)2) 都查不到的，手工接上原场景的血缘
"""
import sys, os, re, glob, json, yaml
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from scenes import BASE, S as V1
from scene_set import SCENES as V2

# 改名场景的血缘：新名 -> v1 原名
RENAMED = {"attr_bind_bottle": "attr_color_bottle",
           "attr_bind_soap_box": "attr_color_x_category_soap",
           "move_cube_on_plate_to_pad": "ref_cube_on_plate_to_pad"}

def build():
    d = yaml.safe_load(open(os.path.join(HERE, "scenes_v2.yaml"), encoding="utf-8"))
    AX = {"skill_x_object": "D1", "skill_x_spatial": "D2", "attribute_binding": "D3",
          "instruction_structure": "D4", "skill_x_skill_temporal": "D5", "mixture": "D7"}
    live = [(AX[k], s) for k, v in d["axes"].items() for s in (v["scenes"] or [])]
    v2 = {s["name"]: s for s in V2}
    v1 = {r[3]: r for r in V1}
    res = {}
    for f in glob.glob(os.path.join(ROOT, "eval_result", "dm05_v5", "*/*/*/*/*/_result.txt")):
        t = f.split(os.sep)[-6]
        vals = re.findall(r"^[0-9]*\.?[0-9]+$", open(f).read(), re.M)
        if vals: res[t] = float(vals[-1])

    out = []
    for dim, s in live:
        n = s["name"]
        if n in v2:
            deps, src = v2[n]["deps"], "table"
        elif n in v1:
            deps, src = v1[n][5], "v1"
        elif n in RENAMED:
            deps, src = v1[RENAMED[n]][5], "renamed"
        else:
            deps, src = [], "missing"
        out.append(dict(name=n, dim=dim, tier=s.get("tier"), ctx=s.get("context", ""),
                        instr=(v2[n]["instr"] if n in v2 else ""), deps=deps, dep_src=src,
                        smoke=s.get("smoke", ""), score=res.get(n)))
    return {"base": BASE, "scenes": out}

if __name__ == "__main__":
    g = build()
    p = os.path.join(HERE, "depgraph.json")
    json.dump(g, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cov = sorted({x for s in g["scenes"] for x in s["deps"]})
    print("%d 个场景 -> depgraph.json；覆盖 RoboTwin 基础任务 %d/50" % (len(g["scenes"]), len(cov)))
    miss = [i for i in range(1, 51) if i not in cov]
    print("未被任何场景依赖：", ", ".join("%d %s" % (i, BASE[i-1]) for i in miss))
    bad = [s["name"] for s in g["scenes"] if not s["deps"]]
    if bad: print("!! 缺 deps：", bad)
