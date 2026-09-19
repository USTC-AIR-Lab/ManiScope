"""LingBot-VA 桥接：把官方 websocket 服务（wan_va_server，msgpack）包成 HTTP，供仿真侧插件按官方三段协议调用。

官方 evaluation/robotwin/eval_polict_client_openpi.py 每个 episode 的协议：
  1) infer({reset: True, prompt})                          -> 清 KV 缓存、设指令
  2) infer({obs: first_obs, prompt, video_guidance_scale, action_guidance_scale}) -> {"action": [D, F, S]}
  3) 客户端执行动作并每 action_per_frame 步抓一帧观测（key frames）后：
     infer({obs: key_frame_list, compute_kv_cache: True, imagine: False, state: action}) -> 更新缓存
本桥接三个端点与之一一对应：/v1/reset {prompt}、/v1/infer {observation, meta}、/v1/kv {frames}
（state=上一次返回的 action 由桥接自己缓存，不必回传）。观测 dict 字段名与官方 format_obs 一致。
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

from evaluation.robotwin.websocket_client_policy import WebsocketClientPolicy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [lingbot-bridge] %(message)s")
log = logging.getLogger("bridge")

PORT = int(os.environ.get("BRIDGE_PORT", "8001"))
WS_PORT = int(os.environ.get("WS_PORT", "8101"))
VIDEO_GS = float(os.environ.get("VIDEO_GUIDANCE_SCALE", "5"))    # 官方 launch_client.sh: 5
ACTION_GS = float(os.environ.get("ACTION_GUIDANCE_SCALE", "1"))  # 官方 launch_client.sh: 1


def decode_img(b64):
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB"), dtype=np.uint8)


def fmt_obs(o):
    """官方 format_obs：三路图 + 14 维关节角 + 指令"""
    return {"observation.images.cam_high": decode_img(o["images"]["1"]),
            "observation.images.cam_left_wrist": decode_img(o["images"]["2"]),
            "observation.images.cam_right_wrist": decode_img(o["images"]["3"]),
            "observation.state": np.asarray(o["state"], dtype=np.float32),
            "task": str(o.get("prompt", ""))}


class Handler(BaseHTTPRequestHandler):
    ws = None
    last_action = None
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
        req = json.loads(self.rfile.read(n) if n else b"{}")
        try:
            if self.path == "/v1/reset":
                self.ws.infer(dict(reset=True, prompt=str(req.get("prompt", "")), save_visualization=False))
                Handler.last_action = None
                return self._json(200, {"ok": True})
            if self.path == "/v1/infer":
                obs = fmt_obs(req["observation"])
                t0 = time.time()
                ret = self.ws.infer(dict(obs=obs, prompt=obs["task"], save_visualization=False,
                                         video_guidance_scale=VIDEO_GS, action_guidance_scale=ACTION_GS))
                dt = time.time() - t0
                act = np.asarray(ret["action"], dtype=np.float64)        # [D, F, S]
                if act.ndim != 3 or not np.isfinite(act).all():
                    raise ValueError(f"动作异常 shape={act.shape}")
                Handler.last_action = np.asarray(ret["action"])
                Handler.n_calls += 1
                if Handler.n_calls % 50 == 1:
                    log.info("infer #%d %.3fs action %s", Handler.n_calls, dt, act.shape)
                return self._json(200, {"action": act.tolist(), "infer_time": dt})
            if self.path == "/v1/kv":
                frames = [fmt_obs(f) for f in req["frames"]]
                t0 = time.time()
                self.ws.infer(dict(obs=frames, compute_kv_cache=True, imagine=False, save_visualization=False,
                                   state=Handler.last_action))
                return self._json(200, {"ok": True, "kv_time": time.time() - t0})
            return self._json(404, {"error": "unknown path"})
        except Exception as e:  # noqa: BLE001
            log.exception("请求失败 %s", self.path)
            return self._json(500, {"error": str(e)})


def main():
    for i in range(240):
        try:
            Handler.ws = WebsocketClientPolicy(host="127.0.0.1", port=WS_PORT)
            log.info("已连上 ws://127.0.0.1:%d", WS_PORT)
            break
        except Exception as e:  # noqa: BLE001
            if i % 12 == 0:
                log.info("等 websocket 服务… (%s)", str(e)[:80])
            time.sleep(5)
    else:
        raise SystemExit("websocket 服务 20 分钟没起来")
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("桥接监听 :%d", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
