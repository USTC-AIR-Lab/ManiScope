"""Local-only credential holder. Remote simulation sends observations over SSH.

The API secret is never returned to the simulation or included in a log.
Only an explicitly configured HTTPS endpoint receives it for authentication.
"""
import argparse
import base64
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError


QUOTA_STOP = Path(os.environ.get("AGENT_RUNTIME_DIR", "configs/private/agent")) / "QUOTA_EXHAUSTED"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


PROMPT = """Control a simulated ALOHA dual-arm robot from RGB cameras and measured
robot state. Perform the user's instruction. You have no object poses or expert
trajectory. Choose absolute end-effector targets; the simulator performs motion
planning and joint control. All positions are meters in the world frame. x<0 is
left, x>0 is right, positive y is away from the robot, z is up. Quaternion order
is [w,x,y,z]. RoboTwin's reported EEF control point is 0.12 m behind the gripper
center along its local +x axis: TCP = EEF_position + R(quaternion)*[0.12,0,0].
Gripper 0 is closed and 1 is open. In eef_state, *_gripper is the commanded
aperture retained for motion; *_gripper_actual is measured from physical joints.
Physical aperture can lag the command while the motor moves; inspect feedback
and images. Its normalization uses the existing drive calibration, not millimeters.
A close command of 0 does not prove an empty grasp; inspect actual aperture and images.
joint_state contains physical joint positions. Use the provided measured poses
as references, preserve orientation unless a change is necessary. Use phases explicitly: transit for clear free space, approach when near objects,
contact for intentional pressing/insertion, and gripper for opening/closing at a fixed pose.
Model-call target envelopes: transit up to 45 cm / 90 degrees,
approach up to 12 cm / 30 degrees, contact up to 3 cm / 10 degrees.
The controller internally interpolates the entire accepted target without additional
model calls. It stops early on unexpected contact or tracking error above 2.5 cm / 10 degrees
relative to an internal segment target (separate from the model-call envelopes). Do not issue
millimeter-by-millimeter calls in free space. Plan purposeful waypoints: align above,
approach, close, lift, transport, place, release. Gripper phase sets the requested aperture in one call at a fixed pose: 0 is closed,
1 is fully open, and intermediate values are allowed for limited clearance.
Other phases preserve aperture. Prefer reorienting above
objects before descending. Use transit only for a clear route, approach near objects,
and contact only for intentional pressing/insertion. After a contact stop, first open
with gripper phase at the measured fixed pose. If stuck, recover phase permits a
translation of at most 3 cm away from contact, keeping measured orientation and
the current gripper command fixed. This is a monitored escape: new contact, excessive/increasing force,
or persistent non-improving force stops it. Do not repeatedly push into the obstacle.
Inspect actual final pose and
contact feedback before the next target. Keep
clear of the table and other objects. Identify the requested object and destination from the images and instruction.
Do not assume motion succeeded: compare the next measured pose and image.
Return exactly one move_eef or finish tool call. Finish when completed or when
you cannot proceed. Your claim does not determine the environment's score.
"""

TOOLS = [
    {"type": "function", "name": "move_eef", "description": "Move one arm to an absolute EEF pose.",
     "strict": True, "parameters": {"type": "object", "additionalProperties": False,
      "properties": {"arm": {"type": "string", "enum": ["left", "right"]},
       "position": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
       "quaternion_wxyz": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4},
       "phase": {"type": "string", "enum": ["transit", "approach", "contact", "gripper", "recover"]},
       "gripper": {"type": "number"}, "note": {"type": "string"}},
      "required": ["arm", "position", "quaternion_wxyz", "gripper", "phase", "note"]}},
    {"type": "function", "name": "finish", "description": "End the attempt; the simulator independently scores success.",
     "strict": True, "parameters": {"type": "object", "additionalProperties": False,
      "properties": {"note": {"type": "string"}}, "required": ["note"]}},
]


