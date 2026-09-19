"""D7-06 · mixture · L3 · 厨房备餐

属性 × 时序

依赖的 RoboTwin 基础任务: 23 place_bread_basket, 6 click_bell, 19 pick_diverse_bottles
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class attr_teabox_basket_then_ring(CompoScene):
    A_DESC = 'tea box'
    GOAL = {'type': 'seq',
            'stages': [{'type': 'in', 'ref': 'breadbasket', 'r': 0.12},
                       {'type': 'press', 'ref': 'bell', 'model': '050_bell', 'cp': 0}]}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '112_tea-box',
             'ids': [0, 1, 2],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'desc': 'tea box',
             'rot': False},
            {'role': 'distractor',
             'kind': 'model',
             'model': '035_apple',
             'ids': [0, 1],
             'region': [[-0.21000000000000002, -0.12000000000000001], [0.01, 0.07]],
             'qpos': [1, 0, 0, 0]},
            {'role': 'breadbasket',
             'kind': 'model',
             'model': '110_basket',
             'ids': [0, 1, 2, 3],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.02, 0.05]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.5,
             'pad': 0.05,
             'rot': False},
            {'role': 'bell',
             'kind': 'model',
             'model': '050_bell',
             'ids': [0, 1],
             'region': [[-0.21000000000000002, -0.12000000000000001], [0.02, 0.08]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.3,
             'pad': 0.08}]
