# 单场景插桩：跑几个种子，把 GOAL 各分量的实际数值打出来，定位是判据太紧还是专家没做到。
import sys, os, argparse
sys.path.append("./"); sys.path.append("./description/utils")
import numpy as np
from envs.utils.create_actor import UnStableError
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from suite.diag.expert_smoke import class_decorator, build_args

ap = argparse.ArgumentParser(); ap.add_argument("task"); ap.add_argument("--n", type=int, default=4)
a = ap.parse_args()
env = class_decorator(a.task); args = build_args(a.task)
for seed in range(a.n):
    try:
        env.setup_demo(now_ep_num=seed, seed=seed, is_test=True, **args)
        env.play_once()
    except UnStableError:
        print(f"seed{seed}: UNSTABLE");
        try: env.close_env()
        except Exception: pass
        continue
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(sys.exc_info()[2])
        where = " <- ".join("%s:%d %s" % (os.path.basename(f.filename), f.lineno, f.name) for f in tb[-3:])
        print(f"seed{seed}: EXC {e!r}  AT {where}")
        try: env.close_env()
        except Exception: pass
        continue
    env._track()
    g = env.GOAL
    line = [f"seed{seed}", f"plan={getattr(env,'plan_success',True)}", f"stage={env.stage}"]
    line.append(f"sel={env._selected_right()}")
    line.append(f"disp={ {k: round(v,3) for k,v in env._maxdisp.items()} }")
    def dump(gg, tag=""):
        t = gg.get("type"); who = gg.get("who", env.TARGET)
        try:
            if t in ("on", "stack"):
                p, q = env._p(who), env._p(gg["ref"])
                line.append(f"{tag}{t}[dx={p[0]-q[0]:+.3f} dy={p[1]-q[1]:+.3f} dz={p[2]-q[2]:+.3f}]")
            elif t == "in":
                p, q = env._p(who), env._p(gg["ref"])
                line.append(f"{tag}in[xy={np.linalg.norm(p[:2]-q[:2]):.3f} dz={p[2]-q[2]:+.3f}]")
            elif t == "rel":
                p, q = env._p(who), env._p(gg["ref"])
                line.append(f"{tag}rel[dx={p[0]-q[0]:+.3f} dy={p[1]-q[1]:+.3f} dz={p[2]-q[2]:+.3f}]")
            elif t == "press":
                line.append(f"{tag}press[ok={env._goal_ok(gg)}]")
            elif t == "qpos":
                aa = env._actors[gg["ref"]]; lim = aa.get_qlimits()[0]
                cur = float(aa.get_qpos()[gg.get('joint',0)])
                line.append(f"{tag}qpos[frac={(cur-lim[0])/max(1e-6,lim[1]-lim[0]):.2f}]")
            else:
                line.append(f"{tag}{t}[ok={env._goal_ok(gg)}]")
        except Exception as e:
            line.append(f"{tag}{t}[ERR {e!r}]")
        line.append(f"{tag}ok={env._goal_ok(gg)}")
    if g.get("type") == "seq":
        for i, s in enumerate(g["stages"]): dump(s, f"s{i+1}:")
    else:
        dump(g)
    try: line.append(f"grip={env.is_left_gripper_open()},{env.is_right_gripper_open()}")
    except Exception: pass
    line.append(f"SUCCESS={env.check_success()}")
    print("  ".join(str(x) for x in line), flush=True)
    env.close_env()
