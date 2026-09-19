"""AHA-WAM (SereneC/AHA-WAM-RoboTwin2.0, task robotwin_ahawam) 推理服务：/v1/infer 同 DM0.5 契约。

直接复用官方 experiments/robotwin/ahawam_policy/deploy_policy.py：
  * 用它的 get_model(usr_args) 建 WorldActionRobotWinPolicy（hydra: sim_robotwin + task robotwin_ahawam）
  * 官方 step()：pending_actions 为空时才取观测、调 _fill_action_queue 生成一个 action_chunk_size(16) 的 chunk，
    然后逐步 popleft 执行；视频 DiT 每 chunks_per_video_prefill(2) 个 chunk 用新观测 prefill 一次，
    历史帧/推理状态（_inference_state, history）都在 policy 对象内部维护 —— 服务端保持同一对象即可
  * 本服务每次请求 = 官方"队列空 -> 取观测 -> 填一个 chunk"，把 16 步整段返回；内核执行完 16 步再带新观测请求，
    与官方逐步 step 的观测取样点完全一致
  * /v1/reset -> policy.reset()（清队列 + reset_history），每个 episode 开始前由内核调用
Wan2.2 侧车（VAE/T5/tokenizer）按 DiffSynth 约定放在 DIFFSYNTH_MODEL_BASE_PATH 下；DiT/ActionDiT 权重来自 .pt
（skip_dit_load_from_pretrain 由官方 load_checkpoint 处理）。
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ahawam] %(message)s")
log = logging.getLogger("ahawam")

AW_ROOT = os.environ["AHAWAM_ROOT"]
CKPT = os.environ["AHAWAM_CKPT"]
STATS = os.environ["AHAWAM_STATS"]
TASK = os.environ.get("AHAWAM_TASK", "robotwin_ahawam")
PORT = int(os.environ.get("AHAWAM_PORT") or os.environ.get("PORT", "7996"))

sys.path.insert(0, os.path.join(AW_ROOT, "experiments", "robotwin", "ahawam_policy"))
sys.path.insert(0, os.path.join(AW_ROOT, "src"))
sys.path.insert(0, AW_ROOT)
os.chdir(AW_ROOT)                                   # 官方插件用相对 PROJECT_ROOT 解析 configs/
import deploy_policy as aw  # noqa: E402  官方插件

# 官方模型 yaml 默认 redirect_common_files=true，把 T5/VAE 重定向到 DiffSynth-Studio 的 safetensors 转换版；
# 这里用的是 Wan-AI 原版 .pth（与 FastWAM 共用同一侧车），所以关掉重定向。
_orig_compose = aw._compose_sim_cfg


def _compose_no_redirect(sim_cfg_path, sim_cfg_name, sim_task):
    cfg = _orig_compose(sim_cfg_path, sim_cfg_name, sim_task)
    cfg.model.redirect_common_files = False
    return cfg


aw._compose_sim_cfg = _compose_no_redirect


def decode_img(b64):
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"), dtype=np.uint8)


def infer_chunk(policy, observation, instruction):
    """官方 step() 的"队列空 -> 填队列"部分，整段取出返回。"""
    assert not policy.pending_actions, "队列非空：内核应执行完整个 chunk 再请求"
    policy._fill_action_queue(observation=observation, instruction=instruction)
    acts = np.stack(list(policy.pending_actions), axis=0)
    policy.pending_actions.clear()
    policy.step_count += len(acts)
    return acts


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
        return self._json(200, {"ok": True, "calls": Handler.n_calls, "chunk": int(self.policy.model.action_chunk_size),
                                "chunks_per_video_prefill": self.policy.chunks_per_video_prefill,
                                "episodes": self.policy.episode_count})

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
            act = np.asarray(infer_chunk(self.policy, observation, str(obs.get("prompt", ""))), dtype=np.float64)
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
    Handler.policy = aw.get_model({"sim_cfg_name": "sim_robotwin", "sim_task": TASK, "ckpt_setting": CKPT,
                                   "dataset_stats_path": STATS, "device": "cuda", "seed": 0})
    p = Handler.policy
    log.info("policy 加载 %.1fs  ckpt=%s horizon=%d chunk=%d prefill_every=%d steps=%d", time.time() - t0, CKPT,
             p.action_horizon, int(p.model.action_chunk_size), p.chunks_per_video_prefill, p.num_inference_steps)
    z = np.zeros((240, 320, 3), np.uint8)
    t0 = time.time()
    for _ in range(3):
        infer_chunk(p, {"observation": {"head_camera": {"rgb": z}, "left_camera": {"rgb": z}, "right_camera": {"rgb": z}},
                        "joint_action": {"vector": np.zeros(14, np.float32)}}, "warmup")
    p.reset()
    log.info("预热完成 %.1fs", time.time() - t0)
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("监听 :%d  /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
