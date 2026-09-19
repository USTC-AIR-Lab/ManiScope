# -*- coding: utf-8 -*-
import re, io, os
p = "gen_scenes.py"
s = open(p, encoding="utf-8").read()

block = '''
# --- 容器/参照物的静置位姿：全部取自 RoboTwin 原任务，别自己猜 --------------------
# 三个坑一起踩过：
#   a) 姿态用错 —— 008_tray / 106_skillet / 074_displaystand / 024_scanner 的正确姿态
#      各不相同，统一套 [0.5,0.5,0.5,0.5] 会让托盘和锅是斜的（总览图上肉眼可见）。
#   b) rot 默认开着 —— rand_pose 的随机旋转作用在**局部**轴上，容器的局部 z 不是世界竖直，
#      于是随机一转就倾斜。容器一律 rot=False。
#   c) zlim 默认 0.79，比桌面(0.741)高 5cm。非静态的会掉下来settle，
#      static=True 的**永远悬空**。容器一律贴桌面。
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
    """被操作物之外的模型：套原任务的静置位姿、关掉随机旋转、贴桌面。"""
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
print("容器位姿修正已加入编译器")
