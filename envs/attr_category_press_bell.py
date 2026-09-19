"""D3-10 · attribute binding · L1 · 前台服务

按压型动作上的属性绑定 —— 不涉及抓取，语言信号最干净

依赖的 RoboTwin 基础任务: 6 click_bell, 5 click_alarmclock
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
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
