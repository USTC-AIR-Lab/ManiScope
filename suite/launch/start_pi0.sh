#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
set -euo pipefail
export OPENPI="${OPENPI:?Set OPENPI in configs/local.env}"
export PI0_CKPT="${PI0_CKPT:?Set PI0_CKPT in configs/local.env}"
export PI0_PORT="${PI0_PORT:-${PORT:-7894}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$OPENPI/.venv/bin/python" "$PI0_CKPT/params" "$ROOT/policy/Pi05/serve.py"; do
  [[ -e "$p" ]] || { echo "[pi0] missing $p" >&2; exit 1; }
done
cd "$OPENPI"
exec env CUDA_VISIBLE_DEVICES="$GPU" PI_VARIANT=pi0 PI_CKPT="$PI0_CKPT" PI_PORT="$PI0_PORT" \
  PI_ASSET_ID="${PI0_ASSET_ID:-aloha-agilex_clean-50_flow}" PI_HORIZON="${PI0_HORIZON:-50}" \
  PI_ADAPT_TO_PI="${PI0_ADAPT_TO_PI:-1}" PI_DELTA_ACTIONS="${PI0_DELTA_ACTIONS:-1}" \
  XLA_PYTHON_CLIENT_PREALLOCATE=false XLA_PYTHON_CLIENT_ALLOCATOR=platform \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  PYTHONPATH="$OPENPI/src:$OPENPI/packages/openpi-client/src" \
  "$OPENPI/.venv/bin/python" "$ROOT/policy/Pi05/serve.py"
