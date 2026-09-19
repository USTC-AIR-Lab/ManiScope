"""D4-08 · instruction structure · L2 · 快餐取餐

依赖的 RoboTwin 基础任务: 25 place_burger_fries
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class ref_cup_on_tray(CompoScene):
    A_DESC = 'block on the tray'
    MIRROR = True
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'tray',
             'kind': 'model',
             'model': '008_tray',
             'ids': [0, 1, 2, 3],
             'region': [[-0.06, 0.06], [-0.15, -0.04]],
             'qpos': [0.706527, 0.706483, -0.0291356, -0.0291767],
             'static': True,
             'pad': 0.03,
             'rot': False,
             'zlim': [0.741]},
            {'role': 'target',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'rel': 'tray',
             'offset': [0, 0, 0.035],
             'desc': 'block on the tray'},
            {'role': 'distractor',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[0.14, 0.22], [-0.15, -0.04]]}]
