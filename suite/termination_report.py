"""LLM agent 终止方式统计：读各 run 下已完成场景的 _agent_timing.jsonl（每条 episode 一行：termination/success/api_calls...）
和 _lift.txt（目标/干扰物最大位移），输出 suite/AGENT_TERMINATION_STATS.md。用法: python3 suite/termination_report.py <run> [<run> ...]"""
import sys, os, glob, json, re, collections
TITLE = {"gpt6": "GPT-6 Astra(high)", "gemini38flash": "Gemini 3.8 Flash(high)", "claude51": "Claude Fable 5.1(high)"}
def pol_of(run): return run.split("_")[1]
out = ["# LLM agent 终止方式统计", "", "口径：每场景前 5 个冻结种子，只统计已落盘 `_result.txt` 的场景（不含 `_failed/`）。",
       "终止类型：`env_success` 判据在任一步满足即结束；`model_finish` 模型调用 finish 工具；`wall_budget_3300s` 单 episode 墙钟 55 min；`budget` 120 次调用上限；`step_limit` 步数上限。", ""]
for run in sys.argv[1:]:
    pol = pol_of(run); rows = []
    for t in glob.glob(f"eval_result/{run}/*/*/*/*/*/_agent_timing.jsonl"):
        d = os.path.dirname(t); scene = t.split("/")[2]
        if not os.path.exists(os.path.join(d, "_result.txt")): continue
        lift = {}
        lp = os.path.join(d, "_lift.txt")
        if os.path.exists(lp):
            for l in open(lp):
                m = re.match(r"episode(\d+)\t.*目标位移=([-\d.]+|-)\t最大干扰物位移=([-\d.]+|-)", l)
                if m and m.group(2) != "-": lift[int(m.group(1))] = (float(m.group(2)), float(m.group(3)) if m.group(3) != "-" else 0.0)
        for l in open(t):
            e = json.loads(l); e["scene"] = scene; e["lift"] = lift.get(e["episode"]); rows.append(e)
    n = len(rows); scenes = len({r["scene"] for r in rows})
    term = collections.Counter(r.get("termination") for r in rows)
    succ = collections.Counter(r.get("termination") for r in rows if r.get("success"))
    out += [f"## {TITLE.get(pol, pol)} · `{run}` · {scenes} 场景 / {n} episode", "", "| 终止方式 | episode 数 | 占比 | 其中判据成功 | 成功占该类 |", "|---|---|---|---|---|"]
    for k, v in term.most_common():
        out.append(f"| {k} | {v} | {v/n:.1%} | {succ.get(k,0)} | {succ.get(k,0)/v:.1%} |")
    mf = [r for r in rows if r.get("termination") == "model_finish"]
    mf_ok = sum(1 for r in mf if r.get("success"))
    total_ok = sum(1 for r in rows if r.get("success"))
    out += ["", f"- 总成功率 {total_ok}/{n} = {total_ok/n:.3f}。判据每步检查、满足即终止，所以成功的 episode 全部记为 env_success；",
            f"  model_finish 恒为失败——它表示模型在判据尚未满足时就宣告完成（误报完成）。误报完成率 = {len(mf)}/{n} = {len(mf)/n:.1%}；",
            f"  从未宣告完成、直到墙钟/步数耗尽 = {n-len(mf)-total_ok} 条（{(n-len(mf)-total_ok)/n:.1%}）。"]
    # model_finish 且失败 的位移分类
    cat = collections.Counter(); ex = collections.defaultdict(list)
    for r in mf:
        if r.get("success"): continue
        lf = r["lift"]
        if lf is None: c = "F 无位移记录(按压/开合类)"
        elif lf[0] < 0.03: c = "A 目标几乎没动(空报完成)"
        elif lf[0] > 1.0: c = "B 目标掉出桌面"
        elif lf[1] > lf[0]: c = "C 干扰物位移>目标(先动/多动干扰物)"
        elif lf[1] > 0.05: c = "D 目标动了且干扰物被碰>5cm"
        else: c = "E 目标动了、干扰物没动、终态不达标"
        cat[c] += 1; ex[c].append(f"{r['scene']}#{r['episode']}")
    if cat:
        out += ["", "model_finish 且判据失败 的 episode 按位移记录分类：", "", "| 类别 | 数量 | 占比 | 例 |", "|---|---|---|---|"]
        tot = sum(cat.values())
        for c in sorted(cat): out.append(f"| {c} | {cat[c]} | {cat[c]/tot:.0%} | {', '.join(ex[c][:3])} |")
    out.append("")
open("suite/AGENT_TERMINATION_STATS.md", "w", encoding="utf-8").write("\n".join(out) + "\n"); print("写出 suite/AGENT_TERMINATION_STATS.md")
