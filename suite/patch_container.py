# -*- coding: utf-8 -*-
import re, io, os
p = "gen_scenes.py"
s = open(p, encoding="utf-8").read()

block = '''
# Use source-task resting orientations for references. Disable local random rotation for containers; static actors must be placed at table height.







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
    """Apply source-task resting poses to non-manipulated model references, disable random rotation and place static references at support height."""
    manip = manipulated_roles(sc["goal"])
    for p in sc["spec"]:
        if p.get("kind") != "model" or p["role"] in manip or "rel" in p:
            continue
        q = CONTAINER_POSE.get(p["model"])
        if q is None:
            continue
        p["qpos"] = list(q)
        p["rot"] = False
        p.setdefault("zlim", [TABLE_Z])

'''
s = s.replace("for sc in SCENES:\n    normalize(sc)",
              block + "for sc in SCENES:\n    normalize(sc)\n    fix_containers(sc)")
assert "def fix_containers" in s
open(p, "w", encoding="utf-8").write(s)
import ast; ast.parse(s)
print("Container pose correction added to generator")
