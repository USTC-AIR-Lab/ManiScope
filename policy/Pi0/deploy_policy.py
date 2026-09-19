"""pi0 (yuffish/robotwin-pi0_aloha-agilex_clean-50) 的 RoboTwin eval 插件——与 Pi05 插件完全同构，仅 chunk=50、端口不同。

单内核契约：script/eval_policy.py 通过 policy/<name>/ 找 get_model()/eval()/reset_model()。
和 policy/DM05/deploy_policy.py **逐行对齐**——两者走的是同一套 openpi `/v1/infer` JSON 协议
（见 DM05 插件里 api_style="v1" 的注释：「Pi0/DM0 这类」），所以这里只是换了服务端和 chunk 长度。
行为保持一致是为了让跨策略成绩可比：eval() 里按 step_lim / eval_success 中断、
组合场景在阶段交接处调 maybe_bridge_to_stage2()、NaN/inf 动作直接报错、record_stage() 落盘。

checkpoint 要点（来自 motus-robotics/pi0.5_robotwin2 的 README 与 norm_stats）:
  * pi0.5 base 在 RoboTwin 2.0 全 50 任务上微调（clean 50/任务 + randomized 500/任务）
  * Pi0Config(pi05=True, action_horizon=50) —— 所以 chunk 是 32，不是 DM0.5 的 50
  * norm_stats 的 state / actions 均为 14 维 = aloha-agilex 双臂 6 关节 + 2 夹爪
  * 输出绝对 qpos，不走 relative/delta
"""

import base64
import json
import logging
import os

import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)

# eval_policy.py 的 encode_obs 用 RoboTwin 相机名
_CAM_SOURCE = {
    "head_camera_rgb": "head_camera",
    "front_camera_rgb": "front_camera",
    "left_camera_rgb": "left_camera",
    "right_camera_rgb": "right_camera",
}


class Pi0Client:
    def __init__(self, base_url, use_cameras, action_horizon=50,
                 action_mode="absolute", api_style="v1", sampling=None):
        self.base_url = base_url.rstrip("/")
        assert api_style == "v1", "Pi0.5 服务只提供 /v1/infer"
        self.api_style = api_style
        self.server_url = f"{self.base_url}/v1/infer"
        self.use_cameras = list(use_cameras)
        self.action_horizon = int(action_horizon)
        assert action_mode in ("absolute", "relative", "delta"), \
            "action_mode 只支持 absolute / relative / delta"
        self.action_mode = action_mode
        self.sampling = dict(sampling or {})
        self.stage_log_path = os.environ.get("STAGE_LOG") or None
        self.stages = {}
        # 服务端返回的纯模型推理耗时；内核（打过延迟补丁后）每条 episode 清空并落盘到 _latency.txt
        self.infer_times = []
        print(f"[Pi0] server={self.server_url} cameras={self.use_cameras} "
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
            raise RuntimeError("v1 推理服务返回缺少 actions")
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
            raise RuntimeError("推理服务返回 NaN/inf 动作 —— 多半是 checkpoint 坏了，换一个")
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
    return Pi0Client(
        base_url=usr_args["base_url"],
        use_cameras=cams,
        action_horizon=int(usr_args.get("action_horizon", 50)),
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
