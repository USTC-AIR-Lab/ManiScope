"""D1-10 · skill x object · L1

RoboTwin source-task links: 8 grab_roller
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class grab_dumbbell(CompoScene):
    A_DESC = 'dumbbell'
    GOAL = {'type': 'lift', 'dz': 0.035}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '052_dumbbell',
             'ids': [0, 1, 2, 3, 4, 5, 6],
             'region': [[-0.22, -0.14], [-0.15, -0.04]],
             'qpos': [0.707, 0.707, 0, 0]}]
