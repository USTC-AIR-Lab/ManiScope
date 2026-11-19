#!/usr/bin/env bash
# Development-set entry point: check the interface, run the six development scenes, export a
# submission file and validate it. See docs/SUBMISSIONS.md.
#
#   DRY_RUN=1 bash suite/run_dev_check.sh <policy_key>   # inputs only, no simulator, no model calls
#   bash suite/run_dev_check.sh <policy_key>
#
# Development seeds are generated locally; the resulting numbers are not leaderboard numbers.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
POLICY="${1:?Usage: run_dev_check.sh POLICY_KEY}"
[[ "$POLICY" =~ ^[a-zA-Z0-9_]+$ ]] || { echo 'Invalid policy key' >&2; exit 2; }

EPISODES="${EPISODES:-$("$YAML_PY" -c 'import yaml;print(yaml.safe_load(open("suite/dev_set.yaml"))["episodes_per_scene"])')}"
mapfile -t SCENES < <("$YAML_PY" -c 'import yaml;print("\n".join(yaml.safe_load(open("suite/dev_set.yaml"))["scenes"]))')
RUN_NAME="${RUN_NAME:-dev_${POLICY}_$(date -u +%Y%m%dT%H%M%SZ)}"
DISPLAY_NAME="${DISPLAY_NAME:-$POLICY}"
TRACK="${TRACK:-standard_agent}"
KIND="${KIND:-agent}"
OUT="${OUT:-$ROOT/submissions/out/${RUN_NAME}.json}"

"$YAML_PY" -c 'import sys,yaml; p=yaml.safe_load(open("suite/policies.yaml"))["policies"]; sys.exit("Unregistered policy key: "+sys.argv[1]) if sys.argv[1] not in p else None' "$POLICY"

# Development seeds: generated here, never the organizer-held formal lists.
for T in "${SCENES[@]}"; do
  if [[ ! -f "suite/seeds/$T.json" ]]; then
    if [[ "${DRY_RUN:-0}" == 1 ]]; then
      echo "note: suite/seeds/$T.json is absent; a real run generates it with suite/gen_seeds.py"
    else
      echo "Generating $EPISODES development seeds for $T (simulator required)"
      "$ROBOTWIN_PYTHON" suite/gen_seeds.py "$T" "$EPISODES"
    fi
  fi
done

if [[ "${DRY_RUN:-0}" == 1 ]]; then
  ROBOTWIN_FROZEN_SEEDS=0 "$YAML_PY" tools/preflight.py --episodes "$EPISODES" "${SCENES[@]}"
  echo "Dry run ok: $POLICY on ${#SCENES[@]} development scenes x $EPISODES episodes"
  exit 0
fi

EPISODES="$EPISODES" RUN_NAME="$RUN_NAME" bash suite/run_suite.sh "$POLICY" "${SCENES[@]}"

mkdir -p "$(dirname "$OUT")"
"$YAML_PY" tools/export_submission.py "eval_result/$RUN_NAME" --out "$OUT" \
  --display-name "$DISPLAY_NAME" --track "$TRACK" --kind "$KIND" \
  ${MODEL_ID:+--model-id "$MODEL_ID"} ${API_INTERFACE:+--api-interface "$API_INTERFACE"} \
  ${REASONING:+--reasoning "$REASONING"} ${OUTPUT_CAP_TOKENS:+--output-cap-tokens "$OUTPUT_CAP_TOKENS"} \
  --max-model-calls "${MAX_MODEL_CALLS:-120}" --wall-time-s "${WALL_TIME_S:-3300}" \
  ${WALL_EXCLUDES_API_WAIT:+--wall-excludes-api-wait}
"$YAML_PY" tools/validate_submission.py "$OUT"
echo "Attach $OUT to the evaluation request (docs/SUBMISSIONS.md)."
