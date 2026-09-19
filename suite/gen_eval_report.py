# -*- coding: utf-8 -*-
"""生成评测结果文档：分维度/难度汇总 + 梯度自检 + 全场景明细。"""
import glob, re, os, math, sys, yaml
from collections import defaultdict

RUN = sys.argv[sys.argv.index("--run")+1] if "--run" in sys.argv else "dm05_v3_clean"
# 策略名从 run 目录名推断（formal_<policy>_<date>），报告标题和输出文件名都按它走，免得互相覆盖
_POL = RUN[len("formal_"):RUN.rfind("_")] if RUN.startswith("formal_") and RUN.count("_") >= 2 else "dm05"
_POL_TITLE = {"dm05": "DM0.5", "wla": "WLA", "wla_wrong": "WLA(内部误用)", "wla_formal": "WLA", "pi05": "Pi0.5", "xvla": "X-VLA", "pi0": "pi0", "starvla": "StarVLA"}.get(_POL, _POL)
_OUT = "EVAL_RESULTS.md" if _POL == "dm05" else "EVAL_RESULTS_%s.md" % _POL
HERE = os.path.dirname(os.path.abspath(__file__))
# 开源权重/代码来源，写进报告开头（policies.yaml 的 hf_repo / code_repo）
try:
    import yaml as _yaml
    _PE = _yaml.safe_load(open(os.path.join(HERE, "policies.yaml"), encoding="utf-8"))["policies"].get(_POL, {})
except Exception:
    _PE = {}
_SRC_LINES = []
if _PE.get("hf_repo"):
    _SRC_LINES.append("> - **开源权重**：%s" % _PE["hf_repo"])
if _PE.get("code_repo"):
    _SRC_LINES.append("> - **推理代码**：%s" % _PE["code_repo"])
if _PE.get("desc"):
    _SRC_LINES.append("> - **模型说明**：%s" % str(_PE["desc"]).strip())
ROOT = os.path.dirname(HERE)
AX = {"skill_x_object": "D1 技能×物体", "skill_x_spatial": "D2 技能×空间",
      "attribute_binding": "D3 属性绑定", "instruction_structure": "D4 指代结构",
      "skill_x_skill_temporal": "D5 技能×技能(时序)", "mixture": "D7 混合"}

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

# 每场景 episode 数：正式评测是 100（冻结种子文件里有多少就是多少），
# 早期探索轮是 20。写死会让置信区间算错，所以从种子文件推断。
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
    "> **正式评测口径**（写论文/对外引用时请照此说明）", ">",
    "> - 48 个场景 × %d 条 episode；代码冻结于 git tag `formal-eval-v1` @ `39808b6`" % EP,
    "> - **种子冻结**：每场景 100 个专家可解种子存于 `suite/seeds/<场景>.json`（含每个种子的初始位姿摘要），",
    ">   评测时直接读文件而非现场搜索 —— 不同算法面对的是**逐条对应的同一批初始状态**；",
    ">   指令也由种子唯一确定，同种子同指令。",
    "> - **排除 3 个场景**（正式清单 51→48）：`place_a2b_behind_novel`、`attr_color_bottle_basket`、",
    ">   `ref_cube_on_plate_to_pad`，原因是**脚本专家产出率 < 30%**（实测 12%~15%），",
    ">   种子集会被筛成极窄子集、成绩没有代表性。**不是因为分数低而排除**，详见 `scenes_v2.yaml`。",
    "> - **step_lim 并非全场景统一**：41 个场景为 1000，7 个为 600（沿用各自历史值）。",
    ">   同一场景对所有算法一致，跨算法可比；但按场景引用时需标注。",
    "> - **各算法的预处理不同，属方法本身而非评测偏差**：仿真侧观测完全一致",
    ">   （head+left+right 三路相机、320×240、无深度、无特权状态），",
    ">   但 WLA 缩放到 224 并 JPEG 编码，DM0.5 用原分辨率 PNG。",
    "> - 逐条数据见同目录 `episodes.csv`（含步数、位移、净空、接触距离等），",
    ">   逐场景汇总见 `scenes.csv`（含 Wilson 置信区间与失败归类）。", "",
]

o = ["# %s 组合泛化评测结果" % _POL_TITLE, ""] + (_SRC_LINES + [">"] if _SRC_LINES else []) + HEAD_NOTE + ["",
     "`eval_result/%s/` · 每场景 %d 条 episode · 成功和失败视频全部保存（仅 head 相机）" % (RUN, EP), "",
     "**完成 %d/%d 个场景，共 %d 条 episode。**" % (len(rows), len(meta), len(rows) * EP), ""]

o += ["## 难度梯度自检", "",
      "套件的自检项：同一策略在 L1→L3 上若不单调下降，说明分级无效。", "",
      "| 难度 | 成功率 | 场景数 |", "|---|---|---|"]
ks = sorted(bt)
for k in ks:
    o.append("| L%d | **%.3f** | %d |" % (k, sum(bt[k]) / len(bt[k]), len(bt[k])))
means = [sum(bt[k]) / len(bt[k]) for k in ks]
viol = [(ks[i], ks[i + 1]) for i in range(len(ks) - 1) if means[i] < means[i + 1]]
o += ["", "**结论：%s**" % ("严格单调递减，分级有效 ✓" if not viol else "违例 %s ✗" % viol), ""]

o += ["## 分维度", "",
      "置信区间按每场景 %d 条 episode 的正态近似算。" % EP, "",
      "| 维度 | 成功率 | 95% CI | 场景数 | episode 数 |", "|---|---|---|---|---|"]
for k in sorted(bd, key=lambda x: -sum(bd[x]) / len(bd[x])):
    v = bd[k]; m = sum(v) / len(v)
    ci = 1.96 * math.sqrt(max(m * (1 - m), 1e-9) / (EP * len(v)))
    o.append("| %s | **%.2f** | ±%.2f | %d | %d |" % (k, m, ci, len(v), EP * len(v)))
o.append("")

o += ["## 全场景明细", "",
      "`专家` 是专家演示产出率（场景是否可解），`DM0.5` 是策略成功率。", "",
      "| 维度 | 难度 | 场景 | 生活场景 | 专家 | **DM0.5** |", "|---|---|---|---|---|---|"]
for dim, tier, t, v, ctx, sm in rows:
    o.append("| %s | L%s | `%s` | %s | %s | **%.2f** |" % (dim, tier, t, ctx, sm, v))

missing = sorted(n for n in meta if n not in res)
if missing:
    o += ["", "## 未完成（%d 个）" % len(missing), "",
          "8 小时预算到点时仍在队列中或未跑满 20 条。", ""]
    mb = defaultdict(list)
    for n in missing:
        mb[meta[n][0]].append(n)
    for k in sorted(mb):
        o.append("- **%s**：%s" % (k, "、".join("`%s`" % x for x in sorted(mb[k]))))

zero = [(dim, t, sm) for dim, tier, t, v, ctx, sm in rows if v == 0.0]
if zero:
    o += ["", "## 需要复查的零分场景", "",
          "专家烟测都通过（场景可解），但策略 0/20。需要看视频确认是模型失败还是判据过严。", "",
          "| 维度 | 场景 | 专家产出率 |", "|---|---|---|"]
    for dim, t, sm in zero:
        o.append("| %s | `%s` | %s |" % (dim, t, sm))

open(os.path.join(HERE, _OUT), "w", encoding="utf-8").write("\n".join(o) + "\n")
print("写出 %d 个场景结果 -> %s" % (len(rows), _OUT))
