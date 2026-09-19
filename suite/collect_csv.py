# -*- coding: utf-8 -*-
"""把一次评测的所有产物汇总成统一 CSV，供论文画图用。

用法:
    python3 suite/collect_csv.py <run_dir_name> [policy]
    例: python3 suite/collect_csv.py formal_dm05_20260911 dm05

产出两个文件（写在 run 目录下）:
    episodes.csv  逐条 episode：policy, scene, dim, tier, episode, seed, instruction,
                  success, steps, step_lim, target_disp, distractor_disp,
                  clearance, clearance_held, clearance_thr, contact_dist, contact_thr
    scenes.csv    逐场景汇总：policy, scene, dim, tier, n, success_rate,
                  wilson_lo, wilson_hi, mean_steps, mean_steps_success, mean_steps_fail,
                  fail_touched_distractor, fail_not_lifted, fail_no_contact, fail_other

数据来源（全部是已有产物，不需要重跑）:
    _result.txt        场景成功率
    _instructions.txt  每条的 seed 与实际指令
    _lift.txt          每条的成败、目标/干扰物位移、离地净空
    _contact.txt       接触类每条的最近接触距离
    suite/logs/*/<policy>_<scene>.log  每条的步数（日志里每步都打了 step: N / LIM）

注意：步数是从日志反解出来的。日志按 \\r 刷新同一行，每条 episode 以 Success!/Fail! 收尾，
按这个边界切分、取每段里最大的 step 值即可。日志可能包含同一场景的多轮运行，
所以只取**最后 n 条**与本次 episode 数对齐。
"""
import os, re, sys, csv, glob, math, json

RUN = sys.argv[1] if len(sys.argv) > 1 else "formal_dm05_20260911"
POLICY = sys.argv[2] if len(sys.argv) > 2 else ("wla" if "wla" in RUN else "dm05")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
RUNDIR = os.path.join("eval_result", RUN)

ANSI = re.compile(r"\x1b\[[0-9;]*m")
STEP = re.compile(r"step:\s*(\d+)\s*/\s*(\d+)")
OUTCOME = re.compile(r"(Success!|Fail!)")


def scene_meta():
    import yaml
    d = yaml.safe_load(open("suite/scenes_v2.yaml", encoding="utf-8"))
    AX = {"skill_x_object": "D1", "skill_x_spatial": "D2", "attribute_binding": "D3",
          "instruction_structure": "D4", "skill_x_skill_temporal": "D5", "mixture": "D7"}
    m = {}
    for k, v in d["axes"].items():
        for s in (v["scenes"] or []):
            m[s["name"]] = (AX[k], s.get("tier"))
    return m


def parse_kv_lines(path, keys):
    """解析 _lift.txt / _contact.txt 这类 'episodeN\\t字段=值\\t...' 的行。"""
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if not parts or not parts[0].startswith("episode"):
            continue
        try:
            ep = int(parts[0][len("episode"):])
        except ValueError:
            continue
        rec = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                rec[k.strip()] = v.strip()
            else:
                rec["_outcome"] = p.strip()
        out[ep] = rec
    return out


def steps_from_log(scene, n_expect):
    """从场景日志反解每条 episode 的步数。返回 [(steps, step_lim, outcome), ...]。"""
    cands = glob.glob(os.path.join("suite", "logs", "*", "%s_%s.log" % (POLICY, scene)))
    if not cands:
        return []
    path = max(cands, key=os.path.getmtime)
    try:
        raw = open(path, "rb").read().decode("utf-8", "ignore")
    except Exception:
        return []
    raw = ANSI.sub("", raw).replace("\r", "\n")
    eps, cur_max, cur_lim = [], 0, 0
    for line in raw.split("\n"):
        m = STEP.search(line)
        if m:
            v, lim = int(m.group(1)), int(m.group(2))
            cur_max = max(cur_max, v); cur_lim = lim
            continue
        o = OUTCOME.search(line)
        if o:
            eps.append((cur_max, cur_lim, "成功" if o.group(1) == "Success!" else "失败"))
            cur_max = 0
    return eps[-n_expect:] if n_expect and len(eps) >= n_expect else eps


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - half) / d, (c + half) / d)


meta = scene_meta()
ep_rows, sc_rows = [], []

