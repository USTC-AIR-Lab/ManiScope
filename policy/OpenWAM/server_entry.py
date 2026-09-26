"""Launch the upstream OpenWAM server with a corrected bounded prompt-cache eviction path. Delete the oldest entry directly to avoid recursive __getitem__ calls during popitem."""
from collections import OrderedDict

from openwam.deploy import engine, server


def _setitem(self, key, value):
    OrderedDict.__setitem__(self, key, value)
    OrderedDict.move_to_end(self, key)
    while len(self) > self._maxsize:
        OrderedDict.__delitem__(self, next(iter(self)))      # Delete the oldest key directly; popitem would recurse through __getitem__.


def _getitem(self, key):
    value = OrderedDict.__getitem__(self, key)
    OrderedDict.move_to_end(self, key)
    return value


engine._BoundedPromptEmbedCache.__setitem__ = _setitem
engine._BoundedPromptEmbedCache.__getitem__ = _getitem

if __name__ == "__main__":
    server.main()
