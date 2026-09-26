"""D1-05 · skill x object · L2

RoboTwin source-task links: 2 beat_block_hammer, 8 grab_roller
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class grasp_mallet_novel(CompoScene):
    A_DESC = 'wooden mallet'
    GOAL = {'type': 'lift', 'dz': 0.035}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '084_woodenmallet',
             'ids': [0, 1, 2, 3, 4],
             'region': [[-0.22, -0.14], [-0.15, -0.04]],
             'qpos': [0.707, 0.707, 0, 0]}]
