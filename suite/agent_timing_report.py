"""Aggregate per-episode agent API, execution, wall-time and token records."""
import csv, glob, json, os, sys
RUN = sys.argv[1]; POL = sys.argv[2]
rows = []
for f in glob.glob(f"eval_result/{RUN}/*/*/*/*/*/_agent_timing.jsonl"):
    if "/_failed/" in f: continue
    scene = f.split("/")[2]
    for l in open(f, encoding="utf-8"):
        if l.strip():
            d = json.loads(l); d["scene"] = scene; rows.append(d)
meta = {r["scene"]: r for r in csv.DictReader(open(f"eval_result/{RUN}/scenes.csv", encoding="utf-8-sig"))}
def m(xs): return sum(xs) / max(1, len(xs))
by = {}
for r in rows: by.setdefault(r["scene"], []).append(r)
o = [f"# {POL} agent timing (run `{RUN}`)", "",
     "Simulation pauses during inference. API and execution time are measured separately; inspect metadata for episode and seed counts.", "",
     "| Family | Level | Scene | Success | Calls | API seconds | Execution seconds | Wall seconds | Reasoning tokens | Input tokens | Termination |",
     "|---|---|---|---|---|---|---|---|---|---|---|"]
from collections import Counter
for s in sorted(by, key=lambda s: (meta.get(s, {}).get("dim", ""), s)):
    rs = by[s]; t = Counter(r.get("termination") or "running" for r in rs)
    o.append("| %s | L%s | `%s` | %d/%d | %.1f | %.0f | %.0f | %.0f | %.0f | %.0f | %s |" % (
        meta.get(s, {}).get("dim", ""), meta.get(s, {}).get("tier", ""), s, sum(r["success"] for r in rs), len(rs),
        m([r["api_calls"] for r in rs]), m([r["api_seconds"] for r in rs]), m([r["exec_seconds"] for r in rs]),
        m([r["wall_seconds"] for r in rs]), m([r["reasoning_tokens"] for r in rs]), m([r["input_tokens"] for r in rs]),
        ", ".join(f"{k}×{v}" for k, v in t.most_common())))
succ = [r for r in rows if r["success"]]; fail = [r for r in rows if not r["success"]]
o += ["", "## Summary", "",
      f"- Episodes {len(rows)}, successes {len(succ)} ({100*len(succ)/max(1,len(rows)):.1f}%)",
      f"- Per episode: calls {m([r['api_calls'] for r in rows]):.1f}, API {m([r['api_seconds'] for r in rows]):.0f} s, execution {m([r['exec_seconds'] for r in rows]):.0f} s, wall {m([r['wall_seconds'] for r in rows]):.0f} s",
      f"- Mean API response {sum(r['api_seconds'] for r in rows)/max(1,sum(r['api_calls'] for r in rows)):.1f} s",
      f"- Successful episodes: calls {m([r['api_calls'] for r in succ]):.1f} / API {m([r['api_seconds'] for r in succ]):.0f} s / execution {m([r['exec_seconds'] for r in succ]):.0f} s; failed episodes: calls {m([r['api_calls'] for r in fail]):.1f} / API {m([r['api_seconds'] for r in fail]):.0f} s / execution {m([r['exec_seconds'] for r in fail]):.0f} s",
      f"- Total tokens: input {sum(r['input_tokens'] for r in rows):,}, cached {sum(r['cached_input_tokens'] for r in rows):,}, output {sum(r['output_tokens'] for r in rows):,}, reasoning {sum(r['reasoning_tokens'] for r in rows):,}",
      f"- Total API {sum(r['api_seconds'] for r in rows)/3600:.1f} h, execution {sum(r['exec_seconds'] for r in rows)/3600:.1f} h, wall {sum(r['wall_seconds'] for r in rows)/3600:.1f} h",
      f"- Termination reasons: {dict(Counter(r.get('termination') for r in rows))}", ""]
out = f"suite/AGENT_TIMING_{POL}.md"; open(out, "w", encoding="utf-8").write("\n".join(o)); print("Wrote", out, len(rows), "records")
