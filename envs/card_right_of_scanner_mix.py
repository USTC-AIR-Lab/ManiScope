"""D2-12 · mixture · L3 · 超市结账

混合维度：源场景 card_right_of_scanner + 一个语义无关的干扰物（071_can）。收银台上多一个易拉罐。判据/指令/依赖全部继承源场景，只多干扰物 —— 和源场景的分差就是「干扰物 + 背景变化」这一维的代价。

依赖的 RoboTwin 基础任务: 41 rotate_qrcode, 42 scan_object, 22 place_a2b_right
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class card_right_of_scanner_mix(CompoScene):
    A_DESC = 'payment card'
    GOAL = {'type': 'rel', 'ref': 'scanner', 'dir': 'right', 'gap': [0.05, 0.22], 'min_start': 0.18}
    SPEC = [{'role': 'target',
             'kind': 'model',
             'model': '070_paymentsign',
             'ids': [0, 1, 2],
             'region': [[-0.05, 0.05], [-0.19, -0.14]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False},
            {'role': 'scanner',
             'kind': 'model',
             'model': '024_scanner',
             'ids': [0, 1, 2, 3, 4],
             'region': [[-0.21000000000000002, -0.12000000000000001], [-0.05, 0.03]],
             'qpos': [0, 0, 0.707, 0.707],
             'static': True,
             'pad': 0.08,
             'rot': False,
             'zlim': [0.741]},
            {'role': 'mix_distractor',
             'kind': 'model',
             'model': '071_can',
             'ids': [0, 1, 2],
             'region': [[0.12000000000000001, 0.21000000000000002], [-0.14, -0.04]],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'rot': False,
             'pad': 0.06}]
