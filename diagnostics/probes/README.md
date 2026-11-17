# Model-access probes (Section 5.3, Appendix E)

Paired instruction x layout study on `attr_color_block_3way` for pi0.5 and Motus, the future-video readout of
the Motus forecasts, and the internal key/value (K/V) intervention at the Motus action-attention interface.

## Design

- **Paired conditions** (`protocols/protocol_v1.json`, `protocols/jobs.json`). Twenty initial configurations
  (seeds 200000-200019), each with four conditions: original or red-blue-exchanged object poses, crossed with
  "Pick up the red block." / "Pick up the blue block.". Runs end at task success or 256 native action commands;
  inference noise uses seed 17 + d at decision d. `run_episode.py` runs one condition against an HTTP policy
  service (`service.py`) and records the model input/output of every decision and passive physics telemetry
  (`pilot_telemetry.py`). `analyze.py` derives the first loaded contact (0.1 N), approach and holding events;
  `noise_controls.py` replays the first decision with the same and a different noise seed and a paraphrase.
- **Future-video readout** (`future_targets.py`, `future_sheets.py`, `finalize_future_labels.py`). The forecast
  frames returned with the first Motus decision are read by a fixed RGB rule: the candidate closest to the
  visible dark gripper region in the final predicted frame, with `none` / `ambiguous` outcomes. Contact sheets
  of all frames are written for visual review; the final label requires the rule and the review
  (`reports/future_visual_review.json`, one entry per forecast with `visible_approach`) to agree.
- **Internal K/V intervention** (`directional_probe.py`, `directional_probe_swapped.py`, `norm_audit.py`). For
  each paired state, the near-future video-token keys and values (120 tokens) computed under the alternate
  instruction (the donor) replace the recipient's entries at every one of the 30 layers x 10 denoising steps,
  only for the action-query rows; video generation stays native. Controls: sham (zero change, must reproduce
  the baseline exactly), half-strength, current-frame and understanding-token spans, per-site norm-matched
  versions and a scrambled direction (`norm_audit.py` records per-site K/V norms). `forward_kinematics.py` maps
  commanded joints to TCP positions; `internal_summary.py` measures the change in relative distance to the donor
  goal versus the recipient goal, with configuration-bootstrap intervals.

## Running

Set the model paths in the environment (`MODELS_ROOT`, or `PI05_CKPT`, `MOTUS_ROOT`, `MOTUS_CKPT`, `MOTUS_WAN`,
`MOTUS_VLM` as in `configs/local.env.example`) and the interpreters (`SIM_PYTHON` for the simulator,
`PI05_PYTHON` and `MOTUS_PYTHON` for the model services; default: the current interpreter). Outputs go to
`PATHWAYS_ROOT` (default `runs/probes`).

```bash
export PATHWAYS_ROOT=$PWD/runs/probes
mkdir -p $PATHWAYS_ROOT && cp -r diagnostics/probes/protocols $PATHWAYS_ROOT/
cd diagnostics/probes
python3 launch.py 0 1 2 3 4 5 6 7   # services: GPUs 0-3 serve pi0.5, 4-7 Motus (port 8200 + GPU)
python3 lane.py <gpu>               # per GPU: run the conditions of protocols/lane_<gpu>.json
python3 after_lane.py <gpu>         # per GPU: noise controls; on GPUs 0-3 then the K/V intervention
                                    #   (directional_probe.py, lane = GPU) once the Motus runs it needs exist
python3 norm_audit_stage.py <gpu>   # GPUs 4-7: per-site norm audit (lane = GPU - 4)
python3 swapped_stage.py <lane>     # lanes 0-3: intervention on the exchanged layout
python3 offline_pipeline.py         # events, future readout, contact sheets, kinematics, figures, archive
# after the visual review of the forecast contact sheets:
python3 finalize_future_labels.py && python3 internal_summary.py
```

The lane files assign conditions to GPUs as in our runs; edit `gpu` and `url` in `protocols/jobs.json` and
regenerate the lane files for another layout. To apply the probes to another video-predicting policy, replace
the forecast capture in `service.py`, the RGB rule in `future_targets.py` (scene-specific) and the attention
hook in `directional_probe.py` (model-specific); the paired design and the analysis are model-independent.
