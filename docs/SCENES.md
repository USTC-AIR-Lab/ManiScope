# Formal scene catalog

From the frozen manifest; exact instruction pools live in `description/task_instruction/`.

## D1 — 训练过的技能迁到没见过的物体

- `grab_dumbbell` — L1; generated; criterion: lift
- `move_can_coaster` — L1; generated; criterion: on
- `move_cup_pad` — L1; handwritten; criterion: handwritten
- `place_teabox_scale` — L1; generated; criterion: on
- `grasp_mallet_novel` — L2; generated; criterion: lift
- `lift_trophy` — L2; generated; criterion: lift
- `place_seal_coaster` — L2; generated; criterion: on
- `place_teabox_skillet` — L2; generated; criterion: in
- `place_teabox_stand` — L2; generated; criterion: on
- `place_toycar_plasticbox` — L2; generated; criterion: in

## D2 — 空间关系迁到没见过的物体对 / 没训练过的关系词

- `place_a2b_left_novel` — L1; handwritten; criterion: handwritten
- `place_a2b_right_novel` — L1; handwritten; criterion: handwritten
- `card_right_of_scanner` — L2; generated; criterion: rel
- `phone_right_of_laptop` — L2; generated; criterion: rel
- `place_can_right_of_plasticbox` — L2; generated; criterion: rel
- `place_cube_right_of_plate` — L2; generated; criterion: rel
- `place_teabox_front_of_skillet` — L2; generated; criterion: rel
- `put_toycar_left_basket` — L2; generated; criterion: in
- `place_between_bowls` — L3; generated; criterion: between

## D3 — 必须解析属性词才能在干扰物中选对（5 类属性 × 4 类动作）

- `attr_bind_bottle` — L1; handwritten; criterion: handwritten
- `attr_category_press_bell` — L1; generated; criterion: press
- `attr_category_can_plasticbox` — L2; generated; criterion: in
- `attr_color_beat_block` — L2; generated; criterion: beat
- `attr_color_block_3way` — L2; generated; criterion: lift
- `attr_size_beat_smaller` — L2; generated; criterion: beat
- `attr_size_block_pick` — L2; generated; criterion: lift
- `attr_bind_soap_box` — L3; handwritten; criterion: handwritten
- `attr_size_rank_middle` — L3; generated; criterion: lift

## D4 — 必须解析指代结构才能锁定目标（嵌套/序位/序数/邻接/否定）

- `ref_block_on_plate` — L1; generated; criterion: lift
- `ref_block_behind_can` — L2; generated; criterion: lift
- `ref_cup_on_tray` — L2; generated; criterion: lift
- `ref_leftmost_of_four` — L2; generated; criterion: lift
- `ref_mug_next_to_bowl` — L2; generated; criterion: lift
- `ref_not_the_red_one` — L2; generated; criterion: lift
- `ref_second_from_left` — L2; generated; criterion: lift

## D5 — 两个训练过的技能串联，训练里从未融合，顺序有真实依赖

- `adjust_bottle_dustbin` — L2; handwritten; criterion: handwritten
- `click_bell_press_stapler` — L2; handwritten; criterion: handwritten
- `serve_teabox_then_ring` — L2; generated; criterion: seq
- `stapler_pad_press` — L2; handwritten; criterion: handwritten
- `lift_pot_to_pad` — L3; generated; criterion: dual_carry_to
- `pack_toycar_then_ring` — L3; generated; criterion: seq

## D7 — 两条以上维度叠加，复合深度阶梯

- `move_cup_pad_mix` — L2; generated; criterion: on
- `ref_block_on_plate_mix` — L2; generated; criterion: lift
- `attr_teabox_basket_then_ring` — L3; generated; criterion: seq
- `card_right_of_scanner_mix` — L3; generated; criterion: rel
- `place_teabox_skillet_mix` — L3; generated; criterion: in
- `put_toycar_left_basket_mix` — L3; generated; criterion: in
- `roller_to_plate_mix` — L3; generated; criterion: on
