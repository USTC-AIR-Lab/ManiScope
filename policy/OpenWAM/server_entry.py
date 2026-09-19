"""OpenWAM 官方 websocket 服务的启动壳：修 prompt 嵌入 LRU 缓存的淘汰 bug 后再进官方 main。

官方 openwam/deploy/engine.py 的 _BoundedPromptEmbedCache 在超过 maxsize 淘汰时（popitem -> 被重写的 __getitem__）
抛 KeyError，导致服务对某条新指令返回错误、eval 收到 500 而整场失败（本评测每场景 100 条指令各不相同，必然触发）。
这里用 OrderedDict 的原始方法做淘汰，语义不变（仍是 LRU、同 maxsize）。
"""
from collections import OrderedDict

from openwam.deploy import engine, server


def _setitem(self, key, value):
    OrderedDict.__setitem__(self, key, value)
    OrderedDict.move_to_end(self, key)
    while len(self) > self._maxsize:
        OrderedDict.__delitem__(self, next(iter(self)))      # popitem 会回调 __getitem__，改为直接删最旧键


def _getitem(self, key):
    value = OrderedDict.__getitem__(self, key)
    OrderedDict.move_to_end(self, key)
    return value


engine._BoundedPromptEmbedCache.__setitem__ = _setitem
engine._BoundedPromptEmbedCache.__getitem__ = _getitem

if __name__ == "__main__":
    server.main()
