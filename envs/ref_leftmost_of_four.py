"""D4-05 · instruction structure · L2

RoboTwin source-task links: 3 blocks_ranking_rgb, 45 stack_blocks_three
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class ref_leftmost_of_four(CompoScene):
    A_DESC = 'leftmost block'
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'target',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[-0.22, -0.16], [-0.13, -0.05]],
             'desc': 'leftmost block'},
            {'role': 'd1',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[-0.13, -0.09], [-0.13, -0.05]]},
            {'role': 'd2',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[0.0, 0.04], [-0.13, -0.05]]},
            {'role': 'd3',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[0.13, 0.17], [-0.13, -0.05]]}]
