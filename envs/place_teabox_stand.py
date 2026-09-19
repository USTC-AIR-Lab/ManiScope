"""D1-12 · skill x object · L2 · 书架

依赖的 RoboTwin 基础任务: 35 place_object_stand
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class place_teabox_stand(CompoScene):
    A_DESC = 'tea box'
    GOAL = {'type': 'on', 'ref': 'stand'}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '112_tea-box',
             'ids': [0, 1, 2],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'stand',
             'kind': 'model',
             'model': '074_displaystand',
             'ids': [0, 1, 2, 3, 4],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.15, -0.04]],
             'qpos': [0.707, 0.707, 0.0, 0.0],
             'static': True,
             'pad': 0.06,
             'rot': False,
             'zlim': [0.741]}]
