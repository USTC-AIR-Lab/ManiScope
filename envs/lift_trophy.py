"""D1-09 · skill x object · L2 · 厨房备餐

依赖的 RoboTwin 基础任务: 8 grab_roller
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class lift_trophy(CompoScene):
    A_DESC = 'trophy'
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '090_trophy',
             'ids': [0, 1, 2, 3, 4],
             'region': [[-0.22, -0.14], [-0.15, -0.04]],
             'qpos': [1, 0, 0, 0],
             'mass': 0.2}]
