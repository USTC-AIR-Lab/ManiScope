"""D1-16 · mixture · L3 · 厨房备餐

混合维度：源场景 roller_to_plate + 一个语义无关的干扰物（112_tea-box）。备餐台上多一个茶叶盒。判据/指令/依赖全部继承源场景，只多干扰物 —— 和源场景的分差就是「干扰物 + 背景变化」这一维的代价。

依赖的 RoboTwin 基础任务: 8 grab_roller, 28 place_container_plate
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class roller_to_plate_mix(CompoScene):
    A_DESC = 'rolling pin'
    GOAL = {'type': 'on', 'ref': 'plate'}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '102_roller',
             'ids': [0, 1, 2],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'plate',
             'kind': 'model',
             'model': '003_plate',
             'ids': [0],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.15, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'static': True,
             'pad': 0.05,
             'rot': False,
             'zlim': [0.741]},
            {'role': 'mix_distractor',
             'kind': 'model',
             'model': '112_tea-box',
             'ids': [0, 1, 2, 3],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.14, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False,
             'pad': 0.06}]
