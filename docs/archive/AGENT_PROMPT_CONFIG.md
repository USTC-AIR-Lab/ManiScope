> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# LLM agent 评测：提示词、接口配置与终止方式比例

> 供论文方法/附录使用。代码：本地桥接 `gpt6-eval/campaign_formal/local_bridge.py`、`motion_limits.py`，内核插件 `policy/GPT6/deploy_policy.py`。三家模型（GPT-6 Astra、Gemini 3.8 Flash、Claude Fable 5.1）共用同一套提示词、工具与执行管线，只有 provider 的请求格式和推理强度参数名不同。

## 1. 终止方式比例

口径：每场景前 5 个冻结种子 × 48 场景 = 240 episode；只统计已落盘 `_result.txt` 的场景。判据每步检查、满足即终止，因此**成功 episode 全部记为 `env_success`，`model_finish` 恒为失败**（= 判据未满足时模型宣告完成，即误报完成）。

| 终止方式 | GPT-6 Astra (high) · 240 ep | Gemini 3.8 Flash (high) · 240 ep | Claude Fable 5.1 (high) · 145 ep（29/48 场景，**已中止，不计入正式结果**） |
|---|---|---|---|
| `env_success` 判据判定成功 | **185 (77.1%)** | **58 (24.2%)** | **91 (62.8%)** |
| `model_finish` 模型自己宣告结束（误报完成） | 46 (19.2%) | 120 (50.0%) | 51 (35.2%) |
| `wall_budget_3300s` 单 episode 墙钟 55 min 耗尽 | 6 (2.5%) | 62 (25.8%) | 3 (2.1%) |
| `step_limit` 仿真 1000 步耗尽 | 3 (1.2%) | 0 | 0 |
| 120 次调用上限 | 0 | 0 | 0 |

- 成功率 = env_success 比例：GPT-6 0.771 / Gemini 0.242。Claude Fable 5.1 因 API 额度限制于 2026-09-15 在 29/48 场景处中止，未完成正式评测，其列仅供参考、不进入对比表（同 29 场景上 Claude 0.628 vs GPT-6 0.834）。
- 三家排名差异主要来自误报完成率（19% / 50% / 35%）和 Gemini 特有的 26% 墙钟耗尽（单次调用 46.6 s、动作保守）。
- 误报完成的进一步分类（按目标/干扰物位移）见 `AGENT_TERMINATION_STATS.md`：GPT-6 的误报中"目标几乎没动就宣告完成"占 11%，Claude 24%，Gemini 33%。

## 2. 系统提示（三家逐字相同）

```
Control a simulated ALOHA dual-arm robot from RGB cameras and measured
robot state. Perform the user's instruction. You have no object poses or expert
trajectory. Choose absolute end-effector targets; the simulator performs motion
planning and joint control. All positions are meters in the world frame. x<0 is
left, x>0 is right, positive y is away from the robot, z is up. Quaternion order
is [w,x,y,z]. RoboTwin's reported EEF control point is 0.12 m behind the gripper
center along its local +x axis: TCP = EEF_position + R(quaternion)*[0.12,0,0].
Gripper 0 is closed and 1 is open. In eef_state, *_gripper is the commanded
aperture retained for motion; *_gripper_actual is measured from physical joints.
Physical aperture can lag the command while the motor moves; inspect feedback
and images. Its normalization uses the existing drive calibration, not millimeters.
A close command of 0 does not prove an empty grasp; inspect actual aperture and images.
joint_state contains physical joint positions. Use the provided measured poses
as references, preserve orientation unless a change is necessary. Use phases explicitly: transit for clear free space, approach when near objects,
contact for intentional pressing/insertion, and gripper for opening/closing at a fixed pose.
Model-call target envelopes: transit up to 45 cm / 90 degrees,
approach up to 12 cm / 30 degrees, contact up to 3 cm / 10 degrees.
The controller internally interpolates the entire accepted target without additional
model calls. It stops early on unexpected contact or tracking error above 2.5 cm / 10 degrees
relative to an internal segment target (separate from the model-call envelopes). Do not issue
millimeter-by-millimeter calls in free space. Plan purposeful waypoints: align above,
approach, close, lift, transport, place, release. Gripper phase sets the requested aperture in one call at a fixed pose: 0 is closed,
1 is fully open, and intermediate values are allowed for limited clearance.
Other phases preserve aperture. Prefer reorienting above
objects before descending. Use transit only for a clear route, approach near objects,
and contact only for intentional pressing/insertion. After a contact stop, first open
with gripper phase at the measured fixed pose. If stuck, recover phase permits a
translation of at most 3 cm away from contact, keeping measured orientation and
the current gripper command fixed. This is a monitored escape: new contact, excessive/increasing force,
or persistent non-improving force stops it. Do not repeatedly push into the obstacle.
Inspect actual final pose and
contact feedback before the next target. Keep
clear of the table and other objects. Identify the requested object and destination from the images and instruction.
Do not assume motion succeeded: compare the next measured pose and image.
Return exactly one move_eef or finish tool call. Finish when completed or when
you cannot proceed. Your claim does not determine the environment's score.
```

要点：模型得不到物体位姿、成功判据、专家轨迹；只知道坐标系约定、TCP 偏置、夹爪语义、各 phase 的运动包络、以及"finish 不决定得分"。

