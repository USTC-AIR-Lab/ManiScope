"""D3-02 · attribute binding · L2 · 积木码垛

三路颜色干扰，随机基线 33%

依赖的 RoboTwin 基础任务: 45 stack_blocks_three, 9 handover_block
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class attr_color_block_3way(CompoScene):
    A_DESC = 'red block'
    MIRROR = True
    SHUFFLE_SLOTS = ['target', 'd1', 'd2']
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'target',
             'kind': 'box',
             'color': (0.9, 0.15, 0.15),
             'half': 0.025,
             'region': [[-0.22, -0.17], [-0.13, -0.05]],
             'desc': 'red block'},
            {'role': 'd1',
             'kind': 'box',
             'color': (0.15, 0.75, 0.2),
             'half': 0.025,
             'region': [[-0.04, 0.04], [-0.13, -0.05]]},
            {'role': 'd2',
             'kind': 'box',
             'color': (0.15, 0.3, 0.9),
             'half': 0.025,
             'region': [[0.17, 0.22], [-0.13, -0.05]]}]
