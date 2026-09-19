"""Motus (motus-robotics/Motus_robotwin2) 推理服务：/v1/infer 同 DM0.5 契约。

直接复用官方 inference/robotwin/Motus/deploy_policy.py 的 MotusPolicy：
  * get_model(usr_args)：ckpt 目录（mp_rank_00_model_states.pt）+ Wan2.2 侧车（config / VAE / umt5 T5）+ Qwen3-VL-2B-Instruct 处理器
    （权重来自 ckpt，load_pretrained_backbones=False），配置 utils/robotwin.yml（384x320，10 步去噪）
  * 每次请求 = 官方 eval() 的一次循环：set_instruction -> update_obs(观测 dict：三视角拼接 head 320x240 + 两腕 160x120，
    resize_with_padding 到 384x320；14 维关节角) -> get_action() -> 整段预测动作（绝对 qpos）
  * 官方每次把整段 chunk 执行完再重推，本仓库 deploy_policy.yml action_horizon=0（不截断）等价；无跨步状态
  * 关掉官方每步存预测帧网格图（save_images=False，纯日志功能，不影响动作）
"""

import base64
import io
import json
import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [motus] %(message)s")
log = logging.getLogger("motus")

MOTUS_ROOT = os.environ["MOTUS_ROOT"]
POLICY_DIR = os.path.join(MOTUS_ROOT, "inference", "robotwin", "Motus")
CKPT = os.environ["MOTUS_CKPT"]
WAN = os.environ["MOTUS_WAN"]
VLM = os.environ["MOTUS_VLM"]
PORT = int(os.environ.get("MOTUS_PORT") or os.environ.get("PORT", "8000"))

sys.path.insert(0, MOTUS_ROOT)
sys.path.insert(0, os.path.dirname(POLICY_DIR))     # 官方插件按 RoboTwin/policy/Motus 布局用包内相对导入
sys.path.insert(0, POLICY_DIR)                      # 最前：utils/models 要解析到插件目录，不是仓库根的 utils/
os.chdir(POLICY_DIR)
import deploy_policy as mt  # noqa: E402  官方插件


def decode_img(b64):
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"), dtype=np.uint8)


class Handler(BaseHTTPRequestHandler):
    policy = None
    n_calls = 0

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        return self._json(200, {"ok": True, "calls": Handler.n_calls})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        if self.path == "/v1/reset":
            mt.reset_model(self.policy)
            return self._json(200, {"ok": True})
        if self.path != "/v1/infer":
            return self._json(404, {"error": "unknown path"})
        try:
            obs = json.loads(raw)["observation"]
            imgs = obs["images"]
            head, left, right = (decode_img(imgs[k]) for k in ("1", "2", "3"))
            state = np.asarray(obs["state"], dtype=np.float32)
            if state.shape != (14,):
                raise ValueError(f"state 应为 14 维，收到 {state.shape}")
            observation = {"observation": {"head_camera": {"rgb": head}, "left_camera": {"rgb": left},
                                           "right_camera": {"rgb": right}},
                           "joint_action": {"vector": state}}
            t0 = time.time()
            self.policy.set_instruction(str(obs.get("prompt", "")))
            self.policy.update_obs(observation)
            act = np.asarray(self.policy.get_action(), dtype=np.float64)
            dt = time.time() - t0
            if act.ndim != 2 or act.shape[1] != 14 or not np.isfinite(act).all():
                raise ValueError(f"动作异常 shape={act.shape}")
            Handler.n_calls += 1
            if Handler.n_calls % 50 == 1:
                log.info("infer #%d %.3fs actions %s", Handler.n_calls, dt, act.shape)
            return self._json(200, {"actions": act.tolist(), "infer_time": dt})
        except Exception as e:  # noqa: BLE001
            log.exception("infer 失败")
            return self._json(500, {"error": str(e)})


def main():
    logging.getLogger("deploy_policy").setLevel(logging.WARNING)   # 官方每步打 Instruction set，太吵
    t0 = time.time()
    Handler.policy = mt.get_model({"ckpt_setting": CKPT, "wan_path": WAN, "vlm_path": VLM,
                                   "log_dir": "/tmp/motus_logs", "task_name": "serve"})
    Handler.policy.save_images = False
    log.info("policy 加载 %.1fs  ckpt=%s", time.time() - t0, CKPT)
    z = np.zeros((240, 320, 3), np.uint8)
    t0 = time.time()
    Handler.policy.set_instruction("warmup")
    Handler.policy.update_obs({"observation": {"head_camera": {"rgb": z}, "left_camera": {"rgb": z}, "right_camera": {"rgb": z}},
                               "joint_action": {"vector": np.zeros(14, np.float32)}})
    a = Handler.policy.get_action()
    mt.reset_model(Handler.policy)
    log.info("预热完成 %.1fs  chunk=%s", time.time() - t0, np.asarray(a).shape)
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("监听 :%d  /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
