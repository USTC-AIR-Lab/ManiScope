# -*- coding: utf-8 -*-
"""Generate fixed expert-solvable seed files for a reviewed scene version. Expert filtering depends on scene code and predicates, so matching search starting points does not ensure matching initial states. Save accepted seeds and initial-state summaries. Run under the configured simulator environment.

Usage: python suite/gen_seeds.py <scene> [count=100] [seed_start=300000] [max_tries=4000]
The formal seed lists are held by the organizers; development seed files must not be reported as formal results."""
import sys, os, json
sys.path.append("./"); sys.path.append("./description/utils")
import numpy as np
from envs.utils.create_actor import UnStableError
from suite.diag.expert_smoke import class_decorator, build_args

name = sys.argv[1]
want = int(sys.argv[2]) if len(sys.argv) > 2 else 100
seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 300000
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
    # Capture initial poses before execution and check workspace reachability.
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
            print("%s: %d/%d (%d seeds tried)" % (name, len(seeds), want, tries), flush=True)
    seed += 1

json.dump({"task": name, "count": len(seeds), "seed_start": seed0,
           "tried": tries, "yield": round(len(seeds) / max(1, tries), 4),
           "seeds": seeds, "init_poses": poses},
          open(out, "w"), indent=1)
print("%s -> %s  accepted %d/%d, tried %d seeds, yield %.1f%%"
      % (name, out, len(seeds), want, tries, 100.0 * len(seeds) / max(1, tries)))
