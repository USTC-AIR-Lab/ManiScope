"""D1-15 · mixture · L3 · 厨房备餐

混合维度：源场景 place_teabox_skillet + 一个语义无关的干扰物（073_rubikscube）。灶台上多一个魔方。判据/指令/依赖全部继承源场景，只多干扰物 —— 和源场景的分差就是「干扰物 + 背景变化」这一维的代价。

依赖的 RoboTwin 基础任务: 24 place_bread_skillet
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class place_teabox_skillet_mix(CompoScene):
    A_DESC = 'tea box'
    GOAL = {'type': 'in', 'ref': 'skillet', 'r': 0.16}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '112_tea-box',
             'ids': [0, 1, 2, 3, 4],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'skillet',
             'kind': 'model',
             'model': '106_skillet',
             'ids': [0, 1, 2, 3],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.02, 0.06]],
             'qpos': [0, 0, 0.707, 0.707],
             'mass': 0.6,
             'pad': 0.05,
             'rot': False},
            {'role': 'mix_distractor',
             'kind': 'model',
             'model': '073_rubikscube',
             'ids': [0, 1, 2],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.14, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False,
             'pad': 0.06}]
