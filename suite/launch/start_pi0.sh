#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
# 启动 pi0 推理服务（openpi JAX 路径，复用 policy/Pi05/serve.py，PI_VARIANT=pi0）。
set -euo pipefail
export OPENPI="${OPENPI:?Set OPENPI in configs/local.env}"
export PI0_CKPT="${PI0_CKPT:?Set PI0_CKPT in configs/local.env}"
export PI0_PORT="${PI0_PORT:-${PORT:-7894}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$OPENPI/.venv/bin/python" "$PI0_CKPT/params" "$ROOT/policy/Pi05/serve.py"; do
  [[ -e "$p" ]] || { echo "[pi0] 缺少 $p" >&2; exit 1; }
done
cd "$OPENPI"
# JAX 默认预分配 75% 显存，和同卡的其它车道抢；关掉预分配、按需增长
exec env CUDA_VISIBLE_DEVICES="$GPU" PI_VARIANT=pi0 PI_CKPT="$PI0_CKPT" PI_PORT="$PI0_PORT" \
  PI_ASSET_ID="${PI0_ASSET_ID:-aloha-agilex_clean-50_flow}" PI_HORIZON="${PI0_HORIZON:-50}" \
  PI_ADAPT_TO_PI="${PI0_ADAPT_TO_PI:-1}" PI_DELTA_ACTIONS="${PI0_DELTA_ACTIONS:-1}" \
  XLA_PYTHON_CLIENT_PREALLOCATE=false XLA_PYTHON_CLIENT_ALLOCATOR=platform \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  PYTHONPATH="$OPENPI/src:$OPENPI/packages/openpi-client/src" \
  "$OPENPI/.venv/bin/python" "$ROOT/policy/Pi05/serve.py"
