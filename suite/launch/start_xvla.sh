#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
# 启动 X-VLA 推理服务（官方 deploy.py，FastAPI，POST /act）。由 run_suite.sh 按 policies.yaml 的 launch 拉起。
#   GPU=0 PORT=7960 bash suite/launch/start_xvla.sh
set -euo pipefail
export XVLA_DIR="${XVLA_DIR:?Set XVLA_DIR in configs/local.env}"
export XVLA_CKPT="${XVLA_CKPT:?Set XVLA_CKPT in configs/local.env}"
export XVLA_PORT="${XVLA_PORT:-${PORT:-7960}}"     # run_suite 只透传 PORT
export GPU="${GPU:-0}"
for p in "$XVLA_DIR/.venv/bin/python" "$XVLA_CKPT/model.safetensors" "$XVLA_DIR/deploy.py"; do
  [[ -e "$p" ]] || { echo "[xvla] 缺少 $p" >&2; exit 1; }
done
# deploy.py 见到 <output_dir>/info.json 就拒绝启动（上次被杀的服务会留下它），每次清空
export OUT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/manipscope-xvla-${XVLA_PORT}.XXXXXX")"
cd "$XVLA_DIR"
exec env CUDA_VISIBLE_DEVICES="$GPU" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  "$XVLA_DIR/.venv/bin/python" deploy.py --model_path "$XVLA_CKPT" --port "$XVLA_PORT" \
  --output_dir "$OUT_DIR" --disable_slurm
