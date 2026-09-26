#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
set -euo pipefail
export AHAWAM_ROOT="${AHAWAM_ROOT:?Set AHAWAM_ROOT in configs/local.env}"
export AHAWAM_PORT="${AHAWAM_PORT:-${PORT:-7996}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$AHAWAM_ROOT/.venv/bin/python" "${AHAWAM_CKPT:?Set AHAWAM_CKPT}" "$ROOT/policy/AHAWAM/serve.py"; do
  [[ -e "$p" ]] || { echo "[ahawam] missing $p" >&2; exit 1; }
done
exec env CUDA_VISIBLE_DEVICES="$GPU" AHAWAM_ROOT="$AHAWAM_ROOT" AHAWAM_PORT="$AHAWAM_PORT" \
  DIFFSYNTH_MODEL_BASE_PATH="${DIFFSYNTH_MODEL_BASE_PATH:?Set DIFFSYNTH_MODEL_BASE_PATH}" DIFFSYNTH_SKIP_DOWNLOAD=true \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$AHAWAM_ROOT/src:$AHAWAM_ROOT" \
  "$AHAWAM_ROOT/.venv/bin/python" "$ROOT/policy/AHAWAM/serve.py"
