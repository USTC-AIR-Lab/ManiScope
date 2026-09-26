# -*- coding: utf-8 -*-
"""Generate a scene-goal checklist from the frozen manifest. Generated GOAL descriptions supplement the manifest; handwritten scenes refer to their own implementations."""
import os, sys, yaml
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scene_set import SCENES
from scenes import BASE

AXIS = [("skill_x_object", "D1 Skill x object", "Reuse skills with new objects"),
        ("skill_x_spatial", "D2 Skill x spatial", "Apply spatial relations to new object pairs"),
        ("attribute_binding", "D3 Attribute binding", "Select the target by its requested attributes"),
        ("instruction_structure", "D4 Referring expressions", "Resolve the referring expression to identify the target"),
        ("skill_x_skill_temporal", "D5 Skill sequences", "Compose two source skills in an ordered sequence"),
        ("mixture", "D6 Mixture", "Combine multiple task requirements")]


def goal_zh(g, spec):
    def role(r):
        for p in spec:
            if p["role"] == r:
                return p.get("desc") or (p.get("model", "").split("_", 1)[-1]
                                         if p["kind"] == "model" else "block")
        return r
    t = g.get("type")
    who = role(g.get("who", "target"))
    if t == "lift":
        return "Lift target clear of the table by >%.2fm" % g.get("dz", 0.06)
    if t == "moved":
        return "Target displacement >%.2fm" % g.get("eps", 0.05)
    if t in ("on", "stack"):
        e = g.get("eps", [0.035, 0.035, 0.03])
        v = "Stack" if t == "stack" else "Place"
        return "%s %s above %s (xy tolerance +/-%.03gm), both grippers open" % (who, v, role(g["ref"]), e[0])
    if t == "in":
        return "%s inside %s (xy distance <%.02fm, above container opening), both grippers open" % (
            who, role(g["ref"]), g.get("r", 0.12))
    if t == "rel":
        d = {"left": "left", "right": "right", "front": "front", "behind": "behind"}[g.get("dir", "left")]
        lo, hi = g.get("gap", [0.05, 0.22])
        return "%s on the %s reference %s side (gap %.02f-%.02fm, lateral tolerance), both grippers open" % (
            who, role(g["ref"]), d, lo, hi)
    if t == "between":
        a, b = g["refs"]
        return "%s near midpoint of %s and %s (<%.02fm), both grippers open" % (
            who, role(a), role(b), g.get("lat", 0.09))
    if t == "press":
        return "Gripper at %s press point; object displacement <%.02fm" % (
            role(g.get("ref", "target")), g.get("max_move", 0.04))
    if t == "seq":
        return " **→** ".join("①②③"[i] + goal_zh(x, spec) for i, x in enumerate(g["stages"]))
    return str(t)


def main():
    y = yaml.safe_load(open(os.path.join(HERE, "scenes_v2.yaml"), encoding="utf-8"))
    by_name = {s["name"]: s for s in SCENES}
    out = ["# Scene goal checklist", "",
           "Task identifiers correspond to the scene overview.", "",
           "**Inspect both selection and physical-goal predicates:**",
           "1. Target-selection guards depend on the task implementation.",
           "2. The physical goal specifies the required end state or ordered sequence.", "",
           "Expert yield is a feasibility observation, not policy performance;",
           "Some handwritten scenes retain earlier feasibility records.", ""]
    n = 0
    for key, title, desc in AXIS:
        scs = (y["axes"].get(key) or {}).get("scenes") or []
        if not scs:
            continue
        out += ["", "## %s" % title, "", "> %s" % desc, "",
                "| # | Scene | Context | Level | Instruction | Goal | RoboTwin links | Expert |",
                "|---|---|---|---|---|---|---|---|"]
        for sc in scs:
            n += 1
            name = sc["name"]
            deps = ", ".join("%d %s" % (d, BASE[d - 1]) for d in (sc.get("deps") or []))
            t = by_name.get(name)
            if sc.get("source") == "handwritten" or t is None:
                instr = "See `envs/%s.py`" % name
                cond = sc.get("note") or "Handwritten predicate"
            else:
                instr = t["instr"].replace("{A}", t.get("desc") or "target").replace("{a}", "specified arm")
                cond = goal_zh(t["goal"], t["spec"])
            out.append("| %d | `%s` | %s | L%s | %s | %s | %s | %s |" % (
                n, name, sc.get("context", ""), sc.get("tier", "?"), instr, cond, deps, sc.get("smoke", "")))

    pend = (y.get("pending") or {}).get("scenes") or []
    if pend:
        out += ["", "---", "", "## Development candidates outside formal membership", "",
                "Review candidate objects, spawn regions and predicates in suite/table.py before rerunning smoke checks.",
                "The frozen manifest is not automatically changed by candidate generation.", "",
                "| Scene | Family | Level | Expert | Diagnostic |", "|---|---|---|---|---|"]
        for s in sorted(pend, key=lambda x: (x.get("dim", ""), x["name"])):
            err = s.get("smoke_err", "")
            err = "No reachable grasp plan" if "target_pose cannot be None" in err else (err or "Trajectory completed without meeting the predicate")
            out.append("| `%s` | %s | L%s | %s | %s |" % (
                s["name"], s.get("dim", ""), s.get("tier", "?"), s.get("smoke", ""), err))

    open(os.path.join(HERE, "SCENE_GOALS.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("Wrote %d formal scenes and %d candidates -> SCENE_GOALS.md" % (n, len(pend)))


if __name__ == "__main__":
    main()
