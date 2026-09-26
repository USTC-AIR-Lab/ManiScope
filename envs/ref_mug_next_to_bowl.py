"""D4-06 · instruction structure · L2

RoboTwin source-task links: 11 hanging_mug, 48 stack_bowls_two
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class ref_mug_next_to_bowl(CompoScene):
    A_DESC = 'mug next to the bowl'
    MIRROR = True
    NEAREST = {'who': 'target', 'ref': 'bowl', 'rivals': ['distractor'], 'ratio': 1.6}
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'bowl',
             'kind': 'model',
             'model': '002_bowl',
             'ids': [1, 2, 3],
             'region': [[-0.06, 0.06], [-0.12, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.03,
             'rot': False,
             'zlim': [0.741]},
            {'role': 'target',
             'kind': 'model',
             'model': '039_mug',
             'ids': [0, 1, 2],
             'rel': 'bowl',
             'offset': [-0.1, 0, 0],
             'qpos': [0.707, 0.707, 0, 0],
             'desc': 'mug next to the bowl'},
            {'role': 'distractor',
             'kind': 'model',
             'model': '039_mug',
             'ids': [0, 1, 2],
             'region': [[0.15, 0.22], [-0.14, -0.04]],
             'qpos': [0.707, 0.707, 0, 0]}]
