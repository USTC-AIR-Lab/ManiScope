> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# dm05_v6 每个任务的指令与判据（按字母序，同 eval_result/dm05_v6 目录顺序）

每条 episode 的指令从下面的**指令池**里随机抽一句（instruction_type = unseen）。
本轮跑的时候还没有逐条落盘，所以无法对应到具体某条视频；已给 eval_policy 加了记录，
之后跑的会在各任务输出目录下生成 `_instructions.txt`（格式：episodeN\tseed\t指令）。

`{A}` 运行时会被替换成该物体的一句自然语言描述（同一资产有多种说法，逐条随机抽），
`{a}` 替换成用哪条手臂 —— 所以同一句模板在不同 episode 的字面也可能不同。

| # | 任务 | 维度 | L | 指令池（unseen） | 判据 |
|---|---|---|---|---|---|
| 1 | `adjust_bottle_dustbin` | D5 时序 | L2 | `Stand the fallen {A} up, then throw it away into {B}.`<br>`First make {A} head-up with {a}, then dispose of it in {B}.`<br>`Upright {A} and then drop it into {B}.`<br>`Turn {A} head-up, afterwards put it into {B}.`<br>`Get {A} standing, then discard it in {B}.` | 两阶段：瓶子先被扶正（长轴朝上、在左侧），再落进垃圾桶内 |
| 2 | `attr_bind_bottle` | D3 属性绑定 | L1 | `Pick up the {A} please.`<br>`Raise the {A}.`<br>`Use {a} to lift the {A}.`<br>`Take hold of the {A}.`<br>`Pick the {A} up.` | 目标位移 > 0.05m 且大于所有干扰物（只判「去够的是哪一个」，不判高度） |
| 3 | `attr_bind_soap_box` | D3 属性绑定 | L3 | `Pick up the {A} please.`<br>`Raise the {A}.`<br>`Use {a} to lift the {A}.`<br>`Take hold of the {A}.`<br>`Pick the {A} up.` | 目标抬升 > 0.10m（三件套：目标/同色异类/同类异色，颜色和类别必须同时绑定） |
| 4 | `attr_category_can_plasticbox` | D3 属性绑定 | L2 | `Put the {A} into the plastic box.`<br>`Please put the {A} into the plastic box.` | 目标进入容器内部（低于容器口沿、在footprint内），双爪松开 |
| 5 | `attr_category_press_bell` | D3 属性绑定 | L1 | `Press the {A}.`<br>`Please press the {A}.` | 夹爪与目标发生真实接触且接触点落在按压点上，物体不能被搬走 |
| 6 | `attr_color_beat_block` | D3 属性绑定 | L2 | `Beat the {A} with the hammer.`<br>`Please beat the {A} with the hammer.` | 锤头(fp0)落到方块敲击点(fp1)上且两者真实接触 |
| 7 | `attr_color_block_3way` | D3 属性绑定 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 8 | `attr_color_bottle_basket` | D3 属性绑定 | L3 | `Put the {A} into the basket.`<br>`Please put the {A} into the basket.` | 目标进入容器内部（低于容器口沿、在footprint内），双爪松开 |
| 9 | `attr_size_beat_smaller` | D3 属性绑定 | L2 | `Beat the {A} with the hammer.`<br>`Please beat the {A} with the hammer.` | 锤头(fp0)落到方块敲击点(fp1)上且两者真实接触 |
| 10 | `attr_size_block_pick` | D3 属性绑定 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 11 | `attr_size_rank_middle` | D3 属性绑定 | L3 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 12 | `attr_teabox_basket_then_ring` | D7 混合 | L3 | `Put the {A} into the basket, then press the bell.`<br>`Please put the {A} into the basket, then press the bell.` | 分阶段：每一步都要按顺序完成 |
| 13 | `card_right_of_scanner` | D2 技能×空间 | L2 | `Put the {A} to the right of the barcode scanner.`<br>`Please put the {A} to the right of the barcode scanner.` | 目标落在参照物指定一侧的间距区间内，横向不跑偏，双爪松开 |
| 14 | `card_right_of_scanner_mix` | D7 混合 | L3 | `Put the {A} to the right of the barcode scanner.`<br>`Please put the {A} to the right of the barcode scanner.` | 目标落在参照物指定一侧的间距区间内，横向不跑偏，双爪松开 |
| 15 | `click_bell_press_stapler` | D5 时序 | L2 | `Click {A} first, then press {B}.`<br>`Ring {A} and then push {B} down.`<br>`After clicking {A}, press {B}.`<br>`Tap {A}, afterwards press down on {B}.`<br>`Press {A} then {B}, in that order.` | stage >= 2：先按响铃铛再按下订书机，第二步必须在第一步之后 |
| 16 | `grab_dumbbell` | D1 技能×物体 | L1 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 17 | `grasp_mallet_novel` | D1 技能×物体 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 18 | `lift_pot_dual` | D5 时序 | L3 | `Lift the {A} with both arms.`<br>`Please lift the {A} with both arms.` | 双臂各抓一个把手，把物体抬离桌面 |
| 19 | `lift_trophy` | D1 技能×物体 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 20 | `move_can_coaster` | D1 技能×物体 | L1 | `Put the {A} on the coaster.`<br>`Please put the {A} on the coaster.` | 目标落在参照物上方薄层内，且双爪松开、有支撑接触 |
| 21 | `move_cube_on_plate_to_pad` | D4 指代结构 | L3 | `Move the cube that is on the plate onto the pad, then release it.`<br>`Move the cube that is on the plate onto the pad, then release it.`<br>`Move the cube that is on the plate onto the pad, then release it.`<br>`Move the cube that is on the plate onto the pad, then release it.`<br>`Move the cube that is on the plate onto the pad, then release it.` | 盘子上那个魔方抬升 > 0.10m；先抬错的那个直接判负 |
| 22 | `move_cup_pad` | D1 技能×物体 | L1 | `Move {A} to the {B} mat.`<br>`Place {A} on the {B} colored mat.`<br>`Use {a} to move {A} to {B} mat.`<br>`Place {A} on the {B} colored mat.`<br>`Use {a} to move {A} to the {B} mat`<br>`Move {A} to the {B} colored mat`<br>`Grab {A} and set it on {B} mat`<br>`Use {a} to move {A} to {B} mat`<br>`Move {A} to the {B} mat`<br>`Place {A} on the {B} mat` |  |
| 23 | `move_cup_pad_mix` | D7 混合 | L2 | `Move the {A} onto the pad.`<br>`Please move the {A} onto the pad.` | 目标落在参照物上方薄层内，且双爪松开、有支撑接触 |
| 24 | `pack_toycar_then_ring` | D5 时序 | L3 | `Put the {A} into the plastic box, then press the bell.`<br>`Please put the {A} into the plastic box, then press the bell.` | 分阶段：每一步都要按顺序完成 |
| 25 | `phone_right_of_laptop` | D2 技能×空间 | L2 | `Put the {A} to the right of the laptop.`<br>`Please put the {A} to the right of the laptop.` | 目标落在参照物指定一侧的间距区间内，横向不跑偏，双爪松开 |
| 26 | `place_a2b_behind_novel` | D2 技能×空间 | L2 | `Put the {A} behind the bowl.`<br>`Please put the {A} behind the bowl.` | 目标落在参照物指定一侧的间距区间内，横向不跑偏，双爪松开 |
| 27 | `place_a2b_left_novel` | D2 技能×空间 | L1 | `Use {a} to put {A} left of {B}.`<br>`Set {A} on the left side of {B}.`<br>`Set {A} to the left of {B}`<br>`Position {A} on the left of {B}`<br>`Grab {A} and place left of {B}`<br>`Set {A} down to the left of {B}`<br>`Pick {A} and set it left of {B}.`<br>`Use {a} to place {A} left of {B}.`<br>`Set {A} on the left side of {B}`<br>`Place {A} to the left of {B} using {a}` |  |
| 28 | `place_a2b_right_novel` | D2 技能×空间 | L1 | `Use {a} to put {A} right of {B}.`<br>`Set {A} on the right side of {B}.`<br>`Set {A} to the right of {B}`<br>`Position {A} on the right of {B}`<br>`Grab {A} and place right of {B}`<br>`Set {A} down to the right of {B}`<br>`Pick {A} and set it right of {B}.`<br>`Use {a} to place {A} right of {B}.`<br>`Set {A} on the right side of {B}`<br>`Place {A} to the right of {B} using {a}` |  |
| 29 | `place_between_bowls` | D2 技能×空间 | L3 | `Put the {A} between the two bowls.`<br>`Please put the {A} between the two bowls.` | 目标落在两个参照物连线中点附近，双爪松开 |
| 30 | `place_can_right_of_plasticbox` | D2 技能×空间 | L2 | `Put the {A} to the right of the plastic box.`<br>`Please put the {A} to the right of the plastic box.` | 目标落在参照物指定一侧的间距区间内，横向不跑偏，双爪松开 |
| 31 | `place_cube_right_of_plate` | D2 技能×空间 | L2 | `Put the {A} to the right of the plate.`<br>`Please put the {A} to the right of the plate.` | 目标落在参照物指定一侧的间距区间内，横向不跑偏，双爪松开 |
| 32 | `place_seal_coaster` | D1 技能×物体 | L2 | `Put the {A} on the coaster.`<br>`Please put the {A} on the coaster.` | 目标落在参照物上方薄层内，且双爪松开、有支撑接触 |
| 33 | `place_teabox_front_of_skillet` | D2 技能×空间 | L2 | `Put the {A} in front of the skillet.`<br>`Please put the {A} in front of the skillet.` | 目标落在参照物指定一侧的间距区间内，横向不跑偏，双爪松开 |
| 34 | `place_teabox_scale` | D1 技能×物体 | L1 | `Put the {A} on the scale.`<br>`Please put the {A} on the scale.` | 目标落在参照物上方薄层内，且双爪松开、有支撑接触 |
| 35 | `place_teabox_skillet` | D1 技能×物体 | L2 | `Put the {A} into the skillet.`<br>`Please put the {A} into the skillet.` | 目标进入容器内部（低于容器口沿、在footprint内），双爪松开 |
| 36 | `place_teabox_skillet_mix` | D7 混合 | L3 | `Put the {A} into the skillet.`<br>`Please put the {A} into the skillet.` | 目标进入容器内部（低于容器口沿、在footprint内），双爪松开 |
| 37 | `place_teabox_stand` | D1 技能×物体 | L2 | `Put the {A} on the display stand.`<br>`Please put the {A} on the display stand.` | 目标落在参照物上方薄层内，且双爪松开、有支撑接触 |
| 38 | `place_toycar_plasticbox` | D1 技能×物体 | L2 | `Put the {A} into the plastic box.`<br>`Please put the {A} into the plastic box.` | 目标进入容器内部（低于容器口沿、在footprint内），双爪松开 |
| 39 | `put_toycar_left_basket` | D2 技能×空间 | L2 | `Put the {A} into the left basket.`<br>`Please put the {A} into the left basket.` | 目标进入容器内部（低于容器口沿、在footprint内），双爪松开 |
| 40 | `put_toycar_left_basket_mix` | D7 混合 | L3 | `Put the {A} into the left basket.`<br>`Please put the {A} into the left basket.` | 目标进入容器内部（低于容器口沿、在footprint内），双爪松开 |
| 41 | `ref_block_behind_can` | D4 指代结构 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 42 | `ref_block_on_plate` | D4 指代结构 | L1 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 43 | `ref_block_on_plate_mix` | D7 混合 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 44 | `ref_cube_on_plate_to_pad` | D4 指代结构 | L3 | `Move the {A} onto the pad.`<br>`Please move the {A} onto the pad.` | 目标落在参照物上方薄层内，且双爪松开、有支撑接触 |
| 45 | `ref_cup_on_tray` | D4 指代结构 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 46 | `ref_leftmost_of_four` | D4 指代结构 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 47 | `ref_mug_next_to_bowl` | D4 指代结构 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 48 | `ref_not_the_red_one` | D4 指代结构 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 49 | `ref_second_from_left` | D4 指代结构 | L2 | `Pick up the {A}.`<br>`Please pick up the {A}.` | 把目标拿离桌面（且仍被夹爪夹住） |
| 50 | `roller_to_plate_mix` | D7 混合 | L3 | `Put the {A} on the plate.`<br>`Please put the {A} on the plate.` | 目标落在参照物上方薄层内，且双爪松开、有支撑接触 |
| 51 | `serve_teabox_then_ring` | D5 时序 | L2 | `Put the {A} into the basket, then press the bell.`<br>`Please put the {A} into the basket, then press the bell.` | 分阶段：每一步都要按顺序完成 |
| 52 | `stapler_pad_press` | D5 时序 | L2 | `Move {A} to the {B} mat, then press down on it.`<br>`Put {A} onto the {B} colored mat and press it.`<br>`Use {a} to move {A} to the {B} mat, then press {A}.`<br>`Set {A} on the {B} mat, then push it down.`<br>`Place {A} on the {B} mat and then press on it.` | stage >= 2：先把订书机放到垫子上再按下去，顺序不能反 |

