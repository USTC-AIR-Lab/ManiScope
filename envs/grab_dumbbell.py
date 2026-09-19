"""D1-10 · skill x object · L1 · 健身角

依赖的 RoboTwin 基础任务: 8 grab_roller
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class grab_dumbbell(CompoScene):
    A_DESC = 'dumbbell'
    GOAL = {'type': 'lift', 'dz': 0.035}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '052_dumbbell',
             'ids': [0, 1, 2, 3, 4, 5, 6],
             'region': [[-0.22, -0.14], [-0.15, -0.04]],
             'qpos': [0.707, 0.707, 0, 0]}]
