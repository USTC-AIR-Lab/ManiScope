"""AHA-WAM HTTP inference service using the upstream robotwin policy loader and action queue. Preserve upstream normalization, chunk size and video/action inference settings; return the complete queue refill as a chunk."""

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
os.chdir(AW_ROOT)                                   # Resolve official plugin configs relative to PROJECT_ROOT.
import deploy_policy as aw

# Disable common-file redirection when using original Wan-AI .pth weights rather than converted safetensors.

_orig_compose = aw._compose_sim_cfg


def _compose_no_redirect(sim_cfg_path, sim_cfg_name, sim_task):
    cfg = _orig_compose(sim_cfg_path, sim_cfg_name, sim_task)
    cfg.model.redirect_common_files = False
    return cfg


aw._compose_sim_cfg = _compose_no_redirect


def decode_img(b64):
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"), dtype=np.uint8)


def infer_chunk(policy, observation, instruction):
    """Return the upstream queue-empty refill as a complete action chunk."""
    assert not policy.pending_actions, "Action queue is not empty; execute the complete chunk before requesting again"
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
                raise ValueError(f"Expected 14-dimensional state, got {state.shape}")
            observation = {"observation": {"head_camera": {"rgb": head}, "left_camera": {"rgb": left},
                                           "right_camera": {"rgb": right}},
                           "joint_action": {"vector": state}}
            t0 = time.time()
            act = np.asarray(infer_chunk(self.policy, observation, str(obs.get("prompt", ""))), dtype=np.float64)
            dt = time.time() - t0
            if act.ndim != 2 or act.shape[1] != 14 or not np.isfinite(act).all():
                raise ValueError(f"Invalid action shape={act.shape}")
            Handler.n_calls += 1
            if Handler.n_calls % 50 == 1:
                log.info("infer #%d %.3fs actions %s", Handler.n_calls, dt, act.shape)
            return self._json(200, {"actions": act.tolist(), "infer_time": dt})
        except Exception as e:  # noqa: BLE001
            log.exception("Inference failed")
            return self._json(500, {"error": str(e)})


def main():
    t0 = time.time()
    Handler.policy = aw.get_model({"sim_cfg_name": "sim_robotwin", "sim_task": TASK, "ckpt_setting": CKPT,
                                   "dataset_stats_path": STATS, "device": "cuda", "seed": 0})
    p = Handler.policy
    log.info("Policy loaded %.1fs ckpt=%s horizon=%d chunk=%d prefill_every=%d steps=%d", time.time() - t0, CKPT,
             p.action_horizon, int(p.model.action_chunk_size), p.chunks_per_video_prefill, p.num_inference_steps)
    z = np.zeros((240, 320, 3), np.uint8)
    t0 = time.time()
    for _ in range(3):
        infer_chunk(p, {"observation": {"head_camera": {"rgb": z}, "left_camera": {"rgb": z}, "right_camera": {"rgb": z}},
                        "joint_action": {"vector": np.zeros(14, np.float32)}}, "warmup")
    p.reset()
    log.info("Warmup complete %.1fs", time.time() - t0)
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("Listening :%d /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
