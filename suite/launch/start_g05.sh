#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
# 启动 GalaxeaVLA G0.5 推理服务（policy/G05/serve.py，官方仓库 .venv）。run_suite 只透传 PORT。
set -euo pipefail
export G05_ROOT="${G05_ROOT:?Set G05_ROOT in configs/local.env}"
export G05_PORT="${G05_PORT:-${PORT:-7999}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$G05_ROOT/.venv/bin/python" "$G05_ROOT/checkpoints/g05-robotwin20/checkpoints/model_state_dict.pt" "$G05_ROOT/checkpoints/action_tokenizer.pt" "$ROOT/policy/G05/serve.py"; do
  [[ -e "$p" ]] || { echo "[g05] 缺少 $p" >&2; exit 1; }
done
exec env OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES="$GPU" G05_ROOT="$G05_ROOT" G05_PORT="$G05_PORT" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$G05_ROOT/src:$G05_ROOT" \
  "$G05_ROOT/.venv/bin/python" "$ROOT/policy/G05/serve.py"
