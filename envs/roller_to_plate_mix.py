"""D1-16 · mixture · L3

RoboTwin source-task links: 8 grab_roller, 28 place_container_plate
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class roller_to_plate_mix(CompoScene):
    A_DESC = 'rolling pin'
    GOAL = {'type': 'on', 'ref': 'plate'}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '102_roller',
             'ids': [0, 1, 2],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'plate',
             'kind': 'model',
             'model': '003_plate',
             'ids': [0],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.15, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.05,
             'rot': False,
             'zlim': [0.741]},
            {'role': 'mix_distractor',
             'kind': 'model',
             'model': '112_tea-box',
             'ids': [0, 1, 2, 3],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.14, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False,
             'pad': 0.06}]
