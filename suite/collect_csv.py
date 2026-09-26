# -*- coding: utf-8 -*-
"""Collect episode and scene CSVs from a run. Episode records include native success and available displacement, clearance and contact diagnostics; scene summaries report counts, Wilson intervals and observed failure categories. Missing telemetry remains missing. Do not infer latent causes from final scores."""
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
    """Parse episodeN tab-separated key=value telemetry such as _lift.txt and _contact.txt."""
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
    """Extract (steps, step_limit, outcome) tuples from scene logs."""
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
            eps.append((cur_max, cur_lim, "success" if o.group(1) == "Success!" else "failure"))
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
        continue
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
    lat = parse_kv_lines(os.path.join(base, "_latency.txt"), None)   # Use recorded latency-step counts when available rather than log inference.
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

        if T.get("steps"):
            st = int(T["steps"])
        ok = (L.get("_outcome") == "success")
        st, lim, log_out = (steps[ep] if ep < len(steps) else (None, None, None))
        if ok:
            nsucc += 1
            if st: s_steps.append(st)
        else:
            if st: f_steps.append(st)
            # Report observed failure categories, summaries, matched episodes and scene-level details without inferring unrecorded causes.
            try:
                dd = float(L.get("max_distractor_displacement", "nan"))
                ch = L.get("max_gripped_clearance", "")
                thr = float(L.get("threshold", "nan"))
                cd = C.get("min_distance", "")
                if dd == dd and dd > 0.05:
                    f_touch += 1
                elif cd and cd != "never_contacted" and float(cd) > float(C.get("threshold", 0)):
                    f_nocontact += 1
                elif cd == "never_contacted":
                    f_nocontact += 1
                elif ch and ch != "never_gripped" and thr == thr and float(ch) < thr:
                    f_nolift += 1
                else:
                    f_other += 1
            except Exception:
                f_other += 1

        ep_rows.append(dict(
            policy=POLICY, scene=scene, dim=dim, tier=tier, episode=ep, seed=seed,
            instruction=ins, success=int(ok), steps=st or "", step_lim=lim or "",
            target_disp=L.get("target_displacement", ""), distractor_disp=L.get("max_distractor_displacement", ""),
            clearance=L.get("max_clearance", ""), clearance_held=L.get("max_gripped_clearance", ""),
            clearance_thr=L.get("threshold", ""),
            contact_dist=C.get("min_distance", ""), contact_thr=C.get("threshold", ""),
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
    print("%s: %d rows -> %s" % (name, len(rows), p))
