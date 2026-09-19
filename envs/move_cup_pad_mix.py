"""D1-01 · mixture · L2 · 办公桌

混合维度：源场景 move_cup_pad + 一个语义无关的干扰物（071_can）。办公桌上多一个易拉罐。判据/指令/依赖全部继承源场景，只多干扰物 —— 和源场景的分差就是「干扰物 + 背景变化」这一维的代价。

依赖的 RoboTwin 基础任务: 16 move_stapler_pad
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class move_cup_pad_mix(CompoScene):
    A_DESC = 'cup'
    GOAL = {'type': 'on', 'ref': 'pad'}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '021_cup',
             'ids': [0, 1, 2, 3, 4, 5],
             'region': [[-0.05, 0.05], [-0.15, -0.06]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'pad',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half_size': [0.055, 0.055, 0.0005],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.15, -0.04]],
             'rot': False,
             'zlim': [0.7415],
             'pad': 0.12,
             'desc': 'pad'},
            {'role': 'mix_distractor',
             'kind': 'model',
             'model': '071_can',
             'ids': [0, 1, 2],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.14, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False,
             'pad': 0.06}]
