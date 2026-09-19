"""D4-04 · instruction structure · L2 · 积木码垛

序位；MIRROR 必须关，镜像会改答案

依赖的 RoboTwin 基础任务: 3 blocks_ranking_rgb, 45 stack_blocks_three
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class ref_second_from_left(CompoScene):
    A_DESC = 'second block from the left'
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'd1',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[-0.22, -0.17], [-0.13, -0.05]]},
            {'role': 'target',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[-0.04, 0.04], [-0.13, -0.05]],
             'desc': 'second block from the left'},
            {'role': 'd2',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[0.17, 0.22], [-0.13, -0.05]]}]
