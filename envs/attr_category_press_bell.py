"""D3-10 · attribute binding · L1

RoboTwin source-task links: 6 click_bell, 5 click_alarmclock
Generated candidate from suite/table.py for evaluation, not training.
The checked-in release may include reviewed refinements; do not overwrite it blindly.
"""
from ._compo_scene import CompoScene


class attr_category_press_bell(CompoScene):
    A_DESC = 'bell'
    MIRROR = True
    GOAL = {'type': 'press', 'ref': 'target', 'model': '050_bell', 'cp': 0}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '050_bell',
             'ids': [0, 1],
             'region': [[-0.22, -0.14], [-0.15, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.3,
             'pad': 0.1,
             'desc': 'bell'},
            {'role': 'distractor',
             'kind': 'model',
             'model': '046_alarm-clock',
             'ids': [0, 1, 2],
             'region': [[0.14, 0.22], [-0.15, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'mass': 0.3,
             'pad': 0.1}]
