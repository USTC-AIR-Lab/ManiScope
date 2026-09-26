#!/usr/bin/env python3
"""Collect latest result files per task/configuration/checkpoint from eval_result. Optional --stages reports recorded stage distributions; --gradient summarizes descriptive level trends."""
import argparse
import collections
import glob
import json
import os
import re

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # Repository root.
EVAL_RESULT = os.path.join(ROOT, "eval_result")
SUITE_RESULTS = os.path.join(HERE, "results")

_v2 = os.path.join(HERE, "scenes_v2.yaml")
SCENES_FILE = _v2 if os.path.exists(_v2) else os.path.join(HERE, "scenes_v2.yaml")
scenes = yaml.safe_load(open(SCENES_FILE))
policies = yaml.safe_load(open(os.path.join(HERE, "policies.yaml")))["policies"]

axis_of = {sc["name"]: ax for ax, b in scenes["axes"].items()
           for sc in (b.get("scenes") or []) if not str(sc["name"]).startswith("<")}
baseline_of = {sc["name"]: sc.get("baseline")
               for b in scenes["axes"].values() for sc in (b.get("scenes") or [])}
tier_of = {sc["name"]: sc.get("tier")
           for b in scenes["axes"].values() for sc in (b.get("scenes") or []) if sc.get("tier")}
# Use policies.yaml registration order for checkpoint display names.
col_order = [p.get("ckpt_setting") for p in policies.values() if p.get("ckpt_setting")]

# (task, task_config) -> {ckpt: (timestamp, value)}
rows = collections.defaultdict(dict)


def note(task, tcfg, ck, ts, path):
    vals = re.findall(r"^[0-9]*\.?[0-9]+$", open(path).read(), re.M)
    if not vals:
        return
    prev = rows[(task, tcfg)].get(ck)
    if prev is None or ts > prev[0]:
        rows[(task, tcfg)][ck] = (ts, float(vals[-1]))


# Accept both eval_result/task/... and eval_result/run/task/... layouts by parsing path components from the end.


_seen_files = set()
for pattern in ("/*/*/*/*/*/_result*.txt", "/*/*/*/*/*/*/_result*.txt"):
    for f in glob.glob(EVAL_RESULT + pattern):
        if f in _seen_files:
            continue
        _seen_files.add(f)
        p = f.split("/")
        note(p[-6], p[-4], p[-3], p[-2], f)

if not rows:
    raise SystemExit("No results found (" + EVAL_RESULT + "）")

ckpts = [c for c in col_order if any(c in v for v in rows.values())]
ckpts += sorted({c for v in rows.values() for c in v} - set(ckpts))

w = max([len(t) for t, _ in rows] + [22])
DASH = "-"
hdr = "{:<{w}}  {:<22}  {:<16}  ".format("Scene", "Family", "Configuration", w=w) + "  ".join("{:>8}".format(c) for c in ckpts)
print(hdr)
print("-" * len(hdr))


def line(task, tcfg, ax):
    cells = "  ".join(
        "{:>8.2f}".format(rows[(task, tcfg)][c][1]) if c in rows[(task, tcfg)] else "{:>8}".format(DASH)
        for c in ckpts)
    print("{:<{w}}  {:<22}  {:<16}  {}".format(task, ax, tcfg, cells, w=w))


seen = set()
for ax in scenes["axes"]:
    for sc in (scenes["axes"][ax].get("scenes") or []):
        for (task, tcfg) in sorted(rows):
            if task == sc["name"]:
                line(task, tcfg, ax)
                seen.add((task, tcfg))

extra = sorted(set(rows) - seen)
if extra:
    print("\n(Baseline / unregistered scenes)")
    for task, tcfg in extra:
        line(task, tcfg, "")


def show_stages():
    files = sorted(glob.glob(SUITE_RESULTS + "/*_stages.json"))
    if not files:
        return
    print("\n=== Recorded stage distribution ===")
    for f in files:
        try:
            data = json.load(open(f))
        except Exception:
            continue
        if not data:
            continue
        dist = collections.Counter(int(r.get("max_stage", 0)) for r in data)
        n = len(data)
        succ = sum(1 for r in data if r.get("success"))
        tag = os.path.basename(f)[:-len("_stages.json")]
        body = ", ".join("stage{}={}/{}".format(k, dist[k], n) for k in sorted(dist))
        print("  {:<32} success={}/{}  {}".format(tag, succ, n, body))


def show_gradient():
    """Inspect descriptive success trends by level using manifest tiers. Non-monotonicity flags a comparison for inspection; it does not by itself validate or invalidate a difficulty scale."""
    if not tier_of:
        print("\n(No manifest tier field; skipping level trend)")
        return
    print("\n=== Descriptive level trend (L1 -> L4) ===")
    for ck in ckpts:
        per = collections.defaultdict(list)
        for (task, tcfg), v in rows.items():
            t = tier_of.get(task)
            if t and ck in v:
                per[t].append(v[ck][1])
        got = sorted(per)
        if len(got) < 2:
            print("  {:<12} insufficient data (only {} levels with results)".format(ck, len(got)))
            continue
        means = [(t, sum(per[t]) / len(per[t]), len(per[t])) for t in got]
        body = "  ".join("L{}={:.2f}(n={})".format(t, m, n) for t, m, n in means)
        bad = [(a[0], b[0]) for a, b in zip(means, means[1:]) if b[1] > a[1] + 0.02]
        flag = "OK" if not bad else "Non-monotonic: " + ", ".join("L{}<L{}".format(a, b) for a, b in bad)
        print("  {:<12} {}   {}".format(ck, body, flag))
        if bad:
            print("           ^ Inspect task-group differences; this trend alone does not establish a cause.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", action="store_true", help="Include per-scene recorded stage distributions")
    ap.add_argument("--gradient", action="store_true", help="Inspect level trend (L1->L4)")
    a = ap.parse_args()
    if a.stages:
        show_stages()
    if a.gradient:
        show_gradient()
