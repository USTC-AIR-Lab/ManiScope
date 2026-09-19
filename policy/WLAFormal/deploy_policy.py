"""公开 WLA (SJTU-DENG-Lab/wla_robotwin_all_image_action) 的 RoboTwin eval 插件。

瘦 HTTP 客户端（同 DM05/Pi05 契约），服务端是 policy/WLAFormal/serve.py。与官方
experiments/robotwin/robotwin_utils.py 的 eval_step 逐行对齐，只多了本内核统一的中断条件：

  * **公开官方对该 checkpoint 用 eef 控制**（run_robotwin_eval.sh: CONTROL_MODE=eef, UNNORM_KEY=robotwin_all_eef, 16 维）：
    状态 = [左 endpose(7), 左夹爪, 右 endpose(7), 右夹爪]（obs["endpose"]），动作 (32, 16) 走 take_action(action_type="ee")
  * 每次 eval(): 当前观测 + 上一 chunk 抓的历史 head 帧 -> 推理；逐个 take_action(ee)，每步 get_obs()；
    执行到第 target = max(len-8-1, 0) 步时把该观测存为下一次的历史帧
    （官方逻辑：history_obs_step=8，历史帧是上一 chunk 倒数第 9 步的观测；首次推理没有历史就用当前帧）
  * 与 DM05/Pi05 一致：eval_success / step_lim 时中断；NaN/inf 报错；record_stage 落盘；infer_times 记服务端耗时
"""

import base64
import json
import logging
import os

import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)

_CAM = {"head_camera_rgb": "head_camera", "left_camera_rgb": "left_camera", "right_camera_rgb": "right_camera"}


def _png_b64(rgb):
    return base64.b64encode(cv2.imencode(".png", cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR))[1].tobytes()).decode()


class WLAFormalClient:
    def __init__(self, base_url, use_cameras, action_horizon=32, history_obs_step=8, control_mode="eef"):
        self.base_url = base_url.rstrip("/")
        self.server_url = f"{self.base_url}/v1/infer"
        self.use_cameras = list(use_cameras)
        self.action_horizon = int(action_horizon)
        self.history_obs_step = int(history_obs_step)
        self.control_mode = control_mode
        self.history_head = None          # 上一 chunk 抓到的历史 head 帧（RGB ndarray）
        self.stage_log_path = os.environ.get("STAGE_LOG") or None
        self.stages = {}
        self.infer_times = []
        print(f"[WLAFormal] server={self.server_url} cameras={self.use_cameras} "
              f"horizon={self.action_horizon} history_obs_step={self.history_obs_step} control={self.control_mode}")

    def get_action(self, instruction, observation):
        o = observation["observation"]
        images = {str(i + 1): _png_b64(o[_CAM.get(c, c.replace("_rgb", ""))]["rgb"]) for i, c in enumerate(self.use_cameras)}
        if self.history_head is not None:
            images["0"] = _png_b64(self.history_head)
        if self.control_mode == "eef":       # 官方 _encode_obs 的 eef 分支
            ep = observation["endpose"]
            state = np.concatenate([np.asarray(ep["left_endpose"], np.float32).reshape(-1), np.asarray(ep["left_gripper"], np.float32).reshape(-1),
                                    np.asarray(ep["right_endpose"], np.float32).reshape(-1), np.asarray(ep["right_gripper"], np.float32).reshape(-1)])
        else:
            state = np.asarray(observation["joint_action"]["vector"], dtype=np.float32)
        ret = requests.post(self.server_url,
                            json={"observation": {"prompt": instruction, "images": images, "state": state.tolist()},
                                  "sampling": {}}, timeout=60)
        ret.raise_for_status()
        body = ret.json()
        if "infer_time" in body:
            self.infer_times.append(float(body["infer_time"]))
        chunk = np.asarray(body["actions"], dtype=np.float64)
        if self.action_horizon > 0 and len(chunk) > self.action_horizon:
            chunk = chunk[: self.action_horizon]
        if not np.isfinite(chunk).all():
            raise RuntimeError("推理服务返回 NaN/inf 动作")
        return chunk

    def record_stage(self, TASK_ENV):
        if self.stage_log_path is None:
            return
        stage = getattr(TASK_ENV, "stage", None)
        if stage is None:
            return
        key = str(getattr(TASK_ENV, "test_num", 0))
        e = self.stages.setdefault(key, {"episode": int(key), "max_stage": 0, "success": False})
        e["max_stage"] = max(e["max_stage"], int(stage))
        e["success"] = bool(getattr(TASK_ENV, "eval_success", False)) or e["success"]
        try:
            with open(self.stage_log_path, "w", encoding="utf-8") as f:
                json.dump(list(self.stages.values()), f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def reset(self):
        self.history_head = None
        try:
            requests.post(f"{self.base_url}/v1/reset", timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("通知推理服务 /v1/reset 失败: %s", exc)


def get_model(usr_args):
    cams = usr_args["cameras"]
    if isinstance(cams, str):
        cams = cams.split(",")
    return WLAFormalClient(base_url=usr_args["base_url"], use_cameras=cams,
                           action_horizon=int(usr_args.get("action_horizon", 32)),
                           history_obs_step=int(usr_args.get("history_obs_step", 8)),
                           control_mode=str(usr_args.get("control_mode", "eef")))


def eval(TASK_ENV, model, observation):
    if observation is None:
        observation = TASK_ENV.get_obs()
    bridge = getattr(TASK_ENV, "maybe_bridge_to_stage2", None)
    if bridge is not None:
        bridge()
    instruction = TASK_ENV.get_instruction()
    actions = model.get_action(instruction, observation)
    # 官方 eval_step：历史帧取本 chunk 第 max(len-8-1, 0) 步执行后的观测
    target_history_index = max(len(actions) - model.history_obs_step - 1, 0)
    last_obs = observation
    for index, action in enumerate(actions):
        TASK_ENV.take_action(action, action_type=("ee" if model.control_mode == "eef" else "qpos"))
        last_obs = TASK_ENV.get_obs()
        if index == target_history_index:
            model.history_head = np.asarray(last_obs["observation"]["head_camera"]["rgb"]).copy()
        if TASK_ENV.eval_success or TASK_ENV.take_action_cnt >= TASK_ENV.step_lim:
            break
    if model.history_head is None:
        model.history_head = np.asarray(last_obs["observation"]["head_camera"]["rgb"]).copy()
    model.record_stage(TASK_ENV)
    return last_obs


def reset_model(model):
    model.reset()
