> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# LLM agent 评测的终止协议与"模型自判完成"分析

> 供论文写作使用。数据来源：`eval_result/formal_{gpt6,claude51,gemini38flash}_*/*/_agent_timing.jsonl`（逐 episode 终止方式）、`_lift.txt`（目标/干扰物最大位移）、本地桥接账本 `decisions.jsonl`（模型每次调用的工具参数与 finish 备注）。统计表由 `suite/termination_report.py` 生成为 `suite/AGENT_TERMINATION_STATS.md`，跑完后重新生成即为终版。

## 1. 三类被测策略的终止方式

| 策略类型 | 谁决定结束 | 结束条件 |
|---|---|---|
| VLA / 世界模型策略（DM0.5、Pi0.5、X-WAM、OpenWAM 等） | 只有环境 | 判据满足 → 成功结束；否则跑满步数上限（1000 步）→ 失败 |
| LLM agent（GPT-6 Astra、Claude Fable 5.1、Gemini 3.8 Flash） | 环境 **或** 模型 | ① 判据满足 → `env_success`；② 模型调用 `finish` → `model_finish`；③ 单 episode 墙钟 3300 s → `wall_budget`；④ 120 次调用上限 / 步数上限 |

VLA 策略没有"自己说完成"的通道，因此它们的失败只有一种形态（跑满步数）。LLM agent 多了 `finish` 工具，于是出现"模型认为完成了、判据不认"的情况。

## 2. LLM agent 的接口是三家完全相同的

三家模型共用同一套系统提示、同一组工具、同一条推理管线（本地桥接 `local_bridge.py` + 内核插件 `policy/GPT6/deploy_policy.py`），差别仅在 provider 的请求格式（Responses / Messages / generateContent）与各自的推理强度参数（均为 high）。

- **工具**只有两个：`move_eef`（一个绝对末端目标 + 夹爪开度 + phase，仿真器负责运动规划）和 `finish(note)`。
- `finish` 的工具描述："End the attempt; the simulator independently scores success."
- 系统提示最后一句："Return exactly one move_eef or finish tool call. **Finish when completed or when you cannot proceed. Your claim does not determine the environment's score.**"
- 模型得到的观测：三路相机 RGB（head / left wrist / right wrist）、末端位姿与夹爪实测开度、关节角、上一步的执行反馈（接触停止、跟踪误差、动作被拒的原因）。**模型得不到**：物体位姿、成功判据、专家轨迹。
- 上下文：同一 episode 内保留完整文本历史（含模型自己的推理/工具调用），只保留最近一帧观测的图片；episode 之间上下文清空。

`finish` 的处理：模型一旦调用 `finish`，插件立刻把步数计数置为上限、结束该 episode，随后由环境按判据打分；`note` 只记录、不参与评分。判据是**每一步**都检查的，满足即终止，因此：

> **成功的 episode 全部以 `env_success` 结束；`model_finish` 在定义上恒为失败**——它表示"判据尚未满足时模型宣告完成"，即模型的**误报完成**。

所以论文里比较的不是"模型自判的准确率"，而是三个比例：
- **env_success 率** = 成功率；
- **误报完成率**（model_finish / 全部 episode）：模型在任务未完成时就停手；
- **未宣告率**（墙钟/步数耗尽）：模型既没完成也没放弃，一直在尝试。

## 3. 为什么模型的判断和判据不一样：判据在看什么

组合泛化场景的判据（`envs/_compo_scene.py::check_success`）由三层与门组成，模型对这三层一无所知，只能从图像推断：

1. **选对了没有**（`_selected_right`）：目标必须动了；**第一个动的物体必须是目标**；目标位移必须大于任何干扰物的位移。设计意图是"指代/属性场景考的是第一次就选对，试错不给分"。
2. **参照物没被搬动**（`_refs_stayed_put`）：容器/参照物位移 ≤ 阈值。防止"把锅端到茶叶盒旁边"这类作弊。
3. **终态达标**（`_goal_ok`）：按目标类型检查——`in`（在容器内半径 r 内）、`on`（xy 公差 3.5 cm、z 在合理薄层、**夹爪已张开**）、`between`（在两参照物连线附近、横向公差 10 cm）、`rel`（在参照物某一侧的距离带内）、`lift`（被夹住状态下离地 ≥ dz）、`press` 等。

模型看到的是"东西好像放进去了"，判据看的是上面三条。两者分歧的典型情形（均来自真实 episode，末帧已抽查）：

