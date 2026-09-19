"""D3-08 · attribute binding · L3 · 家务分拣

尺寸序位（三选一的中间档），比二选一的大/小难一级

依赖的 RoboTwin 基础任务: 4 blocks_ranking_size, 28 place_container_plate
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class attr_size_rank_middle(CompoScene):
    A_DESC = 'medium block'
    SHUFFLE_SLOTS = ['target', 'd1', 'd2']
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'target',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half': 0.023,
             'region': [[-0.04, 0.04], [-0.13, -0.05]],
             'desc': 'medium block'},
            {'role': 'small',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half': 0.015,
             'region': [[-0.22, -0.17], [-0.13, -0.05]]},
            {'role': 'big',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half': 0.031,
             'region': [[0.17, 0.22], [-0.13, -0.05]]}]