def validate_move(a, state):
    arm = a.get("arm")
    if arm not in ("left", "right"):
        raise ValueError("invalid arm")
    p, q, g = a.get("position"), a.get("quaternion_wxyz"), a.get("gripper")
    if not isinstance(p, list) or len(p) != 3 or not isinstance(q, list) or len(q) != 4:
        raise ValueError("invalid pose dimensions")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p + q + [g]):
        raise ValueError("non-finite or non-numeric pose")
    if not 0 <= g <= 1:
        raise ValueError("gripper must be within [0,1]")
    if any(abs(v) > 2 for v in p):
        raise ValueError("outside workspace envelope")
    if math.dist(p, state[arm + "_endpose"][:3]) > 0.450001:
        raise ValueError("translation exceeds 0.45 meters; split the motion")
    norm = math.sqrt(sum(v*v for v in q))
    if not 0.9 <= norm <= 1.1:
        raise ValueError("quaternion must be approximately unit length")
    from policy.GPT6.motion_limits import bound
    return bound({**a, "quaternion_wxyz": [v/norm for v in q]}, state)


class Bridge:
    """Responses, Chat Completions, native Gemini and Anthropic API transports."""
    def __init__(self, config, key, log_dir, max_calls):
        self.provider = config.get("provider", "responses")
        model = config.get("model", "gpt-6-astra")
        if self.provider == "gemini":
            base = config["base_url"].rstrip("/")
            base = base[:-3] if base.endswith("/v1") else base
            endpoint = f"{base}/v1beta/models/{model}:generateContent"
        else:
            route = {"responses": "/responses", "chat": "/chat/completions", "anthropic": "/messages"}[self.provider]
            endpoint = config["base_url"].rstrip("/") + route
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base_url must be an HTTPS API base without credentials/query/fragment")
        self.endpoint, self.key = endpoint, key
        self.model = config.get("model", "gpt-6-astra")
        self.effort = config.get("reasoning_effort", "medium")
        # Output cap per request. Reasoning can exhaust the cap before a tool call is emitted,
        # so a new model may need a larger value than this provider default; report the value used.
        self.max_output_tokens = int(config.get("max_output_tokens") or
                                     {"responses": 4096, "chat": 8192, "gemini": 8192,
                                      "anthropic": 16000}.get(self.provider, 8192))
        self.opener = build_opener(ProxyHandler({}), HTTPSHandler(), NoRedirect())
        self.history = []
        self.calls, self.max_calls = 0, max_calls
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)


    def _text_block(self, txt):
        if self.provider == "gemini":
            return {"text": txt}
        return {"type": "input_text", "text": txt} if self.provider == "responses" else {"type": "text", "text": txt}

    def _image_blocks(self, name, encoded):
        if self.provider == "responses":
            return [{"type": "input_text", "text": "camera: " + name},
                    {"type": "input_image", "image_url": "data:image/png;base64," + encoded}]
        if self.provider == "chat":
            return [{"type": "text", "text": "camera: " + name},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}}]
        if self.provider == "gemini":
            return [{"text": "camera: " + name}, {"inline_data": {"mime_type": "image/png", "data": encoded}}]
        return [{"type": "text", "text": "camera: " + name},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": encoded}}]

    def _build_payload(self):
        h = {"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}
        if self.provider == "responses":
            return ({"model": self.model, "instructions": PROMPT, "input": self.history,
                     "tools": TOOLS, "tool_choice": "required", "parallel_tool_calls": False,
                     "reasoning": {"effort": self.effort}, "max_output_tokens": self.max_output_tokens,
                     "store": False, "include": ["reasoning.encrypted_content"],
                     "prompt_cache_key": getattr(self, "cache_key", "ep-0")}, h)   # Route this episode through a stable prompt-cache key.
        if self.provider == "chat":
            tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in TOOLS]
            # Chat compatibility mode retains text history and the latest two image observations.

            transcript = []
            users = [m for m in self.history if m.get("role") == "user"]
            for m in self.history:
                if m.get("role") == "assistant":
                    for tc in m.get("tool_calls") or []:
                        transcript.append("assistant tool_call %s(%s)" % (tc["function"]["name"], tc["function"]["arguments"]))
                elif m.get("role") == "tool":
                    transcript.append("tool_result " + str(m.get("content"))[:400])
                elif m.get("role") == "user":
                    txt = next((c["text"] for c in m["content"] if c.get("type") == "text"), "")
                    transcript.append("observation " + txt[:1500])
            cur = users[-1]["content"]
            prev_imgs = [c for c in users[-2]["content"] if c.get("type") == "image_url"] if len(users) >= 2 else []
            content = [{"type": "text", "text": "Transcript of this episode so far (oldest first):\n" + "\n".join(transcript[:-1])}] if len(transcript) > 1 else []
            if prev_imgs:
                content += [{"type": "text", "text": "Previous observation images:"}] + prev_imgs
            content += [{"type": "text", "text": "Current observation:"}] + cur
            return ({"model": self.model, "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": content}],
                     "tools": tools, "tool_choice": "required", "parallel_tool_calls": False,
                     "reasoning_effort": self.effort, "max_tokens": self.max_output_tokens}, h)
        if self.provider == "gemini":
            # Native Gemini retains function-call signatures; retry modes progressively omit signatures/history.


            mode = getattr(self, "_gemini_mode", "full")
            contents = []
            if mode == "stateless":
                transcript = []
                for m in self.history:
                    if m.get("role") == "model":
                        for pt in m["parts"]:
                            if "functionCall" in pt:
                                transcript.append("assistant tool_call %s(%s)" % (pt["functionCall"]["name"], json.dumps(pt["functionCall"].get("args") or {})))
                    elif m.get("role") == "function":
                        transcript.append("tool_result " + json.dumps(m["response"])[:400])
                    elif m.get("role") == "user":
                        txt = next((c["text"] for c in m["content"] if "text" in c), "")
                        transcript.append("observation " + txt[:1500])
                users = [m for m in self.history if m.get("role") == "user"]
                parts = [{"text": "Transcript of this episode so far (oldest first):\n" + "\n".join(transcript[:-1])}] if len(transcript) > 1 else []
                if len(users) >= 2:
                    parts += [{"text": "Previous observation images:"}] + [c for c in users[-2]["content"] if "inline_data" in c]
                parts += [{"text": "Current observation:"}] + users[-1]["content"]
                contents = [{"role": "user", "parts": parts}]
            else:
                for m in self.history:
                    if m.get("role") == "user":
                        contents.append({"role": "user", "parts": m["content"]})
                    elif m.get("role") == "model":
                        parts = m["parts"] if mode == "full" else [{k: v for k, v in pt.items() if k != "thoughtSignature"} for pt in m["parts"]]
                        contents.append({"role": "model", "parts": parts})
                    elif m.get("role") == "function":
                        contents.append({"role": "user", "parts": [{"functionResponse": {"name": m["name"], "response": m["response"]}}]})
                merged = []                      # Merge function responses and the next observation into one user turn.
                for c in contents:
                    if merged and merged[-1]["role"] == "user" and c["role"] == "user":
                        merged[-1]["parts"] = merged[-1]["parts"] + c["parts"]
                    else:
                        merged.append({"role": c["role"], "parts": list(c["parts"])})
                contents = merged
            def _gschema(o):   # Adapt the tool schema to the provider-supported subset.
                if isinstance(o, dict):
                    r = {}
                    for k, v in o.items():
                        if k in ("additionalProperties", "minItems", "maxItems"): continue
                        r[k] = _gschema(v)
                    return r
                if isinstance(o, list): return [_gschema(x) for x in o]
                return o
            decls = [{"name": t["name"], "description": t["description"] + (" position is [x,y,z] (3 numbers); quaternion_wxyz is [w,x,y,z] (4 numbers)." if t["name"] == "move_eef" else ""), "parameters": _gschema(t["parameters"])} for t in TOOLS]
            return ({"system_instruction": {"parts": [{"text": PROMPT}]}, "contents": contents,
                     "tools": [{"functionDeclarations": decls}],
                     "toolConfig": {"functionCallingConfig": {"mode": "ANY"}},
                     "generationConfig": {"maxOutputTokens": self.max_output_tokens, "thinkingConfig": {"thinkingLevel": self.effort.upper()}}}, h)
        # Anthropic thinking uses automatic tool choice with a prompt constraint.
        tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in TOOLS]
        h["anthropic-version"] = "2023-06-01"
        # Cache stable text history and the current turn; preserve the content seen by the model.


        cc = {"type": "ephemeral"}
        tools[-1] = dict(tools[-1], cache_control=cc)
        system = [{"type": "text", "text": PROMPT, "cache_control": cc}]
        messages = [dict(m) for m in self.history]
        user_idx = [i for i, m in enumerate(messages)
                    if m.get("role") == "user" and isinstance(m.get("content"), list) and m["content"]]

        def _has_img(blocks):
            return any(b.get("type") == "image" or (b.get("type") == "tool_result" and isinstance(b.get("content"), list) and _has_img(b["content"]))
                       for b in blocks)
        img_idx = [i for i in user_idx if _has_img(messages[i]["content"])]
        before = [i for i in user_idx if img_idx and i < img_idx[0]]
        for i in {user_idx[-1]} | ({before[-1]} if before else set()):
            blocks = list(messages[i]["content"])
            blocks[-1] = dict(blocks[-1], cache_control=cc)
            messages[i] = dict(messages[i], content=blocks)
        return ({"model": self.model, "system": system, "messages": messages, "tools": tools,
                 "tool_choice": {"type": "auto"}, "thinking": {"type": "adaptive"},
                 "output_config": {"effort": self.effort}, "max_tokens": self.max_output_tokens}, h)

    def _parse_tool_call(self, result):
        """Return the parsed tool call and the assistant output retained in history."""
        if self.provider == "responses":
            output = result.get("output", [])
            fns = [x for x in output if x.get("type") == "function_call"]
            if len(fns) != 1:
                raise ValueError("API did not return exactly one action")
            c = fns[0]
            return {"name": c["name"], "arguments": json.loads(c["arguments"]), "id": c["call_id"]}, output
        if self.provider == "chat":
            msg = result["choices"][0]["message"]
            tcs = msg.get("tool_calls") or []
            if len(tcs) != 1:
                raise ValueError("API did not return exactly one action")
            c = tcs[0]["function"]
            assistant = dict(msg)                      # Preserve provider-specific signature fields in the original message.
            assistant["role"] = "assistant"
            if assistant.get("content") is None:
                assistant["content"] = ""
            return {"name": c["name"], "arguments": json.loads(c["arguments"] or "{}"), "id": tcs[0]["id"]}, assistant
        if self.provider == "gemini":
            cand = (result.get("candidates") or [{}])[0]
            parts = (cand.get("content") or {}).get("parts") or []
            fcs = [pt for pt in parts if "functionCall" in pt]
            if len(fcs) != 1:
                raise ValueError("API did not return exactly one action")
            fc = fcs[0]["functionCall"]
            return {"name": fc["name"], "arguments": fc.get("args") or {}, "id": None}, {"role": "model", "parts": parts}
        blocks = result.get("content") or []
        tus = [b for b in blocks if b.get("type") == "tool_use"]
        if len(tus) != 1:
            raise ValueError("API did not return exactly one action")
        c = tus[0]
        # Retain signed thinking blocks.
        return {"name": c["name"], "arguments": c.get("input") or {}, "id": c["id"]}, {"role": "assistant", "content": blocks}

    def _append_history(self, output, call, tool_result):
        if self.provider == "responses":
            self.history.extend(output)
            self.history.append({"type": "function_call_output", "call_id": call["id"], "output": tool_result})
        elif self.provider == "chat":
            self.history.append(output)
            self.history.append({"role": "tool", "tool_call_id": call["id"], "content": tool_result})
        elif self.provider == "gemini":
            self.history.append(output)
            self.history.append({"role": "function", "name": call["name"], "response": json.loads(tool_result)})
        else:
            self.history.append(output)
            self.history.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": call["id"], "content": tool_result}]})

    def _usage(self, u):
        if self.provider == "responses":
            return {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
                    "reasoning_tokens": (u.get("output_tokens_details") or {}).get("reasoning_tokens"),
                    "cached_input_tokens": (u.get("input_tokens_details") or {}).get("cached_tokens")}
        if self.provider == "chat":
            return {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
                    "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                    "cached_input_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens")}
        if self.provider == "gemini":
            return {"input_tokens": u.get("promptTokenCount"), "output_tokens": u.get("candidatesTokenCount"),
                    "reasoning_tokens": u.get("thoughtsTokenCount"), "cached_input_tokens": u.get("cachedContentTokenCount")}
        return {"input_tokens": u.get("input_tokens"), "output_tokens": u.get("output_tokens"),
                "reasoning_tokens": None, "cached_input_tokens": u.get("cache_read_input_tokens")}

    def infer(self, obs):
        if self.calls >= self.max_calls:
            return {"type": "finish", "note": "local API call budget exhausted"}
        # Select fields explicitly: never forward arbitrary remote request fields.
        text = {"instruction": obs["instruction"], "eef_state": obs["eef_state"],
                "joint_state": obs.get("joint_state"), "feedback": obs.get("feedback"),
                "step": obs.get("step"), "contact_feedback": obs.get("contact_feedback")}
        content = [self._text_block(json.dumps(text))]
        for name, encoded in obs["images"].items():
            if name not in ("head_camera", "left_camera", "right_camera"):
                raise ValueError("unexpected camera")
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > 4_000_000 or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("expected a bounded PNG")
            frame_dir = self.log_dir / "frames" / f"ep{getattr(self, 'episode', 0):04d}" / f"{self.calls + 1:03d}"
            frame_dir.mkdir(parents=True, exist_ok=True)
            (frame_dir / (name + ".png")).write_bytes(raw)
            content += self._image_blocks(name, encoded)
        # Retain the last two visual observations, keep the full textual history.
        seen = 0
        for item in reversed(self.history):
            if item.get("role") == "user":
                seen += 1
                if seen >= 2:
                    item["content"] = [c for c in item["content"] if c.get("type") not in ("input_image", "image_url", "image") and "inline_data" not in c]
                    for c in item["content"]:      # Strip old images nested in tool-result content.
                        if c.get("type") == "tool_result" and isinstance(c.get("content"), list):
                            c["content"] = [b for b in c["content"] if b.get("type") != "image"]
        last = self.history[-1] if self.history else None
        if (self.provider == "anthropic" and last and last.get("role") == "user"
                and len(last["content"]) == 1 and last["content"][0].get("type") == "tool_result"):
            # Combine tool results and observations in a single user message for caching.

            last["content"] = last["content"] + content
        else:
            self.history.append({"role": "user", "content": content})
        payload, headers = self._build_payload()
        req = Request(self.endpoint, data=json.dumps(payload).encode(), headers=headers)
        self.calls += 1
        started = time.monotonic()
        result = None
        if QUOTA_STOP.exists():
            raise RuntimeError("quota exhausted; API calls stopped (" + str(QUOTA_STOP) + ")")
        for attempt in range(3):                      # Retry transient HTTP/transport errors with bounded backoff.
            try:
                from policy.GPT6.budget import reserve, settle
                _reservation = reserve(self.model)
                with self.opener.open(req, timeout=600) as response:
                    result = json.load(response)
                settle(_reservation, result)
                break
            except HTTPError as e:
                body = ""
                try: body = e.read().decode()[:300].replace(self.key, "[REDACTED]")
                except Exception: pass
                if e.code == 402 or any(code in body.lower() for code in ("insufficient_quota", "billing_hard_limit_reached", "quota_exhausted")):
                    QUOTA_STOP.write_text(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "message": body[:200]}, ensure_ascii=False))
                    print("QUOTA EXHAUSTED: stop marker written, no further API calls", flush=True)
                    raise RuntimeError("quota exhausted")
                if attempt < 2 and e.code in (400, 408, 429, 500, 502, 503, 504):
                    print(f"API HTTP {e.code} on attempt {attempt+1}, retrying: {body[:200]}", flush=True)
                    if self.provider == "gemini" and e.code == 400 and "signature" in body.lower():
                        self._gemini_mode = {"full": "nosig", "nosig": "stateless"}.get(getattr(self, "_gemini_mode", "full"), "stateless")
                        print(f"Gemini signature rejected; retry mode: {self._gemini_mode}", flush=True)
                        payload, headers = self._build_payload()
                        req = Request(self.endpoint, data=json.dumps(payload).encode(), headers=headers)
                    time.sleep(5 * (attempt + 1)); continue
                raise
            except (TimeoutError, OSError) as e:
                if attempt < 2:
                    print(f"API timeout/OS error on attempt {attempt+1}, retrying: {type(e).__name__}", flush=True)
                    time.sleep(5 * (attempt + 1)); continue
                raise
        if self.provider == "gemini":
            self._gemini_mode = "full"
        if result is None:
            raise RuntimeError("no result")
        call, output = self._parse_tool_call(result)
        args = call["arguments"]
        if call["name"] == "move_eef":
            try:
                action = {"type": "move_eef", **validate_move(args, obs["eef_state"])}
            except ValueError as exc:
                action = {"type": "rejected", "note": str(exc)}
        elif call["name"] == "finish":
            action = {"type": "finish", "note": str(args.get("note", ""))}
        else:
            raise ValueError("unexpected action tool")
        tool_result = json.dumps({"status": action["type"],
                                  "detail": "Movement, if accepted, is dispatched to the simulator. Next observation reports actual outcome.",
                                  "note": action.get("note", "")})
        self._append_history(output, call, tool_result)
        record = {"pilot_meta": obs.get("pilot_meta"), "episode": getattr(self,"episode",0), "call": self.calls, "model": self.model, "returned_model": result.get("model") or result.get("modelVersion"), "api_seconds": time.monotonic()-started,
                  "observation": text, "action": action, "usage": result.get("usage") or result.get("usageMetadata")}
        # Only a selected record is persisted, never headers, config, or raw API responses.
        safe = json.dumps(record, ensure_ascii=False).replace(self.key, "[REDACTED]")
        with (self.log_dir / "decisions.jsonl").open("a") as f:
            f.write(safe + "\n")
        action = dict(action); action["api_seconds"] = record["api_seconds"]
        action["usage"] = self._usage(result.get("usage") or result.get("usageMetadata") or {})
        return json.loads(json.dumps(action).replace(self.key, "[REDACTED]"))


