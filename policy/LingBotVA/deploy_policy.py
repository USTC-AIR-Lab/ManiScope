"""LingBot-VA evaluation adapter using the official reset/infer/cache protocol through the HTTP bridge. State is joint position; actions follow the upstream relative end-effector convention."""

import base64
import json
import logging
import os

import cv2
import numpy as np
import requests
from scipy.spatial.transform import Rotation as R

logger = logging.getLogger(__name__)


def _png_b64(rgb):
    return base64.b64encode(cv2.imencode(".png", cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR))[1].tobytes()).decode()


def add_eef_pose(new_pose, init_pose):            # Match the upstream implementation.
    new_pose_R = R.from_quat(new_pose[3:7][None])
    init_pose_R = R.from_quat(init_pose[3:7][None])
    out_rot = (init_pose_R * new_pose_R).as_quat().reshape(-1)
    out_trans = new_pose[:3] + init_pose[:3]
    return np.concatenate([out_trans, out_rot, new_pose[7:8]])


def add_init_pose(new_pose, init_pose):           # Match the upstream implementation.
    left_pose = add_eef_pose(new_pose[:8], init_pose[:8])
    right_pose = add_eef_pose(new_pose[8:], init_pose[8:])
    return np.concatenate([left_pose, right_pose])


def _fmt(observation, prompt):
    o = observation["observation"]
    return {"images": {str(i + 1): _png_b64(o[c]["rgb"]) for i, c in enumerate(("head_camera", "left_camera", "right_camera"))},
            "state": [float(v) for v in np.asarray(observation["joint_action"]["vector"], np.float32)], "prompt": prompt}


class LingBotVAClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.first = True
        self.first_obs = None
        self.init_eef = None
        self.stage_log_path = os.environ.get("STAGE_LOG") or None
        self.stages = {}
        self.infer_times = []
        print(f"[LingBotVA] server={self.base_url} upstream reset/infer/kv protocol action_type=ee")

    def _post(self, path, payload, timeout=900):
        r = requests.post(f"{self.base_url}{path}", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def begin_episode(self, observation, prompt):
        self._post("/v1/reset", {"prompt": prompt}, timeout=120)
        ep = observation["endpose"]
        self.init_eef = np.array(list(ep["left_endpose"]) + [ep["left_gripper"]] + list(ep["right_endpose"]) + [ep["right_gripper"]],
                                 dtype=np.float64)
        self.first_obs = _fmt(observation, prompt)
        self.first = True

    def infer(self):
        body = self._post("/v1/infer", {"observation": self.first_obs})
        if "infer_time" in body:
            self.infer_times.append(float(body["infer_time"]))
        act = np.asarray(body["action"], dtype=np.float64)     # [16, F, S]
        if act.ndim != 3 or act.shape[0] != 16 or not np.isfinite(act).all():
            raise RuntimeError(f"Service returned invalid actions {act.shape}")
        return act

    def update_kv(self, frames):
        self._post("/v1/kv", {"frames": frames})

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
        self.first_obs = None
        self.init_eef = None
        self.first = True


def get_model(usr_args):
    return LingBotVAClient(base_url=usr_args["base_url"])


def eval(TASK_ENV, model, observation):
    if observation is None:
        observation = TASK_ENV.get_obs()
    bridge = getattr(TASK_ENV, "maybe_bridge_to_stage2", None)
    if bridge is not None:
        bridge()
    prompt = TASK_ENV.get_instruction()
    if model.first_obs is None:
        model.begin_episode(observation, prompt)
    action = model.infer()                                  # [16, F, S]
    assert action.shape[2] % 4 == 0
    action_per_frame = action.shape[2] // 4
    start_idx = 1 if model.first else 0
    key_frames, done = [], False
    for i in range(start_idx, action.shape[1]):
        for j in range(action.shape[2]):
            ee = add_init_pose(action[:, i, j], model.init_eef)
            ee = np.concatenate([ee[:3], ee[3:7] / np.linalg.norm(ee[3:7]), ee[7:11], ee[11:15] / np.linalg.norm(ee[11:15]), ee[15:16]])
            TASK_ENV.take_action(ee, action_type="ee")
            if TASK_ENV.eval_success or TASK_ENV.take_action_cnt >= TASK_ENV.step_lim:
                done = True
                break
            if (j + 1) % action_per_frame == 0:
                key_frames.append(_fmt(TASK_ENV.get_obs(), prompt))
        if done:
            break
    model.first = False
    if not done and key_frames:
        model.update_kv(key_frames)
    model.record_stage(TASK_ENV)
    return TASK_ENV.get_obs()


def reset_model(model):
    model.reset()
