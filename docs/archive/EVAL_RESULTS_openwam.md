> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# openwam 组合泛化评测结果

> **未完成**：2026-09-16 15:25 用户决定停止，定格于 38/48 场景；其余 10 个场景（pack_toycar_then_ring、card_right_of_scanner_mix、place_teabox_front_of_skillet、place_teabox_skillet_mix、ref_mug_next_to_bowl、place_between_bowls、roller_to_plate_mix、serve_teabox_then_ring、lift_pot_to_pad、place_teabox_skillet）未评测，不进入正式对比表。

> - **开源权重**：https://huggingface.co/OpenWAM/OpenWAM-Alpha-Sim-RoboTwin-Full
> - **推理代码**：https://github.com/OpenWAM-Official/OpenWAM
> - **模型说明**：OpenWAM-α (OpenWAM-Official)，Wan2.2-TI2V-5B 双系统联合自注意力世界-动作模型，RoboTwin 2.0 全任务微调；eef 口径（状态 20 维 xyz+rot6d+grip×2，动作 20 维 -> 16 维 ee），每步一个动作、服务端分块
>
> **正式评测口径**（写论文/对外引用时请照此说明）
>
> - 48 个场景 × 100 条 episode；代码冻结于 git tag `formal-eval-v1` @ `39808b6`
> - **种子冻结**：每场景 100 个专家可解种子存于 `suite/seeds/<场景>.json`（含每个种子的初始位姿摘要），
>   评测时直接读文件而非现场搜索 —— 不同算法面对的是**逐条对应的同一批初始状态**；
>   指令也由种子唯一确定，同种子同指令。
> - **排除 3 个场景**（正式清单 51→48）：`place_a2b_behind_novel`、`attr_color_bottle_basket`、
>   `ref_cube_on_plate_to_pad`，原因是**脚本专家产出率 < 30%**（实测 12%~15%），
>   种子集会被筛成极窄子集、成绩没有代表性。**不是因为分数低而排除**，详见 `scenes_v2.yaml`。
> - **step_lim 并非全场景统一**：41 个场景为 1000，7 个为 600（沿用各自历史值）。
>   同一场景对所有算法一致，跨算法可比；但按场景引用时需标注。
> - **各算法的预处理不同，属方法本身而非评测偏差**：仿真侧观测完全一致
>   （head+left+right 三路相机、320×240、无深度、无特权状态），
>   但 WLA 缩放到 224 并 JPEG 编码，DM0.5 用原分辨率 PNG。
> - 逐条数据见同目录 `episodes.csv`（含步数、位移、净空、接触距离等），
>   逐场景汇总见 `scenes.csv`（含 Wilson 置信区间与失败归类）。


`eval_result/formal_openwam_20260912/` · 每场景 100 条 episode · 成功和失败视频全部保存（仅 head 相机）

**完成 38/48 个场景，共 3800 条 episode。**

## 难度梯度自检

套件的自检项：同一策略在 L1→L3 上若不单调下降，说明分级无效。

| 难度 | 成功率 | 场景数 |
|---|---|---|
| L1 | **0.547** | 9 |
| L2 | **0.451** | 25 |
| L3 | **0.295** | 4 |

**结论：严格单调递减，分级有效 ✓**

## 分维度

置信区间按每场景 100 条 episode 的正态近似算。

| 维度 | 成功率 | 95% CI | 场景数 | episode 数 |
|---|---|---|---|---|
| D1 技能×物体 | **0.71** | ±0.03 | 9 | 900 |
| D3 属性绑定 | **0.66** | ±0.03 | 9 | 900 |
| D5 技能×技能(时序) | **0.65** | ±0.05 | 3 | 300 |
| D2 技能×空间 | **0.30** | ±0.03 | 7 | 700 |
| D7 混合 | **0.15** | ±0.03 | 4 | 400 |
| D4 指代结构 | **0.07** | ±0.02 | 6 | 600 |

## 全场景明细

`专家` 是专家演示产出率（场景是否可解），`DM0.5` 是策略成功率。

