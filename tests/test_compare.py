from __future__ import annotations

import os
from functools import partial
from pathlib import Path

from openscadq import parse
from openscadq._test import testcase as reader


def _test(i):
    import tests.env_openscad as _env

    res = reader(i)

    # Compare the two. They must be (a) same size,
    # (b) occupy the same space.
    # We don't subtract them because that's liable to confuse OCC.
    # Instead we add them and make sure that the size doesn't change.
    # (Also, that's faster, because subtraction isn't symmetric.)

    if len(res) < 2:
        raise ValueError("Not enough results")

    if res.numeric:
        v = iter(res.models)
        try:
            vn = res.value
        except AttributeError:
            vn,vname = next(v)
            if callable(vn):
                breakpoint()
                vn=vn()
        else:
            vname = "preset"
        for vv,vvn in v:
            if callable(vv):
                vv=vv()
            assert abs(vn - vv) < res.tolerance, (vname,vn, vvn,vv)
        return

    v = [(x.volume,n) for x,n in res.models]
    mods = iter(res.models)
    msum = next(mods)[0]
    for m,n in mods:
        msum += m
    msum = msum.volume

    try:
        vn = res.volume
    except AttributeError:
        vn,vname = v.pop()
    else:
        vname = "preset"
    assert abs(msum - vn) < res.tolerance, (msum,vname,vn)
    for vv,vvn in v:
        assert abs(vn - vv) < res.tolerance, (vname,vn, vvn,vv)
        assert abs(msum - vv) < res.tolerance, (msum, vvn,vv)

_i = 0
_missing = 0
while True:
    _i += 1
    if not os.path.exists(f"tests/models/{_i :03d}.scad") and \
       not os.path.exists(f"tests/models/{_i :03d}.py"):
        _missing += 1
        if _missing > 10:
            break
        continue
    print("TEST", _i)
    globals()[f"test_{_i :03d}"] = partial(_test, _i)
