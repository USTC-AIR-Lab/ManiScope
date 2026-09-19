# Development

## Frozen release versus scene generation

`formal48-v1` is defined by the checked-in manifest, environments, instruction pools, step limits,
and seeds. `protocol.lock.json` hashes the critical implementation and inputs. The validator fails
when they change. The hash detects drift; it does not certify scientific validity or runtime success.

`suite/table.py` and `suite/gen_scenes.py` describe candidate generated scenes. The generator writes
under `out/`; historical handwritten or manually refined environments may differ from generated
candidates. Review candidates individually instead of overwriting all `envs/`. Importing the legacy
`scene_set` generator can write candidates under `out/`, so validation does not import it.

For a new benchmark version: develop and smoke-test the scene, verify seen/unseen instruction pools,
update membership and step limits, regenerate expert-solvable seeds and initial poses in your own
GPU environment, and document the changed protocol. Then explicitly refresh hashes:

```bash
python3 tools/lock_protocol.py --version YOUR_NEW_PROTOCOL_VERSION
python3 tools/validate_repo.py
python3 -m pytest -q tests
```

Do not refresh the lock merely to silence a failing check. `suite/gen_yaml.py` exports a copy of the
frozen manifest to `out/scenes_v2.yaml` and refuses to overwrite the official manifest.

## Adapters

A model implements `get_model`, `eval`, and `reset_model` in `policy/<Plugin>/deploy_policy.py`,
with `deploy_policy.yml`. Register only implemented adapters in `suite/policies.yaml`; planned
integrations belong under `planned_policies`. Add a configurable launcher and update BACKENDS.md.
Use finite actions, reset between episodes, respect evaluator step/success limits, and document
image/state ordering, coordinate conventions and action horizons.

## Checks

CI runs CPU-only syntax, manifest, seeds, configuration, protocol-hash and regression checks.
It does not load weights or run physics. Run a bounded render/expert smoke after simulation changes,
then an end-to-end policy episode for the affected adapter. Keep runtime outputs out of Git.
