from __future__ import annotations

import os
from functools import partial
from pathlib import Path

from openscadq import parse


def _test(i):
    import tests.env_openscad as _env

    # Get the OpenSCAD part

    env1 = parse(f"tests/models/{i :03d}.scad")
    try:
        m1 = env1["work"]
    except KeyError:
        # Oh well. Gathering toplevel elements.
        from openscadq.eval import Eval

        ev = Eval(env1)
        m1 = ev.union(env1["_e_children"])

    else:
        m1 = m1()

    # Get the Python part

    pyf = Path(f"tests/models/{i :03d}.py")
    py = pyf.read_text()
    pyc = compile(py, str(pyf), "exec")
    env2 = {}
    exec(pyc, _env.__dict__, env2)
    m2 = env2["work"]()
    tol = env2.get("tolerance", 0.001)

    # Compare the two. They must be (a) same size,
    # (b) occupy the same space.
    # We don't subtract them because that's liable to confuse OCC.
    # Instead we add them and make sure that the size doesn't change.
    # (Also, that's faster, because subtraction isn't symmetric.)

    v1 = m1.volume
    v2 = m2.volume
    assert abs(v1 - v2) < tol

    m12 = m1 + m2
    v12 = m12.volume
    assert abs(v12 - v1) < tol
    assert abs(v12 - v2) < tol


_i = 0
while True:
    _i += 1
    if not os.path.exists(f"tests/models/{_i :03d}.scad"):
        break
    print("TEST", _i)
    globals()[f"test_{_i :03d}"] = partial(_test, _i)
