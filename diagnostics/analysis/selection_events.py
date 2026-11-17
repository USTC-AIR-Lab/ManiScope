"""Selection events and gripper-state contact classes on the formal pick-type scenes.

Per episode:
  first contact      the candidate touched first by any robot link (grip tracker first_touch; a tie is 'ambiguous')
  first displacement the first candidate displaced >= 5 cm (CompoScene first_moved)
  contact class      grasp / push / brush / none for the target and, most severe first, for the non-targets
                     (diagnostics/grip_tracker.py)
Each event is reported as target / non-target / none, crossed with task success, so correct selection without
completion and success after touching a non-target are both visible.
Usage: python diagnostics/analysis/selection_events.py runs/diagnostics/selection_events
"""
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load  # noqa: E402

SEVERITY = {"none": 0, "brush": 1, "push": 2, "grasp": 3}


def first_contact(r):
    objs = r["grip"]["objects"]
    touched = {k: v["first_touch"] for k, v in objs.items() if v["first_touch"] is not None}
    if not touched:
        return "none"
    t0 = min(touched.values())
    first = [k for k, t in touched.items() if t == t0]
    if len(first) > 1:
        return "ambiguous"
    return "target" if first[0] == r["target_role"] else "non-target"


def first_displacement(r):
    if r["first_moved"] is None:
        return "none"
    return "target" if r["first_moved"] == r["target_role"] else "non-target"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    a = ap.parse_args()
    recs = [r for r in load(a.root) if r.get("grip")]
    by = defaultdict(lambda: defaultdict(Counter))
    for r in recs:
        p, s = r["_policy"], "success" if r["success"] else "failure"
        objs = r["grip"]["objects"]
        others = r.get("distractor_roles") or [k for k in objs if k != r["target_role"]]
        worst = max((objs[k]["cls"] for k in others if k in objs), key=SEVERITY.get, default="none")
        by[p]["first contact"][(first_contact(r), s)] += 1
        by[p]["first displacement (5 cm)"][(first_displacement(r), s)] += 1
        by[p]["target contact class"][(objs.get(r["target_role"], {}).get("cls", "none"), s)] += 1
        by[p]["most severe non-target contact"][(worst, s)] += 1
    for p in sorted(by):
        n = sum(by[p]["first contact"].values())
        print(f"\n{p}  ({n} episodes)")
        for ev, c in by[p].items():
            cats = sorted({k for k, _ in c}, key=lambda x: (-SEVERITY.get(x, -1), x))
            print(f"  {ev:32} " + "  ".join(f"{k}: {c[(k, 'success')]}S/{c[(k, 'failure')]}F" for k in cats))


if __name__ == "__main__":
    main()
