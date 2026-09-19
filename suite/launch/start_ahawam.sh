#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
# 启动 AHA-WAM 推理服务（policy/AHAWAM/serve.py，官方仓库 .venv）。run_suite 只透传 PORT。
set -euo pipefail
export AHAWAM_ROOT="${AHAWAM_ROOT:?Set AHAWAM_ROOT in configs/local.env}"
export AHAWAM_PORT="${AHAWAM_PORT:-${PORT:-7996}}"
export GPU="${GPU:-0}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for p in "$AHAWAM_ROOT/.venv/bin/python" "${AHAWAM_CKPT:?Set AHAWAM_CKPT}" "$ROOT/policy/AHAWAM/serve.py"; do
  [[ -e "$p" ]] || { echo "[ahawam] 缺少 $p" >&2; exit 1; }
done
# Wan2.2 侧车按 DiffSynth 约定：<BASE>/Wan-AI/Wan2.2-TI2V-5B/{Wan2.2_VAE.pth,models_t5_umt5-xxl-enc-bf16.pth}、<BASE>/Wan-AI/Wan2.1-T2V-1.3B/google/umt5-xxl/
exec env CUDA_VISIBLE_DEVICES="$GPU" AHAWAM_ROOT="$AHAWAM_ROOT" AHAWAM_PORT="$AHAWAM_PORT" \
  DIFFSYNTH_MODEL_BASE_PATH="${DIFFSYNTH_MODEL_BASE_PATH:?Set DIFFSYNTH_MODEL_BASE_PATH}" DIFFSYNTH_SKIP_DOWNLOAD=true \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH="$AHAWAM_ROOT/src:$AHAWAM_ROOT" \
  "$AHAWAM_ROOT/.venv/bin/python" "$ROOT/policy/AHAWAM/serve.py"
