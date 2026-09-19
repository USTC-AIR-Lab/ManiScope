"""D4-07 · instruction structure · L2 · 积木码垛

否定式指代 —— 旧套件完全没有这一类

依赖的 RoboTwin 基础任务: 3 blocks_ranking_rgb
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class ref_not_the_red_one(CompoScene):
    A_DESC = 'block that is not red'
    MIRROR = True
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'target',
             'kind': 'box',
             'color': (0.15, 0.3, 0.9),
             'half': 0.025,
             'region': [[-0.22, -0.14], [-0.15, -0.04]],
             'desc': 'block that is not red'},
            {'role': 'distractor',
             'kind': 'box',
             'color': (0.9, 0.15, 0.15),
             'half': 0.025,
             'region': [[0.14, 0.22], [-0.15, -0.04]]}]
