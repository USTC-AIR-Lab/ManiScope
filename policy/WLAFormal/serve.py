"""Public WLA HTTP inference service following WLARoboTwinPolicy. Preserve configured observation history, public action/state normalization, action chunking and enabled inference modules; do not substitute an internal training checkpoint."""

import base64
import io
import json
import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision.transforms.functional import to_tensor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [wla-formal] %(message)s")
log = logging.getLogger("wla")

WLA_ROOT = Path(os.environ["WLA_ROOT"])
MODEL_ID = os.environ["WLA_MODEL_ID"]
NORM_FILE = os.environ.get("WLA_NORM_FILE", str(WLA_ROOT / "configs" / "norm_stats.json"))
UNNORM_KEY = os.environ.get("WLA_UNNORM_KEY", "robotwin_all_eef")
PORT = int(os.environ.get("WLA_PORT") or os.environ.get("PORT", "7980"))
MAX_STATE_DIM = int(os.environ.get("WLA_MAX_STATE_DIM", "16"))
ACTION_DIM = int(os.environ.get("WLA_ACTION_DIM", "16"))
PRIMARY = int(os.environ.get("WLA_PRIMARY_IMAGE_SIZE", "256"))
AUX = int(os.environ.get("WLA_AUX_IMAGE_SIZE", "256"))
TARGET_IMAGE_SIZE = int(os.environ.get("WLA_TARGET_IMAGE_SIZE", "512"))
VAE_F = int(os.environ.get("WLA_VAE_F", "32"))
DTYPE = getattr(torch, os.environ.get("WLA_DTYPE", "bfloat16"))

sys.path.insert(0, str(WLA_ROOT))
from models.wla import WLA  # noqa: E402
from utils.transforms import _make_transform, normalize_and_pad, unnormalize_and_unpad  # noqa: E402

class Policy:
    def __init__(self):
        with open(NORM_FILE, "r", encoding="utf-8") as f:
            ns = json.load(f)
        if UNNORM_KEY not in ns:
            raise KeyError(f"norm_stats has no {UNNORM_KEY}; available keys: {sorted(ns)}")
        self.norm_stats = ns[UNNORM_KEY]
        t0 = time.time()
        self.model = WLA.from_pretrained(MODEL_ID, input_size=TARGET_IMAGE_SIZE // VAE_F)
        self.history_obs_step = int(getattr(self.model.config, "history_obs_step", 8))
        self.chunk = int(getattr(self.model.config, "chunk_size", 32))
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self.model.to(device=device, dtype=DTYPE)      # Use one dtype for the full model, matching upstream.
        self.model.eval()
        self.primary_tf = _make_transform(PRIMARY)
        self.aux_tf = _make_transform(AUX)
        log.info("Model loaded %.1fs model=%s history_obs_step=%d chunk=%d unnorm=%s dims=%d/%d",
                 time.time() - t0, MODEL_ID, self.history_obs_step, self.chunk, UNNORM_KEY, MAX_STATE_DIM, ACTION_DIM)

    @torch.inference_mode()
    def infer(self, hist, head, left, right, state, instruction):
        input_images = [[self.aux_tf(to_tensor(hist)), self.primary_tf(to_tensor(head)),
                         self.aux_tf(to_tensor(left)), self.aux_tf(to_tensor(right))]]
        states = torch.tensor(np.asarray(state, dtype=np.float32).reshape(-1))
        states, _ = normalize_and_pad(states, self.norm_stats["observation.state"], MAX_STATE_DIM)
        pr = next(self.model.model.action_expert.parameters())
        states = states.unsqueeze(0).to(dtype=pr.dtype, device=pr.device)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=pr.device.type == "cuda"):
            actions = self.model.sample_actions(caption=instruction, input_images=input_images,
                                                num_images_per_prompt=1, states=states)
        actions = unnormalize_and_unpad(torch.as_tensor(actions), self.norm_stats["action"], ACTION_DIM)
        if ACTION_DIM == 16:                                       # Normalize both end-effector quaternions, matching upstream postprocessing.
            lq, rq = actions[:, 3:7], actions[:, 11:15]
            actions = torch.cat([actions[:, :3], lq / torch.linalg.norm(lq, dim=1, keepdim=True),
                                 actions[:, 7:11], rq / torch.linalg.norm(rq, dim=1, keepdim=True),
                                 actions[:, 15:16]], dim=1)
        return actions.detach().float().cpu().numpy()


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
        return self._json(200, {"ok": True, "calls": Handler.n_calls, "chunk": self.policy.chunk,
                                "history_obs_step": self.policy.history_obs_step})

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
            hist = decode_img(imgs["0"]) if imgs.get("0") else head
            state = np.asarray(obs["state"], dtype=np.float32)
            if state.shape != (MAX_STATE_DIM,):
                raise ValueError(f"Expected {MAX_STATE_DIM}-dimensional state, got {state.shape}")
            t0 = time.time()
            act = self.policy.infer(hist, head, left, right, state, str(obs.get("prompt", "")))
            dt = time.time() - t0
            if act.ndim != 2 or act.shape[1] != ACTION_DIM or not np.isfinite(act).all():
                raise ValueError(f"Invalid action shape={act.shape}")
            Handler.n_calls += 1
            if Handler.n_calls % 50 == 1:
                log.info("infer #%d %.3fs actions %s", Handler.n_calls, dt, act.shape)
            return self._json(200, {"actions": act.tolist(), "infer_time": dt})
        except Exception as e:  # noqa: BLE001
            log.exception("Inference failed")
            return self._json(500, {"error": str(e)})


def main():
    Handler.policy = Policy()
    z = np.zeros((240, 320, 3), np.uint8)
    t0 = time.time()
    Handler.policy.infer(z, z, z, z, np.zeros(MAX_STATE_DIM, np.float32), "warmup")
    log.info("Warmup complete %.1fs", time.time() - t0)
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("Listening :%d /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
