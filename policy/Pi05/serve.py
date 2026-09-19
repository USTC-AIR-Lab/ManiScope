"""Pi0.5 (motus-robotics/pi0.5_robotwin2) 推理服务：把 openpi 的 policy 包成和 DM0.5 同款的 /v1/infer。

请求 (JSON):  {"observation": {"prompt": str, "images": {"1": b64png, "2": ..., "3": ...}, "state": [14]},
               "sampling": {...}}          # 图顺序 = deploy_policy.yml 的 cameras: head, left, right
响应 (JSON):  {"actions": [[14] * action_horizon]}   # 绝对关节角

训练配置来自 checkpoint README（motus 用的 TrainConfig），这里逐项复刻，否则动作解码会错：
  * Pi0Config(pi05=True, action_horizon=32)
  * LeRobotAlohaDataConfig(adapt_to_pi=True, use_delta_joint_actions=True)
    —— openpi 的 Policy 在推理时自动做逆变换，所以本服务输出的是绝对 Aloha 关节角，不需要再处理
  * norm_stats 在 <ckpt>/assets/<asset_id>/norm_stats.json，asset_id 取下载到的目录名

用 openpi 的 .venv 跑：
  PI05_CKPT=... PI05_PORT=7893 CUDA_VISIBLE_DEVICES=0 .venv/bin/python policy/Pi05/serve.py
"""

import base64
import io
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [pi05] %(message)s")
log = logging.getLogger("pi05")

# 同一份服务同时供 pi0.5（PyTorch）和 pi0（JAX/orbax）用：变体由 PI_VARIANT 决定，
# create_trained_policy 见到 model.safetensors 走 PyTorch，否则走 JAX params/。
VARIANT = os.environ.get("PI_VARIANT", "pi05")                      # pi05 | pi0
CKPT = os.environ.get("PI_CKPT") or os.environ["PI05_CKPT"]
PORT = int(os.environ.get("PI_PORT") or os.environ.get("PI05_PORT", "7893"))
ASSET_ID = os.environ.get("PI_ASSET_ID") or os.environ.get("PI05_ASSET_ID", "pi0.5_clean_randomize_joint_training")
ACTION_HORIZON = int(os.environ.get("PI_HORIZON") or os.environ.get("PI05_HORIZON", "32" if VARIANT == "pi05" else "50"))
ADAPT_TO_PI = os.environ.get("PI_ADAPT_TO_PI", "1") == "1"
DELTA_ACTIONS = os.environ.get("PI_DELTA_ACTIONS", "1") == "1"


def build_policy():
    from openpi.models import pi0_config
    from openpi.policies import policy_config as _policy_config
    from openpi.training import config as _config
    import openpi.transforms as _transforms

    data = _config.LeRobotAlohaDataConfig(
        repo_id="robotwin",                       # 推理不读数据集，只用来满足 dataclass
        assets=_config.AssetsConfig(asset_id=ASSET_ID),
        adapt_to_pi=ADAPT_TO_PI,
        use_delta_joint_actions=DELTA_ACTIONS,
        repack_transforms=_transforms.Group(inputs=[_transforms.RepackTransform({
            "images": {"cam_high": "high_image",
                       "cam_left_wrist": "left_wrist_image",
                       "cam_right_wrist": "right_wrist_image"},
            "state": "state", "actions": "actions", "prompt": "prompt"})]),
    )
    train_config = _config.TrainConfig(
        name="%s_robotwin_infer" % VARIANT,
        model=pi0_config.Pi0Config(pi05=(VARIANT == "pi05"), action_horizon=ACTION_HORIZON),
        data=data,
    )
    t0 = time.time()
    policy = _policy_config.create_trained_policy(train_config, CKPT)
    log.info("policy 加载完成 %.1fs  variant=%s ckpt=%s asset=%s horizon=%d adapt_to_pi=%s delta=%s",
             time.time() - t0, VARIANT, CKPT, ASSET_ID, ACTION_HORIZON, ADAPT_TO_PI, DELTA_ACTIONS)
    return policy


def decode_img(b64):
    im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    # openpi 的 AlohaInputs 期待 CHW（_decode_aloha 里无条件 "c h w -> h w c"），所以这里转成 CHW
    return np.ascontiguousarray(np.asarray(im, dtype=np.uint8).transpose(2, 0, 1))


class Handler(BaseHTTPRequestHandler):
    policy = None
    lock = threading.Lock()
    n_calls = 0

    def log_message(self, *a):                      # 静默默认访问日志
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        if self.path == "/v1/reset":
            return self._json(200, {"ok": True})
        if self.path != "/v1/infer":
            return self._json(404, {"error": "unknown path"})
        try:
            req = json.loads(raw)
            obs = req["observation"]
            imgs = obs["images"]
            keys = sorted(imgs.keys(), key=lambda k: int(k))
            if len(keys) != 3:
                raise ValueError(f"需要 3 路图 (head,left,right)，收到 {len(keys)}")
            high, left, right = (decode_img(imgs[k]) for k in keys)
            state = np.asarray(obs["state"], dtype=np.float32)
            if state.shape != (14,):
                raise ValueError(f"state 应为 14 维，收到 {state.shape}")
            # repack_transforms 只在训练读数据集时生效，推理要直接给 repack 之后的形状
            # （同 openpi aloha_policy.make_aloha_example）
            example = {
                "images": {"cam_high": high, "cam_left_wrist": left, "cam_right_wrist": right},
                "state": state, "prompt": obs.get("prompt", ""),
            }
            t0 = time.time()
            with self.lock:
                out = self.policy.infer(example)
            dt = time.time() - t0
            actions = np.asarray(out["actions"], dtype=np.float64)
            if actions.ndim != 2 or actions.shape[1] != 14:
                raise ValueError(f"动作形状异常 {actions.shape}")
            Handler.n_calls += 1
            if Handler.n_calls % 50 == 1:
                log.info("infer #%d %.3fs actions %s", Handler.n_calls, dt, actions.shape)
            return self._json(200, {"actions": actions.tolist(), "infer_time": dt})
        except Exception as e:                        # noqa: BLE001
            log.exception("infer 失败")
            return self._json(500, {"error": str(e)})

    def do_GET(self):
        if self.path in ("/", "/health"):
            return self._json(200, {"ok": True, "calls": Handler.n_calls})
        return self._json(404, {})


def main():
    Handler.policy = build_policy()
    # 预热一次，把 torch 编译/显存分配吃掉，免得第一条 episode 超时
    z = lambda: np.zeros((3, 240, 320), np.uint8)  # noqa: E731  CHW
    dummy = {"images": {"cam_high": z(), "cam_left_wrist": z(), "cam_right_wrist": z()},
             "state": np.zeros(14, np.float32), "prompt": "warmup"}
    t0 = time.time()
    Handler.policy.infer(dummy)
    log.info("预热完成 %.1fs", time.time() - t0)
    # 必须单线程：torch.compile 的 cudagraph 在预热线程之外重新录制会报
    # CUDNN_STATUS_INTERNAL_ERROR_DEVICE_ALLOCATION_FAILED；每条车道独占一个服务，无并发需求
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("监听 :%d  /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
