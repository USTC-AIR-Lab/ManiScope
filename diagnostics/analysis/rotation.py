"""Target reassignment: classify each frozen initial state by the objects selected under its k instructions.

Selection is the first candidate displaced by at least 5 cm (CompoScene first_moved). A state is
  follow   every instruction selects its own target
  no_move  no instruction displaces any candidate
  fixed    every instruction selects the same candidate
  mixed    otherwise
The instruction-blind reference is a chooser that picks uniformly among the k candidates regardless of the
instruction: follow k^-k and fixed k^(1-k) per state. The empty-instruction runs give each policy's
instruction-independent preference.
Usage: python diagnostics/analysis/rotation.py runs/diagnostics/rotation [--json out.json]
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import load, pct, wilson  # noqa: E402
from conditions import ROTATION  # noqa: E402

CLASSES = ("follow", "fixed", "no_move", "mixed")


def classify(runs):
    fm = [r["first_moved"] for r in runs]
    if all(r["first_moved"] == r["target_role"] for r in runs):
        return "follow"
    if all(f is None for f in fm):
        return "no_move"
    return "fixed" if len(set(fm)) == 1 else "mixed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json")
    a = ap.parse_args()
    recs = load(a.root)
    k = {s: sum(c != "empty" for c, _, _ in conds) for s, conds in ROTATION.items()}
    by_state = defaultdict(dict)
    empty = defaultdict(Counter)
    sel = defaultdict(lambda: [0, 0])
    for r in recs:
        p, s = r["_policy"], r["task"]
        if r["condition"] == "empty":
            empty[(p, s)][str(r["first_moved"])] += 1
            continue
        by_state[(p, s, r["seed"])][r["condition"]] = r
        sel[(p, s, r["condition"])][0] += r["first_moved"] == r["target_role"]
        sel[(p, s, r["condition"])][1] += 1
    cls = defaultdict(lambda: defaultdict(Counter))
    for (p, s, _), d in by_state.items():
        if len(d) == k[s]:
            cls[p][s][classify(list(d.values()))] += 1
            cls[p][s]["states"] += 1
    out = {}
    print("policy        states  " + "  ".join(f"{c:>16}" for c in CLASSES) + "   blind follow/fixed")
    for p in sorted(cls):
        tot = sum(cls[p].values(), Counter())
        n = tot["states"]
        blind = [sum(cls[p][s]["states"] * k[s] ** e(k[s]) for s in cls[p]) / n
                 for e in (lambda x: -x, lambda x: 1 - x)]
        print(f"{p:13} {n:6}  " + "  ".join(f"{pct(tot[c], n):>16}" for c in CLASSES)
              + f"   {100 * blind[0]:.0f}% / {100 * blind[1]:.0f}%")
        out[p] = dict(states=n, **{c: tot[c] for c in CLASSES},
                      follow_wilson95=[round(100 * x, 1) for x in wilson(tot["follow"], n)],
                      blind_follow=blind[0], blind_fixed=blind[1],
                      by_scene={s: dict(cls[p][s]) for s in sorted(cls[p])},
                      selection_by_instruction={f"{s}/{c}": sel[(p, s, c)] for s in ROTATION for c, _, _ in ROTATION[s]
                                                if (p, s, c) in sel},
                      empty_instruction_first_moved={s: dict(empty[(p, s)]) for s in ROTATION if (p, s) in empty})
    for p in sorted(out):
        print(f"\n{p}: per scene (follow/fixed/no_move/mixed of states)")
        for s, c in out[p]["by_scene"].items():
            pref = out[p]["empty_instruction_first_moved"].get(s, {})
            print(f"  {s:24} " + "/".join(str(c.get(x, 0)) for x in CLASSES) + f" of {c['states']}"
                  + f"   empty instruction first moved: {pref}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
