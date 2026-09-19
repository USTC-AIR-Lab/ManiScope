"""GalaxeaVLA G0.5 (OpenGalaxea/G05 g05-robotwin20) 推理服务：/v1/infer 同 DM0.5 契约。

直接复用官方 experiments/robotwin/galaxeafm_policy/deploy_policy.py：
  * get_model(usr_args) 建 GalaxeaFMRobotWinPolicy（hydra: sim_robotwin.yaml + 任务 robotwin；
    模型/tokenizer 架构取自 ckpt 自带 .hydra/config.yaml，权重 model_state_dict.pt，HF processor 与
    action_tokenizer 按官方 checkpoints/ 布局用软链接指到 ckpts/g05_robotwin20）
  * 每次请求把 3 路图 + 14 维关节角还原成 RoboTwin 观测 dict，调官方 _infer_action_chunk(observation, instruction)
    —— 图像 CHW/历史帧复制、状态切分、prompt、自回归动作 token 解码、反归一化全是官方代码；无跨步状态
  * 官方 replan_steps=8：每次只执行 chunk 前 8 步再重推；本仓库通过 deploy_policy.yml action_horizon: 8 让内核等价执行
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [g05] %(message)s")
log = logging.getLogger("g05")

G05_ROOT = os.environ["G05_ROOT"]
CKPT = os.environ.get("G05_CKPT", os.path.join(G05_ROOT, "checkpoints/g05-robotwin20/checkpoints/model_state_dict.pt"))
STATS = os.environ.get("G05_STATS", os.path.join(G05_ROOT, "checkpoints/g05-robotwin20/dataset_stats.json"))
TASK = os.environ.get("G05_TASK", "robotwin")
PORT = int(os.environ.get("G05_PORT") or os.environ.get("PORT", "7999"))

sys.path.insert(0, os.path.join(G05_ROOT, "experiments", "robotwin", "galaxeafm_policy"))
sys.path.insert(0, os.path.join(G05_ROOT, "src"))
sys.path.insert(0, G05_ROOT)
os.chdir(G05_ROOT)                                   # 官方插件用相对 PROJECT_ROOT 解析 configs/ 与 checkpoints/
import deploy_policy as g05  # noqa: E402  官方插件


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
        return self._json(200, {"ok": True, "calls": Handler.n_calls, "horizon": self.policy.exec_action_horizon,
                                "replan_steps": self.policy.replan_steps})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        if self.path == "/v1/reset":
            self.policy.reset()
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
            act = np.asarray(self.policy._infer_action_chunk(observation, str(obs.get("prompt", ""))), dtype=np.float64)
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
    t0 = time.time()
    Handler.policy = g05.get_model({"sim_cfg_name": "sim_robotwin.yaml", "sim_task": TASK, "ckpt_setting": CKPT,
                                    "dataset_stats_path": STATS, "device": "cuda", "seed": 0})
    p = Handler.policy
    log.info("policy 加载 %.1fs  ckpt=%s horizon=%d replan=%d", time.time() - t0, CKPT,
             p.exec_action_horizon, p.replan_steps)
    z = np.zeros((240, 320, 3), np.uint8)
    t0 = time.time()
    p._infer_action_chunk({"observation": {"head_camera": {"rgb": z}, "left_camera": {"rgb": z}, "right_camera": {"rgb": z}},
                           "joint_action": {"vector": np.zeros(14, np.float32)}}, "warmup")
    log.info("预热完成 %.1fs", time.time() - t0)
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("监听 :%d  /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
