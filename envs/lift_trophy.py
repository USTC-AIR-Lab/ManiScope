"""D1-09 · skill x object · L2

RoboTwin source-task links: 8 grab_roller
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class lift_trophy(CompoScene):
    A_DESC = 'trophy'
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '090_trophy',
             'ids': [0, 1, 2, 3, 4],
             'region': [[-0.22, -0.14], [-0.15, -0.04]],
             'qpos': [1, 0, 0, 0],
             'mass': 0.2}]
