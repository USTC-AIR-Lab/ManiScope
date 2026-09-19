#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
# 启动 Motus 推理服务（policy/Motus/serve.py，官方仓库 .venv）。run_suite 只透传 PORT。
set -euo pipefail
export MOTUS_ROOT="${MOTUS_ROOT:?Set MOTUS_ROOT in configs/local.env}"
export MOTUS_PORT="${MOTUS_PORT:-${PORT:-8000}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$MOTUS_ROOT/.venv/bin/python" "${MOTUS_CKPT:?Set MOTUS_CKPT}" "${MOTUS_VLM:?Set MOTUS_VLM}/config.json" "$ROOT/policy/Motus/serve.py"; do
  [[ -e "$p" ]] || { echo "[motus] 缺少 $p" >&2; exit 1; }
done
exec env OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES="$GPU" MOTUS_ROOT="$MOTUS_ROOT" MOTUS_PORT="$MOTUS_PORT" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$MOTUS_ROOT/bak:$MOTUS_ROOT" \
  "$MOTUS_ROOT/.venv/bin/python" "$ROOT/policy/Motus/serve.py"
