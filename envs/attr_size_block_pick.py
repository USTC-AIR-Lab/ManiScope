"""D3-04 · attribute binding · L2 · 积木码垛

尺寸属性。用裸方块 + lift 判据：方块能抓能举，但过不了 place_actor(实测 0-1/10)，所以尺寸这一维只能做纯抓取；容器动作那一维由 D3-05/D3-11 承担

依赖的 RoboTwin 基础任务: 4 blocks_ranking_size, 45 stack_blocks_three
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class attr_size_block_pick(CompoScene):
    A_DESC = 'smaller block'
    MIRROR = True
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'target',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half': 0.016,
             'region': [[-0.22, -0.18], [-0.15, -0.05]],
             'desc': 'smaller block'},
            {'role': 'distractor',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half': 0.03,
             'region': [[-0.22, -0.18], [-0.02, 0.06]]}]
