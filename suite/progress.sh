#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/config.sh"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
printf "%-30s %-10s %s\n" "SCENE" "SUC/DONE" "STATE"
for L in suite/logs/dm05_*.log; do
  [ -f "$L" ] || continue
  sc=$(basename "$L" .log | sed 's/^dm05_//')
  case "$sc" in lane*|*server*|fix_*) continue;; esac
  r=$(sed -e 's/\x1b\[[0-9;]*m//g' "$L" 2>/dev/null | grep -oE 'Success rate: [0-9]+/[0-9]+' | tail -1 | sed 's/Success rate: //')
  fin=$(find "eval_result/$sc" -name _result.txt 2>/dev/null | head -1)
  st="running"; [ -n "$fin" ] && st="[done]"; [ -z "$r" ] && st="seed-select"
  printf "%-30s %-10s %s\n" "$sc" "${r:-0/0}" "$st"
done | sort
echo "-----"
echo "eval processes: $(ps -C python -o cmd= 2>/dev/null | grep -c eval_policy)   completed results: $(find eval_result -name _result.txt 2>/dev/null | wc -l)   $(date '+%H:%M:%S')"
