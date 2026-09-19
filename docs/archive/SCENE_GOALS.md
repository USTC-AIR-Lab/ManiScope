> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# 组合泛化场景 · 目标清单

对应总览图 `compo_v2_overview.png`，编号一致。

**判据分两层，缺一不可**：
1. **选对** — 目标位移必须严格大于所有干扰物（不解析指令的策略拿不到分）；
2. **做对** — 下表「达成条件」列，即任务名承诺的那个终态。

`专家` 是专家产出率（`script/collect_data.py` 口径），≥ 2/8 才进这张表；
`未跑` 的是 v1 沿用的手写场景，判据本来就完整。


## D1 技能×物体

> 训练过的技能迁到没见过的物体

| # | 场景 | 生活场景 | 难度 | 指令 | 达成条件 | 依赖的 RoboTwin 任务 | 专家 |
|---|---|---|---|---|---|---|---|
| 1 | `grab_dumbbell` | 健身角 | L1 | Pick up the dumbbell. | 把目标抬离桌面 >0.04m | 8 grab_roller | 2/4 |
| 2 | `move_can_coaster` | 床头药盒 | L1 | Put the pill bottle on the coaster. | can 落在「coaster」上方（xy 容差 ±0.035m），双爪张开 | 26 place_can_basket, 30 place_empty_cup | 2/2 |
| 3 | `move_cup_pad` | 办公桌 | L1 | 见 `envs/move_cup_pad.py` | 手写克隆 move_stapler_pad，判据含姿态与双爪张开 | 16 move_stapler_pad | 未跑（v1 沿用） |
| 4 | `place_teabox_scale` | 超市称重 | L1 | Put the tea box on the scale. | tea-box 落在「electronicscale」上方（xy 容差 ±0.035m），双爪张开 | 34 place_object_scale | 2/2 |
| 5 | `grasp_mallet_novel` | 工具台 | L2 | Pick up the wooden mallet. | 把目标抬离桌面 >0.04m | 2 beat_block_hammer, 8 grab_roller | 2/2 |
| 6 | `lift_trophy` | 厨房备餐 | L2 | Pick up the trophy. | 把目标抬离桌面 >0.06m | 8 grab_roller | 2/2 |
| 7 | `place_seal_coaster` | 厨房备餐 | L2 | Put the seal on the coaster. | seal 落在「coaster」上方（xy 容差 ±0.035m），双爪张开 | 49 stamp_seal, 30 place_empty_cup | 2/2 |
| 8 | `place_teabox_skillet` | 厨房备餐 | L2 | Put the tea box into the skillet. | tea-box 落进「skillet」内（xy 距中心 <0.16m、不低于容器口），双爪张开 | 24 place_bread_skillet | 2/2 |
| 9 | `place_teabox_stand` | 书架 | L2 | Put the tea box on the display stand. | tea-box 落在「displaystand」上方（xy 容差 ±0.035m），双爪张开 | 35 place_object_stand | 2/2 |
| 10 | `place_toycar_plasticbox` | 玄关 | L2 | Put the toy car into the plastic box. | toycar 落进「plasticbox」内（xy 距中心 <0.13m、不低于容器口），双爪张开 | 33 place_object_basket, 27 place_cans_plasticbox | 2/2 |

## D2 技能×空间

> 空间关系迁到没见过的物体对

| # | 场景 | 生活场景 | 难度 | 指令 | 达成条件 | 依赖的 RoboTwin 任务 | 专家 |
|---|---|---|---|---|---|---|---|
| 11 | `place_a2b_left_novel` | 通用桌面 | L1 | 见 `envs/place_a2b_left_novel.py` | 手写克隆 place_a2b_left，判据逐字相同 | 21 place_a2b_left | 未跑（v1 沿用） |
| 12 | `place_a2b_right_novel` | 通用桌面 | L1 | 见 `envs/place_a2b_right_novel.py` | 手写克隆 place_a2b_right | 22 place_a2b_right | 未跑（v1 沿用） |
| 13 | `card_right_of_scanner` | 超市结账 | L2 | Put the payment card to the right of the barcode scanner. | paymentsign 落在「scanner」的右侧（间距 0.05–0.22m，横向不跑偏），双爪张开 | 41 rotate_qrcode, 42 scan_object, 22 place_a2b_right | 2/3 |
| 14 | `phone_right_of_laptop` | 办公桌 | L2 | Put the phone to the right of the laptop. | phone 落在「方块」的右侧（间距 0.05–0.22m，横向不跑偏），双爪张开 | 17 open_laptop, 36 place_phone_stand, 22 place_a2b_right | 2/3 |
| 15 | `place_can_right_of_plasticbox` | 仓储上架 | L2 | Put the can to the right of the plastic box. | can 落在「plasticbox」的右侧（间距 0.05–0.24m，横向不跑偏），双爪张开 | 27 place_cans_plasticbox, 21 place_a2b_left | 2/4 |
| 16 | `place_cube_right_of_plate` | 餐桌摆盘 | L2 | Put the cube to the right of the plate. | rubikscube 落在「plate」的右侧（间距 0.14–0.26m，横向不跑偏），双爪张开 | 21 place_a2b_left, 22 place_a2b_right, 28 place_container_plate | 2/4 |
| 17 | `place_teabox_front_of_skillet` | 厨房备餐 | L2 | Put the tea box in front of the skillet. | tea-box 落在「skillet」的前侧（间距 0.05–0.22m，横向不跑偏），双爪张开 | 24 place_bread_skillet, 21 place_a2b_left | 2/2 |
| 18 | `put_toycar_left_basket` | 家务分拣 | L2 | Put the toy car into the left basket. | toycar 落进「basket」内（xy 距中心 <0.12m、不低于容器口），双爪张开 | 33 place_object_basket, 21 place_a2b_left | 2/4 |
| 19 | `place_between_bowls` | 餐桌摆盘 | L3 | Put the cube between the two bowls. | rubikscube 落在「bowl」「bowl」连线中点附近（<0.10m），双爪张开 | 21 place_a2b_left, 22 place_a2b_right, 48 stack_bowls_two | 2/2 |

