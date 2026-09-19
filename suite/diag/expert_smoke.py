# 不连 policy 的专家冒烟：复刻 eval_policy 的 expert_check(setup_demo+play_once+check_success)+指令生成。
# 用来在拉 DM0.5 前，验证新组合场景能否过"专家关"(抓取规划/稳定性/指令模板)。
import sys, os, yaml, importlib, argparse
sys.path.append("./"); sys.path.append("./description/utils")
from envs import CONFIGS_PATH
from envs.utils.create_actor import UnStableError
import numpy as np
from generate_episode_instructions import generate_episode_descriptions

def class_decorator(t):
    m = importlib.import_module(f"envs.{t}"); return getattr(m, t)()

def build_args(task_name, task_config="demo_clean"):
    args = yaml.safe_load(open(f"./task_config/{task_config}.yml"))
    args["task_name"] = task_name; args["task_config"] = task_config; args["ckpt_setting"] = ""
    emb = yaml.safe_load(open(os.path.join(CONFIGS_PATH, "_embodiment_config.yml")))
    cam = yaml.safe_load(open(CONFIGS_PATH + "_camera_config.yml"))
    et = args["embodiment"]
    ef = lambda t: emb[t]["file_path"]
    hc = args["camera"]["head_camera_type"]; args["head_camera_h"] = cam[hc]["h"]; args["head_camera_w"] = cam[hc]["w"]
    if len(et) == 1:
        args["left_robot_file"] = ef(et[0]); args["right_robot_file"] = ef(et[0]); args["dual_arm_embodied"] = True
    else:
        args["left_robot_file"] = ef(et[0]); args["right_robot_file"] = ef(et[1]); args["embodiment_dis"] = et[2]; args["dual_arm_embodied"] = False
    args["left_embodiment_config"] = yaml.safe_load(open(os.path.join(args["left_robot_file"], "config.yml")))
    args["right_embodiment_config"] = yaml.safe_load(open(os.path.join(args["right_robot_file"], "config.yml")))
    args["render_freq"] = 0; args["eval_mode"] = True
    return args

def smoke(task_name, target, max_tries, seed0):
    env = class_decorator(task_name); args = build_args(task_name)
    succ = tries = 0; seed = seed0; instr = None; errs = []
    while succ < target and tries < max_tries:
        try:
            env.setup_demo(now_ep_num=tries, seed=seed, is_test=True, **args)
            ep = env.play_once(); env.close_env()
        except UnStableError:
            try: env.close_env()
            except Exception: pass
            seed += 1; tries += 1; continue
        except Exception as e:
            errs.append(repr(e))
            try: env.close_env()
            except Exception: pass
            seed += 1; tries += 1; continue
        ok = getattr(env, "plan_success", True) and env.check_success()
        if ok:
            succ += 1
            try:
                r = generate_episode_descriptions(task_name, [ep["info"]], 50)
                pool = (r[0].get("unseen") or r[0].get("seen")) if r else None
                instr = str(np.random.choice(pool)) if pool else "<NO_INSTR>"
            except Exception as e:
                instr = f"<INSTR_ERR {e!r}>"
        seed += 1; tries += 1
    return succ, tries, instr, errs[:2]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="+")
    ap.add_argument("--target", type=int, default=2)
    ap.add_argument("--max_tries", type=int, default=15)
    ap.add_argument("--seed0", type=int, default=0)
    a = ap.parse_args()
    for t in a.tasks:
        try:
            s, tr, ins, er = smoke(t, a.target, a.max_tries, a.seed0)
        except Exception as e:
            print(f"[FATAL] {t}: {e!r}", flush=True); continue
        tag = "OK  " if s > 0 else "ZERO"
        print(f"[{tag}] {t}: expert {s}/{tr}  instr={ins!r}  err={er}", flush=True)
