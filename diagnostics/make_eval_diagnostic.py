"""Create script/eval_diagnostic.py from script/eval_policy.py without modifying the original.

Hooks (all inactive unless the corresponding environment variable is set):
  PROBE_INSTRUCTION   replaces the sampled instruction (empty string allowed).
  PROBE_TARGET_ROLE   reassigns CompoScene.TARGET after the initial state is built.
  PROBE_ROLES         JSON {role: attribute} for native RoboTwin tasks; tracks displacement per role.
  PROBE_LOG           JSONL path; one record per episode.
  PROBE_CONDITION     free-form condition label copied into the record.
  PROBE_SEED_OFFSET   skips this many frozen seeds, so episode chunks cover disjoint initial states.
  PROBE_GRIP          gripper-state contact classification (diagnostics/grip_tracker.py).
  PROBE_SWAP          "roleA,roleB": exchange the two objects' poses after the initial state is built.
  PROBE_FIRST_CHUNK   N: record whole action chunks (commands and joint states) until at least N commands,
                      then end the episode; 1 = the first chunk only.
  PROBE_EXP, PROBE_CFG_W  copied into the record as exp and w; model.relay (diagnostics/remedies) is
                      copied as relay.
Usage: python diagnostics/make_eval_diagnostic.py [repository root]
"""
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
src = (root / "script/eval_policy.py").read_text()
dst = root / "script/eval_diagnostic.py"

anchor_instr = "        TASK_ENV.set_instruction(instruction=instruction)  # set language instruction\n"
anchor_step = "            eval_func(TASK_ENV, model, observation)\n"
anchor_log = "        # Record minimum contact distance, which a binary success flag does not expose.\n"
anchor_seed_check = "            if len(frozen_seeds) < test_num:\n"
anchor_seed_slice = "            frozen_seeds = frozen_seeds[:test_num]\n"
for a in (anchor_instr, anchor_step, anchor_log, anchor_seed_check, anchor_seed_slice):
    assert src.count(a) == 1, a
# With frozen seeds and an injected instruction, the expert replay only fills instruction
# placeholders that are then overwritten, so it is skipped.
anchor_expert = "    expert_check = True\n"
anchor_info = '        episode_info_list = [episode_info["info"]]\n'
anchor_desc = ('        results = generate_episode_descriptions(args["task_name"], episode_info_list, test_num)\n'
               '        instruction = np.random.RandomState(int(now_seed)).choice(results[0][instruction_type])\n')
for a in (anchor_expert, anchor_info, anchor_desc):
    assert src.count(a) == 1, a
src = src.replace(anchor_expert, '    expert_check = not (os.environ.get("PROBE_INSTRUCTION") is not None\n'
                                 '                        and os.environ.get("ROBOTWIN_FROZEN_SEEDS", "1") != "0")\n')
src = src.replace(anchor_info, '        if expert_check:\n    ' + anchor_info)
src = src.replace(anchor_desc, '        if expert_check:\n' + "".join("    " + l + "\n" for l in anchor_desc.splitlines())
                  + '        else:\n            instruction = os.environ["PROBE_INSTRUCTION"]\n')
src = src.replace(anchor_seed_check,
                  '            _probe_off = int(os.environ.get("PROBE_SEED_OFFSET", "0"))\n'
                  '            frozen_seeds = frozen_seeds[_probe_off:]\n' + anchor_seed_check)

