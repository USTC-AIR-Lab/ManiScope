"""DM0.5 inference service with inference-time language guidance.

Runs playground/dm05_robotwin2.py unchanged except for DM05InferenceConfig._predict: the request is
tokenized twice (guidance prompt and empty prompt), each branch gets its own prefix KV cache, and both
branches start from the same noise. At every Euler step v = v_empty + w * (v_guide - v_empty).
PROBE_CFG_W sets w; w = 1 calls the original _predict."""

import importlib.util
import os
import sys

import torch

OPENDM_DIR = os.environ["OPENDM_DIR"]
sys.path.insert(0, OPENDM_DIR)
spec = importlib.util.spec_from_file_location("dm05_robotwin2", os.path.join(OPENDM_DIR, "playground/dm05_robotwin2.py"))
pg = importlib.util.module_from_spec(spec)
sys.modules["dm05_robotwin2"] = pg  # tyro resolves the dataclasses' source through sys.modules
spec.loader.exec_module(pg)

import opendm.exp.dm05_exp as ex  # noqa: E402
import opendm.model.dm05.dm05_arch as arch  # noqa: E402

W = float(os.environ["PROBE_CFG_W"])


def _branch_velocity(m, kv_cache, prefix_len, input_ids, x_t, time_val, action_mask):
    batch_size, device = x_t.shape[0], x_t.device
    time_tensor = torch.full((batch_size,), time_val, device=device, dtype=x_t.dtype)
    if action_mask is not None:
        x_t = x_t * action_mask
    suffix_embeds = m.model.action_in_proj(x_t)
    adarms_cond = m._build_adarms_cond(time_tensor, suffix_embeds.dtype)
    suffix_len = int(suffix_embeds.shape[1])
    pad = m.model.vlm.model.language_model.padding_idx
    invisible = (arch.HISTORY_PAD_TOKEN_ID,)
    suffix_attn_mask = arch.make_suffix_attn_mask(
        input_ids=input_ids, prefix_len=prefix_len, suffix_len=suffix_len, batch_size=batch_size,
        device=suffix_embeds.device, dtype=suffix_embeds.dtype, pad_token_id=pad,
        invisible_prefix_token_ids=invisible)
    suffix_position_ids = m._build_suffix_position_ids(
        prefix_len, suffix_len, device, input_ids=input_ids, pad_token_id=pad,
        invisible_prefix_token_ids=invisible)
    out = m._suffix_forward(suffix_embeds=suffix_embeds, attention_mask=suffix_attn_mask,
                            position_ids=suffix_position_ids, past_key_values=kv_cache, adarms_cond=adarms_cond)
    return m.model.action_out_proj(out)


@torch.no_grad()
def cfg_inference(m, branches, diffusion_steps, action_mask, w):
    caches = []
    for b in branches:
        kv, plen = m._compute_prefix_cache(
            input_ids=b["input_ids"], attention_mask=b["attention_mask"], pixel_values=b["pixel_values"],
            token_type_ids=b["token_type_ids"], history_pixel_values=b.get("history_pixel_values"),
            history_mask=b.get("history_mask"), cache_cls=arch.DynamicCache)
        caches.append((kv, plen))
    ids = branches[0]["input_ids"]
    dtype = m.model.action_in_proj.weight.dtype
    x_t = torch.randn(ids.shape[0], m.model.config.chunk_size, m.model.config.action_dim, device=ids.device, dtype=dtype)
    time_val, dt = 1.0, -1.0 / diffusion_steps
    for _ in range(diffusion_steps):
        v_guide, v_empty = (_branch_velocity(m, kv, plen, b["input_ids"], x_t, time_val, action_mask)
                            for b, (kv, plen) in zip(branches, caches))
        x_t = x_t + (v_empty + w * (v_guide - v_empty)) * dt
        time_val += dt
    return x_t


_orig_predict = ex.DM05InferenceConfig._predict


def _predict(self, data):
    if W == 1:
        return _orig_predict(self, data)
    self.last_model_latency_sec = None
    state = data["state"]
    branches = [self.input_transform({**data, "images": list(data["images"]), "state": data["state"].copy(),
                                      "history_images": list(data.get("history_images") or []),
                                      "meta_data": dict(data["meta_data"]), "prompt": p})
                for p in (data["prompt"], "")]
    m = ex.unwrap_dm05_model(self.model)
    action_mask = torch.zeros(1, 1, m.model.config.action_dim, device=self.device,
                              dtype=m.model.action_in_proj.weight.dtype)
    action_mask[..., : self.output_action_dim] = 1.0
    actions = cfg_inference(m, branches, self.diffusion_steps, action_mask, W)
    raw_actions = actions.to(torch.float32).detach().cpu().numpy()[0, :, : self.output_action_dim]
    return self.output_transform({"action": raw_actions, "state": state, "meta_data": data["meta_data"]})["action"]


ex.DM05InferenceConfig._predict = _predict

if __name__ == "__main__":
    import tyro

    print(f"[dm05-cfg] language guidance w={W}", flush=True)
    exp = tyro.cli(pg.DM05Exp)
    assert exp.task == "inference"
    assert exp.inference_config.backend == "default"
    exp.inference()
