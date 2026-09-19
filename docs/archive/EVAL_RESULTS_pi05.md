> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# Pi0.5 组合泛化评测结果

> - **开源权重**：https://huggingface.co/motus-robotics/pi0.5_robotwin2
> - **推理代码**：https://github.com/Physical-Intelligence/openpi
> - **模型说明**：Pi0.5 (motus-robotics/pi0.5_robotwin2)，RoboTwin 2.0 全 50 任务微调（clean 50/任务 + randomized 500/任务）
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


`eval_result/formal_pi05_20260912/` · 每场景 100 条 episode · 成功和失败视频全部保存（仅 head 相机）

**完成 48/48 个场景，共 4800 条 episode。**

## 难度梯度自检

套件的自检项：同一策略在 L1→L3 上若不单调下降，说明分级无效。

| 难度 | 成功率 | 场景数 |
|---|---|---|
| L1 | **0.377** | 9 |
| L2 | **0.359** | 29 |
| L3 | **0.187** | 10 |

**结论：严格单调递减，分级有效 ✓**

## 分维度

置信区间按每场景 100 条 episode 的正态近似算。

| 维度 | 成功率 | 95% CI | 场景数 | episode 数 |
|---|---|---|---|---|
| D3 属性绑定 | **0.48** | ±0.03 | 9 | 900 |
| D1 技能×物体 | **0.46** | ±0.03 | 10 | 1000 |
| D5 技能×技能(时序) | **0.32** | ±0.04 | 6 | 600 |
| D2 技能×空间 | **0.24** | ±0.03 | 9 | 900 |
| D7 混合 | **0.20** | ±0.03 | 7 | 700 |
| D4 指代结构 | **0.18** | ±0.03 | 7 | 700 |

## 全场景明细

`专家` 是专家演示产出率（场景是否可解），`DM0.5` 是策略成功率。

