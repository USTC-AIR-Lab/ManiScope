#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
set -euo pipefail
export FASTWAM_ROOT="${FASTWAM_ROOT:?Set FASTWAM_ROOT in configs/local.env}"
export FASTWAM_PORT="${FASTWAM_PORT:-${PORT:-7995}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$FASTWAM_ROOT/.venv/bin/python" "${FASTWAM_CKPT:?Set FASTWAM_CKPT}" "$ROOT/policy/FastWAM/serve.py"; do
  [[ -e "$p" ]] || { echo "[fastwam] missing $p" >&2; exit 1; }
done
exec env CUDA_VISIBLE_DEVICES="$GPU" FASTWAM_ROOT="$FASTWAM_ROOT" FASTWAM_PORT="$FASTWAM_PORT" \
  DIFFSYNTH_MODEL_BASE_PATH="${DIFFSYNTH_MODEL_BASE_PATH:?Set DIFFSYNTH_MODEL_BASE_PATH}" DIFFSYNTH_SKIP_DOWNLOAD=true \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$FASTWAM_ROOT/src:$FASTWAM_ROOT" \
  "$FASTWAM_ROOT/.venv/bin/python" "$ROOT/policy/FastWAM/serve.py"