hook_instr = anchor_instr + '''        if os.environ.get("PROBE_SWAP"):
            # exchange the poses of two objects; the scene's displacement baselines follow the new poses
            _ra, _rb = os.environ["PROBE_SWAP"].split(",")
            _xa, _xb = TASK_ENV._actors[_ra], TASK_ENV._actors[_rb]
            _pa, _pb = _xa.get_pose(), _xb.get_pose()
            _xa.actor.set_pose(_pb)
            _xb.actor.set_pose(_pa)
            TASK_ENV._p0 = {k: np.asarray(v.get_pose().p).copy() for k, v in TASK_ENV._actors.items()}
            TASK_ENV._maxdisp = {k: 0.0 for k in TASK_ENV._actors}
            TASK_ENV._maxz = {k: float(p[2]) for k, p in TASK_ENV._p0.items()}
            if hasattr(TASK_ENV, "_bottom0"):
                from envs._placement_judge import world_bounds as _pwb
                TASK_ENV._bottom0 = {k: float(_pwb(v)[0][2]) for k, v in TASK_ENV._actors.items()}
        _probe_tracker = None
        if os.environ.get("PROBE_INSTRUCTION") is not None:
            instruction = os.environ["PROBE_INSTRUCTION"]
            TASK_ENV.set_instruction(instruction=instruction)
        _probe_role = os.environ.get("PROBE_TARGET_ROLE")
        if _probe_role:
            if _probe_role not in getattr(TASK_ENV, "_actors", {}):
                raise ValueError("PROBE_TARGET_ROLE %r not in scene roles %r"
                                 % (_probe_role, sorted(getattr(TASK_ENV, "_actors", {}))))
            TASK_ENV.TARGET = _probe_role
        if os.environ.get("PROBE_ROLES"):
            import json as _pjson
            _probe_tracker = {"actors": {r: getattr(TASK_ENV, a) for r, a in
                                         _pjson.loads(os.environ["PROBE_ROLES"]).items()}}
            _probe_tracker["p0"] = {r: np.asarray(v.get_pose().p, dtype=float).copy()
                                    for r, v in _probe_tracker["actors"].items()}
            _probe_tracker["maxdisp"] = {r: 0.0 for r in _probe_tracker["actors"]}
            _probe_tracker["maxz"] = {r: float(p[2]) for r, p in _probe_tracker["p0"].items()}
            _probe_tracker["first_moved"] = None
            _probe_tracker["first_moved_step"] = None
        _probe_grip = None
        if os.environ.get("PROBE_GRIP"):
            # Gripper-state classification of every tracked object (diagnostics/grip_tracker.py), sampled
            # after each environment action.
            import sys as _psys
            _ptools = os.environ.get("PROBE_TOOLS") or os.path.join(os.getcwd(), "diagnostics")
            if _ptools not in _psys.path:
                _psys.path.insert(0, _ptools)
            from grip_tracker import GripTracker as _GripTracker
            _grip_actors = (_probe_tracker["actors"] if _probe_tracker is not None
                            else dict(getattr(TASK_ENV, "_actors", None) or getattr(TASK_ENV, "objects", None) or {}))
            _probe_grip = _GripTracker(TASK_ENV, _grip_actors)
            if not hasattr(TASK_ENV, "_probe_orig_take_action"):
                TASK_ENV._probe_orig_take_action = TASK_ENV.take_action

            def _probe_take_action(*_a, _g=_probe_grip, _f=TASK_ENV._probe_orig_take_action, **_k):
                _r = _f(*_a, **_k)
                _g.sample()
                return _r
            TASK_ENV.take_action = _probe_take_action
        _probe_chunk = None
        if os.environ.get("PROBE_FIRST_CHUNK"):
            # Record the commands and the measured 14-d joint vector (arms + grippers) for every command
            # of the first decisions that produce actions; the episode ends at the first decision boundary
            # with at least PROBE_FIRST_CHUNK commands recorded.
            _probe_chunk = {"commands": [], "joints": [], "action_type": None, "done": False,
                            "min": int(os.environ["PROBE_FIRST_CHUNK"])}
            _pf0 = TASK_ENV.take_action
            _pf0 = getattr(_pf0, "_probe_inner", _pf0)

            def _probe_chunk_take_action(action, *_a, _c=_probe_chunk, _f=_pf0, **_k):
                _r = _f(action, *_a, **_k)
                if not _c["done"]:
                    _c["commands"].append(np.asarray(action, dtype=float).tolist())
                    _c["action_type"] = _k.get("action_type", _a[0] if _a else "qpos")
                    _c["joints"].append([float(x) for x in list(TASK_ENV.robot.get_left_arm_jointState())
                                         + list(TASK_ENV.robot.get_right_arm_jointState())])
                return _r
            _probe_chunk_take_action._probe_inner = _pf0
            TASK_ENV.take_action = _probe_chunk_take_action
'''

