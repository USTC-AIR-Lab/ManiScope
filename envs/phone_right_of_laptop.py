"""D2-13 · skill x spatial · L2 · 办公桌

用户提的 open_laptop+放手机。开盖需要关节开度判据(暂无)，先做空间关系版

依赖的 RoboTwin 基础任务: 17 open_laptop, 36 place_phone_stand, 22 place_a2b_right
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class phone_right_of_laptop(CompoScene):
    A_DESC = 'phone'
    GOAL = {'type': 'rel', 'ref': 'laptop', 'dir': 'right', 'gap': [0.05, 0.22]}
    SPEC = [{'role': 'laptop',
             'kind': 'urdf',
             'model': '015_laptop',
             'ids': [0],
             'region': [[-0.06, 0.06], [-0.06, 0.04]],
             'qpos': [0.7, 0, 0, 0.7],
             'rot': False,
             'fix_root': True,
             'mass': 1.0,
             'pad': 0.08},
            {'role': 'target',
             'kind': 'model',
             'model': '077_phone',
             'ids': [0, 1, 2, 3],
             'rel': 'laptop',
             'offset': [0, 0, 0.07],
             'qpos': [0.5, 0.5, 0.5, 0.5],
             'desc': 'phone'}]
