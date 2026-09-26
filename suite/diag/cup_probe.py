
import sys, os, yaml, importlib, argparse
sys.path.append("./"); sys.path.append("./description/utils")
import numpy as np
from envs import CONFIGS_PATH
from envs.utils.create_actor import UnStableError

def build_args(task_name, task_config="demo_clean"):
    args = yaml.safe_load(open("./task_config/%s.yml" % task_config))
    args["task_name"] = task_name; args["task_config"] = task_config; args["ckpt_setting"] = ""
    emb = yaml.safe_load(open(os.path.join(CONFIGS_PATH, "_embodiment_config.yml")))
    cam = yaml.safe_load(open(CONFIGS_PATH + "_camera_config.yml"))
    et = args["embodiment"]; ef = lambda t: emb[t]["file_path"]
    hc = args["camera"]["head_camera_type"]; args["head_camera_h"]=cam[hc]["h"]; args["head_camera_w"]=cam[hc]["w"]
    args["left_robot_file"]=ef(et[0]); args["right_robot_file"]=ef(et[0]); args["dual_arm_embodied"]=True
    args["left_embodiment_config"]=yaml.safe_load(open(os.path.join(args["left_robot_file"],"config.yml")))
    args["right_embodiment_config"]=yaml.safe_load(open(os.path.join(args["right_robot_file"],"config.yml")))
    args["render_freq"]=0; args["eval_mode"]=True
    return args

ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=8); a = ap.parse_args()
m = importlib.import_module("envs.move_cup_pad"); env = getattr(m, "move_cup_pad")()
args = build_args("move_cup_pad")
print("pad half_size = [0.055, 0.03, 0.0005] -> 11cm x 6cm")
for seed in range(a.n):
    try:
        env.setup_demo(now_ep_num=seed, seed=seed, is_test=True, **args)
        env.play_once()
    except UnStableError:
        print("seed%d UNSTABLE" % seed)
        try: env.close_env()
        except Exception: pass
        continue
    except Exception as e:
        print("seed%d EXC %r" % (seed, e))
        try: env.close_env()
        except Exception: pass
        continue
    cup = np.asarray(env.stapler.get_pose().p, float)
    pad = np.asarray(env.pad.get_pose().p, float)
    d = cup - pad
    grip = bool(env.robot.is_left_gripper_open() and env.robot.is_right_gripper_open())
    plan = getattr(env, "plan_success", True)
    old = bool(np.all(abs(d) < np.array([0.02, 0.02, 0.01])) and grip)
    print("seed%d plan=%s grip=%s dx=%+.3f dy=%+.3f dz=%+.3f r_xy=%.3f old_predicate=%s"
          % (seed, plan, grip, d[0], d[1], d[2], float(np.hypot(d[0], d[1])), old))
    env.close_env()
