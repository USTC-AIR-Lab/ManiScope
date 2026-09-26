#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
#   GPU=0 PORT=7970 bash suite/launch/start_starvla.sh
set -euo pipefail
export STARVLA_DIR="${STARVLA_DIR:?Set STARVLA_DIR in configs/local.env}"
export STARVLA_CKPT="${STARVLA_CKPT:?Set STARVLA_CKPT in configs/local.env}"
export BRIDGE_PORT="${STARVLA_PORT:-${PORT:-7970}}"
export WS_PORT=$((BRIDGE_PORT + 100))
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PY="$STARVLA_DIR/.venv/bin/python"
for p in "$PY" "$STARVLA_CKPT" "$ROOT/policy/StarVLA/bridge.py"; do
  [[ -e "$p" ]] || { echo "[starvla] missing $p" >&2; exit 1; }
done
cd "$STARVLA_DIR"
env CUDA_VISIBLE_DEVICES="$GPU" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$STARVLA_DIR" \
  "$PY" "$ROOT/policy/StarVLA/server_gc.py" --ckpt_path "$STARVLA_CKPT" --port "$WS_PORT" --use_bf16 \
  > "/tmp/starvla_ws_${WS_PORT}.log" 2>&1 &
export WS_PID=$!
env PYTHONPATH="$STARVLA_DIR" BRIDGE_PORT="$BRIDGE_PORT" WS_PORT="$WS_PORT" "$PY" "$ROOT/policy/StarVLA/bridge.py" &
export BR_PID=$!
trap 'kill $WS_PID $BR_PID 2>/dev/null; sleep 1; kill -9 $WS_PID $BR_PID 2>/dev/null; true' EXIT
wait -n $WS_PID $BR_PID
