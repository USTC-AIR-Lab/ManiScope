> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# gpt6 agent 计时账本汇总（run `formal_gpt6_20260913`）

仿真在模型推理期间暂停：API 时间与执行时间可分开统计。每场景 5 条（前 5 个冻结种子）。

| 维度 | 难度 | 场景 | 成功 | 平均调用 | 平均 API 秒 | 平均执行秒 | 平均墙钟秒 | 平均推理 token | 平均输入 token | 终止原因 |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | L1 | `grab_dumbbell` | 5/5 | 8.2 | 87 | 169 | 273 | 1662 | 46911 | env_success×5 |
| D1 | L2 | `grasp_mallet_novel` | 5/5 | 8.0 | 76 | 90 | 174 | 1298 | 43819 | env_success×5 |
| D1 | L2 | `lift_trophy` | 5/5 | 30.8 | 433 | 273 | 736 | 8494 | 809696 | env_success×5 |
| D1 | L1 | `move_can_coaster` | 3/5 | 43.8 | 606 | 521 | 1187 | 12157 | 1280673 | env_success×3, model_finish×2 |
| D1 | L1 | `move_cup_pad` | 4/5 | 18.6 | 219 | 301 | 549 | 4232 | 244085 | env_success×4, model_finish×1 |
| D1 | L2 | `place_seal_coaster` | 4/5 | 16.6 | 194 | 217 | 433 | 3739 | 173387 | env_success×4, model_finish×1 |
| D1 | L1 | `place_teabox_scale` | 4/5 | 50.6 | 695 | 476 | 1226 | 13256 | 2004172 | env_success×4, model_finish×1 |
| D1 | L2 | `place_teabox_skillet` | 4/5 | 24.0 | 285 | 560 | 899 | 5386 | 357749 | env_success×4, model_finish×1 |
| D1 | L2 | `place_teabox_stand` | 4/5 | 31.8 | 398 | 476 | 923 | 7289 | 738778 | env_success×4, model_finish×1 |
| D1 | L2 | `place_toycar_plasticbox` | 4/5 | 17.0 | 179 | 208 | 409 | 3126 | 185876 | env_success×4, model_finish×1 |
| D2 | L2 | `card_right_of_scanner` | 2/5 | 39.2 | 557 | 864 | 1496 | 11674 | 1085834 | model_finish×3, env_success×2 |
| D2 | L2 | `phone_right_of_laptop` | 4/5 | 38.0 | 530 | 629 | 1212 | 11163 | 1210326 | env_success×4, wall_budget_3300s×1 |
| D2 | L1 | `place_a2b_left_novel` | 7/9 | 14.2 | 151 | 154 | 323 | 2656 | 163307 | env_success×7, running×1, model_finish×1 |
| D2 | L1 | `place_a2b_right_novel` | 5/5 | 15.8 | 170 | 153 | 341 | 3080 | 180194 | env_success×5 |
| D2 | L3 | `place_between_bowls` | 5/5 | 16.6 | 186 | 218 | 429 | 3396 | 179809 | env_success×5 |
| D2 | L2 | `place_can_right_of_plasticbox` | 2/5 | 17.2 | 187 | 213 | 422 | 3343 | 213060 | model_finish×3, env_success×2 |
| D2 | L2 | `place_cube_right_of_plate` | 5/5 | 12.4 | 118 | 141 | 275 | 1896 | 99942 | env_success×5 |
| D2 | L2 | `place_teabox_front_of_skillet` | 5/5 | 22.0 | 261 | 340 | 635 | 5024 | 317650 | env_success×5 |
| D2 | L2 | `put_toycar_left_basket` | 3/5 | 17.8 | 200 | 222 | 446 | 3575 | 244995 | env_success×3, model_finish×2 |
| D3 | L1 | `attr_bind_bottle` | 1/5 | 10.8 | 147 | 227 | 392 | 3280 | 81683 | model_finish×4, env_success×1 |
| D3 | L3 | `attr_bind_soap_box` | 4/5 | 28.2 | 415 | 335 | 787 | 9184 | 528567 | env_success×4, model_finish×1 |
| D3 | L2 | `attr_category_can_plasticbox` | 4/5 | 20.0 | 247 | 362 | 642 | 4785 | 275197 | env_success×4, model_finish×1 |
| D3 | L1 | `attr_category_press_bell` | 5/5 | 6.4 | 70 | 75 | 152 | 1441 | 30247 | env_success×5 |
| D3 | L2 | `attr_color_beat_block` | 1/5 | 52.8 | 798 | 1013 | 1896 | 17310 | 2187785 | model_finish×3, wall_budget_3300s×1, env_success×1 |
| D3 | L2 | `attr_color_block_3way` | 5/5 | 8.8 | 88 | 70 | 166 | 1630 | 53001 | env_success×5 |
| D3 | L2 | `attr_size_beat_smaller` | 2/5 | 50.4 | 711 | 1197 | 1987 | 14954 | 1723129 | model_finish×2, env_success×2, step_limit×1 |
| D3 | L2 | `attr_size_block_pick` | 5/5 | 23.2 | 309 | 223 | 554 | 6537 | 508251 | env_success×5 |
| D3 | L3 | `attr_size_rank_middle` | 5/5 | 9.4 | 100 | 75 | 183 | 1846 | 58759 | env_success×5 |
| D4 | L2 | `ref_block_behind_can` | 5/5 | 16.0 | 211 | 221 | 454 | 4298 | 191319 | env_success×5 |
| D4 | L1 | `ref_block_on_plate` | 5/5 | 11.6 | 138 | 148 | 304 | 2743 | 95048 | env_success×5 |
| D4 | L2 | `ref_cup_on_tray` | 5/5 | 9.4 | 99 | 142 | 254 | 1757 | 58465 | env_success×5 |
| D4 | L2 | `ref_leftmost_of_four` | 4/5 | 11.0 | 115 | 83 | 208 | 2134 | 82231 | env_success×4, model_finish×1 |
| D4 | L2 | `ref_mug_next_to_bowl` | 5/5 | 16.0 | 201 | 255 | 482 | 3909 | 197694 | env_success×5 |
| D4 | L2 | `ref_not_the_red_one` | 5/5 | 12.4 | 140 | 91 | 242 | 2816 | 122159 | env_success×5 |
| D4 | L2 | `ref_second_from_left` | 5/5 | 11.8 | 133 | 117 | 264 | 2593 | 103619 | env_success×5 |
| D5 | L2 | `adjust_bottle_dustbin` | 1/5 | 37.0 | 567 | 632 | 1246 | 10913 | 911165 | model_finish×3, step_limit×1, env_success×1 |
| D5 | L2 | `click_bell_press_stapler` | 4/5 | 36.4 | 530 | 548 | 1130 | 11277 | 1342862 | env_success×4, step_limit×1 |
| D5 | L3 | `lift_pot_to_pad` | 0/5 | 47.8 | 736 | 766 | 1584 | 15917 | 1387301 | model_finish×5 |
| D5 | L3 | `pack_toycar_then_ring` | 5/5 | 29.6 | 335 | 377 | 752 | 5773 | 619413 | env_success×5 |
| D5 | L2 | `serve_teabox_then_ring` | 3/5 | 40.6 | 536 | 607 | 1211 | 9543 | 1606151 | env_success×3, wall_budget_3300s×1, model_finish×1 |
| D5 | L2 | `stapler_pad_press` | 4/5 | 19.4 | 268 | 198 | 486 | 4853 | 312533 | env_success×4, model_finish×1 |
| D7 | L3 | `attr_teabox_basket_then_ring` | 1/5 | 85.0 | 1365 | 1105 | 2590 | 27016 | 4478231 | wall_budget_3300s×2, model_finish×2, env_success×1 |
| D7 | L3 | `card_right_of_scanner_mix` | 3/5 | 40.6 | 628 | 357 | 1027 | 13552 | 1833458 | env_success×3, wall_budget_3300s×1, model_finish×1 |
| D7 | L2 | `move_cup_pad_mix` | 4/5 | 27.2 | 329 | 489 | 866 | 6040 | 740323 | env_success×4, model_finish×1 |
| D7 | L3 | `place_teabox_skillet_mix` | 5/5 | 20.8 | 229 | 244 | 501 | 4127 | 273492 | env_success×5 |
| D7 | L3 | `put_toycar_left_basket_mix` | 2/5 | 19.8 | 232 | 185 | 438 | 4031 | 271601 | model_finish×3, env_success×2 |
| D7 | L2 | `ref_block_on_plate_mix` | 5/5 | 15.4 | 198 | 132 | 343 | 4083 | 199418 | env_success×5 |
| D7 | L3 | `roller_to_plate_mix` | 5/5 | 28.8 | 368 | 749 | 1179 | 7250 | 563104 | env_success×5 |

## 总览

- episode 总数 244，成功 188（77.0%）
- 平均每条：调用 24.6 次，API 326 s，执行 356 s，墙钟 717 s
- 单次 API 平均响应 13.2 s
- 成功 episode 平均：调用 18.8 次 / API 226 s / 执行 247 s；失败 episode 平均：调用 44.1 次 / API 659 s / 执行 721 s
- token 合计：输入 152,735,561（其中缓存命中 4,508），输出 2,151,325，推理 1,570,817
- API 总时长 22.1 h，执行总时长 24.1 h，墙钟总时长 48.6 h
- 终止原因：{'model_finish': 46, 'env_success': 188, 'wall_budget_3300s': 6, None: 1, 'step_limit': 3}
