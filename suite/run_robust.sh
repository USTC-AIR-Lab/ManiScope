#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
# 稳健并行：每张卡一个工作队列，逐个场景跑；每个场景用【全新推理服务】，
# 若该场景没产出 _result.txt（服务崩溃等）则自动重试，最多 RETRIES 次。
# 不同卡并行，互不影响；某场景反复失败也不拖累其它场景。
#
#   bash suite/run_robust.sh <policy> <gpu_csv> <episodes> [scene...]
# 环境: PORT_BASE(端口基址,避开被占端口), RETRIES(默认3)
#
#   PORT_BASE=7950 bash suite/run_robust.sh dm05 0,1,2,3 100
#   RETRIES=3 bash suite/run_robust.sh wla 0,1,2,3 100
set -uo pipefail

POLICY="${1:?用法: run_robust.sh <policy> <gpu_csv> <episodes> [scene...]}"
GPU_LIST="${2:?需要 gpu 列表}"
EPISODES="${3:?需要 episodes}"; shift 3
RETRIES="${RETRIES:-3}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; SUITE="$ROOT/suite"; cd "$ROOT"
PY="${YAML_PY:-python3}"
mkdir -p "$SUITE/logs"

PLUGIN="$(SUITE="$SUITE" POLICY="$POLICY" "$PY" -c 'import os,yaml; print(yaml.safe_load(open(os.environ["SUITE"]+"/policies.yaml"))["policies"][os.environ["POLICY"]].get("policy_name",os.environ["POLICY"]))')"
BASE_PORT="$(SUITE="$SUITE" POLICY="$POLICY" "$PY" -c 'import os,yaml; print(yaml.safe_load(open(os.environ["SUITE"]+"/policies.yaml"))["policies"][os.environ["POLICY"]].get("port",5599))')"
BASE_PORT="${PORT_BASE:-$BASE_PORT}"
ALL_SCENES="$(SUITE="$SUITE" "$PY" -c 'import os,yaml; s=yaml.safe_load(open(os.environ["SUITE"]+"/scenes_v2.yaml")); print(" ".join(dict.fromkeys(str(sc["name"]) for ax in s["axes"].values() for sc in (ax.get("scenes") or []) if not str(sc["name"]).startswith("<"))))')"
SCENES=("${@:-}"); [ -z "${SCENES[*]:-}" ] && SCENES=($ALL_SCENES)

IFS=',' read -ra GPUS <<< "$GPU_LIST"; N=${#GPUS[@]}
declare -A Q; i=0
for sc in "${SCENES[@]}"; do g="${GPUS[$((i%N))]}"; Q[$g]="${Q[$g]:-} $sc"; i=$((i+1)); done

echo "=== 稳健并行 policy=$POLICY plugin=$PLUGIN 卡=$GPU_LIST ep=$EPISODES 重试<=$RETRIES base_port=$BASE_PORT ==="
for idx in "${!GPUS[@]}"; do g="${GPUS[$idx]}"; echo "  卡$g 队列:${Q[$g]:-（空）}"; done

worker() {
  local g="$1" port="$2"; shift 2
  local failures=0
  local lg="$SUITE/logs/robust_${POLICY}_gpu${g}.log"; : > "$lg"
  for sc in "$@"; do
    local ok=0 mark="$SUITE/logs/.mark_${POLICY}_${g}_${sc}"
    for att in $(seq 1 "$RETRIES"); do
      touch "$mark"; sleep 1
      echo "[gpu$g] === $sc 第 $att 次 ===" >> "$lg"
      RUN_NAME="robust_${POLICY}_${g}" GPU="$g" SIM_GPU="$g" PORT="$port" EPISODES="$EPISODES" \
        bash "$SUITE/run_suite.sh" "$POLICY" "$sc" >> "$lg" 2>&1
      # 该 policy 插件目录下、本次尝试后新出现的 _result.txt 视为成功
      if find "$ROOT/eval_result/robust_${POLICY}_${g}/$sc/$PLUGIN" -name "_result.txt" -newer "$mark" 2>/dev/null | grep -q .; then
        echo "[gpu$g] $sc 成功(第 $att 次)" >> "$lg"; ok=1; break
      fi
      echo "[gpu$g] $sc 第 $att 次未出结果，清理服务后重试" >> "$lg"
      # run_suite 退出已按进程组清理本车道服务，这里不做机器级 pkill
      sleep 3
    done
    [ "$ok" = 0 ] && failures=$((failures+1))
    [ "$ok" = 0 ] && echo "[gpu$g] !!! $sc 连续 $RETRIES 次失败，放弃" >> "$lg"
    rm -f "$mark"
  done
  echo "[gpu$g] 队列完成" >> "$lg"
  [[ "$failures" == 0 ]]
}

PIDS=()
for idx in "${!GPUS[@]}"; do
  g="${GPUS[$idx]}"; [ -z "${Q[$g]:-}" ] && continue
  worker "$g" "$((BASE_PORT + g))" ${Q[$g]} &
  PIDS+=($!)
done
echo "=== 等 ${#PIDS[@]} 个卡队列结束 ==="
failed=0
for pid in "${PIDS[@]}"; do wait "$pid" || failed=$((failed+1)); done
echo "=== 全部结束 ==="

[[ "$failed" == 0 ]]
