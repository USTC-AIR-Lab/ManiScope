"""Launch the official LingBot-VA websocket service with a configured local Wan checkpoint and single-device distributed environment."""
import argparse
import os

os.environ.setdefault("RANK", "0"); os.environ.setdefault("LOCAL_RANK", "0"); os.environ.setdefault("WORLD_SIZE", "1")
os.environ.setdefault("MASTER_ADDR", "127.0.0.1")

import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.environ["LB_DIR"], "wan_va"))
from configs import VA_CONFIGS  # noqa: E402  Match the official service top-level imports so modules share one instance.
import wan_va_server  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--ckpt", required=True)
p.add_argument("--port", type=int, required=True)
p.add_argument("--save_root", default="/tmp/lingbot_vis")
a = p.parse_args()
os.makedirs(a.save_root, exist_ok=True)
wan_va_server.save_async = lambda *a, **k: None   # Disable official asynchronous observation dumps during evaluation; inference is unchanged.
import torch  # noqa: E402
# For one GPU, move the model to BF16 directly without FSDP sharding; this matches the forward parameter dtype.

wan_va_server.shard_model = lambda m: m.to(torch.bfloat16).to("cuda")
cfg = VA_CONFIGS["robotwin"]
cfg.wan22_pretrained_model_name_or_path = a.ckpt
cfg.host = "127.0.0.1"
wan_va_server.init_logger()
wan_va_server.run(argparse.Namespace(config_name="robotwin", port=a.port, save_root=a.save_root))
