"""Aggregate per-episode _latency.txt. Model-side time is the server-reported inference interval; eval wall includes execution, and episode wall includes the full episode. Report actual deployment conditions rather than treating these as isolated speed benchmarks."""
import glob, os, sys, csv
runs = sys.argv[1:]
TITLE = {"dm05":"DM0.5","wla_wrong":"WLA (excluded internal run)","pi05":"Pi0.5","xvla":"X-VLA","pi0":"pi0","wla_formal":"WLA","starvla":"StarVLA","fastwam":"FastWAM","ahawam":"AHA-WAM","g05":"GalaxeaVLA(G0.5)","openwam":"OpenWAM-α","motus":"Motus","lingbot_va":"LingBot-VA","gpt6":"GPT-6 Astra(high)","gemini31pro":"Gemini 3.1 Pro(high)","claude51":"Claude Fable 5.1(high)","gemini38flash":"Gemini 3.8 Flash(high)","xwam":"X-WAM"}
def load(run):
    rows = []
    for f in glob.glob(f"eval_result/{run}/*/*/*/*/*/_latency.txt"):
        if "/_failed/" in f or "/_staged_orig/" in f: continue
        scene = f.split("/")[2]
        for l in open(f):
            p = l.strip().split("\t")
            if len(p) < 2: continue
            d = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in p[1:] if "=" in kv}
            d["scene"] = scene; d["ep"] = p[0]; rows.append(d)
    return rows
o = ["# Per-episode inference and execution timing", "",
     "> Model time is server-reported inference including preprocessing; eval wall includes action execution and rendering.",
     "> The first episode can include warmup/compilation. Timing reflects the recorded deployment, not an isolated speed benchmark.", "",
     "| System | Episodes | Calls/episode | Model/call (s) | Model/call p50/p95 (s) | Model/episode (s) | Eval wall/episode (s) | Steps | Episode wall (s) | Model share |",
     "|---|---|---|---|---|---|---|---|---|---|"]
for run in runs:
    pol = run[len("formal_"):run.rfind("_")]
    rows = load(run)
    if not rows: continue
    n = len(rows); calls = sum(r["calls"] for r in rows); mt = sum(r["model_total"] for r in rows)
    per = sorted(r["model_total"] / max(1, r["calls"]) for r in rows)
    ew = sum(r["eval_wall_total"] for r in rows); st = sum(r["steps"] for r in rows); epw = sum(r["episode_wall"] for r in rows)
    o.append("| %s | %d | %.1f | %.3f | %.3f / %.3f | %.1f | %.1f | %.0f | %.1f | %.0f%% |" % (
        TITLE.get(pol, pol), n, calls / n, mt / max(1, calls), per[n // 2], per[int(n * 0.95)], mt / n, ew / n, st / n, epw / n, 100 * mt / max(1, ew)))

    by = {}
    for r in rows: by.setdefault(r["scene"], []).append(r)
    with open(f"eval_result/{run}/latency_scenes.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["policy", "scene", "n", "calls_mean", "model_per_call_s", "model_per_episode_s", "eval_wall_per_episode_s", "steps_mean", "episode_wall_s"])
        for s in sorted(by):
            rs = by[s]; k = len(rs); c = sum(r["calls"] for r in rs); m = sum(r["model_total"] for r in rs)
            w.writerow([pol, s, k, round(c / k, 2), round(m / max(1, c), 4), round(m / k, 2), round(sum(r["eval_wall_total"] for r in rs) / k, 2), round(sum(r["steps"] for r in rs) / k, 1), round(sum(r["episode_wall"] for r in rs) / k, 2)])
# Compare the same first five frozen seeds per scene (240 episodes).
o += ["", "## Matched first-five-seed comparison (240 episodes)", "",
      "> Use episode0-4 per scene and audit actual instructions/interfaces; align timing and success on the same accepted records.", "",
      "| System | Episodes | Success (240) | Calls/episode | Model/call (s) | Model/call p50/p95 (s) | Model/episode (s) | Eval wall/episode (s) | Steps | Episode wall (s) |",
      "|---|---|---|---|---|---|---|---|---|---|"]
for run in runs:
    pol = run[len("formal_"):run.rfind("_")]
    rows = [r for r in load(run) if r["ep"].startswith("episode") and r["ep"][7:].isdigit() and int(r["ep"][7:]) < 5]
    if not rows: continue
    succ = None
    ep_csv = f"eval_result/{run}/episodes.csv"
    if os.path.exists(ep_csv):
        er = [x for x in csv.DictReader(open(ep_csv, encoding="utf-8-sig")) if x.get("episode", "").isdigit() and int(x["episode"]) < 5]
        if er: succ = sum(float(x["success"]) for x in er) / len(er)
    n = len(rows); calls = sum(r["calls"] for r in rows); mt = sum(r["model_total"] for r in rows)
    per = sorted(r["model_total"] / max(1, r["calls"]) for r in rows)
    ew = sum(r["eval_wall_total"] for r in rows); st = sum(r["steps"] for r in rows); epw = sum(r["episode_wall"] for r in rows)
    o.append("| %s | %d | %s | %.1f | %.3f | %.3f / %.3f | %.1f | %.1f | %.0f | %.1f |" % (
        TITLE.get(pol, pol), n, ("%.3f" % succ) if succ is not None else "—", calls / n, mt / max(1, calls), per[n // 2], per[min(n - 1, int(n * 0.95))], mt / n, ew / n, st / n, epw / n))
o += ["", "Per-scene detail: latency_scenes.csv in each run. Agent calls/tokens: AGENT_TIMING_<policy>.md.", ""]
open("suite/LATENCY.md", "w", encoding="utf-8").write("\n".join(o)); print("Wrote suite/LATENCY.md")
