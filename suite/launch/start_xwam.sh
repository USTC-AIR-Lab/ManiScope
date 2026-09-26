#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
set -euo pipefail
export XWAM_ROOT="${XWAM_ROOT:?Set XWAM_ROOT in configs/local.env}"
export XWAM_PORT="${XWAM_PORT:-${PORT:-7997}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$XWAM_ROOT/.venv/bin/python" "${XWAM_EXP:?Set XWAM_EXP}/checkpoints/last.ckpt/checkpoint/mp_rank_00_model_states.pt" "$ROOT/policy/XWAM/serve.py"; do
  [[ -e "$p" ]] || { echo "[xwam] missing $p" >&2; exit 1; }
done
exec env CUDA_VISIBLE_DEVICES="$GPU" XWAM_ROOT="$XWAM_ROOT" XWAM_PORT="$XWAM_PORT" \
  XWAM_WAN_DIR="${XWAM_WAN_DIR:?Set XWAM_WAN_DIR}" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$XWAM_ROOT" \
  "$XWAM_ROOT/.venv/bin/python" "$ROOT/policy/XWAM/serve.py"