## 3. 工具定义（三家相同，按各家 schema 方言转写）

```json
move_eef: {
  "arm": "left" | "right",
  "position": [x, y, z],              // 米，世界坐标，绝对目标
  "quaternion_wxyz": [w, x, y, z],
  "phase": "transit" | "approach" | "contact" | "gripper" | "recover",
  "gripper": 0..1,                    // 0 闭合 1 张开；仅 gripper phase 生效，其它 phase 保持当前开度
  "note": string                      // 模型自述意图，仅记录
}
finish: { "note": string }            // "End the attempt; the simulator independently scores success."
```

桥接对每个 `move_eef` 做硬校验（不满足则整步"被拒"、把原因作为反馈返回，模型重新给动作，不消耗仿真步）：
- 平移 ≤ 0.45 m，四元数近似单位，位置绝对值 ≤ 2 m，夹爪 ∈ [0,1]；
- 按 phase 的包络（`motion_limits.py`）：transit ≤ 45 cm / 90°，approach ≤ 12 cm / 30°，contact ≤ 3 cm / 10°，recover ≤ 3 cm 且保持朝向，gripper 不移动；
- 执行侧（仿真内）自动细分插值，遇到意外接触或跟踪误差 > 2.5 cm / 10° 提前停止。

## 4. 每步观测（user 轮内容）

文本 JSON：`instruction`（场景指令，分阶段场景使用完整复合句：`COMBO_STAGED_INSTRUCTION=0`、`STAPLER_STAGED_INSTRUCTION=0`）、`eef_state`（左右臂末端位姿 + 命令/实测夹爪开度）、`joint_state`、`step`、`contact_feedback`、以及上一步执行的 `feedback`：请求位姿 vs 实测位姿、位置残差(m)、朝向残差(°)、请求/命令/实测夹爪、分段执行反馈（是否因接触/跟踪误差提前停止）、`environment_success`（布尔；为真时 episode 已结束，模型实际上不会在它为真时再被调用）。

图片：`head_camera`、`left_camera`、`right_camera` 三路 RGB（PNG，base64）。**上下文中只有当前一步的观测带图**（更早轮次的图片在下一次调用前被剥掉，只留文本）；文本历史（模型自己的推理/工具调用/反馈）在 episode 内完整保留；episode 之间上下文清空。

## 5. 各 provider 的请求配置

| | GPT-6 Astra | Gemini 3.8 Flash | Claude Fable 5.1 |
|---|---|---|---|
| 接口 | OpenAI Responses `/v1/responses` | Google 原生 `/v1beta/models/gemini-3.8-flash:generateContent` | Anthropic `/v1/messages` |
| 推理强度 | `reasoning.effort = "high"` | `generationConfig.thinkingConfig.thinkingLevel = "HIGH"` | `thinking = {type: adaptive}` + `output_config.effort = "high"` |
| 工具调用约束 | `tool_choice = "required"`，`parallel_tool_calls = false` | `toolConfig.functionCallingConfig.mode = "ANY"` | `tool_choice = auto`（开 thinking 时不允许强制），靠提示词要求恰好一个工具调用 |
| 输出上限 | `max_output_tokens = 4096` | `maxOutputTokens = 8192` | `max_tokens = 16000` |
| 推理内容回传 | `include: ["reasoning.encrypted_content"]`，`store=false` | 回传 `thoughtSignature`（失败时降级：去签名 → 无状态转写） | 回传 thinking 块 |
| 提示词缓存 | `prompt_cache_key` = 每 episode 唯一键 | 隐式缓存（实测命中 ~5%） | `cache_control: ephemeral` 4 断点（系统提示、工具、上一稳定轮、当前轮），2026-09-15 16:59 起生效，之前无缓存 |
| 单次请求超时 / 重试 | 600 s，网关 400/5xx/超时重试 3 次；额度用尽立即停 | 同 | 同 |

统一预算：每 episode 最多 120 次模型调用；单 episode 墙钟 3300 s（仿真在模型推理期间暂停，因此 API 时间与执行时间可分开统计）；仿真步数上限 1000。桥接连续 5 次 API 失败则代模型 finish。

## 6. 三家实测的调用/耗时概况（每 episode 均值，已完成场景）

| | GPT-6 Astra | Gemini 3.8 Flash | Claude Fable 5.1（29 场景） |
|---|---|---|---|
| 调用次数 均值 / 中位 / 最大 | 24.8 / 18 / 118 | 33.1 / 29 / 78 | 17.9 / 14 / 67 |
| 单次 API 响应 | 13.1 s | 46.6 s | ~22 s |
| API 总时长 / 执行时长 | 315 s / 344 s | 1630 s / 294 s | ~400 s / ~150 s |
| 输入 token | 0.63 M | 2.96 M（缓存读 0.17 M） | ~0.7 M（无缓存时）；启用缓存后约 1.35 M，其中 0.77 M 缓存读 |
| 输出（含推理）token | 8.9 k | 62 k（推理 58.8 k） | 28 k |

成功 episode 明显更短：Gemini 成功 20.6 次调用 vs 失败 39.5 次；GPT-6、Claude 同趋势。
