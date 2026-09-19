"""X-WAM (sharinka0715/X-WAM-checkpoints robotwin_sft) 的 RoboTwin eval 插件。

官方 evaluation/X-WAM/deploy_policy.py 的原样移植：坐标变换（BASE_COORD_XFORM / EEF_AXES_XFORM）、16 维 eef 状态编码、
增量动作累加 compute_future_poses、逐步 take_action(action_type="ee") 一字不改；只把 zmq 传输换成本内核统一的
HTTP /v1/infer（服务端 policy/XWAM/serve.py），并加上本内核统一的中断条件（eval_success / step_lim）与 _latency 记录。
官方默认：action_length=32（每次执行前 32 步再重推），cfg=0.0，seed = md5(env_rank, rollout_id, step_id)，
rollout_id = episode 序号（官方 client 传 now_id），step_id = take_action_cnt。
"""

import base64
import json
import logging
import os

import cv2
import numpy as np
import requests
from scipy.spatial.transform import Rotation

logger = logging.getLogger(__name__)

# Base frame is redefined by rotating the frame +90 deg around its z axis.
# For coordinates expressed in the frame, this is a change of basis by Rz(-90 deg).
BASE_COORD_XFORM = np.array(
    [
        [0.0, 1.0, 0.0],
        [-1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
    ],
    dtype=np.float64,
)

# New eef axes are defined as x' = z, z' = x, and y' = -y to keep a right-handed frame.
# This matrix maps coordinates from the new eef frame to the old eef frame.
EEF_AXES_XFORM = np.array(
    [
        [0.0, 0.0, 1.0],
        [0.0, -1.0, 0.0],
        [1.0, 0.0, 0.0],
    ],
    dtype=np.float64,
)


def compute_future_poses(initial_proprio: np.ndarray, actions: np.ndarray) -> np.ndarray:
    """
    Given initial pose (xyz+wxyz+gripper) and a sequence of [T,7] deltas (xyz+axisangle+gripper),
    compute absolute future poses in global frame for each step.
    Args:
        initial_proprio: np.ndarray of shape [8], (xyz + quat, wxyz order, gripper)
        actions: np.ndarray of shape [T, 7], (delta_xyz + delta_axisangle + delta_gripper, all global frame, all relative-to-previous)
    Returns:
        poses: np.ndarray of shape [T, 8], (xyz + quat in wxyz order, global frame, gripper)
    """
    T = actions.shape[0]
    poses = np.zeros((T, 8), dtype=np.float64)
    # Start with initial pose
    pos = initial_proprio[:3].astype(np.float64).copy()
    quat_wxyz = initial_proprio[3:7].astype(np.float64)
    rot = Rotation.from_quat(quat_wxyz[[1, 2, 3, 0]])  # wxyz -> xyzw for scipy
    gripper = initial_proprio[7].astype(np.float64).copy()

    for i in range(T):
        d_pos = actions[i, :3]
        d_axisangle = actions[i, 3:6]
        # Accumulate position
        pos = pos + d_pos
        # Update orientation: compose dR after current quat (i.e., q_new = dR * q_prev)
        dR = Rotation.from_rotvec(d_axisangle)
        rot = dR * rot

        poses[i, :3] = pos
        poses[i, 3:7] = rot.as_quat()[[3, 0, 1, 2]]

        # Accumulate gripper
        gripper = gripper + actions[i, 6]
        poses[i, 7] = gripper
    return poses




def _png_b64(rgb):
    return base64.b64encode(cv2.imencode(".png", cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR))[1].tobytes()).decode()


def _arm_state(endpose, gripper):
    """官方 eval() 的单臂状态编码：xyz 换基 + 四元数换基换轴 -> [xyz, wxyz, gripper]"""
    xyz = np.asarray(endpose[:3], np.float64) @ BASE_COORD_XFORM.T
    quat = np.asarray(endpose[3:], np.float64)  # wxyz
    mat = Rotation.from_quat(quat[[1, 2, 3, 0]]).as_matrix()
    mat = BASE_COORD_XFORM @ mat @ EEF_AXES_XFORM
    quat = Rotation.from_matrix(mat).as_quat(canonical=True)[..., [3, 0, 1, 2]]
    return np.concatenate([xyz, quat, [float(gripper)]])