## D3 属性绑定

> 必须解析属性词才能在干扰物中选对

| # | 场景 | 生活场景 | 难度 | 指令 | 达成条件 | 依赖的 RoboTwin 任务 | 专家 |
|---|---|---|---|---|---|---|---|
| 20 | `attr_bind_bottle` | 冰箱取饮 | L1 | 见 `envs/attr_bind_bottle.py` | 手写，含 ATTR_BIND_LOG 诊断 | 1 adjust_bottle, 19 pick_diverse_bottles | 未跑（v1 沿用） |
| 21 | `attr_category_press_bell` | 前台服务 | L1 | Press the bell. | 夹爪按到「bell」的按压点上，且物体没被搬走（位移 <0.04m） | 6 click_bell, 5 click_alarmclock | 2/3 |
| 22 | `attr_category_can_plasticbox` | 仓储上架 | L2 | Put the can into the plastic box. | can 落进「plasticbox」内（xy 距中心 <0.13m、不低于容器口），双爪张开 | 27 place_cans_plasticbox, 19 pick_diverse_bottles | 2/7 |
| 23 | `attr_color_beat_block` | 积木码垛 | L2 | Beat the purple block with the hammer. | beat | 2 beat_block_hammer, 45 stack_blocks_three | 3/5 |
| 24 | `attr_color_block_3way` | 积木码垛 | L2 | Pick up the red block. | 把目标抬离桌面 >0.06m | 45 stack_blocks_three, 9 handover_block | 2/2 |
| 25 | `attr_size_beat_smaller` | 积木码垛 | L2 | Beat the smaller block with the hammer. | beat | 2 beat_block_hammer, 4 blocks_ranking_size | 3/3 |
| 26 | `attr_size_block_pick` | 积木码垛 | L2 | Pick up the smaller block. | 把目标抬离桌面 >0.06m | 4 blocks_ranking_size, 45 stack_blocks_three | 2/2 |
| 27 | `attr_bind_soap_box` | 日用品收纳 | L3 | 见 `envs/attr_bind_soap_box.py` | 手写，颜色×类别三元组 + 诊断日志 | 40 put_object_cabinet, 42 scan_object | 未跑（v1 沿用） |
| 28 | `attr_size_rank_middle` | 家务分拣 | L3 | Pick up the medium block. | 把目标抬离桌面 >0.06m | 4 blocks_ranking_size, 28 place_container_plate | 2/2 |

## D4 指代结构

> 必须解析指代结构才能锁定目标

| # | 场景 | 生活场景 | 难度 | 指令 | 达成条件 | 依赖的 RoboTwin 任务 | 专家 |
|---|---|---|---|---|---|---|---|
| 29 | `ref_block_on_plate` | 餐桌收拾 | L1 | Pick up the block on the plate. | 把目标抬离桌面 >0.06m | 28 place_container_plate | 2/2 |
| 30 | `ref_block_behind_can` | 通用桌面 | L2 | Pick up the block behind the can. | 把目标抬离桌面 >0.06m | 21 place_a2b_left, 22 place_a2b_right | 2/3 |
| 31 | `ref_cup_on_tray` | 快餐取餐 | L2 | Pick up the block on the tray. | 把目标抬离桌面 >0.06m | 25 place_burger_fries | 2/2 |
| 32 | `ref_leftmost_of_four` | 积木码垛 | L2 | Pick up the leftmost block. | 把目标抬离桌面 >0.06m | 3 blocks_ranking_rgb, 45 stack_blocks_three | 2/2 |
| 33 | `ref_mug_next_to_bowl` | 餐桌收拾 | L2 | Pick up the mug next to the bowl. | 把目标抬离桌面 >0.06m | 11 hanging_mug, 48 stack_bowls_two | 2/3 |
| 34 | `ref_not_the_red_one` | 积木码垛 | L2 | Pick up the block that is not red. | 把目标抬离桌面 >0.06m | 3 blocks_ranking_rgb | 2/2 |
| 35 | `ref_second_from_left` | 积木码垛 | L2 | Pick up the second block from the left. | 把目标抬离桌面 >0.06m | 3 blocks_ranking_rgb, 45 stack_blocks_three | 2/2 |

