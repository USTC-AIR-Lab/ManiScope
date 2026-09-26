#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
set -euo pipefail
export OPENWAM_DIR="${OPENWAM_DIR:?Set OPENWAM_DIR in configs/local.env}"
export OPENWAM_CKPT="${OPENWAM_CKPT:?Set OPENWAM_CKPT in configs/local.env}"
export BRIDGE_PORT="${OPENWAM_PORT:-${PORT:-7998}}"
export WS_PORT=$((BRIDGE_PORT + 100))
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PY="$OPENWAM_DIR/.venv/bin/python"
for p in "$PY" "$OPENWAM_CKPT/config.yaml" "$ROOT/policy/OpenWAM/bridge.py"; do
  [[ -e "$p" ]] || { echo "[openwam] missing $p" >&2; exit 1; }
done
cd "$OPENWAM_DIR"
env CUDA_VISIBLE_DEVICES="$GPU" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$OPENWAM_DIR" \
  "$PY" "$ROOT/policy/OpenWAM/server_entry.py" --ckpt-dir "$OPENWAM_CKPT" --host 127.0.0.1 --port "$WS_PORT" \
  > "/tmp/openwam_ws_${WS_PORT}_$(date +%H%M%S).log" 2>&1 &
export WS_PID=$!
env PYTHONPATH="$OPENWAM_DIR" BRIDGE_PORT="$BRIDGE_PORT" WS_URL="ws://127.0.0.1:$WS_PORT" "$PY" "$ROOT/policy/OpenWAM/bridge.py" &
export BR_PID=$!
trap 'kill $WS_PID $BR_PID 2>/dev/null; sleep 1; kill -9 $WS_PID $BR_PID 2>/dev/null; true' EXIT
wait -n $WS_PID $BR_PID
