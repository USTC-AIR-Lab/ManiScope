"""汇总各 run 的 _latency.txt（内核逐条记录：模型调用次数/模型侧耗时/eval 墙钟/步数/episode 墙钟）-> suite/LATENCY.md
口径：模型侧耗时 = 推理服务返回的 infer_time（含前后处理，不含网络）；eval_wall = 每次 eval() 含执行；
均为在线评测条件下测得（每卡 2 条车道共享），不是隔离基准，横向比较看量级。"""
import glob, os, sys, csv
runs = sys.argv[1:]
TITLE = {"dm05":"DM0.5","wla_wrong":"WLA(内部误用)","pi05":"Pi0.5","xvla":"X-VLA","pi0":"pi0","wla_formal":"WLA","starvla":"StarVLA","fastwam":"FastWAM","ahawam":"AHA-WAM","g05":"GalaxeaVLA(G0.5)","openwam":"OpenWAM-α","motus":"Motus","lingbot_va":"LingBot-VA","gpt6":"GPT-6 Astra(high)","gemini31pro":"Gemini 3.1 Pro(high)","claude51":"Claude Fable 5.1(high)","gemini38flash":"Gemini 3.8 Flash(high)","xwam":"X-WAM"}
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
o = ["# 各策略推理延迟与耗时汇总（内核 `_latency.txt`，逐 episode）", "",
     "> 模型侧耗时 = 推理服务自报的单次 infer 时间（含图像编解码/前后处理）；eval 墙钟 = 一次 eval() 含动作执行与渲染；",
     "> 首条 episode 含预热/编译。所有数字为正式评测在线条件（每卡 2 条车道共享 GPU/CPU）下测得，非隔离基准。", "",
     "| 策略 | episodes | 平均调用/条 | 模型侧 单次 (s) | 模型侧 单次 p50/p95 (s) | 模型侧 /条 (s) | eval 墙钟 /条 (s) | 平均步数 | episode 墙钟 /条 (s) | 模型侧占比 |",
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
    # 逐场景明细
    by = {}
    for r in rows: by.setdefault(r["scene"], []).append(r)
    with open(f"eval_result/{run}/latency_scenes.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["policy", "scene", "n", "calls_mean", "model_per_call_s", "model_per_episode_s", "eval_wall_per_episode_s", "steps_mean", "episode_wall_s"])
        for s in sorted(by):
            rs = by[s]; k = len(rs); c = sum(r["calls"] for r in rs); m = sum(r["model_total"] for r in rs)
            w.writerow([pol, s, k, round(c / k, 2), round(m / max(1, c), 4), round(m / k, 2), round(sum(r["eval_wall_total"] for r in rs) / k, 2), round(sum(r["steps"] for r in rs) / k, 1), round(sum(r["episode_wall"] for r in rs) / k, 2)])
# ---- 同一 240 条 episode（每场景前 5 个冻结种子 = episode0..4）上的公平对比 ----
o += ["", "## 同一 240 条 episode（每场景前 5 个冻结种子）上的对比", "",
      "> 各策略只取 episode0–4（与 LLM agent 评测用的同一批种子/指令），耗时与成功率在完全相同的实例上比较。", "",
      "| 策略 | episodes | 成功率(240) | 平均调用/条 | 模型侧 单次 (s) | 模型侧 单次 p50/p95 (s) | 模型侧 /条 (s) | eval 墙钟 /条 (s) | 平均步数 | episode 墙钟 /条 (s) |",
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
o += ["", "逐场景明细：各 run 目录下 `latency_scenes.csv`。GPT-6 的 API 次数/响应/执行/token 详见 `AGENT_TIMING_gpt6.md`。", ""]
open("suite/LATENCY.md", "w", encoding="utf-8").write("\n".join(o)); print("写出 suite/LATENCY.md")
