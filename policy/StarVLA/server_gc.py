"""Launch the upstream StarVLA server with periodic Python garbage collection to release cyclic references holding GPU tensors. Collection frequency is configurable; inference outputs are unchanged."""

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
    logging.info("[server_gc] gc.collect() every %d predict_action calls", GC_EVERY)
    args = server_policy.build_argparser().parse_args()
    server_policy.main(args)
