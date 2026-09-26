#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
#
#   bash suite/run_robust.sh <policy> <gpu_csv> <episodes> [scene...]
#
#   PORT_BASE=7950 bash suite/run_robust.sh dm05 0,1,2,3 100
#   RETRIES=3 bash suite/run_robust.sh wla 0,1,2,3 100
set -uo pipefail

POLICY="${1:?Usage: run_robust.sh <policy> <gpu_csv> <episodes> [scene...]}"
GPU_LIST="${2:?GPU list required}"
EPISODES="${3:?episodes required}"; shift 3
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

echo "=== retryingparallel policy=$POLICY plugin=$PLUGIN GPU=$GPU_LIST ep=$EPISODES retry<=$RETRIES base_port=$BASE_PORT ==="
for idx in "${!GPUS[@]}"; do g="${GPUS[$idx]}"; echo "  GPU$g queue:${Q[$g]:-(empty)}"; done

worker() {
  local g="$1" port="$2"; shift 2
  local failures=0
  local lg="$SUITE/logs/robust_${POLICY}_gpu${g}.log"; : > "$lg"
  for sc in "$@"; do
    local ok=0 mark="$SUITE/logs/.mark_${POLICY}_${g}_${sc}"
    for att in $(seq 1 "$RETRIES"); do
      touch "$mark"; sleep 1
      echo "[gpu$g] === $sc attempt $att  ===" >> "$lg"
      RUN_NAME="robust_${POLICY}_${g}" GPU="$g" SIM_GPU="$g" PORT="$port" EPISODES="$EPISODES" \
        bash "$SUITE/run_suite.sh" "$POLICY" "$sc" >> "$lg" 2>&1
      if find "$ROOT/eval_result/robust_${POLICY}_${g}/$sc/$PLUGIN" -name "_result.txt" -newer "$mark" 2>/dev/null | grep -q .; then
        echo "[gpu$g] $sc completed (attempt $att time)" >> "$lg"; ok=1; break
      fi
      echo "[gpu$g] $sc attempt $att produced no result; retry after service cleanup" >> "$lg"
      sleep 3
    done
    [ "$ok" = 0 ] && failures=$((failures+1))
    [ "$ok" = 0 ] && echo "[gpu$g] !!! $sc after $RETRIES failed attempts; giving up" >> "$lg"
    rm -f "$mark"
  done
  echo "[gpu$g] queue completed" >> "$lg"
  [[ "$failures" == 0 ]]
}

PIDS=()
for idx in "${!GPUS[@]}"; do
  g="${GPUS[$idx]}"; [ -z "${Q[$g]:-}" ] && continue
  worker "$g" "$((BASE_PORT + g))" ${Q[$g]} &
  PIDS+=($!)
done
echo "=== waiting for ${#PIDS[@]} GPU queues ==="
failed=0
for pid in "${PIDS[@]}"; do wait "$pid" || failed=$((failed+1)); done
echo "=== all completed ==="

[[ "$failed" == 0 ]]