for scene in sorted(os.listdir(RUNDIR)) if os.path.isdir(RUNDIR) else []:
    sdir = os.path.join(RUNDIR, scene)
    if not os.path.isdir(sdir):
        continue
    res = glob.glob(os.path.join(sdir, "*/*/*/*/_result.txt"))
    if not res:
        continue                      # 还没跑完的场景跳过
    base = os.path.dirname(res[0])
    rate = None
    for tok in re.findall(r"^[01]?\.?\d+$", open(res[0]).read(), re.M):
        try:
            rate = float(tok)
        except ValueError:
            pass

    instr = {}
    ip = os.path.join(base, "_instructions.txt")
    if os.path.exists(ip):
        for line in open(ip, encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3 and parts[0].startswith("episode"):
                instr[int(parts[0][7:])] = (parts[1].replace("seed=", ""), parts[2])

    lift = parse_kv_lines(os.path.join(base, "_lift.txt"), None)
    cont = parse_kv_lines(os.path.join(base, "_contact.txt"), None)
    lat = parse_kv_lines(os.path.join(base, "_latency.txt"), None)   # formal-eval-v2 起才有
    n_ep = max([len(instr), len(lift)] or [0])
    steps = steps_from_log(scene, n_ep)

    dim, tier = meta.get(scene, ("?", "?"))
    nsucc = 0
    s_steps, f_steps = [], []
    f_touch = f_nolift = f_nocontact = f_other = 0

    for ep in range(n_ep):
        seed, ins = instr.get(ep, ("", ""))
        L = lift.get(ep, {})
        C = cont.get(ep, {})
        T = lat.get(ep, {})
        # 有 _latency.txt 时步数直接取记录值，比解析日志可靠
        if T.get("steps"):
            st = int(T["steps"])
        ok = (L.get("_outcome") == "成功")
        st, lim, log_out = (steps[ep] if ep < len(steps) else (None, None, None))
        if ok:
            nsucc += 1
            if st: s_steps.append(st)
        else:
            if st: f_steps.append(st)
            # 失败归类（只用已记录的量，不臆测）
            try:
                dd = float(L.get("最大干扰物位移", "nan"))
                ch = L.get("被夹着时最大净空", "")
                thr = float(L.get("阈值", "nan"))
                cd = C.get("最近距离", "")
                if dd == dd and dd > 0.05:
                    f_touch += 1
                elif cd and cd != "从未接触" and float(cd) > float(C.get("阈值", 0)):
                    f_nocontact += 1
                elif cd == "从未接触":
                    f_nocontact += 1
                elif ch and ch != "从未夹住" and thr == thr and float(ch) < thr:
                    f_nolift += 1
                else:
                    f_other += 1
            except Exception:
                f_other += 1

        ep_rows.append(dict(
            policy=POLICY, scene=scene, dim=dim, tier=tier, episode=ep, seed=seed,
            instruction=ins, success=int(ok), steps=st or "", step_lim=lim or "",
            target_disp=L.get("目标位移", ""), distractor_disp=L.get("最大干扰物位移", ""),
            clearance=L.get("最大净空", ""), clearance_held=L.get("被夹着时最大净空", ""),
            clearance_thr=L.get("阈值", ""),
            contact_dist=C.get("最近距离", ""), contact_thr=C.get("阈值", ""),
            model_calls=T.get("calls", ""), eval_wall_mean=T.get("eval_wall_mean", ""),
            eval_wall_p95=T.get("eval_wall_p95", ""), model_time_mean=T.get("model_mean", ""),
            episode_wall=T.get("episode_wall", "")))

    lo, hi = wilson(nsucc, n_ep)
    sc_rows.append(dict(
        policy=POLICY, scene=scene, dim=dim, tier=tier, n=n_ep,
        success_rate=round(nsucc / n_ep, 4) if n_ep else "",
        result_file_rate=rate,
        wilson_lo=round(lo, 4), wilson_hi=round(hi, 4),
        mean_steps=round(sum(s_steps + f_steps) / max(1, len(s_steps + f_steps)), 1),
        mean_steps_success=round(sum(s_steps) / len(s_steps), 1) if s_steps else "",
        mean_steps_fail=round(sum(f_steps) / len(f_steps), 1) if f_steps else "",
        fail_touched_distractor=f_touch, fail_not_lifted=f_nolift,
        fail_no_contact=f_nocontact, fail_other=f_other))

for name, rows in (("episodes.csv", ep_rows), ("scenes.csv", sc_rows)):
    if not rows:
        continue
    p = os.path.join(RUNDIR, name)
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("%s: %d 行 -> %s" % (name, len(rows), p))
