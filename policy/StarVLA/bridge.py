"""Bridge the upstream StarVLA websocket policy service to HTTP /v1/infer using the configured external repository and websocket client. Preserve observation formatting, reset semantics and action chunking."""

import base64
import io
import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2
import numpy as np
from PIL import Image

from deployment.model_server.tools.websocket_policy_client import WebsocketClientPolicy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [starvla-bridge] %(message)s")
log = logging.getLogger("bridge")

PORT = int(os.environ.get("BRIDGE_PORT", "7970"))
WS_HOST = os.environ.get("WS_HOST", "127.0.0.1")
WS_PORT = int(os.environ.get("WS_PORT", "8070"))
UNNORM_KEY = os.environ.get("UNNORM_KEY", "new_embodiment")
IMAGE_SIZE = int(os.environ.get("IMAGE_SIZE", "224"))
NUM_DDIM = int(os.environ.get("NUM_DDIM_STEPS", "10"))
REORDER = [0, 1, 2, 3, 4, 5, 12, 6, 7, 8, 9, 10, 11, 13]


def decode_img(b64):
    im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    return cv2.resize(np.asarray(im, dtype=np.uint8), (IMAGE_SIZE, IMAGE_SIZE), interpolation=cv2.INTER_AREA)


class Handler(BaseHTTPRequestHandler):
    client = None
    chunk = None
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
        return self._json(200, {"ok": True, "calls": Handler.n_calls, "chunk": Handler.chunk})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        if self.path == "/v1/reset":
            return self._json(200, {"ok": True})
        if self.path != "/v1/infer":
            return self._json(404, {"error": "unknown path"})
        try:
            obs = json.loads(raw)["observation"]
            keys = sorted(obs["images"].keys(), key=lambda k: int(k))
            if len(keys) != 3:
                raise ValueError(f"Expected 3 views (head,left,right), got {len(keys)}")
            imgs = [decode_img(obs["images"][k]) for k in keys]
            vla_input = {
                "examples": [{"image": imgs, "lang": str(obs.get("prompt", ""))}],
                "do_sample": False, "use_ddim": True, "num_ddim_steps": NUM_DDIM, "unnorm_key": UNNORM_KEY,
            }
            t0 = time.time()
            resp = self.client.predict_action(vla_input)
            dt = time.time() - t0
            act = np.asarray(resp["data"]["actions"][0], dtype=np.float64)
            if act.ndim != 2 or act.shape[1] != 14:
                raise ValueError(f"Invalid action shape {act.shape}")
            act = act[:, REORDER]
            Handler.n_calls += 1
            if Handler.n_calls % 50 == 1:
                log.info("infer #%d %.3fs actions %s", Handler.n_calls, dt, act.shape)
            return self._json(200, {"actions": act.tolist(), "infer_time": dt})
        except Exception as e:  # noqa: BLE001
            log.exception("Inference failed")
            return self._json(500, {"error": str(e)})


def main():
    for i in range(120):                     # Wait for websocket model loading.
        try:
            Handler.client = WebsocketClientPolicy(WS_HOST, WS_PORT)
            meta = Handler.client.get_server_metadata()
            Handler.chunk = meta.get("action_chunk_size")
            log.info("Connected websocket %s:%d server_meta=%s", WS_HOST, WS_PORT, meta)
            break
        except Exception as e:  # noqa: BLE001
            if i % 12 == 0:
                log.info("Waiting for websocket service (%s)", str(e)[:80])
            time.sleep(5)
    else:
        raise SystemExit("Websocket service did not start within 10 minutes")
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("Bridge listening :%d /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
