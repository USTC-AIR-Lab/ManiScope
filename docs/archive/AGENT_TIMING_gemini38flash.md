> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# gemini38flash agent 计时账本汇总（run `formal_gemini38flash_20260914`）

仿真在模型推理期间暂停：API 时间与执行时间可分开统计。每场景 5 条（前 5 个冻结种子）。

| 维度 | 难度 | 场景 | 成功 | 平均调用 | 平均 API 秒 | 平均执行秒 | 平均墙钟秒 | 平均推理 token | 平均输入 token | 终止原因 |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 | L1 | `grab_dumbbell` | 1/5 | 28.6 | 1418 | 412 | 1892 | 62851 | 2525397 | wall_budget_3300s×2, model_finish×2, env_success×1 |
| D1 | L2 | `grasp_mallet_novel` | 1/5 | 27.6 | 1077 | 174 | 1288 | 52588 | 1934794 | model_finish×4, env_success×1 |
| D1 | L2 | `lift_trophy` | 0/5 | 37.0 | 1715 | 160 | 1922 | 59216 | 3297609 | model_finish×4, wall_budget_3300s×1 |
| D1 | L1 | `move_can_coaster` | 1/5 | 36.6 | 1305 | 446 | 1808 | 51892 | 3430205 | model_finish×2, wall_budget_3300s×2, env_success×1 |
| D1 | L1 | `move_cup_pad` | 0/5 | 42.8 | 1817 | 595 | 2474 | 78967 | 4217260 | model_finish×3, wall_budget_3300s×2 |
| D1 | L2 | `place_seal_coaster` | 1/5 | 35.6 | 1563 | 173 | 1782 | 53921 | 3056882 | model_finish×3, env_success×1, wall_budget_3300s×1 |
| D1 | L1 | `place_teabox_scale` | 0/5 | 54.4 | 2125 | 374 | 2568 | 74081 | 5853316 | model_finish×3, wall_budget_3300s×2 |
| D1 | L2 | `place_teabox_skillet` | 3/5 | 45.6 | 1798 | 292 | 2151 | 75158 | 4945881 | env_success×3, wall_budget_3300s×2 |
| D1 | L2 | `place_teabox_stand` | 0/5 | 39.2 | 2381 | 606 | 3062 | 79280 | 3843175 | wall_budget_3300s×4, model_finish×1 |
| D1 | L2 | `place_toycar_plasticbox` | 2/5 | 45.2 | 1758 | 535 | 2377 | 68725 | 4223863 | env_success×2, model_finish×2, wall_budget_3300s×1 |
| D2 | L2 | `card_right_of_scanner` | 1/5 | 16.2 | 633 | 130 | 779 | 28635 | 1040864 | model_finish×4, env_success×1 |
| D2 | L2 | `phone_right_of_laptop` | 0/5 | 43.4 | 1763 | 837 | 2683 | 63956 | 4200573 | model_finish×3, wall_budget_3300s×2 |
| D2 | L1 | `place_a2b_left_novel` | 3/5 | 26.4 | 1187 | 238 | 1470 | 50301 | 2300574 | env_success×3, model_finish×1, wall_budget_3300s×1 |
| D2 | L1 | `place_a2b_right_novel` | 2/5 | 33.6 | 1296 | 269 | 1612 | 46178 | 2571000 | model_finish×3, env_success×2 |
| D2 | L3 | `place_between_bowls` | 0/5 | 37.4 | 1734 | 366 | 2144 | 61903 | 3322677 | model_finish×4, wall_budget_3300s×1 |
| D2 | L2 | `place_can_right_of_plasticbox` | 0/5 | 24.6 | 868 | 197 | 1091 | 57124 | 1793542 | model_finish×5 |
| D2 | L2 | `place_cube_right_of_plate` | 4/5 | 23.8 | 742 | 176 | 943 | 38787 | 1866383 | env_success×4, model_finish×1 |
| D2 | L2 | `place_teabox_front_of_skillet` | 1/5 | 40.4 | 1604 | 587 | 2248 | 55594 | 3354591 | model_finish×3, env_success×1, wall_budget_3300s×1 |
| D2 | L2 | `put_toycar_left_basket` | 0/5 | 47.2 | 1908 | 349 | 2314 | 57985 | 4767893 | model_finish×3, wall_budget_3300s×2 |
| D3 | L1 | `attr_bind_bottle` | 0/5 | 20.6 | 1423 | 198 | 1662 | 55096 | 1264775 | model_finish×5 |
| D3 | L3 | `attr_bind_soap_box` | 0/5 | 44.2 | 1995 | 199 | 2228 | 76282 | 4610667 | model_finish×4, wall_budget_3300s×1 |
| D3 | L2 | `attr_category_can_plasticbox` | 0/5 | 39.4 | 1946 | 345 | 2336 | 60451 | 3335874 | model_finish×4, wall_budget_3300s×1 |
| D3 | L1 | `attr_category_press_bell` | 5/5 | 7.2 | 350 | 41 | 396 | 29933 | 212569 | env_success×5 |
| D3 | L2 | `attr_color_beat_block` | 0/5 | 33.6 | 1877 | 219 | 2129 | 49853 | 2803794 | model_finish×3, wall_budget_3300s×2 |
| D3 | L2 | `attr_color_block_3way` | 1/5 | 40.6 | 1905 | 222 | 2251 | 74017 | 4440652 | model_finish×3, env_success×1, wall_budget_3300s×1 |
| D3 | L2 | `attr_size_beat_smaller` | 0/5 | 29.6 | 1588 | 257 | 2037 | 71921 | 2223884 | model_finish×4, wall_budget_3300s×1 |
| D3 | L2 | `attr_size_block_pick` | 2/5 | 41.8 | 1994 | 328 | 2369 | 74838 | 4227508 | model_finish×3, env_success×2 |
| D3 | L3 | `attr_size_rank_middle` | 2/5 | 28.4 | 1299 | 239 | 1563 | 61100 | 2602394 | model_finish×2, env_success×2, wall_budget_3300s×1 |
| D4 | L2 | `ref_block_behind_can` | 0/5 | 33.4 | 1786 | 145 | 1963 | 74044 | 3715790 | model_finish×3, wall_budget_3300s×2 |
| D4 | L1 | `ref_block_on_plate` | 2/5 | 31.2 | 1409 | 184 | 1625 | 51553 | 2623387 | model_finish×3, env_success×2 |
| D4 | L2 | `ref_cup_on_tray` | 1/5 | 51.8 | 2914 | 281 | 3251 | 89484 | 5840167 | wall_budget_3300s×3, env_success×1, model_finish×1 |
| D4 | L2 | `ref_leftmost_of_four` | 4/5 | 25.2 | 1300 | 171 | 1493 | 58106 | 2092381 | env_success×4, wall_budget_3300s×1 |
| D4 | L2 | `ref_mug_next_to_bowl` | 1/5 | 33.4 | 1873 | 223 | 2131 | 73829 | 3201489 | model_finish×3, wall_budget_3300s×1, env_success×1 |
| D4 | L2 | `ref_not_the_red_one` | 3/5 | 17.4 | 796 | 101 | 911 | 47009 | 935260 | env_success×3, model_finish×2 |
| D4 | L2 | `ref_second_from_left` | 5/5 | 20.2 | 1017 | 179 | 1222 | 44957 | 1293617 | env_success×5 |
| D5 | L2 | `adjust_bottle_dustbin` | 0/5 | 28.6 | 1656 | 321 | 2008 | 55100 | 2501173 | model_finish×3, wall_budget_3300s×2 |
| D5 | L2 | `click_bell_press_stapler` | 2/5 | 22.6 | 1008 | 111 | 1138 | 47769 | 1238275 | model_finish×3, env_success×2 |
| D5 | L3 | `lift_pot_to_pad` | 0/5 | 41.4 | 1145 | 221 | 1834 | 49030 | 3187617 | model_finish×5 |
| D5 | L3 | `pack_toycar_then_ring` | 0/5 | 51.4 | 2706 | 393 | 3379 | 55597 | 4793013 | wall_budget_3300s×4, model_finish×1 |
| D5 | L2 | `serve_teabox_then_ring` | 1/5 | 55.2 | 2499 | 392 | 2954 | 62243 | 5124052 | wall_budget_3300s×3, env_success×1, model_finish×1 |
| D5 | L2 | `stapler_pad_press` | 0/5 | 35.2 | 2282 | 369 | 2701 | 57429 | 2797564 | model_finish×4, wall_budget_3300s×1 |
| D7 | L3 | `attr_teabox_basket_then_ring` | 0/5 | 57.0 | 2867 | 401 | 3332 | 66685 | 6005329 | wall_budget_3300s×4, model_finish×1 |
| D7 | L3 | `card_right_of_scanner_mix` | 2/5 | 21.4 | 1009 | 241 | 1272 | 47919 | 1469068 | model_finish×3, env_success×2 |
| D7 | L2 | `move_cup_pad_mix` | 0/5 | 28.2 | 1249 | 186 | 1462 | 59317 | 2058092 | model_finish×5 |
| D7 | L3 | `place_teabox_skillet_mix` | 3/5 | 30.0 | 1109 | 217 | 1775 | 53236 | 2309219 | env_success×3, model_finish×1, wall_budget_3300s×1 |
| D7 | L3 | `put_toycar_left_basket_mix` | 0/5 | 50.0 | 2699 | 427 | 3369 | 80968 | 5677616 | wall_budget_3300s×5 |
| D7 | L2 | `ref_block_on_plate_mix` | 4/5 | 24.0 | 1221 | 200 | 1446 | 50553 | 1763976 | env_success×4, model_finish×1 |
| D7 | L3 | `roller_to_plate_mix` | 0/5 | 50.4 | 2639 | 405 | 3100 | 70975 | 5129218 | wall_budget_3300s×4, model_finish×1 |

## 总览

- episode 总数 240，成功 58（24.2%）
- 平均每条：调用 35.0 次，API 1630 s，执行 294 s，墙钟 1999 s
- 单次 API 平均响应 46.6 s
- 成功 episode 平均：调用 20.6 次 / API 947 s / 执行 155 s；失败 episode 平均：调用 39.5 次 / API 1848 s / 执行 339 s
- token 合计：输入 760,124,507（其中缓存命中 41,993,782），输出 754,869，推理 14,332,189
- API 总时长 108.7 h，执行总时长 19.6 h，墙钟总时长 133.3 h
- 终止原因：{'wall_budget_3300s': 62, 'model_finish': 120, 'env_success': 58}
