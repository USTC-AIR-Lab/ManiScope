"""The two controls of target reassignment.

training_control: on unmodified RoboTwin training tasks, does the first displaced block (>= 5 cm) change with
  the instruction? Reported per condition: episodes, success, and the distribution of the first displaced block
  (keyed by attribute: red / green / blue or largest / medium / smallest), plus how often it matches the
  instructed attribute.
source_baseline: success on the linked RoboTwin source tasks with their training instruction (95% Wilson
  intervals); a checkpoint near zero here does not measure instruction following on the derived scenes.
Usage: python diagnostics/analysis/controls.py runs/diagnostics/training_control
       python diagnostics/analysis/controls.py runs/diagnostics/source_baseline
"""
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load, pct  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    a = ap.parse_args()
    recs = load(a.root)
    cells = defaultdict(list)
    for r in recs:
        cells[(r["_policy"], r["task"], r["condition"])].append(r)
    for (p, t, c), rs in sorted(cells.items()):
        n = len(rs)
        succ = sum(r["success"] for r in rs)
        first = Counter(str(r["first_moved"]) for r in rs)
        line = f"{p:12} {t:24} {c:9} n={n:3}  success {pct(succ, n):>14}"
        if any(r.get("maxdisp") for r in rs) and c not in ("train", "taskname"):
            match = sum(r["first_moved"] == c for r in rs) if c != "empty" else None
            line += f"  first displaced {dict(first)}" + (f"  matches instruction {pct(match, n)}" if match is not None else "")
        elif c == "train" and first.keys() - {"None"}:
            line += f"  first displaced {dict(first)}"
        print(line)


if __name__ == "__main__":
    main()
