"""D1-01 · mixture · L2

RoboTwin source-task links: 16 move_stapler_pad
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class move_cup_pad_mix(CompoScene):
    A_DESC = 'cup'
    GOAL = {'type': 'on', 'ref': 'pad'}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '021_cup',
             'ids': [0, 1, 2, 3, 4, 5],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'pad',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half_size': [0.055, 0.055, 0.0005],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.15, -0.04]],
             'rot': False,
             'zlim': [0.7415],
             'pad': 0.12,
             'desc': 'pad'},
            {'role': 'mix_distractor',
             'kind': 'model',
             'model': '071_can',
             'ids': [0, 1, 2],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.14, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False,
             'pad': 0.06}]
