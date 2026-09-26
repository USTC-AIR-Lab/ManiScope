#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROBOTWIN_PYTHON:-python3}"
TAG="${TAG:-run}"; TARGET="${TARGET:-2}"; TRIES="${TRIES:-8}"
cd "$ROOT"; mkdir -p logs_smoke2
TASKS=("$@"); NG="${NUM_GPUS:-1}"
declare -A Q
i=0; for t in "${TASKS[@]}"; do g=$((i%NG)); Q[$g]="${Q[$g]:-} $t"; i=$((i+1)); done
worker(){ local g=$1; shift
  for t in "$@"; do
    env CUDA_VISIBLE_DEVICES=$g NVIDIA_DRIVER_CAPABILITIES=all PYTHONWARNINGS=ignore \
      "$PY" suite/diag/expert_smoke.py "$t" --target $TARGET --max_tries $TRIES \
      > "logs_smoke2/${t}.log" 2>&1
    grep -hE "^\[" "logs_smoke2/${t}.log" >> "logs_smoke2/_${TAG}.summary" || echo "[FAIL] $t: no output" >> "logs_smoke2/_${TAG}.summary"
  done
}
: > "logs_smoke2/_${TAG}.summary"
for g in $(seq 0 $((NG-1))); do [ -z "${Q[$g]:-}" ] && continue; worker "$g" ${Q[$g]} & done
wait
echo "=== $TAG done ==="
sort "logs_smoke2/_${TAG}.summary"
