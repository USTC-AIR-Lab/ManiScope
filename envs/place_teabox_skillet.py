"""D1-15 · skill x object · L2 · 厨房备餐

依赖的 RoboTwin 基础任务: 24 place_bread_skillet
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class place_teabox_skillet(CompoScene):
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
             'rot': False}]
