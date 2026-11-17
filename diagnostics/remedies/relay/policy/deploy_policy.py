"""Relay policy: the GPT-6 agent (policy/GPT6 client, diagnostics/remedies/relay/relay_bridge.py) selects the object
the instruction refers to, brings an open gripper to it and finishes; the remaining step budget of the episode goes to DM0.5
(policy/DM05 client at RELAY_VLA_URL) with the original instruction.

The agent's finish ends an episode in policy/GPT6 (take_action_cnt = step_lim); here the step counter
is restored and control switches to DM0.5. The agent's contact guard is disabled for the DM0.5 phase
and reinstated for the next episode. model.relay is copied into the probe record; the candidate
nearest to the gripper at handoff is computed from simulator poses for that record only."""
import os
import time

import numpy as np
import requests

from GPT6 import deploy_policy as agent
from DM05 import deploy_policy as vla


class Relay:
    def __init__(self, usr_args):
        self.agent = agent.get_model(usr_args)
        url = os.environ["RELAY_VLA_URL"]
        for _ in range(360):  # the DM0.5 server may still be loading
            try:
                requests.post(url + "/v1/reset", timeout=3)
                break
            except Exception:  # noqa: BLE001
                time.sleep(5)
        self.vla = vla.get_model({"base_url": url, "cameras": "head_camera_rgb,left_camera_rgb,right_camera_rgb",
                                  "action_horizon": 50, "api_style": "v1", "action_mode": "absolute"})
        self.phase = "agent"
        self.relay = None
        self.saved_guard = None
        self.infer_times = []


def get_model(usr_args):
    return Relay(usr_args)


def reset_model(model):
    agent.reset_model(model.agent)
    vla.reset_model(model.vla)
    model.phase = "agent"
    model.relay = None


def _nearest_candidate(TASK_ENV, obs):
    actors = getattr(TASK_ENV, "_actors", None) or {}
    if not actors:
        return None, None
    best = None
    for side in ("left", "right"):
        p = np.asarray(obs["endpose"][side + "_endpose"][:3], dtype=float)
        for role, a in actors.items():
            q = np.asarray(a.get_pose().p, dtype=float)
            d = float(np.linalg.norm(p[:2] - q[:2]))
            if best is None or d < best[2]:
                best = (side, role, d)
    return best[1], {"arm": best[0], "xy_dist_m": best[2]}


def eval(TASK_ENV, model, observation):
    if model.phase == "agent":
        if model.saved_guard is not None and model.agent.calls == 0:
            TASK_ENV._fine_step_guard = model.saved_guard
        before = int(TASK_ENV.take_action_cnt)
        out = agent.eval(TASK_ENV, model.agent, observation)
        if TASK_ENV.take_action_cnt >= TASK_ENV.step_lim and not TASK_ENV.eval_success:
            term = (model.agent.cur or {}).get("termination")
            TASK_ENV.take_action_cnt = before
            obs = TASK_ENV.get_obs()
            nearest, info = _nearest_candidate(TASK_ENV, obs)
            model.relay = {"step": before, "agent_calls": model.agent.calls, "termination": term,
                                 "note": (model.agent.feedback or {}).get("termination"),
                                 "nearest_candidate": nearest, **(info or {}),
                                 "agent_api_seconds": (model.agent.cur or {}).get("api_seconds")}
            model.saved_guard = getattr(TASK_ENV, "_fine_step_guard", None)
            TASK_ENV._fine_step_guard = lambda: False
            if hasattr(TASK_ENV, "_fine_control"):
                TASK_ENV._fine_control.update(phase="transit", stopped=False, reason=None)
            model.phase = "vla"
            print("[relay] handoff", model.relay, flush=True)
            return obs
        return out
    return vla.eval(TASK_ENV, model.vla, observation)
