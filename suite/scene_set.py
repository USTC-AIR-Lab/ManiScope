# -*- coding: utf-8 -*-
"""场景全集的唯一入口：table.py 的手写表 + gen_scenes.py 的 D7 派生。

下游（gen_yaml / gen_checklist / gen_zh）一律从这里取，别再直接 import table ——
直接读 table 会漏掉派生出来的 *_mix 场景（踩过：D7 只剩 1 个）。
"""
import gen_scenes          # 导入时会把派生场景 extend 进 SCENES
from table import SCENES   # noqa: E402  —— 此时已含派生场景

__all__ = ["SCENES"]
