#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
# 启动公开 WLA 推理服务（policy/WLAFormal/serve.py，官方仓库 .venv）。run_suite 只透传 PORT。
#   GPU=0 PORT=7980 bash suite/launch/start_wla_formal.sh
set -euo pipefail
export WLA_ROOT="${WLA_ROOT:?Set WLA_ROOT in configs/local.env}"
export WLA_MODEL_ID="${WLA_MODEL_ID:?Set WLA_MODEL_ID in configs/local.env}"
export WLA_PORT="${WLA_FORMAL_PORT:-${PORT:-7980}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$WLA_ROOT/.venv/bin/python" "$WLA_ROOT/models/wla.py" "$WLA_MODEL_ID/config.json" "$ROOT/policy/WLAFormal/serve.py"; do
  [[ -e "$p" ]] || { echo "[wla_formal] 缺少 $p" >&2; exit 1; }
done
cd "$WLA_ROOT"
exec env CUDA_VISIBLE_DEVICES="$GPU" WLA_ROOT="$WLA_ROOT" WLA_MODEL_ID="$WLA_MODEL_ID" WLA_PORT="$WLA_PORT" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$WLA_ROOT" \
  "$WLA_ROOT/.venv/bin/python" "$ROOT/policy/WLAFormal/serve.py"
