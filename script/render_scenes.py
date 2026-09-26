# Render initial head-camera frames without policy trajectories; target mode skips failed or unstable scene initializations.

import sys, os, yaml, importlib, argparse, traceback
sys.path.append("./")
import numpy as np
from envs import *  # Provide CONFIGS_PATH.
import sapien.core as sapien

def class_decorator(task_name):
    m = importlib.import_module(f"envs.{task_name}")
    return getattr(m, task_name)()

def get_embodiment_config(robot_file):
    with open(os.path.join(robot_file, "config.yml"), "r", encoding="utf-8") as f:
        return yaml.load(f.read(), Loader=yaml.FullLoader)

def build_args(task_name, task_config, cam_type):
    with open(f"./task_config/{task_config}.yml", "r", encoding="utf-8") as f:
        args = yaml.load(f.read(), Loader=yaml.FullLoader)
    args["task_name"] = task_name; args["task_config"] = task_config
    with open(os.path.join(CONFIGS_PATH, "_embodiment_config.yml"), "r", encoding="utf-8") as f:
        emb = yaml.load(f.read(), Loader=yaml.FullLoader)
    et = args.get("embodiment")
    def ef(t): return emb[t]["file_path"]
    if len(et) == 1:
        args["left_robot_file"] = ef(et[0]); args["right_robot_file"] = ef(et[0]); args["dual_arm_embodied"] = True
        args["embodiment_name"] = str(et[0])
    elif len(et) == 3:
        args["left_robot_file"] = ef(et[0]); args["right_robot_file"] = ef(et[1]); args["embodiment_dis"] = et[2]; args["dual_arm_embodied"] = False
        args["embodiment_name"] = str(et[0]) + "+" + str(et[1])
    else:
        raise ValueError("embodiment param must be 1 or 3")
    args["left_embodiment_config"] = get_embodiment_config(args["left_robot_file"])
    args["right_embodiment_config"] = get_embodiment_config(args["right_robot_file"])
    if cam_type: args["camera"]["head_camera_type"] = cam_type
    args["render_freq"] = 0; args["need_plan"] = False; args["save_data"] = False
    args["collect_data"] = False; args["eval_mode"] = False; args["eval_video_log"] = False
    return args

def render_one(task, base_args, ep, seed, out_png, camera_name):
    task.setup_demo(now_ep_num=ep, seed=seed, **base_args)
    task.save_camera_rgb(out_png, camera_name=camera_name)
    task.close_env()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task_name")
    ap.add_argument("--task_config", default="demo_clean")
    ap.add_argument("--episodes", type=int, default=50)
    ap.add_argument("--seed_base", type=int, default=0)
    ap.add_argument("--target", type=int, default=50, help=">0: skip unstable/failed seeds until target frames are collected")
    ap.add_argument("--max_tries", type=int, default=400)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cam_type", default="Large_D435")
    ap.add_argument("--camera_name", default="head_camera")
    ap.add_argument("--traceback", action="store_true", help="Include full errors in failed smoke attempts")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    task = class_decorator(a.task_name)
    base_args = build_args(a.task_name, a.task_config, a.cam_type)

    if a.target and a.target > 0:
        count, seed = 0, a.seed_base
        while count < a.target and seed < a.seed_base + a.max_tries:
            out_png = os.path.join(a.out, f"ep{count:02d}_seed{seed}.png")
            try:
                render_one(task, base_args, count, seed, out_png, a.camera_name)
                count += 1
                print(f"[{a.task_name}] ep{count-1:02d} seed{seed} OK", flush=True)
            except Exception as e:
                if a.traceback: traceback.print_exc()
                print(f"[{a.task_name}] seed{seed} SKIP: {e}", flush=True)
                try: task.close_env()
                except Exception: pass
            seed += 1
        print(f"[{a.task_name}] completed {count}/{a.target} (last seed={seed-1}) -> {a.out}", flush=True)
        if count < a.target:
            raise SystemExit(1)
    else:
        ok = 0
        for ep in range(a.episodes):
            seed = a.seed_base + ep
            out_png = os.path.join(a.out, f"ep{ep:02d}_seed{seed}.png")
            try:
                render_one(task, base_args, ep, seed, out_png, a.camera_name); ok += 1
                print(f"[{a.task_name}] ep{ep:02d} seed{seed} OK", flush=True)
            except Exception as e:
                if a.traceback: traceback.print_exc()
                print(f"[{a.task_name}] ep{ep:02d} seed{seed} FAIL: {e}", flush=True)
                try: task.close_env()
                except Exception: pass
        print(f"[{a.task_name}] completed {ok}/{a.episodes} -> {a.out}", flush=True)
        if ok < a.episodes:
            raise SystemExit(1)

if __name__ == "__main__":
    main()
