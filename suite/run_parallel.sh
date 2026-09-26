#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
#
#   bash suite/run_parallel.sh <policy> <gpu_list> [episodes] [scene...]
#
#   bash suite/run_parallel.sh wla  0,1     10 attr_bind_bottle move_cup_pad
#
set -uo pipefail

POLICY="${1:?Usage: run_parallel.sh <policy> <gpu_list> [episodes] [scene...]}"
GPU_LIST="${2:?GPU list required, e.g. 0,1,2,3}"
EPISODES="${3:-10}"; shift 3 2>/dev/null || shift $#

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUITE="$ROOT/suite"
cd "$ROOT"
YAML_PY="${YAML_PY:-python3}"

BASE_PORT="$(SUITE="$SUITE" POLICY="$POLICY" "$YAML_PY" -c 'import os,yaml; print(yaml.safe_load(open(os.environ["SUITE"]+"/policies.yaml"))["policies"][os.environ["POLICY"]].get("port",5599))')"
BASE_PORT="${PORT_BASE:-$BASE_PORT}"
ALL_SCENES="$(SUITE="$SUITE" SCENES_YAML="${SCENES_YAML:-scenes_v2.yaml}" "$YAML_PY" -c 'import os,yaml; s=yaml.safe_load(open(os.environ["SUITE"]+"/"+os.environ.get("SCENES_YAML","scenes_v2.yaml"))); print(" ".join(dict.fromkeys(str(sc["name"]) for ax in s["axes"].values() for sc in (ax.get("scenes") or []) if not str(sc["name"]).startswith("<"))))')"
SCENES=("${@:-}"); [ -z "${SCENES[*]:-}" ] && SCENES=($ALL_SCENES)

IFS=',' read -ra GPUS <<< "$GPU_LIST"
NLANES=${#GPUS[@]}

declare -A LANE_SCENES
i=0
for sc in "${SCENES[@]}"; do
  g=$(( i % NLANES ))
  LANE_SCENES[$g]="${LANE_SCENES[$g]:-} $sc"
  i=$((i+1))
done

echo "=== parallel policy=$POLICY  GPU=$GPU_LIST  episodes=$EPISODES  lanes=$NLANES base_port=$BASE_PORT ==="
HOST_TAG="${HOST_TAG:-$(hostname -s)}"
mkdir -p "$SUITE/logs/$HOST_TAG"
PIDS=()
for idx in "${!GPUS[@]}"; do
  g="${GPUS[$idx]}"
  scenes="${LANE_SCENES[$idx]:-}"
  [ -z "$scenes" ] && continue
  port=$(( BASE_PORT + g ))
  echo "  lane GPU$g port$port:$scenes"
  GPU="$g" SIM_GPU="$g" PORT="$port" EPISODES="$EPISODES" \
    RUN_NAME="${RUN_NAME:-}" SCENES_YAML="${SCENES_YAML:-scenes_v2.yaml}" \
    MAX_SUCC_VIDEOS="${MAX_SUCC_VIDEOS:-unlimited}" MAX_FAIL_VIDEOS="${MAX_FAIL_VIDEOS:-unlimited}" \
    bash "$SUITE/run_suite.sh" "$POLICY" $scenes \
    > "$SUITE/logs/$HOST_TAG/parallel_${POLICY}_gpu${g}.log" 2>&1 &
  PIDS+=($!)
done

echo "=== waiting for ${#PIDS[@]} lanes ==="
fail=0
for pid in "${PIDS[@]}"; do wait "$pid" || fail=$((fail+1)); done
echo "=== all lanes completed (failed $fail). Summary: ==="
"$YAML_PY" "$SUITE/collect.py" --stages 2>/dev/null || true

[[ "$fail" == 0 ]]
