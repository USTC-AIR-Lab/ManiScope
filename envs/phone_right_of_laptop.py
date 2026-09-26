"""D2-13 · skill x spatial · L2

RoboTwin source-task links: 17 open_laptop, 36 place_phone_stand, 22 place_a2b_right
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class phone_right_of_laptop(CompoScene):
    A_DESC = 'phone'
    GOAL = {'type': 'rel', 'ref': 'laptop', 'dir': 'right', 'gap': [0.05, 0.22]}
    SPEC = [{'role': 'laptop',
             'kind': 'urdf',
             'model': '015_laptop',
             'ids': [0],
             'region': [[-0.06, 0.06], [-0.06, 0.04]],
             'qpos': [0.7, 0, 0, 0.7],
             'rot': False,
             'fix_root': True,
             'mass': 1.0,
             'pad': 0.08},
            {'role': 'target',
             'kind': 'model',
             'model': '077_phone',
             'ids': [0, 1, 2, 3],
             'rel': 'laptop',
             'offset': [0, 0, 0.07],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'desc': 'phone'}]
