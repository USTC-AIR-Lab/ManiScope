# -*- coding: utf-8 -*-
"""Generate an evaluation report with family/level summaries and scene details."""
import glob, re, os, math, sys, yaml
from collections import defaultdict

RUN = sys.argv[sys.argv.index("--run")+1] if "--run" in sys.argv else "dm05_v3_clean"
# Infer policy identity from the run name; read model/code sources from policies.yaml.
_POL = RUN[len("formal_"):RUN.rfind("_")] if RUN.startswith("formal_") and RUN.count("_") >= 2 else "dm05"
_POL_TITLE = {"dm05": "DM0.5", "wla": "WLA", "wla_wrong": "WLA (excluded internal run)", "wla_formal": "WLA", "pi05": "Pi0.5", "xvla": "X-VLA", "pi0": "pi0", "starvla": "StarVLA"}.get(_POL, _POL)
_OUT = "EVAL_RESULTS.md" if _POL == "dm05" else "EVAL_RESULTS_%s.md" % _POL
HERE = os.path.dirname(os.path.abspath(__file__))

try:
    import yaml as _yaml
    _PE = _yaml.safe_load(open(os.path.join(HERE, "policies.yaml"), encoding="utf-8"))["policies"].get(_POL, {})
except Exception:
    _PE = {}
_SRC_LINES = []
if _PE.get("hf_repo"):
    _SRC_LINES.append("> - **Weights**: %s" % _PE["hf_repo"])
if _PE.get("code_repo"):
    _SRC_LINES.append("> - **Inference code**: %s" % _PE["code_repo"])
if _PE.get("desc"):
    _SRC_LINES.append("> - **Model notes**: %s" % str(_PE["desc"]).strip())
ROOT = os.path.dirname(HERE)
AX = {"skill_x_object": "D1 Skill x object", "skill_x_spatial": "D2 Skill x spatial",
      "attribute_binding": "D3 Attribute binding", "instruction_structure": "D4 Referring expressions",
      "skill_x_skill_temporal": "D5 Skill sequences", "mixture": "D6 Mixture"}

d = yaml.safe_load(open(os.path.join(HERE, "scenes_v2.yaml"), encoding="utf-8"))
meta = {}
for k, v in d["axes"].items():
    for s in (v["scenes"] or []):
        meta[s["name"]] = (AX[k], s.get("tier"), s.get("context", ""), s.get("smoke", ""))

res = {}
for f in glob.glob(os.path.join(ROOT, "eval_result", RUN, "*/*/*/*/*/_result.txt")):
    t = f.split(os.sep)[-6]
    vals = re.findall(r"^[0-9]*\.?[0-9]+$", open(f).read(), re.M)
    if vals:
        res[t] = float(vals[-1])

# Infer episode counts from frozen-seed files instead of hard-coding denominators for confidence intervals.

def _episodes_per_scene():
    import glob as _g, json as _j
    ns = []
    for f in _g.glob(os.path.join(HERE, "seeds", "*.json")):
        try:
            ns.append(len(_j.load(open(f, encoding="utf-8")).get("seeds") or []))
        except Exception:
            pass
    return max(ns) if ns else 20

EP = _episodes_per_scene()
rows = [(meta[t][0], meta[t][1], t, v, meta[t][2], meta[t][3]) for t, v in res.items() if t in meta]
rows.sort()
bd, bt = defaultdict(list), defaultdict(list)
for dim, tier, t, v, ctx, sm in rows:
    bd[dim].append(v); bt[tier].append(v)

