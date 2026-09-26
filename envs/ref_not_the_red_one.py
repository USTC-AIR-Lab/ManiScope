"""D4-07 · instruction structure · L2

RoboTwin source-task links: 3 blocks_ranking_rgb
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
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
