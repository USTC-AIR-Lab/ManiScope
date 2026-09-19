#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../config.sh"
# 启动 DM0.5 推理服务（Dexmal DM05-robotwin2 通才 checkpoint）。
# 由 opendm（dexbotic 的推理框架）承载，单内核评测端只通过 base_url 访问，不关心内部。
#
# 用法:
#   GPU=0 DM05_PORT=7891 bash suite/launch/start_dm05.sh
#
# 环境变量（都有默认值）:
#   DM05_MODEL   checkpoint 目录（默认 ModelsHub 下的 DM05-robotwin2）
#   DM05_PORT    服务端口（默认 7891，要和 policies.yaml / deploy_policy.yml 一致）
#   GPU          CUDA_VISIBLE_DEVICES（默认 0）
#   OPENDM_DIR   opendm 仓库根（推理后端，外部依赖）
#   OPENDM_ENV   opendm 的 venv（其 bin 会加到 PATH 前）
#
# 注意: vision-attn 必须显式 sdpa —— opendm 的 DM05ModelConfig 把
# vision_attn_implementation 硬编码默认成 flash_attention_2（不是 auto，不会自动降级），
# 本机没装 flash_attn 就会在构造模型时崩。
#
# 若本机没装 flash_attn，光靠 --vision-attn-implementation sdpa 不够（模型构造早于该参数
# 生效）。需要把 checkpoint 的 config.json 里所有 attn_implementation 从 flash_attention_2
# 改成 sdpa（含嵌套的 vision_config），备份 config.json.bak。一次性命令:
#   python3 -c 'import json,sys; p=sys.argv[1]; c=json.load(open(p));\
#     import re; s=json.dumps(c).replace("flash_attention_2","sdpa"); open(p,"w").write(s)' $DM05_MODEL/config.json
set -euo pipefail

export DM05_MODEL="${DM05_MODEL:?Set DM05_MODEL in configs/local.env}"
export DM05_PORT="${DM05_PORT:-${PORT:-7891}}"
export GPU="${GPU:-0}"
export OPENDM_DIR="${OPENDM_DIR:?Set OPENDM_DIR in configs/local.env}"
export OPENDM_ENV="${OPENDM_ENV:?Set OPENDM_ENV in configs/local.env}"

for p in "$DM05_MODEL" "$OPENDM_DIR" "$OPENDM_ENV/bin/python"; do
  [[ -e "$p" ]] || { echo "[dm05] 缺少: $p" >&2; exit 1; }
done

# 去掉机器级 pkill：同机多车道会误杀别车道的服务。
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
