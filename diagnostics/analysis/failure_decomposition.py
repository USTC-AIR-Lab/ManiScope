"""Decompose formal-run failures on the selection scenes by which objects were displaced >= 5 cm.

Reads the per-episode _lift.txt lines that script/eval_policy.py writes into each scene's output directory
(target_displacement, max_distractor_displacement, success / failure). Categories:
  S success; W only a distractor moved; T only the target moved; B both moved; N neither moved.
Usage: python diagnostics/analysis/failure_decomposition.py dm05=eval_result/formal_dm05 pi05=eval_result/formal_pi05 ...
  Each argument is <label>=<run root of suite/run_suite.sh>; when a scene was evaluated more than once, the
  latest output directory is used.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conditions import DECOMPOSITION_SCENES, DISPLACEMENT_M  # noqa: E402

CATS = ["S", "W", "T", "B", "N"]


def classify(line):
    t = re.search(r"target_displacement=([\d.]+)", line)
    d = re.search(r"max_distractor_displacement=([\d.]+)", line)
    if not t or not d:
        return None
    if line.rstrip().endswith("success"):
        return "S"
    tm, dm = float(t.group(1)) >= DISPLACEMENT_M, float(d.group(1)) >= DISPLACEMENT_M
    return {(False, True): "W", (True, False): "T", (True, True): "B", (False, False): "N"}[(tm, dm)]


def main(args):
    by_scene, by_policy, total = defaultdict(Counter), defaultdict(Counter), Counter()
    for arg in args:
        label, root = arg.split("=", 1)
        latest = {}
        for f in Path(root).rglob("_lift.txt"):
            scene = next((p for p in f.parts if p in DECOMPOSITION_SCENES), None)
            if scene and (scene not in latest or f.parent.name > latest[scene].parent.name):
                latest[scene] = f
        for scene, f in sorted(latest.items()):
            for line in f.read_text().splitlines():
                c = classify(line)
                if c:
                    by_scene[scene][c] += 1
                    by_policy[label][c] += 1
                    total[c] += 1
    fails = sum(total[c] for c in CATS[1:])
    print(f"episodes={sum(total.values())} success={total['S']} failures={fails}")
    for c, name in zip(CATS[1:], ("distractor only", "target only", "both", "neither")):
        print(f"  {c} {name:15}: {total[c]} ({100 * total[c] / max(fails, 1):.1f}% of failures)")
    print("\nscene\t" + "\t".join(CATS))
    for s, c in sorted(by_scene.items()):
        print(s + "\t" + "\t".join(str(c[k]) for k in CATS))
    print("\npolicy\t" + "\t".join(CATS) + "\tfailure shares W/T/B/N (%)")
    for p, c in by_policy.items():
        f = sum(c[k] for k in CATS[1:]) or 1
        print(p + "\t" + "\t".join(str(c[k]) for k in CATS) + "\t" + "/".join(f"{100 * c[k] / f:.1f}" for k in CATS[1:]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
