import sys
import os
import time
import subprocess

sys.path.append("./")
sys.path.append(f"./policy")
sys.path.append("./description/utils")
from envs import CONFIGS_PATH
from envs.utils.create_actor import UnStableError

import numpy as np
from pathlib import Path
from collections import deque
import traceback

import yaml
from datetime import datetime
import importlib
import argparse
import pdb

from generate_episode_instructions import *

current_file_path = os.path.abspath(__file__)
parent_directory = os.path.dirname(current_file_path)


def class_decorator(task_name):
    envs_module = importlib.import_module(f"envs.{task_name}")
    try:
        env_class = getattr(envs_module, task_name)
        env_instance = env_class()
    except:
        raise SystemExit("No Task")
    return env_instance


def eval_function_decorator(policy_name, model_name):
    try:
        policy_model = importlib.import_module(policy_name)
        return getattr(policy_model, model_name)
    except ImportError as e:
        raise e

def get_camera_config(camera_type):
    camera_config_path = os.path.join(parent_directory, "../task_config/_camera_config.yml")

    assert os.path.isfile(camera_config_path), "task config file is missing"

    with open(camera_config_path, "r", encoding="utf-8") as f:
        args = yaml.load(f.read(), Loader=yaml.FullLoader)

    assert camera_type in args, f"camera {camera_type} is not defined"
    return args[camera_type]


def get_embodiment_config(robot_file):
    robot_config_file = os.path.join(robot_file, "config.yml")
    with open(robot_config_file, "r", encoding="utf-8") as f:
        embodiment_args = yaml.load(f.read(), Loader=yaml.FullLoader)
    return embodiment_args


def get_eval_video_size(args):
    head_camera_cfg = get_camera_config(args["camera"]["head_camera_type"])
    video_w = int(head_camera_cfg["w"])
    video_h = int(head_camera_cfg["h"])

    return f"{video_w}x{video_h}"


def get_eval_wrist_video_size(args):
    cfg = get_camera_config(args["camera"]["wrist_camera_type"])
    return f"{int(cfg['w'])}x{int(cfg['h'])}"


# Optional left-wrist recordings improve bin visibility; EVAL_WRIST_VIDEO overrides the default.


WRIST_VIDEO_DEFAULT_TASKS = {
    "adjust_bottle_dustbin",
    "put_bottles_dustbin",
}


def want_wrist_video(args):
    # Only start wrist video when that camera is configured.
    if not args.get("camera", {}).get("collect_wrist_camera", True):
        return False
    override = os.environ.get("EVAL_WRIST_VIDEO", "").strip()
    if override:
        return parse_bool(override)
    # Record head-camera video by default; EVAL_WRIST_VIDEO=1 enables an additional wrist file.

    return False


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n"}:
            return False
    return bool(value)


def parse_optional_nonnegative_int(value, name):
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "none", "null", "unlimited"}:
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError(f"`{name}` must be >= 0 or None, got: {value}")
    return parsed


def _result_suffix_from_task_config(task_config):
    if task_config == "demo_clean":
        return "clean"
    if task_config == "demo_randomized":
        return "random"
    return None


