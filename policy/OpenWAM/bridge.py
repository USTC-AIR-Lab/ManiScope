"""HTTP bridge to the upstream OpenWAM websocket service. Use official observation payloads and client helpers, preserve instruction-change resets, and let the server own action chunk state."""

import base64
import io
import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
from PIL import Image

from benchmarks.robotwin.prompt_template import format_prompt_for_inference
from benchmarks.utils import WSPolicyClient, client, transport

logging.basicConfig(level=logging.INFO, format="%(asctime)s [openwam-bridge] %(message)s")
log = logging.getLogger("bridge")

PORT = int(os.environ.get("BRIDGE_PORT", "7998"))
WS_URL = os.environ.get("WS_URL", "ws://127.0.0.1:8098")
STATE_DIM = int(os.environ.get("STATE_DIM", "20"))


def decode_img(b64):
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"), dtype=np.uint8)


class Handler(BaseHTTPRequestHandler):
    ws = None
    task_description = ""
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
            Handler.task_description = ""
            r = self.ws.reset()
            ok = r.get("type") == transport.RESET_ACK
            return self._json(200 if ok else 500, {"ok": ok, "resp": str(r)[:200]})
        if self.path != "/v1/infer":
            return self._json(404, {"error": "unknown path"})
        try:
            obs = json.loads(raw)["observation"]
            imgs = {k: decode_img(obs["images"][k]) for k in ("1", "2", "3")}
            instruction = str(obs.get("prompt", ""))
            if instruction and instruction != Handler.task_description:      # Match upstream reset-on-instruction-change behavior.
                r = self.ws.reset()
                if r.get("type") != transport.RESET_ACK:
                    raise RuntimeError(f"server reset failed: {r}")
                Handler.task_description = instruction
            state = np.asarray(obs["state"], dtype=np.float32).reshape(-1)
            if state.size != STATE_DIM:
                raise ValueError(f"Expected {STATE_DIM}-dimensional state, got {state.size}")
            payload = client.build_payload(head=client.encode_numpy_b64(imgs["1"]),
                                           left_wrist=client.encode_numpy_b64(imgs["2"]),
                                           right_wrist=client.encode_numpy_b64(imgs["3"]),
                                           prompt=format_prompt_for_inference(instruction),
                                           state=[float(v) for v in state])
            t0 = time.time()
            resp = self.ws.predict(payload)
            dt = time.time() - t0
            act = np.asarray(resp["action"], dtype=np.float64).reshape(-1)
            if act.size != 20 or not np.isfinite(act).all():
                raise ValueError(f"Invalid actions {act.shape}")
            Handler.n_calls += 1
            if Handler.n_calls % 200 == 1:
                log.info("infer #%d %.3fs action %s", Handler.n_calls, dt, act.shape)
            return self._json(200, {"actions": [act.tolist()], "infer_time": dt})
        except Exception as e:  # noqa: BLE001
            log.exception("Inference failed")
            return self._json(500, {"error": str(e)})


def main():
    ws = WSPolicyClient(WS_URL, timeout=300.0)
    for i in range(180):
        try:
            r = ws.ping()
            log.info("Connected %s ping=%s", WS_URL, str(r)[:120])
            break
        except Exception as e:  # noqa: BLE001
            if i % 12 == 0:
                log.info("Waiting for websocket service (%s)", str(e)[:80])
            time.sleep(5)
    else:
        raise SystemExit("Websocket service did not start within 15 minutes")
    Handler.ws = ws
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("Bridge listening :%d /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
