# Installation

## Environments

Use separate Python environments for simulation and each inference backend. The HTTP/socket
boundary avoids importing incompatible model packages into the simulator. The inherited
simulation configuration targets Python 3.10 and SAPIEN 3.0.0b1. Install PyTorch/CUDA versions
compatible with your GPU driver; the inherited requirements are a reference, not a universal
hardware lockfile.

```bash
python3.10 -m venv .venv-sim
source .venv-sim/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements/sim.txt -r requirements/client.txt
# Vendored cuRobo needs the CUDA toolkit/compiler and torch at build time.
SETUPTOOLS_SCM_PRETEND_VERSION=0.7.0 python -m pip install --no-build-isolation -e envs/curobo
```

The source snapshot has no cuRobo Git metadata. The SCM override above is a packaging label,
not a claim that this snapshot equals the upstream v0.7.0 tag. Its content digest is recorded
in `provenance.json`. Do not replace it with the latest cuRobo without rerunning validation.
System tools include `ffmpeg`, a C++ toolchain, and compatible CUDA/Vulkan libraries for SAPIEN.
The inherited `script/requirements.txt` is legacy reference material; use `requirements/sim.txt`.

Set `ROBOTWIN_PYTHON` to the environment's Python in `configs/local.env`.
Do not run installers against another user's shared environment. The old installer that edited
SAPIEN/mplib in place is archived as text; `script/_install.sh` no longer makes those edits.
If a backend requires a patch, apply and record it in your own environment and rerun the smoke test.

## Assets

Obtain the matching RoboTwin 2.0 assets from the upstream project:
https://github.com/RoboTwin-Platform/RoboTwin . Assets must include `objects/`, `embodiments/`,
and the textures required by the task configuration. The repository does not redistribute them.

```bash
python3 tools/link_assets.py /absolute/path/to/robotwin_assets
```

This creates an ignored local link. It refuses to replace an existing different path and never
edits the target. Keep embodiment config/URDF paths portable; migrated asset bundles may contain
machine-specific references. The planner resolves known embodiment-local URDF and collision paths
in memory against the current resource directory; it never rewrites the shared files. Unknown or
missing external paths fail with a clear error and must be configured explicitly.

## Model backend

Install the chosen upstream backend in a different environment using its own pinned dependencies.
Set its code/checkpoint variables from [BACKENDS.md](BACKENDS.md). Download all required model
and auxiliary files before launching: several adapters use offline mode.

```bash
DRY_RUN=1 bash suite/run_suite.sh dm05 move_can_coaster
# Rendering smoke (no model weights required):
CUDA_VISIBLE_DEVICES=0 "$ROBOTWIN_PYTHON" script/render_scenes.py move_can_coaster \
  --target 1 --max_tries 2 --out out/smoke
# Expert smoke (bounded, no model service):
CUDA_VISIBLE_DEVICES=0 "$ROBOTWIN_PYTHON" suite/diag/expert_smoke.py move_can_coaster \
  --target 1 --max_tries 2
```

Export `ROBOTWIN_PYTHON` in your shell for direct Python commands above; launchers load local.env
automatically. See [NORMALIZATION.md](NORMALIZATION.md) for tests actually performed on this snapshot.
