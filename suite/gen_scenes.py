# -*- coding: utf-8 -*-
"""Compile declarative scene candidates into environment and instruction files under the configured output directory. Review candidates before updating the frozen release."""
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


KEEP_EXISTING = {"move_cup_pad", "place_a2b_left_novel", "place_a2b_right_novel"}


# Validate contact-point metadata for manipulated objects; static references are exempt. graspable.json indexes asset metadata.


GRASPABLE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "graspable.json")))
# Metadata alone does not establish grasp feasibility; require the tested object whitelist as well.


TESTED = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tested.json")))
OKGRASP = set(TESTED["ok"]) | set(TESTED["side_only"]) | set(TESTED["marginal"])

def manipulated_roles(goal):
    """Return grasped GOAL roles, including sequence stages; press targets are not grasped."""
    out = set()
    if goal.get("type") == "seq":
        for st in goal["stages"]:
            out |= manipulated_roles(st)
        return out
    if goal.get("type") in ("press", "qpos"):
        return out
    if goal.get("type") == "beat":
        # For hammer tasks, the hammer is manipulated and the stationary blocks are targets, not grasp candidates.

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
            bad.append("%s: GOAL references missing role %r" % (sc["name"], r)); continue
        if p["kind"] != "model":
            if p["kind"] == "box":
                bad.append("%s: role %r is a bare create_box block with limited place/grasp feasibility"
                           " (inspect the recorded feasibility probes)" % (sc["name"], r))
            continue
        # Allow the source hammer configuration; feasibility depends on the specific pose and must be checked by a smoke run.

        # [0,0,0.995,0.105] + pre_grasp_dis=0.12 + grasp_dis=0.01。


        if p["model"] == "020_hammer" and sc["goal"].get("type") == "beat":
            continue
        if p["model"] not in OKGRASP:
            bad.append("%s: %s is not in the tested graspable set; it may be a distractor/reference"
                       % (sc["name"], p["model"]))
            continue
        ids = GRASPABLE.get(p["model"])
        if ids is None:
            bad.append("%s: %s has no contact_points; grasp_actor cannot use it" % (sc["name"], p["model"]))
        else:
            miss = [i for i in p["ids"] if i not in ids]
            if miss:
                bad.append("%s: %s variant %s has no contact_points" % (sc["name"], p["model"], miss))
    return bad


# Normalize candidate layouts to reachable regions: |x| <= 0.22, y in [-0.15, 0.08]. Placement uses compatible source/reference regions; selection tasks randomize side.


XMAX, YMIN, YMAX = 0.22, -0.15, 0.08
CENTER = [[-0.05, 0.05], [-0.15, -0.06]]

def clamp(region):
    (x0, x1), (y0, y1) = region
    x0, x1 = max(-XMAX, min(XMAX, x0)), max(-XMAX, min(XMAX, x1))
    if x1 - x0 < 0.04:                       # Do not collapse the spawn interval during clipping.
        c = (x0 + x1) / 2
        c = max(-XMAX + 0.03, min(XMAX - 0.03, c))
        x0, x1 = c - 0.03, c + 0.03
    y0, y1 = max(YMIN, min(YMAX, y0)), max(YMIN, min(YMAX, y1))
    if y1 - y0 < 0.04:
        c = max(YMIN + 0.03, min(YMAX - 0.03, (y0 + y1) / 2))
        y0, y1 = c - 0.03, c + 0.03
    return [[round(x0, 3), round(x1, 3)], [round(y0, 3), round(y1, 3)]]

# Use the tested cup/mug orientation; container quaternions are not interchangeable with cup poses.

CUP_QPOS = {"021_cup": [0.707, 0.707, 0, 0], "039_mug": [0.707, 0.707, 0, 0]}

def normalize(sc):
    # Do not apply generic placement-slot rules to beat or dual_carry_to: hammer blocks need separate slots and the pot pad must stay nearby.


    placement = sc["goal"]["type"] not in (
        "lift", "moved", "press", "qpos", "beat", "dual_carry_to")
    manip = manipulated_roles(sc["goal"])
    for p in sc["spec"]:
        if p.get("model") in CUP_QPOS and not p.get("static"):
            p["qpos"] = CUP_QPOS[p["model"]]
        if "region" not in p:                # Relative placement does not require an independent spawn region.
            continue
        if p.get("model") in TESTED["side_only"] and p["role"] in manip:
            # Keep lying bottles in side regions compatible with their grasp orientations.
            p["region"] = clamp(p["region"])
            continue
        if placement and p["role"] in manip and not p.get("fixed") and not p.get("rel"):
            p["region"] = list(CENTER)       # Move the manipulated object toward the center and shift conflicting references sideways.
        else:
            p["region"] = clamp(p["region"])

    # Keep the anchor of a relatively placed target central so the target stays reachable.


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
            # Separate references in x while retaining the reachable y band; sampling-time rejection handles overlap.


            # An explicit side places the reference opposite the requested displacement, leaving destination clearance.


            side = p.get("side")
            if side is None:
                side = -1 if len([u for u in used if u < 0]) <= len([u for u in used if u > 0]) else 1
            used.append(side)
            # side_x controls reference distance from the center line.

            mag = float(p.get("side_x", 0.165))
            p["region"] = [[mag * side - 0.045, mag * side + 0.045], clamp(r)[1]]


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
        # Set table-height z only for static containers. Dynamic containers fall and settle; forcing them into the table causes collisions.


        if p.get("static"):
            p.setdefault("zlim", [TABLE_Z])


