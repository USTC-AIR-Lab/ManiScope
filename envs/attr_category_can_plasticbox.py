"""D3-05 · attribute binding · L2

RoboTwin source-task links: 27 place_cans_plasticbox, 19 pick_diverse_bottles
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class attr_category_can_plasticbox(CompoScene):
    A_DESC = 'can'
    GOAL = {'type': 'in', 'ref': 'pbox', 'r': 0.13}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '071_can',
             'ids': [0, 1, 2, 3],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'desc': 'can',
             'rot': False},
            {'role': 'distractor',
             'kind': 'model',
             'model': '001_bottle',
             'ids': [13, 16],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.02, 0.06]],
             'qpos': [0.707, 0.707, 0, 0]},
            {'role': 'pbox',
             'kind': 'model',
             'model': '062_plasticbox',
             'ids': [3, 5],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.02, 0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.6,
             'pad': 0.05,
             'rot': False}]