| 维度 | 难度 | 场景 | 生活场景 | 专家 | **DM0.5** |
|---|---|---|---|---|---|
| D1 技能×物体 | L1 | `grab_dumbbell` | 健身角 | 2/4 | **0.60** |
| D1 技能×物体 | L1 | `move_can_coaster` | 床头药盒 | 2/2 | **0.45** |
| D1 技能×物体 | L1 | `move_cup_pad` | 办公桌 | 未跑（v1 沿用） | **0.97** |
| D1 技能×物体 | L1 | `place_teabox_scale` | 超市称重 | 2/2 | **0.76** |
| D1 技能×物体 | L2 | `grasp_mallet_novel` | 工具台 | 2/2 | **0.92** |
| D1 技能×物体 | L2 | `lift_trophy` | 厨房备餐 | 2/2 | **0.42** |
| D1 技能×物体 | L2 | `place_seal_coaster` | 厨房备餐 | 2/2 | **0.80** |
| D1 技能×物体 | L2 | `place_teabox_stand` | 书架 | 2/2 | **0.77** |
| D1 技能×物体 | L2 | `place_toycar_plasticbox` | 玄关 | 2/2 | **0.67** |
| D2 技能×空间 | L1 | `place_a2b_left_novel` | 通用桌面 | 未跑（v1 沿用） | **0.35** |
| D2 技能×空间 | L1 | `place_a2b_right_novel` | 通用桌面 | 未跑（v1 沿用） | **0.40** |
| D2 技能×空间 | L2 | `card_right_of_scanner` | 超市结账 | 2/3 | **0.14** |
| D2 技能×空间 | L2 | `phone_right_of_laptop` | 办公桌 | 2/3 | **0.00** |
| D2 技能×空间 | L2 | `place_can_right_of_plasticbox` | 仓储上架 | 2/4 | **0.42** |
| D2 技能×空间 | L2 | `place_cube_right_of_plate` | 餐桌摆盘 | 2/4 | **0.36** |
| D2 技能×空间 | L2 | `put_toycar_left_basket` | 家务分拣 | 2/4 | **0.44** |
| D3 属性绑定 | L1 | `attr_bind_bottle` | 冰箱取饮 | 未跑（v1 沿用） | **0.39** |
| D3 属性绑定 | L1 | `attr_category_press_bell` | 前台服务 | 2/3 | **1.00** |
| D3 属性绑定 | L2 | `attr_category_can_plasticbox` | 仓储上架 | 2/7 | **0.27** |
| D3 属性绑定 | L2 | `attr_color_beat_block` | 积木码垛 | 3/5 | **0.86** |
| D3 属性绑定 | L2 | `attr_color_block_3way` | 积木码垛 | 2/2 | **0.72** |
| D3 属性绑定 | L2 | `attr_size_beat_smaller` | 积木码垛 | 3/3 | **0.79** |
| D3 属性绑定 | L2 | `attr_size_block_pick` | 积木码垛 | 2/2 | **0.99** |
| D3 属性绑定 | L3 | `attr_bind_soap_box` | 日用品收纳 | 未跑（v1 沿用） | **0.89** |
| D3 属性绑定 | L3 | `attr_size_rank_middle` | 家务分拣 | 2/2 | **0.02** |
| D4 指代结构 | L1 | `ref_block_on_plate` | 餐桌收拾 | 2/2 | **0.00** |
| D4 指代结构 | L2 | `ref_block_behind_can` | 通用桌面 | 2/3 | **0.01** |
| D4 指代结构 | L2 | `ref_cup_on_tray` | 快餐取餐 | 2/2 | **0.00** |
| D4 指代结构 | L2 | `ref_leftmost_of_four` | 积木码垛 | 2/2 | **0.36** |
| D4 指代结构 | L2 | `ref_not_the_red_one` | 积木码垛 | 2/2 | **0.06** |
| D4 指代结构 | L2 | `ref_second_from_left` | 积木码垛 | 2/2 | **0.00** |
| D5 技能×技能(时序) | L2 | `adjust_bottle_dustbin` | 垃圾清理 | 2/2 | **0.93** |
| D5 技能×技能(时序) | L2 | `click_bell_press_stapler` | 前台服务 | 未跑（v1 沿用） | **0.06** |
| D5 技能×技能(时序) | L2 | `stapler_pad_press` | 办公桌 | 未跑（v1 沿用） | **0.97** |
| D7 混合 | L2 | `move_cup_pad_mix` | 办公桌 | 2/2 | **0.31** |
| D7 混合 | L2 | `ref_block_on_plate_mix` | 餐桌收拾 | 2/2 | **0.00** |
| D7 混合 | L3 | `attr_teabox_basket_then_ring` | 厨房备餐 | 2/3 | **0.00** |
| D7 混合 | L3 | `put_toycar_left_basket_mix` | 家务分拣 | 2/6 | **0.27** |

## 未完成（10 个）

8 小时预算到点时仍在队列中或未跑满 20 条。

- **D1 技能×物体**：`place_teabox_skillet`
- **D2 技能×空间**：`place_between_bowls`、`place_teabox_front_of_skillet`
- **D4 指代结构**：`ref_mug_next_to_bowl`
- **D5 技能×技能(时序)**：`lift_pot_to_pad`、`pack_toycar_then_ring`、`serve_teabox_then_ring`
- **D7 混合**：`card_right_of_scanner_mix`、`place_teabox_skillet_mix`、`roller_to_plate_mix`

## 需要复查的零分场景

专家烟测都通过（场景可解），但策略 0/20。需要看视频确认是模型失败还是判据过严。

| 维度 | 场景 | 专家产出率 |
|---|---|---|
| D2 技能×空间 | `phone_right_of_laptop` | 2/3 |
| D4 指代结构 | `ref_block_on_plate` | 2/2 |
| D4 指代结构 | `ref_cup_on_tray` | 2/2 |
| D4 指代结构 | `ref_second_from_left` | 2/2 |
| D7 混合 | `ref_block_on_plate_mix` | 2/2 |
| D7 混合 | `attr_teabox_basket_then_ring` | 2/3 |
