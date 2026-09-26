"""FastWAM RoboTwin HTTP adapter using the configured upstream replanning interval and the shared get_model/eval/reset_model contract."""

import base64
import json
import logging
import os

import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)

# Use RoboTwin camera names. Record server-reported inference duration per episode in _latency.txt.
_CAM_SOURCE = {
    "head_camera_rgb": "head_camera",
    "front_camera_rgb": "front_camera",
    "left_camera_rgb": "left_camera",
    "right_camera_rgb": "right_camera",
}


class FastWAMClient:
    def __init__(self, base_url, use_cameras, action_horizon=24,
                 action_mode="absolute", api_style="v1", sampling=None):
        self.base_url = base_url.rstrip("/")
        assert api_style == "v1", "Pi0.5 service only supports /v1/infer"
        self.api_style = api_style
        self.server_url = f"{self.base_url}/v1/infer"
        self.use_cameras = list(use_cameras)
        self.action_horizon = int(action_horizon)
        assert action_mode in ("absolute", "relative", "delta"), \
            "action_mode must be absolute, relative or delta"
        self.action_mode = action_mode
        self.sampling = dict(sampling or {})
        self.stage_log_path = os.environ.get("STAGE_LOG") or None
        self.stages = {}

        self.infer_times = []
        print(f"[FastWAM] server={self.server_url} cameras={self.use_cameras} "
              f"horizon={self.action_horizon} mode={self.action_mode}"
              + (f", stage log -> {self.stage_log_path}" if self.stage_log_path else ""))

    def _infer_v1(self, instruction, encoded_images, state):
        obs = {
            "prompt": instruction,
            "images": {str(i + 1): base64.b64encode(img).decode()
                       for i, img in enumerate(encoded_images)},
        }
        if state is not None:
            obs["state"] = np.asarray(state, dtype=np.float32).tolist()
        ret = requests.post(self.server_url,
                            json={"observation": obs, "sampling": self.sampling},
                            timeout=30)
        ret.raise_for_status()
        body = ret.json()
        raw = body.get("actions")
        if raw is None:
            raise RuntimeError("v1 service response missing actions")
        if "infer_time" in body:
            self.infer_times.append(float(body["infer_time"]))
        return raw

    def get_action(self, instruction, rgbs, state=None):
        encoded = [cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))[1].tobytes()
                   for rgb in rgbs]
        raw = self._infer_v1(instruction, encoded, state)
        chunk = np.asarray(raw, dtype=np.float64)
        if self.action_horizon > 0 and len(chunk) > self.action_horizon:
            chunk = chunk[: self.action_horizon]
        if not np.isfinite(chunk).all():
            raise RuntimeError("Service returned NaN/inf actions; verify the checkpoint and inference configuration")
        return chunk

    @staticmethod
    def _to_absolute(state, chunk, cumulative):
        la, ra = state[:6], state[7:13]
        l_arm, l_grip = chunk[:, :6], chunk[:, 6:7]
        r_arm, r_grip = chunk[:, 7:13], chunk[:, 13:14]
        if cumulative:
            l_arm, r_arm = np.cumsum(l_arm, axis=0), np.cumsum(r_arm, axis=0)
        return np.concatenate([la + l_arm, l_grip, ra + r_arm, r_grip], axis=1)

    def to_absolute(self, state, chunk):
        if self.action_mode == "absolute":
            return chunk
        return self._to_absolute(state, chunk, cumulative=(self.action_mode == "delta"))

    def record_stage(self, TASK_ENV):
        if self.stage_log_path is None:
            return
        stage = getattr(TASK_ENV, "stage", None)
        if stage is None:
            return
        key = str(getattr(TASK_ENV, "test_num", 0))
        entry = self.stages.setdefault(key, {"episode": int(key), "max_stage": 0, "success": False})
        entry["max_stage"] = max(entry["max_stage"], int(stage))
        entry["success"] = bool(getattr(TASK_ENV, "eval_success", False)) or entry["success"]
        try:
            with open(self.stage_log_path, "w", encoding="utf-8") as f:
                json.dump(list(self.stages.values()), f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def reset(self):
        try:
            requests.post(f"{self.base_url}/v1/reset", timeout=5)
        except Exception as exc:
            logger.warning("Failed to notify inference service /v1/reset: %s", exc)


# --------------------------------------------------------------------------- #
# RoboTwin single-evaluator interface.
# --------------------------------------------------------------------------- #
def encode_obs(observation, use_cameras):
    imgs = []
    for cam in use_cameras:
        src = _CAM_SOURCE.get(cam, cam.replace("_rgb", ""))
        imgs.append(np.asarray(observation["observation"][src]["rgb"]))
    state = observation["joint_action"]["vector"]
    return imgs, state


def get_model(usr_args):
    cams = usr_args["cameras"]
    if isinstance(cams, str):
        cams = cams.split(",")
    return FastWAMClient(
        base_url=usr_args["base_url"],
        use_cameras=cams,
        action_horizon=int(usr_args.get("action_horizon", 24)),
        action_mode=usr_args.get("action_mode", "absolute"),
        api_style=usr_args.get("api_style", "v1"),
        sampling=usr_args.get("sampling", None),
    )


def eval(TASK_ENV, model, observation):
    if observation is None:
        observation = TASK_ENV.get_obs()
    bridge = getattr(TASK_ENV, "maybe_bridge_to_stage2", None)
    if bridge is not None:
        bridge()

    rgbs, state = encode_obs(observation, model.use_cameras)
    instruction = TASK_ENV.get_instruction()
    chunk = model.to_absolute(state, model.get_action(instruction, rgbs, state))

    for action in chunk:
        TASK_ENV.take_action(action, action_type="qpos")
        if TASK_ENV.eval_success or TASK_ENV.take_action_cnt >= TASK_ENV.step_lim:
            break
    model.record_stage(TASK_ENV)
    return TASK_ENV.get_obs()


def reset_model(model):
    model.reset()
