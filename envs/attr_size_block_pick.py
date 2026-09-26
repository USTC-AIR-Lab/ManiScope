"""D3-04 · attribute binding · L2

RoboTwin source-task links: 4 blocks_ranking_size, 45 stack_blocks_three
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
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
