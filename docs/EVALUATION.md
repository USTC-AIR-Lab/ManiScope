# Evaluation

The formal manifest is `suite/scenes_v2.yaml`: 48 scenes and 100 saved seeds each.
Defaults are 50 episodes, `demo_clean`, and unseen instructions. `ROBOTWIN_FROZEN_SEEDS=0`
is an exploratory mode and must not be reported as the same frozen protocol.

```bash
EPISODES=50 RUN_NAME=dm05_formal bash suite/run_suite.sh dm05
# Reuse a service only with explicit opt-in:
AUTO_LAUNCH=0 PORT=7891 EPISODES=1 bash suite/run_suite.sh dm05 move_can_coaster
# Multiple GPUs; each lane launches a separate inference service:
bash suite/run_parallel.sh dm05 0,1 50
python3 suite/collect.py --stages
```

`GPU` selects model inference; `SIM_GPU` selects simulation. A two-card host can use one for each.
The parallel wrapper instead colocates each lane's model and simulation on its assigned card;
ensure memory is sufficient. Use a distinct `PORT_BASE` for simultaneous campaigns.

Results live under `eval_result/<run>/<task>/<plugin>/<task-config>/<checkpoint>/<timestamp>/`.
Each task records `_run_metadata.json` with commit, dirty state, selected controls and protocol
hashes; the evaluator writes results, actual instructions and videos. Model filenames and secrets
are not copied into metadata. Record model revision, backend revision, hardware and sampling
settings in your experiment report; these are external to the frozen scene contract.

Video eligibility is the first `ROBOTWIN_VIDEO_FIRST_N` seeds (default 10), independent of success.
Optional success/failure caps can further reduce saved video count. Images/videos and raw outputs
are gitignored. Historical reports in `docs/archive` are not rerun results for this snapshot.

For generated scenes, `CompoScene.check_success` combines target selection, reference stability,
and the declared goal. Handwritten scenes have individual criteria. Model action horizons,
action spaces and inference budgets can differ. Compare runs with matching task/seed/instruction
settings and explicitly disclose these remaining differences.

A task failure makes the runner return nonzero after processing its remaining tasks. Existing
services are not silently reused, and launcher cleanup targets only its own process group.