## D5 技能×技能(时序)

> 两个训练过的技能串联，训练里从未融合

| # | 场景 | 生活场景 | 难度 | 指令 | 达成条件 | 依赖的 RoboTwin 任务 | 专家 |
|---|---|---|---|---|---|---|---|
| 36 | `adjust_bottle_dustbin` | 垃圾清理 | L2 | 见 `envs/adjust_bottle_dustbin.py` | 手写，两段 stage 判据 | 1 adjust_bottle, 39 put_bottles_dustbin | 2/2 |
| 37 | `click_bell_press_stapler` | 前台服务 | L2 | 见 `envs/click_bell_press_stapler.py` | 手写，跨物体按压时序 | 6 click_bell, 38 press_stapler | 未跑（v1 沿用） |
| 38 | `serve_teabox_then_ring` | 厨房备餐 | L2 | Put the tea box into the basket, then press the bell. | ①tea box 落进「basket」内（xy 距中心 <0.12m、不低于容器口），双爪张开 **→** ②夹爪按到「bell」的按压点上，且物体没被搬走（位移 <0.04m） | 23 place_bread_basket, 6 click_bell | 2/2 |
| 39 | `stapler_pad_press` | 办公桌 | L2 | 见 `envs/stapler_pad_press.py` | 手写，stage 序判据 + 分段指令 | 16 move_stapler_pad, 38 press_stapler | 未跑（v1 沿用） |
| 40 | `lift_pot_to_pad` | 厨房备餐 | L3 | Lift the pot with both arms and put it on the pad. | dual_carry_to | 12 lift_pot, 16 move_stapler_pad | 3/10 |
| 41 | `pack_toycar_then_ring` | 玄关 | L3 | Put the toy car into the plastic box, then press the bell. | ①toy car 落进「plasticbox」内（xy 距中心 <0.13m、不低于容器口），双爪张开 **→** ②夹爪按到「bell」的按压点上，且物体没被搬走（位移 <0.04m） | 33 place_object_basket, 27 place_cans_plasticbox, 6 click_bell | 2/2 |

## D7 混合

> 两条以上维度叠加

| # | 场景 | 生活场景 | 难度 | 指令 | 达成条件 | 依赖的 RoboTwin 任务 | 专家 |
|---|---|---|---|---|---|---|---|
| 42 | `move_cup_pad_mix` | 办公桌 | L2 | Move the cup onto the pad. | cup 落在「pad」上方（xy 容差 ±0.035m），双爪张开 | 16 move_stapler_pad | 2/2 |
| 43 | `ref_block_on_plate_mix` | 餐桌收拾 | L2 | Pick up the block on the plate. | 把目标抬离桌面 >0.06m | 28 place_container_plate | 2/2 |
| 44 | `attr_teabox_basket_then_ring` | 厨房备餐 | L3 | Put the tea box into the basket, then press the bell. | ①tea box 落进「basket」内（xy 距中心 <0.12m、不低于容器口），双爪张开 **→** ②夹爪按到「bell」的按压点上，且物体没被搬走（位移 <0.04m） | 23 place_bread_basket, 6 click_bell, 19 pick_diverse_bottles | 2/3 |
| 45 | `card_right_of_scanner_mix` | 超市结账 | L3 | Put the payment card to the right of the barcode scanner. | paymentsign 落在「scanner」的右侧（间距 0.05–0.22m，横向不跑偏），双爪张开 | 41 rotate_qrcode, 42 scan_object, 22 place_a2b_right | 2/3 |
| 46 | `place_teabox_skillet_mix` | 厨房备餐 | L3 | Put the tea box into the skillet. | tea-box 落进「skillet」内（xy 距中心 <0.16m、不低于容器口），双爪张开 | 24 place_bread_skillet | 2/2 |
| 47 | `put_toycar_left_basket_mix` | 家务分拣 | L3 | Put the toy car into the left basket. | toycar 落进「basket」内（xy 距中心 <0.12m、不低于容器口），双爪张开 | 33 place_object_basket, 21 place_a2b_left | 2/6 |
| 48 | `roller_to_plate_mix` | 厨房备餐 | L3 | Put the rolling pin on the plate. | roller 落在「plate」上方（xy 容差 ±0.035m），双爪张开 | 8 grab_roller, 28 place_container_plate | 2/5 |
