"""汇总大模型 agent 评测的时间/调用/token 账本（_agent_timing.jsonl）-> suite/AGENT_TIMING_<pol>.md"""
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
o = [f"# {POL} agent 计时账本汇总（run `{RUN}`）", "",
     "仿真在模型推理期间暂停：API 时间与执行时间可分开统计。每场景 5 条（前 5 个冻结种子）。", "",
     "| 维度 | 难度 | 场景 | 成功 | 平均调用 | 平均 API 秒 | 平均执行秒 | 平均墙钟秒 | 平均推理 token | 平均输入 token | 终止原因 |",
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
o += ["", "## 总览", "",
      f"- episode 总数 {len(rows)}，成功 {len(succ)}（{100*len(succ)/max(1,len(rows)):.1f}%）",
      f"- 平均每条：调用 {m([r['api_calls'] for r in rows]):.1f} 次，API {m([r['api_seconds'] for r in rows]):.0f} s，执行 {m([r['exec_seconds'] for r in rows]):.0f} s，墙钟 {m([r['wall_seconds'] for r in rows]):.0f} s",
      f"- 单次 API 平均响应 {sum(r['api_seconds'] for r in rows)/max(1,sum(r['api_calls'] for r in rows)):.1f} s",
      f"- 成功 episode 平均：调用 {m([r['api_calls'] for r in succ]):.1f} 次 / API {m([r['api_seconds'] for r in succ]):.0f} s / 执行 {m([r['exec_seconds'] for r in succ]):.0f} s；失败 episode 平均：调用 {m([r['api_calls'] for r in fail]):.1f} 次 / API {m([r['api_seconds'] for r in fail]):.0f} s / 执行 {m([r['exec_seconds'] for r in fail]):.0f} s",
      f"- token 合计：输入 {sum(r['input_tokens'] for r in rows):,}（其中缓存命中 {sum(r['cached_input_tokens'] for r in rows):,}），输出 {sum(r['output_tokens'] for r in rows):,}，推理 {sum(r['reasoning_tokens'] for r in rows):,}",
      f"- API 总时长 {sum(r['api_seconds'] for r in rows)/3600:.1f} h，执行总时长 {sum(r['exec_seconds'] for r in rows)/3600:.1f} h，墙钟总时长 {sum(r['wall_seconds'] for r in rows)/3600:.1f} h",
      f"- 终止原因：{dict(Counter(r.get('termination') for r in rows))}", ""]
out = f"suite/AGENT_TIMING_{POL}.md"; open(out, "w", encoding="utf-8").write("\n".join(o)); print("写出", out, len(rows), "条")