HEAD_NOTE = [
    "> **Evaluation protocol**", ">",
    "> - 48 scenes x %d episodes; use the recorded protocol version and run metadata." % EP,
    "> - **Fixed seeds**: use the versioned scene seed files and initial-state summaries,",
    ">   reading the same ordered records rather than searching anew for each system;",
    ">   audit the actual instruction recorded for every episode.",
    "> - **Formal membership**: use the checked-in scenes_v2.yaml;",
    ">   development candidates and incomplete attempts do not belong in formal aggregates.",
    ">   Report any membership changes as a new protocol version.",
    "> - **Step limits differ by task**: 41 scenes use 1000 and seven use 600.",
    ">   Report per-task limits and actual system interfaces.",
    "> - **Preprocessing is model-specific**; the simulator supplies the configured views,",
    ">   normally head/left/right RGB at 320x240,",
    ">   and each adapter applies its documented resize/encoding and state inputs.",
    "> - See episodes.csv for recorded episode telemetry",
    ">   and scenes.csv for per-scene counts and uncertainty summaries.", "",
]

o = ["# %s evaluation results" % _POL_TITLE, ""] + (_SRC_LINES + [">"] if _SRC_LINES else []) + HEAD_NOTE + ["",
     "`eval_result/%s/` · %d episodes per scene · inspect run metadata for video retention" % (RUN, EP), "",
     "**Completed %d/%d scenes, %d episodes.**" % (len(rows), len(meta), len(rows) * EP), ""]

o += ["## Descriptive level trend", "",
      "Check observed level ordering; monotonicity alone does not validate a difficulty scale.", "",
      "| Level | Success rate | Scenes |", "|---|---|---|"]
ks = sorted(bt)
for k in ks:
    o.append("| L%d | **%.3f** | %d |" % (k, sum(bt[k]) / len(bt[k]), len(bt[k])))
means = [sum(bt[k]) / len(bt[k]) for k in ks]
viol = [(ks[i], ks[i + 1]) for i in range(len(ks) - 1) if means[i] < means[i + 1]]
o += ["", "**Observed trend: %s**" % ("Strictly decreasing" if not viol else "Non-monotonic at %s" % viol), ""]

o += ["## By task family", "",
      "Normal-approximation intervals use %d episodes per scene." % EP, "",
      "| Family | Success rate | 95% CI | Scenes | Episodes |", "|---|---|---|---|---|"]
for k in sorted(bd, key=lambda x: -sum(bd[x]) / len(bd[x])):
    v = bd[k]; m = sum(v) / len(v)
    ci = 1.96 * math.sqrt(max(m * (1 - m), 1e-9) / (EP * len(v)))
    o.append("| %s | **%.2f** | ±%.2f | %d | %d |" % (k, m, ci, len(v), EP * len(v)))
o.append("")

o += ["## Scene details", "",
      "Expert feasibility and policy success are distinct measurements.", "",
      "| Family | Level | Scene | Context | Expert | **Policy** |", "|---|---|---|---|---|---|"]
for dim, tier, t, v, ctx, sm in rows:
    o.append("| %s | L%s | `%s` | %s | %s | **%.2f** |" % (dim, tier, t, ctx, sm, v))

missing = sorted(n for n in meta if n not in res)
if missing:
    o += ["", "## Incomplete (%d)" % len(missing), "",
          "Incomplete records are excluded from completed-scene summaries.", ""]
    mb = defaultdict(list)
    for n in missing:
        mb[meta[n][0]].append(n)
    for k in sorted(mb):
        o.append("- **%s**：%s" % (k, "、".join("`%s`" % x for x in sorted(mb[k]))))

zero = [(dim, t, sm) for dim, tier, t, v, ctx, sm in rows if v == 0.0]
if zero:
    o += ["", "## Zero-success scenes for inspection", "",
          "Inspect retained trajectories and native predicates; zero success does not identify a failure cause.", "",
          "| Family | Scene | Expert yield |", "|---|---|---|"]
    for dim, t, sm in zero:
        o.append("| %s | `%s` | %s |" % (dim, t, sm))

open(os.path.join(HERE, _OUT), "w", encoding="utf-8").write("\n".join(o) + "\n")
print("Wrote %d scene results -> %s" % (len(rows), _OUT))
