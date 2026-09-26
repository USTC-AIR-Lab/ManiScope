"""D1-07 · skill x object · L1

RoboTwin source-task links: 34 place_object_scale
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class place_teabox_scale(CompoScene):
    A_DESC = 'tea box'
    GOAL = {'type': 'on', 'ref': 'scale'}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '112_tea-box',
             'ids': [0, 1, 2, 3, 4, 5],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'scale',
             'kind': 'model',
             'model': '072_electronicscale',
             'ids': [0, 1, 2],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.15, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.06,
             'rot': False,
             'zlim': [0.741]}]