hook_step = anchor_step + '''            if _probe_chunk is not None and not _probe_chunk["done"] and len(_probe_chunk["commands"]) >= _probe_chunk["min"]:
                _probe_chunk["done"] = True
                TASK_ENV.take_action_cnt = TASK_ENV.step_lim
            if _probe_tracker is not None:
                for _r, _a in _probe_tracker["actors"].items():
                    _pp = np.asarray(_a.get_pose().p, dtype=float)
                    _probe_tracker["maxdisp"][_r] = max(_probe_tracker["maxdisp"][_r],
                                                        float(np.linalg.norm(_pp - _probe_tracker["p0"][_r])))
                    _probe_tracker["maxz"][_r] = max(_probe_tracker["maxz"][_r], float(_pp[2]))
                if _probe_tracker["first_moved"] is None:
                    _mv = [r for r, d in _probe_tracker["maxdisp"].items() if d > 0.05]
                    if _mv:
                        _probe_tracker["first_moved"] = max(_mv, key=lambda r: _probe_tracker["maxdisp"][r])
                        _probe_tracker["first_moved_step"] = int(TASK_ENV.take_action_cnt)
'''

hook_log = '''        if os.environ.get("PROBE_LOG"):
            try:
                import json as _pjson
                if _probe_tracker is not None:
                    _md, _mz, _p0 = _probe_tracker["maxdisp"], _probe_tracker["maxz"], _probe_tracker["p0"]
                    _fm, _fms = _probe_tracker["first_moved"], _probe_tracker["first_moved_step"]
                else:
                    _md = getattr(TASK_ENV, "_maxdisp", {}) or {}
                    _mz = getattr(TASK_ENV, "_maxz", {}) or {}
                    _p0 = getattr(TASK_ENV, "_p0", {}) or {}
                    _fm, _fms = getattr(TASK_ENV, "_first_moved", None), None
                _rec = {
                    "task": task_name, "policy": args["policy_name"], "ckpt": args["ckpt_setting"],
                    "episode": succ_seed - 1, "seed": int(now_seed),
                    "condition": os.environ.get("PROBE_CONDITION", ""),
                    "target_role": getattr(TASK_ENV, "TARGET", None), "instruction": instruction,
                    "success": bool(succ), "first_moved": _fm, "first_moved_step": _fms,
                    "maxdisp": {k: float(v) for k, v in _md.items()},
                    "rise": {k: float(_mz[k]) - float(_p0[k][2]) for k in _mz if k in _p0},
                    "steps": int(getattr(TASK_ENV, "take_action_cnt", 0)),
                    "step_lim": int(getattr(TASK_ENV, "step_lim", 0) or 0),
                    "wall": time.time() - _t_ep0,
                }
                if os.environ.get("PROBE_EXP"):
                    _rec["exp"] = os.environ["PROBE_EXP"]
                if os.environ.get("PROBE_CFG_W"):
                    _rec["w"] = float(os.environ["PROBE_CFG_W"])
                if getattr(model, "relay", None) is not None:
                    _rec["relay"] = model.relay
                if _probe_chunk is not None:
                    _rec["first_chunk"] = {k: v for k, v in _probe_chunk.items() if k != "done"}
                if _probe_grip is not None:
                    _rec["grip"] = _probe_grip.summary()
                    _dr = getattr(TASK_ENV, "_distractor_roles", None)
                    if callable(_dr):
                        _rec["distractor_roles"] = sorted(_dr())
                    elif "target" in _rec["grip"]["objects"]:  # scenes that keep a plain {role: actor} dict
                        _rec["distractor_roles"] = sorted(k for k in _rec["grip"]["objects"] if k != "target")
                        _rec["target_role"] = _rec["target_role"] or "target"
                    else:
                        _rec["distractor_roles"] = None
                with open(os.environ["PROBE_LOG"], "a", encoding="utf-8") as _pf:
                    _pf.write(_pjson.dumps(_rec) + "\\n")
            except Exception as _pe:
                print("[probe] log failed:", repr(_pe))

''' + anchor_log

out = src.replace(anchor_instr, hook_instr).replace(anchor_step, hook_step).replace(anchor_log, hook_log)
if dst.exists() and dst.read_text() != out:
    print("overwriting existing", dst)
dst.write_text(out)
print("wrote", dst)
