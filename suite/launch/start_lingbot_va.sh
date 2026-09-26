#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
set -euo pipefail
export LB_DIR="${LB_DIR:?Set LB_DIR in configs/local.env}"
export LB_CKPT="${LB_CKPT:?Set LB_CKPT in configs/local.env}"
export BRIDGE_PORT="${LB_PORT:-${PORT:-8001}}"
export WS_PORT=$((BRIDGE_PORT + 100)); MP=$((BRIDGE_PORT + 200))
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PY="$LB_DIR/.venv/bin/python"
for p in "$PY" "$LB_CKPT/transformer" "$ROOT/policy/LingBotVA/bridge.py"; do
  [[ -e "$p" ]] || { echo "[lingbot] missing $p" >&2; exit 1; }
done
cd "$LB_DIR"
env CUDA_VISIBLE_DEVICES="$GPU" MASTER_PORT="$MP" LB_DIR="$LB_DIR" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=8 PYTHONPATH="$LB_DIR" \
  "$PY" "$ROOT/policy/LingBotVA/serve_entry.py" --ckpt "$LB_CKPT" --port "$WS_PORT" --save_root "/tmp/lingbot_vis_$WS_PORT" \
  > "/tmp/lingbot_ws_${WS_PORT}.log" 2>&1 &
export WS_PID=$!
env PYTHONPATH="$LB_DIR" BRIDGE_PORT="$BRIDGE_PORT" WS_PORT="$WS_PORT" "$PY" "$ROOT/policy/LingBotVA/bridge.py" &
export BR_PID=$!
trap 'kill $WS_PID $BR_PID 2>/dev/null; sleep 1; kill -9 $WS_PID $BR_PID 2>/dev/null; true' EXIT
wait -n $WS_PID $BR_PID
