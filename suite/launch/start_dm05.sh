#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
#
#   GPU=0 DM05_PORT=7891 bash suite/launch/start_dm05.sh
#
#
#
#   python3 -c 'import json,sys; p=sys.argv[1]; c=json.load(open(p));\
#     import re; s=json.dumps(c).replace("flash_attention_2","sdpa"); open(p,"w").write(s)' $DM05_MODEL/config.json
set -euo pipefail

export DM05_MODEL="${DM05_MODEL:?Set DM05_MODEL in configs/local.env}"
export DM05_PORT="${DM05_PORT:-${PORT:-7891}}"
export GPU="${GPU:-0}"
export OPENDM_DIR="${OPENDM_DIR:?Set OPENDM_DIR in configs/local.env}"
export OPENDM_ENV="${OPENDM_ENV:?Set OPENDM_ENV in configs/local.env}"

for p in "$DM05_MODEL" "$OPENDM_DIR" "$OPENDM_ENV/bin/python"; do
  [[ -e "$p" ]] || { echo "[dm05] missing: $p" >&2; exit 1; }
done

sleep 3
cd "$OPENDM_DIR"
exec env \
  PATH="$OPENDM_ENV/bin:/usr/local/nvidia/bin:/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  CUDA_VISIBLE_DEVICES="$GPU" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  bash script/dm05_launcher.sh \
    --exp playground/dm05_robotwin2.py --task inference \
    --model-config.model-name-or-path "$DM05_MODEL" \
    --model-config.chunk-size 50 \
    --model-config.vision-attn-implementation sdpa \
    --inference-config.port "$DM05_PORT"
