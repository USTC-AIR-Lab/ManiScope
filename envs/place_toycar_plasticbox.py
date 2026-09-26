"""D1-14 · skill x object · L2

RoboTwin source-task links: 33 place_object_basket, 27 place_cans_plasticbox
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class place_toycar_plasticbox(CompoScene):
    A_DESC = 'toy car'
    GOAL = {'type': 'in', 'ref': 'box', 'r': 0.13}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '057_toycar',
             'ids': [0, 1, 2, 3, 4, 5],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.707, 0.707, 0, 0]},
            {'role': 'box',
             'kind': 'model',
             'model': '062_plasticbox',
             'ids': [3, 5],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.02, 0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.6,
             'pad': 0.05,
             'rot': False}]
