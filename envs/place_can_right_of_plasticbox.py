"""D2-10 · skill x spatial · L2

RoboTwin source-task links: 27 place_cans_plasticbox, 21 place_a2b_left
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class place_can_right_of_plasticbox(CompoScene):
    A_DESC = 'can'
    GOAL = {'type': 'rel', 'ref': 'pbox', 'dir': 'right', 'gap': [0.05, 0.24], 'lat': 0.14, 'upright': True}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '071_can',
             'ids': [0, 1, 2, 3],
             'region': [[-0.05, 0.05], [-0.19, -0.14]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False,
             'half': 0.035},
            {'role': 'pbox',
             'kind': 'model',
             'model': '062_plasticbox',
             'ids': [3, 5],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.05, 0.03]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.06,
             'side': -1,
             'rot': False,
             'zlim': [0.741]}]
