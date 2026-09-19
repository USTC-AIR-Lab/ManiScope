"""StarVLA 官方 websocket 服务的启动壳：修 GPU 显存泄漏后再进官方 main。

官方 PolicyServerWrapper.predict_action 每次调用泄漏约 170MB 显存（QwenOFT 推理产生的引用环持有 GPU
张量，Python 的 gc 阈值不看显存，故长时间不回收；实测 gc.collect() 后全部释放）。正式评测每场景
~1500 次调用，跑到第 20 条左右服务就 OOM 崩溃、eval 收到 500。这里不改官方仓库，只在启动时把
predict_action 包一层：每 GC_EVERY 次调用做一次 gc.collect()（+ empty_cache），推理本身与口径不变。
"""

import gc
import logging
import os
import sys

import torch

from deployment.model_server import policy_wrapper, server_policy

GC_EVERY = int(os.environ.get("STARVLA_GC_EVERY", "4"))
_orig = policy_wrapper.PolicyServerWrapper.predict_action
_n = {"calls": 0}


def _predict_with_gc(self, *a, **kw):
    out = _orig(self, *a, **kw)
    _n["calls"] += 1
    if _n["calls"] % GC_EVERY == 0:
        gc.collect()
        torch.cuda.empty_cache()
    return out


policy_wrapper.PolicyServerWrapper.predict_action = _predict_with_gc

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, force=True)
    logging.info("[server_gc] predict_action 每 %d 次调用 gc.collect()", GC_EVERY)
    args = server_policy.build_argparser().parse_args()
    server_policy.main(args)
