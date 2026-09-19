#!/usr/bin/env python3
"""汇总所有 policy 在所有组合场景上的结果，输出对比表。

单内核之后结果只有一棵树（仓库自己的 eval_result）：
    eval_result/<task>/<POLICY_NAME>/<task_config>/<ckpt>/<时间戳>/_result*.txt
同一 (task, task_config, ckpt) 有多次结果时取时间戳最新的。

用法:
    python3 suite/collect.py                 # 全部
    python3 suite/collect.py --stages        # 附带各场景的 stage 分布
    python3 suite/collect.py --gradient      # 难度梯度自检：L1->L4 成功率是否单调下降
"""
import argparse
import collections
import glob
import json
import os
import re

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # 仓库根
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
# policies.yaml 里登记的列顺序（ckpt_setting -> 展示名）
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


# 两种布局都收：
#   旧  eval_result/<task>/<policy>/<tcfg>/<ckpt>/<ts>/_result*.txt
#   新  eval_result/<RUN_NAME>/<task>/<policy>/<tcfg>/<ckpt>/<ts>/_result*.txt
# 下标从**末尾**数，所以多一级也不影响解析。
_seen_files = set()
for pattern in ("/*/*/*/*/*/_result*.txt", "/*/*/*/*/*/*/_result*.txt"):
    for f in glob.glob(EVAL_RESULT + pattern):
        if f in _seen_files:
            continue
        _seen_files.add(f)
        p = f.split("/")
        note(p[-6], p[-4], p[-3], p[-2], f)

if not rows:
    raise SystemExit("没有找到任何结果（" + EVAL_RESULT + "）")

ckpts = [c for c in col_order if any(c in v for v in rows.values())]
ckpts += sorted({c for v in rows.values() for c in v} - set(ckpts))

w = max([len(t) for t, _ in rows] + [22])
DASH = "-"
hdr = "{:<{w}}  {:<22}  {:<16}  ".format("场景", "维度", "配置", w=w) + "  ".join("{:>8}".format(c) for c in ckpts)
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
    print("\n（基线 / 未登记场景）")
    for task, tcfg in extra:
        line(task, tcfg, "")


def show_stages():
    files = sorted(glob.glob(SUITE_RESULTS + "/*_stages.json"))
    if not files:
        return
    print("\n=== stage 分布（组合场景）===")
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
    """难度梯度自检：同一策略在 L1 -> L4 上成功率必须单调下降。

    不单调说明分级是错的 —— 要么某一档的判据松紧不对，要么干扰物强度没拉开。
    这是套件的自检项，不是策略的成绩：违例了要回去改场景，不是改策略。
    读 scenes_v2.yaml 的 tier 字段；v1 的 scenes_v2.yaml 没有 tier，这一节会自动跳过。
    """
    if not tier_of:
        print("\n（场景清单里没有 tier 字段，跳过难度梯度自检；v2 清单才有）")
        return
    print("\n=== 难度梯度自检（L1 -> L4 成功率应单调下降）===")
    for ck in ckpts:
        per = collections.defaultdict(list)
        for (task, tcfg), v in rows.items():
            t = tier_of.get(task)
            if t and ck in v:
                per[t].append(v[ck][1])
        got = sorted(per)
        if len(got) < 2:
            print("  {:<12} 数据不足（只有 {} 个难度档有结果）".format(ck, len(got)))
            continue
        means = [(t, sum(per[t]) / len(per[t]), len(per[t])) for t in got]
        body = "  ".join("L{}={:.2f}(n={})".format(t, m, n) for t, m, n in means)
        bad = [(a[0], b[0]) for a, b in zip(means, means[1:]) if b[1] > a[1] + 0.02]
        flag = "OK" if not bad else "违例: " + ", ".join("L{}<L{}".format(a, b) for a, b in bad)
        print("  {:<12} {}   {}".format(ck, body, flag))
        if bad:
            print("           ^ 分级可疑：回去看这两档的判据松紧和干扰物强度，别改策略")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", action="store_true", help="附带各场景 stage 分布")
    ap.add_argument("--gradient", action="store_true", help="难度梯度自检（L1->L4 是否单调）")
    a = ap.parse_args()
    if a.stages:
        show_stages()
    if a.gradient:
        show_gradient()