# Use asset-specific canonical manipulated-object poses from source tasks to avoid unintended lying or rolling configurations.


# Bottle orientation is handled separately by side-dependent qpos_lr.

CANON_POSE = {
    "112_tea-box":   [0.5, 0.5, 0.5, 0.5],
    "100_seal":      [0.5, 0.5, 0.5, 0.5],
    "071_can":       [0.5, 0.5, 0.5, 0.5],
    "021_cup":       [0.5, 0.5, 0.5, 0.5],
    "105_sauce-can": [0.5, 0.5, 0.5, 0.5],
    "080_pillbottle":[0.5, 0.5, 0.5, 0.5],
    # Retain the tested trophy pose; it has no source-task canonical pose in this suite.

    "050_bell":      [0.5, 0.5, 0.5, 0.5],
}

def canon_pose(sc):
    """Use source-task canonical poses for manipulated objects with random rotation disabled. Explicit keep_pose=True preserves intentional exceptions such as lying bottles."""
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


# Mixture candidates add an unrelated distractor to an existing scene, away from the target and goal. The added object participates in selection-exclusivity checks.


# Do not derive mixtures from KEEP_EXISTING scenes whose handwritten layout differs from the table specification.


MIX_SRC = [
    ("move_cup_pad",           "071_can",        [0, 1, 2],       "An additional can on the desk"),
    ("place_teabox_skillet",   "073_rubikscube", [0, 1, 2],       "An additional cube near the skillet"),
    ("roller_to_plate",        "112_tea-box",    [0, 1, 2, 3],    "An additional tea box on the preparation surface"),
    ("ref_block_on_plate",     "057_toycar",     [0, 1, 2, 3],    "An additional toy car on the table"),
    ("card_right_of_scanner",  "071_can",        [0, 1, 2],       "An additional can near the checkout scanner"),
    ("put_toycar_left_basket", "112_tea-box",    [0, 1, 2, 3],    "An additional tea box beside the task objects"),
]

def build_mix():
    import copy as _copy
    by = {sc["name"]: sc for sc in SCENES}
    out = []
    for src, dmodel, dids, note in MIX_SRC:
        base = by.get(src)
        if base is None:      # Skip missing source specifications; place the distractor opposite the target and destination.
            continue
        sc = _copy.deepcopy(base)
        sc["name"] = src + "_mix"
        sc["dim"] = "D7"
        sc["tier"] = min(4, base["tier"] + 1)
        sc["note"] = "Mixture: source scene %s plus an unrelated distractor (%s). %s." \
                     "Inherit source predicates, instructions and dependencies; add the distractor. " \
                     "Compare the observed effects under the documented scene configurations." % (src, dmodel, note)

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


# For relation goals, leave clearance beyond the reference and start the target away along the perpendicular axis so the goal is not initially satisfied.


NEAR_Y = [-0.19, -0.14]      # Near-side target y band.
FAR_Y  = [-0.05, 0.03]       # Reference y band.

def rel_layout(sc):
    """Separate relation-task targets and references in y while retaining normalized x coordinates. This avoids initially satisfied goals without changing the grasp-to-placement lateral relationship; initial guards handle residual cases."""
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
        # Front/back goals need their own y bands: retain enough reachable space behind the reference for the destination.


        # Retain the tested reference band and narrow the target band rather than shifting the destination beyond reach.


        tgt["region"] = [tgt["region"][0], [-0.16, -0.13]]
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
# Instruction templates must include {A} so placeholder filtering can bind episode metadata; literal object names can produce an empty instruction pool.


for _sc in SCENES:
    if "{A}" not in _sc.get("instr", ""):
        problems.append("%s: instruction template is missing {A}; evaluation requires this placeholder"
                        % _sc["name"])

for sc in SCENES:
    if sc["name"] in KEEP_EXISTING:
        continue
    if sc["goal"]["type"] == "lift" or sc["goal"]["type"] == "moved":
        # For lift-only tasks, bare blocks are valid; check contact-point metadata.
        problems += [b for b in check(sc) if "bare block" not in b]
    else:
        problems += check(sc)
if problems:
    print("=== Candidate validation failed ===")
    for p in problems:
        print("  " + p)
    raise SystemExit(1)
print("Validation passed: manipulated objects in %d scenes have supported grasps" % len(SCENES))

for sc in SCENES:
    if sc["name"] in KEEP_EXISTING:
        continue
    deps = ", ".join("%d %s" % (d, BASE[d - 1]) for d in sc["deps"])
    head = ['"""%s · %s · L%d · %s' % (sc["id"], DIMNAME[sc["dim"]], sc["tier"], sc["ctx"])]
    if sc["note"]:
        head.append("")
        head.append(sc["note"])
    head += ["",
             "RoboTwin source-task links: " + deps,
             "Generated candidate from suite/table.py for evaluation, not training; review before replacing the frozen release.",
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
           "_note": "%s %s L%d;predicate=%s;generated from suite/table.py" % (
               sc["id"], DIMNAME[sc["dim"]], sc["tier"], sc["goal"]["type"])}
    ins["seen"] = list(dict.fromkeys(ins["seen"]))
    json.dump(ins, open(os.path.join(OUT_INS, sc["name"] + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

print("generated %d envs + %d instruction files" % (len(os.listdir(OUT_ENV)), len(os.listdir(OUT_INS))))
