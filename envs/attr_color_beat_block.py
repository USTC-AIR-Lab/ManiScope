"""D3-12 · attribute binding · L2

RoboTwin source-task links: 2 beat_block_hammer, 45 stack_blocks_three
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class attr_color_beat_block(CompoScene):
    A_DESC = 'purple block'
    SHUFFLE_SLOTS = ['target', 'd1', 'd2']
    GOAL = {'type': 'beat', 'tool': 'hammer'}
    SPEC = [{'role': 'hammer',
             'kind': 'model',
             'model': '020_hammer',
             'ids': [0],
             'region': [[-0.02, 0.02], [-0.08, -0.04]],
             'qpos': [0, 0, 0.995, 0.105],
             'rot': False,
             'zlim': [0.783],
             'mass': 0.001},
            {'role': 'target',
             'kind': 'box',
             'color': (0.55, 0.2, 0.75),
             'half': 0.025,
             'region': [[-0.22, -0.17], [0.01, 0.07]],
             'desc': 'purple block',
             'static': True,
             'zlim': [0.76]},
            {'role': 'd1',
             'kind': 'box',
             'color': (0.1, 0.65, 0.62),
             'half': 0.025,
             'region': [[-0.03, 0.03], [0.01, 0.07]],
             'static': True,
             'zlim': [0.76]},
            {'role': 'd2',
             'kind': 'box',
             'color': (0.92, 0.82, 0.15),
             'half': 0.025,
             'region': [[0.17, 0.22], [0.01, 0.07]],
             'static': True,
             'zlim': [0.76]}]
