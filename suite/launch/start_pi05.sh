#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
# 启动 Pi0.5 推理服务（openpi PyTorch）。由 run_suite.sh 按 policies.yaml 的 launch 字段拉起。
#   GPU=0 PI05_PORT=7893 bash policy/Pi05/start_pi05.sh
set -euo pipefail
export OPENPI="${OPENPI:?Set OPENPI in configs/local.env}"
export PI05_CKPT="${PI05_CKPT:?Set PI05_CKPT in configs/local.env}"
export PI05_PORT="${PI05_PORT:-${PORT:-7893}}"   # run_suite 只透传 PORT，不设 PI05_PORT
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"  # suite/launch/ -> 仓库根
for p in "$OPENPI/.venv/bin/python" "$PI05_CKPT/model.safetensors"; do
  [[ -e "$p" ]] || { echo "[pi05] 缺少 $p" >&2; exit 1; }
done
cd "$OPENPI"
exec env CUDA_VISIBLE_DEVICES="$GPU" PI05_CKPT="$PI05_CKPT" PI05_PORT="$PI05_PORT" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  PYTHONPATH="$OPENPI/src:$OPENPI/packages/openpi-client/src" \
  "$OPENPI/.venv/bin/python" "$ROOT/policy/Pi05/serve.py"
