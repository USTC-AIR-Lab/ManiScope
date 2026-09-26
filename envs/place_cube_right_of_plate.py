"""D2-06 · skill x spatial · L2

RoboTwin source-task links: 21 place_a2b_left, 22 place_a2b_right, 28 place_container_plate
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class place_cube_right_of_plate(CompoScene):
    A_DESC = 'cube'
    GOAL = {'type': 'rel', 'ref': 'plate', 'dir': 'right', 'gap': [0.14, 0.26], 'lat': 0.13}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '073_rubikscube',
             'ids': [0, 1, 2],
             'region': [[-0.05, 0.05], [-0.19, -0.14]],
             'qpos': [1, 0, 0, 0]},
            {'role': 'plate',
             'kind': 'model',
             'model': '003_plate',
             'ids': [0],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.05, 0.03]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.05,
             'rot': False,
             'zlim': [0.741]}]