def main(usr_args):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_name = usr_args["task_name"]
    task_config = usr_args["task_config"]
    ckpt_setting = usr_args["ckpt_setting"]
    # checkpoint_num = usr_args['checkpoint_num']
    policy_name = usr_args["policy_name"]
    instruction_type = usr_args["instruction_type"]
    skip_get_obs_within_replan = parse_bool(usr_args.get("skip_get_obs_within_replan", False))
    # Default to 50 episodes; the runner may explicitly override eval_num_episodes.
    eval_num_episodes = int(usr_args.get("eval_num_episodes", 50))
    if eval_num_episodes <= 0:
        raise ValueError(f"`eval_num_episodes` must be > 0, got: {eval_num_episodes}")
    max_success_videos = parse_optional_nonnegative_int(
        usr_args.get("max_success_videos"), "max_success_videos"
    )
    max_failure_videos = parse_optional_nonnegative_int(
        usr_args.get("max_failure_videos"), "max_failure_videos"
    )
    eval_output_dir = usr_args.get("eval_output_dir")
    save_dir = None
    video_save_dir = None
    video_size = None

    get_model = eval_function_decorator(policy_name, "get_model")

    with open(f"./task_config/{task_config}.yml", "r", encoding="utf-8") as f:
        args = yaml.load(f.read(), Loader=yaml.FullLoader)

    args['task_name'] = task_name
    args["task_config"] = task_config
    args["ckpt_setting"] = ckpt_setting

    embodiment_type = args.get("embodiment")
    embodiment_config_path = os.path.join(CONFIGS_PATH, "_embodiment_config.yml")

    with open(embodiment_config_path, "r", encoding="utf-8") as f:
        _embodiment_types = yaml.load(f.read(), Loader=yaml.FullLoader)

    def get_embodiment_file(embodiment_type):
        robot_file = _embodiment_types[embodiment_type]["file_path"]
        if robot_file is None:
            raise "No embodiment files"
        return robot_file

    with open(CONFIGS_PATH + "_camera_config.yml", "r", encoding="utf-8") as f:
        _camera_config = yaml.load(f.read(), Loader=yaml.FullLoader)

    head_camera_type = args["camera"]["head_camera_type"]
    args["head_camera_h"] = _camera_config[head_camera_type]["h"]
    args["head_camera_w"] = _camera_config[head_camera_type]["w"]

    if len(embodiment_type) == 1:
        args["left_robot_file"] = get_embodiment_file(embodiment_type[0])
        args["right_robot_file"] = get_embodiment_file(embodiment_type[0])
        args["dual_arm_embodied"] = True
    elif len(embodiment_type) == 3:
        args["left_robot_file"] = get_embodiment_file(embodiment_type[0])
        args["right_robot_file"] = get_embodiment_file(embodiment_type[1])
        args["embodiment_dis"] = embodiment_type[2]
        args["dual_arm_embodied"] = False
    else:
        raise "embodiment items should be 1 or 3"

    args["left_embodiment_config"] = get_embodiment_config(args["left_robot_file"])
    args["right_embodiment_config"] = get_embodiment_config(args["right_robot_file"])

    if len(embodiment_type) == 1:
        embodiment_name = str(embodiment_type[0])
    else:
        embodiment_name = str(embodiment_type[0]) + "+" + str(embodiment_type[1])

    if eval_output_dir is not None and str(eval_output_dir).strip() != "":
        save_dir = Path(str(eval_output_dir))
    else:
        save_dir = Path(f"eval_result/{task_name}/{policy_name}/{task_config}/{ckpt_setting}/{current_time}")
    save_dir.mkdir(parents=True, exist_ok=True)

    if args["eval_video_log"]:
        video_save_dir = save_dir
        video_size = get_eval_video_size(args)
        video_save_dir.mkdir(parents=True, exist_ok=True)
        args["eval_video_save_dir"] = video_save_dir

    # output camera config
    print("============= Config =============\n")
    print("\033[95mMessy Table:\033[0m " + str(args["domain_randomization"]["cluttered_table"]))
    print("\033[95mRandom Background:\033[0m " + str(args["domain_randomization"]["random_background"]))
    if args["domain_randomization"]["random_background"]:
        print(" - Clean Background Rate: " + str(args["domain_randomization"]["clean_background_rate"]))
    print("\033[95mRandom Light:\033[0m " + str(args["domain_randomization"]["random_light"]))
    if args["domain_randomization"]["random_light"]:
        print(" - Crazy Random Light Rate: " + str(args["domain_randomization"]["crazy_random_light_rate"]))
    print("\033[95mRandom Table Height:\033[0m " + str(args["domain_randomization"]["random_table_height"]))
    print("\033[95mRandom Head Camera Distance:\033[0m " + str(args["domain_randomization"]["random_head_camera_dis"]))

    print("\033[94mHead Camera Config:\033[0m " + str(args["camera"]["head_camera_type"]) + f", " +
          str(args["camera"]["collect_head_camera"]))
    print("\033[94mWrist Camera Config:\033[0m " + str(args["camera"]["wrist_camera_type"]) + f", " +
          str(args["camera"]["collect_wrist_camera"]))
    print("\033[94mEmbodiment Config:\033[0m " + embodiment_name)
    print("\n==================================")

    TASK_ENV = class_decorator(args["task_name"])
    args["policy_name"] = policy_name
    usr_args["left_arm_dim"] = len(args["left_embodiment_config"]["arm_joints_name"][0])
    usr_args["right_arm_dim"] = len(args["right_embodiment_config"]["arm_joints_name"][1])

    seed = usr_args["seed"]

    st_seed = 100000 * (1 + seed)
    suc_nums = []
    test_num = eval_num_episodes
    topk = 1

    model = get_model(usr_args)
    st_seed, suc_num = eval_policy(task_name,
                                   TASK_ENV,
                                   args,
                                   model,
                                   st_seed,
                                   test_num=test_num,
                                   video_size=video_size,
                                   instruction_type=instruction_type,
                                   skip_get_obs_within_replan=skip_get_obs_within_replan,
                                   max_success_videos=max_success_videos,
                                   max_failure_videos=max_failure_videos)
    suc_nums.append(suc_num)

    topk_success_rate = sorted(suc_nums, reverse=True)[:topk]

    result_suffix = _result_suffix_from_task_config(task_config)
    result_filename = f"_result_{result_suffix}.txt" if result_suffix is not None else "_result.txt"
    file_path = os.path.join(save_dir, result_filename)
    result_text = (
        f"Timestamp: {current_time}\n\n"
        f"Instruction Type: {instruction_type}\n\n"
        + "\n".join(map(str, np.array(suc_nums) / test_num))
    )
    with open(file_path, "w") as file:
        file.write(result_text)

    legacy_file_path = os.path.join(save_dir, "_result.txt")
    if legacy_file_path != file_path:
        with open(legacy_file_path, "w") as file:
            file.write(result_text)

    print(f"Data has been saved to {file_path}")
    # return task_reward


