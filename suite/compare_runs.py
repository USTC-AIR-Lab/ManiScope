# -*- coding: utf-8 -*-
"""Compare scene CSVs across runs and match episodes by recorded seeds. Shared seed identity alone does not establish equal instructions, interfaces or budgets."""
import csv, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNS = sys.argv[1:] or ["formal_dm05_20260911", "formal_wla_20260911"]
TITLE = {"dm05": "DM0.5", "wla": "WLA", "wla_wrong": "WLA (excluded internal run)", "wla_formal": "WLA", "pi05": "Pi0.5", "xvla": "X-VLA", "pi0": "pi0", "starvla": "StarVLA", "fastwam": "FastWAM", "ahawam": "AHA-WAM", "eventvla": "EventVLA", "xwam": "X-WAM", "g05": "GalaxeaVLA(G0.5)", "openwam": "OpenWAM-α", "motus": "Motus", "lingbot_va": "LingBot-VA", "gpt6": "GPT-6 Astra(high)", "gemini31pro": "Gemini 3.1 Pro(high)", "claude51": "Claude Fable 5.1(high)", "gemini38flash": "Gemini 3.8 Flash(high)"}


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
src_lines = ["## Model sources", ""] + [
    "- **%s**: weights %s; code %s" % (TITLE.get(q, q), _PE.get(q, {}).get("hf_repo", "—"), _PE.get(q, {}).get("code_repo", "—"))
    for q in pols] + [""]
_rest = [q for q in _PE if q not in pols and _PE[q].get("hf_repo")]
if _rest:
    src_lines += ["**Planned / not included in comparison**", ""] + [
        "- **%s**: weights %s; code %s" % (TITLE.get(q, q), _PE[q].get("hf_repo", "—"), _PE[q].get("code_repo", "—"))
        for q in _rest] + [""]
o = ["# Evaluation comparison", ""] + src_lines + [
     "> Per-scene rates use the recorded episode counts. Brackets show 95% Wilson intervals;",
     "> Delta is relative to **%s** in percentage points." % names[0], "",
     "Compared runs:" + "、".join("`%s`" % r for r in RUNS), ""]


hdr = "| Family | Level | Scene | " + " | ".join(names) + " | " + " | ".join("Δ %s" % n for n in names[1:]) + " |"
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


def summ(title, acc, keyfmt):
    out = ["", "## %s" % title, "", "| %s | " % title + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for k in sorted(acc):
        row = []
        for i in range(len(RUNS)):
            xs = acc[k][i]; row.append("%.3f (n=%d)" % (sum(xs) / len(xs), len(xs)) if xs else "—")
        out.append("| %s | %s |" % (keyfmt(k), " | ".join(row)))
    return out
o += summ("Mean by family", dim_acc, lambda k: k)
o += summ("Mean by level", tier_acc, lambda k: "L%s" % k)
allm = ["%.3f" % (sum(float(r["success_rate"]) for r in s.values()) / len(s)) if s else "—" for s in S]
o += ["", "**Mean across 48 scenes**:" + "、".join("%s %s" % (n, m) for n, m in zip(names, allm)), ""]


for j in range(1, len(RUNS)):
    a, b = E[0], E[j]
    keys = sorted(set(a) & set(b))
    ab = sum(1 for k in keys if a[k] and b[k]); a_only = sum(1 for k in keys if a[k] and not b[k])
    b_only = sum(1 for k in keys if b[k] and not a[k]); nn = sum(1 for k in keys if not a[k] and not b[k])
    o += ["## Matched episodes: %s vs %s (%d shared seeds)" % (names[0], names[j], len(keys)), "",
          "| Both succeed | Only %s succeeds | Only %s succeeds | Both fail |" % (names[0], names[j]), "|---|---|---|---|",
          "| %d | %d | %d | %d |" % (ab, a_only, b_only, nn), ""]

open(os.path.join(HERE, "EVAL_COMPARE.md"), "w", encoding="utf-8").write("\n".join(o) + "\n")
print("Wrote suite/EVAL_COMPARE.md: %d scenes x %d systems" % (len(scenes), len(RUNS)))
