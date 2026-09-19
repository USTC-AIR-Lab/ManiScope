# Normalization record

## Scope

This is an independent repository prepared from the existing working-tree snapshot, not a clone
of its Git history. Source project files and Git status were checked against a pre-copy snapshot
and remained unchanged. No remote repository has been created or pushed.

## Changes

- Preserved 48 formal environments and their 100 frozen seeds each; scene/evaluator ASTs and
  seed JSON content were compared with the source. Success logic was not changed.
- Recovered the broken compound-task instruction link and available stage templates as regular files.
- Included previously ignored diagnostic Python source used by seed generation.
- Removed private-backend registration/launcher, separated planned integrations from implemented
  ones, and replaced proprietary provider registrations with an explicitly external EEF bridge.
- Replaced personal runtime paths with configuration; isolated local assets/runtime configuration.
- Reworked the runner to validate before launching, propagate failures, preserve explicit environment
  settings and video controls, require explicit service reuse, and write run provenance.
- Corrected stale manifest references and recovered goal-type metadata from actual environment
  definitions (unquoted YAML `on` had been read as a boolean).
- Added protocol hashes, portable docs, archived-report scope, dependency guidance, license notices,
  ignore rules, tests and CPU CI. Kept cuRobo's separate license and source snapshot.
- Replaced the old environment-mutating installation script with installation guidance.

## Verification

- 48 unique formal scenes; all environment, instruction, seed and step-limit entries present.
- 100 distinct frozen seeds per scene; seen/unseen instruction pools nonempty.
- Python and shell syntax checks and protocol hashes pass.
- Six CPU regression tests pass, including a real runner with a mock simulator/service that confirms
  failure propagation, video/frozen-seed controls and per-task metadata.
- Optional model inference services have not all been launched; no new success-rate claims are made.
- The existing simulation environment imports PyTorch 2.7.1+cu126, SAPIEN and mplib, and CUDA is available after an isolated expat preload workaround. A bounded render attempt reached CUDA extension compilation but timed out before rendering; this is not a passed simulation test. A cached follow-up is being checked separately.

## Release boundaries

Assets and model weights are external downloads. Inference backends need their own environments;
there is no verified universal dependency lock. The vendored cuRobo's exact original commit is
unknown and identified by a snapshot content digest instead. Historical reports are archival and
must not be presented as new measurements. Automated credential scans are heuristic.