def eval_policy(task_name,
                TASK_ENV,
                args,
                model,
                st_seed,
                test_num=50,
                video_size=None,
                instruction_type=None,
                skip_get_obs_within_replan=False,
                max_success_videos=None,
                max_failure_videos=None):
    print(f"\033[34mTask Name: {args['task_name']}\033[0m")
    print(f"\033[34mPolicy Name: {args['policy_name']}\033[0m")

    expert_check = True
    TASK_ENV.suc = 0
    TASK_ENV.test_num = 0

    now_id = 0
    succ_seed = 0
    suc_test_seed_list = []

    policy_name = args["policy_name"]
    eval_func = eval_function_decorator(policy_name, "eval")
    reset_func = eval_function_decorator(policy_name, "reset_model")

    now_seed = st_seed
    task_total_reward = 0
    clear_cache_freq = args["clear_cache_freq"]

    args["eval_mode"] = True
    base_eval_video_save_dir = args.get("eval_video_save_dir")
    saved_success_videos = 0
    saved_failure_videos = 0

    # Use frozen seeds in formal evaluation. Expert replay still populates instruction placeholders but does not select a different accepted seed.
    frozen_seeds = None
    if os.environ.get("ROBOTWIN_FROZEN_SEEDS", "1") != "0":
        _sp = os.path.join("suite", "seeds", "%s.json" % task_name)
        if os.path.exists(_sp):
            import json as _json
            _sd = _json.load(open(_sp, encoding="utf-8"))
            frozen_seeds = list(_sd.get("seeds") or [])
            if len(frozen_seeds) < test_num:
                raise RuntimeError(
                    "%s has only %d frozen seeds, fewer than requested %d; populate suite/seeds/%s.json first"
                    % (task_name, len(frozen_seeds), test_num, task_name))
            frozen_seeds = frozen_seeds[:test_num]
            print("[frozen] %s uses %d frozen seeds (no expert seed search)" % (task_name, len(frozen_seeds)))

    expert_attempts = 0
    expert_attempt_limit = int(os.environ.get("ROBOTWIN_MAX_EXPERT_SEED_ATTEMPTS", "100"))
    if expert_attempt_limit < 1:
        raise ValueError("ROBOTWIN_MAX_EXPERT_SEED_ATTEMPTS must be positive")
    while succ_seed < test_num:
        if frozen_seeds is not None:

            now_seed = frozen_seeds[succ_seed]


        if expert_check:
            if expert_attempts >= expert_attempt_limit:
                raise RuntimeError(
                    f"No expert-validated seed for {task_name} after {expert_attempt_limit} attempts; "
                    "episode is unscored. This does not prove the task is impossible.")
            expert_attempts += 1
        render_freq = args["render_freq"]
        args["render_freq"] = 0

        if expert_check:
            try:
                TASK_ENV.setup_demo(now_ep_num=now_id, seed=now_seed, is_test=True, **args)
                episode_info = TASK_ENV.play_once()
                TASK_ENV.close_env()
            except UnStableError as e:
                # print(" -------------")
                # print("Error: ", e)
                # print(" -------------")
                TASK_ENV.close_env()
                now_seed += 1
                args["render_freq"] = render_freq
                continue
            except Exception as e:
                print(" -------------")
                print("Error: ", e)
                print("Stack Trace: ", traceback.format_exc())
                print(" -------------")
                TASK_ENV.close_env()
                now_seed += 1
                args["render_freq"] = render_freq
                print("error occurs !")
                continue

        if frozen_seeds is not None or (not expert_check) or (
                TASK_ENV.plan_success and TASK_ENV.check_success()):
            succ_seed += 1
            suc_test_seed_list.append(now_seed)
            # Reset the failed-seed search budget after a usable seed: the limit counts consecutive failures, not attempts across the entire run.


            expert_attempts = 0
        else:
            now_seed += 1
            args["render_freq"] = render_freq
            continue

        args["render_freq"] = render_freq

        # Record the first N seeds regardless of outcome so systems share video initial states; ROBOTWIN_VIDEO_FIRST_N defaults to 10.


        _vid_n = int(os.environ.get("ROBOTWIN_VIDEO_FIRST_N", "10"))
        should_record_video = base_eval_video_save_dir is not None and (succ_seed - 1) < _vid_n
        args["eval_video_save_dir"] = base_eval_video_save_dir if should_record_video else None
        TASK_ENV.setup_demo(now_ep_num=now_id, seed=now_seed, is_test=True, **args)
        episode_info_list = [episode_info["info"]]
        # Seed global template shuffling and use an independent RandomState for final instruction sampling.


        import random as _rnd
        _rnd.seed(int(now_seed))
        results = generate_episode_descriptions(args["task_name"], episode_info_list, test_num)
        instruction = np.random.RandomState(int(now_seed)).choice(results[0][instruction_type])
        TASK_ENV.set_instruction(instruction=instruction)  # set language instruction
        # Save the actual instruction for each episode for video and predicate auditing.

        if base_eval_video_save_dir is not None:
            try:
                os.makedirs(base_eval_video_save_dir, exist_ok=True)
                with open(os.path.join(base_eval_video_save_dir, "_instructions.txt"),
                          "a", encoding="utf-8") as _f:
                    _f.write("episode%d\tseed=%d\t%s\n" % (succ_seed - 1, now_seed, instruction))
            except Exception:
                pass

        video_tmp_path = None
        video_filename = None
        if TASK_ENV.eval_video_path is not None:
            video_suffix = _result_suffix_from_task_config(args.get("task_config"))
            video_filename = f"episode{TASK_ENV.test_num}.mp4"
            if video_suffix is not None:
                video_filename = f"episode{TASK_ENV.test_num}_{video_suffix}.mp4"
            video_stem, _ = os.path.splitext(video_filename)
            video_tmp_path = os.path.join(TASK_ENV.eval_video_path, f".{video_stem}.tmp.mp4")
            ffmpeg = subprocess.Popen(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-f",
                    "rawvideo",
                    "-pixel_format",
                    "rgb24",
                    "-video_size",
                    video_size,
                    "-framerate",
                    "10",
                    "-i",
                    "-",
                    "-pix_fmt",
                    "yuv420p",
                    "-vcodec",
                    "libx264",
                    "-crf",
                    "23",
                    video_tmp_path,
                ],
                stdin=subprocess.PIPE,
            )
            wrist_ffmpeg = None
            wrist_tmp_path = None
            if want_wrist_video(args):
                wrist_tmp_path = os.path.join(TASK_ENV.eval_video_path, f".{video_stem}_wrist.tmp.mp4")
                wrist_ffmpeg = subprocess.Popen(
                    [
                        "ffmpeg", "-y", "-loglevel", "error",
                        "-f", "rawvideo", "-pixel_format", "rgb24",
                        "-video_size", get_eval_wrist_video_size(args),
                        "-framerate", "10", "-i", "-",
                        "-pix_fmt", "yuv420p", "-vcodec", "libx264", "-crf", "23",
                        wrist_tmp_path,
                    ],
                    stdin=subprocess.PIPE,
                )
            TASK_ENV._set_eval_video_ffmpeg(ffmpeg, wrist_ffmpeg)

        succ = False
        reset_func(model)
        # Measure eval-call timing consistently and save it after any post-success recording grace period.
        _lat = []
        _t_ep0 = time.time()
        if hasattr(model, "infer_times"):
            model.infer_times = []
        while TASK_ENV.take_action_cnt < TASK_ENV.step_lim:
            need_obs = True
            if skip_get_obs_within_replan and hasattr(model, "should_request_observation"):
                need_obs = bool(model.should_request_observation())

            observation = None
            if need_obs:
                observation = TASK_ENV.get_obs()
            _t0 = time.time()
            eval_func(TASK_ENV, model, observation)
            _lat.append(time.time() - _t0)
            if TASK_ENV.eval_success:
                succ = True

                if getattr(TASK_ENV, "_post_success_actions", 0) >= int(
                        getattr(TASK_ENV, "POST_SUCCESS_ACTIONS", 0)):
                    break

        if base_eval_video_save_dir is not None:
            try:
                _n = len(_lat)
                _srt = sorted(_lat)
                _q = lambda f: (_srt[min(_n - 1, int(f * _n))] if _n else 0.0)  # noqa: E731
                _mt = getattr(model, "infer_times", None)
                _mtot = ("%.4f" % sum(_mt)) if _mt else "-"
                _mmean = ("%.4f" % (sum(_mt) / len(_mt))) if _mt else "-"
                with open(os.path.join(base_eval_video_save_dir, "_latency.txt"),
                          "a", encoding="utf-8") as _f:
                    _f.write("episode%d\tcalls=%d\teval_wall_total=%.4f\teval_wall_mean=%.4f\t"
                             "eval_wall_p50=%.4f\teval_wall_p95=%.4f\tmodel_total=%s\tmodel_mean=%s\t"
                             "steps=%d\tepisode_wall=%.2f\n" % (
                                 succ_seed - 1, _n, sum(_lat), (sum(_lat) / _n if _n else 0.0),
                                 _q(0.5), _q(0.95), _mtot, _mmean,
                                 int(getattr(TASK_ENV, "take_action_cnt", 0)), time.time() - _t_ep0))
            except Exception:
                pass
        # Record maximum lift clearance for post-run diagnostics.

        _c = getattr(TASK_ENV, "_max_clearance", None)
        if base_eval_video_save_dir is not None and _c is not None:
            try:
                _dt = _dd = None
                _md = getattr(TASK_ENV, "_maxdisp", None)
                if _md:
                    _dt = _md.get("target")
                    _others = [v for k, v in _md.items() if k != "target"]
                    _dd = max(_others) if _others else 0.0
                with open(os.path.join(base_eval_video_save_dir, "_lift.txt"),
                          "a", encoding="utf-8") as _f:
                    _ch = getattr(TASK_ENV, "_max_clearance_held", -1e9)
                    _f.write("episode%d	max_clearance=%.4f	max_gripped_clearance=%s	threshold=%.4f	target_displacement=%s	max_distractor_displacement=%s	%s\n" % (
                        succ_seed - 1, _c,
                        ("%.4f" % _ch) if _ch > -1e8 else "never_gripped",
                        getattr(TASK_ENV, "_clearance_thr", 0.0) or 0.0,
                        ("%.4f" % _dt) if _dt is not None else "-",
                        ("%.4f" % _dd) if _dd is not None else "-",
                        "success" if succ else "failure"))
            except Exception:
                pass

        # Record minimum contact distance, which a binary success flag does not expose.

        _d = getattr(TASK_ENV, "_min_contact_d", None)
        _want = False
        try:
            _want = bool(TASK_ENV.wants_contact_log())
        except Exception:
            _want = False
        if _want and base_eval_video_save_dir is not None and _d is None:
            _d = 1e9
        if base_eval_video_save_dir is not None and _d is not None and (_d < 1e8 or _want):
            try:
                with open(os.path.join(base_eval_video_save_dir, "_contact.txt"),
                          "a", encoding="utf-8") as _f:
                    _f.write("episode%d	min_distance=%s	threshold=%.4f	%s\n" % (
                        succ_seed - 1,
                        ("never_contacted" if _d >= 1e8 else "%.4f" % _d),
                        getattr(TASK_ENV, "_contact_thr", 0.0) or 0.0,
                        "success" if succ else "failure"))
            except Exception:
                pass

        # task_total_reward += TASK_ENV.episode_score
        if TASK_ENV.eval_video_path is not None:
            TASK_ENV._del_eval_video_ffmpeg()
            if video_tmp_path is not None and video_filename is not None and os.path.exists(video_tmp_path):
                if succ:
                    keep_video = max_success_videos is None or saved_success_videos < max_success_videos
                else:
                    keep_video = max_failure_videos is None or saved_failure_videos < max_failure_videos
                if keep_video:
                    video_status_dir = os.path.join(TASK_ENV.eval_video_path, "success" if succ else "failure")
                    os.makedirs(video_status_dir, exist_ok=True)
                    os.replace(video_tmp_path, os.path.join(video_status_dir, video_filename))
                    if succ:
                        saved_success_videos += 1
                    else:
                        saved_failure_videos += 1
                else:
                    os.remove(video_tmp_path)
                # Apply the same retention policy to wrist video, using the _wrist suffix.
                if wrist_tmp_path is not None and os.path.exists(wrist_tmp_path):
                    if keep_video:
                        stem, ext = os.path.splitext(video_filename)
                        os.replace(wrist_tmp_path,
                                   os.path.join(video_status_dir, f"{stem}_wrist{ext}"))
                    else:
                        os.remove(wrist_tmp_path)

        if succ:
            TASK_ENV.suc += 1
            print("\033[92mSuccess!\033[0m")
        else:
            print("\033[91mFail!\033[0m")

        now_id += 1
        TASK_ENV.close_env(clear_cache=((succ_seed + 1) % clear_cache_freq == 0))

        if TASK_ENV.render_freq:
            TASK_ENV.viewer.close()

        TASK_ENV.test_num += 1

        print(
            f"\033[93m{task_name}\033[0m | \033[94m{args['policy_name']}\033[0m | \033[92m{args['task_config']}\033[0m | \033[91m{args['ckpt_setting']}\033[0m\n"
            f"Success rate: \033[96m{TASK_ENV.suc}/{TASK_ENV.test_num}\033[0m => \033[95m{round(TASK_ENV.suc/TASK_ENV.test_num*100, 1)}%\033[0m, current seed: \033[90m{now_seed}\033[0m\n"
        )
        # TASK_ENV._take_picture()
        now_seed += 1

    return now_seed, TASK_ENV.suc


def parse_args_and_config():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--overrides", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Parse overrides
    def parse_override_pairs(pairs):
        override_dict = {}
        for i in range(0, len(pairs), 2):
            key = pairs[i].lstrip("--")
            value = pairs[i + 1]
            try:
                value = eval(value)
            except:
                pass
            override_dict[key] = value
        return override_dict

    if args.overrides:
        overrides = parse_override_pairs(args.overrides)
        config.update(overrides)

    return config


if __name__ == "__main__":
    from test_render import Sapien_TEST
    Sapien_TEST()

    usr_args = parse_args_and_config()

    main(usr_args)
