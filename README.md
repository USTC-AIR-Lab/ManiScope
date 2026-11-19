# ManipScope

An evaluation-only diagnostic benchmark for robotic instruction following under changed task requirements,
built on RoboTwin 2.0 simulation resources. ManipScope separates the simulation/evaluation loop from model
inference adapters. The bundled **formal48-v1** suite contains **48 held-out scenes** with **100 frozen
initial states per scene** in six task families: D1 skill-object transfer, D2 skill-spatial transfer,
D3 attribute selection, D4 referring expressions, D5 skill sequences, and D6 mixed combinations. Each scene
is linked to the RoboTwin 2.0 source tasks it derives from. Policies are trained on unmodified RoboTwin 2.0
demonstrations; no demonstrations of the 48 evaluation scenes are provided.

Beyond task success, [`diagnostics/`](diagnostics/README.md) tests whether a policy's choices follow the
instruction: selection events and contact classes, failure decomposition, target reassignment on frozen
initial states with its two controls, first-decision sensitivity, and the future-video and internal
key/value probes for models that expose them.

![48 formal scenes](docs/images/formal48-overview.png)

## Quick start

Use Linux with a compatible NVIDIA driver and an isolated simulation environment.
Model checkpoints and RoboTwin assets are external downloads, not part of this repository.

```bash
python3 -m pip install -r requirements/dev.txt
python3 tools/validate_repo.py
python3 -m pytest -q tests
cp configs/local.env.example configs/local.env
# Edit configs/local.env for your machine and selected backend.
python3 tools/link_assets.py /absolute/path/to/robotwin_assets
# Formal seed lists are held by the organizers; generate development seeds (suite/seeds/README.md):
python suite/gen_seeds.py move_can_coaster 100
# Validate inputs without starting a simulation or model:
DRY_RUN=1 bash suite/run_suite.sh dm05 move_can_coaster
# After installing opendm and setting DM05_MODEL, OPENDM_DIR, OPENDM_ENV:
EPISODES=1 RUN_NAME=smoke_dm05 bash suite/run_suite.sh dm05 move_can_coaster
```

To evaluate a new model or system, start with the development set and the submission process in
[docs/SUBMISSIONS.md](docs/SUBMISSIONS.md): `DRY_RUN=1 bash suite/run_dev_check.sh <policy_key>`.

See [installation](docs/INSTALLATION.md) before the first simulation run.
A dry run checks configuration and benchmark inputs; it does not check GPU compatibility.
**Validation status:** CPU checks pass, including a clean clone. GPU rendering depends on the local driver
and Vulkan setup; see [the validation record](docs/NORMALIZATION.md) before running or reporting benchmark
results.

## Evaluation contract

- Runner default: 50 episodes per scene, `demo_clean`, unseen instructions. The reported policy results use
  all 100 frozen initial states per scene (`EPISODES=100`); agents use the first 5.
- Frozen seeds are used in file order; requesting more seeds than available fails early. The formal seed
  lists are held by the organizers (digests in `protocol.lock.json`); a formal scene without a seed file
  is refused. Use `suite/gen_seeds.py` for development seeds, whose results are not leaderboard results.
- Each seed determines the instruction sampling. Actual instructions are recorded.
- The first 10 evaluated seeds are eligible for head-camera video, independent of outcome.
  Set `ROBOTWIN_VIDEO_FIRST_N`; `MAX_SUCC_VIDEOS`/`MAX_FAIL_VIDEOS` are additional caps.
- Generated scenes check target selection, goal completion, and reference-object stability.
  Handwritten scenes retain their task-specific criteria.
- A common evaluator does not imply identical action spaces, inference budgets, or training data.
  Report these alongside success rates; see [evaluation](docs/EVALUATION.md).
- The checked-in scene implementations and `suite/scenes_v2.yaml` define this frozen release.
  Generators produce development candidates under `out/`; do not blindly replace the release.

## Language-following diagnostics

Run on any registered policy with the same evaluator and frozen initial states (details, definitions and
the probe instructions: [diagnostics/README.md](diagnostics/README.md)).

| Diagnostic | Paper section | Command |
| --- | --- | --- |
| Selection events (first contact, first 5 cm displacement, grasp / push / brush contact classes) | 5.2, App. D.5 | `python3 diagnostics/run_diagnostic.py run selection_events --policy <p> --start-server` |
| Failure decomposition by displaced objects | 5.2, App. D.6 | `python3 diagnostics/analysis/failure_decomposition.py <p>=<formal run dir>` |
| Target reassignment (instruction rotation) with the instruction-blind reference | 5.3, App. G.2 | `python3 diagnostics/run_diagnostic.py run rotation --policy <p> --start-server` |
| Instruction change on unmodified RoboTwin training tasks | App. G.3 | `python3 diagnostics/run_diagnostic.py run training_control --policy <p> --start-server` |
| Source-task baseline | App. G.3 | `python3 diagnostics/run_diagnostic.py run source_baseline --policy <p> --start-server` |
| First-decision sensitivity | App. E | `python3 diagnostics/run_diagnostic.py run first_decision --policy <p> --start-server` |
| Future-video readout and internal K/V intervention (Motus) | 5.3, App. E.2-E.3 | see [diagnostics/probes](diagnostics/probes/README.md) |
| Example remedies: language guidance, agent-selection relay | App. G.4 | see [diagnostics/README.md](diagnostics/README.md#example-remedies-appendix-g4) |

Each run writes one JSON record per episode under `runs/diagnostics/`; the matching scripts in
`diagnostics/analysis/` (`rotation.py`, `controls.py`, `selection_events.py`, `first_decision.py`) produce the
tables. Create the instrumented evaluator once with `python3 diagnostics/make_eval_diagnostic.py .`
(a generated copy, `script/eval_diagnostic.py`, is included).

## Repository

- `envs/`: RoboTwin environments, common composition engine, and vendored cuRobo.
- `description/`: object descriptions and task instruction pools (regular files, no external links).
- `suite/scenes_v2.yaml`: formal membership; `suite/seeds/`: development seed files (formal lists are held by the organizers).
- `suite/policies.yaml`, `policy/`: public model registrations and adapters.
- `suite/run_suite.sh`: sequential evaluation; parallel/retry wrappers are also included.
- `diagnostics/`: language-following diagnostics, model-access probes and example remedies.
- `tools/`, `tests/`: preflight, provenance, release validation and regression tests.
- `docs/RESULTS_PROVENANCE.md`: reporting scope and provenance requirements.

## Documentation

- [Installation](docs/INSTALLATION.md) and [backend configuration](docs/BACKENDS.md)
- [Evaluation and results](docs/EVALUATION.md)
- [Scene catalog](docs/SCENES.md)
- [Development and frozen protocol](docs/DEVELOPMENT.md)
- [Optional external EEF agent](docs/EXTERNAL_AGENT.md)
- [Normalization and validation status](docs/NORMALIZATION.md)
- [Submitting an evaluation](docs/SUBMISSIONS.md) and the [model configuration interface](configs/model_configs/README.md)
- [Contributing](CONTRIBUTING.md), [security](SECURITY.md), [third-party notices](THIRD_PARTY_NOTICES.md)

## Attribution and license

This project derives from RoboTwin and retains the original MIT notice in [LICENSE](LICENSE).
The vendored `envs/curobo` snapshot has its own [NVIDIA license](envs/curobo/LICENSE)
and [asset license](envs/curobo/LICENSE_ASSETS). These are not replaced by the root MIT license.
External assets, models and inference backends retain their respective terms.
No model weights, API credentials, private backend, or original repository Git history are bundled.
