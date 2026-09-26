"""D4-01 · instruction structure · L1

RoboTwin source-task links: 28 place_container_plate
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class ref_block_on_plate(CompoScene):
    A_DESC = 'block on the plate'
    MIRROR = True
    GOAL = {'type': 'lift', 'dz': 0.06}
    SPEC = [{'role': 'plate',
             'kind': 'model',
             'model': '003_plate',
             'ids': [0],
             'region': [[-0.06, 0.06], [-0.15, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.03,
             'rot': False,
             'zlim': [0.741]},
            {'role': 'target',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'rel': 'plate',
             'offset': [0, 0, 0.035],
             'desc': 'block on the plate'},
            {'role': 'distractor',
             'kind': 'box',
             'color': (0.95, 0.6, 0.1),
             'half': 0.025,
             'region': [[0.14, 0.22], [-0.15, -0.04]]}]
