"""D2-08 · mixture · L3

RoboTwin source-task links: 33 place_object_basket, 21 place_a2b_left
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class put_toycar_left_basket_mix(CompoScene):
    A_DESC = 'toy car'
    GOAL = {'type': 'in', 'ref': 'basket_l', 'r': 0.12}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '057_toycar',
             'ids': [0, 1, 2, 3, 4, 5],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.707, 0.707, 0, 0]},
            {'role': 'basket_l',
             'kind': 'model',
             'model': '110_basket',
             'ids': [0, 1],
             'region': [[-0.21000000000000002, -0.12000000000000001], [0.0, 0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.5,
             'pad': 0.05,
             'rot': False},
            {'role': 'basket_r',
             'kind': 'model',
             'model': '110_basket',
             'ids': [2, 3],
             'region': [[0.15000000000000002, 0.24], [0.0, 0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.5,
             'pad': 0.05,
             'side': 1,
             'side_x': 0.195,
             'rot': False},
            {'role': 'mix_distractor',
             'kind': 'model',
             'model': '112_tea-box',
             'ids': [0, 1, 2, 3],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.14, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False,
             'pad': 0.06}]
