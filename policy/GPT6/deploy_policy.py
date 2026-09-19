"""EEF policy for the existing RoboTwin-Compo evaluator; contains NO API key.

Connect only to a local SSH reverse-forward endpoint. No expert actions, object
poses, segmentation labels, or task internals are sent to the model.
"""
import base64
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

import cv2
import numpy as np
import requests
from .audit import capture, install
from . import fine_control
from .robot_state import gripper_aperture, measured_joint_vector
from .execute_target import execute
from .wall_video import WallVideo


class GPT6Client:
    def __init__(self, args):
        self.url = args.get("base_url", "http://127.0.0.1:18766").rstrip("/")
        p = urlsplit(self.url)
        if p.scheme != "http" or p.hostname not in ("127.0.0.1", "localhost") or p.username or p.password or p.query or p.fragment or p.path:
            raise ValueError("bridge must be a loopback SSH tunnel")
        token_file = args.get("bridge_token_file") or os.environ.get("GPT6_BRIDGE_TOKEN_FILE")
        if not token_file:
            raise ValueError("missing separate bridge token file")
        self.token = Path(token_file).read_text().strip()
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers["Authorization"] = "Bearer " + self.token
        self.limit = int(args.get("max_llm_calls", 40))
        self.audit_dir = Path(token_file).parent / "audit"
        self.calls = 0
        self.feedback = None
        self.infer_times = []
        # 大模型 agent 计时账本（每条 episode 一条，每次调用后覆盖写 _agent_timing.jsonl）：
        # API 次数/响应时间/token、执行（规划+仿真）时间、episode 墙钟、终止原因
        self.timing_dir = Path(str(args.get("eval_output_dir") or "")) if args.get("eval_output_dir") else None
        self.timing = {}
        self.cur = None

    def request(self, route, payload):
        """桥接/网关偶发超时或 5xx：重试 3 次；仍失败则返回 rejected（本步跳过，不让整场崩），连续 5 次失败才 finish。"""
        last = None
        for attempt in range(3):
            try:
                r = self.session.post(self.url + route, json=payload, timeout=(10, 900), allow_redirects=False)
                if r.status_code == 200:
                    self.consecutive_errors = 0
                    return r.json()
                last = "HTTP " + str(r.status_code)
            except Exception as exc:  # noqa: BLE001
                last = type(exc).__name__
            time.sleep(5 * (attempt + 1))
        if route != "/infer":
            raise RuntimeError("local bridge failed; " + str(last))
        self.consecutive_errors = getattr(self, "consecutive_errors", 0) + 1
        print("[GPT6] bridge/API error:", last, "consecutive", self.consecutive_errors, flush=True)
        if self.consecutive_errors >= 5:
            return {"type": "finish", "note": "bridge/API repeatedly unavailable: " + str(last)}
        return {"type": "rejected", "note": "bridge/API error: " + str(last) + "; retry with the same observation"}


