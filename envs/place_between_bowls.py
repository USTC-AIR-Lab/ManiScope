"""D2-05 · skill x spatial · L3

RoboTwin source-task links: 21 place_a2b_left, 22 place_a2b_right, 48 stack_bowls_two
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class place_between_bowls(CompoScene):
    A_DESC = 'cube'
    GOAL = {'type': 'between', 'refs': ['b1', 'b2'], 'lat': 0.1}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '073_rubikscube',
             'ids': [0, 1, 2],
             'region': [[-0.05, 0.05], [-0.19, -0.14]],
             'qpos': [1, 0, 0, 0]},
            {'role': 'b1',
             'kind': 'model',
             'model': '002_bowl',
             'ids': [1, 2, 3],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.05, 0.03]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.05,
             'rot': False,
             'zlim': [0.741]},
            {'role': 'b2',
             'kind': 'model',
             'model': '002_bowl',
             'ids': [4, 5, 6],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.05, 0.03]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.05,
             'rot': False,
             'zlim': [0.741]}]
