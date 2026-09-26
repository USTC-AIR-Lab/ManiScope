"""X-VLA RoboTwin adapter for the upstream FastAPI service. Encode the official observations and commanded end-effector state, then convert 20-dimensional xyz/rot6D/gripper predictions to 16-dimensional xyz/quaternion/gripper actions. Record HTTP time when isolated model time is unavailable."""

import base64
import json
import logging
import os
import time

import numpy as np
import requests
from scipy.spatial.transform import Rotation as R

logger = logging.getLogger(__name__)


def _jn_dumps(arr):
    """Encode the json_numpy wire representation expected by the server without requiring that package in the simulator environment."""
    a = np.ascontiguousarray(arr)
    return json.dumps({"__numpy__": base64.b64encode(a.tobytes()).decode(),
                       "dtype": str(a.dtype), "shape": list(a.shape)})


def quat_to_rotate6D(q):
    return R.from_quat(q).as_matrix()[..., :, :2].reshape(q.shape[:-1] + (6,))


def rotate6D_to_quat(v6):
    v6 = np.asarray(v6)
    a1, a2 = v6[..., 0:5:2], v6[..., 1:6:2]
    b1 = a1 / np.linalg.norm(a1, axis=-1, keepdims=True)
    b2 = a2 - np.sum(b1 * a2, axis=-1, keepdims=True) * b1
    b2 = b2 / np.linalg.norm(b2, axis=-1, keepdims=True)
    b3 = np.cross(b1, b2)
    return R.from_matrix(np.stack((b1, b2, b3), axis=-1)).as_quat()


class XVLAClient:
    def __init__(self, base_url, domain_id=6, action_horizon=30, gripper_thr=0.7):
        self.url = base_url.rstrip("/") + "/act"
        self.domain_id = int(domain_id)
        self.action_horizon = int(action_horizon)
        self.gripper_thr = float(gripper_thr)
        self.stage_log_path = os.environ.get("STAGE_LOG") or None
        self.stages = {}
        self.infer_times = []
        self._last_cmd = None          # Use the previous commanded left/right seven-dimensional target poses.
        print(f"[XVLA] server={self.url} domain_id={self.domain_id} horizon={self.action_horizon} action=ee")

    # Encode observations for the request; measure HTTP round-trip time when the server provides no isolated inference duration.
    def build_proprio(self, obs):
        ep = obs["endpose"]
        left_ee = np.asarray(ep["left_endpose"], dtype=np.float64)
        right_ee = np.asarray(ep["right_endpose"], dtype=np.float64)
        if self._last_cmd is not None:
            left_ee, right_ee = self._last_cmd
        lg = 1.0 - 2.0 * float(ep["left_gripper"])
        rg = 1.0 - 2.0 * float(ep["right_gripper"])
        return np.concatenate([left_ee[:3], quat_to_rotate6D(left_ee[3:7]), [lg],
                               right_ee[:3], quat_to_rotate6D(right_ee[3:7]), [rg]]).astype(np.float32)

    def get_action(self, instruction, obs):
        o = obs["observation"]
        query = {
            "domain_id": self.domain_id,
            "proprio": _jn_dumps(self.build_proprio(obs)),
            "language_instruction": instruction,
            "image0": _jn_dumps(np.asarray(o["head_camera"]["rgb"], dtype=np.uint8)),
            "image1": _jn_dumps(np.asarray(o["left_camera"]["rgb"], dtype=np.uint8)),
            "image2": _jn_dumps(np.asarray(o["right_camera"]["rgb"], dtype=np.uint8)),
        }
        t0 = time.time()
        ret = requests.post(self.url, json=query, timeout=60)
        ret.raise_for_status()
        self.infer_times.append(time.time() - t0)
        act = np.asarray(ret.json()["action"], dtype=np.float64)
        if act.ndim != 2 or act.shape[1] != 20:
            raise RuntimeError(f"X-VLA returned invalid action shape {act.shape}")
        if not np.isfinite(act).all():
            raise RuntimeError("X-VLA returned NaN/inf actions")
        return act[: self.action_horizon]

    # Convert (N, 20) predictions to (N, 16) end-effector actions.
    def to_ee(self, act):
        lq = rotate6D_to_quat(act[:, 3:9]); rq = rotate6D_to_quat(act[:, 13:19])
        lg = 1.0 - 2.0 * (act[:, 9:10] > self.gripper_thr)
        rg = 1.0 - 2.0 * (act[:, 19:20] > self.gripper_thr)
        return np.concatenate([act[:, 0:3], lq, lg, act[:, 10:13], rq, rg], axis=1)

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
        self._last_cmd = None


# --------------------------------------------------------------------------- #
def get_model(usr_args):
    return XVLAClient(
        base_url=usr_args["base_url"],
        domain_id=int(usr_args.get("domain_id", 6)),
        action_horizon=int(usr_args.get("action_horizon", 30)),
        gripper_thr=float(usr_args.get("gripper_thr", 0.7)),
    )


def eval(TASK_ENV, model, observation):
    if observation is None:
        observation = TASK_ENV.get_obs()
    bridge = getattr(TASK_ENV, "maybe_bridge_to_stage2", None)
    if bridge is not None:
        bridge()
    instruction = TASK_ENV.get_instruction()
    chunk = model.to_ee(model.get_action(instruction, observation))
    for action in chunk:
        TASK_ENV.take_action(action, action_type="ee")
        model._last_cmd = (action[0:7].copy(), action[8:15].copy())
        if TASK_ENV.eval_success or TASK_ENV.take_action_cnt >= TASK_ENV.step_lim:
            break
    model.record_stage(TASK_ENV)
    return TASK_ENV.get_obs()


def reset_model(model):
    model.reset()
