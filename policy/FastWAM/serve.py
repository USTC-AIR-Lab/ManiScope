"""FastWAM (yuanty/fastwam robotwin_uncond_3cam_384) 推理服务：/v1/infer 同 DM0.5 契约。

直接复用官方 experiments/robotwin/fastwam_policy/deploy_policy.py：
  * 用它的 get_model(usr_args) 建 WorldActionRobotWinPolicy（hydra: sim_robotwin + task robotwin_uncond_3cam_384_1e-4）
  * 每次请求把 3 路图 + 14 维关节角还原成 RoboTwin 观测 dict，调它的 _infer_action_chunk(observation, instruction)
    —— 拼接（head 320x256 + 两腕 160x128 并排 -> 384x320）、状态归一化、prompt 模板、反归一化全是官方代码
  * 返回整段 action_horizon(32) 的绝对关节角；官方 replan_steps=24 即每次只执行前 24 步再重推，
    本仓库通过 deploy_policy.yml 的 action_horizon: 24 让内核只执行前 24 个，等价
Wan2.2 侧车（VAE/T5/tokenizer）按 DiffSynth 约定放在 DIFFSYNTH_MODEL_BASE_PATH 下；DiT 权重来自 fastwam .pt
（skip_dit_load_from_pretrain=true）。
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [fastwam] %(message)s")
log = logging.getLogger("fastwam")

FW_ROOT = os.environ["FASTWAM_ROOT"]
CKPT = os.environ["FASTWAM_CKPT"]
STATS = os.environ["FASTWAM_STATS"]
TASK = os.environ.get("FASTWAM_TASK", "robotwin_uncond_3cam_384_1e-4")
PORT = int(os.environ.get("FASTWAM_PORT") or os.environ.get("PORT", "7995"))

sys.path.insert(0, os.path.join(FW_ROOT, "experiments", "robotwin", "fastwam_policy"))
sys.path.insert(0, FW_ROOT)
os.chdir(FW_ROOT)                                   # 官方插件用相对 PROJECT_ROOT 解析 configs/
import deploy_policy as fw  # noqa: E402  官方插件

# 官方模型 yaml 默认 redirect_common_files=true，把 T5/VAE 重定向到 DiffSynth-Studio 的 safetensors 转换版；
# 这里用的是 Wan-AI 原版 .pth（加载器按文件 hash 识别，原版 hash 在其注册表里），所以关掉重定向。
_orig_compose = fw._compose_sim_cfg


def _compose_no_redirect(sim_cfg_path, sim_cfg_name, sim_task):
    cfg = _orig_compose(sim_cfg_path, sim_cfg_name, sim_task)
    cfg.model.redirect_common_files = False
    return cfg


fw._compose_sim_cfg = _compose_no_redirect


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
        return self._json(200, {"ok": True, "calls": Handler.n_calls, "horizon": self.policy.action_horizon,
                                "replan_steps": self.policy.replan_steps})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        if self.path == "/v1/reset":
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
    Handler.policy = fw.get_model({"sim_cfg_name": "sim_robotwin", "sim_task": TASK, "ckpt_setting": CKPT,
                                   "dataset_stats_path": STATS, "device": "cuda", "seed": 0})
    log.info("policy 加载 %.1fs  ckpt=%s horizon=%d replan=%d steps=%d", time.time() - t0, CKPT,
             Handler.policy.action_horizon, Handler.policy.replan_steps, Handler.policy.num_inference_steps)
    z = np.zeros((240, 320, 3), np.uint8)
    t0 = time.time()
    Handler.policy._infer_action_chunk({"observation": {"head_camera": {"rgb": z}, "left_camera": {"rgb": z}, "right_camera": {"rgb": z}},
                                        "joint_action": {"vector": np.zeros(14, np.float32)}}, "warmup")
    log.info("预热完成 %.1fs", time.time() - t0)
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("监听 :%d  /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
