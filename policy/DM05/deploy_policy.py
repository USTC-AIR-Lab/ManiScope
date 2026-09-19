"""DM0.5 (Dexmal DM05-robotwin2) 的 RoboTwin eval 插件。

单内核契约：script/eval_policy.py 通过 policy/<name>/ 找 get_model()/eval()/reset_model()。
这里是一个瘦 HTTP 客户端：把观测 POST 给 opendm 起的推理服务（/v1/infer），
收回 (chunk, 14) 的**绝对** qpos，逐步 take_action。DM0.5 的 chunk 是 50。

和 WLA 插件（policy/WLA/deploy_policy.py）保持**逐行对齐的行为**，这样两个策略走
同一个内核时评测协议完全一致：
  * eval() 里按 step_lim / eval_success 中断（不是把整块 50 步无脑执行完）；
  * 组合场景在阶段交接处调用 maybe_bridge_to_stage2()（若任务提供）；
  * NaN/inf 动作直接报错（喂进 sapien 会段错误，日志里什么都看不到）；
  * record_stage() 把每条 episode 走到的最高 stage 落盘，供 collect 对比。

协议字段来自 deploy_policy.yml / run_suite.sh 的 --overrides：
    base_url / cameras / action_horizon / action_mode / api_style / sampling
"""

import base64
import json
import logging
import os

import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)

# eval_policy.py 的 encode_obs 用 RoboTwin 相机名，DM0.5 服务按 use_cameras 顺序取图
_CAM_SOURCE = {
    "head_camera_rgb": "head_camera",
    "front_camera_rgb": "front_camera",
    "left_camera_rgb": "left_camera",
    "right_camera_rgb": "right_camera",
}


class DM05Client:
    def __init__(self, base_url, use_cameras, action_horizon=50,
                 action_mode="absolute", api_style="v1", sampling=None):
        self.base_url = base_url.rstrip("/")
        assert api_style in ("legacy", "v1"), "api_style 只支持 legacy / v1"
        self.api_style = api_style
        self.server_url = (f"{self.base_url}/process_frame" if api_style == "legacy"
                           else f"{self.base_url}/v1/infer")
        self.use_cameras = list(use_cameras)
        self.action_horizon = int(action_horizon)
        assert action_mode in ("absolute", "relative", "delta"), \
            "action_mode 只支持 absolute / relative / delta"
        self.action_mode = action_mode
        self.sampling = dict(sampling or {})
        # 组合泛化评测用：光看 success 分不出「第一步就没做到」和「做到一半」。
        # 任务提供 stage 时才有内容（见 envs/adjust_bottle_dustbin.py）。
        self.stage_log_path = os.environ.get("STAGE_LOG") or None
        self.stages = {}
        print(f"[DM05] server={self.server_url} cameras={self.use_cameras} "
              f"horizon={self.action_horizon} mode={self.action_mode}"
              + (f", stage log -> {self.stage_log_path}" if self.stage_log_path else ""))

    # ---- 与推理服务通信 --------------------------------------------------- #
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
        raw = ret.json().get("actions")
        if raw is None:
            raise RuntimeError("v1 推理服务返回缺少 actions")
        return raw

    def _infer_legacy(self, instruction, encoded_images, state):
        data = {"text": instruction, "temperature": 1.0}
        if state is not None:
            data["states"] = json.dumps(np.asarray(state, dtype=np.float32).tolist())
        ret = requests.post(self.server_url, data=data,
                            files=[("image", img) for img in encoded_images])
        ret.raise_for_status()
        raw = ret.json().get("response")
        if raw is None:
            raise RuntimeError("legacy 推理服务返回缺少 response")
        return raw

    def get_action(self, instruction, rgbs, state=None):
        encoded = [cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))[1].tobytes()
                   for rgb in rgbs]
        raw = (self._infer_v1(instruction, encoded, state) if self.api_style == "v1"
               else self._infer_legacy(instruction, encoded, state))
        chunk = np.asarray(raw, dtype=np.float64)
        if self.action_horizon > 0 and len(chunk) > self.action_horizon:
            chunk = chunk[: self.action_horizon]
        if not np.isfinite(chunk).all():
            raise RuntimeError("推理服务返回 NaN/inf 动作 —— 多半是 checkpoint 坏了，换一个")
        return chunk

    # ---- 相对/增量 -> 绝对（DM0.5 用 absolute，一般不走这两条） -------------- #
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

    # ---- stage 记录（与 WLA 插件同格式） ---------------------------------- #
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
        if self.api_style != "v1":
            return
        try:
            requests.post(f"{self.base_url}/v1/reset", timeout=5)
        except Exception as exc:
            logger.warning("通知推理服务 /v1/reset 失败: %s", exc)


# --------------------------------------------------------------------------- #
# RoboTwin 单内核接口
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
    return DM05Client(
        base_url=usr_args["base_url"],
        use_cameras=cams,
        action_horizon=int(usr_args.get("action_horizon", 50)),
        action_mode=usr_args.get("action_mode", "absolute"),
        api_style=usr_args.get("api_style", "v1"),
        sampling=usr_args.get("sampling", None),
    )


def eval(TASK_ENV, model, observation):
    if observation is None:                      # skip_get_obs_within_replan 时可能为 None
        observation = TASK_ENV.get_obs()
    # 组合泛化场景可以在阶段交接处插一段脚本动作（同 WLA 插件）。别的任务没有此方法。
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