| 例子 | 模型 finish 时的说法 | 判据的裁决 | 归因 |
|---|---|---|---|
| `attr_category_can_plasticbox` #0、#2（Claude） | "Can grasped…released inside the plastic box; head camera confirms the can lies within the box interior." | 末帧确认罐子**确实在盒内**，但可乐瓶横在罐子前面，模型先把瓶子推开（干扰物位移 0.38 m > 目标 0.30 m，且干扰物先动）→ 第 1 层不通过 | **判据严格处**：把"清障"算作"选错"。三家模型都会撞上（C 类占比 6–8%），不影响排名 |
| `attr_category_can_plasticbox` #1（Claude） | "carried over the plastic box, lowered inside, and released" | 放置时把塑料盒推走（参照物位移超阈值）→ 第 2 层不通过 | 判据合理（容器被推走） |
| `attr_category_can_plasticbox` #4（Claude） | "it is now standing inside the box. Arm retreated clear." | 目标位移 **2 mm**——罐子根本没动过 | **模型幻觉**：抓取失败后从图像里"看出"成功 |
| `attr_color_beat_block` #0–#2（Claude）、#1/#3/#4（GPT-6） | 宣告完成 | 目标几乎没动 | 同上，空报完成 |
| `place_between_bowls` #2（Claude） | 宣告放到两碗之间 | 方块放在两碗连线**前方**十几厘米，不在连线附近 | 模型侧空间理解/放置精度 |
| `grab_dumbbell` #4（Claude） | 宣告已抓起 | 哑铃被拖了 29 cm，但被夹住时离地最大 0.1 mm → `lift` 不通过 | 模型侧：拖动而非抬起 |
| `place_teabox_scale` #2（GPT-6）等 B 类 | 宣告完成 | 目标位移 > 1 m：物体被撞飞/掉出桌面 | 模型侧 |

## 4. 误报完成的分布（跑完后以 `suite/AGENT_TERMINATION_STATS.md` 为准）

按位移记录把 `model_finish` 且失败的 episode 分成六类（`termination_report.py` 自动分类）：

- A 目标几乎没动（空报完成）；B 目标掉出桌面；C 干扰物位移 > 目标（清障/选错）；D 目标动了但干扰物也被碰过；E 目标动了、干扰物没动、终态不达标（放置精度/容器/夹爪）；F 无位移记录（按压、开合类，需看视频）。

截至 2026-09-16（GPT-6、Gemini 终版 48/48；Claude 于 29/48 中止、不计入正式结果，其数字仅供参考）：

| | GPT-6 Astra | Claude Fable 5.1 | Gemini 3.8 Flash |
|---|---|---|---|
| 成功率（env_success） | **0.771** (185/240) | 0.628 (91/145) | 0.275 (55/200) |
| 误报完成率（model_finish） | 19.2% | 35.2% | 53.0% |
| 未宣告（墙钟/步数耗尽） | 3.8% | 2.1% | 19.5% |
| 误报中 A 类"空报" | 11% | 24% | 33% |
| 误报中 C 类"清障算选错" | 7% | 6% | 8% |
| 误报中 E 类"终态差一点" | 35% | 41% | 33% |
| 平均调用次数 / episode | 24 | ~20 | ~34 |

解读：
- 三家的排名差异主要来自**误报完成率**（GPT-6 19% / Claude 35% / Gemini 53%）：GPT-6 更倾向于多做几步核实再 finish，Claude 与 Gemini 更常在图像"看起来完成"时停手。
- C 类（判据把清障算选错）三家占比相近，属于判据的统一严格性，不改变相对结论；如需宽松口径，可从位移记录事后计算"忽略首动规则"的成功率，无需重跑。
- Gemini 还有 19.5% 的 episode 从未宣告完成、直到 55 min 墙钟耗尽，对应其单次调用慢（约 47 s/次）且动作幅度保守。

## 5. 协议说明（可直接写进论文的要点）

1. LLM agent 通过统一的工具接口控制机器人，每步一次绝对末端目标；仿真器负责规划与执行，并把接触/跟踪反馈返回给模型。
2. 模型可在任意时刻调用 `finish` 结束尝试；成功与否**只由环境判据决定**，模型的声明不参与评分；判据每步检查、满足即终止。
3. 因而 `model_finish` 恒为失败，其比例度量了模型"误报完成"的倾向；`wall_budget/step_limit` 度量了"既不成功也不放弃"的倾向。
4. 判据包含"首动必须是目标、参照物不得移动、终态公差"三层；模型不知道判据，只能从图像自证。这使得少数"清障后完成"的 episode 被判失败（C 类），该效应对所有被测模型一致。
5. 同一场景、同一冻结种子、同一提示词与工具，三家模型仅在推理接口和推理强度参数（均取 high）上不同。
