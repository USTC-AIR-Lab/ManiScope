"""Summarize agent termination from completed-scene _agent_timing.jsonl and displacement logs. Usage: python3 suite/termination_report.py <run> [<run> ...]."""
import sys, os, glob, json, re, collections
TITLE = {"gpt6": "GPT-6 Astra(high)", "gemini38flash": "Gemini 3.8 Flash(high)", "claude51": "Claude Fable 5.1(high)"}
def pol_of(run): return run.split("_")[1]
out = ["# Agent termination statistics", "", "First five frozen seeds per scene; include only scenes with saved `_result.txt`, excluding `_failed/`.",
       "Termination: `env_success`: predicate met; `model_finish`: finish tool; `wall_budget_3300s`: 55-minute wall limit; `budget`: 120-call limit; `step_limit`: simulation-step limit.", ""]
for run in sys.argv[1:]:
    pol = pol_of(run); rows = []
    for t in glob.glob(f"eval_result/{run}/*/*/*/*/*/_agent_timing.jsonl"):
        d = os.path.dirname(t); scene = t.split("/")[2]
        if not os.path.exists(os.path.join(d, "_result.txt")): continue
        lift = {}
        lp = os.path.join(d, "_lift.txt")
        if os.path.exists(lp):
            for l in open(lp):
                m = re.match(r"episode(\d+)\t.*target_displacement=([-\d.]+|-)\tmax_distractor_displacement=([-\d.]+|-)", l)
                if m and m.group(2) != "-": lift[int(m.group(1))] = (float(m.group(2)), float(m.group(3)) if m.group(3) != "-" else 0.0)
        for l in open(t):
            e = json.loads(l); e["scene"] = scene; e["lift"] = lift.get(e["episode"]); rows.append(e)
    n = len(rows); scenes = len({r["scene"] for r in rows})
    term = collections.Counter(r.get("termination") for r in rows)
    succ = collections.Counter(r.get("termination") for r in rows if r.get("success"))
    out += [f"## {TITLE.get(pol, pol)} · `{run}` · {scenes} scenes / {n} episodes", "", "| Termination | Episodes | Share | Native successes | Success within category |", "|---|---|---|---|---|"]
    for k, v in term.most_common():
        out.append(f"| {k} | {v} | {v/n:.1%} | {succ.get(k,0)} | {succ.get(k,0)/v:.1%} |")
    mf = [r for r in rows if r.get("termination") == "model_finish"]
    mf_ok = sum(1 for r in mf if r.get("success"))
    total_ok = sum(1 for r in rows if r.get("success"))
    out += ["", f"- Native success {total_ok}/{n} = {total_ok/n:.3f}. Success is checked each step and terminates as env_success;",
            f"  model_finish indicates stopping before the native predicate passes: {len(mf)}/{n} = {len(mf)/n:.1%};",
            f"  non-success without model finish, ending at a budget: {n-len(mf)-total_ok} ({(n-len(mf)-total_ok)/n:.1%})."]
    # Classify completed model-finish failures by recorded displacement; skip incomplete scenes.
    cat = collections.Counter(); ex = collections.defaultdict(list)
    for r in mf:
        if r.get("success"): continue
        lf = r["lift"]
        if lf is None: c = "F No displacement telemetry (press/articulated tasks)"
        elif lf[0] < 0.03: c = "A Target barely moved"
        elif lf[0] > 1.0: c = "B Target left the table"
        elif lf[1] > lf[0]: c = "C Distractor displacement exceeds target displacement"
        elif lf[1] > 0.05: c = "D Target moved; distractor displacement exceeds 5 cm"
        else: c = "E Target moved without distractor motion; final goal unmet"
        cat[c] += 1; ex[c].append(f"{r['scene']}#{r['episode']}")
    if cat:
        out += ["", "Classify native failures ending with model_finish using recorded displacement:", "", "| Category | Count | Share | Example |", "|---|---|---|---|"]
        tot = sum(cat.values())
        for c in sorted(cat): out.append(f"| {c} | {cat[c]} | {cat[c]/tot:.0%} | {', '.join(ex[c][:3])} |")
    out.append("")
open("suite/AGENT_TERMINATION_STATS.md", "w", encoding="utf-8").write("\n".join(out) + "\n"); print("Wrote suite/AGENT_TERMINATION_STATS.md")