## 判据原文（GOAL 字段）

- `adjust_bottle_dustbin`: ``
- `attr_bind_bottle`: ``
- `attr_bind_soap_box`: ``
- `attr_category_can_plasticbox`: `{'type': 'in', 'ref': 'pbox', 'r': 0.13}`
- `attr_category_press_bell`: `{'type': 'press', 'ref': 'target', 'model': '050_bell', 'cp': 0}`
- `attr_color_beat_block`: `{'type': 'beat', 'tool': 'hammer'}`
- `attr_color_block_3way`: `{'type': 'lift', 'dz': 0.06}`
- `attr_color_bottle_basket`: `{'type': 'in', 'ref': 'basket', 'r': 0.12}`
- `attr_size_beat_smaller`: `{'type': 'beat', 'tool': 'hammer'}`
- `attr_size_block_pick`: `{'type': 'lift', 'dz': 0.06}`
- `attr_size_rank_middle`: `{'type': 'lift', 'dz': 0.06}`
- `attr_teabox_basket_then_ring`: `{'type': 'seq',`
- `card_right_of_scanner`: `{'type': 'rel', 'ref': 'scanner', 'dir': 'right', 'gap': [0.05, 0.22], 'min_start': 0.18}`
- `card_right_of_scanner_mix`: `{'type': 'rel', 'ref': 'scanner', 'dir': 'right', 'gap': [0.05, 0.22], 'min_start': 0.18}`
- `click_bell_press_stapler`: ``
- `grab_dumbbell`: `{'type': 'lift', 'dz': 0.05}`
- `grasp_mallet_novel`: `{'type': 'lift', 'dz': 0.05}`
- `lift_pot_dual`: `{'type': 'dual_carry', 'dz': 0.08}`
- `lift_trophy`: `{'type': 'lift', 'dz': 0.06}`
- `move_can_coaster`: `{'type': 'on', 'ref': 'coaster'}`
- `move_cube_on_plate_to_pad`: ``
- `move_cup_pad`: ``
- `move_cup_pad_mix`: `{'type': 'on', 'ref': 'pad'}`
- `pack_toycar_then_ring`: `{'type': 'seq',`
- `phone_right_of_laptop`: `{'type': 'rel', 'ref': 'laptop', 'dir': 'right', 'gap': [0.05, 0.22]}`
- `place_a2b_behind_novel`: `{'type': 'rel', 'ref': 'ref', 'dir': 'behind', 'gap': [0.05, 0.22], 'lat': 0.13}`
- `place_a2b_left_novel`: ``
- `place_a2b_right_novel`: ``
- `place_between_bowls`: `{'type': 'between', 'refs': ['b1', 'b2'], 'lat': 0.1}`
- `place_can_right_of_plasticbox`: `{'type': 'rel', 'ref': 'pbox', 'dir': 'right', 'gap': [0.05, 0.24], 'lat': 0.14, 'upright': True}`
- `place_cube_right_of_plate`: `{'type': 'rel', 'ref': 'plate', 'dir': 'right', 'gap': [0.14, 0.26], 'lat': 0.13}`
- `place_seal_coaster`: `{'type': 'on', 'ref': 'coaster'}`
- `place_teabox_front_of_skillet`: `{'type': 'rel', 'ref': 'skillet', 'dir': 'front', 'gap': [0.05, 0.22], 'lat': 0.14}`
- `place_teabox_scale`: `{'type': 'on', 'ref': 'scale'}`
- `place_teabox_skillet`: `{'type': 'in', 'ref': 'skillet', 'r': 0.16}`
- `place_teabox_skillet_mix`: `{'type': 'in', 'ref': 'skillet', 'r': 0.16}`
- `place_teabox_stand`: `{'type': 'on', 'ref': 'stand'}`
- `place_toycar_plasticbox`: `{'type': 'in', 'ref': 'box', 'r': 0.13}`
- `put_toycar_left_basket`: `{'type': 'in', 'ref': 'basket_l', 'r': 0.12}`
- `put_toycar_left_basket_mix`: `{'type': 'in', 'ref': 'basket_l', 'r': 0.12}`
- `ref_block_behind_can`: `{'type': 'lift', 'dz': 0.06}`
- `ref_block_on_plate`: `{'type': 'lift', 'dz': 0.06}`
- `ref_block_on_plate_mix`: `{'type': 'lift', 'dz': 0.06}`
- `ref_cube_on_plate_to_pad`: `{'type': 'on', 'ref': 'pad', 'dz': 0.03, 'eps': [0.05, 0.05, 0.035]}`
- `ref_cup_on_tray`: `{'type': 'lift', 'dz': 0.06}`
- `ref_leftmost_of_four`: `{'type': 'lift', 'dz': 0.06}`
- `ref_mug_next_to_bowl`: `{'type': 'lift', 'dz': 0.06}`
- `ref_not_the_red_one`: `{'type': 'lift', 'dz': 0.06}`
- `ref_second_from_left`: `{'type': 'lift', 'dz': 0.06}`
- `roller_to_plate_mix`: `{'type': 'on', 'ref': 'plate'}`
- `serve_teabox_then_ring`: `{'type': 'seq',`
- `stapler_pad_press`: ``
