#!/usr/bin/env bash
# ManipScope formal evaluator. See docs/EVALUATION.md.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
POLICY="${1:?Usage: run_suite.sh POLICY [SCENE ...]}"; shift
[[ "$POLICY" =~ ^[a-zA-Z0-9_]+$ ]] || { echo 'Invalid policy name' >&2; exit 2; }
EPISODES="${EPISODES:-50}"
SIM_GPU="${SIM_GPU:-0}"
TASK_CONFIG="${SCENE_TASK_CONFIG:-demo_clean}"
RUN_NAME="${RUN_NAME:-${POLICY}_$(date -u +%Y%m%dT%H%M%SZ)_$$}"
AUTO_LAUNCH="${AUTO_LAUNCH:-1}"
export ROBOTWIN_FROZEN_SEEDS="${ROBOTWIN_FROZEN_SEEDS:-1}"
export ROBOTWIN_VIDEO_FIRST_N="${ROBOTWIN_VIDEO_FIRST_N:-10}"
export EVAL_WRIST_VIDEO="${EVAL_WRIST_VIDEO:-0}"
for value in "$RUN_NAME" "$TASK_CONFIG"; do
  [[ "$value" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Run/config names must be simple path components' >&2; exit 2; }
done
field() { "$YAML_PY" -c 'import sys,yaml; p=yaml.safe_load(open("suite/policies.yaml"))["policies"][sys.argv[1]]; print(p.get(sys.argv[2]) or "")' "$POLICY" "$1"; }
POLICY_NAME="$(field policy_name)"; CKPT="$(field ckpt_setting)"; SERVER="$(field server)"
export PORT="${PORT:-$(field port)}"
LAUNCH="$(field launch)"
if [[ "$AUTO_LAUNCH" == 1 && -z "$LAUNCH" ]]; then
  echo 'This adapter needs an external service; use AUTO_LAUNCH=0. See docs/EXTERNAL_AGENT.md.' >&2; exit 2
fi
if (( $# )); then SCENES=("$@"); else
  mapfile -t SCENES < <("$YAML_PY" -c 'import yaml; s=yaml.safe_load(open("suite/scenes_v2.yaml")); print("\n".join(v["name"] for a in s["axes"].values() for v in a["scenes"]))')
fi
"$YAML_PY" tools/preflight.py --episodes "$EPISODES" --task-config "$TASK_CONFIG" "${SCENES[@]}"
if [[ "${DRY_RUN:-0}" == 1 ]]; then printf 'Validated %s scenes for %s; run=%s; port=%s\n' "${#SCENES[@]}" "$POLICY" "$RUN_NAME" "$PORT"; exit 0; fi
command -v "$ROBOTWIN_PYTHON" >/dev/null || { echo 'ROBOTWIN_PYTHON not executable' >&2; exit 2; }
command -v ffmpeg >/dev/null || { echo 'ffmpeg is required for evaluation videos' >&2; exit 2; }
[[ -d assets/objects && -d assets/embodiments ]] || { echo 'Assets missing; see docs/INSTALLATION.md' >&2; exit 2; }
if [[ "$AUTO_LAUNCH" == 1 ]]; then
  "$YAML_PY" -c 'import os,sys,yaml; p=yaml.safe_load(open("suite/policies.yaml"))["policies"][sys.argv[1]]; missing=[k for k in p.get("required_env",[]) if not os.environ.get(k)]; sys.exit("Set these paths in configs/local.env: " + ", ".join(missing)) if missing else None' "$POLICY"
fi
LOGS="$ROOT/suite/logs/$RUN_NAME"; mkdir -p "$LOGS"
port_open() { "$YAML_PY" -c 'import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(s.connect_ex(("127.0.0.1",int(sys.argv[1]))))' "$PORT"; }
SERVER_PID=''
cleanup() { if [[ -n "$SERVER_PID" ]]; then kill -TERM -- "-$SERVER_PID" 2>/dev/null || true; fi; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ "$AUTO_LAUNCH" == 1 ]]; then
  if port_open; then echo "Port $PORT already in use. Use AUTO_LAUNCH=0 to explicitly reuse a service." >&2; exit 2; fi
  GPU="${GPU:-$SIM_GPU}" setsid bash "$LAUNCH" > "$LOGS/server_${PORT}.log" 2>&1 & SERVER_PID=$!
  ready=0
  for ((i=0;i<${SERVER_WAIT_ATTEMPTS:-240};i++)); do
    if port_open; then ready=1; break; fi
    kill -0 "$SERVER_PID" 2>/dev/null || { echo "Service exited; see $LOGS/server_${PORT}.log" >&2; exit 1; }
    sleep 5
  done
  [[ "$ready" == 1 ]] || { echo 'Service startup timed out' >&2; exit 1; }
else
  port_open || { echo "No service listening on port $PORT" >&2; exit 1; }
fi
CONN=()
case "$SERVER" in
  socket) CONN=(--policy_port "$PORT");;
  http) CONN=(--base_url "http://127.0.0.1:$PORT");;
  *) echo 'Unsupported transport' >&2; exit 2;;
esac
# A shell-word list, not evaluated as code. Paths containing spaces should be in config files.
read -r -a EXTRA_ARGS <<< "${EXTRA_EVAL_ARGS:-}"
failed=0
for T in "${SCENES[@]}"; do
  OUTDIR="eval_result/$RUN_NAME/$T/$POLICY_NAME/$TASK_CONFIG/$CKPT/$(date -u +%Y%m%d_%H%M%S)"
  mkdir -p "$OUTDIR"
  "$YAML_PY" tools/run_metadata.py "$OUTDIR" "$POLICY" "$T" "$EPISODES" "$TASK_CONFIG"
  echo "Evaluating $T ($POLICY, $EPISODES episodes)"
  if env CUDA_VISIBLE_DEVICES="$SIM_GPU" NVIDIA_DRIVER_CAPABILITIES=all \
    STAGE_LOG="$ROOT/$OUTDIR/_stages.json" ATTR_BIND_LOG="$ROOT/$OUTDIR/_attr.jsonl" \
    NESTED_REF_LOG="$ROOT/$OUTDIR/_nested.jsonl" CUP_PAD_LOG="$ROOT/$OUTDIR/_cuppad.jsonl" \
    "$ROBOTWIN_PYTHON" script/eval_policy.py --config "policy/$POLICY_NAME/deploy_policy.yml" --overrides \
    --task_name "$T" --task_config "$TASK_CONFIG" --ckpt_setting "$CKPT" --seed "${SEED:-0}" \
    --policy_name "$POLICY_NAME" --eval_num_episodes "$EPISODES" \
    --max_success_videos "${MAX_SUCC_VIDEOS:-unlimited}" --max_failure_videos "${MAX_FAIL_VIDEOS:-unlimited}" \
    --eval_output_dir "$OUTDIR" "${CONN[@]}" "${EXTRA_ARGS[@]}" > "$LOGS/${T}.log" 2>&1; then
    echo "Completed $T"
  else
    echo "Failed $T; see $LOGS/${T}.log" >&2; failed=$((failed+1))
  fi
done
[[ "$failed" == 0 ]]
