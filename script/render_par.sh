#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/../suite/config.sh"
set -uo pipefail
GPUS_CSV="${1:?gpus}"; CONFIG="${2:?config}"; shift 2; TASKS=("$@")
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROBOTWIN_PYTHON:-python3}"
cd "$ROOT"; mkdir -p logs_render_compo
IFS="," read -ra GPUS <<< "$GPUS_CSV"; N=${#GPUS[@]}
declare -A Q; i=0
for t in "${TASKS[@]}"; do g=${GPUS[$((i%N))]}; Q[$g]="${Q[$g]:-} $t"; i=$((i+1)); done
worker(){ local g=$1; shift
  for t in "$@"; do
    env CUDA_VISIBLE_DEVICES=$g NVIDIA_DRIVER_CAPABILITIES=all PYTHONWARNINGS=ignore \
      "$PY" script/render_scenes.py "$t" --task_config "$CONFIG" --target 2 --max_tries 20 \
      --out "scene_gallery_compo/$t" --cam_type Large_D435 > "logs_render_compo/${t}.log" 2>&1
    ok=$(ls scene_gallery_compo/$t/*.png 2>/dev/null | wc -l)
    echo "[gpu$g] $t -> ${ok} imgs"
  done
}
PIDS=()
for g in "${GPUS[@]}"; do [ -z "${Q[$g]:-}" ] && continue; worker "$g" ${Q[$g]} & PIDS+=($!); done
for p in "${PIDS[@]}"; do wait "$p"; done
echo "ALL DONE"
