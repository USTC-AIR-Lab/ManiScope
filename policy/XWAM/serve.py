"""X-WAM HTTP inference service following the upstream policy server. Build the model from config, then load the supplied complete checkpoint rather than separately loading Wan DiT weights. Preserve the upstream state normalization, dual-arm dimensions, history, sampling and action conventions."""

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [xwam] %(message)s")
log = logging.getLogger("xwam")

XW_ROOT = os.environ["XWAM_ROOT"]
EXP = os.environ["XWAM_EXP"]
WAN_DIR = os.environ["XWAM_WAN_DIR"]
PORT = int(os.environ.get("XWAM_PORT") or os.environ.get("PORT", "7997"))
DENOISE = int(os.environ.get("XWAM_DENOISE_STEPS", "50"))
ACT_DENOISE = int(os.environ.get("XWAM_ACTION_DENOISE_STEPS", "10"))

os.environ["TOKENIZERS_PARALLELISM"] = "false"
sys.path.insert(0, XW_ROOT)
os.chdir(XW_ROOT)
import torch  # noqa: E402
import lightning as L  # noqa: E402
from einops import rearrange  # noqa: E402
from omegaconf import OmegaConf  # noqa: E402

from evaluation import policy_server as ps  # noqa: E402  Use upstream statistics, crop and seed helpers.
from modules import wan_model  # noqa: E402

# Build from config without loading Wan DiT weights; last.ckpt subsequently supplies all model parameters.
_orig_from_pretrained = wan_model.XWAMModel.from_pretrained.__func__


def _from_config_only(cls, path, **kw):
    kw.pop("low_cpu_mem_usage", None)
    cfg = cls.load_config(path)
    log.info("XWAMModel.from_config(%s), awaiting checkpoint model weights", path)
    return cls.from_config(cfg, **kw)


wan_model.XWAMModel.from_pretrained = classmethod(_from_config_only)


class Policy:
    def __init__(self):
        config = OmegaConf.load(os.path.join(EXP, "config.yaml"))
        config.sample_steps = DENOISE
        config.use_decoupled_inference = ACT_DENOISE > 0
        config.action_denoise_steps = ACT_DENOISE
        config.action_num = config.dataset.frame_skip // config.dataset.action_skip
        config.wan_checkpoint_dir = WAN_DIR
        self.config = config
        self.s01, self.s99, self.a01, self.a99, self.dual = ps.build_statistics(config)
        self.action_dim = len(self.a01)
        L.seed_everything(config.seed, workers=True)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        from runners.xwam_runner import XWAMRunner
        t0 = time.time()
        self.model = XWAMRunner(config=config).cuda().bfloat16()
        ck = torch.load(os.path.join(EXP, "checkpoints/last.ckpt/checkpoint/mp_rank_00_model_states.pt"), map_location="cpu")
        missing, unexpected = self.model.load_state_dict(ck["module"], strict=False)
        model_missing = [k for k in missing if k.startswith("model.")]
        if model_missing:
            raise RuntimeError(f"Checkpoint lacks {len(model_missing)} model.* weights, e.g. {model_missing[:5]}")
        log.info("Checkpoint loaded %.1fs missing(non-model.*)=%d unexpected=%d dual_arm=%s action_dim=%d action_num=%d frame_num=%s",
                 time.time() - t0, len(missing), len(unexpected), self.dual, self.action_dim, config.action_num, config.frame_num)
        del ck
        self.model.eval()
        self.model.model = torch.compile(self.model.model)

    @torch.inference_mode()
    def infer(self, imgs, proprio_raw, prompt, seed, cfg):
        rgb = torch.from_numpy(np.stack(imgs, 0).astype(np.float32) / 127.5 - 1.0).bfloat16().unsqueeze(0).cuda()  # [1,V,H,W,C]
        rgb = rearrange(rgb, "b v h w c -> b v c h w")
        rgb = ps.resize_and_center_crop_tensor(rgb, self.config.dataset.video_size, 0.95)
        pn = 2 * (proprio_raw - self.s01) / (self.s99 - self.s01) - 1
        if not self.dual:
            pn[8:] = 0.0
        proprio = torch.from_numpy(pn).bfloat16().unsqueeze(0).cuda()
        _, xt_actions, _, _ = self.model.generate(rgb, proprio, [prompt], seeds=[seed], early_stop=True, cfg=cfg, run_depth=False)
        a = xt_actions[0].float().cpu().numpy()
        a = (a[:, :self.action_dim] + 1) / 2 * (self.a99 - self.a01) + self.a01
        if not self.dual:
            a[:, 6] *= -1.0
        return a


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
        return self._json(200, {"ok": True, "calls": Handler.n_calls, "action_dim": self.policy.action_dim})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        if self.path == "/v1/reset":
            return self._json(200, {"ok": True})
        if self.path != "/v1/infer":
            return self._json(404, {"error": "unknown path"})
        try:
            req = json.loads(raw)
            obs, meta = req["observation"], req.get("meta", {})
            imgs = [decode_img(obs["images"][k]) for k in ("1", "2", "3")]
            state = np.asarray(obs["state"], dtype=np.float64)
            if state.shape != (16,):
                raise ValueError(f"Expected 16-dimensional state, got {state.shape}")
            seed = ps.compute_seed(int(meta.get("env_rank", 0)), int(meta.get("rollout_id", 0)), int(meta.get("step_id", 0)))
            t0 = time.time()
            act = self.policy.infer(imgs, state, str(obs.get("prompt", "")), seed, float(meta.get("cfg", 0.0)))
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
    Handler.policy = Policy()
    z = [np.zeros((240, 320, 3), np.uint8)] * 3
    t0 = time.time()
    Handler.policy.infer(z, np.zeros(16), "warmup", 0, 0.0)
    log.info("Warmup complete %.1fs including torch.compile", time.time() - t0)
    srv = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info("Listening :%d /v1/infer", PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
