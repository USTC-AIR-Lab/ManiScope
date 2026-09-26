"""D4-03 · instruction structure · L2

RoboTwin source-task links: 21 place_a2b_left, 22 place_a2b_right
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class ref_block_behind_can(CompoScene):
    A_DESC = 'block behind the can'
    MIRROR = True
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'can',
             'kind': 'model',
             'model': '071_can',
             'ids': [0, 1, 2],
             'region': [[-0.06, 0.06], [-0.14, -0.08]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False,
             'static': True,
             'pad': 0.03},
            {'role': 'target',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'rel': 'can',
             'offset': [0, 0.11, -0.02],
             'desc': 'block behind the can'},
            {'role': 'distractor',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[0.14, 0.22], [-0.15, -0.04]]}]
