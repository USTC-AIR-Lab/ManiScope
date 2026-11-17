#!/bin/bash
# suite/launch/start_dm05.sh with dm05_cfg_exp.py as the experiment entry point; PROBE_CFG_W sets the guidance weight w.
MS="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../../.." && pwd)"
source "$MS/suite/config.sh"
set -euo pipefail
export DM05_MODEL="${DM05_MODEL:?Set DM05_MODEL}"
export DM05_PORT="${DM05_PORT:-${PORT:-7891}}"
export GPU="${GPU:-0}"
export OPENDM_DIR="${OPENDM_DIR:?Set OPENDM_DIR in configs/local.env}"
export OPENDM_ENV="${OPENDM_ENV:?Set OPENDM_ENV in configs/local.env}"
export PROBE_CFG_W="${PROBE_CFG_W:?Set PROBE_CFG_W}"
cd "$OPENDM_DIR"
exec env \
  PATH="$OPENDM_ENV/bin:/usr/local/nvidia/bin:/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  CUDA_VISIBLE_DEVICES="$GPU" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OPENDM_DIR="$OPENDM_DIR" PROBE_CFG_W="$PROBE_CFG_W" \
  bash script/dm05_launcher.sh \
    --exp "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/dm05_cfg_exp.py" --task inference \
    --model-config.model-name-or-path "$DM05_MODEL" \
    --model-config.chunk-size 50 \
    --model-config.vision-attn-implementation sdpa \
    --inference-config.port "$DM05_PORT"