def _flush_timing(model, TASK_ENV, termination):
    """每次调用后覆盖写本条 episode 的计时账本（JSONL，每条 episode 一行）。"""
    c = model.cur
    if c is None:
        return
    c["wall_seconds"] = time.monotonic() - c["wall_start"]
    c["sim_steps"] = int(TASK_ENV.take_action_cnt)
    c["success"] = bool(TASK_ENV.eval_success)
    if termination and not c.get("termination"):
        c["termination"] = termination
    if model.timing_dir is None:
        return
    try:
        model.timing_dir.mkdir(parents=True, exist_ok=True)
        with (model.timing_dir / "_agent_timing.jsonl").open("w", encoding="utf-8") as f:
            for e in model.timing.values():
                f.write(json.dumps({k: v for k, v in e.items() if k != "wall_start"}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def get_model(usr_args):
    return GPT6Client(usr_args)


def reset_model(model):
    model.request("/reset", {})
    model.calls = 0
    model.feedback = None


def eval(TASK_ENV, model, observation):
    if getattr(TASK_ENV, '_soft_eval_episode', None) != TASK_ENV.test_num:   # 正式多条评测：每条 episode 各自计时
        TASK_ENV._soft_eval_episode = TASK_ENV.test_num
        TASK_ENV._soft_eval_deadline = time.monotonic() + 3300
    if time.monotonic() >= TASK_ENV._soft_eval_deadline:
        obs = TASK_ENV.get_obs()
        capture(TASK_ENV, model, obs, "budget_finish")
        model.feedback = {"termination": "evaluation_wall_budget_3300s"}
        (model.audit_dir.parent / 'budget_termination.json').write_text(
            json.dumps({'reason': 'evaluation_wall_budget', 'seconds': 3300,
                        'model_calls': model.calls, 'environment_success': bool(TASK_ENV.eval_success)}))
        TASK_ENV.take_action_cnt = TASK_ENV.step_lim
        _flush_timing(model, TASK_ENV, "wall_budget_3300s")
        return obs
    if model.calls >= model.limit:
        # End as an unsuccessful/budget-limited attempt, never fabricate success.
        TASK_ENV.take_action_cnt = TASK_ENV.step_lim
        _flush_timing(model, TASK_ENV, "call_budget_%d" % model.limit)
        return observation
    obs = observation if observation is not None else TASK_ENV.get_obs()
    ep_key = int(TASK_ENV.test_num)
    if ep_key not in model.timing:
        model.timing[ep_key] = model.cur = {"episode": ep_key, "seed": getattr(TASK_ENV, "seed", None), "api_calls": 0,
                                            "api_seconds": 0.0, "exec_seconds": 0.0, "wall_start": time.monotonic(),
                                            "wall_seconds": 0.0, "input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0,
                                            "cached_input_tokens": 0, "sim_steps": 0, "termination": None, "success": False}
    model.cur = model.timing[ep_key]
    if model.calls == 0:
        install(TASK_ENV)
        fine_control.install(TASK_ENV)
        old = getattr(TASK_ENV, "_wall_recorder", None)
        if old is not None:
            old.close()
        TASK_ENV._wall_recorder = WallVideo(model.audit_dir.parent / "wall_clock" / f"{getattr(TASK_ENV, 'task_name', 'task')}_ep{TASK_ENV.test_num:03d}",
                                            obs["observation"]["head_camera"]["rgb"])
        capture(TASK_ENV, model, obs, "initial")
    images = {}
    for name in ("head_camera", "left_camera", "right_camera"):
        rgb = np.asarray(obs["observation"][name]["rgb"])
        ok, data = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        if not ok:
            raise RuntimeError("camera encoding failed")
        images[name] = base64.b64encode(data.tobytes()).decode()
    state = {name: np.asarray(value).tolist() for name, value in obs["endpose"].items()}
    for side in ('left','right'):
        state[side+'_gripper_actual'] = gripper_aperture(TASK_ENV.robot, side)
    payload = {"instruction": TASK_ENV.get_instruction(), "images": images, "eef_state": state,
               "joint_state": measured_joint_vector(TASK_ENV.robot),
               "feedback": model.feedback, "contact_feedback": getattr(TASK_ENV,"_fine_control",None), "step": TASK_ENV.take_action_cnt}
    started = time.monotonic()
    TASK_ENV._wall_recorder.push(obs["observation"]["head_camera"]["rgb"], "inference_wait")
    action = model.request("/infer", payload)
    api_s = float(action.get("api_seconds", time.monotonic() - started))
    model.infer_times.append(api_s)
    model.cur["api_calls"] += 1; model.cur["api_seconds"] += api_s
    for k in ("input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens"):
        model.cur[k] += int((action.get("usage") or {}).get(k) or 0)
    TASK_ENV._wall_recorder.push(obs["observation"]["head_camera"]["rgb"], "motion")
    model.calls += 1
    if action["type"] == "finish":
        capture(TASK_ENV, model, obs, "finish")
        model.feedback = {"termination": action.get("note", "")}
        TASK_ENV.take_action_cnt = TASK_ENV.step_lim
        _flush_timing(model, TASK_ENV, "model_finish")
        return obs
    if action["type"] == "rejected":
        model.feedback = {"rejected": action.get("note", "")}
        _flush_timing(model, TASK_ENV, None)
        return obs
    if action["type"] != "move_eef" or action.get("arm") not in ("left", "right"):
        raise ValueError("invalid bridge action")
    arm = action["arm"]
    target = np.asarray(action["position"] + action["quaternion_wxyz"], dtype=float)
    gripper = float(action["gripper"])
    if target.shape != (7,) or not np.isfinite(target).all() or not np.isfinite(gripper):
        raise ValueError("non-finite or malformed action")
    if not 0 <= gripper <= 1 or abs(np.linalg.norm(target[3:])-1) > 1e-4:
        raise ValueError("invalid gripper or quaternion")
    if np.linalg.norm(target[:3]-np.asarray(state[arm+"_endpose"][:3])) > 0.450001:
        raise ValueError("translation exceeds step envelope")
    from .motion_math import bound
    action = bound(action, state)
    target = np.asarray(action['position'] + action['quaternion_wxyz'], dtype=float)
    gripper = float(action['gripper'])
    # RoboTwin's action_type=ee expects [xyz,wxyz,gripper] for each arm.
    # This uses its existing planner; no scripted grasp/place macro is called.
    exec_t0 = time.monotonic()
    segment_feedback = execute(TASK_ENV, action, state)
    model.cur["exec_seconds"] += time.monotonic() - exec_t0
    after = TASK_ENV.get_obs()
    capture(TASK_ENV, model, after, "after")
    measured = np.asarray(after["endpose"][arm+"_endpose"])
    q_target=target[3:]/np.linalg.norm(target[3:])
    q_measured=measured[3:]/np.linalg.norm(measured[3:])
    orientation_error=float(np.degrees(2*np.arccos(np.clip(abs(np.dot(q_target,q_measured)),0,1))))
    model.feedback = {"arm": arm, "requested_pose": target.tolist(),
                      "orientation_residual_deg": orientation_error,
                      "measured_pose": measured.tolist(),
                      "requested_gripper": gripper, "commanded_gripper": float(after["endpose"][arm+"_gripper"]), "measured_gripper": gripper_aperture(TASK_ENV.robot, arm),
                      "position_residual_m": float(np.linalg.norm(target[:3]-measured[:3])),
                      "roundtrip_and_execution_seconds": time.monotonic()-started,
                      "environment_success": bool(TASK_ENV.eval_success),
                      "executed_bounded_command": action, "segment_feedback": segment_feedback, "contact_feedback": dict(TASK_ENV._fine_control)}
    print("[GPT6] call", model.calls, "position residual", round(model.feedback["position_residual_m"], 4), flush=True)
    _flush_timing(model, TASK_ENV, "env_success" if TASK_ENV.eval_success else ("step_limit" if TASK_ENV.take_action_cnt >= TASK_ENV.step_lim else None))
    return after
