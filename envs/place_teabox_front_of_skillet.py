"""D2-11 · skill x spatial · L2 · 厨房备餐

依赖的 RoboTwin 基础任务: 24 place_bread_skillet, 21 place_a2b_left
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class place_teabox_front_of_skillet(CompoScene):
    A_DESC = 'tea box'
    GOAL = {'type': 'rel', 'ref': 'skillet', 'dir': 'front', 'gap': [0.05, 0.22], 'lat': 0.14}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '112_tea-box',
             'ids': [0, 1, 2, 3, 4],
             'region': [[-0.05, 0.05], [-0.19, -0.14]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'skillet',
             'kind': 'model',
             'model': '106_skillet',
             'ids': [0, 1, 2, 3],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.05, 0.03]],
             'qpos': [0, 0, 0.707, 0.707],
             'static': True,
             'pad': 0.06,
             'rot': False,
             'zlim': [0.741]}]
