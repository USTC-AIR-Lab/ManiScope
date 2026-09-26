"""D5-06 · skill x skill (temporal) · L3

RoboTwin source-task links: 33 place_object_basket, 27 place_cans_plasticbox, 6 click_bell
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class pack_toycar_then_ring(CompoScene):
    A_DESC = 'toy car'
    GOAL = {'type': 'seq',
            'stages': [{'type': 'in', 'ref': 'box', 'r': 0.13},
                       {'type': 'press', 'ref': 'bell', 'model': '050_bell', 'cp': 0}]}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '057_toycar',
             'ids': [0, 1, 2, 3, 4, 5],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.707, 0.707, 0, 0],
             'desc': 'toy car'},
            {'role': 'box',
             'kind': 'model',
             'model': '062_plasticbox',
             'ids': [3, 5],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.02, 0.05]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.6,
             'pad': 0.05,
             'rot': False},
            {'role': 'bell',
             'kind': 'model',
             'model': '050_bell',
             'ids': [0, 1],
             'region': [[0.12000000000000001, 0.21000000000000002], [0.02, 0.08]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.3,
             'pad': 0.08}]
