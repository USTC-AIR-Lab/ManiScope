#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
#   GPU=0 PI05_PORT=7893 bash policy/Pi05/start_pi05.sh
set -euo pipefail
export OPENPI="${OPENPI:?Set OPENPI in configs/local.env}"
export PI05_CKPT="${PI05_CKPT:?Set PI05_CKPT in configs/local.env}"
export PI05_PORT="${PI05_PORT:-${PORT:-7893}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$OPENPI/.venv/bin/python" "$PI05_CKPT/model.safetensors"; do
  [[ -e "$p" ]] || { echo "[pi05] missing $p" >&2; exit 1; }
done
cd "$OPENPI"
exec env CUDA_VISIBLE_DEVICES="$GPU" PI05_CKPT="$PI05_CKPT" PI05_PORT="$PI05_PORT" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  PYTHONPATH="$OPENPI/src:$OPENPI/packages/openpi-client/src" \
  "$OPENPI/.venv/bin/python" "$ROOT/policy/Pi05/serve.py"
