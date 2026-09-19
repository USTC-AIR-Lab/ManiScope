# -*- coding: utf-8 -*-
"""把用户发现的几类问题写成自动检查，扫全表。
每一条检查都对应一个真实踩过的坑，不是凭空想的规则。"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scene_set import SCENES
from gen_scenes import KEEP_EXISTING

XMAX = 0.22          # 可达范围
issues = []

def add(sev, name, what):
    issues.append((sev, name, what))

by_sig = {}
for sc in SCENES:
    n = sc["name"]; g = sc["goal"]; spec = sc["spec"]
    roles = {p["role"]: p for p in spec}
    gt = g.get("type")

    # 1) 落点是否超出可达范围（place_can_left_of_plasticbox 踩过：几何上无解）
    #    只对**编译器生成**的场景有效：手写场景(KEEP_EXISTING)的实际生成区写在
    #    envs/*.py 里，表里的 region 不作数，照算会误报（place_a2b_left_novel）。
    if gt == "rel" and g.get("ref") in roles and n not in KEEP_EXISTING:
        ref = roles[g["ref"]]
        r = ref.get("region")
        if r:
            lo, hi = g.get("gap", [0.05, 0.22])
            d = g.get("dir")
            if d == "left":
                far = r[0][0] - lo           # 落点最靠右也只能到这
                if far < -XMAX:
                    add("严重", n, "落点 x≈%.2f 超出可达 |x|<=%.2f（参照物太靠左，'放左边'无解）" % (far, XMAX))
            elif d == "right":
                far = r[0][1] + lo
                if far > XMAX:
                    add("严重", n, "落点 x≈%.2f 超出可达 |x|<=%.2f（参照物太靠右）" % (far, XMAX))

    # 2) 指令方向 vs 判据方向（place_a2b_right_novel 踩过：指令说左、判据判右）
    if gt == "rel":
        d = g.get("dir")
        instr = (sc.get("instr") or "").lower()
        for w, k in (("left", "left"), ("right", "right"), ("behind", "behind"), ("front", "front")):
            if w in instr and d and d != k:
                add("严重", n, "指令里写 '%s' 但判据方向是 '%s'" % (w, d))

    # 3) 场景名 vs 判据方向/类型（名实不符）
    nm = n.lower()
    if gt == "rel" and g.get("dir"):
        for w in ("left", "right", "behind", "front"):
            if ("_%s_" % w) in nm and g["dir"] != w:
                add("严重", n, "场景名含 '%s' 但判据方向是 '%s'" % (w, g["dir"]))
    if ("_in_" in nm or nm.endswith("_basket") or nm.endswith("_plasticbox")) \
       and "_of_" not in nm and "_left" not in nm and "_right" not in nm:
        if gt not in ("in", "seq"):
            add("提示", n, "名字暗示放进容器，判据却是 '%s'" % gt)

    # 4) 属性/指代维度必须有干扰物（否则不解析指令也能拿分）
    if sc["dim"] in ("D3", "D4"):
        if not any(k for k in roles if "distract" in k or k.startswith("d")) and len(spec) < 3:
            add("严重", n, "%s 维度但没有干扰物 —— 不解析指令也能拿分" % sc["dim"])

    # 5) GOAL 引用的 role 必须存在
    refs = set()
    def collect(x):
        if not isinstance(x, dict): return
        if x.get("ref"): refs.add(x["ref"])
        for r_ in (x.get("refs") or []): refs.add(r_)
        for st in (x.get("stages") or []): collect(st)
    collect(g)
    for r_ in refs:
        if r_ not in roles:
            add("严重", n, "GOAL 引用了不存在的 role '%s'" % r_)

    # 6) 重复场景（attr_bind_bottle vs attr_color_bottle 踩过）
    # 重复检测把 desc（测的是哪个属性）也纳入签名 —— 三色/尺寸/序位方块物体相同
    # 但测的属性不同，是有效的不同测试，不该报重复。
    sig = (gt, sc.get("desc"), tuple(sorted((p.get("model") or "box",
           tuple(p.get("ids") or [])) for p in spec)))
    by_sig.setdefault(sig, []).append(n)

    # 7) 指令模板必须有 {A}
    if "{A}" not in (sc.get("instr") or ""):
        add("严重", n, "指令模板缺 {A} 占位符 —— eval 阶段会 IndexError")

for sig, names in by_sig.items():
    if len(names) > 1:
        add("提示", " / ".join(names), "物体与判据类型完全相同，疑似重复场景")

print("扫描 %d 个场景，发现 %d 处：\n" % (len(SCENES), len(issues)))
for sev in ("严重", "提示"):
    rows = [i for i in issues if i[0] == sev]
    if not rows: continue
    print("=== %s (%d) ===" % (sev, len(rows)))
    for _, n, w in sorted(rows):
        print("  [%s] %s" % (n, w))
    print()
if not issues:
    print("未发现问题")
