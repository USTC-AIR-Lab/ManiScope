"""D5-11 · skill x skill (temporal) · L3 · 厨房备餐

用户提的 lift_pot 组合版：双臂各抓一个把手抬起，再一起送到垫子上松手

依赖的 RoboTwin 基础任务: 12 lift_pot, 16 move_stapler_pad
由 suite/table.py 生成，不要直接改这个文件。组合泛化测评专用，不用于训练。
"""
from ._compo_scene import CompoScene


class lift_pot_to_pad(CompoScene):
    A_DESC = 'pot'
    GOAL = {'type': 'dual_carry_to', 'ref': 'pad', 'dz': 0.06, 'eps': [0.09, 0.09]}
    SPEC = [{'role': 'target',
             'kind': 'urdf',
             'model': '060_kitchenpot',
             'ids': [0, 1],
             'fix_root': False,
             'region': [[-0.05, 0.05], [-0.05, 0.05]],
             'qpos': [0.704141, 0, 0, 0.71006],
             'rot': True,
             'rotlim': [0, 0, 0.39]},
            {'role': 'pad',
             'kind': 'box',
             'color': (0.45, 0.45, 0.45),
             'half_size': [0.055, 0.055, 0.0005],
             'region': [[0.09, 0.13], [-0.05, 0.05]],
             'rot': False,
             'zlim': [0.7415],
             'pad': 0.12,
             'desc': 'pad'}]
