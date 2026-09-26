# -*- coding: utf-8 -*-
"""Audit declared candidate scenes for reachability, instruction/goal consistency, role validity and duplicate signatures."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scene_set import SCENES
from gen_scenes import KEEP_EXISTING

XMAX = 0.22
issues = []

def add(sev, name, what):
    issues.append((sev, name, what))

by_sig = {}
for sc in SCENES:
    n = sc["name"]; g = sc["goal"]; spec = sc["spec"]
    roles = {p["role"]: p for p in spec}
    gt = g.get("type")

    # Check candidate destinations against the reachable x range; skip handwritten scenes whose true regions are defined in envs/.


    if gt == "rel" and g.get("ref") in roles and n not in KEEP_EXISTING:
        ref = roles[g["ref"]]
        r = ref.get("region")
        if r:
            lo, hi = g.get("gap", [0.05, 0.22])
            d = g.get("dir")
            if d == "left":
                far = r[0][0] - lo
                if far < -XMAX:
                    add("Error", n, "Destination x=%.2f exceeds reachable |x|<=%.2f (reference too far left)" % (far, XMAX))
            elif d == "right":
                far = r[0][1] + lo
                if far > XMAX:
                    add("Error", n, "Destination x=%.2f exceeds reachable |x|<=%.2f (reference too far right)" % (far, XMAX))

    # Check instruction direction against goal direction.
    if gt == "rel":
        d = g.get("dir")
        instr = (sc.get("instr") or "").lower()
        for w, k in (("left", "left"), ("right", "right"), ("behind", "behind"), ("front", "front")):
            if w in instr and d and d != k:
                add("Error", n, "Instruction says '%s' but goal direction is '%s'" % (w, d))

    # Check task-name direction/type against the predicate.
    nm = n.lower()
    if gt == "rel" and g.get("dir"):
        for w in ("left", "right", "behind", "front"):
            if ("_%s_" % w) in nm and g["dir"] != w:
                add("Error", n, "Task name contains '%s' but goal direction is '%s'" % (w, g["dir"]))
    if ("_in_" in nm or nm.endswith("_basket") or nm.endswith("_plasticbox")) \
       and "_of_" not in nm and "_left" not in nm and "_right" not in nm:
        if gt not in ("in", "seq"):
            add("Note", n, "Task name implies containment but goal type is '%s'" % gt)

    # Attribute and referring-expression tasks require distractors.
    if sc["dim"] in ("D3", "D4"):
        if not any(k for k in roles if "distract" in k or k.startswith("d")) and len(spec) < 3:
            add("Error", n, "%s family has no distractor; inspect selection requirements" % sc["dim"])

    # Every GOAL role must exist.
    refs = set()
    def collect(x):
        if not isinstance(x, dict): return
        if x.get("ref"): refs.add(x["ref"])
        for r_ in (x.get("refs") or []): refs.add(r_)
        for st in (x.get("stages") or []): collect(st)
    collect(g)
    for r_ in refs:
        if r_ not in roles:
            add("Error", n, "GOAL references missing role '%s'" % r_)

    # Include the requested attribute description in duplicate signatures so distinct color/size/ordinal tests remain distinct.


    sig = (gt, sc.get("desc"), tuple(sorted((p.get("model") or "box",
           tuple(p.get("ids") or [])) for p in spec)))
    by_sig.setdefault(sig, []).append(n)

    # Require the {A} instruction placeholder.
    if "{A}" not in (sc.get("instr") or ""):
        add("Error", n, "Instruction template lacks {A}")

for sig, names in by_sig.items():
    if len(names) > 1:
        add("Note", " / ".join(names), "Object/goal signature duplicates another scene")

print("Scanned %d scenes; found %d issues:\n" % (len(SCENES), len(issues)))
for sev in ("Error", "Note"):
    rows = [i for i in issues if i[0] == sev]
    if not rows: continue
    print("=== %s (%d) ===" % (sev, len(rows)))
    for _, n, w in sorted(rows):
        print("  [%s] %s" % (n, w))
    print()
if not issues:
    print("No issues found")
