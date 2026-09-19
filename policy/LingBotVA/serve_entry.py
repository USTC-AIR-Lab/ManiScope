"""LingBot-VA 官方 websocket 服务的启动壳：把 robotwin 配置里写死的 wan22_pretrained_model_name_or_path
指到本机权重目录，然后进官方 wan_va_server.run()（单卡：直接设 RANK/WORLD_SIZE 环境，不经 torchrun）。"""
import argparse
import os

os.environ.setdefault("RANK", "0"); os.environ.setdefault("LOCAL_RANK", "0"); os.environ.setdefault("WORLD_SIZE", "1")
os.environ.setdefault("MASTER_ADDR", "127.0.0.1")

import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.environ["LB_DIR"], "wan_va"))
from configs import VA_CONFIGS  # noqa: E402  官方服务用顶层  模块名（从 wan_va/ 目录运行），必须同一实例
import wan_va_server  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--ckpt", required=True)
p.add_argument("--port", type=int, required=True)
p.add_argument("--save_root", default="/tmp/lingbot_vis")
a = p.parse_args()
os.makedirs(a.save_root, exist_ok=True)
wan_va_server.save_async = lambda *a, **k: None   # 官方每块把观测异步存盘用于调试，正式评测关掉（不影响推理）
import torch  # noqa: E402
# 单卡不需要 FSDP 分片：官方 shard_model 用 FSDP2 fully_shard(mp_policy bf16)，torch 2.7 对混合 fp32/bf16 参数直接断言；
# 这里等价地把整模型转 bf16 放到 GPU（FSDP 前向本来也是按 param_dtype=bf16 计算）
wan_va_server.shard_model = lambda m: m.to(torch.bfloat16).to("cuda")
cfg = VA_CONFIGS["robotwin"]
cfg.wan22_pretrained_model_name_or_path = a.ckpt
cfg.host = "127.0.0.1"
wan_va_server.init_logger()
wan_va_server.run(argparse.Namespace(config_name="robotwin", port=a.port, save_root=a.save_root))
