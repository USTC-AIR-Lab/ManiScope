# Language-following diagnostics

These scripts test whether a policy's choices follow the instruction, not only whether it completes the task.
They run on any checkpoint registered in `suite/policies.yaml` with the same evaluator, seed-file format
and server contract as the formal benchmark. The paper's numbers use the organizers' formal seed lists;
with development seeds from `suite/gen_seeds.py` (see `suite/seeds/README.md`) the same diagnostics run on
other initial states. The two model-access probes in `probes/` need access to the
model internals and are implemented for Motus.

| Diagnostic | Paper | Run | Analyse |
| --- | --- | --- | --- |
| Selection events: first contact, first 5 cm displacement, gripper-state contact class (grasp / push / brush) | Sec. 5.2, App. D.5 | `run_diagnostic.py run selection_events` | `analysis/selection_events.py` |
| Failure decomposition by displaced objects | Sec. 5.2, App. D.6 | formal run (`suite/run_suite.sh`) | `analysis/failure_decomposition.py` |
| Target reassignment (instruction rotation) on held-out scenes, with the instruction-blind reference | Sec. 5.3, App. G.2 | `run_diagnostic.py run rotation` | `analysis/rotation.py` |
| Control 1: instruction change on unmodified RoboTwin training tasks | App. G.3 | `run_diagnostic.py run training_control` | `analysis/controls.py` |
| Control 2: source-task baseline | App. G.3 | `run_diagnostic.py run source_baseline` | `analysis/controls.py` |
| First-decision sensitivity (instruction, layout, sampling noise) | App. E | `run_diagnostic.py run first_decision` | `analysis/first_decision.py` |
| Paired instruction x layout study, future-video readout, internal K/V intervention | Sec. 5.3, App. E.1-E.3 | `probes/` | `probes/` |
| Example remedies: language guidance and agent-selection relay | App. G.4 | `remedies/` | `analysis/rotation.py` |

## Setup

Install the benchmark as described in the top-level README (`configs/local.env`, RoboTwin assets, the
backend of the policy to test), then create the instrumented evaluator once:

```bash
python3 diagnostics/make_eval_diagnostic.py .     # writes script/eval_diagnostic.py from script/eval_policy.py
```

`script/eval_diagnostic.py` is `script/eval_policy.py` plus hooks that are inactive unless their environment
variable is set (instruction override, target reassignment, object-pose exchange, per-episode JSONL record,
gripper-state tracking, first-chunk recording); see the docstring of `make_eval_diagnostic.py`. A pre-generated
copy is included.

## Running

```bash
# list the jobs of a diagnostic (conditions in diagnostics/conditions.py)
python3 diagnostics/run_diagnostic.py plan rotation

# run against a server that already listens on the registry port of the policy
python3 diagnostics/run_diagnostic.py run rotation --policy dm05 --gpu 0

# or let the runner start the registry launcher (suite/launch/*.sh) with configs/local.env
python3 diagnostics/run_diagnostic.py run rotation         --policy dm05 --gpu 0 --start-server
python3 diagnostics/run_diagnostic.py run training_control --policy dm05 --gpu 0 --start-server
python3 diagnostics/run_diagnostic.py run source_baseline  --policy dm05 --gpu 0 --start-server   # --extra: all 30 linked tasks
python3 diagnostics/run_diagnostic.py run selection_events --policy dm05 --gpu 0 --start-server
python3 diagnostics/run_diagnostic.py run first_decision   --policy dm05 --gpu 0 --start-server
```

Results go to `runs/diagnostics/<diagnostic>/<policy>/<task>/<job>/probe.jsonl`, one JSON record per episode
(instruction, reassigned target, first displaced object, per-object maximum displacement and rise, success,
and, where enabled, gripper-state classes or the first action chunk). Finished jobs are skipped on re-run.
For a checkpoint conditioned on task names instead of instructions, add `--task-name-instruction` to
`source_baseline`.

## Analysis

```bash
python3 diagnostics/analysis/rotation.py         runs/diagnostics/rotation
python3 diagnostics/analysis/controls.py         runs/diagnostics/training_control
python3 diagnostics/analysis/controls.py         runs/diagnostics/source_baseline
python3 diagnostics/analysis/selection_events.py runs/diagnostics/selection_events
python3 diagnostics/analysis/first_decision.py   runs/diagnostics/first_decision --out first_decision_summary
python3 diagnostics/analysis/failure_decomposition.py dm05=eval_result/<formal run of dm05> pi05=...
```

Definitions used by the scripts:

- **Selection (displacement event).** The first candidate displaced at least 5 cm from its initial position
  (`CompoScene.MOVED_EPS`; `first_moved` in the record).
- **Target reassignment classes.** On each frozen initial state, the k instructions of a scene are run with
  the target reassigned to the named candidate. The state is *follow* if every instruction selects its own
  target, *fixed* if all select the same candidate, *no move* if none displaces a candidate, *mixed*
  otherwise. The instruction-blind reference picks uniformly among the k candidates: follow k^-k, fixed
  k^(1-k). The empty-instruction runs give the instruction-independent preference.
- **Gripper-state contact classes** (`grip_tracker.py`). *grasp*: two gripper links of one arm in contact
  with the object while that gripper is closed (finger aperture <= 0.9) for at least 3 consecutive samples
  and the object moves >= 2 cm within that run; *push*: not grasp and displaced >= 5 cm; *brush*: touched by
  any robot link otherwise.
- **Failure decomposition.** Formal-run failures on the eleven selection scenes, split into distractor only /
  target only / both / neither displaced >= 5 cm.
- **First-decision sensitivity.** RMS difference of the first 16 commanded arm-joint targets (12 joints,
  grippers excluded) between paired episodes from the same frozen state that differ in instruction, layout
  (red and blue blocks exchanged) or only the sampling repeat (the noise floor).

## Model-access probes

`probes/` contains the paired instruction x layout study for pi0.5 and Motus, the future-video readout of
Motus forecasts, and the internal key/value intervention at the Motus action-attention interface. See
[`probes/README.md`](probes/README.md).

## Example remedies (Appendix G.4)

- **Language guidance** (`remedies/language_guidance/`): DM0.5 with classifier-free-style guidance at inference
  time, v = v_empty + w (v_instruction - v_empty), both branches starting from the same noise. Start the server
  with `PROBE_CFG_W=<w> bash diagnostics/remedies/language_guidance/start_dm05_cfg.sh` (same environment as
  `suite/launch/start_dm05.sh`), then run `rotation` against it.
- **Agent-selection relay** (`remedies/relay/`): the GPT-6 agent identifies the requested object and brings an
  open gripper around it at grasp height; DM0.5 then completes the episode with the original instruction.
  Link the policy adapter once with `ln -s ../diagnostics/remedies/relay/policy policy/Relay`, start the agent
  bridge `python3 diagnostics/remedies/relay/relay_bridge.py --config <provider.json> --token-file <file>
  --log-dir <dir> --port <port>` (see `docs/EXTERNAL_AGENT.md`; the API key is read from the file named in
  `provider.json`), start a DM0.5 server, and set `RELAY_VLA_URL=http://127.0.0.1:<dm05 port>` for the
  evaluator.
