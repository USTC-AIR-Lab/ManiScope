"""D2-12 · skill x spatial · L2

RoboTwin source-task links: 41 rotate_qrcode, 42 scan_object, 22 place_a2b_right
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class card_right_of_scanner(CompoScene):
    A_DESC = 'payment card'
    GOAL = {'type': 'rel', 'ref': 'scanner', 'dir': 'right', 'gap': [0.05, 0.22], 'min_start': 0.18}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '070_paymentsign',
             'ids': [0, 1, 2],
             'region': [[-0.05, 0.05], [-0.19, -0.14]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'scanner',
             'kind': 'model',
             'model': '024_scanner',
             'ids': [0, 1, 2, 3, 4],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.05, 0.03]],
             'qpos': [0, 0, 0.707, 0.707],
             'static': True,
             'pad': 0.08,
             'rot': False,
             'zlim': [0.741]}]
