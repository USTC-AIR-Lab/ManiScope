"""First-decision sensitivity: how much the first decision moves when the instruction, the layout, or only the sampling changes.

Each episode stops after the policy's first action chunk. For every pair of episodes that start from the
same frozen initial state, the distance is the RMS over the first STEPS steps and the 12 arm joints
(grippers excluded) of the commanded joint targets; policies that command end-effector poses are compared
on the joint states reached instead. Pairs:
  language: red vs blue instruction, same layout and repeat
  layout:   original vs red/blue blocks exchanged, same instruction and repeat
  noise:    two repeats of the same condition (the floor that the other two must clear)
  same_target: red/original vs blue/swapped (and blue/original vs red/swapped), same repeat: the instructed
            block sits at the same place while the word and the image change; small when the policy goes
            where the instructed colour is
Usage: python diagnostics/analysis/first_decision.py runs/diagnostics/first_decision [--out DIR]
"""
import argparse
import collections
import glob
import itertools
import json
import os

import numpy as np

STEPS = 16
ARM = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12]
ORDER = ["pi05", "g05", "pi0", "xvla", "wla_formal", "starvla", "dm05", "xwam", "motus", "fastwam", "ahawam", "lingbot_va"]


def load(runs):
    eps = collections.defaultdict(dict)
    meta = collections.defaultdict(lambda: {"chunk": [], "type": set(), "motion": []})
    for f in glob.glob(f"{runs}/*/*/*/probe.jsonl"):
        policy = f.split("/")[-4]
        for line in open(f):
            r = json.loads(line)
            fc = r.get("first_chunk")
            if not fc or not fc["commands"]:
                continue
            color, layout, rep = r["condition"].split("_")
            ee = fc["action_type"] != "qpos"
            traj = np.asarray(fc["joints"] if ee else fc["commands"], dtype=float)[:STEPS][:, ARM]
            eps[policy][(r["seed"], color, layout, rep)] = traj
            meta[policy]["motion"].append(float(np.sqrt(np.mean((traj - traj[0]) ** 2))))
            meta[policy]["chunk"].append(len(fc["commands"]))
            meta[policy]["type"].add(fc["action_type"])
    return eps, meta


def rms(a, b):
    n = min(len(a), len(b))
    return float(np.sqrt(np.mean((a[:n] - b[:n]) ** 2)))


def pairs(e):
    out = {"language": [], "layout": [], "noise": [], "same_target": []}
    keys = set(e)
    for (seed, color, layout, rep) in keys:
        other = "blue" if color == "red" else "red"
        if color == "red" and (seed, other, layout, rep) in keys:
            out["language"].append((seed, rms(e[(seed, color, layout, rep)], e[(seed, other, layout, rep)])))
        if layout == "original" and (seed, other, "swapped", rep) in keys:
            out["same_target"].append((seed, rms(e[(seed, color, layout, rep)], e[(seed, other, "swapped", rep)])))
        if layout == "original" and (seed, color, "swapped", rep) in keys:
            out["layout"].append((seed, rms(e[(seed, color, layout, rep)], e[(seed, color, "swapped", rep)])))
    reps = collections.defaultdict(dict)
    for (seed, color, layout, rep) in keys:
        reps[(seed, color, layout)][rep] = e[(seed, color, layout, rep)]
    for (seed, _, _), d in reps.items():
        for ra, rb in itertools.combinations(sorted(d), 2):
            out["noise"].append((seed, rms(d[ra], d[rb])))
    return out


def seed_bootstrap(vals, n=2000, rng=np.random.default_rng(0)):
    by_seed = collections.defaultdict(list)
    for s, v in vals:
        by_seed[s].append(v)
    seeds = sorted(by_seed)
    means = [np.mean([v for s in rng.choice(seeds, len(seeds)) for v in by_seed[s]]) for _ in range(n)]
    return float(np.mean([v for _, v in vals])), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default="first_decision_summary")
    a = ap.parse_args()
    eps, meta = load(a.root)
    summary = {}
    for p in sorted(eps, key=lambda p: ORDER.index(p) if p in ORDER else 99):
        pr = pairs(eps[p])
        row = {"episodes": len(eps[p]), "chunk_len": sorted(set(meta[p]["chunk"])),
               "action_type": sorted(meta[p]["type"]), "motion": float(np.mean(meta[p]["motion"]))}
        for k, v in pr.items():
            row[k] = dict(zip(("mean", "lo", "hi"), seed_bootstrap(v))) if v else None
            row[k + "_pairs"] = len(v)
        if row["noise"] and row["noise"]["mean"] > 0:
            for k in ("language", "layout"):
                if row[k]:
                    row[k + "_over_noise"] = row[k]["mean"] / row["noise"]["mean"]
        summary[p] = row
    os.makedirs(a.out, exist_ok=True)
    json.dump(summary, open(f"{a.out}/first_decision.json", "w"), indent=1)
    fmt = lambda d: "-" if not d else f"{d['mean']:.3f} [{d['lo']:.3f}, {d['hi']:.3f}]"
    lines = [f"# First-decision sensitivity (RMS rad over first {STEPS} steps, 12 arm joints)", "",
             "motion = RMS of the window's trajectory about its first step (how far the arm moves at all).", "",
             "| policy | eps | chunk | type | motion | language | layout | noise | same target | lang/noise | layout/noise |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p, r in summary.items():
        ratio = lambda k: f"{r[k]:.1f}" if k in r else "-"
        lines.append(f"| {p} | {r['episodes']} | {','.join(map(str, r['chunk_len']))} | {','.join(r['action_type'])} | "
                     f"{r['motion']:.3f} | "
                     f"{fmt(r['language'])} | {fmt(r['layout'])} | {fmt(r['noise'])} | {fmt(r['same_target'])} | "
                     f"{ratio('language_over_noise')} | {ratio('layout_over_noise')} |")
    open(f"{a.out}/first_decision.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