| 维度 | 难度 | 场景 | 生活场景 | 专家 | **DM0.5** |
|---|---|---|---|---|---|
| D1 技能×物体 | L1 | `grab_dumbbell` | 健身角 | 2/4 | **0.56** |
| D1 技能×物体 | L1 | `move_can_coaster` | 床头药盒 | 2/2 | **0.07** |
| D1 技能×物体 | L1 | `move_cup_pad` | 办公桌 | 未跑（v1 沿用） | **0.68** |
| D1 技能×物体 | L1 | `place_teabox_scale` | 超市称重 | 2/2 | **0.21** |
| D1 技能×物体 | L2 | `grasp_mallet_novel` | 工具台 | 2/2 | **0.97** |
| D1 技能×物体 | L2 | `lift_trophy` | 厨房备餐 | 2/2 | **0.66** |
| D1 技能×物体 | L2 | `place_seal_coaster` | 厨房备餐 | 2/2 | **0.34** |
| D1 技能×物体 | L2 | `place_teabox_skillet` | 厨房备餐 | 2/2 | **0.05** |
| D1 技能×物体 | L2 | `place_teabox_stand` | 书架 | 2/2 | **0.39** |
| D1 技能×物体 | L2 | `place_toycar_plasticbox` | 玄关 | 2/2 | **0.71** |
| D2 技能×空间 | L1 | `place_a2b_left_novel` | 通用桌面 | 未跑（v1 沿用） | **0.46** |
| D2 技能×空间 | L1 | `place_a2b_right_novel` | 通用桌面 | 未跑（v1 沿用） | **0.41** |
| D2 技能×空间 | L2 | `card_right_of_scanner` | 超市结账 | 2/3 | **0.12** |
| D2 技能×空间 | L2 | `phone_right_of_laptop` | 办公桌 | 2/3 | **0.02** |
| D2 技能×空间 | L2 | `place_can_right_of_plasticbox` | 仓储上架 | 2/4 | **0.29** |
| D2 技能×空间 | L2 | `place_cube_right_of_plate` | 餐桌摆盘 | 2/4 | **0.36** |
| D2 技能×空间 | L2 | `place_teabox_front_of_skillet` | 厨房备餐 | 2/2 | **0.04** |
| D2 技能×空间 | L2 | `put_toycar_left_basket` | 家务分拣 | 2/4 | **0.02** |
| D2 技能×空间 | L3 | `place_between_bowls` | 餐桌摆盘 | 2/2 | **0.42** |
| D3 属性绑定 | L1 | `attr_bind_bottle` | 冰箱取饮 | 未跑（v1 沿用） | **0.46** |
| D3 属性绑定 | L1 | `attr_category_press_bell` | 前台服务 | 2/3 | **0.54** |
| D3 属性绑定 | L2 | `attr_category_can_plasticbox` | 仓储上架 | 2/7 | **0.04** |
| D3 属性绑定 | L2 | `attr_color_beat_block` | 积木码垛 | 3/5 | **0.69** |
| D3 属性绑定 | L2 | `attr_color_block_3way` | 积木码垛 | 2/2 | **0.83** |
| D3 属性绑定 | L2 | `attr_size_beat_smaller` | 积木码垛 | 3/3 | **0.58** |
| D3 属性绑定 | L2 | `attr_size_block_pick` | 积木码垛 | 2/2 | **0.66** |
| D3 属性绑定 | L3 | `attr_bind_soap_box` | 日用品收纳 | 未跑（v1 沿用） | **0.45** |
| D3 属性绑定 | L3 | `attr_size_rank_middle` | 家务分拣 | 2/2 | **0.03** |
| D4 指代结构 | L1 | `ref_block_on_plate` | 餐桌收拾 | 2/2 | **0.00** |
| D4 指代结构 | L2 | `ref_block_behind_can` | 通用桌面 | 2/3 | **0.24** |
| D4 指代结构 | L2 | `ref_cup_on_tray` | 快餐取餐 | 2/2 | **0.00** |
| D4 指代结构 | L2 | `ref_leftmost_of_four` | 积木码垛 | 2/2 | **0.52** |
| D4 指代结构 | L2 | `ref_mug_next_to_bowl` | 餐桌收拾 | 2/3 | **0.45** |
| D4 指代结构 | L2 | `ref_not_the_red_one` | 积木码垛 | 2/2 | **0.01** |
| D4 指代结构 | L2 | `ref_second_from_left` | 积木码垛 | 2/2 | **0.07** |
| D5 技能×技能(时序) | L2 | `adjust_bottle_dustbin` | 垃圾清理 | 2/2 | **0.97** |
| D5 技能×技能(时序) | L2 | `click_bell_press_stapler` | 前台服务 | 未跑（v1 沿用） | **0.00** |
| D5 技能×技能(时序) | L2 | `serve_teabox_then_ring` | 厨房备餐 | 2/2 | **0.01** |
| D5 技能×技能(时序) | L2 | `stapler_pad_press` | 办公桌 | 未跑（v1 沿用） | **0.59** |
| D5 技能×技能(时序) | L3 | `lift_pot_to_pad` | 厨房备餐 | 3/10 | **0.11** |
| D5 技能×技能(时序) | L3 | `pack_toycar_then_ring` | 玄关 | 2/2 | **0.24** |
| D7 混合 | L2 | `move_cup_pad_mix` | 办公桌 | 2/2 | **0.78** |
| D7 混合 | L2 | `ref_block_on_plate_mix` | 餐桌收拾 | 2/2 | **0.00** |
| D7 混合 | L3 | `attr_teabox_basket_then_ring` | 厨房备餐 | 2/3 | **0.00** |
| D7 混合 | L3 | `card_right_of_scanner_mix` | 超市结账 | 2/3 | **0.08** |
| D7 混合 | L3 | `place_teabox_skillet_mix` | 厨房备餐 | 2/2 | **0.00** |
| D7 混合 | L3 | `put_toycar_left_basket_mix` | 家务分拣 | 2/6 | **0.04** |
| D7 混合 | L3 | `roller_to_plate_mix` | 厨房备餐 | 2/5 | **0.50** |

## 需要复查的零分场景

专家烟测都通过（场景可解），但策略 0/20。需要看视频确认是模型失败还是判据过严。

| 维度 | 场景 | 专家产出率 |
|---|---|---|
| D4 指代结构 | `ref_block_on_plate` | 2/2 |
| D4 指代结构 | `ref_cup_on_tray` | 2/2 |
| D5 技能×技能(时序) | `click_bell_press_stapler` | 未跑（v1 沿用） |
| D7 混合 | `ref_block_on_plate_mix` | 2/2 |
| D7 混合 | `attr_teabox_basket_then_ring` | 2/3 |
| D7 混合 | `place_teabox_skillet_mix` | 2/2 |
