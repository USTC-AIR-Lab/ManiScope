"""D3-08 · attribute binding · L3

RoboTwin source-task links: 4 blocks_ranking_size, 28 place_container_plate
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class attr_size_rank_middle(CompoScene):
    A_DESC = 'medium block'
    SHUFFLE_SLOTS = ['target', 'd1', 'd2']
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'target',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half': 0.023,
             'region': [[-0.04, 0.04], [-0.13, -0.05]],
             'desc': 'medium block'},
            {'role': 'small',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half': 0.015,
             'region': [[-0.22, -0.17], [-0.13, -0.05]]},
            {'role': 'big',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half': 0.031,
             'region': [[0.17, 0.22], [-0.13, -0.05]]}]
