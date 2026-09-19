# -*- coding: utf-8 -*-
"""多策略逐场景并排对比（同冻结种子、同指令，可直接横比）。

用法: python3 suite/compare_runs.py formal_dm05_20260911 formal_wla_20260911 [更多 run...]
读各 run 目录下的 scenes.csv（collect_csv.py 产出），写 suite/EVAL_COMPARE.md：
  * 总表：每场景各策略成功率 + Wilson 95% CI，以及相对首个策略的差值
  * 按维度 / 难度的均值汇总
  * 逐条对齐：同一 seed 上「A 成 B 败 / A 败 B 成 / 都成 / 都败」计数（用 episodes.csv）
"""
import csv, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNS = sys.argv[1:] or ["formal_dm05_20260911", "formal_wla_20260911"]
TITLE = {"dm05": "DM0.5", "wla": "WLA", "wla_wrong": "WLA(内部误用)", "wla_formal": "WLA", "pi05": "Pi0.5", "xvla": "X-VLA", "pi0": "pi0", "starvla": "StarVLA", "fastwam": "FastWAM", "ahawam": "AHA-WAM", "eventvla": "EventVLA", "xwam": "X-WAM", "g05": "GalaxeaVLA(G0.5)", "openwam": "OpenWAM-α", "motus": "Motus", "lingbot_va": "LingBot-VA", "gpt6": "GPT-6 Astra(high)", "gemini31pro": "Gemini 3.1 Pro(high)", "claude51": "Claude Fable 5.1(high)", "gemini38flash": "Gemini 3.8 Flash(high)"}


def pol_of(run):
    return run[len("formal_"):run.rfind("_")] if run.startswith("formal_") else run


def load_scenes(run):
    p = os.path.join(ROOT, "eval_result", run, "scenes.csv")
    with open(p, encoding="utf-8-sig") as f:
        return {r["scene"]: r for r in csv.DictReader(f)}


def load_eps(run):
    p = os.path.join(ROOT, "eval_result", run, "episodes.csv")
    d = {}
    with open(p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            d[(r["scene"], r["seed"])] = int(r["success"] or 0)
    return d


pols = [pol_of(r) for r in RUNS]
names = [TITLE.get(p, p) for p in pols]
S = [load_scenes(r) for r in RUNS]
E = [load_eps(r) for r in RUNS]
scenes = sorted(set().union(*[set(s) for s in S]))

try:
    import yaml as _yaml
    _PE = _yaml.safe_load(open(os.path.join(HERE, "policies.yaml"), encoding="utf-8"))["policies"]
except Exception:
    _PE = {}
src_lines = ["## 各策略开源来源", ""] + [
    "- **%s**：权重 %s ；代码 %s" % (TITLE.get(q, q), _PE.get(q, {}).get("hf_repo", "—"), _PE.get(q, {}).get("code_repo", "—"))
    for q in pols] + [""]
_rest = [q for q in _PE if q not in pols and _PE[q].get("hf_repo")]
if _rest:
    src_lines += ["**待评测 / 接入中**（尚未进入本对比表）", ""] + [
        "- **%s**：权重 %s ；代码 %s" % (TITLE.get(q, q), _PE[q].get("hf_repo", "—"), _PE[q].get("code_repo", "—"))
        for q in _rest] + [""]
o = ["# 组合泛化评测 · 策略并排对比", ""] + src_lines + [
     "> 同一冻结种子集、同一指令，逐场景 100 条。括号内为 Wilson 95% 置信区间；",
     "> Δ 为相对 **%s** 的差值（百分点）。" % names[0], "",
     "对比的 run：" + "、".join("`%s`" % r for r in RUNS), ""]

# 总表
hdr = "| 维度 | 难度 | 场景 | " + " | ".join(names) + " | " + " | ".join("Δ %s" % n for n in names[1:]) + " |"
o += [hdr, "|" + "---|" * (3 + len(names) + len(names) - 1)]
dim_acc = defaultdict(lambda: [[] for _ in RUNS]); tier_acc = defaultdict(lambda: [[] for _ in RUNS])
for sc in scenes:
    base = next((s[sc] for s in S if sc in s), None)
    cells = []
    vals = []
    for i, s in enumerate(S):
        r = s.get(sc)
        if r is None:
            cells.append("—"); vals.append(None); continue
        v = float(r["success_rate"]); vals.append(v)
        cells.append("**%.2f** [%.2f, %.2f]" % (v, float(r["wilson_lo"]), float(r["wilson_hi"])))
        dim_acc[r["dim"]][i].append(v); tier_acc[r["tier"]][i].append(v)
    deltas = []
    for v in vals[1:]:
        deltas.append("%+.0f" % ((v - vals[0]) * 100) if (v is not None and vals[0] is not None) else "—")
    o.append("| %s | %s | `%s` | %s | %s |" % (base["dim"], base["tier"], sc, " | ".join(cells), " | ".join(deltas)))

# 汇总
def summ(title, acc, keyfmt):
    out = ["", "## %s" % title, "", "| %s | " % title + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for k in sorted(acc):
        row = []
        for i in range(len(RUNS)):
            xs = acc[k][i]; row.append("%.3f (n=%d)" % (sum(xs) / len(xs), len(xs)) if xs else "—")
        out.append("| %s | %s |" % (keyfmt(k), " | ".join(row)))
    return out
o += summ("按维度均值", dim_acc, lambda k: k)
o += summ("按难度均值", tier_acc, lambda k: "L%s" % k)
allm = ["%.3f" % (sum(float(r["success_rate"]) for r in s.values()) / len(s)) if s else "—" for s in S]
o += ["", "**48 场景总均值**：" + "、".join("%s %s" % (n, m) for n, m in zip(names, allm)), ""]

# 逐条对齐（两两，相对首个策略）
for j in range(1, len(RUNS)):
    a, b = E[0], E[j]
    keys = sorted(set(a) & set(b))
    ab = sum(1 for k in keys if a[k] and b[k]); a_only = sum(1 for k in keys if a[k] and not b[k])
    b_only = sum(1 for k in keys if b[k] and not a[k]); nn = sum(1 for k in keys if not a[k] and not b[k])
    o += ["## 逐条对齐：%s vs %s（共 %d 条同种子 episode）" % (names[0], names[j], len(keys)), "",
          "| 都成功 | 仅 %s 成功 | 仅 %s 成功 | 都失败 |" % (names[0], names[j]), "|---|---|---|---|",
          "| %d | %d | %d | %d |" % (ab, a_only, b_only, nn), ""]

open(os.path.join(HERE, "EVAL_COMPARE.md"), "w", encoding="utf-8").write("\n".join(o) + "\n")
print("写出 suite/EVAL_COMPARE.md：%d 场景 × %d 策略" % (len(scenes), len(RUNS)))
