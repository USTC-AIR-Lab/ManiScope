# -*- coding: utf-8 -*-
"""为正式评测冻结每个场景的 100 个专家可解种子。

为什么必须冻结成文件：现在 eval_policy 是从 st_seed 起逐个让专家试跑、能解的才收，
这个搜索**依赖当时的场景代码和判据**。只要场景或判据动过，同一起点搜出来的种子集就变了，
DM0.5 和 WLA 面对的初始状态就不是同一批，跨算法比较失去意义。

除种子外还存每个种子的**初始位姿摘要**：事后可以验证两个算法确实面对同一初始状态，
而不只是「用了同一个种子数字」——如果哪次改动让同一种子生成出不同布局，一比就发现。

用法: gen_seeds.py <场景名> [目标条数=100] [起始种子=100000] [最多尝试=4000]
"""
import sys, os, json
sys.path.append("./"); sys.path.append("./description/utils")
import numpy as np
from envs.utils.create_actor import UnStableError
from suite.diag.expert_smoke import class_decorator, build_args

name = sys.argv[1]
want = int(sys.argv[2]) if len(sys.argv) > 2 else 100
seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 100000
maxtry = int(sys.argv[4]) if len(sys.argv) > 4 else 4000

out = "suite/seeds/%s.json" % name
os.makedirs("suite/seeds", exist_ok=True)

env = class_decorator(name)
args = build_args(name)
seeds, poses = [], []
seed, tries = seed0, 0
while len(seeds) < want and tries < maxtry:
    tries += 1
    try:
        env.setup_demo(now_ep_num=tries, seed=seed, is_test=True, **args)
    except UnStableError:
        try: env.close_env()
        except Exception: pass
        seed += 1; continue
    except Exception:
        try: env.close_env()
        except Exception: pass
        seed += 1; continue
    # 生成后、执行前先抓一份初始位姿
    snap = {}
    try:
        for role, act in getattr(env, "_actors", {}).items():
            p = act.get_pose()
            snap[role] = [round(float(x), 5) for x in list(p.p) + list(p.q)]
    except Exception:
        snap = {}
    ok = False
    try:
        env.play_once()
        ok = bool(env.check_success())
    except Exception:
        ok = False
    try: env.close_env()
    except Exception: pass
    if ok:
        seeds.append(seed)
        poses.append(snap)
        if len(seeds) % 10 == 0:
            print("%s: %d/%d (试了 %d 个种子)" % (name, len(seeds), want, tries), flush=True)
    seed += 1

json.dump({"task": name, "count": len(seeds), "seed_start": seed0,
           "tried": tries, "yield": round(len(seeds) / max(1, tries), 4),
           "seeds": seeds, "init_poses": poses},
          open(out, "w"), indent=1)
print("%s -> %s  收到 %d/%d，试了 %d 个种子，产出率 %.1f%%"
      % (name, out, len(seeds), want, tries, 100.0 * len(seeds) / max(1, tries)))
