"""StarVLA 桥接：把 StarVLA 自带的 websocket 策略服务包成和 DM0.5 同款的 HTTP /v1/infer。

在 StarVLA 的 .venv 里跑（需要 PYTHONPATH 指向 StarVLA 仓库，用它的 websocket 客户端）。
请求/响应契约与 policy/DM05、policy/Pi05 完全一致：
  POST /v1/infer  {"observation": {"prompt", "images": {"1","2","3"} (b64 PNG, head/left/right), "state": [14]}}
  -> {"actions": [[14] * chunk], "infer_time": 秒}

逐行复刻官方 examples/simBenchmarks/Robotwin/eval_files/model2robotwin_interface.py：
  * 三路图 cv2.resize 到 224x224，INTER_AREA
  * vla_input = {"examples":[{"image":[3 图], "lang": 指令}], "do_sample": False, "use_ddim": True,
                 "num_ddim_steps": 10, "unnorm_key": "new_embodiment"}
  * 取 response["data"]["actions"][0] -> (chunk, 14)
  * **关节重排** [0..5, 12, 6..11, 13]：模型输出 [L6, R6, Lg, Rg]，RoboTwin 要 [L6, Lg, R6, Rg]
  * 不送 state（该 checkpoint 无状态输入；abs 模式）
"""

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
                raise ValueError(f"需要 3 路图 (head,left,right)，收到 {len(keys)}")
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
                raise ValueError(f"动作形状异常 {act.shape}")
            act = act[:, REORDER]
            Handler.n_calls += 1
            if Handler.n_calls % 50 == 1:
                log.info("infer #%d %.3fs actions %s", Handler.n_calls, dt, act.shape)
            return self._json(200, {"actions": act.tolist(), "infer_time": dt})
        except Exception as e:  # noqa: BLE001
            log.exception("infer 失败")
            return self._json(500, {"error": str(e)})


def main():
    for i in range(120):                     # 等 websocket 服务把模型加载完
        try:
            Handler.client = WebsocketClientPolicy(WS_HOST, WS_PORT)
            meta = Handler.client.get_server_metadata()
            Handler.chunk = meta.get("action_chunk_size")
            log.info("已连上 websocket %s:%d  server_meta=%s", WS_HOST, WS_PORT, meta)
            break
        except Exception as e:  # noqa: BLE001
            if i % 12 == 0:
                log.info("等 websocket 服务… (%s)", str(e)[:80])
            time.sleep(5)
    else:
        raise SystemExit("websocket 服务 10 分钟没起来")
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("桥接监听 :%d  /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
