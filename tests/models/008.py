
from __future__ import annotations

def work():
    return Box(2, 3, 4, align=(Align.CENTER,) * 3) - \
           Box(1, 99, 1, align=(Align.CENTER,) * 3)
