"""D1-14 · skill x object · L2 · 玄关

依赖的 RoboTwin 基础任务: 33 place_object_basket, 27 place_cans_plasticbox
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class place_toycar_plasticbox(CompoScene):
    A_DESC = 'toy car'
    GOAL = {'type': 'in', 'ref': 'box', 'r': 0.13}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '057_toycar',
             'ids': [0, 1, 2, 3, 4, 5],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.707, 0.707, 0, 0]},
            {'role': 'box',
             'kind': 'model',
             'model': '062_plasticbox',
             'ids': [3, 5],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.02, 0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.6,
             'pad': 0.05,
             'rot': False}]
