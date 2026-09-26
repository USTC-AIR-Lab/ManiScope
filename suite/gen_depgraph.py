# -*- coding: utf-8 -*-
"""Export declared RoboTwin task links for visualization. Prefer table.py dependencies, fall back to the earlier scene table, then apply explicit rename mappings."""
import sys, os, re, glob, json, yaml
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from scenes import BASE, S as V1
from scene_set import SCENES as V2

# Preserve handwritten implementations and map renamed scenes to their earlier identifiers; do not overwrite them with generated candidates.
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
    print("%d scenes -> depgraph.json; linked RoboTwin tasks %d/50" % (len(g["scenes"]), len(cov)))
    miss = [i for i in range(1, 51) if i not in cov]
    print("No scene links to:", ", ".join("%d %s" % (i, BASE[i-1]) for i in miss))
    bad = [s["name"] for s in g["scenes"] if not s["deps"]]
    if bad: print("Missing deps:", bad)
