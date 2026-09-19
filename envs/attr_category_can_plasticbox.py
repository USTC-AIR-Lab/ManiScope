"""D3-05 · attribute binding · L2 · 仓储上架

类别属性 + 容器动作

依赖的 RoboTwin 基础任务: 27 place_cans_plasticbox, 19 pick_diverse_bottles
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class attr_category_can_plasticbox(CompoScene):
    A_DESC = 'can'
    GOAL = {'type': 'in', 'ref': 'pbox', 'r': 0.13}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '071_can',
             'ids': [0, 1, 2, 3],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'desc': 'can',
             'rot': False},
            {'role': 'distractor',
             'kind': 'model',
             'model': '001_bottle',
             'ids': [13, 16],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.02, 0.06]],
             'qpos': [0.707, 0.707, 0, 0]},
            {'role': 'pbox',
             'kind': 'model',
             'model': '062_plasticbox',
             'ids': [3, 5],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.02, 0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.6,
             'pad': 0.05,
             'rot': False}]
