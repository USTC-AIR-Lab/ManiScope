"""D1-08 · skill x object · L2 · 厨房备餐

依赖的 RoboTwin 基础任务: 49 stamp_seal, 30 place_empty_cup
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class place_seal_coaster(CompoScene):
    A_DESC = 'seal'
    GOAL = {'type': 'on', 'ref': 'coaster'}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '100_seal',
             'ids': [0, 1, 2, 3],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'coaster',
             'kind': 'model',
             'model': '019_coaster',
             'ids': [0],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.15, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.05,
             'rot': False,
             'zlim': [0.741]}]
