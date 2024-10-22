from __future__ import annotations

from pathlib import Path

from openscadq import parse


def testcase(i):
    import tests.env_openscad as _env

    env1 = parse(f"tests/models/{i :03d}.scad")
    m1 = env1["work"]()

    pyf = Path(f"tests/models/{i :03d}.py")
    py = pyf.read_text()
    pyc = compile(py, str(pyf), "exec")
    env2 = {}
    exec(pyc, _env.__dict__, env2)
    m2 = env2["work"]()

    return m1, m2
