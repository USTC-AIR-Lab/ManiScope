> Historical development record. Not current ManipScope instructions or validated release results. See [archive scope](README.md).

# LLM agent 终止方式统计

口径：每场景前 5 个冻结种子，只统计已落盘 `_result.txt` 的场景（不含 `_failed/`）。
终止类型：`env_success` 判据在任一步满足即结束；`model_finish` 模型调用 finish 工具；`wall_budget_3300s` 单 episode 墙钟 55 min；`budget` 120 次调用上限；`step_limit` 步数上限。

## GPT-6 Astra(high) · `formal_gpt6_20260913` · 48 场景 / 240 episode

| 终止方式 | episode 数 | 占比 | 其中判据成功 | 成功占该类 |
|---|---|---|---|---|
| env_success | 185 | 77.1% | 185 | 100.0% |
| model_finish | 46 | 19.2% | 0 | 0.0% |
| wall_budget_3300s | 6 | 2.5% | 0 | 0.0% |
| step_limit | 3 | 1.2% | 0 | 0.0% |

- 总成功率 185/240 = 0.771。判据每步检查、满足即终止，所以成功的 episode 全部记为 env_success；
  model_finish 恒为失败——它表示模型在判据尚未满足时就宣告完成（误报完成）。误报完成率 = 46/240 = 19.2%；
  从未宣告完成、直到墙钟/步数耗尽 = 9 条（3.8%）。

model_finish 且判据失败 的 episode 按位移记录分类：

| 类别 | 数量 | 占比 | 例 |
|---|---|---|---|
| A 目标几乎没动(空报完成) | 5 | 11% | attr_color_beat_block#1, attr_color_beat_block#3, attr_color_beat_block#4 |
| B 目标掉出桌面 | 6 | 13% | place_teabox_scale#2, place_toycar_plasticbox#2, put_toycar_left_basket_mix#2 |
| C 干扰物位移>目标(先动/多动干扰物) | 3 | 7% | place_teabox_skillet#0, attr_bind_bottle#0, attr_bind_bottle#3 |
| D 目标动了且干扰物被碰>5cm | 9 | 20% | move_cup_pad_mix#1, attr_teabox_basket_then_ring#3, attr_teabox_basket_then_ring#4 |
| E 目标动了、干扰物没动、终态不达标 | 16 | 35% | card_right_of_scanner_mix#4, place_seal_coaster#3, card_right_of_scanner#0 |
| F 无位移记录(按压/开合类) | 7 | 15% | move_cup_pad#0, attr_bind_soap_box#1, place_a2b_left_novel#0 |

## Gemini 3.8 Flash(high) · `formal_gemini38flash_20260914` · 48 场景 / 240 episode

| 终止方式 | episode 数 | 占比 | 其中判据成功 | 成功占该类 |
|---|---|---|---|---|
| model_finish | 120 | 50.0% | 0 | 0.0% |
| wall_budget_3300s | 62 | 25.8% | 0 | 0.0% |
| env_success | 58 | 24.2% | 58 | 100.0% |

- 总成功率 58/240 = 0.242。判据每步检查、满足即终止，所以成功的 episode 全部记为 env_success；
  model_finish 恒为失败——它表示模型在判据尚未满足时就宣告完成（误报完成）。误报完成率 = 120/240 = 50.0%；
  从未宣告完成、直到墙钟/步数耗尽 = 62 条（25.8%）。

model_finish 且判据失败 的 episode 按位移记录分类：

| 类别 | 数量 | 占比 | 例 |
|---|---|---|---|
| A 目标几乎没动(空报完成) | 40 | 33% | card_right_of_scanner_mix#4, place_seal_coaster#1, card_right_of_scanner#0 |
| B 目标掉出桌面 | 10 | 8% | move_cup_pad_mix#1, move_can_coaster#4, attr_bind_bottle#0 |
| C 干扰物位移>目标(先动/多动干扰物) | 8 | 7% | card_right_of_scanner_mix#3, attr_bind_bottle#1, attr_bind_bottle#2 |
| D 目标动了且干扰物被碰>5cm | 3 | 2% | card_right_of_scanner_mix#0, place_teabox_skillet_mix#2, lift_pot_to_pad#0 |
| E 目标动了、干扰物没动、终态不达标 | 38 | 32% | place_teabox_scale#0, place_teabox_scale#1, place_teabox_scale#3 |
| F 无位移记录(按压/开合类) | 21 | 18% | move_cup_pad#1, move_cup_pad#2, move_cup_pad#4 |
