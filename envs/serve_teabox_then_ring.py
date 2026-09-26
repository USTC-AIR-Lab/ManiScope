"""D5-02 · skill x skill (temporal) · L2

RoboTwin source-task links: 23 place_bread_basket, 6 click_bell
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class serve_teabox_then_ring(CompoScene):
    A_DESC = 'tea box'
    GOAL = {'type': 'seq',
            'stages': [{'type': 'in', 'ref': 'breadbasket', 'r': 0.12},
                       {'type': 'press', 'ref': 'bell', 'model': '050_bell', 'cp': 0}]}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '112_tea-box',
             'ids': [0, 1, 2, 3],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'desc': 'tea box',
             'rot': False},
            {'role': 'breadbasket',
             'kind': 'model',
             'model': '110_basket',
             'ids': [0, 1, 2, 3],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.02, 0.05]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.5,
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