def _arm_actions(arm_state, deltas):
    """官方 eval() 的单臂动作还原：增量累加 -> 逆换基 -> [xyz, wxyz, gripper]"""
    poses = compute_future_poses(arm_state, deltas)
    grip = poses[:, 7:8]
    xyz = poses[:, :3] @ BASE_COORD_XFORM
    mat = Rotation.from_quat(poses[:, 3:7][..., [1, 2, 3, 0]]).as_matrix()
    mat = BASE_COORD_XFORM.T @ mat @ EEF_AXES_XFORM.T
    quat = Rotation.from_matrix(mat).as_quat(canonical=True)[..., [3, 0, 1, 2]]
    return np.concatenate([xyz, quat, grip], axis=1)


class XWAMClient:
    def __init__(self, base_url, action_length=32, cfg=0.0, env_rank=0):
        self.base_url = base_url.rstrip("/")
        self.server_url = f"{self.base_url}/v1/infer"
        self.action_length = int(action_length)
        self.cfg = float(cfg)
        self.env_rank = int(env_rank)
        self.rollout_id = -1                     # reset() 时 +1，对应官方 client 的 now_id
        self.stage_log_path = os.environ.get("STAGE_LOG") or None
        self.stages = {}
        self.infer_times = []
        print(f"[XWAM] server={self.server_url} action_length={self.action_length} cfg={self.cfg}")

    def get_action(self, instruction, observation, step_id):
        o = observation["observation"]
        images = {str(i + 1): _png_b64(o[c]["rgb"]) for i, c in enumerate(("head_camera", "left_camera", "right_camera"))}
        ep = observation["endpose"]
        left = _arm_state(ep["left_endpose"], ep["left_gripper"])
        right = _arm_state(ep["right_endpose"], ep["right_gripper"])
        state = np.concatenate([left, right])
        ret = requests.post(self.server_url, json={"observation": {"prompt": instruction, "images": images, "state": state.tolist()},
                                                   "meta": {"env_rank": self.env_rank, "rollout_id": self.rollout_id,
                                                            "step_id": int(step_id), "cfg": self.cfg}}, timeout=600)
        ret.raise_for_status()
        body = ret.json()
        if "infer_time" in body:
            self.infer_times.append(float(body["infer_time"]))
        deltas = np.asarray(body["actions"], dtype=np.float64)   # [Ta, 14]
        if not np.isfinite(deltas).all():
            raise RuntimeError("推理服务返回 NaN/inf 动作")
        actions = np.concatenate([_arm_actions(left, deltas[:, 0:7]), _arm_actions(right, deltas[:, 7:14])], axis=1)
        return actions[: min(len(actions), self.action_length)]

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
        self.rollout_id += 1
        try:
            requests.post(f"{self.base_url}/v1/reset", timeout=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("通知推理服务 /v1/reset 失败: %s", exc)


def get_model(usr_args):
    return XWAMClient(base_url=usr_args["base_url"], action_length=int(usr_args.get("action_length", 32)),
                      cfg=float(usr_args.get("cfg", 0.0)))


def eval(TASK_ENV, model, observation):
    if observation is None:
        observation = TASK_ENV.get_obs()
    bridge = getattr(TASK_ENV, "maybe_bridge_to_stage2", None)
    if bridge is not None:
        bridge()
    instruction = TASK_ENV.get_instruction()
    actions = model.get_action(instruction, observation, TASK_ENV.take_action_cnt)
    for action in actions:
        TASK_ENV.take_action(action, action_type="ee")
        if TASK_ENV.eval_success or TASK_ENV.take_action_cnt >= TASK_ENV.step_lim:
            break
    model.record_stage(TASK_ENV)
    return TASK_ENV.get_obs()


def reset_model(model):
    model.reset()
