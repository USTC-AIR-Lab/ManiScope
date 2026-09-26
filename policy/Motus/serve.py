"""Motus HTTP inference service using the official MotusPolicy loader, reset and prediction methods. Keep the upstream action/video chunking and preprocessing."""

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
sys.path.insert(0, os.path.dirname(POLICY_DIR))     # Resolve plugin-relative imports and prioritize plugin utils/models over repository-root modules.
sys.path.insert(0, POLICY_DIR)
os.chdir(POLICY_DIR)
import deploy_policy as mt


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
                raise ValueError(f"Expected 14-dimensional state, got {state.shape}")
            observation = {"observation": {"head_camera": {"rgb": head}, "left_camera": {"rgb": left},
                                           "right_camera": {"rgb": right}},
                           "joint_action": {"vector": state}}
            t0 = time.time()
            self.policy.set_instruction(str(obs.get("prompt", "")))
            self.policy.update_obs(observation)
            act = np.asarray(self.policy.get_action(), dtype=np.float64)
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
    logging.getLogger("deploy_policy").setLevel(logging.WARNING)   # Suppress repetitive instruction-set logging.
    t0 = time.time()
    Handler.policy = mt.get_model({"ckpt_setting": CKPT, "wan_path": WAN, "vlm_path": VLM,
                                   "log_dir": "/tmp/motus_logs", "task_name": "serve"})
    Handler.policy.save_images = False
    log.info("Policy loaded %.1fs ckpt=%s", time.time() - t0, CKPT)
    z = np.zeros((240, 320, 3), np.uint8)
    t0 = time.time()
    Handler.policy.set_instruction("warmup")
    Handler.policy.update_obs({"observation": {"head_camera": {"rgb": z}, "left_camera": {"rgb": z}, "right_camera": {"rgb": z}},
                               "joint_action": {"vector": np.zeros(14, np.float32)}})
    a = Handler.policy.get_action()
    mt.reset_model(Handler.policy)
    log.info("Warmup complete %.1fs chunk=%s", time.time() - t0, np.asarray(a).shape)
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("Listening :%d /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
