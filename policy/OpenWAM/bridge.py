"""OpenWAM 桥接：把官方 websocket 策略服务（openwam-serve）包成和 DM0.5 同款的 HTTP /v1/infer。

在 OpenWAM 的 .venv 里跑（PYTHONPATH 指向官方仓库根，用它的 benchmarks.utils 客户端与 payload 组装）。
逐行复刻官方 benchmarks/robotwin/openwam2robotwin_interface.py 的 ModelClient.step()：
  * 三路图按官方 client.encode_numpy_b64 编码（客户端不做 resize，服务端按 ckpt 配置裁切/拼 L 形多视角）
  * prompt = format_prompt_for_inference(instruction)（训练时模板前缀）
  * state = 20 维 eef proprio（由仿真侧插件按官方 robotwin_endpose_to_eef20d 算好后送来）
  * 指令变化即 reset（官方逻辑）；/v1/reset -> 官方 client.reset()（服务端清 episode 状态与内部动作块）
  * 服务端内部管理动作分块：每步送一次观测、回一个 20 维动作（xyz+rot6d+grip ×2）
请求: {"observation": {"prompt", "images": {"1","2","3"}, "state": [20]}} -> {"actions": [[20]], "infer_time": 秒}
"""

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
            if instruction and instruction != Handler.task_description:      # 官方：指令变化即 reset
                r = self.ws.reset()
                if r.get("type") != transport.RESET_ACK:
                    raise RuntimeError(f"server reset failed: {r}")
                Handler.task_description = instruction
            state = np.asarray(obs["state"], dtype=np.float32).reshape(-1)
            if state.size != STATE_DIM:
                raise ValueError(f"state 应为 {STATE_DIM} 维，收到 {state.size}")
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
                raise ValueError(f"动作异常 {act.shape}")
            Handler.n_calls += 1
            if Handler.n_calls % 200 == 1:
                log.info("infer #%d %.3fs action %s", Handler.n_calls, dt, act.shape)
            return self._json(200, {"actions": [act.tolist()], "infer_time": dt})
        except Exception as e:  # noqa: BLE001
            log.exception("infer 失败")
            return self._json(500, {"error": str(e)})


def main():
    ws = WSPolicyClient(WS_URL, timeout=300.0)
    for i in range(180):
        try:
            r = ws.ping()
            log.info("已连上 %s  ping=%s", WS_URL, str(r)[:120])
            break
        except Exception as e:  # noqa: BLE001
            if i % 12 == 0:
                log.info("等 websocket 服务… (%s)", str(e)[:80])
            time.sleep(5)
    else:
        raise SystemExit("websocket 服务 15 分钟没起来")
    Handler.ws = ws
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("桥接监听 :%d  /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
