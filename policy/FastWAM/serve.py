"""FastWAM HTTP inference service using the upstream RoboTwin policy loader and step routine. Preserve checkpoint configuration, replanning interval and enabled inference modules."""

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
os.chdir(FW_ROOT)                                   # Resolve official plugin configs relative to PROJECT_ROOT.
import deploy_policy as fw

# Disable common-file redirection when using original Wan-AI .pth weights rather than converted safetensors.
# Use original Wan-AI .pth weights recognized by the loader hash registry; disable redirection.
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
                raise ValueError(f"Expected 14-dimensional state, got {state.shape}")
            observation = {"observation": {"head_camera": {"rgb": head}, "left_camera": {"rgb": left},
                                           "right_camera": {"rgb": right}},
                           "joint_action": {"vector": state}}
            t0 = time.time()
            act = np.asarray(self.policy._infer_action_chunk(observation, str(obs.get("prompt", ""))), dtype=np.float64)
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
    Handler.policy = fw.get_model({"sim_cfg_name": "sim_robotwin", "sim_task": TASK, "ckpt_setting": CKPT,
                                   "dataset_stats_path": STATS, "device": "cuda", "seed": 0})
    log.info("Policy loaded %.1fs ckpt=%s horizon=%d replan=%d steps=%d", time.time() - t0, CKPT,
             Handler.policy.action_horizon, Handler.policy.replan_steps, Handler.policy.num_inference_steps)
    z = np.zeros((240, 320, 3), np.uint8)
    t0 = time.time()
    Handler.policy._infer_action_chunk({"observation": {"head_camera": {"rgb": z}, "left_camera": {"rgb": z}, "right_camera": {"rgb": z}},
                                        "joint_action": {"vector": np.zeros(14, np.float32)}}, "warmup")
    log.info("Warmup complete %.1fs", time.time() - t0)
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("Listening :%d /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
