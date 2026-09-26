"""openpi inference service for pi0.5 and pi0. Exposes /v1/infer using observation prompt, three base64 PNG images, and a 14-dimensional joint state. PI_VARIANT chooses the backend; checkpoint preprocessing and output action conventions follow openpi. Warm up and serve on one thread to retain compiled CUDA-graph thread affinity."""

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

# PI_VARIANT selects pi0.5/PyTorch or pi0/JAX; create_trained_policy chooses weights from the checkpoint layout.

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
        repo_id="robotwin",                       # Only satisfies the configuration dataclass; inference does not load a dataset.
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
    log.info("Policy loaded %.1fs variant=%s ckpt=%s asset=%s horizon=%d adapt_to_pi=%s delta=%s",
             time.time() - t0, VARIANT, CKPT, ASSET_ID, ACTION_HORIZON, ADAPT_TO_PI, DELTA_ACTIONS)
    return policy


def decode_img(b64):
    im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    # openpi AlohaInputs expects CHW, so convert image axes before decoding.
    return np.ascontiguousarray(np.asarray(im, dtype=np.uint8).transpose(2, 0, 1))


class Handler(BaseHTTPRequestHandler):
    policy = None
    lock = threading.Lock()
    n_calls = 0

    def log_message(self, *a):                      # Suppress default access logs.
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
                raise ValueError(f"Expected 3 views (head,left,right), got {len(keys)}")
            high, left, right = (decode_img(imgs[k]) for k in keys)
            state = np.asarray(obs["state"], dtype=np.float32)
            if state.shape != (14,):
                raise ValueError(f"Expected 14-dimensional state, got {state.shape}")
            # Training repack_transforms do not run in inference; provide already-repacked shapes as in make_aloha_example.

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
                raise ValueError(f"Invalid action shape {actions.shape}")
            Handler.n_calls += 1
            if Handler.n_calls % 50 == 1:
                log.info("infer #%d %.3fs actions %s", Handler.n_calls, dt, actions.shape)
            return self._json(200, {"actions": actions.tolist(), "infer_time": dt})
        except Exception as e:                        # noqa: BLE001
            log.exception("Inference failed")
            return self._json(500, {"error": str(e)})

    def do_GET(self):
        if self.path in ("/", "/health"):
            return self._json(200, {"ok": True, "calls": Handler.n_calls})
        return self._json(404, {})


def main():
    Handler.policy = build_policy()
    # Warm up compilation and allocation before the first episode.
    z = lambda: np.zeros((3, 240, 320), np.uint8)  # noqa: E731  CHW
    dummy = {"images": {"cam_high": z(), "cam_left_wrist": z(), "cam_right_wrist": z()},
             "state": np.zeros(14, np.float32), "prompt": "warmup"}
    t0 = time.time()
    Handler.policy.infer(dummy)
    log.info("Warmup complete %.1fs", time.time() - t0)
    # Use one service thread: compiled CUDA graphs must remain on the warmup thread; each evaluation lane has its own service.

    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("Listening :%d /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