class ReplayBridge:
    """Replay saved tool actions for judging diagnostics; no external API call."""
    def __init__(self, source, log_dir):
        self.rows = [json.loads(line) for line in Path(source).read_text().splitlines()]
        self.calls = 0
        self.history = []
        self.log_dir = Path(log_dir)

    def infer(self, obs):
        if self.calls >= len(self.rows):
            return {"type": "finish", "note": "replay exhausted"}
        row = self.rows[self.calls]
        action = dict(row['action'])
        if 'relative_translation' in row:
            arm = action['arm']; current = obs['eef_state'][arm+'_endpose']
            action.update(position=[x+d for x,d in zip(current[:3],row['relative_translation'])],
                          quaternion_wxyz=current[3:7],gripper=obs['eef_state'][arm+'_gripper'])
        difference = max(abs(a-b) for side in ("left", "right")
                         for a,b in zip(obs["eef_state"][side+"_endpose"], row["observation"]["eef_state"][side+"_endpose"]))
        self.calls += 1
        with (self.log_dir/"replay.jsonl").open("a") as f:
            f.write(json.dumps({"call": self.calls, "eef_max_abs_difference_from_original": difference,
                                "action": action, "api_calls": 0,
                                "observation": {k: obs.get(k) for k in ("eef_state", "feedback", "contact_feedback")}})+"\n")
        return action


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-actions")
    parser.add_argument("--config", required=True, help="Local JSON: base_url, api_key_file, model, reasoning_effort")
    parser.add_argument("--token-file", required=True, help="Separate tunnel token, NOT the API key")
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--port", type=int, default=18766)
    parser.add_argument("--max-calls", type=int, default=40)
    args = parser.parse_args()
    QUOTA_STOP.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(args.config).read_text())
    key_path = Path(config["api_key_file"]).expanduser()
    if key_path.stat().st_mode & 0o077:
        raise ValueError("API key file must only be readable by its owner (chmod 600)")
    key = key_path.read_text().strip()
    if not key or "\n" in key:
        raise ValueError("API key file must contain one nonempty line")
    bridge = ReplayBridge(args.replay_actions, args.log_dir) if args.replay_actions else Bridge(config, key, args.log_dir, args.max_calls)
    token = secrets.token_urlsafe(32)
    fd = os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 16_000_000:
                    raise ValueError("invalid request size")
                body = json.loads(self.rfile.read(length))
                if self.path == "/reset":
                    bridge.history = []; bridge.calls = 0; bridge.episode = getattr(bridge, "episode", 0) + 1
                    bridge.cache_key = "ep-" + secrets.token_hex(6)
                    result = {"ok": True}
                elif self.path == "/infer":
                    result = bridge.infer(body)
                else:
                    self.send_error(404)
                    return
                data = json.dumps(result).encode()
                self.send_response(200)
            except Exception as e:
                reason = str(e) if isinstance(e, (ValueError, RuntimeError)) else type(e).__name__
                print("Bridge request failed:", reason.replace(key, "[REDACTED]"), flush=True)
                data = json.dumps({"error": type(e).__name__}).encode()
                self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        print("Local bridge ready on loopback; credentials will not be logged.", flush=True)
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
