# Third-party notices

- RoboTwin-derived environment, description and evaluation code: original MIT notice retained
  in `LICENSE`; upstream reference https://github.com/RoboTwin-Platform/RoboTwin .
- Vendored cuRobo under `envs/curobo`: its NVIDIA license and asset license are retained in
  `envs/curobo/LICENSE` and `envs/curobo/LICENSE_ASSETS`, along with per-file notices.
  The exact upstream commit was not recorded in the supplied source snapshot; a content digest
  is recorded in `provenance.json`. Do not represent it as a verified upstream release.
- Model adapters interface with external projects listed in `suite/policies.yaml`. Their model
  weights and upstream inference code are not bundled. Install and use those under their own terms.
- RoboTwin assets are supplied separately and are not covered by this repository's root license.

Root MIT licensing does not relicense third-party components. Existing copyright notices remain
unchanged. The normalized repository begins a new history; historical provenance is recorded
without importing deployment paths or the original Git author metadata.
