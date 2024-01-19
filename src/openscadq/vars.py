"""
Variable storage
"""
from __future__ import annotations

import warnings


class Vars:
    """
    This is a quick-and-dirty hierarchical data storage.
    """

    def __init__(
        self, name: str | None = None, parent: Vars | None = None, init: dict | None = None,
    ):
        self._data = dict()
        self._p = parent
        self._name = name
        if init:
            self._data.update(init)

    def __contains__(self, k):
        return k in self._data

    def set(self, k, v):
        """force set a value even if otherwise immutable"""
        self._data[k] = v

    def child(self, name, init: dict | None = None):
        """return a sub-scope"""
        return Vars(name=name, parent=self, init=init)

    def inject(self, np: Vars):
        """inject values in "np" into the current list"""
        np = Vars(name=np._name, init=np._data)
        np._p = self._p
        self._p = np

    def __getitem__(self, k):
        try:
            res = self._data[k]
        except KeyError:
            try:
                if self._p is not None:
                    return self._p[k]
            except KeyError:
                pass
        else:
            return res
        raise KeyError(k, self._name) from None

    def __setitem__(self, k, v):
        if k in self._data:
            warnings.warn(f"Dup assignment of {k !r}")
        else:
            self._data[k] = v

    def __delitem__(self, k):
        raise RuntimeError(f"Deletion of {k !r}")
